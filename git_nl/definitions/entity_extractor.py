"""Shared entity extraction for branch, message, and target (commit-ish) slots."""

from __future__ import annotations

import re
import shlex
from typing import Dict, Tuple

# Allowed characters for git ref/branch-style tokens.
_REF_CHARS = r"[A-Za-z0-9._\-/~^]+"
_REF_PATTERN = re.compile(rf"^{_REF_CHARS}$")

# Reusable phrase-based patterns (kept small and readable).
_MESSAGE_PATTERN = re.compile(
    r"\b(?:with\s+(?:the\s+)?message|message|msg)\s+(?P<message>['\"`]?[^'\"`]+['\"`]?)",
    re.IGNORECASE,
)

_BRANCH_PATTERNS = [
    # Explicit branch mentions.
    re.compile(r"\bbranch\s+(?:called|named|with\s+name\s+)?(?P<branch>[_A-Za-z0-9.\-/]+)", re.IGNORECASE),
    # Create branch phrasing, allow optional article and naming words.
    re.compile(
        r"\b(?:create|make|new)\s+(?:a\s+)?branch(?:\s+(?:called|named|with\s+name))?\s+(?P<branch>[_A-Za-z0-9.\-/]+)",
        re.IGNORECASE,
    ),
    # Switch/checkout phrasing even with filler words before "branch".
    re.compile(
        r"\b(?:switch|checkout|change|go)\b.*?\bbranch\s+(?P<branch>[_A-Za-z0-9.\-/]+)",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:push|publish|send)\s+(?:my\s+)?branch\s+(?P<branch>[_A-Za-z0-9.\-/]+)", re.IGNORECASE),
    # Allow extra words between pull verb and origin.
    re.compile(r"\b(?:pull|sync|update)\b.*?\borigin\s+(?P<branch>[_A-Za-z0-9.\-/]+)", re.IGNORECASE),
    re.compile(r"\brebase\b.*\b(?:onto|on|with|against)\s+(?P<branch>[_A-Za-z0-9.\-/~^]+)", re.IGNORECASE),
    # Fallback for terse commands like "checkout main" or "switch develop".
    re.compile(r"\b(?:checkout|switch|go)\s+(?P<branch>[_A-Za-z0-9.\-/]+)\b", re.IGNORECASE),
]

_TARGET_PATTERNS = [
    re.compile(r"\breset\b.*?\bto\s+(?P<target>[_A-Za-z0-9.\-/~^]+)", re.IGNORECASE),
    re.compile(r"\breset\s+(?:--)?(?:soft|hard)?\s*(?P<target>[_A-Za-z0-9.\-/~^]+)", re.IGNORECASE),
    re.compile(r"\b(?P<target>HEAD[~^][A-Za-z0-9._\-/~^]*)", re.IGNORECASE),
]


def _safe_split(text: str) -> Tuple[list[str], bool]:
    """Split respecting quotes; return tokens and whether parsing succeeded."""
    try:
        tokens = shlex.split(text, posix=True)
        return tokens, True
    except ValueError:
        # Unbalanced quotes – fall back to a simple split.
        return text.split(), False


def _strip_wrapping(value: str) -> str:
    """Trim surrounding quotes/backticks/brackets and whitespace."""
    value = value.strip()
    value = value.strip('`"\'')
    value = value.strip("[]()")
    return value.strip()


def _is_valid_ref(value: str) -> bool:
    return bool(value) and bool(_REF_PATTERN.fullmatch(value))


def _set_value(bucket: Dict[str, str], key: str, raw_value: str, validate_ref: bool = False, overwrite: bool = False) -> None:
    if key in bucket and not overwrite:
        return
    cleaned = _strip_wrapping(raw_value)
    if not cleaned:
        return
    if validate_ref and not _is_valid_ref(cleaned):
        return
    bucket[key] = cleaned


def _parse_flags(text: str) -> Tuple[Dict[str, str], str]:
    """Extract entities from CLI-style flags; return (entities, remaining_text)."""
    tokens, _ = _safe_split(text)
    captured: Dict[str, str] = {}
    remaining: list[str] = []

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        low = tok.lower()

        def take_next() -> str | None:
            nonlocal i
            if i + 1 < len(tokens):
                i += 1
                return tokens[i]
            return None

        # Commit message flags.
        if low.startswith("--message="):
            _set_value(captured, "message", tok.split("=", 1)[1])
        elif low in {"--message", "--msg", "-m"}:
            nxt = take_next()
            if nxt:
                _set_value(captured, "message", nxt)
        elif low.startswith("-m") and len(tok) > 2:
            _set_value(captured, "message", tok[2:])

        # Branch flags.
        elif low.startswith("--branch="):
            _set_value(captured, "branch", tok.split("=", 1)[1], validate_ref=True)
        elif low in {"--branch", "-b"}:
            nxt = take_next()
            if nxt:
                _set_value(captured, "branch", nxt, validate_ref=True)
        elif low.startswith("-b") and len(tok) > 2:
            _set_value(captured, "branch", tok[2:], validate_ref=True)

        # Target flags (reset/rebase target).
        elif low.startswith("--target=") or low.startswith("--to=") or low.startswith("--onto="):
            _, _, val = tok.partition("=")
            _set_value(captured, "target", val, validate_ref=True)
        elif low in {"--target", "--to", "--onto"}:
            nxt = take_next()
            if nxt:
                _set_value(captured, "target", nxt, validate_ref=True)

        else:
            remaining.append(tok)
        i += 1

    remaining_text = " ".join(remaining).strip()
    return captured, remaining_text


def _apply_patterns(text: str, captured: Dict[str, str]) -> Dict[str, str]:
    """Apply fallback patterns where flags were absent."""
    if "message" not in captured:
        msg_match = _MESSAGE_PATTERN.search(text)
        if msg_match and msg_match.group("message"):
            _set_value(captured, "message", msg_match.group("message"))

    if "branch" not in captured:
        best_branch = None
        best_pos = -1
        for pat in _BRANCH_PATTERNS:
            for m in pat.finditer(text):
                if not m:
                    continue
                val = m.group("branch")
                if not val:
                    continue
                cleaned = _strip_wrapping(val)
                if not _is_valid_ref(cleaned):
                    continue
                pos = m.start("branch")
                if pos >= best_pos:
                    best_pos = pos
                    best_branch = cleaned
        if best_branch:
            _set_value(captured, "branch", best_branch, validate_ref=False, overwrite=True)

    if "target" not in captured:
        best_target = None
        best_pos = -1
        stopwords = {"everything", "changes", "work"}
        for pat in _TARGET_PATTERNS:
            for m in pat.finditer(text):
                if not m:
                    continue
                val = m.group("target")
                if not val:
                    continue
                cleaned = _strip_wrapping(val)
                if not _is_valid_ref(cleaned):
                    continue
                if cleaned.lower() in stopwords:
                    continue
                pos = m.start("target")
                if pos >= best_pos:
                    best_pos = pos
                    best_target = cleaned
        if best_target:
            _set_value(captured, "target", best_target, validate_ref=False, overwrite=True)

    return captured


def extract_entities(text: str) -> Dict[str, str]:
    """Extract commit message, branch, and target/ref from user text."""
    initial, remaining = _parse_flags(text)
    # Prefer original text for phrase patterns to avoid duplication artifacts.
    return _apply_patterns(text, initial.copy())
