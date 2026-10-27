"""
Gemeinsame Hilfsfunktionen: Indikatoren (leicht, numpy-only), Zeit, Logging.
Kein pandas, kein torch — nur numpy. ARM-tauglich.
"""
import numpy as np


# --- EMA (exponentieller gleitender Mittelwert), numpy-only ---
def ema(values: np.ndarray, period: int) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if len(values) == 0:
        return values
    alpha = 2.0 / (period + 1.0)
    out = np.empty_like(values)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    return out


# --- SMA ---
def sma(values: np.ndarray, period: int) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if len(values) < period:
        return np.full(len(values), np.nan)
    out = np.full(len(values), np.nan)
    for i in range(period - 1, len(values)):
        out[i] = values[i - period + 1 : i + 1].mean()
    return out


# --- RSI (Wilder) ---
def rsi(values: np.ndarray, period: int = 14) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if len(values) < period + 1:
        return np.full(len(values), np.nan)
    delta = np.diff(values)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = gain[:period].mean()
    avg_loss = loss[:period].mean()
    out = np.full(len(values), np.nan)
    for i in range(period, len(values)):
        avg_gain = (avg_gain * (period - 1) + gain[i - 1]) / period
        avg_loss = (avg_loss * (period - 1) + loss[i - 1]) / period
        if avg_loss == 0:
            out[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100.0 - 100.0 / (1.0 + rs)
    return out


# --- ATR (Average True Range) ---
def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    high, low, close = map(lambda x: np.asarray(x, dtype=float), (high, low, close))
    n = len(close)
    if n < period + 1:
        return np.full(n, np.nan)
    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
    out = np.full(n, np.nan)
    out[period] = tr[1 : period + 1].mean()
    for i in range(period + 1, n):
        out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out


# --- Z-Score (Standardabweichung vom Mittel) ---
def zscore(values: np.ndarray, period: int = 20) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    n = len(values)
    out = np.full(n, np.nan)
    if n < period:
        return out
    for i in range(period - 1, n):
        window = values[i - period + 1 : i + 1]
        m = window.mean()
        s = window.std()
        out[i] = (values[i] - m) / s if s > 0 else 0.0
    return out


# --- ADX (Average Directional Index), vereinfacht ---
def adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    high, low = map(lambda x: np.asarray(x, dtype=float), (high, low))
    n = len(close)
    if n < period * 2:
        return np.full(n, np.nan)
    up = np.zeros(n)
    down = np.zeros(n)
    for i in range(1, n):
        up[i] = high[i] - high[i - 1]
        down[i] = low[i - 1] - low[i]
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
    out = np.full(n, np.nan)
    plus_di = np.zeros(n)
    minus_di = np.zeros(n)
    for i in range(period, n):
        atr_sum = tr[i - period + 1 : i + 1].sum()
        plus_di[i] = 100 * plus_dm[i - period + 1 : i + 1].sum() / atr_sum if atr_sum else 0
        minus_di[i] = 100 * minus_dm[i - period + 1 : i + 1].sum() / atr_sum if atr_sum else 0
        if plus_di[i] + minus_di[i] > 0:
            dx = 100 * abs(plus_di[i] - minus_di[i]) / (plus_di[i] + minus_di[i])
            out[i] = dx
    return out


# --- Chop (Choppiness Index): Seitwärts-Erkennung ---
def chop(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    high, low = map(lambda x: np.asarray(x, dtype=float), (high, low))
    n = len(close)
    out = np.full(n, np.nan)
    if n < period:
        return out
    tr_sum = np.zeros(n)
    for i in range(1, n):
        tr_sum[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
    for i in range(period, n):
        s = tr_sum[i - period + 1 : i + 1].sum()
        rng = high[i - period + 1 : i + 1].max() - low[i - period + 1 : i + 1].min()
        if rng > 0 and s > 0:
            out[i] = 100 * np.log10(s / rng) / np.log10(period)
    return out


if __name__ == "__main__":
    # Smoke-Test
    np.random.seed(0)
    close = np.cumsum(np.random.randn(100)) + 100
    high = close + 0.5
    low = close - 0.5
    print("EMA9 last:", ema(close, 9)[-1])
    print("RSI14 last:", rsi(close, 14)[-1])
    print("ATR last:", atr(high, low, close, 14)[-1])
    print("zscore last:", zscore(close, 20)[-1])
    print("ADX last:", adx(high, low, close, 14)[-1])
    print("chop last:", chop(high, low, close, 14)[-1])
