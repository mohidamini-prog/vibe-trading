"""
Verfeinerungs-Grid: RSI x Volumen x EMA-Trendfilter über dem besten Setup.
Basis: meanrev_oversold. Variiert systematisch die Parameter, um die
optimale Kombination (hohe Trefferquote + Kapitalrendite + PF) zu finden.
"""
import os
import sys
import json
import time
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import numpy as np
import pandas as pd
from engine import backtest as bt
from engine import data as data_loader
from universe.universes import ALL


def refine_setup(df, rsi_th, vol_min, ema_filter):
    """
    Verfeinerte Mean-Reversion:
    - RSI < rsi_th (überverkauft)
    - Close am/unter unterem Bollinger-Band (Oder-Rückprall)
    - Optional: Volumen-Verhältnis >= vol_min
    - Optional: EMA-Trendfilter (nur Longs im übergeordneten Trend)
    """
    oversold = df["rsi"] < rsi_th
    at_lower = df["Close"] <= df["bb_lower"]
    bounce = df["Close"].shift(1) < df["bb_lower"].shift(1)
    base = oversold & (at_lower | bounce)

    if vol_min is not None:
        base = base & (df["vol_ratio"] >= vol_min)

    if ema_filter == "ema50>ema200":
        base = base & (df["ema50"] > df["ema200"])
    elif ema_filter == "ema20>ema200":
        base = base & (df["ema20"] > df["ema200"])
    elif ema_filter == "ema50>ema20":
        base = base & (df["ema50"] > df["ema20"])
    # None = kein Trendfilter

    return base


def run_refine(years=5, markets="ALL", timeframe="1d", max_hold=30, cost_bps=10.0, position_pct=0.10):
    tickers = ALL
    print(f"=== REFINE-GRID: {len(tickers)} Assets, {years}J, {timeframe}, "
          f"max_hold={max_hold}, {cost_bps}bps, {position_pct:.0%} Kapital ===")
    print("Lade Daten...")
    t0 = time.time()
    data = data_loader.load_universe(tickers, years=years, timeframe=timeframe, refresh=False)
    print(f"  {len(data)} Assets in {time.time()-t0:.1f}s\n")

    # Parameter-Grid
    rsi_ths = [25, 28, 30, 32, 35]
    vol_mins = [None, 0.7, 0.9, 1.0, 1.2, 1.5]
    ema_filters = [None, "ema50>ema200", "ema20>ema200", "ema50>ema20"]
    grid = [(r, v, e) for r in rsi_ths for v in vol_mins for e in ema_filters]
    print(f"GRID: {len(grid)} Kombinationen (RSI x Volumen x EMA-Filter)\n")

    results = []
    total = len(grid)
    # Vorberechnung: Indikatoren pro Ticker NUR EINMAL, dann für alle Kombis wiederverwenden
    print("  Bereite Indikatoren vor (einmal pro Ticker)...")
    prepped = []
    for ticker, df in data.items():
        try:
            prepped.append((ticker, bt.prepare(df)))
        except Exception:
            pass
    print(f"  {len(prepped)} Assets vorbereitet\n")

    for idx, (rsi_th, vol_min, ema_filter) in enumerate(grid, 1):
        sig_name = f"RSI<{rsi_th}"
        if vol_min is not None:
            sig_name += f" +Vol>={vol_min}"
        if ema_filter:
            sig_name += f" +{ema_filter}"

        agg = {"n": 0, "wr_num": 0.0, "avg_num": 0.0, "total_pnl": 0.0,
               "pf_vals": [], "dd_vals": [], "net_ret": 0.0, "assets_ok": 0}

        for ticker, prep in prepped:
            try:
                sig = refine_setup(prep, rsi_th, vol_min, ema_filter)
                s = bt.backtest(prep, lambda d, _sig=sig: _sig,
                                max_hold=max_hold, cost_bps=cost_bps,
                                position_pct=position_pct, _prepared=True)
                if s["n"] > 0:
                    agg["n"] += s["n"]
                    agg["wr_num"] += s["win_rate"] * s["n"]
                    agg["avg_num"] += s["avg_pnl"] * s["n"]
                    agg["total_pnl"] += s["total_pnl"]
                    if s["profit_factor"] != float("inf"):
                        agg["pf_vals"].append(s["profit_factor"])
                    agg["dd_vals"].append(s["max_drawdown"])
                    agg["net_ret"] += s["net_return_pct"]
                    agg["assets_ok"] += 1
            except Exception:
                pass

        wr = agg["wr_num"] / agg["n"] if agg["n"] else 0
        avg = agg["avg_num"] / agg["n"] if agg["n"] else 0
        pf = sum(agg["pf_vals"]) / len(agg["pf_vals"]) if agg["pf_vals"] else 0
        dd = min(agg["dd_vals"]) if agg["dd_vals"] else 0
        results.append({
            "rsi_th": rsi_th, "vol_min": vol_min, "ema_filter": ema_filter,
            "sig_name": sig_name, "n": agg["n"], "win_rate": wr,
            "avg_pnl": avg, "total_pnl": agg["total_pnl"],
            "profit_factor": pf, "max_drawdown": dd,
            "net_return_pct": agg["net_ret"], "assets_ok": agg["assets_ok"],
        })
        print(f"  [{idx:>3}/{total}] {sig_name:<44} Trades={agg['n']:<5} "
              f"WR={wr:5.1f}% Kapital={agg['net_ret']:+8.1f}% PF={pf:5.2f}")

    # Sortieren nach Kapitalrendite
    results.sort(key=lambda x: -x["net_return_pct"])
    print("\n" + "=" * 90)
    print("BESTE VERFEINERUNGEN (nach Kapitalrendite)")
    print("=" * 90)
    hdr = "{:>3} {:<44}{:>7}{:>7}{:>10}{:>7}{:>8}".format(
        "#", "SIGNAL", "Trades", "TREFF%", "Kapital", "PF", "MaxDD")
    print(hdr)
    print("-" * 86)
    for i, r in enumerate(results[:15], 1):
        print("{:>3} {:<44}{:>7}{:>6.1f}%{:>9.1f}%{:>7.2f}{:>8.1f}%".format(
            i, r["sig_name"], r["n"], r["win_rate"], r["net_return_pct"],
            r["profit_factor"], r["max_drawdown"]))

    # Report speichern
    out = os.path.join(BASE, "reports", f"refine_{datetime.now().strftime('%Y%m%d_%H%M')}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump({"meta": {"years": years, "timeframe": timeframe, "n_assets": len(data)},
                   "results": results}, f, indent=2, default=str)
    print(f"\nReport: {out}")
    return results


if __name__ == "__main__":
    run_refine()
