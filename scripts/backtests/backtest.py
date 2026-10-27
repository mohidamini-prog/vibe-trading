import yfinance as pd_yf
import pandas as pd
import numpy as np

# Download DAX (^GDAXI) data on 1-daily interval for 5 years
tickers = ["^GDAXI"]
data = pd_yf.download("^GDAXI", period="5y", interval="1d")
if isinstance(data.columns, pd.MultiIndex):
    data.columns = data.columns.droplevel(1)

# Indicators (Daily setup: EMA 50 & 200)
data['EMA50'] = data['Close'].ewm(span=50, adjust=False).mean()
data['EMA200'] = data['Close'].ewm(span=200, adjust=False).mean()

# Simple RSI calculation
def calc_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

data['RSI'] = calc_rsi(data['Close'])

# Bollinger Bands (20, 2)
data['BB_Middle'] = data['Close'].rolling(window=20).mean()
data['BB_Std'] = data['Close'].rolling(window=20).std()
data['BB_Upper'] = data['BB_Middle'] + (data['BB_Std'] * 2)
data['BB_Lower'] = data['BB_Middle'] - (data['BB_Std'] * 2)
data['BB_Width'] = (data['BB_Upper'] - data['BB_Lower']) / data['BB_Middle']

# Enhanced Strategy with strict filters + Bollinger Squeeze filter
data['Signal'] = 0
# Long condition: Uptrend + RSI healthy + Volatility (BB width > median or expanding)
long_cond = (data['EMA50'] > data['EMA200']) & (data['RSI'] > 45) & (data['RSI'] < 70) & (data['BB_Width'] > data['BB_Width'].rolling(50).median())
data.loc[long_cond, 'Signal'] = 1
data.loc[data['EMA50'] < data['EMA200'], 'Signal'] = -1

data['Market_Returns'] = data['Close'].pct_change()
data['Strategy_Returns'] = data['Market_Returns'] * data['Signal'].shift(1)

cum_market = (1 + data['Market_Returns'].dropna()).prod() - 1
cum_strategy = (1 + data['Strategy_Returns'].dropna()).prod() - 1

print(f"--- BACKTEST RESULT (DAX ^GDAXI - 5 YEARS) ---")
print(f"Buy & Hold Return: {cum_market*100:.2f}%")
print(f"Strategy Return (EMA + RSI): {cum_strategy*100:.2f}%")
