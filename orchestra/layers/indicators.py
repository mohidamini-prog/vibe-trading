"""
Layer 1 — Indikator-Layer.

Zentrale, einmalige Berechnung ALLER Indikatoren pro Symbol/Timeframe.
Jeder nachfolgende Layer liest von hier — KEIN Indikator wird doppelt berechnet.
Liefert ein dict mit Arrays/Serien (pandas-nativ, aber auch numpy-Zugriff).
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd


def compute_indicators(df):
    """
    df: OHLCV (open/high/low/close/volume).
    Returns: df mit allen Indikatoren-Spalten (in-place erweitert).
    """
    c = df["close"]
    h = df["high"]
    l = df["low"]
    v = df["volume"]

    # --- Trend (EMA-Fächer) ---
    for p in (9, 20, 21, 50, 200):
        df[f"ema{p}"] = c.ewm(span=p, adjust=False).mean()

    # --- RSI (2, 14, 50) ---
    for period in (2, 14, 50):
        delta = c.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss
        df[f"rsi{period}"] = 100 - (100 / (1 + rs))

    # --- MACD (12, 26, 9) ---
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # --- ATR (14) ---
    hl = h - l
    hc = (h - c.shift()).abs()
    lc = (l - c.shift()).abs()
    df["atr"] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()

    # --- Bollinger (20, 2) ---
    df["bb_mid"] = c.rolling(20).mean()
    df["bb_std"] = c.rolling(20).std()
    df["bb_up"] = df["bb_mid"] + 2 * df["bb_std"]
    df["bb_low"] = df["bb_mid"] - 2 * df["bb_std"]
    df["z"] = (c - df["bb_mid"]) / df["bb_std"]

    # --- Volumen-Qualität ---
    df["vol_median20"] = v.rolling(20).median()
    df["vol_mean20"] = v.rolling(20).mean()
    df["vol_ratio"] = v / df["vol_median20"]  # > 1.25 = Smart Money

    # --- 52-Wochen High/Low (252 Bars) ---
    w = min(252, len(df) // 2) if len(df) > 252 else len(df) // 2
    df["high_52w"] = h.rolling(w).max()
    df["low_52w"] = l.rolling(w).min()

    # --- ADX (14, vereinfacht) ---
    up = c.diff()
    plus_dm = up.where(up > 0, 0)
    minus_dm = (-up).where(up < 0, 0)
    atr14 = df["atr"].replace(0, np.nan)
    df["plus_di"] = 100 * plus_dm.rolling(14).mean() / atr14
    df["minus_di"] = 100 * minus_dm.rolling(14).mean() / atr14
    dx = 100 * (df["plus_di"] - df["minus_di"]).abs() / (df["plus_di"] + df["minus_di"]).replace(0, np.nan)
    df["adx"] = dx.rolling(14).mean()

    # --- Fibonacci (50-Bar Swing High/Low + Retracements) ---
    df["swing_high50"] = h.rolling(50).max()
    df["swing_low50"] = l.rolling(50).min()
    df["fib_range"] = df["swing_high50"] - df["swing_low50"]
    df["fib_382"] = df["swing_high50"] - df["fib_range"] * 0.382
    df["fib_500"] = df["swing_high50"] - df["fib_range"] * 0.500
    df["fib_618"] = df["swing_high50"] - df["fib_range"] * 0.618

    # --- Returns ---
    df["ret"] = c.pct_change()

    return df


def get_snapshot(df, i=-1):
    """Kompaktes dict der Indikator-Werte an Index i (für Springer-Infos/Reasons)."""
    def _v(col):
        try:
            val = df[col].iloc[i]
            return round(float(val), 4) if pd.notna(val) else None
        except Exception:
            return None
    return {
        "close": _v("close"), "rsi2": _v("rsi2"), "rsi14": _v("rsi14"), "rsi50": _v("rsi50"),
        "macd_hist": _v("macd_hist"), "atr": _v("atr"), "adx": _v("adx"),
        "vol_ratio": _v("vol_ratio"), "z": _v("z"),
        "ema50": _v("ema50"), "ema200": _v("ema200"),
        "high_52w": _v("high_52w"), "low_52w": _v("low_52w"),
        "fib_382": _v("fib_382"), "fib_500": _v("fib_500"), "fib_618": _v("fib_618"),
        "bb_up": _v("bb_up"), "bb_low": _v("bb_low"),
    }


if __name__ == "__main__":
    from orchestra.layers.data import load_ohlcv
    df = load_ohlcv("AAPL", "1d")
    df = compute_indicators(df)
    print("Indikatoren berechnet. Spalten:", [c for c in df.columns if c not in ("open", "high", "low", "close", "volume")][:20])
    print("Snapshot letzte Kerze:", get_snapshot(df))
