import yfinance as pd_yf
import pandas as pd
import numpy as np

def run_combined_backtest(ticker="BTC-USD", period="1y", interval="1d"):
    data = pd_yf.download(ticker, period=period, interval=interval)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(1)
        
    o, h, l, c = data['Open'], data['High'], data['Low'], data['Close']
    body = (c - o).abs()
    rng = h - l
    
    # --- 1. ALTES SETUP (EMA + RSI + Bollinger Squeeze) ---
    data['EMA50'] = c.ewm(span=50, adjust=False).mean()
    data['EMA200'] = c.ewm(span=200, adjust=False).mean()
    
    delta = c.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    data['RSI'] = 100 - (100 / (1 + (gain / loss)))
    
    bb_mid = c.rolling(window=20).mean()
    bb_std = c.rolling(window=20).std()
    bb_width = ((bb_mid + 2*bb_std) - (bb_mid - 2*bb_std)) / bb_mid
    
    base_trend = (data['EMA50'] > data['EMA200']) & (data['RSI'] > 45) & (data['RSI'] < 70) & (bb_width > bb_width.rolling(50).median())
    
    # --- 2. NEUES SETUP (Chart- & Kerzenmuster / Smart Money Trigger) ---
    bullish_engulfing = (c > o) & (c.shift(1) < o.shift(1)) & (c >= o.shift(1)) & (o <= c.shift(1))
    hammer = (l - o.combine(c, min) >= 2*body) & (h - o.combine(c, max) < 0.5*body)
    fvg_bullish = l > h.shift(2)
    
    pattern_trigger = bullish_engulfing | hammer | fvg_bullish
    
    # --- 3. KOMBINATION ---
    data['Signal'] = 0
    # Long wenn Trend-Filter UND ein starkes bullishes Muster triggert
    data.loc[base_trend & pattern_trigger, 'Signal'] = 1
    # Short/Flat im Downtrend
    data.loc[data['EMA50'] < data['EMA200'], 'Signal'] = -1
    
    data['Market_Returns'] = c.pct_change()
    data['Strategy_Returns'] = data['Market_Returns'] * data['Signal'].shift(1)
    
    cum_market = (1 + data['Market_Returns'].dropna()).prod() - 1
    cum_strategy = (1 + data['Strategy_Returns'].dropna()).prod() - 1
    
    print(f"=== COMBINED BACKTEST (OLD SETUP + NEW PATTERN TRIGGERS) ===")
    print(f"Buy & Hold: {cum_market*100:.2f}% | Combined Strategy: {cum_strategy*100:.2f}%\n")

run_combined_backtest("BTC-USD", "1y", "1d")
