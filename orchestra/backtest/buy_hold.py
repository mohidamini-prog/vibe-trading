"""
Buy & Hold Benchmark — Vergleich mit den Strategien.

Berechnet Buy & Hold Rendite, CAGR, Max Drawdown, Sharpe für alle Symbole
(US + DE) auf 1D (5y) und 4h (2y). Als Referenz zum Vergleich mit den
Agenten-Strategien aus engine.py.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd
import yfinance as yf

from orchestra.backtest.engine import US_SYMBOLS, DE_SYMBOLS, OUT_DIR, fetch_data

BARS_PER_YEAR = {"1d": 252, "4h": 1512}


def buy_and_hold_metrics(df, interval):
    """Buy & Hold: einfach halten, Rendite/CAGR/DD/Sharpe."""
    if df is None or len(df) < 50:
        return None
    c = df["Close"]
    ret = c.pct_change().fillna(0)
    cum = (1 + ret).cumprod()
    total_ret = cum.iloc[-1] - 1
    years = len(df) / BARS_PER_YEAR[interval]
    cagr = ((1 + total_ret) ** (1 / years) - 1) if total_ret > -1 and years > 0 else -1.0
    peak = cum.cummax()
    max_dd = (cum / peak - 1).min()
    sharpe = (ret.mean() / ret.std() * np.sqrt(252)) if ret.std() > 0 else 0
    return {
        "total_ret": round(float(total_ret), 4),
        "cagr": round(float(cagr), 4),
        "max_dd": round(float(max_dd), 4),
        "sharpe": round(float(sharpe), 2),
        "n_bars": len(df),
        "years": round(years, 1),
    }


def run_buy_hold():
    results = []
    for interval, period in [("1d", "5y"), ("4h", "2y")]:
        for symbol in US_SYMBOLS + DE_SYMBOLS:
            df = fetch_data(symbol, interval, period)
            m = buy_and_hold_metrics(df, interval)
            if m:
                m.update({"symbol": symbol, "interval": interval, "model": "buy_hold", "period": period})
                results.append(m)
    out = OUT_DIR / "buy_hold_benchmark.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"Buy&Hold: {len(results)} Ergebnisse -> {out}")
    return results


if __name__ == "__main__":
    res = run_buy_hold()
    # Zusammenfassung
    for interval in ["1d", "4h"]:
        subset = [r for r in res if r["interval"] == interval]
        if subset:
            avg_ret = np.mean([r["total_ret"] for r in subset]) * 100
            avg_cagr = np.mean([r["cagr"] for r in subset]) * 100
            avg_dd = np.mean([r["max_dd"] for r in subset]) * 100
            avg_sharpe = np.mean([r["sharpe"] for r in subset])
            print(f"{interval}: Ø Kum {avg_ret:.1f}% | Ø CAGR {avg_cagr:.1f}% | Ø DD {avg_dd:.1f}% | Ø Sharpe {avg_sharpe:.2f}")
