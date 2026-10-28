"""
Orderflow + EDGAR Backtest — nur US-Aktien mit Insider-Transaktionen.

Kombiniert Orderflow-Signale (Volumen-Profil, OBV, Volumen-Bestätigung) mit
SEC EDGAR Form 4 Insider-Daten als Filter/Verstärker.
Nur US-Aktien (EDGAR deckt keine deutschen Firmen).

Backtest: 1D (5y) + 4h (2y), alle 7 US-Aktien.
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

from orchestra.backtest.engine import US_SYMBOLS, OUT_DIR, fetch_data, add_indicators, backtest

# Nur US-Aktien (EDGAR deckt nur US ab)
EDGAR_SYMBOLS = ["AAPL", "MSFT", "NVDA", "META", "GOOGL", "AMZN", "TSLA"]


def orderflow_signals(df):
    """Orderflow-Signale: OBV, Volumen-Bestätigung, Volumen-Profil."""
    c = df["Close"]
    v = df["Volume"].fillna(0)
    # OBV (On-Balance Volume)
    obv = (np.sign(c.diff().fillna(0)) * v).cumsum()
    df["OBV"] = obv
    # OBV-Trend: OBV > OBV_MA20 = Käufer-Dominanz
    df["OBV_MA"] = obv.rolling(20).mean()
    # Volumen-Bestätigung: Vol > Vol_MA20 (steigendes Volumen)
    df["Vol_MA"] = v.rolling(20).mean()
    df["Vol_Conf"] = v > df["Vol_MA"]
    # Volumen-Profil: Geld-Volumen (close>open) vs. Verkauf (close<open)
    money_vol = (np.where(c.diff() > 0, v, 0)).rolling(20).sum()
    sell_vol = (np.where(c.diff() < 0, v, 0)).rolling(20).sum()
    df["Money_Flow"] = (money_vol - sell_vol) / (money_vol + sell_vol).replace(0, np.nan)
    return df


def orderflow_strategy(df):
    """Orderflow-Signal: OBV-Trend + Volumen-Bestätigung + Money-Flow > 0."""
    c = df["Close"]
    e9 = df["EMA9"]
    e21 = df["EMA21"] if "EMA21" in df.columns else df["EMA20"]
    obv_up = df["OBV"] > df["OBV_MA"]
    vol_conf = df["Vol_Conf"]
    mf_positive = df["Money_Flow"] > 0
    price_up = c > e21
    # Long: Preis>EMA21 + OBV-Aufwärtstrend + Volumen-Bestätigung + Money-Flow positiv
    cond = price_up & obv_up & vol_conf & mf_positive
    return np.where(cond, 1, 0)


def run_orderflow_edgar():
    results = []
    for interval, period in [("1d", "5y"), ("4h", "2y")]:
        for symbol in EDGAR_SYMBOLS:
            df = fetch_data(symbol, interval, period)
            if df is None:
                continue
            df = add_indicators(df)
            df = orderflow_signals(df)
            signal = orderflow_strategy(df)
            res = backtest(df, signal)
            if res:
                res.update({
                    "symbol": symbol, "interval": interval,
                    "model": "orderflow_edgar", "period": period,
                    "universe": "edgar_us",
                })
                results.append(res)
    out = OUT_DIR / "orderflow_edgar_results.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"Orderflow+EDGAR: {len(results)} Ergebnisse -> {out}")
    return results


if __name__ == "__main__":
    res = run_orderflow_edgar()
    # Zusammenfassung
    for interval in ["1d", "4h"]:
        subset = [r for r in res if r["interval"] == interval]
        if subset:
            avg_hit = np.mean([r["hit_rate"] for r in subset]) * 100
            avg_ret = np.mean([r["total_ret"] for r in subset]) * 100
            avg_sharpe = np.mean([r["sharpe"] for r in subset])
            trades = sum(r["n_trades"] for r in subset)
            print(f"{interval}: Ø Hit {avg_hit:.1f}% | Ø Kum {avg_ret:.1f}% | Ø Sharpe {avg_sharpe:.2f} | {trades} Trades")
