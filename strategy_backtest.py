#!/usr/bin/env python3
"""
Kraken 4h + 1D Mixed Strategy Backtest
- Trend Following (EMA Stack, MACD, Supertrend)
- Breakout (Donchian, BB Expansion, Volume)
- Mean Reversion (RSI extremes, BB touches) - ONLY in trend direction
- SIDEWAYS FILTER: ADX > 25, BB Width > pctl, Chop Index < threshold
- Hourly scan on 4h candles, daily HTF filter
"""

import json
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import requests
import time

# ============================================================
# KRAKEN DATA FETCHER
# ============================================================
KRAKEN_OHLC_URL = "https://api.kraken.com/0/public/OHLC"

# Major liquid pairs on Kraken (using Kraken's internal names)
PAIRS = {
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

TIMEFRAMES = {
    "4h": 240,    # 4-hour in minutes
    "1d": 1440,   # 1-day in minutes
}

def fetch_ohlc(pair: str, interval: int = 240, since: Optional[int] = None) -> pd.DataFrame:
    """Fetch OHLC data from Kraken public API."""
    params = {"pair": pair, "interval": interval}
    if since:
        params["since"] = since
    
    resp = requests.get(KRAKEN_OHLC_URL, params=params, timeout=30)
    data = resp.json()
    
    if data.get("error"):
        raise ValueError(f"Kraken error: {data['error']}")
    
    # Result key is the pair name
    key = [k for k in data["result"].keys() if k != "last"][0]
    candles = data["result"][key]
    
    df = pd.DataFrame(candles, columns=["time", "open", "high", "low", "close", "vwap", "volume", "count"])
    df["time"] = pd.to_datetime(df["time"], unit="s")
    for col in ["open", "high", "low", "close", "vwap", "volume"]:
        df[col] = df[col].astype(float)
    df = df.set_index("time").sort_index()
    return df[["open", "high", "low", "close", "volume", "vwap"]]

def fetch_all_pairs(interval: int = 240, days_back: int = 365) -> Dict[str, pd.DataFrame]:
    """Fetch data for all major pairs."""
    since = int((datetime.now() - timedelta(days=days_back)).timestamp())
    data = {}
    for name, kraken_pair in PAIRS.items():
        try:
            print(f"Fetching {name} ({kraken_pair})...")
            df = fetch_ohlc(kraken_pair, interval, since)
            data[name] = df
            time.sleep(0.5)  # Rate limit
        except Exception as e:
            print(f"  Failed: {e}")
    return data

# ============================================================
# INDICATORS
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
    """Average Directional Index - trend strength."""
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
    """Choppiness Index - 0-100, >61.8 = choppy, <38.2 = trending."""
    atr_vals = atr(high, low, close, 1)
    high_n = high.rolling(period).max()
    low_n = low.rolling(period).min()
    ci = 100 * np.log10(atr_vals.rolling(period).sum() / (high_n - low_n)) / np.log10(period)
    return ci

def supertrend(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 10, multiplier: float = 3.0) -> Tuple[pd.Series, pd.Series]:
    """Supertrend indicator - returns (trend_line, direction: 1=up, -1=down)."""
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
# STRATEGY CLASS
# ============================================================
@dataclass
class Signal:
    pair: str
    time: pd.Timestamp
    direction: str  # "LONG" or "SHORT"
    entry: float
    sl: float
    tp1: float
    tp2: float
    tp3: float
    confidence: float  # 0-1
    reason: str
    htf_trend: str  # "UP", "DOWN", "NEUTRAL"

class MixedStrategy:
    def __init__(self):
        # Parameters optimized for 4h timeframe
        self.ema_fast = 9
        self.ema_med = 21
        self.ema_slow = 50
        self.ema_trend = 200
        
        self.rsi_period = 14
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        self.rsi_chop_min = 40
        self.rsi_chop_max = 60
        
        self.bb_period = 20
        self.bb_std = 2.0
        self.bb_width_pctl = 0.3  # Bottom 30% = chop
        
        self.adx_period = 14
        self.adx_threshold = 25
        
        self.chop_period = 14
        self.chop_threshold = 55  # Above = choppy
        
        self.donchian_period = 20
        
        self.st_period = 10
        self.st_mult = 3.0
        
        self.vol_lookback = 20
        self.vol_mult = 1.3
        
        self.htf_ema = 50  # 1D EMA for trend filter
        
        self.risk_per_trade = 0.02  # 2% risk
        self.rr_ratios = [1.5, 2.5, 4.0]  # TP levels
        
    def prepare_data(self, df_4h: pd.DataFrame, df_1d: pd.DataFrame) -> pd.DataFrame:
        """Calculate all indicators on 4h data, merge 1D trend."""
        df = df_4h.copy()
        
        # EMAs
        df["ema_fast"] = ema(df["close"], self.ema_fast)
        df["ema_med"] = ema(df["close"], self.ema_med)
        df["ema_slow"] = ema(df["close"], self.ema_slow)
        df["ema_trend"] = ema(df["close"], self.ema_trend)
        
        # MACD
        df["macd"], df["macd_signal"], df["macd_hist"] = macd(df["close"])
        
        # RSI
        df["rsi"] = rsi(df["close"], self.rsi_period)
        
        # Bollinger Bands
        df["bb_upper"], df["bb_mid"], df["bb_lower"] = bollinger_bands(df["close"], self.bb_period, self.bb_std)
        df["bb_width"] = bb_width(df["bb_upper"], df["bb_lower"], df["bb_mid"])
        df["bb_width_pctl"] = df["bb_width"].rolling(100).rank(pct=True)
        
        # ADX
        df["adx"] = adx(df["high"], df["low"], df["close"], self.adx_period)
        
        # Chop Index
        df["chop"] = chop_index(df["high"], df["low"], df["close"], self.chop_period)
        
        # Supertrend
        df["st_line"], df["st_dir"] = supertrend(df["high"], df["low"], df["close"], self.st_period, self.st_mult)
        
        # Donchian
        df["dc_upper"], df["dc_lower"] = donchian(df["high"], df["low"], self.donchian_period)
        
        # Volume
        df["vol_avg"] = df["volume"].rolling(self.vol_lookback).mean()
        df["vol_ratio"] = df["volume"] / df["vol_avg"]
        
        # HTF Trend (1D EMA50)
        if not df_1d.empty:
            df_1d["htf_ema"] = ema(df_1d["close"], self.htf_ema)
            df_1d["htf_trend"] = np.where(df_1d["close"] > df_1d["htf_ema"], "UP", "DOWN")
            # Resample to 4h and forward fill
            htf = df_1d[["htf_trend"]].resample("4H").ffill()
            df = df.join(htf, how="left")
            df["htf_trend"] = df["htf_trend"].ffill()
        else:
            df["htf_trend"] = "NEUTRAL"
        
        # Trend alignment signals
        df["ema_stack_up"] = (df["ema_fast"] > df["ema_med"]) & (df["ema_med"] > df["ema_slow"]) & (df["ema_slow"] > df["ema_trend"])
        df["ema_stack_down"] = (df["ema_fast"] < df["ema_med"]) & (df["ema_med"] < df["ema_slow"]) & (df["ema_slow"] < df["ema_trend"])
        
        df["macd_bull"] = (df["macd"] > df["macd_signal"]) & (df["macd_hist"] > 0)
        df["macd_bear"] = (df["macd"] < df["macd_signal"]) & (df["macd_hist"] < 0)
        
        # Sideways filter
        df["is_choppy"] = (df["adx"] < self.adx_threshold) | (df["chop"] > self.chop_threshold) | (df["bb_width_pctl"] < self.bb_width_pctl)
        df["rsi_chop"] = (df["rsi"] > self.rsi_chop_min) & (df["rsi"] < self.rsi_chop_max)
        
        return df
    
    def generate_signal(self, df: pd.DataFrame, pair: str, idx: int) -> Optional[Signal]:
        """Generate signal at index idx (current candle)."""
        if idx < max(self.ema_trend, self.bb_period, self.adx_period, self.chop_period, self.st_period) + 10:
            return None
        
        row = df.iloc[idx]
        prev = df.iloc[idx-1]
        
        # SIDEWAYS FILTER - hard block
        if row["is_choppy"] or row["rsi_chop"]:
            return None
        
        htf = row["htf_trend"]
        atr_val = atr(df["high"], df["low"], df["close"], 14).iloc[idx]
        atr_val = float(atr_val) if not np.isnan(atr_val) else row["close"] * 0.02
        
        # LONG CONDITIONS
        long_conditions = []
        
        # 1. Trend Following: EMA stack + MACD + Supertrend up + HTF up
        if (row["ema_stack_up"] and row["macd_bull"] and row["st_dir"] == 1 and htf == "UP"):
            long_conditions.append("TrendFollow")
        
        # 2. Breakout: Close above Donchian upper + volume + HTF up
        if (row["close"] > prev["dc_upper"] and row["vol_ratio"] > self.vol_mult and htf == "UP"):
            long_conditions.append("Breakout")
        
        # 3. Pullback in uptrend: RSI oversold bounce + price at EMA/Supertrend + HTF up
        if (prev["rsi"] < self.rsi_oversold and row["rsi"] > prev["rsi"] and 
            row["close"] > row["st_line"] and htf == "UP"):
            long_conditions.append("Pullback")
        
        # SHORT CONDITIONS
        short_conditions = []
        
        if (row["ema_stack_down"] and row["macd_bear"] and row["st_dir"] == -1 and htf == "DOWN"):
            short_conditions.append("TrendFollow")
        
        if (row["close"] < prev["dc_lower"] and row["vol_ratio"] > self.vol_mult and htf == "DOWN"):
            short_conditions.append("Breakout")
        
        if (prev["rsi"] > self.rsi_overbought and row["rsi"] < prev["rsi"] and 
            row["close"] < row["st_line"] and htf == "DOWN"):
            short_conditions.append("Pullback")
        
        # Determine signal
        if long_conditions:
            direction = "LONG"
            reason = "+".join(long_conditions)
            entry = row["close"]
            sl = entry - 2.0 * atr_val
            confidence = min(0.9, 0.5 + 0.15 * len(long_conditions))
            
        elif short_conditions:
            direction = "SHORT"
            reason = "+".join(short_conditions)
            entry = row["close"]
            sl = entry + 2.0 * atr_val
            confidence = min(0.9, 0.5 + 0.15 * len(short_conditions))
            
        else:
            return None
        
        # Risk/Reward targets
        risk = abs(entry - sl)
        tp1 = entry + risk * self.rr_ratios[0] if direction == "LONG" else entry - risk * self.rr_ratios[0]
        tp2 = entry + risk * self.rr_ratios[1] if direction == "LONG" else entry - risk * self.rr_ratios[1]
        tp3 = entry + risk * self.rr_ratios[2] if direction == "LONG" else entry - risk * self.rr_ratios[2]
        
        return Signal(
            pair=pair,
            time=row.name,
            direction=direction,
            entry=round(entry, 2),
            sl=round(sl, 2),
            tp1=round(tp1, 2),
            tp2=round(tp2, 2),
            tp3=round(tp3, 2),
            confidence=round(confidence, 2),
            reason=reason,
            htf_trend=htf
        )
    
    def backtest_pair(self, df_4h: pd.DataFrame, df_1d: pd.DataFrame, pair: str) -> List[Dict]:
        """Run backtest on a single pair."""
        df = self.prepare_data(df_4h, df_1d)
        signals = []
        trades = []
        
        for i in range(len(df)):
            sig = self.generate_signal(df, pair, i)
            if sig:
                signals.append(sig)
                
                # Simulate trade forward
                entry_idx = i
                entry_price = sig.entry
                sl = sig.sl
                tps = [sig.tp1, sig.tp2, sig.tp3]
                direction = sig.direction
                
                # Look forward up to 30 candles (5 days)
                for j in range(i+1, min(i+31, len(df))):
                    future = df.iloc[j]
                    hit = False
                    
                    if direction == "LONG":
                        if future["low"] <= sl:
                            trades.append({"pair": pair, "entry": entry_price, "exit": sl, "result": -1, "bars": j-entry_idx, "type": "SL"})
                            hit = True
                            break
                        for k, tp in enumerate(tps):
                            if future["high"] >= tp and k == 0:
                                trades.append({"pair": pair, "entry": entry_price, "exit": tp, "result": self.rr_ratios[k], "bars": j-entry_idx, "type": f"TP{k+1}"})
                                hit = True
                                break
                            elif future["high"] >= tp and k > 0:
                                # Partial TP logic - for simplicity, take first hit
                                pass
                    else:
                        if future["high"] >= sl:
                            trades.append({"pair": pair, "entry": entry_price, "exit": sl, "result": -1, "bars": j-entry_idx, "type": "SL"})
                            hit = True
                            break
                        for k, tp in enumerate(tps):
                            if future["low"] <= tp and k == 0:
                                trades.append({"pair": pair, "entry": entry_price, "exit": tp, "result": self.rr_ratios[k], "bars": j-entry_idx, "type": f"TP{k+1}"})
                                hit = True
                                break
                
                if not hit:
                    # Exit at close of 30th candle
                    exit_price = df.iloc[min(i+30, len(df)-1)]["close"]
                    pnl = (exit_price - entry_price) / abs(entry_price - sl) if direction == "LONG" else (entry_price - exit_price) / abs(entry_price - sl)
                    trades.append({"pair": pair, "entry": entry_price, "exit": exit_price, "result": round(pnl, 2), "bars": 30, "type": "TIME"})
        
        return trades
    
    def run_backtest(self, data_4h: Dict, data_1d: Dict) -> pd.DataFrame:
        """Run backtest on all pairs."""
        all_trades = []
        for pair, df_4h in data_4h.items():
            df_1d = data_1d.get(pair, pd.DataFrame())
            trades = self.backtest_pair(df_4h, df_1d, pair)
            all_trades.extend(trades)
            print(f"{pair}: {len(trades)} trades")
        
        return pd.DataFrame(all_trades)

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("FETCHING DATA...")
    print("=" * 60)
    
    data_4h = fetch_all_pairs(240, days_back=365)
    data_1d = fetch_all_pairs(1440, days_back=730)
    
    print("\n" + "=" * 60)
    print("RUNNING BACKTEST...")
    print("=" * 60)
    
    strat = MixedStrategy()
    trades_df = strat.run_backtest(data_4h, data_1d)
    
    if len(trades_df) == 0:
        print("No trades generated!")
        exit()
    
    # Statistics
    trades_df["win"] = trades_df["result"] > 0
    total = len(trades_df)
    wins = trades_df["win"].sum()
    winrate = wins / total * 100
    
    avg_win = trades_df[trades_df["win"]]["result"].mean()
    avg_loss = trades_df[~trades_df["win"]]["result"].mean()
    expectancy = (winrate/100 * avg_win) + ((1-winrate/100) * avg_loss)
    
    print("\n" + "=" * 60)
    print("BACKTEST RESULTS")
    print("=" * 60)
    print(f"Total Trades: {total}")
    print(f"Win Rate: {winrate:.1f}%")
    print(f"Avg Win (R): {avg_win:.2f}")
    print(f"Avg Loss (R): {avg_loss:.2f}")
    print(f"Expectancy (R): {expectancy:.2f}")
    print(f"Profit Factor: {abs(trades_df[trades_df['win']]['result'].sum() / trades_df[~trades_df['win']]['result'].sum()):.2f}")
    
    print("\nBy Pair:")
    for pair in trades_df["pair"].unique():
        sub = trades_df[trades_df["pair"] == pair]
        wr = sub["win"].mean() * 100
        exp = (sub[sub["win"]]["result"].mean() * sub["win"].mean() + 
               sub[~sub["win"]]["result"].mean() * (1-sub["win"].mean()))
        print(f"  {pair}: {len(sub)} trades, WR={wr:.1f}%, Exp={exp:.2f}R")
    
    print("\nBy Type:")
    for typ in trades_df["type"].unique():
        sub = trades_df[trades_df["type"] == typ]
        print(f"  {typ}: {len(sub)}")
    
    # Save trades
    trades_df.to_csv("/root/forschung/backtest_results.csv", index=False)
    print("\nSaved to /root/forschung/backtest_results.csv")