"""
Layer 4 — Konfidenz-Modulation & Conductor.

Der Conductor aggregiert die Signale robust:
  - Gewichtete Abstimmung mit DYNAMISCHEN Gewichten (lernend, aus Performance)
  - Veto-Logik (Vola/News können alles dämpfen)
  - Konfidenz-Modulation: nur hoch-konfidente, gefilterte Signale zählen voll
  - Springer-Infos: Begründungen, Indikator-Werte (für Transparenz)

S = Σ(w_i * a_i * conf_i * f_i) / Σ(w_i),  f_i = 1 wenn Filter pass, sonst 0.5 (gedämpft)
Entscheidung: S > +0.5 BUY, S < -0.5 SELL, sonst HOLD.
"""
import sys
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestra.config import get
from orchestra.data import cache


@dataclass
class LayerDecision:
    symbol: str
    timeframe: str
    decision: str            # BUY / HOLD / SELL
    S: float
    strength: float
    avg_confidence: float
    weights: dict
    signals: list = field(default_factory=list)
    filter_report: dict = field(default_factory=dict)
    vetoed: bool = False
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self):
        return {
            "symbol": self.symbol, "timeframe": self.timeframe,
            "decision": self.decision, "S": round(self.S, 4),
            "strength": round(self.strength, 4),
            "avg_confidence": round(self.avg_confidence, 4),
            "weights": self.weights, "signals": self.signals,
            "filter_report": self.filter_report, "vetoed": self.vetoed,
            "timestamp": self.timestamp,
        }


class Conductor:
    def __init__(self, weights=None):
        self.buy_threshold = float(get("conductor.buy_threshold", 0.5))
        self.sell_threshold = float(get("conductor.sell_threshold", -0.5))
        self.alpha = float(get("conductor.alpha", 0.05))
        # Dynamische Gewichte aus State, sonst Standard
        stored = cache.get_state("layer_weights", None)
        self.weights = stored or weights or {
            "new_52w_high_momentum": 0.45,
            "sr_flip_breakout": 0.35,
            "deep_value_bounce_52w": 0.15,
            "fib_pullback_confluence": 0.05,
            "meanrev_bb": 0.0,
        }

    def conduct(self, symbol, timeframe, signals, filter_passed, filter_report):
        """
        signals: Liste von {model, a, conf, reason}
        filter_passed: bool (alle Gates)
        filter_report: {gate: reason}
        """
        vetoed = any(s.get("a") == 0 and s.get("conf", 0) > 0.9 for s in signals)

        total_w = sum(self.weights.get(s["model"], 0.1) for s in signals) or 1.0
        S = 0.0
        for s in signals:
            w = self.weights.get(s["model"], 0.1)
            # Filter-Modulation: gefilterte Signale zählen voll, ungefilterte nur halb
            f = 1.0 if filter_passed else 0.5
            S += w * s["a"] * s["conf"] * f
        S /= total_w

        avg_conf = sum(s["conf"] for s in signals) / len(signals) if signals else 0

        if vetoed:
            S *= 0.3
            avg_conf *= 0.5

        # ODER-Logik (User-Freigabe, 28.10.): Ein einzelnes starkes Signal
        # (conf >= 0.80) reicht für BUY — zusätzlich zur UND-Schwelle S > 0.5.
        # Basierend auf Backtest: ODER erzeugt ~195 Trades (+83% 5y) statt 0 bei UND.
        ODER_CONF = float(get("conductor.oder_conf", 0.80))
        single_buy = any(s.get("a") == 1 and s.get("conf", 0) >= ODER_CONF for s in signals)
        single_sell = any(s.get("a") == -1 and s.get("conf", 0) >= ODER_CONF for s in signals)

        if S > self.buy_threshold or single_buy:
            decision = "BUY"
        elif S < self.sell_threshold or single_sell:
            decision = "SELL"
        else:
            decision = "HOLD"

        strength = abs(S) * avg_conf
        weights_out = {s["model"]: round(self.weights.get(s["model"], 0.1), 3) for s in signals}
        signals_out = [{"model": s["model"], "a": s["a"], "conf": round(s["conf"], 3),
                        "reason": s["reason"]} for s in signals]

        dec = LayerDecision(symbol=symbol, timeframe=timeframe, decision=decision,
                            S=S, strength=strength, avg_confidence=avg_conf,
                            weights=weights_out, signals=signals_out,
                            filter_report=filter_report, vetoed=vetoed)
        self._persist(dec)
        return dec

    def _persist(self, dec):
        hist = cache.get_state("layer_history", [])
        hist.append(dec.to_dict())
        cache.set_state("layer_history", hist[-300:])
        cache.set_state("last_layer_decision", dec.to_dict())

    def update_weights(self, performance):
        """performance: {model: sharpe}. w_neu = w_alt * (1 + alpha*sharpe), normalisiert."""
        for model, sharpe in performance.items():
            if model in self.weights:
                self.weights[model] *= (1 + self.alpha * sharpe)
        total = sum(self.weights.values()) or 1.0
        self.weights = {k: v / total for k, v in self.weights.items()}
        cache.set_state("layer_weights", self.weights)
        return self.weights


if __name__ == "__main__":
    c = Conductor()
    print("Conductor initialisiert. Gewichte:", c.weights)
