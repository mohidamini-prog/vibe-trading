"""
Backtest-Engine für das Orchestra — 5 Jahre, US+DE Börse, 4h+1D.

Testet alle Agenten-Strategie-Kombinationen (Modelle × Indikatoren × Agenten)
und wertet Trefferquoten aus. Nutzt yfinance (4h max 2y wegen yfinance-Limit,
1D voll 5y).
"""
import json
import sys
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd
import yfinance as yf

# Universum: US (AAPL, MSFT, NVDA, META, GOOGL, AMZN, TSLA) + DE (SAP.DE, SIE.DE, ALV.DE, BMW.DE, DTE.DE)
US_SYMBOLS = ["AAPL", "MSFT", "NVDA", "META", "GOOGL", "AMZN", "TSLA"]
DE_SYMBOLS = ["SAP.DE", "SIE.DE", "ALV.DE", "BMW.DE", "DTE.DE", "MBG.DE", "VOW3.DE"]
ALL_SYMBOLS = US_SYMBOLS + DE_SYMBOLS

OUT_DIR = Path(__file__).resolve().parent.parent / "backtests"
OUT_DIR.mkdir(exist_ok=True)


def fetch_data(symbol, interval, period):
    """Daten laden (mit Auto-Adjust)."""
    try:
        df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True)
        if df is None or len(df) == 0:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        return df
    except Exception:
        return None


def add_indicators(df):
    """Indikatoren berechnen: EMA, RSI, ATR, ADX, Bollinger, z-score."""
    c = df["Close"]
    df["EMA9"] = c.ewm(span=9, adjust=False).mean()
    df["EMA20"] = c.ewm(span=20, adjust=False).mean()
    df["EMA50"] = c.ewm(span=50, adjust=False).mean()
    df["EMA200"] = c.ewm(span=200, adjust=False).mean()
    # RSI 14
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))
    # ATR 14
    hl = df["High"] - df["Low"]
    hc = (df["High"] - c.shift()).abs()
    lc = (df["Low"] - c.shift()).abs()
    df["ATR"] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()
    # Bollinger 20
    df["BB_Mid"] = c.rolling(20).mean()
    df["BB_Std"] = c.rolling(20).std()
    df["BB_Up"] = df["BB_Mid"] + 2 * df["BB_Std"]
    df["BB_Low"] = df["BB_Mid"] - 2 * df["BB_Std"]
    # z-score 20
    df["Z"] = (c - df["BB_Mid"]) / df["BB_Std"]
    # ADX 14 (vereinfacht)
    up = c.diff()
    plus_dm = up.where(up > 0, 0)
    minus_dm = (-up).where(up < 0, 0)
    atr14 = df["ATR"].replace(0, np.nan)
    df["+DI"] = 100 * plus_dm.rolling(14).mean() / atr14
    df["-DI"] = 100 * minus_dm.rolling(14).mean() / atr14
    dx = 100 * (df["+DI"] - df["-DI"]).abs() / (df["+DI"] + df["-DI"]).replace(0, np.nan)
    df["ADX"] = dx.rolling(14).mean()
    # Returns
    df["Ret"] = c.pct_change()
    df["Vol"] = df["Ret"].rolling(20).std()
    return df


def strategy_signals(df, model):
    """Signal für ein Modell (Strategie) berechnen. a ∈ {+1, -1, 0}."""
    c = df["Close"]
    if model == "trend_ema":
        # Reiner Trend: EMA20>EMA50>EMA200 + Preis>EMA20 -> long
        cond = (df["EMA20"] > df["EMA50"]) & (df["EMA50"] > df["EMA200"]) & (c > df["EMA20"])
        return np.where(cond, 1, 0)
    elif model == "momentum_rsi":
        # Momentum: EMA50>EMA200 + RSI 45-75
        cond = (df["EMA50"] > df["EMA200"]) & (df["RSI"] > 45) & (df["RSI"] < 75)
        return np.where(cond, 1, 0)
    elif model == "meanrev_bb":
        # MeanRev: Preis < BB_Low oder RSI<35 -> long (Dip-Buy)
        cond = (c <= df["BB_Low"]) | (df["RSI"] < 35)
        return np.where(cond, 1, 0)
    elif model == "vola_atr":
        # Vola/Risk: ATR-Spike -> short/ausstieg
        cond = df["ATR"] > df["ATR"].rolling(50).median() * 1.5
        return np.where(cond, -1, 0)
    elif model == "zscore":
        # z-score: |z|>2 -> meanrev
        cond = df["Z"] < -2.0
        return np.where(cond, 1, 0)
    elif model == "adx_trend":
        # ADX>25 + EMA50>EMA200 (starker Trend)
        cond = (df["ADX"] > 25) & (df["EMA50"] > df["EMA200"])
        return np.where(cond, 1, 0)
    else:
        return np.zeros(len(df))


def backtest(df, signal):
    """Backtest: Signal -> Returns, Trefferquote, Trades."""
    if df is None or len(df) < 50:
        return None
    signal = pd.Series(signal, index=df.index).fillna(0)
    # Positionswechsel zählen
    pos = signal.shift(1).fillna(0)
    ret = df["Ret"].fillna(0) * pos
    # Trades: Signalwechsel
    changes = signal.diff().fillna(0)
    n_trades = int((changes.abs() > 0).sum())
    # Treffer: Tage mit Signal & positivem Return
    active = pos != 0
    if active.sum() == 0:
        return {"n_trades": 0, "hit_rate": 0, "total_ret": 0, "max_dd": 0, "sharpe": 0}
    wins = (ret[active] > 0).sum()
    hit_rate = wins / active.sum()
    cum = (1 + ret).cumprod()
    total_ret = cum.iloc[-1] - 1
    # Max Drawdown
    peak = cum.cummax()
    dd = (cum / peak - 1).min()
    # Sharpe (annualisiert, sqrt(n) mit 252 Tagen)
    if ret.std() > 0:
        sharpe = ret.mean() / ret.std() * np.sqrt(252)
    else:
        sharpe = 0
    return {
        "n_trades": n_trades,
        "hit_rate": round(float(hit_rate), 4),
        "total_ret": round(float(total_ret), 4),
        "max_dd": round(float(dd), 4),
        "sharpe": round(float(sharpe), 2),
        "n_bars": len(df),
    }


def run_all():
    """Alle Kombinationen testen (Modelle × Intervalle × Symbole)."""
    models = ["trend_ema", "momentum_rsi", "meanrev_bb", "vola_atr", "zscore", "adx_trend"]
    intervals = [("1d", "5y"), ("4h", "2y")]  # 1d voll 5y, 4h nur 2y (yfinance-Limit)
    results = []
    total = len(models) * len(intervals) * len(ALL_SYMBOLS)
    done = 0
    print(f"Backtest: {len(models)} Modelle × {len(intervals)} Intervalle × {len(ALL_SYMBOLS)} Symbole = {total} Läufe")
    for interval, period in intervals:
        for symbol in ALL_SYMBOLS:
            df = fetch_data(symbol, interval, period)
            if df is None:
                continue
            df = add_indicators(df)
            for model in models:
                signal = strategy_signals(df, model)
                res = backtest(df, signal)
                if res:
                    res.update({"symbol": symbol, "interval": interval, "model": model, "period": period})
                    results.append(res)
                done += 1
                if done % 20 == 0:
                    print(f"  {done}/{total} ...")
    # Ergebnisse speichern
    out_file = OUT_DIR / "backtest_results.json"
    out_file.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"Fertig: {len(results)} Ergebnisse -> {out_file}")
    return results


if __name__ == "__main__":
    run_all()
