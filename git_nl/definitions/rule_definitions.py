"""Rule-based intent detection based - defines every rule intent, must include keywords, regex and reason. rename to rule_definitions.py. rename folder to definitions"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Pattern

from git_nl import config
from .entity_extractor import extract_entities
from .types import IntentResult


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace for deterministic matching."""
    CONTRACTIONS = {
        "i've": "i have",
        "ive": "i have",
        "can't": "cannot",
        "don't": "do not",
    }

    lowered = text.lower()
    for k, v in CONTRACTIONS.items():
        lowered = re.sub(rf"\b{k}\b", v, lowered)

    cleaned = re.sub(r"[^a-z0-9\s\-/\.]", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


@dataclass
class RuleDefinition:
    intent: str
    exact_phrases: List[str] = field(default_factory=list)
    fullmatch_regexes: List[Pattern[str]] = field(default_factory=list)
    reason: str = ""

    def matches(self, normalized_text: str) -> bool:
        """Return True only when there is an exact phrase or full-string regex match."""
        if self.exact_phrases and normalized_text in self.exact_phrases:
            return True
        for pattern in self.fullmatch_regexes:
            if pattern.fullmatch(normalized_text):
                return True
        return False


# Entities we care about per intent (used to filter extractor output).
_ALLOWED_ENTITIES: Dict[str, set[str]] = {
    "commit_changes": {"message"},
    "stash_changes": {"message"},
    "create_branch": {"branch"},
    "switch_branch": {"branch"},
    "push_branch": {"branch"},
    "pull_origin": {"branch"},
    "rebase_branch": {"branch"},
    "reset_soft": {"target"},
    "reset_hard": {"target"},
    "push_commit_to_origin": set(),
    "undo_commit_soft": set(),
    # Intents without entities keep the extractor output empty.
}


def extract_entities_for_intent(intent: str, text: str) -> Dict[str, str]:
    """Extract entities and filter them to the fields allowed for the intent."""
    all_entities = extract_entities(text)
    allowed = _ALLOWED_ENTITIES.get(intent)
    if allowed is None:
        return all_entities
    if not allowed:
        return {}
    return {k: v for k, v in all_entities.items() if k in allowed}


class RuleBasedIntentDetector:
    """Deterministic, low-latency intent detector using keywords and patterns."""

    def __init__(self) -> None:
        self.rules = self._build_rules()

    def detect(self, text: str) -> Optional[IntentResult]:
        normalized = _normalize(text)
        for rule in self.rules:
            if rule.matches(normalized):
                entities = self._extract_for_intent(rule.intent, text)
                # Default branch handling when the user omitted a branch name.
                branch_intents = {"create_branch", "switch_branch", "push_branch", "pull_origin", "rebase_branch"}
                if rule.intent in branch_intents:
                    missing_branch = not entities.get("branch") or entities.get("branch", "").lower() == "branch"
                    if missing_branch:
                        entities["branch"] = config.DEFAULT_BRANCH
                        reason = f"Branch name not provided; defaulting to '{config.DEFAULT_BRANCH}' unless a name is specified."
                    else:
                        reason = rule.reason or f"Rule matched for intent '{rule.intent}'."
                else:
                    reason = rule.reason or f"Rule matched for intent '{rule.intent}'."

                return IntentResult(
                    intent=rule.intent,
                    confidence=1.0,
                    source="rule",
                    entities=entities,
                    reason=reason,
                )
        return None

    def _extract_for_intent(self, intent: str, text: str) -> Dict[str, str]:
        """Shared extraction, filtered to the entities relevant for the intent."""
        return extract_entities_for_intent(intent, text)

    def _build_rules(self) -> List[RuleDefinition]:
        """Rules derived from the PRD-supported Phase-1 actions."""
        return [
            RuleDefinition(
                intent="commit_changes",
                exact_phrases=[
                    "commit",
                    "commit changes",
                    "save changes",
                    "record changes",
                ],
                fullmatch_regexes=[
                    re.compile(r"commit", re.IGNORECASE),
                    re.compile(r"save changes", re.IGNORECASE),
                    re.compile(r"record changes", re.IGNORECASE),
                    # Broader match: any sentence containing commit/save/record (captures message if present).
                    re.compile(r".*\b(commit|save|record)\b.*", re.IGNORECASE),
                ],
                reason="User asked to create a commit.",
            ),
            RuleDefinition(
                intent="undo_commit_soft",
                exact_phrases=[
                    "undo last commit",
                    "undo previous commit",
                    "soft reset",
                    "reset soft",
                    "uncommit",
                ],
                reason="Explicit request to undo the last commit while keeping changes.",
            ),
            RuleDefinition(
                intent="push_commit_to_origin",
                exact_phrases=[
                    "push commit",
                    "push the commit",
                    "push my commit",
                    "push this commit",
                    "push latest commit",
                    "push commit to origin",
                    "push commit to remote",
                    "push changes",
                    "send changes",
                ],
                fullmatch_regexes=[
                    re.compile(r"(push|send)\s+(latest\s+)?commit(\s+to\s+(origin|remote))?", re.IGNORECASE)
                ],
                reason="User asked to push commits to the remote origin.",
            ),
            RuleDefinition(
                intent="create_branch",
                exact_phrases=[
                    "create branch",
                    "new branch",
                    "make branch",
                ],
                fullmatch_regexes=[
                    re.compile(r"(create|make|new)\s+branch\s+(?P<branch>[a-z0-9._\-/]+)", re.IGNORECASE),
                    re.compile(r"(create|make|new)\s+branch", re.IGNORECASE),
                    # Broader: any sentence asking to create/make a branch, capturing the branch name.
                    re.compile(
                        r".*\b(create|make|new)\s+(?:a\s+)?branch(?:\s+(?:called|named|with\s+name))?\s+(?P<branch>[A-Za-z0-9._\-/]+).*",
                        re.IGNORECASE,
                    ),
                ],
                reason="User asked to create a branch.",
            ),
            RuleDefinition(
                intent="switch_branch",
                exact_phrases=[
                    "switch branch",
                    "checkout branch",
                    "change branch",
                    "go to branch",
                ],
                fullmatch_regexes=[
                    re.compile(r"(switch|checkout|change|go)\s+(to\s+)?branch\s+(?P<branch>[A-Za-z0-9._\-/]+)", re.IGNORECASE),
                    re.compile(r"(switch|checkout|change|go)\s+(to\s+)?branch", re.IGNORECASE),
                    re.compile(
                        r".*\b(switch|checkout|change|go)\s+(?:to\s+)?(?:the\s+)?branch(?:\s+(?:called|named|with\s+name))?\s+(?P<branch>[A-Za-z0-9._\-/]+).*",
                        re.IGNORECASE,
                    ),
                ],
                reason="User asked to switch branches.",
            ),
            RuleDefinition(
                intent="push_branch",
                exact_phrases=[
                    "push branch",
                    "publish branch",
                    "send branch",
                ],
                fullmatch_regexes=[
                    re.compile(r"(push|publish|send)\s+branch\s+(?P<branch>[A-Za-z0-9._\-/]+)", re.IGNORECASE),
                    re.compile(
                        r".*\b(push|publish|send)\s+(?:my\s+)?branch(?:\s+(?:called|named|with\s+name))?\s+(?P<branch>[A-Za-z0-9._\-/]+).*",
                        re.IGNORECASE,
                    ),
                ],
                reason="User asked to push a branch to origin.",
            ),
            RuleDefinition(
                intent="pull_origin",
                exact_phrases=[
                    "pull",
                    "pull origin",
                    "pull latest",
                    "git pull",
                    "sync with origin",
                ],
                fullmatch_regexes=[
                    re.compile(r"(git\s+)?pull(\s+origin(\s+(?P<branch>[A-Za-z0-9._\-/]+))?)?", re.IGNORECASE),
                    re.compile(
                        r"(pull|sync|update)\s+(from\s+)?origin(\s+(?P<branch>[A-Za-z0-9._\-/]+))?", re.IGNORECASE
                    ),
                ],
                reason="User asked to pull the latest changes from origin.",
            ),
            RuleDefinition(
                intent="stash_changes",
                exact_phrases=[
                    "stash",
                    "stash changes",
                    "stash my changes",
                    "stash work",
                    "stash current work",
                ],
                fullmatch_regexes=[
                    re.compile(r"(git\s+)?stash(\s+push)?", re.IGNORECASE),
                    re.compile(r"(stash|save)\s+(my\s+)?changes", re.IGNORECASE),
                    re.compile(r"stash\s+(current\s+)?work", re.IGNORECASE),
                ],
                reason="User asked to stash their uncommitted changes.",
            ),
            RuleDefinition(
                intent="rebase_branch",
                exact_phrases=[
                    "rebase",
                    "rebase branch",
                    "rebase onto main",
                    "rebase with main",
                ],
                fullmatch_regexes=[
                    re.compile(
                        r"rebase\s+(?:onto|on|with|against)\s+(?P<branch>[A-Za-z0-9._\-/]+)", re.IGNORECASE
                    ),
                    re.compile(r"rebase(\s+branch)?(\s+(?P<branch>[A-Za-z0-9._\-/]+))?", re.IGNORECASE),
                ],
                reason="User asked to rebase the current branch onto another branch.",
            ),
            RuleDefinition(
                intent="reset_soft",
                exact_phrases=[
                    "soft reset",
                    "reset soft",
                    "reset --soft",
                    "soft reset last commit",
                ],
                fullmatch_regexes=[
                    re.compile(
                        r"(soft\s+reset|reset\s+(?:--)?soft)(\s+to\s+(?P<target>[A-Za-z0-9._\-/~^]+))?",
                        re.IGNORECASE,
                    ),
                    re.compile(
                        r"(undo|revert)\s+last\s+commit(\s+soft(ly)?)?",
                        re.IGNORECASE,
                    ),
                ],
                reason="User asked to soft reset to a previous commit while keeping changes staged.",
            ),
            RuleDefinition(
                intent="reset_hard",
                exact_phrases=[
                    "hard reset",
                    "reset hard",
                    "reset --hard",
                    "discard my changes",
                ],
                fullmatch_regexes=[
                    re.compile(
                        r"(hard\s+reset|reset\s+(?:--)?hard)(\s+to\s+(?P<target>[A-Za-z0-9._\-/~^]+))?",
                        re.IGNORECASE,
                    ),
                    re.compile(r"(discard|drop)\s+changes", re.IGNORECASE),
                ],
                reason="User asked to hard reset and discard local changes.",
            ),
        ]

