"""
Indikator-Bibliothek für vibe-trading.
Reine Pandas/NumPy-Implementierungen (keine TA-Lib-Abhängigkeit).
"""
import numpy as np
import pandas as pd


def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def sma(series, period):
    return series.rolling(period).mean()


def rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(series, fast=12, slow=26, signal=9):
    line = ema(series, fast) - ema(series, slow)
    sig = ema(line, signal)
    return line, sig, line - sig


def bollinger(series, period=20, std=2.0):
    mid = series.rolling(period).mean()
    sd = series.rolling(period).std()
    return mid + std * sd, mid, mid - std * sd


def atr(high, low, close, period=14):
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def adx(high, low, close, period=14):
    plus_dm = high.diff().clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)
    tr = atr(high, low, close, 1)
    plus_di = 100 * (plus_dm.rolling(period).mean() / tr.rolling(period).mean())
    minus_di = 100 * (minus_dm.rolling(period).mean() / tr.rolling(period).mean())
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.rolling(period).mean()


def supertrend(high, low, close, period=10, mult=3.0):
    atr_v = atr(high, low, close, period)
    hl2 = (high + low) / 2
    upper = hl2 + mult * atr_v
    lower = hl2 - mult * atr_v
    trend = pd.Series(index=close.index, dtype=float)
    direction = pd.Series(index=close.index, dtype=int)
    for i in range(len(close)):
        if i == 0:
            trend.iloc[i] = lower.iloc[i]
            direction.iloc[i] = 1
        else:
            pt, pd_ = trend.iloc[i - 1], direction.iloc[i - 1]
            if pd_ == 1:
                trend.iloc[i] = max(lower.iloc[i], pt)
                if close.iloc[i] < trend.iloc[i]:
                    direction.iloc[i] = -1
                    trend.iloc[i] = upper.iloc[i]
                else:
                    direction.iloc[i] = 1
            else:
                trend.iloc[i] = min(upper.iloc[i], pt)
                if close.iloc[i] > trend.iloc[i]:
                    direction.iloc[i] = 1
                    trend.iloc[i] = lower.iloc[i]
                else:
                    direction.iloc[i] = -1
    return trend, direction


def donchian(high, low, period=20):
    return high.rolling(period).max(), low.rolling(period).min()


def chop_index(high, low, close, period=14):
    atr_v = atr(high, low, close, 1)
    high_n = high.rolling(period).max()
    low_n = low.rolling(period).min()
    return 100 * np.log10(atr_v.rolling(period).sum() / (high_n - low_n)) / np.log10(period)
