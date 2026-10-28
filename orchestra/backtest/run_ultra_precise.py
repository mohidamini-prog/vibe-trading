import sys
from pathlib import Path
REPO_ROOT = Path("/root/forschung")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd
import numpy as np
from orchestra.backtest.engine import US_SYMBOLS, DE_SYMBOLS, fetch_data, add_indicators, backtest

def ultra_precise_signals(df, model):
    c = df["Close"]
    h = df["High"]
    l = df["Low"]
    v = df["Volume"]
    
    # Basis-Indikatoren vorausgesetzt
    if model == "pullback_ema20_rsi":
        # Ultra-präziser Pullback: Aufwärtstrend (EMA20>EMA50>EMA200), 
        # Kurs berührt EMA20 (Low <= EMA20) und RSI war gerade oversold/dip (< 45) und zieht an (> 40)
        uptrend = (df["EMA20"] > df["EMA50"]) & (df["EMA50"] > df["EMA200"])
        touched_ema = l <= df["EMA20"]
        rsi_dip_recovery = (df["RSI"].shift(1) < 45) & (df["RSI"] >= 40)
        cond = uptrend & touched_ema & rsi_dip_recovery
        return np.where(cond, 1, 0)
        
    elif model == "sr_flip_breakout":
        # Support/Resistance Flip: Vorheriger Widerstand (20-bar high) wird durchbrochen + Volumenbestätigung
        prev_high = h.rolling(20).max().shift(1)
        breakout = (c > prev_high) & (c.shift(1) <= prev_high.shift(1))
        vol_confirm = v > v.rolling(20).median() * 1.3
        cond = breakout & vol_confirm & (df["EMA50"] > df["EMA200"])
        return np.where(cond, 1, 0)
        
    elif model == "multi_tf_confluence":
        # Konfluenz: RSI zwischen 40 und 60 in starkem Trend + Z-Score negativ (leicht unter Schnitt, springt nach oben)
        uptrend = df["EMA20"] > df["EMA50"]
        z_dip = (df["Z"] < -0.5) & (df["Z"] > -2.0)
        rsi_ok = (df["RSI"] > 40) & (df["RSI"] < 60)
        cond = uptrend & z_dip & rsi_ok
        return np.where(cond, 1, 0)

    elif model == "bb_squeeze_expansion":
        # Bollinger Squeeze & Expansion (Volatilitäts-Breakout)
        bb_width = (df["BB_Up"] - df["BB_Low"]) / df["BB_Mid"]
        squeeze = bb_width < bb_width.rolling(50).quantile(0.2)
        expansion = (c > df["BB_Up"]) & squeeze.shift(1)
        cond = expansion & (df["EMA20"] > df["EMA50"])
        return np.where(cond, 1, 0)

    else:
        return np.zeros(len(df))

symbols = US_SYMBOLS + DE_SYMBOLS
models = ["pullback_ema20_rsi", "sr_flip_breakout", "multi_tf_confluence", "bb_squeeze_expansion"]
intervals = ["4h", "1d"]

results = []
for symbol in symbols:
    for interval in intervals:
        period = "730d" if interval == "4h" else "max"
        df = fetch_data(symbol, interval, period)
        if df is None or len(df) < 60:
            continue
        df = add_indicators(df)
        
        for model in models:
            sig = ultra_precise_signals(df, model)
            res = backtest(df, sig)
            if res and res["n_trades"] > 0:
                res["symbol"] = symbol
                res["interval"] = interval
                res["model"] = model
                results.append(res)

df_res = pd.DataFrame(results)
if not df_res.empty:
    summary = df_res.groupby(["model", "interval"]).agg({
        "hit_rate": "mean",
        "total_ret": "mean",
        "n_trades": "sum",
        "sharpe": "mean"
    }).sort_values(by="hit_rate", ascending=False)
    
    print("\n--- ULTRA-PRÄZISE ENTRY MODELLE ---")
    print(summary.to_string())
    summary.to_csv("/root/forschung/orchestra/backtests/ultra_precise_summary.csv")
else:
    print("Keine Trades.")
