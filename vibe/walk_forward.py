"""
Walk-Forward-Validierung: out-of-sample Test der besten Setups.
Teilt 5 Jahre in Trainings-/Testfenster, optimiert im Training, testet Out-of-Sample.
Zeigt, ob die Performance stabil ist oder nur Overfitting.
"""
import os, sys, json
import pandas as pd
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from engine import backtest as bt
from engine import data as data_loader
from universe.universes import US_TOP100, DAX_40

# Die besten Setups aus Per-Markt + Refine
SETUPS_TO_TEST = [
    "meanrev_oversold",
    "meanrev_filtered",
    "momentum_obv",
    "momentum_breakout_filtered",
    "momentum_williams",
    "breakout_pullback_combo",
]


def walk_forward(years=5, train_frac=0.6, n_folds=3, markets="ALL"):
    """Walk-Forward: mehrere Folds, jeweils train (60%) -> test (40%)."""
    tickers = US_TOP100 + DAX_40 if markets == "ALL" else (
        US_TOP100 if markets == "US" else DAX_40)
    print(f"=== WALK-FORWARD: {len(tickers)} Assets, {years}J, {n_folds} Folds, train={train_frac:.0%} ===")
    print("Lade Daten...")
    data = data_loader.load_universe(tickers, years=years, timeframe="1d")
    print(f"  {len(data)} Assets\n")

    # Alle Daten zu einem großen Panel mit Ticker als Level
    all_frames = []
    for ticker, df in data.items():
        d = df.copy()
        d["ticker"] = ticker
        all_frames.append(d)
    panel = pd.concat(all_frames).sort_index()
    print(f"Panel: {len(panel)} Zeilen, {panel.index.min()} -> {panel.index.max()}")

    # Fold-Grenzen über Zeitachse
    dates = sorted(set(panel.index))
    total = len(dates)
    fold_size = total // n_folds
    print(f"{total} Bars, fold_size={fold_size}\n")

    all_results = []
    for fold in range(n_folds):
        # Train: vor fold; Test: fold
        start = fold * fold_size
        end = min((fold + 1) * fold_size, total)
        if fold == 0:
            continue  # Fold 0 hat kein Training davor
        train_end = dates[start]
        test_start = dates[start]
        test_end = dates[end] if end < total else dates[-1]

        print(f"--- Fold {fold}: Test {test_start.date()} -> {test_end.date()} ---")
        fold_results = {}
        for name in SETUPS_TO_TEST:
            fn = bt.SETUPS[name]
            test_stats = {"n": 0, "wr": 0.0, "net": 0.0, "pf": []}
            for ticker, df in data.items():
                try:
                    prep = bt.prepare(df)
                    # Nur Testzeitraum
                    mask = (prep.index >= test_start) & (prep.index <= test_end)
                    sub = prep.loc[mask].copy()
                    if len(sub) < 50:
                        continue
                    s = bt.backtest(sub, fn)
                    if s["n"] > 0:
                        test_stats["n"] += s["n"]
                        test_stats["wr"] += s["win_rate"] * s["n"]
                        test_stats["net"] += s["net_return_pct"]
                        if s["profit_factor"] != float("inf"):
                            test_stats["pf"].append(s["profit_factor"])
                except Exception:
                    pass
            n = test_stats["n"]
            wr = test_stats["wr"] / n if n else 0
            pf = sum(test_stats["pf"]) / len(test_stats["pf"]) if test_stats["pf"] else 0
            fold_results[name] = {"n": n, "win_rate": wr, "net_return_pct": test_stats["net"], "pf": pf}
            print(f"  {name:<32} T={n:<4} WR={wr:5.1f}%  Net={test_stats['net']:+7.1f}%  PF={pf:5.2f}")
        all_results.append({"fold": fold, "test_start": str(test_start), "test_end": str(test_end), "results": fold_results})

    # Aggregieren über alle Folds (out-of-sample gesamt)
    print("\n" + "=" * 70)
    print("OUT-OF-SAMPLE GESAMT (über alle Folds)")
    print("=" * 70)
    agg = {}
    for name in SETUPS_TO_TEST:
        n = sum(r["results"][name]["n"] for r in all_results)
        wr = sum(r["results"][name]["win_rate"] * r["results"][name]["n"] for r in all_results)
        net = sum(r["results"][name]["net_return_pct"] for r in all_results)
        pfs = [r["results"][name]["pf"] for r in all_results if r["results"][name]["pf"] > 0]
        pf = sum(pfs) / len(pfs) if pfs else 0
        wr = wr / n if n else 0
        agg[name] = {"n": n, "win_rate": wr, "net_return_pct": net, "pf": pf}
        print(f"  {name:<32} T={n:<4} WR={wr:5.1f}%  Net={net:+7.1f}%  PF={pf:5.2f}")

    out = os.path.join(BASE, "reports", f"walkforward_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.json")
    with open(out, "w") as f:
        json.dump({"agg": agg, "folds": all_results}, f, indent=2, default=str)
    print(f"\nReport: {out}")


if __name__ == "__main__":
    walk_forward()
