"""
Indikator-Verfeinerung: RSI-50/200-Konzept + Momentum-Beschleunigung + Orderflow.
Testet neue Setups (lokal definiert, KEINE Aenderung an backtest.py).
"""
import os, sys, json
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import numpy as np
import pandas as pd
from engine import backtest as bt
from engine import data as data_loader
from universe.universes import US_TOP100, DAX_40


# --- Neue Setups (lokal, nutzen berechnete Indikatoren aus bt.prepare) ---

def setup_rsi_ema_trend(df):
    """RSI>50 (Bullen) + Preis ueber EMA200 + EMA50>EMA200 + Volumen + Noise-Filter."""
    bull = (df["rsi"] > 50) & (df["rsi"] < 70)
    above200 = df["Close"] > df["ema200"]
    trend = df["ema50"] > df["ema200"]
    vol_ok = df["vol_ratio"] > 1.0
    low_noise = df["noise"] < 55
    return bull & above200 & trend & vol_ok & low_noise


def setup_momentum_accel(df):
    """Momentum-Beschleunigung: ROC10 steigt + MACD-Hist positiv + Trend."""
    accel = df["roc10"] > df["roc10"].shift(1)
    macd_ok = df["macd_hist"] > 0
    trend = df["ema50"] > df["ema200"]
    rsi_ok = df["rsi"] > 50
    low_noise = df["noise"] < 55
    return accel & macd_ok & trend & rsi_ok & low_noise


def setup_orderflow(df):
    """Orderflow: OBV-Steigung + Volumen-Z-Score (Kaufdruck) + Preis-Momentum."""
    obv_up = df["obv_slope"] > 0
    vol_press = (df["vol_zscore"] > 0.3) | (df["vol_ratio"] > 1.0)
    price_up = df["roc10"] > 0
    trend = df["ema20"] > df["ema50"]
    rsi_ok = df["rsi"] > 50
    low_noise = df["noise"] < 55
    return obv_up & vol_press & price_up & trend & rsi_ok & low_noise


def setup_orderflow_strict(df):
    """Orderflow strikt: OBV-Steigung + Volumen-Z-Score>0.5 + Williams-R + Noise<50."""
    obv_up = df["obv_slope"] > 0
    vol_press = df["vol_zscore"] > 0.5
    wr_ok = (df["williams_r"] > -50) & (df["williams_r"] < -20)
    trend = df["ema50"] > df["ema200"]
    low_noise = df["noise"] < 50
    return obv_up & vol_press & wr_ok & trend & low_noise


def setup_rsi_200_momentum(df):
    """RSI-200 + Momentum-Kombi: RSI>55, Preis>EMA200, ROC20>0, MACD>0, Volumen."""
    rsi_ok = (df["rsi"] > 55) & (df["rsi"] < 75)
    above200 = df["Close"] > df["ema200"]
    mom_ok = df["roc20"] > 0
    macd_ok = df["macd_hist"] > 0
    vol_ok = df["vol_ratio"] > 1.0
    low_noise = df["noise"] < 50
    return rsi_ok & above200 & mom_ok & macd_ok & vol_ok & low_noise


NEW_SETUPS = {
    "rsi_ema_trend": setup_rsi_ema_trend,
    "momentum_accel": setup_momentum_accel,
    "orderflow": setup_orderflow,
    "orderflow_strict": setup_orderflow_strict,
    "rsi_200_momentum": setup_rsi_200_momentum,
}


def main():
    print("=== INDICATOR REFINEMENT: RSI-50/200 + Momentum + Orderflow (5J, 1d) ===")
    print("Lade Daten...")
    data = data_loader.load_universe(US_TOP100 + DAX_40, years=5, timeframe="1d")
    print(f"  {len(data)} Assets\n")

    results = []
    for name, fn in NEW_SETUPS.items():
        agg = {"n": 0, "wr": 0.0, "net": 0.0, "pf": [], "dd": [], "ok": 0}
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
                    agg["ok"] += 1
            except Exception:
                pass
        wr = agg["wr"] / agg["n"] if agg["n"] else 0
        pf = sum(agg["pf"]) / len(agg["pf"]) if agg["pf"] else 0
        dd = min(agg["dd"]) if agg["dd"] else 0
        results.append({"setup": name, "n": agg["n"], "win_rate": wr,
                        "net_return_pct": agg["net"], "profit_factor": pf,
                        "max_drawdown": dd, "assets": agg["ok"]})
        print(f"  {name:<22} T={agg['n']:<5} WR={wr:5.1f}%  Net={agg['net']:+8.1f}%  PF={pf:5.2f}  DD={dd:6.1f}%")

    results.sort(key=lambda x: -x["net_return_pct"])
    print("\n=== TOP 5 (nach Kapitalrendite) ===")
    for i, r in enumerate(results[:5], 1):
        print(f"  {i}. {r['setup']:<22} T={r['n']:<5} WR={r['win_rate']:5.1f}%  Net={r['net_return_pct']:+8.1f}%  PF={r['profit_factor']:5.2f}")

    out = os.path.join(BASE, "reports", f"refine_indicators_{datetime.now().strftime('%Y%m%d_%H%M')}.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nReport: {out}")


if __name__ == "__main__":
    main()
