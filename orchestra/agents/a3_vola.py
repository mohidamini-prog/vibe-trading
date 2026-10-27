"""
A3 — Volatility/Risk Agent (15% Gewicht): der Bremser. Darf VETO geben.

Eigener, zugeschnittener Datensatz: nur ATR(14), Spread, Vola-Regime.
Wenn ATR explodiert oder Spread riesig => a=0 und senkt das Vertrauen aller.
Schützt vor Fake-Signalen.
"""
import numpy as np

from orchestra.agents.base import BaseAgent
from orchestra.utils import indicators


class VolaRiskAgent(BaseAgent):
    name = "vola"

    def vote(self, data):
        close = np.asarray(data.get("close", []), dtype=float)
        high = np.asarray(data.get("high", close), dtype=float)
        low = np.asarray(data.get("low", close), dtype=float)
        if len(close) < 20:
            return self._make(0, 0.1, "zu wenig Daten")

        atr_period = self.params.get("atr_period", 14)
        atr_spike = self.params.get("atr_spike_mult", 2.5)
        spread_max = self.params.get("spread_max_pct", 0.5)

        atr = indicators.atr(high, low, close, atr_period)
        i = -1
        if np.isnan(atr[i]):
            return self._make(0, 0.2, "ATR unfertig")

        # Baseline = Median der ATR (Regime-Erkennung)
        valid_atr = atr[~np.isnan(atr)]
        baseline = float(np.median(valid_atr[-50:])) if len(valid_atr) else float(atr[i])
        ratio = float(atr[i]) / baseline if baseline > 0 else 1.0

        spread_pct = data.get("spread_pct")
        if spread_pct is None:
            spread_pct = 0.0  # Offline-Fallback: kein Spread

        regime = "wild" if ratio > atr_spike else ("calm" if ratio < 0.7 else "normal")

        # VETO: ATR explodiert oder Spread zu breit
        if ratio > atr_spike:
            return self._make(0, 0.95, f"VETO: ATR-Spike {ratio:.1f}x", veto=True,
                              atr_ratio=round(ratio, 2), regime=regime)
        if spread_pct > spread_max:
            return self._make(0, 0.9, f"VETO: Spread {spread_pct:.2f}% zu breit", veto=True,
                              spread=spread_pct, regime=regime)

        # Kein Veto, aber im wilden Markt Vertrauen senken (dämpft alle)
        conf = 0.5 if regime == "calm" else (0.4 if regime == "wild" else 0.3)
        return self._make(0, conf, f"Regime {regime}, ATR {ratio:.1f}x", veto=False,
                          atr_ratio=round(ratio, 2), regime=regime)


if __name__ == "__main__":
    np.random.seed(3)
    close = np.cumsum(np.random.randn(60) * 0.3) + 100
    high, low = close + 0.5, close - 0.5
    a = VolaRiskAgent()
    print(a.vote({"close": close, "high": high, "low": low}))
    # Test VETO: ATR explodiert
    close2 = np.cumsum(np.random.randn(60) * 3.0) + 100
    print(a.vote({"close": close2, "high": close2 + 3, "low": close2 - 3}))
