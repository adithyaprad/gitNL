"""Intent routing orchestrating rule, semantic, and LLM fallback (stubs)."""

from typing import Optional
import re

from git_nl import config
from .llm import LLMClauseIntent, LLMIntentDetector
from .rule_definitions import RuleBasedIntentDetector, extract_entities_for_intent
from .semantic import SEMANTIC_DETECTOR, SemanticIntentDetector
from .types import IntentResult


_CLAUSE_SPLIT_PATTERN = re.compile(
    r"\b(?:and then|after that|afterwards|then|and|next)\b|;",
    re.IGNORECASE,
)


def _find_quote_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    in_quote: str | None = None
    start: int | None = None
    for idx, ch in enumerate(text):
        if in_quote:
            if ch == in_quote:
                spans.append((start or 0, idx + 1))
                in_quote = None
                start = None
        elif ch in {"'", '"', "`"}:
            in_quote = ch
            start = idx
    return spans


def _overlaps_quotes(span: tuple[int, int], quote_spans: list[tuple[int, int]]) -> bool:
    start, end = span
    for q_start, q_end in quote_spans:
        if start < q_end and end > q_start:
            return True
    return False


def split_clauses(text: str) -> list[str]:
    """Split multi-intent input into clause strings, respecting quotes."""
    stripped = text.strip()
    if not stripped:
        return []

    quote_spans = _find_quote_spans(text)
    split_spans: list[tuple[int, int]] = []
    for match in _CLAUSE_SPLIT_PATTERN.finditer(text):
        if not _overlaps_quotes(match.span(), quote_spans):
            split_spans.append(match.span())

    if not split_spans:
        return [stripped]

    clauses: list[str] = []
    start = 0
    for span_start, span_end in split_spans:
        clause = text[start:span_start].strip(" ,;")
        if clause:
            clauses.append(clause)
        start = span_end
    tail = text[start:].strip(" ,;")
    if tail:
        clauses.append(tail)
    return clauses


class IntentRouter:
    """Routes user input through rule -> semantic -> LLM (Phase-1)."""

    def __init__(
        self,
        semantic_detector: SemanticIntentDetector = SEMANTIC_DETECTOR,
        llm_detector: LLMIntentDetector | None = None,
    ) -> None:
        self.rule_detector = RuleBasedIntentDetector()
        self.semantic_detector = semantic_detector
        self.llm_detector = llm_detector or LLMIntentDetector()
        self.allowed_intents = sorted(
            {rule.intent for rule in self.rule_detector.rules} | set(self.semantic_detector.catalog.keys())
        )

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
                entities=extract_entities_for_intent(semantic_match.intent, text),
                reason=(
                    f"Matched semantic example '{semantic_match.text}' with similarity {semantic_match.score:.2f}; "
                    f"threshold {threshold:.2f}."
                ),
            )

        llm_reason = "LLM fallback disabled."
        llm_result: Optional[IntentResult] = None
        if config.ENABLE_LLM_FALLBACK:
            llm_result, llm_reason = self.llm_detector.detect(text, allowed_intents=self.allowed_intents)
            if llm_result:
                llm_result.entities = extract_entities_for_intent(llm_result.intent, text)
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
            reason=f"No intent matched by rules; {semantic_debug} LLM fallback: {llm_reason}",
        )

    def route_many(self, text: str) -> list[IntentResult]:
        """Route multiple clauses sequentially with LLM fallback when any clause fails."""
        clauses = split_clauses(text)
        if not clauses:
            return [
                IntentResult(
                    intent="unknown",
                    confidence=0.0,
                    source="none",
                    reason="No intent matched: empty input.",
                )
            ]
        if len(clauses) == 1:
            return [self.route(clauses[0])]

        results: list[IntentResult] = []
        needs_llm = False
        for clause in clauses:
            result, confident = self._route_clause_deterministic(clause)
            results.append(result)
            if not confident:
                needs_llm = True

        if not needs_llm:
            return results

        if not config.ENABLE_LLM_FALLBACK:
            for res in results:
                if res.intent == "unknown":
                    res.reason = f"{res.reason} LLM fallback: disabled."
            return results

        llm_results, llm_reason = self.llm_detector.detect_many(clauses, allowed_intents=self.allowed_intents)
        if not llm_results:
            for res in results:
                if res.intent == "unknown":
                    res.reason = f"{res.reason} LLM fallback: {llm_reason}"
            return results

        ordered: list[LLMClauseIntent] = sorted(llm_results, key=lambda item: item.clause_index)
        final_results: list[IntentResult] = []
        for item in ordered:
            clause_text = clauses[item.clause_index]
            if item.intent == "unknown":
                final_results.append(
                    IntentResult(
                        intent="unknown",
                        confidence=0.0,
                        source="llm",
                        reason=item.reason,
                    )
                )
            else:
                entities = extract_entities_for_intent(item.intent, clause_text)
                final_results.append(
                    IntentResult(
                        intent=item.intent,
                        confidence=item.confidence,
                        source="llm",
                        entities=entities,
                        reason=item.reason,
                    )
                )
        return final_results

    def _route_clause_deterministic(self, clause: str) -> tuple[IntentResult, bool]:
        rule_result = self.rule_detector.detect(clause)
        if rule_result:
            return rule_result, True

        semantic_match = self.semantic_detector.score(clause)
        if semantic_match:
            threshold = config.SEMANTIC_CONFIDENCE_BY_INTENT.get(
                semantic_match.intent, config.SEMANTIC_CONFIDENCE_THRESHOLD
            )
        else:
            threshold = config.SEMANTIC_CONFIDENCE_THRESHOLD

        if semantic_match and semantic_match.score >= threshold:
            return (
                IntentResult(
                    intent=semantic_match.intent,
                    confidence=semantic_match.score,
                    source="semantic",
                    entities=extract_entities_for_intent(semantic_match.intent, clause),
                    reason=(
                        f"Matched semantic example '{semantic_match.text}' with similarity {semantic_match.score:.2f}; "
                        f"threshold {threshold:.2f}."
                    ),
                ),
                True,
            )

        if semantic_match:
            semantic_debug = (
                f"Best semantic match: '{semantic_match.text}' -> {semantic_match.intent} "
                f"with similarity {semantic_match.score:.2f}; threshold {threshold:.2f}."
            )
        else:
            semantic_debug = "Semantic match unavailable (no tokens)."

        return (
            IntentResult(
                intent="unknown",
                confidence=0.0,
                source="none",
                reason=f"No intent matched by rules; {semantic_debug}",
            ),
            False,
        )