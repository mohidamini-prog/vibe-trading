"""A/B-Test: Stoppen die Bollinger Bands die Performance?
Vergleicht RSI<32 allein vs. RSI<32+BB-Lower vs. RSI<32+BB-Lower+bounce.
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


def setup_rsi_only(df, rsi_th=32):
    """Nur RSI < Schwelle, OHNE Bollinger."""
    return (df["rsi"] < rsi_th).fillna(False)


def setup_rsi_bb(df, rsi_th=32):
    """RSI < Schwelle + unteres BB-Lower (aktuell)."""
    oversold = df["rsi"] < rsi_th
    at_lower = df["Close"] <= df["bb_lower"]
    return (oversold & at_lower).fillna(False)


def setup_rsi_bb_bounce(df, rsi_th=32):
    """RSI < Schwelle + BB-Lower + Bounce (das aktuelle Setup)."""
    oversold = df["rsi"] < rsi_th
    at_lower = df["Close"] <= df["bb_lower"]
    bounce = df["Close"].shift(1) < df["bb_lower"].shift(1)
    return (oversold & (at_lower | bounce)).fillna(False)


def setup_rsi_bb_loose(df, rsi_th=32, bb_mult=0.5):
    """RSI < Schwelle + Preis nur nahe BB-Lower (0.5*ATR über Lower)."""
    oversold = df["rsi"] < rsi_th
    near_lower = df["Close"] <= (df["bb_lower"] + bb_mult * df["atr"])
    return (oversold & near_lower).fillna(False)


VARIANTS = {
    "rsi_only": setup_rsi_only,
    "rsi_bb": setup_rsi_bb,
    "rsi_bb_bounce": setup_rsi_bb_bounce,
    "rsi_bb_loose": setup_rsi_bb_loose,
}


def main():
    print("=== A/B-TEST: Bollinger Bands Stoppen die Performance? (5J, 1d) ===")
    print("Lade Daten...")
    data = data_loader.load_universe(US_TOP100 + DAX_40, years=5, timeframe="1d")
    print(f"  {len(data)} Assets\n")

    # Vorberechnen
    prepped = []
    for ticker, df in data.items():
        try:
            prepped.append((ticker, bt.prepare(df)))
        except Exception:
            pass
    print(f"  {len(prepped)} Assets vorbereitet\n")

    results = []
    for name, fn in VARIANTS.items():
        agg = {"n": 0, "wr": 0.0, "net": 0.0, "pf": [], "dd": []}
        for ticker, prep in prepped:
            try:
                sig = fn(prep).fillna(False)
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
        results.append({"variant": name, "n": n, "win_rate": wr,
                        "net_return_pct": agg["net"], "profit_factor": pf,
                        "max_drawdown": dd})
        print(f"  {name:<16} T={n:<5} WR={wr:5.1f}%  Net={agg['net']:+8.1f}%  PF={pf:5.2f}  DD={dd:6.1f}%")

    # Save
    out = os.path.join(BASE, "reports", f"ab_bb_{datetime.now().strftime('%Y%m%d_%H%M')}.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nReport: {out}")


if __name__ == "__main__":
    main()
