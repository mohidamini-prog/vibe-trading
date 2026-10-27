import yfinance as pd_yf
import pandas as pd
import numpy as np

def run_adaptive_backtest(ticker="BTC-USD", asset_type="crypto", period="1y"):
    data = pd_yf.download(ticker, period=period, interval="1d")
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(1)
        
    data['BB_Middle'] = data['Close'].rolling(window=20).mean()
    data['BB_Std'] = data['Close'].rolling(window=20).std()
    data['BB_Lower'] = data['BB_Middle'] - (data['BB_Std'] * 2)
    data['BB_Upper'] = data['BB_Middle'] + (data['BB_Std'] * 2)
    
    def calc_rsi(series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
        
    data['RSI'] = calc_rsi(data['Close'])
    data['EMA50'] = data['Close'].ewm(span=50, adjust=False).mean()
    data['EMA200'] = data['Close'].ewm(span=200, adjust=False).mean()
    
    data['Signal'] = 0
    
    if asset_type == "crypto":
        # Trend-Following + Bollinger Squeeze Filter
        data['BB_Width'] = (data['BB_Upper'] - data['BB_Lower']) / data['BB_Middle']
        long_cond = (data['EMA50'] > data['EMA200']) & (data['RSI'] > 45) & (data['RSI'] < 70) & (data['BB_Width'] > data['BB_Width'].rolling(50).median())
        data.loc[long_cond, 'Signal'] = 1
        data.loc[data['EMA50'] < data['EMA200'], 'Signal'] = -1
    elif asset_type == "index":
        # Mean Reversion (Dip Buying)
        long_cond = (data['Close'] <= data['BB_Lower']) | (data['RSI'] < 35)
        data.loc[long_cond, 'Signal'] = 1
        
    data['Market_Returns'] = data['Close'].pct_change()
    data['Strategy_Returns'] = data['Market_Returns'] * data['Signal'].shift(1)
    
    cum_market = (1 + data['Market_Returns'].dropna()).prod() - 1
    cum_strategy = (1 + data['Strategy_Returns'].dropna()).prod() - 1
    
    print(f"=== ASSET: {ticker} ({asset_type.upper()}) ===")
    print(f"Buy & Hold: {cum_market*100:.2f}% | Adaptive Strategy: {cum_strategy*100:.2f}%\n")

run_adaptive_backtest("BTC-USD", "crypto", "1y")
run_adaptive_backtest("^GDAXI", "index", "5y")
