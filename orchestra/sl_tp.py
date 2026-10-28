"""
SL/TP-Modul 🎯 — Stop-Loss & Take-Profit aus Support/Resistance + Fibonacci.

Prinzip (User-Vorgabe):
  SL/TP werden NICHT über ATR, sondern über echte Preisniveaus berechnet:
    - Support/Resistance (Swing-Hochs/Tiefs)
    - Fibonacci-Retracements/-Extensions
  ATR dient NUR als Mindest-Puffer, damit normale Schwankung den Stop nicht
  zu früh auslöst (kein "Niveau-Terror").

  SL  = unter dem nächsten Support (bzw. 61,8% Fib-Retracement)
  TP1 = am nächsten Resistance (bzw. 127,2% Fib-Extension) — Teilgewinn
  TP2 = höherer Resistance (bzw. 161,8% Fib-Extension) — Trend-Rest

Einträge/Signale werden NICHT verändert — nur die Ausstiegs-Ebenen.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd


# --- Niveau-Finder: Support/Resistance aus Swing-Punkten ---
def find_support_resistance(df, lookback=50, n_levels=3):
    """
    Findet Support/Resistance-Niveaus aus Swing-Hochs/-Tiefs.
    Returns: (supports_sorted_desc, resistances_sorted_asc)
      supports:  [höchster_unterhalb_preis, ...]  (absteigend)
      resistances: [niedrigster_oberhalb_preis, ...] (aufsteigend)
    """
    if df is None or len(df) < 30:
        return [], []
    h = df["high"].values
    l = df["low"].values
    c = df["close"].values
    price = c[-1]

    # Swing-Punkte: lokale Hochs/Tiefs mit Fenster w
    w = max(3, lookback // 10)
    highs, lows = [], []
    for i in range(max(w, len(df) - lookback), len(df) - 1):
        if i - w < 0:
            continue
        win_h = h[i - w:i + w + 1]
        win_l = l[i - w:i + w + 1]
        if h[i] == win_h.max() and h[i] >= win_h.mean():
            highs.append(h[i])
        if l[i] == win_l.min() and l[i] <= win_l.mean():
            lows.append(l[i])

    # Niveaus: unterhalb (Support) und oberhalb (Resistance) des Preises
    supports = sorted([x for x in lows if x < price], reverse=True)
    resistances = sorted([x for x in highs if x > price])

    # Auf n_levels reduzieren (nächste zuerst)
    return supports[:n_levels], resistances[:n_levels]


def compute_fib_levels(df, lookback=50):
    """
    Fibonacci-Niveaus aus dem letzten Swing (Hoch-Tief-Range).
    Returns: {
      "high": swing_high, "low": swing_low,
      "retrace_382": ..., "retrace_500": ..., "retrace_618": ...,
      "ext_1272": ..., "ext_1618": ...
    }
    """
    if df is None or len(df) < 30:
        return {}
    h = df["high"].rolling(lookback).max().iloc[-1]
    l = df["low"].rolling(lookback).min().iloc[-1]
    rng = h - l
    if rng <= 0:
        return {}
    return {
        "high": h, "low": l,
        "retrace_382": h - rng * 0.382,
        "retrace_500": h - rng * 0.500,
        "retrace_618": h - rng * 0.618,
        "ext_1272": h + rng * 0.272,   # 127,2% Extension
        "ext_1618": h + rng * 0.618,   # 161,8% Extension
    }


def compute_sl_tp(df, entry, direction=1, atr_mult_buffer=1.0):
    """
    Berechnet SL, TP1, TP2 aus S/R + Fib-Niveaus (ATR nur als Puffer).

    direction: +1 = Long, -1 = Short.
    Returns: {
      "sl": ..., "tp1": ..., "tp2": ...,
      "sl_source": ..., "tp1_source": ..., "tp2_source": ...,
      "atr": ..., "rr1": ..., "rr2": ...
    }
    """
    if df is None or len(df) < 30:
        return None

    atr = float(df["atr"].iloc[-1]) if "atr" in df.columns else None
    supports, resistances = find_support_resistance(df)
    fib = compute_fib_levels(df)
    price = float(df["close"].iloc[-1]) if "close" in df.columns else entry

    if direction > 0:  # LONG
        # SL: nächster Support unter Entry (oder Fib 61,8%), ATR-Puffer
        sl = None
        sl_src = "kein Niveau"
        for s in supports:
            if s < entry:
                sl = s
                sl_src = "Support"
                break
        if sl is None and fib.get("retrace_618") is not None and fib["retrace_618"] < entry:
            sl = fib["retrace_618"]
            sl_src = "Fib 61,8%"
        # ATR-Puffer: Stop minimal atr_mult_buffer*ATR unter Entry
        if atr and atr > 0:
            buffer = entry - atr * atr_mult_buffer
            if sl is None or buffer < sl:
                sl = buffer
                sl_src = sl_src if sl is not None else "ATR-Puffer"
        # TP1: nächster Resistance über Entry (oder Fib 127,2%)
        tp1 = None
        tp1_src = "kein Niveau"
        for r in resistances:
            if r > entry:
                tp1 = r
                tp1_src = "Resistance"
                break
        if tp1 is None and fib.get("ext_1272") is not None and fib["ext_1272"] > entry:
            tp1 = fib["ext_1272"]
            tp1_src = "Fib 127,2%"
        # TP2: höherer Resistance (oder Fib 161,8%)
        tp2 = None
        tp2_src = "kein Niveau"
        if len(resistances) > 1 and resistances[1] > entry:
            tp2 = resistances[1]
            tp2_src = "Resistance 2"
        if tp2 is None and fib.get("ext_1618") is not None and fib["ext_1618"] > entry:
            tp2 = fib["ext_1618"]
            tp2_src = "Fib 161,8%"
    else:  # SHORT
        sl = None
        sl_src = "kein Niveau"
        for r in resistances:
            if r > entry:
                sl = r
                sl_src = "Resistance"
                break
        if sl is None and fib.get("retrace_618") is not None and fib["retrace_618"] > entry:
            sl = fib["retrace_618"]
            sl_src = "Fib 61,8%"
        if atr and atr > 0:
            buffer = entry + atr * atr_mult_buffer
            if sl is None or buffer > sl:
                sl = buffer
                sl_src = sl_src if sl is not None else "ATR-Puffer"
        tp1 = None
        tp1_src = "kein Niveau"
        for s in supports:
            if s < entry:
                tp1 = s
                tp1_src = "Support"
                break
        if tp1 is None and fib.get("ext_1272") is not None and fib["ext_1272"] < entry:
            tp1 = fib["ext_1272"]
            tp1_src = "Fib 127,2%"
        tp2 = None
        tp2_src = "kein Niveau"
        if len(supports) > 1 and supports[1] < entry:
            tp2 = supports[1]
            tp2_src = "Support 2"
        if tp2 is None and fib.get("ext_1618") is not None and fib["ext_1618"] < entry:
            tp2 = fib["ext_1618"]
            tp2_src = "Fib 161,8%"

    # Risiko-Reward-Verhältnisse
    rr1 = rr2 = None
    if sl is not None and entry != sl:
        if direction > 0:
            rr1 = (tp1 - entry) / (entry - sl) if tp1 is not None else None
            rr2 = (tp2 - entry) / (entry - sl) if tp2 is not None else None
        else:
            rr1 = (entry - tp1) / (sl - entry) if tp1 is not None else None
            rr2 = (entry - tp2) / (sl - entry) if tp2 is not None else None

    return {
        "sl": round(float(sl), 4) if sl is not None else None,
        "tp1": round(float(tp1), 4) if tp1 is not None else None,
        "tp2": round(float(tp2), 4) if tp2 is not None else None,
        "sl_source": sl_src, "tp1_source": tp1_src, "tp2_source": tp2_src,
        "atr": round(float(atr), 4) if atr is not None else None,
        "rr1": round(float(rr1), 2) if rr1 is not None else None,
        "rr2": round(float(rr2), 2) if rr2 is not None else None,
    }


if __name__ == "__main__":
    # Test mit echten Daten
    from orchestra.layers.data import load_ohlcv
    from orchestra.layers.indicators import compute_indicators
    df = load_ohlcv("AAPL", "1d")
    df = compute_indicators(df)
    entry = float(df["close"].iloc[-1])
    print(f"AAPL 1d — Entry: {entry:.2f}")
    res = compute_sl_tp(df, entry, direction=1)
    print(f"  SL  : {res['sl']} ({res['sl_source']})")
    print(f"  TP1 : {res['tp1']} ({res['tp1_source']})  RR={res['rr1']}")
    print(f"  TP2 : {res['tp2']} ({res['tp2_source']})  RR={res['rr2']}")
    print(f"  ATR : {res['atr']}")
