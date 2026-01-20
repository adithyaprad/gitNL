from dataclasses import dataclass, field
from typing import Dict


@dataclass
class IntentResult:
    """Unified intent output used across routing strategies."""

    intent: str
    confidence: float
    source: str
    entities: Dict[str, str] = field(default_factory=dict)
    reason: str = ""

