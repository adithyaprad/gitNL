"""LLM fallback intent classifier using a lightweight GPT endpoint."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
import urllib.error
import urllib.request
from typing import List, Tuple

from git_nl import config
from .types import IntentResult

# Prompts defined by product to keep the model scoped to intent-only answers.
SYSTEM_PROMPT = """You are an intent classification engine.

Your job is to map the user's input to exactly ONE intent from the allowed list,
or return "unknown" if unclear.

You must NOT:
- explain your reasoning
- suggest commands
- invent intents
- return multiple intents

Return JSON only."""

USER_PROMPT_TEMPLATE = """User input:
{user_input}

Allowed intents:
{allowed_intents}

Return format:
{{
  "intent": "<intent | unknown>",
  "confidence": <number between 0 and 1>
}}"""

SYSTEM_PROMPT_MULTI = """You are an intent classification engine.

Your job is to map each clause to exactly ONE intent from the allowed list,
or return "unknown" if unclear.

You must NOT:
- explain your reasoning
- suggest commands
- invent intents
- return multiple intents per clause

Return JSON only."""

USER_PROMPT_TEMPLATE_MULTI = """Clauses:
{clauses}

Allowed intents:
{allowed_intents}

Return format:
{{
  "intents": [
    {{
      "clause_index": <integer index of clause>,
      "intent": "<intent | unknown>",
      "confidence": <number between 0 and 1>
    }}
  ]
}}"""


@dataclass
class LLMClauseIntent:
    clause_index: int
    intent: str
    confidence: float
    reason: str = ""


class LLMIntentDetector:
    """Calls a fast LLM to classify intents when deterministic paths fail."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
        timeout: float = config.LLM_TIMEOUT,
    ) -> None:
        _load_env_from_file()
        self.model = model or os.getenv("OPENROUTER_MODEL") or "meta-llama/llama-3.2-1b-instruct"
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.api_base = (api_base or os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").rstrip("/")
        self.timeout = timeout

    def detect(self, text: str, allowed_intents: List[str]) -> Tuple[IntentResult | None, str]:
        """Return an IntentResult when the LLM returns a recognized intent."""
        if not allowed_intents:
            return None, "LLM fallback skipped: no allowed intents provided."

        if not self.api_key:
            return None, "LLM fallback skipped: OPENROUTER_API_KEY not set."

        user_prompt = USER_PROMPT_TEMPLATE.format(
            user_input=text.strip(),
            allowed_intents=", ".join(sorted(set(allowed_intents))),
        )
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        }

        structured, error = self._call_llm(payload)
        if error:
            return None, error

        intent = structured.get("intent")
        confidence_raw = structured.get("confidence", 0.0)
        try:
            confidence = float(confidence_raw)
        except (TypeError, ValueError):
            confidence = 0.0

        if not isinstance(intent, str):
            return None, "LLM response missing intent string."

        if intent == "unknown":
            return None, "LLM returned unknown."

        if intent not in allowed_intents:
            return None, f"LLM intent '{intent}' not in allowed list."

        if not 0.0 <= confidence <= 1.0:
            confidence = 0.0

        if confidence < config.LLM_CONFIDENCE_THRESHOLD:
            return None, f"LLM confidence {confidence:.2f} below threshold {config.LLM_CONFIDENCE_THRESHOLD:.2f}."

        return (
            IntentResult(
                intent=intent,
                confidence=confidence,
                source="llm",
                entities={},
                reason=f"LLM ({self.model}) classified intent '{intent}' with confidence {confidence:.2f}.",
            ),
            "LLM classified intent.",
        )

    def detect_many(self, clauses: List[str], allowed_intents: List[str]) -> Tuple[List[LLMClauseIntent] | None, str]:
        """Return ordered clause intents for multi-intent fallback."""
        if not clauses:
            return None, "LLM fallback skipped: no clauses provided."

        if not allowed_intents:
            return None, "LLM fallback skipped: no allowed intents provided."

        if not self.api_key:
            return None, "LLM fallback skipped: OPENROUTER_API_KEY not set."

        clause_lines = "\n".join(f"{idx}: {clause}" for idx, clause in enumerate(clauses))
        user_prompt = USER_PROMPT_TEMPLATE_MULTI.format(
            clauses=clause_lines,
            allowed_intents=", ".join(sorted(set(allowed_intents))),
        )
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_MULTI},
                {"role": "user", "content": user_prompt},
            ],
        }

        structured, error = self._call_llm(payload)
        if error:
            return None, error

        intents = structured.get("intents")
        if not isinstance(intents, list):
            return None, "LLM response missing intents list."

        result_map: dict[int, LLMClauseIntent] = {}
        for idx in range(len(clauses)):
            result_map[idx] = LLMClauseIntent(
                clause_index=idx,
                intent="unknown",
                confidence=0.0,
                reason="LLM did not return an intent for this clause.",
            )

        for item in intents:
            if not isinstance(item, dict):
                continue
            clause_index = item.get("clause_index")
            if not isinstance(clause_index, int):
                continue
            if clause_index < 0 or clause_index >= len(clauses):
                continue

            intent = item.get("intent")
            confidence_raw = item.get("confidence", 0.0)
            try:
                confidence = float(confidence_raw)
            except (TypeError, ValueError):
                confidence = 0.0

            if not isinstance(intent, str):
                intent = "unknown"

            if intent == "unknown":
                reason = "LLM returned unknown."
                result = LLMClauseIntent(clause_index=clause_index, intent="unknown", confidence=confidence, reason=reason)
            elif intent not in allowed_intents:
                reason = f"LLM intent '{intent}' not in allowed list."
                result = LLMClauseIntent(clause_index=clause_index, intent="unknown", confidence=confidence, reason=reason)
            elif not 0.0 <= confidence <= 1.0:
                reason = "LLM confidence out of range."
                result = LLMClauseIntent(clause_index=clause_index, intent="unknown", confidence=0.0, reason=reason)
            elif confidence < config.LLM_CONFIDENCE_THRESHOLD:
                reason = f"LLM confidence {confidence:.2f} below threshold {config.LLM_CONFIDENCE_THRESHOLD:.2f}."
                result = LLMClauseIntent(clause_index=clause_index, intent="unknown", confidence=confidence, reason=reason)
            else:
                reason = f"LLM ({self.model}) classified intent '{intent}' with confidence {confidence:.2f}."
                result = LLMClauseIntent(clause_index=clause_index, intent=intent, confidence=confidence, reason=reason)

            existing = result_map.get(clause_index)
            if existing and existing.intent != "unknown" and result.intent == "unknown":
                continue
            if existing and existing.intent != "unknown" and result.intent != "unknown":
                if result.confidence <= existing.confidence:
                    continue
            result_map[clause_index] = result

        ordered = [result_map[idx] for idx in range(len(clauses))]
        return ordered, "LLM classified intents."

    def _call_llm(self, payload: dict) -> Tuple[dict | None, str | None]:
        try:
            req = urllib.request.Request(
                url=f"{self.api_base}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return None, f"LLM HTTP error {exc.code}: {exc.reason}"
        except urllib.error.URLError as exc:
            return None, f"LLM network error: {exc.reason}"
        except Exception as exc:  # pragma: no cover - defensive
            return None, f"LLM call failed: {exc}"

        try:
            parsed = json.loads(body)
            content = parsed["choices"][0]["message"]["content"]
            structured = json.loads(content)
        except Exception as exc:
            return None, f"LLM response parse failed: {exc}"

        return structured, None


def _load_env_from_file() -> None:
    """Load .env from repository root into os.environ if present."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
