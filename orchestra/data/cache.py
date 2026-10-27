"""
SQLite-Cache für OHLCV-Kerzen (candles.db, max ~10MB) + Zustand (orchestra_state.db).

Datenarm: speichert nur close, volume, ema9, ema21, z_score — nicht alle Roh-Kerzen.
ARM-tauglich, kein pandas im Hot-Path.
"""
import sqlite3
from contextlib import contextmanager

from orchestra.config import paths


@contextmanager
def _conn(db_path):
    paths.ensure_dirs()
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------- CANDLES ----------
def init_candles():
    with _conn(paths.DB_CANDLES) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS candles (
            symbol TEXT, ts INTEGER, timeframe TEXT,
            close REAL, volume REAL,
            ema9 REAL, ema21 REAL, z_score REAL,
            PRIMARY KEY (symbol, timeframe, ts)
        )""")


def upsert_candles(rows):
    """rows: list of (symbol, ts, timeframe, close, volume, ema9, ema21, z_score)."""
    init_candles()
    with _conn(paths.DB_CANDLES) as c:
        c.executemany(
            """INSERT OR REPLACE INTO candles
               (symbol, ts, timeframe, close, volume, ema9, ema21, z_score)
               VALUES (?,?,?,?,?,?,?,?)""", rows)


def get_candles(symbol, timeframe="5m", limit=100):
    init_candles()
    with _conn(paths.DB_CANDLES) as c:
        cur = c.execute(
            """SELECT ts, close, volume, ema9, ema21, z_score FROM candles
               WHERE symbol=? AND timeframe=? ORDER BY ts DESC LIMIT ?""",
            (symbol, timeframe, limit))
        return list(reversed(cur.fetchall()))


def candle_count():
    init_candles()
    with _conn(paths.DB_CANDLES) as c:
        return c.execute("SELECT COUNT(*) FROM candles").fetchone()[0]


# ---------- STATE ----------
def init_state():
    with _conn(paths.DB_STATE) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS state (
            key TEXT PRIMARY KEY, value TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")


def set_state(key, value):
    import json
    init_state()
    with _conn(paths.DB_STATE) as c:
        c.execute("INSERT OR REPLACE INTO state (key, value) VALUES (?,?)",
                  (key, json.dumps(value)))


def get_state(key, default=None):
    import json
    init_state()
    with _conn(paths.DB_STATE) as c:
        cur = c.execute("SELECT value FROM state WHERE key=?", (key,))
        row = cur.fetchone()
        return json.loads(row[0]) if row else default


if __name__ == "__main__":
    init_candles(); init_state()
    print("DBs initialisiert.")
    print("Candles:", candle_count())
