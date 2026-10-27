#!/usr/bin/env python3
"""
Hourly Scanner - Kraken Crypto + Yahoo Finance Stocks
Runs mixed strategy on 4h timeframe with 1D HTF filter
Outputs new signals only (since last run)
"""

import json
import numpy as np
import pandas as pd
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import requests
import time
import os
import sys
import yfinance as yf

# ============================================================
# CONFIG
# ============================================================
# Kraken major pairs (internal names)
KRAKEN_PAIRS = {
    "BTC/USD": "XXBTZUSD",
    "ETH/USD": "XETHZUSD",
    "SOL/USD": "SOLUSD",
    "XRP/USD": "XXRPZUSD",
    "ADA/USD": "ADAUSD",
    "DOGE/USD": "XDGUSD",
    "AVAX/USD": "AVAXUSD",
    "DOT/USD": "DOTUSD",
    "LINK/USD": "LINKUSD",
    "MATIC/USD": "MATICUSD",
}

# Yahoo Finance major stocks (liquid, options available)
YAHOO_STOCKS = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "NVIDIA",
    "GOOGL": "Alphabet",
    "AMZN": "Amazon",
    "META": "Meta",
    "TSLA": "Tesla",
    "JPM": "JPMorgan",
    "V": "Visa",
    "JNJ": "Johnson & Johnson",
    "WMT": "Walmart",
    "PG": "Procter & Gamble",
    "MA": "Mastercard",
    "UNH": "UnitedHealth",
    "HD": "Home Depot",
}

# State file to track last signals
STATE_FILE = "/root/forschung/scanner_state.json"
OUTPUT_FILE = "/root/forschung/signals_latest.json"

# Strategy parameters (same as backtest)
PARAMS = {
    "ema_fast": 9, "ema_med": 21, "ema_slow": 50, "ema_trend": 200,
    "rsi_period": 14, "rsi_oversold": 30, "rsi_overbought": 70,
    "rsi_chop_min": 40, "rsi_chop_max": 60,
    "bb_period": 20, "bb_std": 2.0, "bb_width_pctl": 0.3,
    "adx_period": 14, "adx_threshold": 25,
    "chop_period": 14, "chop_threshold": 55,
    "donchian_period": 20,
    "st_period": 10, "st_mult": 3.0,
    "vol_lookback": 20, "vol_mult": 1.3,
    "htf_ema": 50,
    "rr_ratios": [1.5, 2.5, 4.0],
    "min_confidence": 0.65,
}

# ============================================================
# INDICATORS (same as backtest)
# ============================================================
def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    middle = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return upper, middle, lower

def bb_width(upper: pd.Series, lower: pd.Series, middle: pd.Series) -> pd.Series:
    return (upper - lower) / middle

def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    plus_dm = high.diff()
    minus_dm = low.diff().abs()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    plus_dm[(plus_dm - minus_dm) < 0] = 0
    minus_dm[(minus_dm - plus_dm) < 0] = 0
    tr = atr(high, low, close, 1)
    plus_di = 100 * (plus_dm.rolling(period).mean() / tr.rolling(period).mean())
    minus_di = 100 * (minus_dm.rolling(period).mean() / tr.rolling(period).mean())
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    return dx.rolling(period).mean()

