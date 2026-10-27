"""Report auswerten: vibes-Ranking + tote Setups debuggen."""
import json, glob, sys

f = sorted(glob.glob('/root/forschung/vibe/reports/sweep_*.json'))[-1]
d = json.load(open(f))

print("META:", d["meta"])
print()
print(f"{'SETUP':<26}{'Trades':>8}{'WR%':>8}{'Avg%':>8}{'Total%':>10}{'PF':>7}{'DD%':>9}")
print("-" * 76)
for r in d["results"]:
    print(f"{r['setup']:<26}{r['n_trades']:>8}{r['win_rate']:>8.1f}{r['avg_pnl']:>8.2f}"
          f"{r['total_pnl']:>10.1f}{r['profit_factor']:>7.2f}{r['max_drawdown']:>9.1f}")

print()
first = d["detail"][0]["assets"]
ok = [a for a in first if "error" not in a]
print(f"Assets mit Daten: {len(ok)}")
with_trades = [a for a in ok if a["n"] > 0]
print(f"Assets mit Trades (Setup 1): {len(with_trades)}")

# Tote Setups: pro Ticker prüfen, ob überhaupt Signale kommen
print()
print("=== TOETE SETUPS: Ursachen-Check auf AAPL ===")
sys.path.insert(0, "/root/forschung/vibe")
from engine import backtest as bt, data as dl

df = dl.load_ticker("AAPL", 5)
prep = bt.prepare(df)
for name, fn in bt.SETUPS.items():
    sig = fn(prep).fillna(False)
    n_sig = int(sig.sum())
    print(f"  {name:<26} Signale auf AAPL(5y): {n_sig}")
