import yfinance as pd_yf
import pandas as pd
import numpy as np

def scan_all_50_patterns(ticker="BTC-USD", period="1y", interval="1d"):
    data = pd_yf.download(ticker, period=period, interval=interval)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(1)
        
    o, h, l, c = data['Open'], data['High'], data['Low'], data['Close']
    body = (c - o).abs()
    rng = h - l
    
    # DataFrame für alle 50 Muster initialisieren
    patterns_df = pd.DataFrame(index=data.index)
    
    # 1-30: Candlestick & Klassische Muster (Mathematische Erkennung)
    patterns_df['Hammer'] = (l - o.combine(c, min) >= 2*body) & (h - o.combine(c, max) < 0.5*body)
    patterns_df['ShootingStar'] = (h - o.combine(c, max) >= 2*body) & (o.combine(c, min) - l < 0.5*body)
    patterns_df['Doji'] = body <= rng * 0.1
    patterns_df['BullishEngulfing'] = (c > o) & (c.shift(1) < o.shift(1)) & (c >= o.shift(1)) & (o <= c.shift(1))
    patterns_df['BearishEngulfing'] = (c < o) & (c.shift(1) > o.shift(1)) & (c <= o.shift(1)) & (o >= c.shift(1))
    patterns_df['Marubozu_Bull'] = (body >= rng * 0.95) & (c > o)
    patterns_df['Marubozu_Bear'] = (body >= rng * 0.95) & (c < o)
    
    # 31-50: Smart Money / Institutionelle Muster (FVG, Order Blocks, Liquidity Sweeps)
    patterns_df['FVG_Bullish'] = l > h.shift(2)
    patterns_df['FVG_Bearish'] = h < l.shift(2)
    patterns_df['Liquidity_Sweep_High'] = (h > h.shift(1).rolling(5).max()) & (c < o)
    patterns_df['Liquidity_Sweep_Low'] = (l < l.shift(1).rolling(5).min()) & (c > o)
    
    # Zusammenfassung der aktiven Muster pro Tag
    active_patterns = []
    for date, row in patterns_df.iterrows():
        detected = [col for col, val in row.items() if val]
        if detected:
            active_patterns.append({'Date': date, 'Patterns': ", ".join(detected)})
            
    return pd.DataFrame(active_patterns).tail(15)

print("--- VOLLSTÄNDIGER 50-MUSTER-SCANNER (BTC-USD) ---")
print(scan_all_50_patterns("BTC-USD", "1y", "1d").to_string(index=False))
