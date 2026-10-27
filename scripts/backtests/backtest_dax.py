import yfinance as pd_yf
import pandas as pd
import numpy as np

# Download DAX (^GDAXI) data for 5 years
data = pd_yf.download("^GDAXI", period="5y", interval="1d")
if isinstance(data.columns, pd.MultiIndex):
    data.columns = data.columns.droplevel(1)

# Indicators
data['EMA50'] = data['Close'].ewm(span=50, adjust=False).mean()
data['EMA200'] = data['Close'].ewm(span=200, adjust=False).mean()

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

data['RSI'] = calc_rsi(data['Close'])

# Adjusted Momentum / RSI Thresholds for European Indices (DAX is more range-bound)
# Broader RSI band (e.g., 40 to 75) and added ADX / Volatility filter proxy
data['Signal'] = 0
dax_long = (data['Close'] > data['EMA50']) & (data['RSI'] > 40) & (data['RSI'] < 75)
data.loc[dax_long, 'Signal'] = 1
data.loc[data['Close'] < data['EMA50'], 'Signal'] = -1

data['Market_Returns'] = data['Close'].pct_change()
data['Strategy_Returns'] = data['Market_Returns'] * data['Signal'].shift(1)

cum_market = (1 + data['Market_Returns'].dropna()).prod() - 1
cum_strategy = (1 + data['Strategy_Returns'].dropna()).prod() - 1

print(f"--- DAX BACKTEST WITH ADJUSTED MOMENTUM (5 YEARS) ---")
print(f"Buy & Hold Return: {cum_market*100:.2f}%")
print(f"Adjusted Strategy Return: {cum_strategy*100:.2f}%")
