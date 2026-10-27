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
        rsi = indicators.rsi(close, 14)
        # Bollinger-Bänder (20, 2) — meanrev_bb 1d: Hit 53.7%, Ret +35.5% (beste MeanRev)
        bb_mid = indicators.sma(close, 20)
        bb_std = indicators.sma(np.abs(close - bb_mid), 20) if len(close) >= 20 else np.full(len(close), np.nan)
        # Robuster: rolling std über numpy
        if len(close) >= 20:
            bb_std = np.array([np.std(close[max(0,j-19):j+1]) for j in range(len(close))])
        else:
            bb_std = np.full(len(close), np.nan)
        bb_low = bb_mid - 2 * bb_std
        bb_up = bb_mid + 2 * bb_std

        i = -1
        if np.isnan(z[i]) or np.isnan(sma[i]) or np.isnan(atr[i]) or np.isnan(bb_low[i]):
            return self._make(0, 0.1, "Indikator unfertig")

        # Trend-Kontext: nur MeanRev IM Trend, nie gegen den Trend (Flow-Prinzip)
        e9 = indicators.ema(close, 9)
        e21 = indicators.ema(close, 21)
        uptrend = e9[i] > e21[i]
        downtrend = e9[i] < e21[i]

        # Backtest-optimiert (meanrev_bb): Preis < BB_Low oder RSI < 35 = Dip im Uptrend => BUY
        dip_buy = (close[i] <= bb_low[i]) or (rsi[i] < 35)
        spike_sell = (close[i] >= bb_up[i]) or (rsi[i] > 70)

        # Überverkaufter Dip IM Aufwärtstrend => BUY (Beifang) — meanrev_bb Priorität
        if dip_buy and uptrend:
            conf = min(1.0, 0.5 + abs(z[i]) / 4.0)
            return self._make(1, conf, f"meanrev_bb Dip im Uptrend, RSI {rsi[i]:.0f}, z={z[i]:.2f}",
                              z=round(float(z[i]), 2), rsi=round(float(rsi[i]), 1),
                              sma=round(float(sma[i]), 2), bb_low=round(float(bb_low[i]), 2))
        # Überkaufter Rausch im Abwärtstrend => SELL (Beifang)
        if (spike_sell or z[i] > z_entry) and downtrend:
            conf = min(1.0, 0.5 + z[i] / 4.0)
            return self._make(-1, conf, f"meanrev_bb Spike im Downtrend, RSI {rsi[i]:.0f}, z={z[i]:.2f}",
                              z=round(float(z[i]), 2), rsi=round(float(rsi[i]), 1),
                              sma=round(float(sma[i]), 2), bb_up=round(float(bb_up[i]), 2))
        # Fallback: klassischer z-score
        if z[i] < -z_entry and uptrend:
            conf = min(1.0, 0.5 + abs(z[i]) / 4.0)
            return self._make(1, conf, f"Dip im Uptrend, z={z[i]:.2f}",
                              z=round(float(z[i]), 2), sma=round(float(sma[i]), 2))
        if z[i] > z_entry and downtrend:
            conf = min(1.0, 0.5 + z[i] / 4.0)
            return self._make(-1, conf, f"Spike im Downtrend, z={z[i]:.2f}",
                              z=round(float(z[i]), 2), sma=round(float(sma[i]), 2))
        return self._make(0, 0.3, f"z={z[i]:.2f} normal, RSI {rsi[i]:.0f}",
                          z=round(float(z[i]), 2), rsi=round(float(rsi[i]), 1))


if __name__ == "__main__":
    np.random.seed(2)
    close = np.cumsum(np.random.randn(60) * 0.3) + 100
    high, low = close + 0.5, close - 0.5
    a = MeanRevAgent()
    print(a.vote({"close": close, "high": high, "low": low}))
