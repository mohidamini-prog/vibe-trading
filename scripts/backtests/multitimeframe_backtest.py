import yfinance as pd_yf
import pandas as pd
import numpy as np

def run_mtf_backtest(ticker="^GDAXI", name="DAX"):
    # 1. Daily Data
    daily = pd_yf.download(ticker, period="1y", interval="1d", progress=False)
    if isinstance(daily.columns, pd.MultiIndex):
        daily.columns = daily.columns.droplevel(1)
    daily['EMA50'] = daily['Close'].ewm(span=50, adjust=False).mean()
    daily['EMA200'] = daily['Close'].ewm(span=200, adjust=False).mean()
    daily['Daily_Trend'] = daily['EMA50'] > daily['EMA200']
    daily = daily.reset_index()
    # rename date column appropriately
    date_col = 'Date' if 'Date' in daily.columns else daily.columns[0]
    daily['TradeDate'] = pd.to_datetime(daily[date_col]).dt.date
    
    # 2. 4h Data (proxy via 1h resample)
    h4 = pd_yf.download(ticker, period="60d", interval="1h", progress=False)
    if isinstance(h4.columns, pd.MultiIndex):
        h4.columns = h4.columns.droplevel(1)
    h4 = h4.resample('4h').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
    
    # 3. Signals & Mapping
    o, h, l, c = h4['Open'], h4['High'], h4['Low'], h4['Close']
    body = (c - o).abs()
    h4['EMA20'] = c.ewm(span=20, adjust=False).mean()
    
    # RSI calculation
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    h4['RSI'] = 100 - (100 / (1 + rs))
    
    bullish_engulfing = (c > o) & (c.shift(1) < o.shift(1)) & (c >= o.shift(1)) & (o <= c.shift(1))
    hammer = (l - o.combine(c, min) >= 2*body) & (h - o.combine(c, max) < 0.5*body)
    
    h4 = h4.reset_index()
    h4_date_col = 'Datetime' if 'Datetime' in h4.columns else h4.columns[0]
    h4['TradeDate'] = pd.to_datetime(h4[h4_date_col]).dt.date
    
    h4 = h4.merge(daily[['TradeDate', 'Daily_Trend']], on='TradeDate', how='left')
    h4.set_index(h4_date_col, inplace=True)
    
    long_cond = h4['Daily_Trend'].fillna(False) & (c > h4['EMA20']) & (h4['RSI'] > 40) & (h4['RSI'] < 75) & (bullish_engulfing | hammer)
    h4['Signal'] = np.where(long_cond, 1, 0)
    h4['Returns'] = c.pct_change() * h4['Signal'].shift(1)
    
    ret = (1 + h4['Returns'].dropna()).prod() - 1
    print(f"=== {name} MTF Strategy (4h/1d) Result: {ret:.2%} ===")

if __name__ == "__main__":
    print("Starte Aktien-Backtest (US & Deutschland, 4h / 1D)...")
    run_mtf_backtest("^GDAXI", "DAX (Deutschland)")
    run_mtf_backtest("AAPL", "Apple (US)")
    run_mtf_backtest("TSLA", "Tesla (US)")
