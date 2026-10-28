"""
ODER-Logik + Risk-Veto Backtest 🎯
===================================
Brainstorming-Test (NICHTS wird übernommen — nur Schauen):

Fragestellung: Was wäre die Rendite, wenn wir von UND- auf ODER-Logik umstellen?
  - UND:   S > 0.5 (viele Signale zusammen)
  - ODER:  EIN Signal mit conf >= 0.80 allein reicht (starker Einzel-Feuerwerker)

Plus Risk-Veto: Earnings in <= 3 Tagen -> VETO (Order geblockt).

Wir testen 3 Varianten:
  V1: UND (bestehend) ohne Veto
  V2: ODER (conf>=0.80) ohne Veto
  V3: ODER (conf>=0.80) MIT Risk-Veto  <-- Ziel-Empfehlung

Fenster: 1d = 5y, 4h = 2y. Ausstieg: SL/TP aus S/R+Fib.
Nur Backtest-Datei, KEINE Änderung an live_loop/conductor.
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
from orchestra.layers.signals import compute_all_signals
from orchestra.sl_tp import compute_sl_tp

US = ["AAPL", "MSFT", "NVDA", "META", "GOOGL", "AMZN", "TSLA"]
DE = ["SAP.DE", "SIE.DE", "BMW.DE", "MBG.DE"]
ALL = US + DE

# Gewichte wie im Live-System
WEIGHTS = {
    "new_52w_high_momentum": 0.45,
    "sr_flip_breakout": 0.35,
    "deep_value_bounce_52w": 0.15,
    "fib_pullback_confluence": 0.05,
    "meanrev_bb": 0.0,
}

# ODER-Schwelle: einzelnes Signal muss mind. so stark sein
ODER_CONF = 0.80
# UND-Schwelle wie im Conductor
UND_BUY = 0.5
# Earnings-Veto-Puffer in Tagen
VETO_DAYS = 3

TP1_EXIT_PCT = 0.5


def compute_score(signals, filter_passed=True):
    """S-Score wie im Conductor (gewichtet)."""
    total_w = sum(WEIGHTS.get(s["model"], 0.1) for s in signals) or 1.0
    f = 1.0 if filter_passed else 0.5
    S = sum(WEIGHTS.get(s["model"], 0.1) * s["a"] * s["conf"] * f for s in signals) / total_w
    return S


def or_signal_fires(signals):
    """ODER: irgendein Signal mit a=+1 und conf>=ODER_CONF."""
    for s in signals:
        if s["a"] == 1 and s["conf"] >= ODER_CONF:
            return True
    return False


def has_earnings_veto(symbol, date_index, earnings_dates):
    """Prüft, ob am Bar `date_index` ein Earnings-Veto ansteht (<= VETO_DAYS Tage)."""
    if not earnings_dates or symbol not in earnings_dates or not earnings_dates[symbol]:
        return False
    try:
        cur = pd.Timestamp(date_index)
        for ed in earnings_dates[symbol]:
            days = (ed - cur).days
            if 0 <= days <= VETO_DAYS:
                return True
    except Exception:
        pass
    return False


def backtest_orchestra(df, symbol, mode, earnings_dates=None):
    """
    Backtest mit ODER/UND + optional Veto.
    mode: 'und_no_veto' | 'oder_no_veto' | 'oder_veto'
    """
    if df is None or len(df) < 120:
        return None
    df = compute_indicators(df)
    n = len(df)
    trades = []
    i = 0
    while i < n - 1:
        # Signale an Bar i
        sigs = compute_all_signals(df.iloc[:i + 1], i=-1)
        S = compute_score(sigs)
        if mode == "und_no_veto":
            fire = S > UND_BUY
        else:
            fire = or_signal_fires(sigs) or (S > UND_BUY)
        if fire:
            # Risk-Veto prüfen (nur bei 'oder_veto')
            if mode == "oder_veto" and has_earnings_veto(symbol, df.index[i], earnings_dates):
                i += 1
                continue
            entry = float(df["close"].iloc[i])
            sltp = compute_sl_tp(df.iloc[:i + 1], entry, direction=1)
            if sltp and sltp["sl"] is not None and sltp["tp1"] is not None:
                sl, tp1, tp2 = sltp["sl"], sltp["tp1"], sltp["tp2"]
                j = i + 1
                outcome = None
                while j < min(n, i + 60):
                    hi = float(df["high"].iloc[j])
                    lo = float(df["low"].iloc[j])
                    if lo <= sl:
                        outcome = ("SL", j)
                        break
                    if hi >= tp1:
                        outcome = ("TP1", j)
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
                i = outcome[1] + 1
            else:
                i += 1
        else:
            i += 1

    if not trades:
        return {"mode": mode, "n_trades": 0, "hit_rate": 0, "avg_ret": 0, "total_ret": 0}
    outcomes = [t["outcome"] for t in trades]
    wins = sum(1 for o in outcomes if o in ("TP1", "TP1_TP2", "TP1_HOLD"))
    losses = sum(1 for o in outcomes if o in ("SL", "TP1_SL"))
    hit_rate = wins / len(trades) if trades else 0
    rets = []
    for t in trades:
        o = t["outcome"]
        entry = t["entry"]
        if o == "TP1_TP2":
            ret = ((t["tp1"] - entry) / entry) * TP1_EXIT_PCT + ((t["tp2"] - entry) / entry) * (1 - TP1_EXIT_PCT)
        elif o == "TP1":
            ret = (t["tp1"] - entry) / entry
        elif o == "TP1_HOLD":
            ret = (t["tp1"] - entry) / entry * TP1_EXIT_PCT
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
        "mode": mode, "n_trades": len(trades), "hit_rate": round(hit_rate, 4),
        "avg_ret": round(avg_ret, 4), "total_ret": round(total_ret, 4),
        "wins": wins, "losses": losses,
        "outcomes": {o: outcomes.count(o) for o in set(outcomes)},
    }


def load_earnings_dates(symbols, timeframe):
    """Lade Earnings-Daten via yfinance (nur 1d, API-Last begrenzen)."""
    import yfinance as yf
    dates = {}
    for sym in symbols:
        try:
            t = yf.Ticker(sym)
            ed = t.get_earnings_dates(limit=40)
            if ed is not None:
                ds = [pd.Timestamp(idx) for idx in ed.index]
                dates[sym] = ds
        except Exception:
            dates[sym] = []
    return dates


if __name__ == "__main__":
    print("=" * 70)
    print("ODER-LOGIK + RISK-VETO BACKTEST (Brainstorming, NICHTS wird übernommen)")
    print("=" * 70)
    print("Varianten:")
    print("  V1 UND (S>0.5) ohne Veto")
    print("  V2 ODER (conf>=0.80) ohne Veto")
    print("  V3 ODER (conf>=0.80) MIT Risk-Veto (Earnings <= 3 Tage)")
    print("=" * 70)

    MODES = [
        ("V1", "und_no_veto", "UND ohne Veto"),
        ("V2", "oder_no_veto", "ODER ohne Veto"),
        ("V3", "oder_veto", "ODER mit Veto"),
    ]

    all_results = []
    for timeframe, period_label in [("1d", "5y"), ("4h", "2y")]:
        # Earnings nur für 1d laden (Veto greift nur dort)
        earnings_dates = None
        if timeframe == "1d":
            print(f"\nLade Earnings-Daten ({timeframe})...")
            earnings_dates = load_earnings_dates(ALL, timeframe)

        for vname, mode, label in MODES:
            agg = []
            for sym in ALL:
                df = load_ohlcv(sym, timeframe, period=period_label)
                r = backtest_orchestra(df, sym, mode, earnings_dates)
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
                "timeframe": timeframe, "variante": vname, "mode": mode, "label": label,
                "n_trades": n, "hit_rate": round(float(hit), 4),
                "avg_ret": round(float(avg), 4), "total_ret": round(float(tot), 4),
                "wins": wins, "losses": losses,
            }
            all_results.append(res)
            print(f"  {vname} {timeframe:3s} | {label:22s} | Trades: {n:5d} | Hit: {hit*100:.1f}% | "
                  f"avg: {avg*100:+.2f}% | total: {tot*100:+.1f}% | W/L: {wins}/{losses}")

    out = Path(__file__).parent.parent / "config" / "oder_backtest.json"
    out.write_text(json.dumps(all_results, indent=2))
    print(f"\nGespeichert: {out}")
