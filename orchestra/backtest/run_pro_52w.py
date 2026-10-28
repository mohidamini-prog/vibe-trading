import sys
from pathlib import Path
REPO_ROOT = Path("/root/forschung")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd
import numpy as np
from orchestra.backtest.engine import US_SYMBOLS, DE_SYMBOLS, fetch_data, add_indicators, backtest

def add_advanced_indicators(df):
    df = add_indicators(df)
    c = df["Close"]
    
    # RSI 2 und RSI 50 (zusätzlich zu RSI 14)
    delta = c.diff()
    gain2 = delta.clip(lower=0).rolling(2).mean()
    loss2 = (-delta.clip(upper=0)).rolling(2).mean()
    df["RSI2"] = 100 - (100 / (1 + (gain2 / loss2)))
    
    gain50 = delta.clip(lower=0).rolling(50).mean()
    loss50 = (-delta.clip(upper=0)).rolling(50).mean()
    df["RSI50"] = 100 - (100 / (1 + (gain50 / loss50)))
    
    # MACD (12, 26, 9)
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]
    
    # 52-Wochen (ca. 252 Trading Days bei 1D, bzw 52 * 6 bei 4h) High / Low
    window_52w = 252 if len(df) > 300 else len(df) // 2
    df["High_52W"] = df["High"].rolling(window_52w).max()
    df["Low_52W"] = df["Low"].rolling(window_52w).min()
    
    return df

def pro_strategy_signals(df, model):
    c = df["Close"]
    v = df["Volume"]
    
    if model == "rsi_macd_vol_breakout":
        # RSI2 extrem oversold (< 10) in Aufwärtstrend (RSI50 > 50) + MACD Histogramm dreht ins Positive + Volumen Spike
        uptrend = df["RSI50"] > 50
        rsi_dip = df["RSI2"] < 15
        macd_cross = (df["MACD_Hist"] > 0) & (df["MACD_Hist"].shift(1) <= 0)
        vol_spike = v > v.rolling(20).median() * 1.2
        cond = uptrend & rsi_dip & macd_cross & vol_spike
        return np.where(cond, 1, 0)
        
    elif model == "new_52w_high_momentum":
        # Ausbruch auf neues 52-Wochen-Hoch + MACD positiv + Volumen über Durchschnitt
        is_new_high = c >= df["High_52W"] * 0.98  # Nahe am 52W High
        macd_ok = df["MACD"] > 0
        vol_ok = v > v.rolling(20).mean()
        cond = is_new_high & macd_ok & vol_ok
        return np.where(cond, 1, 0)

    elif model == "deep_value_bounce_52w":
        # Nahe am 52-Wochen-Tief (Bodenbildung): RSI2 < 10 + RSI50 steigt + Volumen-Anstieg
        near_low = c <= df["Low_52W"] * 1.05
        rsi_bottom = df["RSI2"] < 10
        vol_spike = v > v.rolling(20).median() * 1.5
        cond = near_low & rsi_bottom & vol_spike
        return np.where(cond, 1, 0)

    else:
        return np.zeros(len(df))

symbols = US_SYMBOLS + DE_SYMBOLS
models = ["rsi_macd_vol_breakout", "new_52w_high_momentum", "deep_value_bounce_52w"]
intervals = ["1d"] # 52W macht auf 1D am meisten Sinn

results = []
for symbol in symbols:
    for interval in intervals:
        df = fetch_data(symbol, interval, "max")
        if df is None or len(df) < 100:
            continue
        df = add_advanced_indicators(df)
        
        for model in models:
            sig = pro_strategy_signals(df, model)
            res = backtest(df, sig)
            if res and res["n_trades"] > 0:
                res["symbol"] = symbol
                res["interval"] = interval
                res["model"] = model
                results.append(res)

df_res = pd.DataFrame(results)
if not df_res.empty:
    summary = df_res.groupby("model").agg({
        "hit_rate": "mean",
        "total_ret": "mean",
        "n_trades": "sum",
        "sharpe": "mean"
    }).sort_values(by="hit_rate", ascending=False)
    
    print("\n--- PRO-STRATEGIEN MIT RSI, MACD, VOLUMEN & 52W EXTREMEN ---")
    print(summary.to_string())
    summary.to_csv("/root/forschung/orchestra/backtests/pro_52w_summary.csv")
else:
    print("Keine Trades.")
