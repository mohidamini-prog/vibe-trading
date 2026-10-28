"""
SL/TP-Backtest 🎯 — Testet SL/TP-System (S/R + Fib) mit den besten Entry-Modellen.

Fenster: 1d = 5y, 4h = 2y (yfinance-Limits).
Prüft für jede Position, ob SL, TP1 oder TP2 zuerst getroffen wird,
und wertet die Performance mit Teilgewinn-Ausstieg aus.

Einträge bleiben UNVERÄNDERT — nur die Ausstiegs-Ebenen werden getestet.
"""
import sys
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd

from orchestra.layers.data import load_ohlcv
from orchestra.layers.indicators import compute_indicators
from orchestra.sl_tp import compute_sl_tp

US = ["AAPL", "MSFT", "NVDA", "META", "GOOGL", "AMZN", "TSLA"]
DE = ["SAP.DE", "SIE.DE", "BMW.DE", "MBG.DE"]
ALL = US + DE

# Die besten Entry-Modelle (aus vorherigen Backtests)
MODELS = ["new_52w_high_momentum", "sr_flip_breakout", "deep_value_bounce_52w", "fib_pullback_confluence"]

# Teilgewinn-Verteilung: TP1 zuerst schließen (z.B. 50%), TP2 = Rest
TP1_EXIT_PCT = 0.5


def entry_signal(df, model):
    """Entry-Signal für ein Modell (Long-only, wie im Setup)."""
    c = df["close"]
    h = df["high"]
    l = df["low"]
    if model == "new_52w_high_momentum":
        # 52W-Hoch Ausbruch + MACD+ + Volumen-Bestätigung
        cond = (c > df["high_52w"].shift(1)) & (df["macd_hist"] > 0) & (df["vol_ratio"] > 1.25)
        return np.where(cond, 1, 0)
    elif model == "sr_flip_breakout":
        # S/R-Flip: Preis bricht durch vorheriges Hoch + Trend
        cond = (c > df["swing_high50"].shift(1)) & (c > df["ema50"]) & (df["vol_ratio"] > 1.0)
        return np.where(cond, 1, 0)
    elif model == "deep_value_bounce_52w":
        # Deep Value: 52W-Tief + RSI2 extrem + Erholung
        cond = (l <= df["low_52w"].shift(1) * 1.02) & (df["rsi2"] < 10) & (c > df["ema9"])
        return np.where(cond, 1, 0)
    elif model == "fib_pullback_confluence":
        # Fib-Pullback: Rücksetzer auf Fib 50/61,8 + Trend intakt
        cond = (c <= df["fib_618"]) & (c >= df["fib_382"]) & (c > df["ema200"]) & (df["ema50"] > df["ema200"])
        return np.where(cond, 1, 0)
    return np.zeros(len(df))


