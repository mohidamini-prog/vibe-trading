import yfinance as pd_yf
import pandas as pd
import numpy as np

def detect_patterns(ticker="BTC-USD", period="6mo", interval="1d"):
    data = pd_yf.download(ticker, period=period, interval=interval)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(1)
        
    o = data['Open']
    h = data['High']
    l = data['Low']
    c = data['Close']
    
    # Body and range calculations
    body = (c - o).abs()
    total_range = h - l
    upper_shadow = h - pd.concat([o, c], axis=1).max(axis=1)
    lower_shadow = pd.concat([o, c], axis=1).min(axis=1) - l
    
    # 1. Hammer (Small body at top, long lower shadow >= 2x body, tiny upper shadow)
    data['Hammer'] = (lower_shadow >= (2 * body)) & (upper_shadow < (body * 0.5)) & (body > 0)
    
    # 2. Shooting Star (Small body at bottom, long upper shadow >= 2x body, tiny lower shadow)
    data['ShootingStar'] = (upper_shadow >= (2 * body)) & (lower_shadow < (body * 0.5)) & (body > 0)
    
    # 3. Bullish Engulfing (Current candle green, prev red, current body engulfs prev body)
    prev_o = o.shift(1)
    prev_c = c.shift(1)
    prev_body = (prev_c - prev_o).abs()
    data['BullishEngulfing'] = (c > o) & (prev_c < prev_o) & (c >= prev_o) & (o <= prev_c) & (body > prev_body)
    
    # 4. Bearish Engulfing (Current candle red, prev green, current body engulfs prev body)
    data['BearishEngulfing'] = (c < o) & (prev_c > prev_o) & (c <= prev_o) & (o >= prev_c) & (body > prev_body)

    # Filter only days where a pattern occurred
    signals = data[data['Hammer'] | data['ShootingStar'] | data['BullishEngulfing'] | data['BearishEngulfing']].copy()
    
    signals['Pattern'] = np.select(
        [signals['Hammer'], signals['ShootingStar'], signals['BullishEngulfing'], signals['BearishEngulfing']],
        ['Hammer', 'Shooting Star', 'Bullish Engulfing', 'Bearish Engulfing'],
        default='None'
    )
    
    return signals[['Close', 'Pattern']]

print("--- AUTOMATIC PATTERN RECOGNITION (BTC-USD) ---")
print(detect_patterns("BTC-USD", "6mo", "1d").tail(10))
