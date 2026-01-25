"""Semantic similarity intent detector using a small in-memory catalog."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from git_nl import config
from .types import IntentResult


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace for deterministic matching."""
    import re

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


def _strip_entities(text: str) -> str:
    """Remove or neutralize user-supplied entity fragments (message, branch names)."""
    import re

    # Remove commit message clauses.
    text = re.sub(r"\b(with\s+(the\s+)?)?message\s+['\"]?[^'\"]+['\"]?", " ", text, flags=re.IGNORECASE)

    # Normalize branch-name mentions to a generic token so entity strings don't sway similarity.
    branch_patterns = [
        r"\b(create|make|new)\s+(?:a\s+)?branch\s+(called|named)?\s*[A-Za-z0-9._\-/]+",
        r"\b(switch|checkout|change|go)\s+(to\s+)?(?:the\s+)?branch\s+[A-Za-z0-9._\-/]+",
        r"\b(push|publish|send)\s+(?:my\s+)?branch\s+[A-Za-z0-9._\-/]+",
    ]
    for pat in branch_patterns:
        text = re.sub(pat, r"\1 branch", text, flags=re.IGNORECASE)

    return text


def _tokenize(text: str) -> List[str]:
    return _normalize(text).split()


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _l2_normalize(vector: List[float]) -> List[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0:
        return vector
    return [x / norm for x in vector]


# Extensive catalog per PRD examples; expand as needed for coverage.
SEMANTIC_CATALOG: Dict[str, List[str]] = {
    "commit_changes": [
        "commit my changes",
        "save all current changes",
        "record the changes I have made",
        "check in my work",
        "create a commit for the current work",
        "commit everything that is staged",
    ],
    
    "undo_commit_soft": [
        "undo last commit",
        "undo my previous commit but keep the changes",
        "remove the most recent commit without losing work",
        "get rid of the last commit and keep my files",
        "I want to undo the last commit but keep everything staged",
        "soft reset the previous commit",
    ],

    "push_commit_to_origin": [
        "push the latest commit to origin",
        "send my last commit to the remote",
        "upload the most recent commit",
        "push just the commit, not the whole branch",
        "push my commit upstream",
        "send the current commit",
        "push commits to origin",
    ],

    "create_branch": [
        "create a new branch",
        "make a new branch for this feature",
        "start working on a new branch",
        "create a branch called login-fix",
        "I want to create a separate branch for this work",
        "make another branch from the current one",
    ],

    "switch_branch": [
        "switch to the main branch",
        "checkout the develop branch",
        "change branch to release",
        "move to the feature branch",
        "I want to switch to a different branch",
        "go to the main branch now",
    ],

    "push_branch": [
        "push my branch to origin",
        "publish the current branch",
        "send this branch upstream",
        "push the feature branch",
        "upload my branch to the remote",
        "push the branch I am on",
    ],
}



@dataclass
class SemanticExample:
    intent: str
    text: str
    embedding: List[float]


@dataclass
class SemanticMatch:
    intent: str
    text: str
    score: float


def _build_vocab(catalog: Dict[str, List[str]]) -> List[str]:
    vocab_set = set()
    for phrases in catalog.values():
        for phrase in phrases:
            vocab_set.update(_tokenize(phrase))
    return sorted(vocab_set)


def _build_examples(catalog: Dict[str, List[str]], vocab: List[str]) -> List[SemanticExample]:
    examples: List[SemanticExample] = []
    for intent, phrases in catalog.items():
        for phrase in phrases:
            embedding = _embed(phrase, vocab)
            examples.append(SemanticExample(intent=intent, text=phrase, embedding=embedding))
    return examples


def _embed(text: str, vocab: List[str]) -> List[float]:
    tokens = _tokenize(text)
    counts: Dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    vector = [float(counts.get(term, 0)) for term in vocab]
    return _l2_normalize(vector)


# Build the embedding store once at import time so the catalog grows with code changes.
_PRECOMPUTED_VOCAB = _build_vocab(SEMANTIC_CATALOG)
_PRECOMPUTED_EXAMPLES = _build_examples(SEMANTIC_CATALOG, _PRECOMPUTED_VOCAB)


class SemanticIntentDetector:
    """Local embedding-based matcher against a curated catalog."""

    def __init__(
        self,
        catalog: Dict[str, List[str]] | None = None,
        precomputed_vocab: List[str] | None = None,
        precomputed_examples: List[SemanticExample] | None = None,
    ) -> None:
        self.catalog = catalog or SEMANTIC_CATALOG
        if precomputed_vocab is not None and precomputed_examples is not None:
            self.vocab = precomputed_vocab
            self.examples = precomputed_examples
        else:
            self.vocab = _build_vocab(self.catalog)
            self.examples = _build_examples(self.catalog, self.vocab)

    def score(self, text: str) -> SemanticMatch | None:
        """Return the best catalog match regardless of threshold."""
        normalized = _normalize(_strip_entities(text))
        query_vec = self._embed(normalized, self.vocab)
        if not any(query_vec):
            return None

        best_example: SemanticExample | None = None
        best_score = -1.0
        for example in self.examples:
            score = _cosine_similarity(query_vec, example.embedding)
            if score > best_score:
                best_example = example
                best_score = score

        if best_example is None:
            return None
        return SemanticMatch(intent=best_example.intent, text=best_example.text, score=best_score)

    def detect(self, text: str) -> IntentResult | None:
        match = self.score(text)
        if not match:
            return None

        threshold = config.SEMANTIC_CONFIDENCE_BY_INTENT.get(
            match.intent, config.SEMANTIC_CONFIDENCE_THRESHOLD
        )
        if match.score < threshold:
            return None

        return IntentResult(
            intent=match.intent,
            confidence=match.score,
            source="semantic",
            entities={},
            reason=(
                f"Matched semantic example '{match.text}' with similarity {match.score:.2f}; "
                f"threshold {threshold:.2f}."
            ),
        )

    def _embed(self, text: str, vocab: List[str]) -> List[float]:
        return _embed(text, vocab)


# Shared detector so callers don’t rebuild per instance.
SEMANTIC_DETECTOR = SemanticIntentDetector(
    catalog=SEMANTIC_CATALOG, precomputed_vocab=_PRECOMPUTED_VOCAB, precomputed_examples=_PRECOMPUTED_EXAMPLES
)

