import sys
from pathlib import Path
REPO_ROOT = Path("/root/forschung")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd
import numpy as np
from orchestra.backtest.engine import US_SYMBOLS, DE_SYMBOLS, fetch_data, add_indicators, backtest
from run_pro_52w import add_advanced_indicators

def fibonacci_filter_signals(df, model):
    c = df["Close"]
    h = df["High"]
    l = df["Low"]
    v = df["Volume"]
    
    # Fibonacci Retracement Levels bezogen auf das letzte 50-Bar Swing High / Low
    swing_high = h.rolling(50).max()
    swing_low = l.rolling(50).min()
    diff = swing_high - swing_low
    
    # Wichtige Fib-Zonen für Long-Einstiege (Pullbacks): 61.8% und 50% Retracement
    fib_618 = swing_high - (diff * 0.618)
    fib_500 = swing_high - (diff * 0.500)
    
    # Preis ist nahe der Fib-Zone (± 1.5%)
    near_fib = (c >= fib_618 * 0.985) & (c <= fib_500 * 1.015)
    
    # Filter 1: Trend-Filter (EMA50 > EMA200)
    trend_filter = df["EMA50"] > df["EMA200"]
    
    # Filter 2: RSI-Dip (RSI 14 war unter 40 und zieht wieder an)
    rsi_dip = (df["RSI"].shift(1) < 40) & (df["RSI"] >= 40)
    
    # Filter 3: Volumen-Bestätigung
    vol_ok = v > v.rolling(20).median() * 1.1

    if model == "fib_pullback_confluence":
        cond = trend_filter & near_fib & rsi_dip & vol_ok
        return np.where(cond, 1, 0)
    elif model == "fib_breakout_extension":
        # Ausbruch über 100% Swing High mit starkem MACD
        breakout = c > swing_high.shift(1)
        macd_ok = df["MACD_Hist"] > 0
        cond = trend_filter & breakout & macd_ok & (v > v.rolling(20).mean())
        return np.where(cond, 1, 0)
    else:
        return np.zeros(len(df))

symbols = US_SYMBOLS + DE_SYMBOLS
models = ["fib_pullback_confluence", "fib_breakout_extension"]
intervals = ["1d"]

results = []
for symbol in symbols:
    for interval in intervals:
        df = fetch_data(symbol, interval, "max")
        if df is None or len(df) < 100:
            continue
        df = add_advanced_indicators(df)
        
        for model in models:
            sig = fibonacci_filter_signals(df, model)
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
    
    print("\n--- FIBONACCI + FILTER KOMBI ERGEBNISSE ---")
    print(summary.to_string())
    summary.to_csv("/root/forschung/orchestra/backtests/fib_summary.csv")
else:
    print("Keine Trades.")
