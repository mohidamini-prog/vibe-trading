"""
Filter-Optimierung: Noise x Volumen x ATR-Grid über Top-Setups.
Findet die beste Filter-Kombination (Balance Trefferquote/PF/MaxDD).
"""
import os, sys, json
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import numpy as np
import pandas as pd
from engine import backtest as bt
from engine import data as data_loader
from universe.universes import US_TOP100, DAX_40

TOP = ["meanrev_oversold", "meanrev_filtered", "momentum_obv"]


def apply_filters(df, base_sig, noise_th, vol_th, atr_pct_th):
    """Wendet Filter auf Basis-Signal an."""
    sig = base_sig.copy()
    sig = sig & (df["noise"] < noise_th)
    sig = sig & (df["vol_ratio"] >= vol_th)
    if atr_pct_th is not None:
        atr_pct = df["atr"] / df["Close"] * 100
        sig = sig & (atr_pct < atr_pct_th)
    return sig.fillna(False)


def main():
    print("=== FILTER-OPTIMIERUNG: Noise x Vol x ATR (5J, 1d) ===")
    print("Lade Daten...")
    data = data_loader.load_universe(US_TOP100 + DAX_40, years=5, timeframe="1d")
    print(f"  {len(data)} Assets\n")

    # Vorberechnen: Indikatoren einmal pro Ticker
    prepped = []
    for ticker, df in data.items():
        try:
            prepped.append((ticker, bt.prepare(df)))
        except Exception:
            pass
    print(f"  {len(prepped)} Assets vorbereitet\n")

    # Filter-Grid
    noise_ths = [45, 50, 55, 60]
    vol_ths = [0.8, 0.9, 1.0, 1.2]
    atr_ths = [None, 3.0, 4.0, 5.0]

    results = []
    total = len(TOP) * len(noise_ths) * len(vol_ths) * len(atr_ths)
    idx = 0
    for setup_name in TOP:
        fn = bt.SETUPS[setup_name]
        # Basis-Signale vorberechnen (pro Ticker)
        base_sigs = {}
        for ticker, prep in prepped:
            base_sigs[ticker] = fn(prep).fillna(False)
        for noise_th in noise_ths:
            for vol_th in vol_ths:
                for atr_th in atr_ths:
                    idx += 1
                    agg = {"n": 0, "wr": 0.0, "net": 0.0, "pf": [], "dd": []}
                    for ticker, prep in prepped:
                        try:
                            sig = apply_filters(prep, base_sigs[ticker], noise_th, vol_th, atr_th)
                            s = bt.backtest(prep, lambda d, _sig=sig: _sig, _prepared=True)
                            if s["n"] > 0:
                                agg["n"] += s["n"]
                                agg["wr"] += s["win_rate"] * s["n"]
                                agg["net"] += s["net_return_pct"]
                                if s["profit_factor"] != float("inf"):
                                    agg["pf"].append(s["profit_factor"])
                                agg["dd"].append(s["max_drawdown"])
                        except Exception:
                            pass
                    n = agg["n"]
                    wr = agg["wr"] / n if n else 0
                    pf = sum(agg["pf"]) / len(agg["pf"]) if agg["pf"] else 0
                    dd = min(agg["dd"]) if agg["dd"] else 0
                    # Score: Balance aus PF + WR - DD-Strafe
                    score = (pf * 0.5) + (wr / 100 * 0.3) - (abs(dd) / 100 * 0.2)
                    results.append({"setup": setup_name, "noise": noise_th, "vol": vol_th,
                                    "atr": atr_th, "n": n, "win_rate": wr,
                                    "net_return_pct": agg["net"], "profit_factor": pf,
                                    "max_drawdown": dd, "score": score})
                    if idx % 40 == 0 or idx == total:
                        print(f"  [{idx}/{total}]")

    results.sort(key=lambda x: -x["score"])
    print("\n" + "=" * 90)
    print("TOP 10 FILTER-KOMBIS (nach Balance-Score)")
    print("=" * 90)
    hdr = "{:>3} {:<20}{:>6}{:>6}{:>6}{:>6}{:>7}{:>8}{:>6}{:>8}".format(
        "#", "SETUP", "Noise", "Vol", "ATR", "Trades", "TREFF%", "Kapital", "PF", "MaxDD")
    print(hdr)
    print("-" * 86)
    for i, r in enumerate(results[:10], 1):
        atr = f"{r['atr']}%" if r["atr"] else "-"
        print("{:>3} {:<20}{:>6}{:>6}{:>6}{:>6}{:>6.1f}%{:>7.1f}%{:>6.2f}{:>8.1f}%".format(
            i, r["setup"], r["noise"], r["vol"], atr, r["n"], r["win_rate"],
            r["net_return_pct"], r["profit_factor"], r["max_drawdown"]))

    out = os.path.join(BASE, "reports", f"filter_optimize_{datetime.now().strftime('%Y%m%d_%H%M')}.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nReport: {out}")


if __name__ == "__main__":
    main()
