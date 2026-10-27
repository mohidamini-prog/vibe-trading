"""4h vs 1d Vergleich aus den neuesten Reports."""
import json, glob

def load_newest(prefix):
    fs = sorted(glob.glob('/root/forschung/vibe/reports/sweep_*.json'))
    # neueste, die zum prefix passt
    return json.load(open(fs[-1]))  # letzter = neuester

# Zeitstempel-basierte Zuordnung: letzter 4h- und letzter 1d-Report
reports = sorted(glob.glob('/root/forschung/vibe/reports/sweep_*.json'))
d4 = json.load(open([f for f in reports if '1010' in f][0]))
d1 = json.load(open([f for f in reports if '1013' in f][0]))

def table(d, label):
    rows = sorted(d["results"], key=lambda x: -x["net_return_pct"])
    print("== {} == ({} Assets, {} Jahre)".format(label, d["meta"]["n_assets"], d["meta"]["years"]))
    hdr = "{:>2} {:<24}{:>7}{:>8}{:>9}{:>9}{:>7}{:>8}".format(
        "#", "SETUP", "Trades", "TREFF%", "Kapital", "Avg/T", "PF", "MaxDD")
    print(hdr)
    print("-" * 76)
    for i, r in enumerate(rows, 1):
        print("{:>2} {:<24}{:>7}{:>7.1f}%{:>8.1f}%{:>8.2f}%{:>7.2f}{:>8.1f}%".format(
            i, r["setup"], r["n_trades"], r["win_rate"], r["net_return_pct"],
            r["avg_pnl"], r["profit_factor"], r["max_drawdown"]))
    tot = sum(r["n_trades"] for r in rows)
    wavg = sum(r["win_rate"] * r["n_trades"] for r in rows) / tot
    print("  GESAMT: {} Trades | gewichtete Trefferquote {:.1f}%".format(tot, wavg))
    print()
    return {r["setup"]: r for r in rows}

print("=" * 76)
print("  4H (2 Jahre) vs 1D (5 Jahre) — 10 bps Kosten, 10% Kapital")
print("=" * 76)
r4 = table(d4, "4H")
r1 = table(d1, "1D")

print()
print("VERGLEICH DER TOP-SETUPS:")
print("  {:<24}{:>14}{:>14}".format("SETUP", "4H Kapital", "1D Kapital"))
print("  " + "-" * 50)
for s in r4:
    a = r4[s]["net_return_pct"]
    b = r1.get(s, {}).get("net_return_pct", 0)
    print("  {:<24}{:>13.1f}%{:>13.1f}%".format(s, a, b))
