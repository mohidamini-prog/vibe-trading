"""
Layer 3 — Filter-Layer (Smart-Money-Qualitätsgates).

Nur Signale, die ALLE Gates passieren, sind "handelbar". Das hebt die Qualität
massiv (weniger, aber deutlich bessere Signale). Jedes Gate liefert (pass, reason).

Gates (aus smart_money_filters.json):
  - volume_quality  : Volumen > 1.25x Median (kein Low-Volume-Fake)
  - trend_macro     : Close > EMA50 > EMA200 (nur im Bullen-Trend)
  - volatility_atr  : ATR nicht eingeschlafen (kein Chop)
  - gap_guard       : kein Exzess-Gap beim Open (> 2x ATR)
  - liquidity_52w   : Preis über 52W-Tief * 1.05 (kein fallendes Messer)
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd


def gate_volume_quality(df, i=-1):
    v = df["vol_ratio"].iloc[i]
    if pd.isna(v):
        return (False, "Volumen unfertig")
    return (v > 1.25, f"Vol {v:.2f}x")


def gate_trend_macro(df, i=-1):
    c = df["close"].iloc[i]
    e50, e200 = df["ema50"].iloc[i], df["ema200"].iloc[i]
    if pd.isna(e50) or pd.isna(e200):
        return (False, "Trend unfertig")
    ok = c > e50 > e200
    return (ok, "Trend OK" if ok else "Kein Bullen-Trend")


def gate_volatility_atr(df, i=-1):
    atr = df["atr"].iloc[i]
    baseline = df["atr"].iloc[max(0, i - 50):i + 1].median() if i >= 0 else atr
    if pd.isna(atr) or pd.isna(baseline) or baseline == 0:
        return (False, "ATR unfertig")
    ok = atr > baseline * 0.8
    return (ok, f"ATR {atr/baseline:.2f}x")


def gate_gap_guard(df, i=-1):
    o, c_prev = df["open"].iloc[i], df["close"].iloc[i - 1] if i >= 1 else df["open"].iloc[i]
    atr = df["atr"].iloc[i]
    if pd.isna(atr) or atr == 0:
        return (True, "kein ATR")  # nicht blockieren wenn unbekannt
    gap = abs(o - c_prev) / c_prev
    ok = gap < (2 * atr / c_prev)
    return (ok, "Gap ok" if ok else f"Gap {gap*100:.1f}%")


def gate_liquidity_52w(df, i=-1):
    c = df["close"].iloc[i]
    lo52 = df["low_52w"].iloc[i]
    if pd.isna(lo52):
        return (False, "52W unfertig")
    ok = c > lo52 * 1.05
    return (ok, "über 52W-Tief" if ok else "unter 52W-Tief")


ALL_GATES = {
    "volume_quality": gate_volume_quality,
    "trend_macro": gate_trend_macro,
    "volatility_atr": gate_volatility_atr,
    "gap_guard": gate_gap_guard,
    "liquidity_52w": gate_liquidity_52w,
}


def apply_filters(df, i=-1, gates=None):
    """
    Wendet alle Gates an. Returns: (passed, report)
      passed = True nur wenn ALLE Gates passen.
      report = {"all": {gate: reason}, "blocks": {gate: reason_nur_blockiert}, "passed": {gate: reason_pass}}
    """
    gates = gates or list(ALL_GATES.keys())
    all_results = {}
    blocks = {}
    passed_results = {}
    all_pass = True
    for g in gates:
        fn = ALL_GATES.get(g)
        if fn is None:
            continue
        ok, reason = fn(df, i)
        all_results[g] = reason
        if ok:
            passed_results[g] = reason
        else:
            blocks[g] = reason
            all_pass = False
    report = {"all": all_results, "blocks": blocks, "passed": passed_results}
    return (all_pass, report)


if __name__ == "__main__":
    from orchestra.layers.data import load_ohlcv
    from orchestra.layers.indicators import compute_indicators
    df = compute_indicators(load_ohlcv("AAPL", "1d"))
    passed, reasons = apply_filters(df)
    print("Filter AAPL letzte Kerze:", "PASS" if passed else "BLOCK")
    for g, r in reasons.items():
        print(f"  {g:18s}: {r}")
