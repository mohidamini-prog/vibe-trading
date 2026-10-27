"""Buy-and-Hold-Benchmark vs. Strategie (Alpha-Check)."""
import os, sys, json
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from engine import data as data_loader
from universe.universes import US_TOP100, DAX_40
import numpy as np


def buy_hold_return(df):
    """Rendite über den gesamten Zeitraum (Close[-1]/Close[0]-1)."""
    if df.empty or len(df) < 2:
        return None
    return float(df["Close"].iloc[-1] / df["Close"].iloc[0] - 1) * 100


def main():
    print("=== BUY-AND-HOLD vs STRATEGIE (5J, 1d) ===")
    all_data = {}
    for label, tickers in (("US", US_TOP100), ("DAX", DAX_40)):
        print(f"\n--- {label} ---")
        returns = []
        for t in tickers:
            try:
                df = data_loader.load_ticker(t, years=5, timeframe="1d")
                r = buy_hold_return(df)
                if r is not None:
                    returns.append((t, r))
                    all_data[t] = r
            except Exception:
                pass
        arr = [r for _, r in returns]
        if arr:
            avg = np.mean(arr)
            median = np.median(arr)
            best = max(returns, key=lambda x: x[1])
            worst = min(returns, key=lambda x: x[1])
            print(f"  {label}: n={len(arr)}, avg={avg:+.1f}%, median={median:+.1f}%")
            print(f"    Best: {best[0]} {best[1]:+.1f}% | Worst: {worst[0]} {worst[1]:+.1f}%")

    # Gesamt
    all_returns = list(all_data.values())
    print(f"\n=== GESAMT ({len(all_returns)} Assets) ===")
    print(f"  Buy-and-Hold avg: {np.mean(all_returns):+.1f}% | median: {np.median(all_returns):+.1f}%")

    # Vergleich mit Strategie (aus permarket Report)
    print("\n=== STRATEGIE vs BUY-AND-HOLD (Alpha) ===")
    import glob
    pm = sorted(glob.glob(os.path.join(BASE, "reports", "permarket_*.json")))[-1]
    d = json.load(open(pm))
    for market, label in (("us", "US"), ("dax", "DAX")):
        bh_avg = np.mean([all_data[t] for t in (US_TOP100 if market == "us" else DAX_40) if t in all_data])
        print(f"\n  {label}: Buy-and-Hold avg = {bh_avg:+.1f}%")
        for r in d[market][:3]:
            alpha = r["net_return_pct"] - bh_avg
            print(f"    {r['setup']:<28} Strategie={r['net_return_pct']:+7.1f}%  Alpha={alpha:+7.1f}%")

    # Save
    out = os.path.join(BASE, "reports", f"buyhold_{datetime.now().strftime('%Y%m%d_%H%M')}.json")
    with open(out, "w") as f:
        json.dump({"assets": all_data, "avg": np.mean(all_returns), "median": np.median(all_returns)}, f, indent=2)
    print(f"\nReport: {out}")


if __name__ == "__main__":
    main()
