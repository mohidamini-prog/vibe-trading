"""
Per-Markt-Sweep: US vs DAX getrennt, mit Momentum+Noise-Setups.
Zeigt, welche Setups in welchem Markt am besten funktionieren.
"""
import os, sys, json, time
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from engine import backtest as bt
from engine import data as data_loader
from universe.universes import US_TOP100, DAX_40


def sweep_market(tickers, label, years=5, timeframe="1d"):
    print(f"\n{'='*70}")
    print(f"  {label} ({len(tickers)} Assets, {years}J, {timeframe})")
    print(f"{'='*70}")
    data = data_loader.load_universe(tickers, years=years, timeframe=timeframe)
    print(f"  {len(data)} Assets geladen\n")

    results = []
    for name, fn in bt.SETUPS.items():
        agg = {"n": 0, "wr": 0.0, "avg": 0.0, "tot": 0.0, "pf": [], "dd": [], "net": 0.0, "ok": 0}
        for ticker, df in data.items():
            try:
                s = bt.backtest(df, fn)
                if s["n"] > 0:
                    agg["n"] += s["n"]
                    agg["wr"] += s["win_rate"] * s["n"]
                    agg["avg"] += s["avg_pnl"] * s["n"]
                    agg["tot"] += s["total_pnl"]
                    if s["profit_factor"] != float("inf"):
                        agg["pf"].append(s["profit_factor"])
                    agg["dd"].append(s["max_drawdown"])
                    agg["net"] += s["net_return_pct"]
                    agg["ok"] += 1
            except Exception:
                pass
        wr = agg["wr"] / agg["n"] if agg["n"] else 0
        avg = agg["avg"] / agg["n"] if agg["n"] else 0
        pf = sum(agg["pf"]) / len(agg["pf"]) if agg["pf"] else 0
        dd = min(agg["dd"]) if agg["dd"] else 0
        results.append({"setup": name, "n": agg["n"], "win_rate": wr, "avg_pnl": avg,
                        "total_pnl": agg["tot"], "profit_factor": pf,
                        "max_drawdown": dd, "net_return_pct": agg["net"], "assets": agg["ok"]})
        print(f"  {name:<32} T={agg['n']:<5} WR={wr:5.1f}%  Net={agg['net']:+8.1f}%  PF={pf:5.2f}  DD={dd:6.1f}%")

    results.sort(key=lambda x: -x["net_return_pct"])
    return results


if __name__ == "__main__":
    print("VIBE PER-MARKT-SWEEP: 14 Setups (inkl. Momentum+Noise), 10bps, 10% Kapital")
    us = sweep_market(US_TOP100, "US TOP-100")
    dax = sweep_market(DAX_40, "DAX-40")

    # Save
    out = os.path.join(BASE, "reports", f"permarket_{datetime.now().strftime('%Y%m%d_%H%M')}.json")
    with open(out, "w") as f:
        json.dump({"us": us, "dax": dax}, f, indent=2, default=str)
    print(f"\nReport: {out}")

    # Top 5 je Markt
    print("\n" + "="*70)
    print("  TOP 5 US")
    print("="*70)
    for i, r in enumerate(us[:5], 1):
        print(f"  {i}. {r['setup']:<32} WR={r['win_rate']:5.1f}%  Net={r['net_return_pct']:+8.1f}%  PF={r['profit_factor']:5.2f}")
    print("\n" + "="*70)
    print("  TOP 5 DAX")
    print("="*70)
    for i, r in enumerate(dax[:5], 1):
        print(f"  {i}. {r['setup']:<32} WR={r['win_rate']:5.1f}%  Net={r['net_return_pct']:+8.1f}%  PF={r['profit_factor']:5.2f}")
