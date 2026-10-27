import yfinance as pd_yf
import pandas as pd
import numpy as np

# Download DAX (^GDAXI) data for 5 years
data = pd_yf.download("^GDAXI", period="5y", interval="1d")
if isinstance(data.columns, pd.MultiIndex):
    data.columns = data.columns.droplevel(1)

# Mean Reversion Indicators: Bollinger Bands (20, 2) & RSI
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

# Strategy: Mean Reversion (Buy when price touches lower BB or RSI < 35, Sell when hitting middle/upper BB)
data['Signal'] = 0
# Long when oversold / touching lower band
long_cond = (data['Close'] <= data['BB_Lower']) | (data['RSI'] < 35)
data.loc[long_cond, 'Signal'] = 1

data['Market_Returns'] = data['Close'].pct_change()
data['Strategy_Returns'] = data['Market_Returns'] * data['Signal'].shift(1)

cum_market = (1 + data['Market_Returns'].dropna()).prod() - 1
cum_strategy = (1 + data['Strategy_Returns'].dropna()).prod() - 1

print(f"--- DAX MEAN-REVERSION BACKTEST (5 YEARS) ---")
print(f"Buy & Hold Return: {cum_market*100:.2f}%")
print(f"Mean-Reversion Strategy Return: {cum_strategy*100:.2f}%")
