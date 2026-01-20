"""Rule-based intent detection based on the Phase-1 PRD."""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Pattern

from .types import IntentResult


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace for deterministic matching."""
    lowered = text.lower()
    cleaned = re.sub(r"[^a-z0-9\s\-/\.]", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


@dataclass
class RuleDefinition:
    intent: str
    must_include_all: List[str] = field(default_factory=list)
    must_include_any: List[str] = field(default_factory=list)
    regexes: List[Pattern[str]] = field(default_factory=list)
    entity_patterns: Dict[str, Pattern[str]] = field(default_factory=dict)
    reason: str = ""

    def matches(self, normalized_text: str) -> bool:
        if self.must_include_all and not all(k in normalized_text for k in self.must_include_all):
            return False
        if self.must_include_any and not any(k in normalized_text for k in self.must_include_any):
            return False
        if self.regexes and not any(p.search(normalized_text) for p in self.regexes):
            return False
        return True

    def extract_entities(self, original_text: str) -> Dict[str, str]:
        entities: Dict[str, str] = {}
        for name, pattern in self.entity_patterns.items():
            match = pattern.search(original_text)
            if match and name in match.groupdict():
                entities[name] = match.group(name)
        return entities


class RuleBasedIntentDetector:
    """Deterministic, low-latency intent detector using keywords and patterns."""

    def __init__(self) -> None:
        self.rules = self._build_rules()

    def detect(self, text: str) -> Optional[IntentResult]:
        normalized = _normalize(text)
        for rule in self.rules:
            if rule.matches(normalized):
                entities = rule.extract_entities(text)
                return IntentResult(
                    intent=rule.intent,
                    confidence=1.0,
                    source="rule",
                    entities=entities,
                    reason=rule.reason or f"Rule matched for intent '{rule.intent}'.",
                )
        return None

    def _build_rules(self) -> List[RuleDefinition]:
        """Rules derived from the PRD-supported Phase-1 actions."""
        branch_pattern = re.compile(r"\b(?:branch|checkout|switch|to)\s+(?P<branch>[A-Za-z0-9._\-/]+)")
        push_pattern = re.compile(r"\b(?:push|publish|send)\s+(?P<branch>[A-Za-z0-9._\-/]+)")

        return [
            RuleDefinition(
                intent="undo_commit_soft",
                must_include_any=[
                    "undo last commit",
                    "undo previous commit",
                    "soft reset",
                    "reset soft",
                    "uncommit",
                ],
                regexes=[
                    re.compile(r"\bundo\b.*\bcommit\b"),
                    re.compile(r"\breset\b.*\bsoft\b"),
                ],
                reason="Explicit request to undo the last commit while keeping changes.",
            ),
            RuleDefinition(
                intent="commit_changes",
                must_include_any=[
                    "commit",
                    "save changes",
                    "record changes",
                ],
                regexes=[
                    re.compile(r"\bcommit\b"),
                    re.compile(r"\bsave\b.*\bchanges\b"),
                ],
                reason="User asked to create a commit.",
            ),
            RuleDefinition(
                intent="create_branch",
                must_include_any=[
                    "create branch",
                    "new branch",
                    "make branch",
                ],
                regexes=[re.compile(r"\b(create|make|new)\b.*\bbranch\b")],
                entity_patterns={"branch": branch_pattern},
                reason="User asked to create a branch.",
            ),
            RuleDefinition(
                intent="switch_branch",
                must_include_any=[
                    "switch branch",
                    "checkout",
                    "change branch",
                    "go to branch",
                ],
                regexes=[re.compile(r"\b(switch|checkout|change|go)\b.*\bbranch\b")],
                entity_patterns={"branch": branch_pattern},
                reason="User asked to switch branches.",
            ),
            RuleDefinition(
                intent="push_branch",
                must_include_any=[
                    "push branch",
                    "publish branch",
                    "send branch",
                ],
                regexes=[re.compile(r"\b(push|publish|send)\b.*\bbranch\b")],
                entity_patterns={"branch": push_pattern},
                reason="User asked to push a branch to origin.",
            ),
            RuleDefinition(
                intent="push_commit_to_origin",
                must_include_any=[
                    "push commit",
                    "push changes",
                    "send changes",
                ],
                regexes=[re.compile(r"\bpush\b.*\b(origin|remote|commit|changes)\b")],
                reason="User asked to push commits to the remote origin.",
            ),
        ]

