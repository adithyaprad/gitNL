"""LLM fallback intent classifier using a lightweight GPT endpoint."""

from __future__ import annotations

import json
import os
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
