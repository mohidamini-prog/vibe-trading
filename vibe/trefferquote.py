"""Realistische Trefferquoten aus dem Kosten/Kapital-Sweep."""
import json, glob

f = sorted(glob.glob('/root/forschung/vibe/reports/sweep_*.json'))[-1]
d = json.load(open(f))

print("META:", d["meta"])
print()
rows = sorted(d["results"], key=lambda x: -x["net_return_pct"])
print("=== REALISTISCH: 10 bps Kosten + 10% Kapital pro Position ===")
print()
hdr = "{:>2} {:<24}{:>7}{:>9}{:>9}{:>10}{:>8}{:>8}".format(
    "#", "SETUP", "Trades", "TREFFERQ.", "Kapital", "Avg/T", "PF", "MaxDD")
print(hdr)
print("-" * 78)
for i, r in enumerate(rows, 1):
    print("{:>2} {:<24}{:>7}{:>8.1f}%{:>9.1f}%{:>9.2f}%{:>8.2f}{:>8.1f}%".format(
        i, r["setup"], r["n_trades"], r["win_rate"], r["net_return_pct"],
        r["avg_pnl"], r["profit_factor"], r["max_drawdown"]))
print()
tot = sum(r["n_trades"] for r in rows)
wavg = sum(r["win_rate"] * r["n_trades"] for r in rows) / tot
print("GESAMT: {} Trades | gewichtete Trefferquote: {:.1f}%".format(tot, wavg))
