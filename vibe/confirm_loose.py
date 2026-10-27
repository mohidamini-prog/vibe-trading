"""Bestätigung: meanrev_oversold_loose Performance über alle Assets."""
import sys, json, glob
sys.path.insert(0, '/root/forschung/vibe')
from engine import backtest as bt
from engine import data as data_loader
from universe.universes import US_TOP100, DAX_40
import numpy as np

data = data_loader.load_universe(US_TOP100 + DAX_40, years=5, timeframe="1d")
print(f"{len(data)} Assets")

for name in ["meanrev_oversold", "meanrev_oversold_loose"]:
    fn = bt.SETUPS[name]
    agg = {"n": 0, "wr": 0.0, "net": 0.0, "pf": [], "dd": []}
    for ticker, df in data.items():
        try:
            prep = bt.prepare(df)
            s = bt.backtest(prep, fn, _prepared=True)
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
    print(f"  {name:<28} T={n:<5} WR={wr:5.1f}%  Net={agg['net']:+8.1f}%  PF={pf:5.2f}  DD={dd:6.1f}%")
