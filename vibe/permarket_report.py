"""Per-Markt-Report lesen: US vs DAX gegenüberstellen."""
import json, glob

f = sorted(glob.glob('/root/forschung/vibe/reports/permarket_*.json'))[-1]
d = json.load(open(f))

def show(rows, label, key="net_return_pct"):
    print("== {} (nach Kapitalrendite) ==".format(label))
    hdr = "{:>2} {:<32}{:>7}{:>7}{:>9}{:>6}{:>8}".format(
        "#", "SETUP", "Trades", "TREFF%", "Kapital", "PF", "MaxDD")
    print(hdr)
    print("-" * 70)
    for i, r in enumerate(rows, 1):
        print("{:>2} {:<32}{:>7}{:>6.1f}%{:>8.1f}%{:>6.2f}{:>8.1f}%".format(
            i, r["setup"], r["n"], r["win_rate"], r["net_return_pct"],
            r["profit_factor"], r["max_drawdown"]))
    print()

print("=" * 70)
print("  PER-MARKT: US TOP-100 vs DAX-40 (5J, 10bps, 10% Kapital)")
print("=" * 70)
show(d["us"], "US TOP-100")
show(d["dax"], "DAX-40")

print("\n=== SETUPS, DIE IN BEIDEN MÄRKTEN FUNKTIONIEREN ===")
us_map = {r["setup"]: r for r in d["us"]}
dax_map = {r["setup"]: r for r in d["dax"]}
print("{:<32}{:>12}{:>12}".format("SETUP", "US Net", "DAX Net"))
print("-" * 56)
for s in us_map:
    u = us_map[s]["net_return_pct"]
    x = dax_map.get(s, {}).get("net_return_pct", 0)
    mark = " ✓" if u > 0 and x > 0 else ""
    print("{:<32}{:>11.1f}%{:>11.1f}%{}".format(s, u, x, mark))
