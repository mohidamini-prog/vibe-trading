"""
Der Dirigent — das Herzstück. Keine Magie, nur gewichtete Abstimmung. Und er lernt.

S = Σ(w_i * a_i * conf_i) / Σ(w_i)
    S > +0.5 => BUY
    S < -0.5 => SELL
    sonst    => HOLD

Signal-Stärke = |S| * avg_confidence

Dynamische Gewichte: jede Nacht (offline) w_i_neu = w_i_alt * (1 + alpha * Sharpe_i).
"""
import json
from dataclasses import dataclass, field
from datetime import datetime

from orchestra.config import get
from orchestra.data import cache


@dataclass
class ConductorDecision:
    symbol: str
    decision: str            # BUY / HOLD / SELL
    S: float                 # gewichtete Abstimmung
    strength: float          # |S| * avg_conf
    avg_confidence: float
    weights: dict
    votes: list = field(default_factory=list)
    vetoed: bool = False
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self):
        return {
            "symbol": self.symbol, "decision": self.decision,
            "S": round(self.S, 4), "strength": round(self.strength, 4),
            "avg_confidence": round(self.avg_confidence, 4),
            "weights": self.weights, "votes": self.votes,
            "vetoed": self.vetoed, "timestamp": self.timestamp,
        }


class Conductor:
    def __init__(self, agents=None):
        self.agents = agents or []
        self.buy_threshold = float(get("conductor.buy_threshold", 0.5))
        self.sell_threshold = float(get("conductor.sell_threshold", -0.5))
        self.alpha = float(get("conductor.alpha", 0.05))

    def conduct(self, symbol, results):
        """
        Nimmt die AgentResult-Liste und aggregiert zu einer Entscheidung.
        Veto-Agenten (a=0, high conf, veto=True) dämpfen/dämpfen alle.
        """
        # Veto-Erkennung: wenn ein Agent Veto hat, stark dämpfen
        vetoed = any(r.details.get("veto") for r in results)

        total_w = sum(r.weight for r in results) or 1.0
        S = sum(r.weighted_vote for r in results) / total_w

        avg_conf = sum(r.confidence for r in results) / len(results) if results else 0
        # Bei Veto: Signale abschwächen (Sicherheitsnetz)
        if vetoed:
            S *= 0.3
            avg_conf *= 0.5

        if S > self.buy_threshold:
            decision = "BUY"
        elif S < self.sell_threshold:
            decision = "SELL"
        else:
            decision = "HOLD"

        strength = abs(S) * avg_conf
        weights = {r.agent: r.weight for r in results}
        votes = [{"agent": r.agent, "a": r.a, "conf": round(r.confidence, 3),
                  "reason": r.reason} for r in results]

        dec = ConductorDecision(symbol=symbol, decision=decision, S=S,
                                strength=strength, avg_confidence=avg_conf,
                                weights=weights, votes=votes, vetoed=vetoed)
        self._persist(dec)
        return dec

    def _persist(self, dec):
        """Entscheidung in State-DB speichern (historie)."""
        hist = cache.get_state("conductor_history", [])
        hist.append(dec.to_dict())
        # Nur letzte 200 behalten (datenarm)
        cache.set_state("conductor_history", hist[-200:])
        cache.set_state("last_decision", dec.to_dict())

    # --- Dynamische Gewichte (nächtliche Offline-Optimierung) ---
    def update_weights(self, performance):
        """
        performance: {agent: sharpe} aus den letzten 20 Trades.
        w_i_neu = w_i_alt * (1 + alpha * Sharpe_i), dann normalisieren (Summe=1).
        """
        weights = {r.name: r.weight for r in self.agents} if self.agents else {}
        weights = weights or {a: 1.0 / len(self.agents) for a in performance}
        for agent, sharpe in performance.items():
            if agent in weights:
                weights[agent] = weights[agent] * (1 + self.alpha * sharpe)
        # Normalisieren
        total = sum(weights.values()) or 1.0
        weights = {k: v / total for k, v in weights.items()}
        cache.set_state("agent_weights", weights)
        return weights


if __name__ == "__main__":
    from orchestra.agents.a1_momentum import MomentumAgent
    from orchestra.agents.a2_meanrev import MeanRevAgent
    from orchestra.agents.a3_vola import VolaRiskAgent
    from orchestra.agents.a4_quant import QuantAgent
    from orchestra.agents.a5_news import NewsAgent

    agents = [MomentumAgent(), MeanRevAgent(), VolaRiskAgent(), QuantAgent(), NewsAgent()]
    c = Conductor(agents)
    print("Dirigent initialisiert. Agenten:", [a.name for a in agents])
    print("Buy-Schwelle:", c.buy_threshold, "| Sell-Schwelle:", c.sell_threshold)
    print("Start-Gewichte:", {a.name: a.weight for a in agents})