def chop_index(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    atr_vals = atr(high, low, close, 1)
    high_n = high.rolling(period).max()
    low_n = low.rolling(period).min()
    ci = 100 * np.log10(atr_vals.rolling(period).sum() / (high_n - low_n)) / np.log10(period)
    return ci

def supertrend(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 10, multiplier: float = 3.0) -> Tuple[pd.Series, pd.Series]:
    atr_vals = atr(high, low, close, period)
    hl2 = (high + low) / 2
    upper_band = hl2 + multiplier * atr_vals
    lower_band = hl2 - multiplier * atr_vals
    trend = pd.Series(index=close.index, dtype=float)
    direction = pd.Series(index=close.index, dtype=int)
    for i in range(len(close)):
        if i == 0:
            trend.iloc[i] = lower_band.iloc[i]
            direction.iloc[i] = 1
        else:
            prev_trend = trend.iloc[i-1]
            prev_dir = direction.iloc[i-1]
            if prev_dir == 1:
                trend.iloc[i] = max(lower_band.iloc[i], prev_trend)
                if close.iloc[i] < trend.iloc[i]:
                    direction.iloc[i] = -1
                    trend.iloc[i] = upper_band.iloc[i]
                else:
                    direction.iloc[i] = 1
            else:
                trend.iloc[i] = min(upper_band.iloc[i], prev_trend)
                if close.iloc[i] > trend.iloc[i]:
                    direction.iloc[i] = 1
                    trend.iloc[i] = lower_band.iloc[i]
                else:
                    direction.iloc[i] = -1
    return trend, direction

def donchian(high: pd.Series, low: pd.Series, period: int = 20) -> Tuple[pd.Series, pd.Series]:
    upper = high.rolling(period).max()
    lower = low.rolling(period).min()
    return upper, lower

# ============================================================
# DATA FETCHERS
# ============================================================
def fetch_kraken_ohlc(pair: str, interval: int = 240, days_back: int = 365) -> pd.DataFrame:
    """Fetch 4h or 1d data from Kraken."""
    url = "https://api.kraken.com/0/public/OHLC"
    since = int((datetime.now() - timedelta(days=days_back)).timestamp())
    params = {"pair": pair, "interval": interval, "since": since}
    resp = requests.get(url, params=params, timeout=30)
    data = resp.json()
    if data.get("error"):
        raise ValueError(f"Kraken error: {data['error']}")
    key = [k for k in data["result"].keys() if k != "last"][0]
    candles = data["result"][key]
    df = pd.DataFrame(candles, columns=["time", "open", "high", "low", "close", "vwap", "volume", "count"])
    df["time"] = pd.to_datetime(df["time"], unit="s")
    for col in ["open", "high", "low", "close", "vwap", "volume"]:
        df[col] = df[col].astype(float)
    return df.set_index("time").sort_index()[["open", "high", "low", "close", "volume", "vwap"]]

def fetch_yahoo_ohlc(ticker: str, interval: str = "4h", days_back: int = 365) -> pd.DataFrame:
    """Fetch data from Yahoo Finance. Interval: 4h=240m, 1d=1d."""
    # yfinance doesn't support 4h directly, use 1h and resample
    if interval == "4h":
        df = yf.download(ticker, period=f"{days_back}d", interval="1h", progress=False, auto_adjust=True)
        if df.empty:
            return pd.DataFrame()
        # Resample to 4h
        df = df.resample("4H").agg({
            "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"
        }).dropna()
        df.columns = ["open", "high", "low", "close", "volume"]
    else:  # 1d
        df = yf.download(ticker, period=f"{days_back*2}d", interval="1d", progress=False, auto_adjust=True)
        if df.empty:
            return pd.DataFrame()
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.columns = ["open", "high", "low", "close", "volume"]
    return df.sort_index()

# ============================================================
# STRATEGY
# ============================================================
@dataclass
class Signal:
    symbol: str
    market: str  # "CRYPTO" or "STOCK"
    time: str
    direction: str
    entry: float
    sl: float
    tp1: float
    tp2: float
    tp3: float
    confidence: float
    reason: str
    htf_trend: str
    current_price: float

class MixedStrategy:
    def __init__(self, params: dict):
        self.p = params
    
    def prepare_data(self, df_4h: pd.DataFrame, df_1d: pd.DataFrame) -> pd.DataFrame:
        df = df_4h.copy()
        # EMAs
        df["ema_fast"] = ema(df["close"], self.p["ema_fast"])
        df["ema_med"] = ema(df["close"], self.p["ema_med"])
        df["ema_slow"] = ema(df["close"], self.p["ema_slow"])
        df["ema_trend"] = ema(df["close"], self.p["ema_trend"])
        # MACD
        df["macd"], df["macd_signal"], df["macd_hist"] = macd(df["close"])
        # RSI
        df["rsi"] = rsi(df["close"], self.p["rsi_period"])
        # Bollinger
        df["bb_upper"], df["bb_mid"], df["bb_lower"] = bollinger_bands(df["close"], self.p["bb_period"], self.p["bb_std"])
        df["bb_width"] = bb_width(df["bb_upper"], df["bb_lower"], df["bb_mid"])
        df["bb_width_pctl"] = df["bb_width"].rolling(100).rank(pct=True)
        # ADX
        df["adx"] = adx(df["high"], df["low"], df["close"], self.p["adx_period"])
        # Chop
        df["chop"] = chop_index(df["high"], df["low"], df["close"], self.p["chop_period"])
        # Supertrend
        df["st_line"], df["st_dir"] = supertrend(df["high"], df["low"], df["close"], self.p["st_period"], self.p["st_mult"])
        # Donchian
        df["dc_upper"], df["dc_lower"] = donchian(df["high"], df["low"], self.p["donchian_period"])
        # Volume
        df["vol_avg"] = df["volume"].rolling(self.p["vol_lookback"]).mean()
        df["vol_ratio"] = df["volume"] / df["vol_avg"]
        # HTF Trend
        if not df_1d.empty:
            df_1d = df_1d.copy()
            df_1d["htf_ema"] = ema(df_1d["close"], self.p["htf_ema"])
            df_1d["htf_trend"] = np.where(df_1d["close"] > df_1d["htf_ema"], "UP", "DOWN")
            htf = df_1d[["htf_trend"]].resample("4H").ffill()
            df = df.join(htf, how="left")
            df["htf_trend"] = df["htf_trend"].ffill()
        else:
            df["htf_trend"] = "NEUTRAL"
        # Trend alignment
        df["ema_stack_up"] = (df["ema_fast"] > df["ema_med"]) & (df["ema_med"] > df["ema_slow"]) & (df["ema_slow"] > df["ema_trend"])
        df["ema_stack_down"] = (df["ema_fast"] < df["ema_med"]) & (df["ema_med"] < df["ema_slow"]) & (df["ema_slow"] < df["ema_trend"])
        df["macd_bull"] = (df["macd"] > df["macd_signal"]) & (df["macd_hist"] > 0)
        df["macd_bear"] = (df["macd"] < df["macd_signal"]) & (df["macd_hist"] < 0)
        # Sideways filter
        df["is_choppy"] = (df["adx"] < self.p["adx_threshold"]) | (df["chop"] > self.p["chop_threshold"]) | (df["bb_width_pctl"] < self.p["bb_width_pctl"])
        df["rsi_chop"] = (df["rsi"] > self.p["rsi_chop_min"]) & (df["rsi"] < self.p["rsi_chop_max"])
        return df
    
    def generate_signal(self, df: pd.DataFrame, symbol: str, market: str, idx: int = -1) -> Optional[Signal]:
        """Generate signal at index idx (default: latest closed candle)."""
        if idx == -1:
            idx = len(df) - 1
        if idx < max(self.p["ema_trend"], self.p["bb_period"], self.p["adx_period"], self.p["chop_period"], self.p["st_period"]) + 10:
            return None
        
        row = df.iloc[idx]
        prev = df.iloc[idx-1]
        
        # SIDEWAYS FILTER
        if row["is_choppy"] or row["rsi_chop"]:
            return None
        
        htf = row["htf_trend"]
        atr_val = atr(df["high"], df["low"], df["close"], 14).iloc[idx]
        atr_val = float(atr_val) if not np.isnan(atr_val) else row["close"] * 0.02
        
        long_cond = []
        short_cond = []
        
        # TrendFollow
        if row["ema_stack_up"] and row["macd_bull"] and row["st_dir"] == 1 and htf == "UP":
            long_cond.append("TrendFollow")
        if row["ema_stack_down"] and row["macd_bear"] and row["st_dir"] == -1 and htf == "DOWN":
            short_cond.append("TrendFollow")
        
        # Breakout
        if row["close"] > prev["dc_upper"] and row["vol_ratio"] > self.p["vol_mult"] and htf == "UP":
            long_cond.append("Breakout")
        if row["close"] < prev["dc_lower"] and row["vol_ratio"] > self.p["vol_mult"] and htf == "DOWN":
            short_cond.append("Breakout")
        
        # Pullback
        if prev["rsi"] < self.p["rsi_oversold"] and row["rsi"] > prev["rsi"] and row["close"] > row["st_line"] and htf == "UP":
            long_cond.append("Pullback")
        if prev["rsi"] > self.p["rsi_overbought"] and row["rsi"] < prev["rsi"] and row["close"] < row["st_line"] and htf == "DOWN":
            short_cond.append("Pullback")
        
        if long_cond:
            direction = "LONG"
            reason = "+".join(long_cond)
            entry = row["close"]
            sl = entry - 2.0 * atr_val
            confidence = min(0.9, 0.5 + 0.15 * len(long_cond))
        elif short_cond:
            direction = "SHORT"
            reason = "+".join(short_cond)
            entry = row["close"]
            sl = entry + 2.0 * atr_val
            confidence = min(0.9, 0.5 + 0.15 * len(short_cond))
        else:
            return None
        
        if confidence < self.p["min_confidence"]:
            return None
        
        risk = abs(entry - sl)
        tp1 = entry + risk * self.p["rr_ratios"][0] if direction == "LONG" else entry - risk * self.p["rr_ratios"][0]
        tp2 = entry + risk * self.p["rr_ratios"][1] if direction == "LONG" else entry - risk * self.p["rr_ratios"][1]
        tp3 = entry + risk * self.p["rr_ratios"][2] if direction == "LONG" else entry - risk * self.p["rr_ratios"][2]
        
        return Signal(
            symbol=symbol,
            market=market,
            time=str(row.name),
            direction=direction,
            entry=round(entry, 2),
            sl=round(sl, 2),
            tp1=round(tp1, 2),
            tp2=round(tp2, 2),
            tp3=round(tp3, 2),
            confidence=round(confidence, 2),
            reason=reason,
            htf_trend=htf,
            current_price=round(row["close"], 2)
        )

# ============================================================
# STATE MANAGEMENT
# ============================================================
def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"last_signals": {}}

