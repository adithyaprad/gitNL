"""Intent routing orchestrating rule, semantic, and LLM fallback (stubs)."""

from typing import Optional

from git_nl import config
from .rule_definitions import RuleBasedIntentDetector
from .semantic import SEMANTIC_DETECTOR, SemanticIntentDetector
from .types import IntentResult


class IntentRouter:
    """Routes user input through rule -> semantic -> LLM (Phase-1)."""

    def __init__(self, semantic_detector: SemanticIntentDetector = SEMANTIC_DETECTOR) -> None:
        self.rule_detector = RuleBasedIntentDetector()
        self.semantic_detector = semantic_detector

    def route(self, text: str) -> IntentResult:
        """Route to the first confident intent. Semantic/LLM are placeholders."""
        rule_result = self.rule_detector.detect(text)
        if rule_result:
            return rule_result

        # Always compute semantic best match to surface debug info even if below threshold.
        semantic_match = self.semantic_detector.score(text)
        if semantic_match:
            threshold = config.SEMANTIC_CONFIDENCE_BY_INTENT.get(
                semantic_match.intent, config.SEMANTIC_CONFIDENCE_THRESHOLD
            )
        else:
            threshold = config.SEMANTIC_CONFIDENCE_THRESHOLD

        if semantic_match and semantic_match.score >= threshold:
            return IntentResult(
                intent=semantic_match.intent,
                confidence=semantic_match.score,
                source="semantic",
                entities={},
                reason=(
                    f"Matched semantic example '{semantic_match.text}' with similarity {semantic_match.score:.2f}; "
                    f"threshold {threshold:.2f}."
                ),
            )

        llm_result: Optional[IntentResult] = None
        if config.ENABLE_LLM_FALLBACK and llm_result:
            return llm_result

        if semantic_match:
            semantic_debug = (
                f"Best semantic match: '{semantic_match.text}' -> {semantic_match.intent} "
                f"with similarity {semantic_match.score:.2f}; threshold {threshold:.2f}."
            )
        else:
            semantic_debug = "Semantic match unavailable (no tokens)."

        return IntentResult(
            intent="unknown",
            confidence=0.0,
            source="none",
            reason=f"No intent matched by rules; {semantic_debug}",
        )

