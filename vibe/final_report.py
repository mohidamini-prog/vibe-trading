"""Alle finalen Reports zusammenfassen: Walk-Forward, Filter-Opt, Refine-Indicators, Buy-Hold."""
import json, glob

def load(pattern):
    fs = sorted(glob.glob('/root/forschung/vibe/reports/' + pattern))
    if not fs:
        return None
    return json.load(open(fs[-1]))

print("=" * 80)
print("  FINALE AUSWERTUNG — vibe-trading")
print("=" * 80)

# 1. Walk-Forward (Out-of-Sample)
wf = load('walkforward_*.json')
if wf:
    print("\n--- WALK-FORWARD (Out-of-Sample, 5J, 133 Assets) ---")
    print(f"{'SETUP':<30}{'Trades':>7}{'TREFF%':>8}{'Kapital':>9}{'PF':>6}")
    print("-" * 60)
    for name, r in wf['agg'].items():
        print(f"{name:<30}{r['n']:>7}{r['win_rate']:>7.1f}%{r['net_return_pct']:>8.1f}%{r['pf']:>6.2f}")

# 2. Filter-Optimierung
fo = load('filter_optimize_*.json')
if fo:
    print("\n--- FILTER-OPTIMIERUNG (Top-5 nach Balance) ---")
    print(f"{'SETUP':<20}{'Noise':>6}{'Vol':>6}{'ATR':>6}{'Trades':>7}{'TREFF%':>8}{'PF':>6}{'MaxDD':>8}")
    print("-" * 70)
    for r in fo[:5]:
        atr = f"{r['atr']}%" if r['atr'] else "-"
        print(f"{r['setup']:<20}{r['noise']:>6}{r['vol']:>6}{atr:>6}{r['n']:>7}{r['win_rate']:>7.1f}%{r['profit_factor']:>6.2f}{r['max_drawdown']:>7.1f}%")

# 3. Refine-Indicators (Momentum/Orderflow)
ri = load('refine_indicators_*.json')
if ri:
    print("\n--- INDICATOR-REFINEMENT (RSI/50/200 + Momentum + Orderflow) ---")
    print(f"{'SETUP':<22}{'Trades':>7}{'TREFF%':>8}{'Kapital':>9}{'PF':>6}{'MaxDD':>8}")
    print("-" * 62)
    for r in ri[:5]:
        print(f"{r['setup']:<22}{r['n']:>7}{r['win_rate']:>7.1f}%{r['net_return_pct']:>8.1f}%{r['profit_factor']:>6.2f}{r['max_drawdown']:>7.1f}%")

# 4. Buy-and-Hold
bh = load('buyhold_*.json')
if bh:
    print("\n--- BUY-AND-HOLD vs STRATEGIE (Alpha) ---")
    print(f"Buy-and-Hold avg (134 Assets): {bh['avg']:+.1f}% | median: {bh['median']:+.1f}%")
