"""Intent routing orchestrating rule, semantic, and LLM fallback (stubs)."""

from typing import Optional

from git_nl import config
from .rule_definitions import RuleBasedIntentDetector
from .types import IntentResult


class IntentRouter:
    """Routes user input through rule -> semantic -> LLM (Phase-1)."""

    def __init__(self) -> None:
        self.rule_detector = RuleBasedIntentDetector()

    def route(self, text: str) -> IntentResult:
        """Route to the first confident intent. Semantic/LLM are placeholders."""
        rule_result = self.rule_detector.detect(text)
        if rule_result:
            return rule_result

        semantic_result: Optional[IntentResult] = None
        if semantic_result and semantic_result.confidence >= config.SEMANTIC_CONFIDENCE_THRESHOLD:
            return semantic_result

        llm_result: Optional[IntentResult] = None
        if config.ENABLE_LLM_FALLBACK and llm_result:
            return llm_result

        return IntentResult(
            intent="unknown",
            confidence=0.0,
            source="none",
            reason="No intent matched by rules; semantic/LLM disabled or not implemented.",
        )

