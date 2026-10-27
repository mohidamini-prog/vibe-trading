"""
Tier 1 — WICHTIG (60% Gewicht), läuft IMMER.

Nur das Nötigste, lokal gecached, max 100 Kerzen.
OHLCV 1min/5min, nur Close + Volume reicht oft.
Kosten: ~2KB pro Aktie alle 5min.
"""
from orchestra.config import get
from orchestra.data import cache
from orchestra.utils import indicators
import numpy as np


def fetch_tier1(symbol, timeframe=None, limit=None, use_cache=True):
    """OHLCV (close, volume) für Tier 1. Nutzt yfinance wenn kein Cache."""
    timeframe = timeframe or get("timeframes.base", "5m")
    limit = limit or get("tiers.tier1.max_candles", 100)
    cached = cache.get_candles(symbol, timeframe, limit) if use_cache else []
    if len(cached) >= limit:
        return cached
    # Sonst frisch von yfinance (datenarm: nur close+volume)
    try:
        import yfinance as yf
        # yfinance period nur als grobe Range (1d/5d/1mo/...), Interval macht die Feinheit
        period = "1mo" if limit <= 100 else "3mo"
        df = yf.Ticker(symbol).history(period=period, interval=timeframe,
                                       auto_adjust=True)
        if df is None or df.empty:
            return cached
        close = df["Close"].to_numpy()
        volume = df["Volume"].to_numpy()
        ts = df.index.astype("int64") // 10**9
        # Indikatoren (numpy-only, ARM-schnell)
        e9 = indicators.ema(close, get("agents.momentum.ema_fast", 9))
        e21 = indicators.ema(close, get("agents.momentum.ema_slow", 21))
        z = indicators.zscore(close, get("agents.meanrev.sma_period", 20))
        rows = []
        for i, (c, v) in enumerate(zip(close, volume)):
            if np.isnan(c) or np.isnan(v):
                continue
            e9v = e9[i] if not np.isnan(e9[i]) else None
            e21v = e21[i] if not np.isnan(e21[i]) else None
            zv = z[i] if not np.isnan(z[i]) else None
            rows.append((symbol, int(ts[i]), timeframe, float(c), float(v), e9v, e21v, zv))
        cache.upsert_candles(rows)
        return cache.get_candles(symbol, timeframe, limit)
    except Exception as e:
        # Bei yfinance-Drossel: Cache-Fallback
        return cached or {"error": str(e), "symbol": symbol}


if __name__ == "__main__":
    sym = get("universe.symbols", ["AAPL"])[0]
    data = fetch_tier1(sym)
    print(f"Tier1 {sym}: {len(data)} Kerzen geladen")
    if data and not isinstance(data, dict):
        print("Letzte:", data[-1])
