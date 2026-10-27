#!/usr/bin/env python3
"""
Mohid Hourly Scanner v9.1 - Multi-Pattern + Volume + Trend + Fakeout Filter
Scans Kraken Crypto (24/7) and Yahoo Finance Stocks (with market hours focus).
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
import yfinance as yf

# ============================================================
# CONFIG & UNIVERSE
# ============================================================
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
    "WMT": "Walmart",
    "NFLX": "Netflix",
    "AMD": "AMD",
}

STATE_FILE = "/root/forschung/scanner_state_v9.json"
OUTPUT_FILE = "/root/forschung/signals_v9.json"

# ============================================================
# TECHNICAL ANALYSIS & PATTERN RECOGNITION (Python equivalent of Pine)
# ============================================================
def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def find_pivots(high: pd.Series, low: pd.Series, left: int = 5, right: int = 5):
    """Find pivot highs and lows."""
    piv_highs = {}
    piv_lows = {}
    for i in range(left, len(high) - right):
        # Pivot High
        if high.iloc[i] == high.iloc[i-left:i+right+1].max():
            piv_highs[i] = high.iloc[i]
        # Pivot Low
        if low.iloc[i] == low.iloc[i-left:i+right+1].min():
            piv_lows[i] = low.iloc[i]
    return piv_highs, piv_lows

@dataclass
class Signal:
    symbol: str
    market: str
    time: str
    direction: str
    pattern: str
    entry: float
    sl: float
    tp1: float
    tp2: float
    tp3: float
    confidence: float
    volume_ok: bool
    trend_aligned: bool
    current_price: float

class MohidScanner:
    def __init__(self):
        self.vol_min_mult = 1.3
        self.atr_len = 14
        
    def analyze_dataframe(self, df_4h: pd.DataFrame, df_1d: pd.DataFrame, symbol: str, market: str) -> Optional[Signal]:
        if len(df_4h) < 100:
            return None
        
        close = df_4h["close"]
        high = df_4h["high"]
        low = df_4h["low"]
        volume = df_4h["volume"]
        
        # Indicators
        atr_vals = atr(high, low, close, self.atr_len)
        vol_avg = volume.rolling(20).mean()
        vol_ok = volume.iloc[-1] >= self.vol_min_mult * vol_avg.iloc[-1]
        
        # Trend filter (Daily EMA 50 / 200)
        trend_up = False
        trend_down = False
        if not df_1d.empty and len(df_1d) >= 200:
            d_ema50 = ema(df_1d["close"], 50).iloc[-1]
            d_ema200 = ema(df_1d["close"], 200).iloc[-1]
            d_close = df_1d["close"].iloc[-1]
            trend_up = d_ema50 > d_ema200 and d_close > d_ema200
            trend_down = d_ema50 < d_ema200 and d_close < d_ema200
        
        # Pivot analysis for patterns
        p_highs, p_lows = find_pivots(high, low, left=5, right=5)
        if len(p_highs) < 2 or len(p_lows) < 2:
            return None
            
        last_high_idx = list(p_highs.keys())[-1]
        last_high_val = p_highs[last_high_idx]
        last_low_idx = list(p_lows.keys())[-1]
        last_low_val = p_lows[last_low_idx]
        
        curr_close = close.iloc[-1]
        prev_close = close.iloc[-2]
        curr_atr = atr_vals.iloc[-1]
        
        direction = ""
        pattern = ""
        confidence = 0.5
        
        # 1. Breakout Check (Donchian / Resistance Break with Volume)
        res_level = last_high_val
        sup_level = last_low_val
        
        if curr_close > res_level and prev_close <= res_level:
            direction = "LONG"
            pattern = "Resistance Breakout"
            confidence = 0.75 if vol_ok else 0.55
        elif curr_close < sup_level and prev_close >= sup_level:
            direction = "SHORT"
            pattern = "Support Breakdown"
            confidence = 0.75 if vol_ok else 0.55
            
        # 2. Fakeout / Sweep check
        is_sweep = False
        if direction == "LONG" and high.iloc[-1] > res_level and curr_close <= res_level:
            is_sweep = True
            pattern = "Fakeout / Sweep Top"
            direction = "SHORT"
            confidence = 0.65
        elif direction == "SHORT" and low.iloc[-1] < sup_level and curr_close >= sup_level:
            is_sweep = True
            pattern = "Fakeout / Sweep Bottom"
            direction = "LONG"
            confidence = 0.65
            
        if not direction:
            return None
            
        trend_aligned = (direction == "LONG" and trend_up) or (direction == "SHORT" and trend_down)
        
        # Risk management levels
        entry = curr_close
        if direction == "LONG":
            sl = entry - 2.0 * curr_atr
            tp1 = entry + 1.5 * (entry - sl)
            tp2 = entry + 2.5 * (entry - sl)
            tp3 = entry + 4.0 * (entry - sl)
        else:
            sl = entry + 2.0 * curr_atr
            tp1 = entry - 1.5 * (sl - entry)
            tp2 = entry - 2.5 * (sl - entry)
            tp3 = entry - 4.0 * (sl - entry)
            
        return Signal(
            symbol=symbol,
            market=market,
            time=str(df_4h.index[-1]),
            direction=direction,
            pattern=pattern,
            entry=round(entry, 2),
            sl=round(sl, 2),
            tp1=round(tp1, 2),
            tp2=round(tp2, 2),
            tp3=round(tp3, 2),
            confidence=round(confidence, 2),
            volume_ok=bool(vol_ok),
            trend_aligned=bool(trend_aligned),
            current_price=round(curr_close, 2)
        )

# ============================================================
# FETCHERS
# ============================================================
def fetch_kraken(pair: str, interval: int = 240) -> pd.DataFrame:
    url = "https://api.kraken.com/0/public/OHLC"
    since = int((datetime.now() - timedelta(days=365)).timestamp())
    resp = requests.get(url, params={"pair": pair, "interval": interval, "since": since}, timeout=30)
    data = resp.json()
    if data.get("error"):
        return pd.DataFrame()
    key = [k for k in data["result"].keys() if k != "last"][0]
    df = pd.DataFrame(data["result"][key], columns=["time", "open", "high", "low", "close", "vwap", "volume", "count"])
    df["time"] = pd.to_datetime(df["time"], unit="s")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    return df.set_index("time").sort_index()

def fetch_yahoo(ticker: str, interval: str = "4h") -> pd.DataFrame:
    if interval == "4h":
        df = yf.download(ticker, period="365d", interval="1h", progress=False, auto_adjust=True)
        if df.empty:
            return pd.DataFrame()
        df = df.resample("4H").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}).dropna()
        df.columns = ["open", "high", "low", "close", "volume"]
    else:
        df = yf.download(ticker, period="730d", interval="1d", progress=False, auto_adjust=True)
        if df.empty:
            return pd.DataFrame()
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.columns = ["open", "high", "low", "close", "volume"]
    return df.sort_index()

# ============================================================
# MAIN SCANNER ROUTINE
# ============================================================
def run_scan():
    scanner = MohidScanner()
    signals = []
    
    print(f"[{datetime.now()}] Mohid v9.1 Engine Running...")
    
    # Check if stock market hours or crypto
    hour_utc = datetime.utcnow().hour
    is_stock_session = 7 <= hour_utc <= 21  # Xetra / Wall Street window
    
    # 1. Kraken Crypto (Always scanned or prioritized)
    for name, kpair in KRAKEN_PAIRS.items():
        try:
            df_4h = fetch_kraken(kpair, 240)
            df_1d = fetch_kraken(kpair, 1440)
            sig = scanner.analyze_dataframe(df_4h, df_1d, name, "CRYPTO")
            if sig:
                signals.append(sig)
            time.sleep(0.3)
        except Exception as e:
            print(f"Kraken error {name}: {e}")
            
    # 2. Yahoo Stocks (Scanned during active hours)
    if is_stock_session:
        for ticker, name in YAHOO_STOCKS.items():
            try:
                df_4h = fetch_yahoo(ticker, "4h")
                df_1d = fetch_yahoo(ticker, "1d")
                sig = scanner.analyze_dataframe(df_4h, df_1d, ticker, "STOCK")
                if sig:
                    signals.append(sig)
                time.sleep(0.2)
            except Exception as e:
                print(f"Yahoo error {ticker}: {e}")
                
    # Save output
    with open(OUTPUT_FILE, "w") as f:
        json.dump([asdict(s) for s in signals], f, indent=2)
        
    formatted_msg = format_signals(signals)
    print(formatted_msg)
    with open("/root/forschung/signals_latest_v9.txt", "w") as f:
        f.write(formatted_msg)

def format_signals(signals: List[Signal]) -> str:
    if not signals:
        return "📭 **Mohid v9.1 Scan:** Keine aktuellen Muster / Breakouts (Märkte gefiltert)."
    
    out = "🚀 **Mohid v9.1 — Live Signale & Muster**\n\n"
    for s in signals:
        emoji = "🟢" if s.direction == "LONG" else "🔴"
        vol_badge = "✅ Vol OK" if s.volume_ok else "⚠️ Vol niedrig"
        trend_badge = "📈 Trend OK" if s.trend_aligned else "⚖️ Gegen-Trend"
        out += (
            f"{emoji} **{s.symbol}** ({s.market}) — **{s.direction}**\n"
            f"   Muster: *{s.pattern}*\n"
            f"   Entry: {s.entry} | SL: {s.sl}\n"
            f"   TP1: {s.tp1} | TP2: {s.tp2} | TP3: {s.tp3}\n"
            f"   Status: {vol_badge} | {trend_badge} | Conf: {s.confidence:.0%}\n\n"
        )
    return out

if __name__ == "__main__":
    run_scan()