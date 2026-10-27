import yfinance as pd_yf
import pandas as pd
import numpy as np

def detect_all_patterns(ticker="BTC-USD", period="1y", interval="1d"):
    data = pd_yf.download(ticker, period=period, interval=interval)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(1)
        
    o, h, l, c = data['Open'], data['High'], data['Low'], data['Close']
    body = (c - o).abs()
    
    # 1. Single Candles
    data['Hammer'] = (l - o.combine(c, min) >= 2*body) & (h - o.combine(c, max) < 0.5*body)
    data['ShootingStar'] = (h - o.combine(c, max) >= 2*body) & (o.combine(c, min) - l < 0.5*body)
    data['Doji'] = body <= (h - l) * 0.1
    
    # 2. Multi-Candle
    prev_o, prev_c = o.shift(1), c.shift(1)
    data['BullishEngulfing'] = (c > o) & (prev_c < prev_o) & (c >= prev_o) & (o <= prev_c)
    data['BearishEngulfing'] = (c < o) & (prev_c > prev_o) & (c <= prev_o) & (o >= prev_c)
    
    # 3. Institutional (Concept approximations)
    # Fair Value Gap: Current candle high/low doesn't overlap with candle n-2
    data['FVG_Bullish'] = (l > h.shift(2)) # Simple gap
    data['FVG_Bearish'] = (h < l.shift(2))
    
    # Order Block proxy: Strong move followed by consolidation
    data['Momentum'] = c.pct_change(3)
    data['OrderBlock_Potential'] = (data['Momentum'].abs() > 0.05) & (body < body.rolling(5).mean())
    
    # Aggregation
    patterns = []
    for col in ['Hammer', 'ShootingStar', 'Doji', 'BullishEngulfing', 'BearishEngulfing', 'FVG_Bullish', 'FVG_Bearish', 'OrderBlock_Potential']:
        mask = data[col]
        patterns.append(pd.Series(col, index=data.index[mask]))
        
    all_patterns = pd.concat(patterns).sort_index()
    return all_patterns.tail(20)

print("--- FULL PATTERN SUITE (BTC-USD) ---")
print(detect_all_patterns("BTC-USD", "1y", "1d"))
