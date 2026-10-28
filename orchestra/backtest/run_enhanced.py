import sys
from pathlib import Path
REPO_ROOT = Path("/root/forschung")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd
import yfinance as yf

from orchestra.backtest.engine import US_SYMBOLS, DE_SYMBOLS, fetch_data, add_indicators, backtest

# Erweiterte Strategien mit Breakout, Support/Resistance Bounce, Pullback und Sweeps
def enhanced_strategy_signals(df, model):
    c = df["Close"]
    h = df["High"]
    l = df["Low"]
    v = df["Volume"]
    
    if model == "trend_ema":
        cond = (df["EMA20"] > df["EMA50"]) & (df["EMA50"] > df["EMA200"]) & (c > df["EMA20"])
        return np.where(cond, 1, 0)
    elif model == "momentum_rsi":
        cond = (df["EMA50"] > df["EMA200"]) & (df["RSI"] > 45) & (df["RSI"] < 75)
        return np.where(cond, 1, 0)
    elif model == "meanrev_bb":
        cond = (c <= df["BB_Low"]) | (df["RSI"] < 35)
        return np.where(cond, 1, 0)
    elif model == "adx_trend":
        cond = (df["ADX"] > 25) & (df["EMA50"] > df["EMA200"])
        return np.where(cond, 1, 0)
    
    # NEUE STRATEGIEN:
    elif model == "breakout_donchian":
        # 20-Perioden High Breakout im starken Trend (EMA20 > EMA50)
        donchian_high = h.rolling(20).max().shift(1)
        cond = (c > donchian_high) & (df["EMA20"] > df["EMA50"])
        return np.where(cond, 1, 0)
        
    elif model == "support_bounce":
        # Preis prallt von Support ab (nahe EMA50 oder BB_Low mit bullischem RSI-Reversal)
        near_support = (c - df["EMA50"]).abs() / df["EMA50"] < 0.015
        rsi_bounce = (df["RSI"] > 35) & (df["RSI"].shift(1) <= 35)
        cond = near_support & rsi_bounce
        return np.where(cond, 1, 0)
        
    elif model == "pullback_entry":
        # Im intakten Trend (EMA20 > EMA50 > EMA200) zieht der Kurs kurz auf den EMA20 zurück (RSI 40-50)
        uptrend = (df["EMA20"] > df["EMA50"]) & (df["EMA50"] > df["EMA200"])
        pullback = (c <= df["EMA20"]) & (df["RSI"] >= 40) & (df["RSI"] <= 52)
        cond = uptrend & pullback
        return np.where(cond, 1, 0)
        
    elif model == "liquidity_sweep":
        # Stop-Sweep / False Breakdown unter das 20-Perioden Tief mit sofortigem Rücksetzer über das Tief + Volumen-Spike
        donchian_low = l.rolling(20).min().shift(1)
        swept = l < donchian_low
        reclaimed = c > donchian_low
        vol_spike = v > v.rolling(20).median() * 1.5
        cond = swept & reclaimed & vol_spike
        return np.where(cond, 1, 0)
        
    else:
        return np.zeros(len(df))

models = [
    "trend_ema", "momentum_rsi", "meanrev_bb", "adx_trend",
    "breakout_donchian", "support_bounce", "pullback_entry", "liquidity_sweep"
]

symbols = US_SYMBOLS + DE_SYMBOLS
intervals = ["4h", "1d"]

all_results = []

print(f"Starte Backtest über {len(symbols)} Assets, {len(models)} Modelle, 4h & 1D...")

for symbol in symbols:
    for interval in intervals:
        period = "730d" if interval == "4h" else "max"
        df = fetch_data(symbol, interval, period)
        if df is None or len(df) < 60:
            continue
        df = add_indicators(df)
        
        for model in models:
            sig = enhanced_strategy_signals(df, model)
            res = backtest(df, sig)
            if res and res["n_trades"] > 0:
                res["symbol"] = symbol
                res["interval"] = interval
                res["model"] = model
                all_results.append(res)

res_df = pd.DataFrame(all_results)
if not res_df.empty:
    summary = res_df.groupby("model").agg({
        "hit_rate": "mean",
        "total_ret": "mean",
        "n_trades": "sum",
        "sharpe": "mean"
    }).sort_values(by="hit_rate", ascending=False)
    
    print("\n--- TOP MODELLE (nach Trefferquote) ---")
    print(summary.to_string())
    summary.to_csv("/root/forschung/orchestra/backtests/enhanced_summary.csv")
    res_df.to_csv("/root/forschung/orchestra/backtests/enhanced_all.csv", index=False)
    print("\nGespeichert in /root/forschung/orchestra/backtests/enhanced_summary.csv")
else:
    print("Keine Trades generiert.")