def backtest_sl_tp(df, model):
    """
    Backtest mit SL/TP-Ausstieg.
    Simuliert jeden Entry, prüft ob SL/TP1/TP2 zuerst getroffen wird.
    Returns: dict mit Statistik.
    """
    if df is None or len(df) < 100:
        return None
    df = compute_indicators(df)
    sig = entry_signal(df, model)
    n = len(df)
    trades = []
    i = 0
    while i < n - 1:
        if sig[i] == 1:
            entry = float(df["close"].iloc[i])
            # SL/TP aus S/R + Fib am Entry-Bar
            sltp = compute_sl_tp(df.iloc[:i + 1], entry, direction=1)
            if sltp and sltp["sl"] is not None and sltp["tp1"] is not None:
                sl, tp1, tp2 = sltp["sl"], sltp["tp1"], sltp["tp2"]
                # Position durchlaufen lassen bis SL/TP1/TP2 oder max 60 Bars
                j = i + 1
                outcome = None
                while j < min(n, i + 60):
                    hi = float(df["high"].iloc[j])
                    lo = float(df["low"].iloc[j])
                    if lo <= sl:
                        outcome = ("SL", j)
                        break
                    if hi >= tp1:
                        # TP1 zuerst -> Teilgewinn sichern, dann auf TP2 warten
                        outcome = ("TP1", j)
                        # Weiter auf TP2 prüfen (nur wenn SL nicht vorher)
                        k = j + 1
                        while k < min(n, i + 60):
                            hi2 = float(df["high"].iloc[k])
                            lo2 = float(df["low"].iloc[k])
                            if lo2 <= sl:
                                outcome = ("TP1_SL", k)
                                break
                            if hi2 >= tp2:
                                outcome = ("TP1_TP2", k)
                                break
                            k += 1
                        if outcome == ("TP1", j):
                            outcome = ("TP1_HOLD", j)
                        break
                    j += 1
                if outcome is None:
                    outcome = ("MAX_BARS", j)
                trades.append({"entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2, "outcome": outcome[0]})
                i = outcome[1] + 1  # nach dem Trade weiter
            else:
                i += 1
        else:
            i += 1

    # Statistik
    if not trades:
        return {"model": model, "n_trades": 0, "hit_rate": 0, "avg_ret": 0, "total_ret": 0, "wins": 0, "losses": 0}
    outcomes = [t["outcome"] for t in trades]
    wins = sum(1 for o in outcomes if o in ("TP1", "TP1_TP2", "TP1_HOLD"))
    losses = sum(1 for o in outcomes if o in ("SL", "TP1_SL"))
    hit_rate = wins / len(trades) if trades else 0
    # Durchschnittlicher Return pro Trade (mit Teilgewinn-Logik)
    rets = []
    for t in trades:
        o = t["outcome"]
        entry = t["entry"]
        if o == "TP1_TP2":
            ret = ((t["tp1"] - entry) / entry) * TP1_EXIT_PCT + ((t["tp2"] - entry) / entry) * (1 - TP1_EXIT_PCT)
        elif o == "TP1":
            ret = (t["tp1"] - entry) / entry
        elif o == "TP1_HOLD":
            ret = (t["tp1"] - entry) / entry * TP1_EXIT_PCT  # nur Teilgewinn
        elif o == "TP1_SL":
            ret = (t["tp1"] - entry) / entry * TP1_EXIT_PCT + (t["sl"] - entry) / entry * (1 - TP1_EXIT_PCT)
        elif o == "SL":
            ret = (t["sl"] - entry) / entry
        else:
            ret = 0
        rets.append(ret)
    avg_ret = float(np.mean(rets)) if rets else 0
    total_ret = float(np.sum(rets)) if rets else 0
    return {
        "model": model, "n_trades": len(trades), "hit_rate": round(hit_rate, 4),
        "avg_ret": round(avg_ret, 4), "total_ret": round(total_ret, 4),
        "wins": wins, "losses": losses,
        "outcomes": {o: outcomes.count(o) for o in set(outcomes)},
    }


if __name__ == "__main__":
    print("SL/TP-BACKTEST (S/R + Fib, ATR-Puffer):")
    print("Fenster: 1d=5y, 4h=2y | Modelle:", ", ".join(MODELS))
    print("=" * 70)
    all_results = []
    for timeframe, period_label in [("1d", "5y"), ("4h", "2y")]:
        for model in MODELS:
            agg = []
            for sym in ALL:
                df = load_ohlcv(sym, timeframe, period=period_label)
                r = backtest_sl_tp(df, model)
                if r and r["n_trades"] > 0:
                    agg.append(r)
            if not agg:
                continue
            n = sum(a["n_trades"] for a in agg)
            hit = np.average([a["hit_rate"] for a in agg], weights=[a["n_trades"] for a in agg])
            avg = np.average([a["avg_ret"] for a in agg], weights=[a["n_trades"] for a in agg])
            tot = sum(a["total_ret"] for a in agg)
            wins = sum(a["wins"] for a in agg)
            losses = sum(a["losses"] for a in agg)
            res = {
                "timeframe": timeframe, "model": model, "n_trades": n,
                "hit_rate": round(float(hit), 4), "avg_ret": round(float(avg), 4),
                "total_ret": round(float(tot), 4), "wins": wins, "losses": losses,
            }
            all_results.append(res)
            print(f"  {timeframe:3s} | {model:28s} | Trades: {n:5d} | Hit: {hit*100:.1f}% | "
                  f"avg: {avg*100:+.2f}% | total: {tot*100:+.1f}% | W/L: {wins}/{losses}")

    # Beste speichern
    out = Path(__file__).parent.parent / "config" / "sl_tp_backtest.json"
    out.write_text(json.dumps(all_results, indent=2))
    print(f"\nGespeichert: {out}")
