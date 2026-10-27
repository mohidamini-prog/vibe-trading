"""
Daten-Loader mit Disk-Cache (Parquet) für vibe-trading.
Lädt OHLCV für ein ganzes Universum, auf 1d ODER 4h (via 1h-Resample).
"""
import os
import time
import pandas as pd
import yfinance as yf

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "cache")


def _normalize(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    return df


def load_ticker(ticker, years=5, timeframe="1d", refresh=False):
    """
    Lade OHLCV für einen Ticker.
    timeframe: "1d" (daily) oder "4h" (via 1h resamplen).
    Cache-Datei: {ticker}.parquet (1d) bzw {ticker}_4h.parquet.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    suffix = "_4h" if timeframe == "4h" else ""
    path = os.path.join(CACHE_DIR, f"{ticker.replace('.', '_')}{suffix}.parquet")
    if os.path.exists(path) and not refresh:
        try:
            return pd.read_parquet(path)
        except Exception:
            pass  # Cache defekt -> neu laden

    if timeframe == "4h":
        # 1h laden und auf 4h resamplen. yfinance liefert 1h nur max ~730 Tage.
        years_4h = min(years, 2)  # harte Grenze: 2 Jahre 1h-Verfügbarkeit
        raw = yf.download(ticker, period=f"{years_4h}y", interval="1h",
                          progress=False, auto_adjust=True)
        if raw.empty:
            return pd.DataFrame()
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.droplevel(1)
        df = raw.resample("4h").agg({
            "Open": "first", "High": "max", "Low": "min",
            "Close": "last", "Volume": "sum",
        }).dropna()
    else:
        df = yf.download(ticker, period=f"{years}y", interval="1d",
                         progress=False, auto_adjust=True)
        if df.empty:
            return pd.DataFrame()

    df = _normalize(df)
    try:
        df.to_parquet(path)
    except Exception:
        pass
    time.sleep(0.15)  # Rate-Limit-Schonung
    return df


def load_universe(tickers, years=5, timeframe="1d", refresh=False, verbose=True):
    """Lade alle Ticker, überspringe Fehler. Gibt {ticker: df} zurück."""
    data = {}
    failed = []
    min_rows = 500 if timeframe == "4h" else 250
    for i, t in enumerate(tickers):
        try:
            df = load_ticker(t, years, timeframe, refresh)
            if len(df) > min_rows:
                data[t] = df
            else:
                failed.append(t)
        except Exception:
            failed.append(t)
        if verbose and (i % 25 == 0 or i == len(tickers) - 1):
            print(f"  {i+1}/{len(tickers)} geladen ({len(data)} ok)")
    if failed:
        print(f"  FEHLGESCHLAGEN ({len(failed)}): {', '.join(failed[:20])}")
    return data
