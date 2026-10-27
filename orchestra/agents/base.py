"""
Basis-Agent: gemeinsames Interface für alle Subagenten.

Jeder Agent gibt zurück:
    a  = -1 (SELL), 0 (HOLD), +1 (BUY)
    confidence = 0..1  (wie sicher ist er sich)
    reason = kurze Begründung (datenarm)

Jeder Agent arbeitet ISOLIERT auf seinem eigenen, zugeschnittenen Datensatz.
Kein Agent sieht die Features eines anderen — nur der Dirigent aggregiert.
"""
from dataclasses import dataclass, field


@dataclass
class AgentResult:
    agent: str                 # z.B. "momentum"
    a: int                     # -1, 0, +1
    confidence: float          # 0..1
    reason: str = ""
    weight: float = 0.0        # w_i (vom Dirigenten gesetzt)
    details: dict = field(default_factory=dict)

    @property
    def weighted_vote(self) -> float:
        """w_i * a_i * conf_i — der Beitrag zu S."""
        return self.weight * self.a * self.confidence


class BaseAgent:
    name = "base"
    # Eigenes Gewicht aus Config (zugeschnitten, isoliert)
    weight_key = "conductor.weights"

    def __init__(self, config=None):
        from orchestra.config import get
        self.cfg = config if config is not None else {}
        self.weight = float(get("conductor.weights." + self.name,
                                get(self.weight_key, {}).get(self.name, 0.1)))
        self.params = get("agents." + self.name, {}) or {}

    def vote(self, data) -> AgentResult:
        """Muss von jedem Agenten überschrieben werden.
        data = das, was DIESER Agent braucht (isoliert, zugeschnitten)."""
        raise NotImplementedError

    def _make(self, a, confidence, reason="", **details) -> AgentResult:
        return AgentResult(agent=self.name, a=int(a),
                           confidence=float(max(0, min(1, confidence))),
                           reason=reason, weight=self.weight, details=details)
