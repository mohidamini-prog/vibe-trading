import yfinance as pd_yf
import pandas as pd
import numpy as np

def run_hourly_backtest(ticker="SAP.DE", name="SAP"):
    print(f"\n--- 1h-Frame Backtest für {name} ({ticker}) ---")
    data = pd_yf.download(ticker, start="2025-10-26", end="2026-10-26", interval="1h", progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(1)
    if len(data) < 100:
        print(f"Nicht genug Daten für {name}")
        return
        
    o, h, l, c = data['Open'], data['High'], data['Low'], data['Close']
    body = (c - o).abs()
    
    # Indicators on 1h
    data['EMA50'] = c.ewm(span=50, adjust=False).mean()
    data['EMA200'] = c.ewm(span=200, adjust=False).mean()
    data['Trend'] = data['EMA50'] > data['EMA200']
    
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    data['RSI'] = 100 - (100 / (1 + rs))
    
    bullish_engulfing = (c > o) & (c.shift(1) < o.shift(1)) & (c >= o.shift(1)) & (o <= c.shift(1))
    hammer = (l - o.combine(c, min) >= 2*body) & (h - o.combine(c, max) < 0.5*body)
    
    long_cond = data['Trend'] & (c > data['EMA50']) & (data['RSI'] > 40) & (data['RSI'] < 75) & (bullish_engulfing | hammer)
    data['Signal'] = np.where(long_cond, 1, 0)
    data['Returns'] = c.pct_change() * data['Signal'].shift(1)
    
    ret = (1 + data['Returns'].dropna()).prod() - 1
    trades = int(data['Signal'].diff().abs().sum() / 2)
    print(f"Gesamtrendite (1h): {ret:.2%}")
    print(f"Anzahl Trades (1h): {trades}")

if __name__ == "__main__":
    german_stocks = [("SAP.DE", "SAP"), ("SIE.DE", "Siemens"), ("ALV.DE", "Allianz"), ("BAS.DE", "BASF")]
    for ticker, name in german_stocks:
        run_hourly_backtest(ticker, name)
