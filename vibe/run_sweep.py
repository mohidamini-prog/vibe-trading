"""
Haupt-Runner: fährt alle Indikator-Kombis über das gesamte Universum
und schreibt Ergebnis-Report nach vibe/reports/.
"""
import os
import sys
import json
import time
from datetime import datetime

# Pfade
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from engine import backtest as bt
from engine import data as data_loader
from universe.universes import US_TOP100, DAX_40, ALL


def run_sweep(years=5, markets="ALL", refresh=False):
    """Backtest-Sweep: jede Kombination x jedes Asset."""
    tickers = ALL if markets == "ALL" else (
        US_TOP100 if markets == "US" else DAX_40 if markets == "DAX" else ALL)

    print(f"=== VIBE-TRADING SWEEP: {len(tickers)} Assets, {years} Jahre, Märkte={markets} ===")
    print(f"Lade Daten (Cache{' (REFRESH)' if refresh else ''})...")
    t0 = time.time()
    data = data_loader.load_universe(tickers, years=years, refresh=refresh)
    print(f"  {len(data)} Assets geladen in {time.time()-t0:.1f}s")

    results = []
    for name, fn in bt.SETUPS.items():
        print(f"\n--- Setup: {name} ---")
        setup_results = []
        for ticker, df in data.items():
            try:
                s = bt.backtest(df, fn)
                setup_results.append({"ticker": ticker, **s})
            except Exception as e:
                setup_results.append({"ticker": ticker, "error": str(e)})
        results.append({"setup": name, "assets": setup_results})

    # Aggregieren
    print("\n\n" + "=" * 90)
    print("ERGEBNIS-MATRIX (kumuliert über alle Assets, KOSTEN + KAPITALBEGRENZUNG)")
    print("=" * 90)
    rows = []
    for r in results:
        ok = [a for a in r["assets"] if "error" not in a]
        n_trades = sum(a["n"] for a in ok)
        wins = [a for a in ok if a["n"] > 0]
        wr = (sum(a["win_rate"] * a["n"] for a in wins) / n_trades) if n_trades else 0
        avg = (sum(a["avg_pnl"] * a["n"] for a in wins) / n_trades) if n_trades else 0
        tot = sum(a["total_pnl"] for a in ok)
        pf_vals = [a["profit_factor"] for a in ok if a["n"] > 0 and a["profit_factor"] != float("inf")]
        pf = sum(pf_vals) / len(pf_vals) if pf_vals else 0
        dd = min((a["max_drawdown"] for a in ok if a["n"] > 0), default=0)
        # Kapitalbasiert: pro Asset 10% des Eigenkapitals, kumuliert
        net_ret = sum(a.get("net_return_pct", 0) for a in ok)
        rows.append({
            "setup": r["setup"], "n_trades": n_trades, "win_rate": wr,
            "avg_pnl": avg, "total_pnl": tot, "profit_factor": pf,
            "max_drawdown": dd, "assets_ok": len(ok), "net_return_pct": net_ret,
        })
        print(f"  {r['setup']:<26} Trades={n_trades:<5} WR={wr:5.1f}%  Avg={avg:6.2f}%  "
              f"PF={pf:5.2f}  DD={dd:6.2f}%  Kapital={net_ret:+8.1f}%")

    # Beste Kombis sortieren
    rows.sort(key=lambda x: -x["net_return_pct"])
    print("\nBESTE KOMBINATIONEN (nach Kapitalrendite):")
    for i, r in enumerate(rows[:5], 1):
        print(f"  {i}. {r['setup']:<26} Kapital={r['net_return_pct']:+8.1f}%  WR={r['win_rate']:.1f}%  Trades={r['n_trades']}")

    # Report speichern
    out = os.path.join(BASE, "reports", f"sweep_{datetime.now().strftime('%Y%m%d_%H%M')}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump({"meta": {"years": years, "markets": markets, "n_assets": len(data)},
                   "results": rows, "detail": results}, f, indent=2, default=str)
    print(f"\nReport gespeichert: {out}")
    return rows


if __name__ == "__main__":
    yrs = 5
    mkt = "ALL"
    for a in sys.argv[1:]:
        if a.startswith("years="):
            yrs = int(a.split("=")[1])
        elif a in ("US", "DAX", "ALL"):
            mkt = a
        elif a == "refresh":
            pass
    run_sweep(years=yrs, markets=mkt)
