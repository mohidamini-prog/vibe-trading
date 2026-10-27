"""
A2 — Mean Reversion Agent (20% Gewicht): nur als Beifang, IM Trend.

Eigener, zugeschnittener Datensatz: nur z_score (SMA20/σ), ATR.
Kauft kleine Dips IM Trend (nicht gegen den Trend). z > +2 => überkauft => SELL.
"""
import numpy as np

from orchestra.agents.base import BaseAgent
from orchestra.utils import indicators


class MeanRevAgent(BaseAgent):
    name = "meanrev"

    def vote(self, data):
        close = np.asarray(data.get("close", []), dtype=float)
        high = np.asarray(data.get("high", close), dtype=float)
        low = np.asarray(data.get("low", close), dtype=float)
        if len(close) < 30:
            return self._make(0, 0.1, "zu wenig Daten")

        sma_period = self.params.get("sma_period", 20)
        z_entry = self.params.get("z_entry", 2.0)

        z = indicators.zscore(close, sma_period)
        atr = indicators.atr(high, low, close, self.params.get("atr_period", 14))
        sma = indicators.sma(close, sma_period)

        i = -1
        if np.isnan(z[i]) or np.isnan(sma[i]) or np.isnan(atr[i]):
            return self._make(0, 0.1, "Indikator unfertig")

        # Trend-Kontext: nur MeanRev IM Trend, nie gegen den Trend (Flow-Prinzip)
        e9 = indicators.ema(close, 9)
        e21 = indicators.ema(close, 21)
        uptrend = e9[i] > e21[i]
        downtrend = e9[i] < e21[i]

        # Überverkaufter Dip IM Aufwärtstrend => BUY (Beifang)
        if z[i] < -z_entry and uptrend:
            conf = min(1.0, 0.5 + abs(z[i]) / 4.0)
            return self._make(1, conf, f"Dip im Uptrend, z={z[i]:.2f}",
                              z=round(float(z[i]), 2), sma=round(float(sma[i]), 2))
        # Überkaufter Rausch im Abwärtstrend => SELL (Beifang)
        if z[i] > z_entry and downtrend:
            conf = min(1.0, 0.5 + z[i] / 4.0)
            return self._make(-1, conf, f"Spike im Downtrend, z={z[i]:.2f}",
                              z=round(float(z[i]), 2), sma=round(float(sma[i]), 2))
        return self._make(0, 0.3, f"z={z[i]:.2f} normal", z=round(float(z[i]), 2))


if __name__ == "__main__":
    np.random.seed(2)
    close = np.cumsum(np.random.randn(60) * 0.3) + 100
    high, low = close + 0.5, close - 0.5
    a = MeanRevAgent()
    print(a.vote({"close": close, "high": high, "low": low}))
