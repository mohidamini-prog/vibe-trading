"""Refine-Report lesen: beste RSI/Vol/EMA-Kombis."""
import json, glob

f = sorted(glob.glob('/root/forschung/vibe/reports/refine_*.json'))[-1]
d = json.load(open(f))
print("META:", d["meta"])
print()
rows = d["results"]
# Nach Profit-Faktor (Qualität) sortieren
by_pf = sorted(rows, key=lambda x: -x["profit_factor"])
print("=== TOP 10 nach Profit-Faktor (Qualität) ===")
hdr = "{:>3} {:<46}{:>7}{:>7}{:>9}{:>7}{:>8}".format(
    "#", "SIGNAL", "Trades", "TREFF%", "Kapital", "PF", "MaxDD")
print(hdr)
print("-" * 88)
for i, r in enumerate(by_pf[:10], 1):
    print("{:>3} {:<46}{:>7}{:>6.1f}%{:>8.1f}%{:>7.2f}{:>8.1f}%".format(
        i, r["sig_name"], r["n"], r["win_rate"], r["net_return_pct"],
        r["profit_factor"], r["max_drawdown"]))

print()
print("=== TOP 10 nach Kapitalrendite ===")
by_ret = sorted(rows, key=lambda x: -x["net_return_pct"])
for i, r in enumerate(by_ret[:10], 1):
    print("{:>3} {:<46}{:>7}{:>6.1f}%{:>8.1f}%{:>7.2f}{:>8.1f}%".format(
        i, r["sig_name"], r["n"], r["win_rate"], r["net_return_pct"],
        r["profit_factor"], r["max_drawdown"]))
