"""
A1 — Momentum Agent (25% Gewicht): der Wellenreiter.

Eigener, zugeschnittener Datensatz: nur EMA9/21, RSI, ADX, Chop.
Surft die Trend-Welle: kauft im Aufwärtstrend, verkauft im Abwärtstrend.
"""
import numpy as np

from orchestra.agents.base import BaseAgent
from orchestra.config import get
from orchestra.utils import indicators


class MomentumAgent(BaseAgent):
    name = "momentum"

    def vote(self, data):
        # data: dict mit close[], high[], low[] (isoliert, nur was dieser Agent braucht)
        close = np.asarray(data.get("close", []), dtype=float)
        high = np.asarray(data.get("high", close), dtype=float)
        low = np.asarray(data.get("low", close), dtype=float)
        if len(close) < 30:
            return self._make(0, 0.1, "zu wenig Daten")

        # Eigene Parameter (aus Backtesting zugeschnitten)
        ema_fast = self.params.get("ema_fast", 9)
        ema_slow = self.params.get("ema_slow", 21)
        rsi_period = self.params.get("rsi_period", 14)
        rsi_buy_max = self.params.get("rsi_buy_max", 70)
        rsi_sell_min = self.params.get("rsi_sell_min", 30)
        adx_min = self.params.get("adx_min", 25)
        chop_max = self.params.get("chop_max", 55)

        e_fast = indicators.ema(close, ema_fast)
        e_slow = indicators.ema(close, ema_slow)
        rsi = indicators.rsi(close, rsi_period)
        adx = indicators.adx(high, low, close, 14)
        chop = indicators.chop(high, low, close, 14)

        i = -1
        if np.isnan(e_slow[i]) or np.isnan(rsi[i]) or np.isnan(adx[i]) or np.isnan(chop[i]):
            return self._make(0, 0.1, "Indikator unfertig")

        # Trend-Filter: ADX > 25 (starker Trend) + Chop < 55 (kein Seitwärts)
        strong_trend = adx[i] > adx_min and chop[i] < chop_max

        if e_fast[i] > e_slow[i] and rsi[i] < rsi_buy_max and strong_trend:
            conf = min(1.0, 0.5 + (e_fast[i] - e_slow[i]) / e_slow[i] * 50 + (adx[i] - adx_min) / 100)
            return self._make(1, conf, f"EMA{ema_fast}>EMA{ema_slow}, RSI {rsi[i]:.0f}, ADX {adx[i]:.0f}",
                              ema_fast=ema_fast, ema_slow=ema_slow, rsi=round(float(rsi[i]), 1),
                              adx=round(float(adx[i]), 1), chop=round(float(chop[i]), 1))
        elif e_fast[i] < e_slow[i] and rsi[i] > rsi_sell_min and strong_trend:
            conf = min(1.0, 0.5 + (e_slow[i] - e_fast[i]) / e_slow[i] * 50 + (adx[i] - adx_min) / 100)
            return self._make(-1, conf, f"EMA{ema_fast}<EMA{ema_slow}, RSI {rsi[i]:.0f}, ADX {adx[i]:.0f}",
                              ema_fast=ema_fast, ema_slow=ema_slow, rsi=round(float(rsi[i]), 1),
                              adx=round(float(adx[i]), 1), chop=round(float(chop[i]), 1))
        return self._make(0, 0.3, f"neutral: ADX {adx[i]:.0f} / Chop {chop[i]:.0f}",
                          adx=round(float(adx[i]), 1), chop=round(float(chop[i]), 1))


if __name__ == "__main__":
    from orchestra.tiers import tier1
    np.random.seed(1)
    # Test: synthetischer Aufwärtstrend
    close = np.cumsum(np.random.randn(80) * 0.3) + 100 + np.linspace(0, 20, 80)
    high, low = close + 0.5, close - 0.5
    a = MomentumAgent()
    print(a.vote({"close": close, "high": high, "low": low}))