def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def is_new_signal(sig: Signal, last_signals: dict) -> bool:
    key = f"{sig.market}:{sig.symbol}"
    last = last_signals.get(key)
    if not last:
        return True
    # New if different direction or different entry time
    return last["direction"] != sig.direction or last["time"] != sig.time

# ============================================================
# MAIN SCAN
# ============================================================
def scan_all() -> List[Signal]:
    strat = MixedStrategy(PARAMS)
    signals = []
    state = load_state()
    last_signals = state.get("last_signals", {})
    
    print(f"[{datetime.now()}] Starting scan...")
    
    # --- CRYPTO (Kraken) ---
    for name, kpair in KRAKEN_PAIRS.items():
        try:
            print(f"  Scanning {name}...")
            df_4h = fetch_kraken_ohlc(kpair, 240, 365)
            df_1d = fetch_kraken_ohlc(kpair, 1440, 730)
            df_4h = strat.prepare_data(df_4h, df_1d)
            sig = strat.generate_signal(df_4h, name, "CRYPTO")
            if sig and is_new_signal(sig, last_signals):
                signals.append(sig)
                last_signals[f"CRYPTO:{name}"] = {"direction": sig.direction, "time": sig.time}
            time.sleep(0.3)
        except Exception as e:
            print(f"    Error {name}: {e}")
    
    # --- STOCKS (Yahoo Finance) ---
    for ticker, name in YAHOO_STOCKS.items():
        try:
            print(f"  Scanning {ticker}...")
            df_4h = fetch_yahoo_ohlc(ticker, "4h", 365)
            df_1d = fetch_yahoo_ohlc(ticker, "1d", 730)
            if df_4h.empty or len(df_4h) < 250:
                print(f"    Insufficient data")
                continue
            df_4h = strat.prepare_data(df_4h, df_1d)
            sig = strat.generate_signal(df_4h, ticker, "STOCK")
            if sig and is_new_signal(sig, last_signals):
                signals.append(sig)
                last_signals[f"STOCK:{ticker}"] = {"direction": sig.direction, "time": sig.time}
            time.sleep(0.2)
        except Exception as e:
            print(f"    Error {ticker}: {e}")
    
    # Save state
    state["last_signals"] = last_signals
    state["last_run"] = str(datetime.now())
    save_state(state)
    
    # Save signals
    with open(OUTPUT_FILE, "w") as f:
        json.dump([asdict(s) for s in signals], f, indent=2)
    
    return signals

# ============================================================
# FORMAT OUTPUT
# ============================================================
def format_signal(sig: Signal) -> str:
    emoji = "🟢" if sig.direction == "LONG" else "🔴"
    return (
        f"{emoji} **{sig.symbol}** ({sig.market}) — {sig.direction}\n"
        f"   Entry: {sig.entry} | SL: {sig.sl} | TP1: {sig.tp1} | TP2: {sig.tp2} | TP3: {sig.tp3}\n"
        f"   Confidence: {sig.confidence:.0%} | Reason: {sig.reason} | HTF: {sig.htf_trend}\n"
        f"   Time: {sig.time}"
    )

def main():
    signals = scan_all()
    
    if not signals:
        print("No new signals.")
        msg = "📭 **Hourly Scan** — No new signals (sideways filtered or below confidence)."
    else:
        print(f"\n{len(signals)} NEW SIGNALS:")
        for s in signals:
            print(format_signal(s))
        msg = "🔔 **Hourly Scan — New Signals**\n\n" + "\n\n".join(format_signal(s) for s in signals)
    
    # Print for cron log
    print(msg)
    
    # Also save as readable text
    with open("/root/forschung/signals_latest.txt", "w") as f:
        f.write(msg)

if __name__ == "__main__":
    main()