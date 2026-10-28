"""
Layer 0 — Daten-Layer.

EINZIGE Quelle für OHLCV-Daten. Lädt echte High/Low/Open/Close/Volume für
4h und 1d von yfinance, cacht lokal (Parquet) und stellt allen Layern die
vollständigen Kerzen zur Verfügung — kein Approximation von High/Low mehr.
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd

from orchestra.config import paths

CACHE_DIR = paths.CACHE_DIR / "ohlcv"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_path(symbol, timeframe):
    return CACHE_DIR / f"{symbol.replace('.', '_')}_{timeframe}.parquet"


def load_ohlcv(symbol, timeframe="1d", period=None, force=False):
    """
    Lädt OHLCV für ein Symbol + Timeframe mit Cache.
    yfinance-Limits: 4h max 2y, 1d max ~5y (wir nutzen 2y für beide).
    Returns: pd.DataFrame mit [open, high, low, close, volume] oder None.
    """
    cp = _cache_path(symbol, timeframe)
    # Cache frisch (< 6h alt) und nicht erzwungen -> nutzen
    if not force and cp.exists() and (datetime.now() - datetime.fromtimestamp(cp.stat().st_mtime)) < timedelta(hours=6):
        try:
            df = pd.read_parquet(cp)
            if len(df) > 50:
                return df
        except Exception:
            pass  # Cache korrupt -> neu laden

    try:
        import yfinance as yf
        period = period or ("2y" if timeframe == "4h" else "5y")
        raw = yf.download(symbol, period=period, interval=timeframe,
                          progress=False, auto_adjust=True)
        if raw is None or len(raw) == 0:
            return None
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.droplevel(1)
        df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.columns = ["open", "high", "low", "close", "volume"]
        df = df.dropna()
        df.to_parquet(cp)
        return df
    except Exception as e:
        # Fallback auf alten Cache
        if cp.exists():
            try:
                return pd.read_parquet(cp)
            except Exception:
                pass
        print(f"  [Daten] Fehler {symbol} {timeframe}: {e}")
        return None


def load_universe(symbols, timeframe="1d"):
    """Universum laden -> {symbol: df}."""
    out = {}
    for s in symbols:
        df = load_ohlcv(s, timeframe)
        if df is not None and len(df) > 60:
            out[s] = df
    return out


def load_batch(symbols, timeframe="1d", period=None, force=False):
    """Lädt ein ganzes Universum EFFIZIENT per Batch-Download (yfinance parallel).

    Deutlich schneller als Einzel-Downloads (294 Symbole in ~60s statt ~29min).
    Schreibt jede erfolgreiche Kerzenreihe in den Cache (load_ohlcv liest ihn).
    Returns: {symbol: df} für alle erfolgreich geladenen Symbole.
    """
    import yfinance as yf
    import pandas as pd

    period = period or ("2y" if timeframe == "4h" else "5y")
    out = {}
    # Nur Symbole laden, deren Cache älter als 6h ist
    to_fetch = []
    for s in symbols:
        cp = _cache_path(s, timeframe)
        if force or not cp.exists() or (datetime.now() - datetime.fromtimestamp(cp.stat().st_mtime)) >= timedelta(hours=6):
            to_fetch.append(s)
    # Alle anderen aus Cache lesen
    for s in symbols:
        if s not in to_fetch:
            try:
                df = pd.read_parquet(_cache_path(s, timeframe))
                if len(df) > 50:
                    out[s] = df
            except Exception:
                to_fetch.append(s)

    if not to_fetch:
        return out

    try:
        raw = yf.download(to_fetch, period=period, interval=timeframe,
                          group_by="ticker", threads=True, progress=False,
                          auto_adjust=True)
    except Exception as e:
        print(f"  [Batch] Fehler {timeframe}: {e}")
        return out

    if raw is None or len(raw) == 0:
        return out

    for s in to_fetch:
        try:
            if isinstance(raw.columns, pd.MultiIndex):
                if s not in raw.columns.get_level_values(0):
                    continue
                sub = raw[s]
            else:
                sub = raw
            sub = sub.dropna()
            if len(sub) < 50:
                continue
            sub = sub[["Open", "High", "Low", "Close", "Volume"]].copy()
            sub.columns = ["open", "high", "low", "close", "volume"]
            sub.to_parquet(_cache_path(s, timeframe))
            out[s] = sub
        except Exception as e:
            print(f"  [Batch] {s}: {e}")
    return out


if __name__ == "__main__":
    df = load_ohlcv("AAPL", "1d")
    print(f"AAPL 1d: {len(df)} Kerzen, letzte 5:")
    print(df.tail())
