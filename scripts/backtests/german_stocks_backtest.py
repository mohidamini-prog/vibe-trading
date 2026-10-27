import yfinance as pd_yf
import pandas as pd
import numpy as np

def run_german_backtest(ticker="SAP.DE", name="SAP"):
    print(f"\n--- Backtest für {name} ({ticker}) ---")
    # 1. Daily Trend Filter
    daily = pd_yf.download(ticker, start="2025-10-26", end="2026-10-26", interval="1d", progress=False)
    if isinstance(daily.columns, pd.MultiIndex):
        daily.columns = daily.columns.droplevel(1)
    if len(daily) < 50:
        print(f"Nicht genug Daten für {name}")
        return
    daily['EMA50'] = daily['Close'].ewm(span=50, adjust=False).mean()
    daily['EMA200'] = daily['Close'].ewm(span=200, adjust=False).mean()
    daily['Daily_Trend'] = daily['EMA50'] > daily['EMA200']
    daily = daily.reset_index()
    date_col = 'Date' if 'Date' in daily.columns else daily.columns[0]
    daily['TradeDate'] = pd.to_datetime(daily[date_col]).dt.date
    
    # 2. Hourly Data resampled to 4h
    h4 = pd_yf.download(ticker, start="2025-10-26", end="2026-10-26", interval="1h", progress=False)
    if isinstance(h4.columns, pd.MultiIndex):
        h4.columns = h4.columns.droplevel(1)
    if len(h4) == 0:
        print(f"Keine Intraday-Daten für {name}")
        return
    h4 = h4.resample('4h').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
    
    # 3. Signals & Patterns
    o, h, l, c = h4['Open'], h4['High'], h4['Low'], h4['Close']
    body = (c - o).abs()
    h4['EMA20'] = c.ewm(span=20, adjust=False).mean()
    
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    h4['RSI'] = 100 - (100 / (1 + rs))
    
    bullish_engulfing = (c > o) & (c.shift(1) < o.shift(1)) & (c >= o.shift(1)) & (o <= c.shift(1))
    hammer = (l - o.combine(c, min) >= 2*body) & (h - o.combine(c, max) < 0.5*body)
    
    h4 = h4.reset_index()
    h4_date_col = h4.columns[0]
    h4['TradeDate'] = pd.to_datetime(h4[h4_date_col]).dt.date
    
    h4 = h4.merge(daily[['TradeDate', 'Daily_Trend']], on='TradeDate', how='left')
    h4.set_index(h4_date_col, inplace=True)
    
    long_cond = h4['Daily_Trend'].fillna(False) & (c > h4['EMA20']) & (h4['RSI'] > 40) & (h4['RSI'] < 75) & (bullish_engulfing | hammer)
    h4['Signal'] = np.where(long_cond, 1, 0)
    h4['Returns'] = c.pct_change() * h4['Signal'].shift(1)
    
    ret = (1 + h4['Returns'].dropna()).prod() - 1
    trades = int(h4['Signal'].diff().abs().sum() / 2)
    print(f"Gesamtrendite: {ret:.2%}")
    print(f"Anzahl Trades: {trades}")

if __name__ == "__main__":
    german_stocks = [("SAP.DE", "SAP"), ("SIE.DE", "Siemens"), ("ALV.DE", "Allianz"), ("BAS.DE", "BASF")]
    for ticker, name in german_stocks:
        run_german_backtest(ticker, name)
