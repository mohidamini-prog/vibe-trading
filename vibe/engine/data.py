"""
Daten-Loader mit Disk-Cache (Parquet) für vibe-trading.
Lädt OHLCV-Tagesdaten für ein ganzes Universum über 3-5 Jahre.
"""
import os
import time
import pandas as pd
import yfinance as yf

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "cache")


def load_ticker(ticker, years=5, refresh=False):
    """Lade OHLCV für einen Ticker (Daily), mit Parquet-Cache."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{ticker.replace('.', '_')}.parquet")
    if os.path.exists(path) and not refresh:
        try:
            return pd.read_parquet(path)
        except Exception:
            pass  # Cache defekt -> neu laden

    df = yf.download(ticker, period=f"{years}y", interval="1d", progress=False, auto_adjust=True)
    if df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    try:
        df.to_parquet(path)
    except Exception:
        pass
    time.sleep(0.2)  # Rate-Limit-Schonung
    return df


def load_universe(tickers, years=5, refresh=False, verbose=True):
    """Lade alle Ticker, überspringe Fehler. Gibt {ticker: df} zurück."""
    data = {}
    failed = []
    for i, t in enumerate(tickers):
        try:
            df = load_ticker(t, years, refresh)
            if len(df) > 250:
                data[t] = df
            else:
                failed.append(t)
        except Exception as e:
            failed.append(t)
        if verbose and (i % 25 == 0 or i == len(tickers) - 1):
            print(f"  {i+1}/{len(tickers)} geladen ({len(data)} ok)")
    if failed:
        print(f"  FEHLGESCHLAGEN ({len(failed)}): {', '.join(failed[:20])}")
    return data
