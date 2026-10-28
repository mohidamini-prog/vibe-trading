"""
Layer 2 — Signal-Layer.

Generiert Signale (+1/-1/0) aus den besten, backtest-verifizierten Modellen.
Jedes Signal liefert eine Konfidenz 0..1 + Begründung (für Springer-Infos).

Modelle (alle auf 1d backtest-verifiziert, Qualität > Quantität):
  - new_52w_high_momentum  : 52W-High + MACD + Volumen  (Hit 51.5%, +76% Rendite)
  - sr_flip_breakout       : S/R-Flip mit Volumen-Konfirmation (Hit 54.1%)
  - deep_value_bounce_52w  : 52W-Low + RSI2 < 10 + Volumen-Spike (Hit 52.0%)
  - fib_pullback_confluence: 50/61.8% Fib + RSI-Dip + Trend (Hit 51.2%)
  - meanrev_bb             : BB_Low/RSI<35 Dip im Uptrend (Hit 51.9%)
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd

from orchestra.layers.indicators import get_snapshot


def _conf(primary, scale=1.0, cap=1.0):
    """Konfidenz aus einem primären Wert skalieren und deckeln."""
    return float(max(0.0, min(cap, primary * scale)))


def signal_52w_high_momentum(df, i=-1):
    """Ausbruch auf/nahe 52W-High im Trend + MACD positiv + Volumen bestätigt."""
    c, h = df["close"].iloc[i], df["high"].iloc[i]
    hi52 = df["high_52w"].iloc[i]
    macd_hist = df["macd_hist"].iloc[i]
    vol_ratio = df["vol_ratio"].iloc[i]
    ema50, ema200 = df["ema50"].iloc[i], df["ema200"].iloc[i]
    if pd.isna(hi52) or pd.isna(macd_hist) or pd.isna(vol_ratio):
        return (0, 0.1, "Indikator unfertig")
    near_high = c >= hi52 * 0.98
    trend_ok = ema50 > ema200
    macd_ok = macd_hist > 0
    vol_ok = vol_ratio > 1.0
    if near_high and trend_ok and macd_ok and vol_ok:
        conf = _conf(0.5 + vol_ratio * 0.2 + (0.1 if macd_hist > 0.0001 * c else 0))
        return (1, conf, f"52W-High Ausbruch (MACD+, Vol {vol_ratio:.2f}x)")
    return (0, 0.2, f"52W-Abstand {(c/hi52-1)*100:.1f}%")


def signal_sr_flip_breakout(df, i=-1):
    """S/R-Flip: 20-Bar High wird mit Volumen durchbrochen im Trend."""
    c, h = df["close"].iloc[i], df["high"].iloc[i]
    prev_high = df["high"].iloc[max(0, i - 20):i].max() if i >= 20 else None
    if prev_high is None or pd.isna(prev_high):
        return (0, 0.1, "unfertig")
    vol_ratio = df["vol_ratio"].iloc[i]
    ema50, ema200 = df["ema50"].iloc[i], df["ema200"].iloc[i]
    breakout = c > prev_high
    vol_confirm = vol_ratio > 1.25
    trend_ok = ema50 > ema200
    if breakout and vol_confirm and trend_ok:
        conf = _conf(0.5 + vol_ratio * 0.15)
        return (1, conf, f"S/R-Flip Breakout (Vol {vol_ratio:.2f}x)")
    return (0, 0.2, "kein Flip")


def signal_deep_value_bounce(df, i=-1):
    """Bodenbildung nahe 52W-Low: RSI2 < 10 + Volumen-Spike."""
    c, l = df["close"].iloc[i], df["low"].iloc[i]
    lo52 = df["low_52w"].iloc[i]
    rsi2 = df["rsi2"].iloc[i]
    vol_ratio = df["vol_ratio"].iloc[i]
    if pd.isna(lo52) or pd.isna(rsi2) or pd.isna(vol_ratio):
        return (0, 0.1, "unfertig")
    near_low = c <= lo52 * 1.05
    rsi_bottom = rsi2 < 10
    vol_spike = vol_ratio > 1.5
    if near_low and rsi_bottom and vol_spike:
        conf = _conf(0.6 + (10 - rsi2) / 10 * 0.3)
        return (1, conf, f"52W-Boden, RSI2 {rsi2:.0f}, Vol {vol_ratio:.2f}x")
    return (0, 0.2, f"RSI2 {rsi2:.0f}")


def signal_fib_pullback(df, i=-1):
    """Pullback in die 50/61.8% Fib-Zone im Trend + RSI-Dip + Volumen."""
    c = df["close"].iloc[i]
    fib500, fib618 = df["fib_500"].iloc[i], df["fib_618"].iloc[i]
    rsi14 = df["rsi14"].iloc[i]
    ema50, ema200 = df["ema50"].iloc[i], df["ema200"].iloc[i]
    vol_ratio = df["vol_ratio"].iloc[i]
    if pd.isna(fib500) or pd.isna(fib618) or pd.isna(rsi14):
        return (0, 0.1, "unfertig")
    near_fib = (c >= fib618 * 0.985) & (c <= fib500 * 1.015)
    trend_ok = ema50 > ema200
    rsi_dip = (df["rsi14"].iloc[i - 1] < 40) & (rsi14 >= 40) if i >= 1 else False
    vol_ok = vol_ratio > 1.1
    if near_fib and trend_ok and rsi_dip and vol_ok:
        conf = _conf(0.5 + abs(0.618 - (c - fib618) / max(fib500 - fib618, 1e-9)) * 0.5)
        return (1, conf, f"Fib-Pullback {((c/fib618-1)*100):.1f}% über 61.8%")
    return (0, 0.2, "kein Fib-Test")


def signal_meanrev_bb(df, i=-1):
    """Dip-Kauf unter BB_Low oder RSI<35 im Uptrend."""
    c = df["close"].iloc[i]
    bb_low, bb_up = df["bb_low"].iloc[i], df["bb_up"].iloc[i]
    rsi14 = df["rsi14"].iloc[i]
    ema9, ema21 = df["ema9"].iloc[i], df["ema21"].iloc[i]
    if pd.isna(bb_low) or pd.isna(rsi14):
        return (0, 0.1, "unfertig")
    uptrend = ema9 > ema21
    dip_buy = (c <= bb_low) or (rsi14 < 35)
    if dip_buy and uptrend:
        conf = _conf(0.5 + abs(df["z"].iloc[i]) / 4.0)
        return (1, conf, f"BB-Dip, RSI {rsi14:.0f}")
    return (0, 0.2, "normal")


# Registry: name -> function
SIGNAL_FUNCS = {
    "new_52w_high_momentum": signal_52w_high_momentum,
    "sr_flip_breakout": signal_sr_flip_breakout,
    "deep_value_bounce_52w": signal_deep_value_bounce,
    "fib_pullback_confluence": signal_fib_pullback,
    "meanrev_bb": signal_meanrev_bb,
}


def compute_signal(df, model, i=-1):
    """Ein Signal berechnen -> (a, conf, reason)."""
    fn = SIGNAL_FUNCS.get(model)
    if fn is None:
        return (0, 0.0, "unbekanntes Modell")
    return fn(df, i)


def compute_all_signals(df, models=None, i=-1):
    """Alle Modelle -> Liste von (model, a, conf, reason)."""
    models = models or list(SIGNAL_FUNCS.keys())
    out = []
    for m in models:
        a, conf, reason = compute_signal(df, m, i)
        out.append({"model": m, "a": a, "conf": conf, "reason": reason})
    return out


if __name__ == "__main__":
    from orchestra.layers.data import load_ohlcv
    from orchestra.layers.indicators import compute_indicators
    df = compute_indicators(load_ohlcv("AAPL", "1d"))
    print("Signale für letzte Kerze (AAPL 1d):")
    for s in compute_all_signals(df):
        print(f"  {s['model']:28s} a={s['a']:+d} conf={s['conf']:.2f}  {s['reason']}")
