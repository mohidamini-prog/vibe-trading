"""
Strategie-Upgrade + Auswertung des Backtests.

Liest backtest_results.json, bestimmt die besten Strategien pro Agent,
markiert schlechte und schreibt ein Upgrade in die Agenten (config).
"""
import json
import sys
from pathlib import Path
from collections import defaultdict

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

RESULTS = Path(__file__).resolve().parent.parent / "backtests" / "backtest_results.json"
OUT = Path(__file__).resolve().parent.parent / "backtests" / "strategy_upgrade.json"

# Mapping: Modell -> welcher Agent es nutzt
MODEL_TO_AGENT = {
    "trend_ema": "momentum",
    "momentum_rsi": "momentum",
    "meanrev_bb": "meanrev",
    "zscore": "meanrev",
    "vola_atr": "vola",
    "adx_trend": "momentum",
}


def load_results():
    return json.loads(RESULTS.read_text())


def aggregate():
    results = load_results()
    agg = defaultdict(list)
    for r in results:
        agg[(r["model"], r["interval"])].append(r)
    # Durchschnitt pro Modell+Intervall
    summary = {}
    for (model, interval), items in agg.items():
        n = len(items)
        hit = sum(x["hit_rate"] for x in items) / n
        ret = sum(x["total_ret"] for x in items) / n
        sharpe = sum(x["sharpe"] for x in items) / n
        trades = sum(x["n_trades"] for x in items)
        summary[(model, interval)] = {
            "hit_rate": round(hit, 4), "total_ret": round(ret, 4),
            "sharpe": round(sharpe, 2), "n_trades": trades, "n": n,
        }
    return summary


def rank(summary):
    """Sortiere nach Score (Hit + Sharpe + Return gewichtet)."""
    ranked = []
    for (model, interval), v in summary.items():
        # Score: Hit 60% + Sharpe 30% + Return 10% (normalisiert)
        score = v["hit_rate"] * 0.6 + max(0, v["sharpe"]) * 0.3 + max(0, v["total_ret"]) * 0.1
        ranked.append({"model": model, "interval": interval, **v, "score": round(score, 4)})
    ranked.sort(key=lambda x: -x["score"])
    return ranked


def build_upgrade():
    summary = aggregate()
    ranked = rank(summary)
    # Beste pro Agent übernehmen (Hit >= 0.50), schlechte markieren
    upgrade = {"by_agent": {}, "ranking": ranked, "take": [], "drop": []}
    # Beste Kombination pro Agent
    for agent, models in {
        "momentum": ["trend_ema", "momentum_rsi", "adx_trend"],
        "meanrev": ["meanrev_bb", "zscore"],
        "vola": ["vola_atr"],
    }.items():
        candidates = [r for r in ranked if r["model"] in models]
        if candidates:
            best = candidates[0]
            upgrade["by_agent"][agent] = best
            if best["hit_rate"] >= 0.50:
                upgrade["take"].append({"agent": agent, **best})
            else:
                upgrade["drop"].append({"agent": agent, **best, "reason": "hit_rate < 0.50"})
    # Alle Kombinationen mit Hit < 50 als drop markieren
    for r in ranked:
        if r["hit_rate"] < 0.50:
            upgrade["drop"].append({**r, "reason": "hit_rate < 0.50"})
    # Duplikate entfernen
    seen = set()
    uniq_drop = []
    for d in upgrade["drop"]:
        k = (d["model"], d["interval"])
        if k not in seen:
            seen.add(k)
            uniq_drop.append(d)
    upgrade["drop"] = uniq_drop
    OUT.write_text(json.dumps(upgrade, indent=2, ensure_ascii=False))
    print(f"Upgrade geschrieben: {OUT}")
    return upgrade


if __name__ == "__main__":
    u = build_upgrade()
    print("\n=== ÜBERNEHMEN (pro Agent) ===")
    for t in u["take"]:
        print(f"  ✅ {t['agent']}: {t['model']} ({t['interval']}) — Hit {t['hit_rate']*100:.1f}%, Ret {t['total_ret']*100:.1f}%")
    print("\n=== ABSETZEN ===")
    for d in u["drop"]:
        print(f"  ⚠️ {d['model']} ({d['interval']}) — Hit {d['hit_rate']*100:.1f}%, Ret {d['total_ret']*100:.1f}%")
