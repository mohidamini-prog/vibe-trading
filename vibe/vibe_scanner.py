#!/usr/bin/env python3
"""
Vibe Live-Scanner: scannt das Universum (US-TOP100 + DAX-40) auf 1D
mit den verfeinerten Momentum/Noise-Setups.

Nutzung: python vibe_scanner.py [--all|--top] [--days N]
- --top: nur die Top-5-Setups (default)
- --all: alle 14 Setups
- --days N: Signale der letzten N Tage ausgeben (default 2)

Ausgabe: JSON + lesbarer Text (für Telegram/Cron).
"""
import os
import sys
import json
import time
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(BASE)
sys.path.insert(0, REPO)

import pandas as pd
from engine import backtest as bt
from engine import data as data_loader
from universe.universes import US_TOP100, DAX_40

# Beste Setups aus der Per-Markt-Optimierung
TOP_SETUPS = [
    "meanrev_oversold",
    "meanrev_filtered",
    "momentum_obv",
    "momentum_breakout_filtered",
    "breakout_pullback_combo",
    "supertrend_rsi",
    "momentum_williams",
]

STATE_FILE = os.path.join(BASE, "..", "scanner_state.json")
OUTPUT_JSON = os.path.join(BASE, "..", "signals_latest.json")
OUTPUT_TXT = os.path.join(BASE, "..", "signals_latest.txt")


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"seen": {}}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def is_new(key, sig_date, state):
    """Neues Signal nur, wenn (Symbol+Setup+Datum) noch nicht gesehen wurde."""
    seen = state["seen"]
    k = f"{key}|{sig_date}"
    if k in seen:
        return False
    seen[k] = str(datetime.now())
    # Aufräumen: nur letzte 500 Einträge behalten
    if len(seen) > 500:
        for old in list(seen)[:100]:
            seen.pop(old, None)
    return True


def scan_symbol(ticker, market, setups, days_back=2, state=None):
    """Scannt einen Ticker auf 1D mit allen Setups, liefert Signale der letzten days_back Tage."""
    try:
        df = data_loader.load_ticker(ticker, years=5, timeframe="1d")
        if df.empty or len(df) < 300:
            return []
        prep = bt.prepare(df)
        signals = []
        cutoff = prep.index[-1] - pd.Timedelta(days=days_back)
        for name in setups:
            fn = bt.SETUPS[name]
            sig_mask = fn(prep).fillna(False)
            # Nur echte Signale in den letzten days_back Tagen
            recent = sig_mask[sig_mask & (sig_mask.index >= cutoff)]
            for ts in recent.index:
                sig_date = ts.strftime("%Y-%m-%d")
                key = f"{market}:{ticker}:{name}"
                if state and not is_new(key, sig_date, state):
                    continue
                row = prep.loc[ts]
                atr_v = row["atr"] if not pd.isna(row["atr"]) else row["Close"] * 0.02
                entry = float(row["Close"])
                sl = entry - 2.0 * atr_v
                risk = abs(entry - sl)
                signals.append({
                    "symbol": ticker,
                    "market": market,
                    "setup": name,
                    "date": sig_date,
                    "direction": "LONG",
                    "entry": round(entry, 2),
                    "sl": round(sl, 2),
                    "tp1": round(entry + risk * 1.5, 2),
                    "tp2": round(entry + risk * 2.5, 2),
                    "tp3": round(entry + risk * 4.0, 2),
                    "rsi": round(float(row["rsi"]), 1) if not pd.isna(row["rsi"]) else None,
                    "noise": round(float(row["noise"]), 1) if not pd.isna(row["noise"]) else None,
                    "vol_ratio": round(float(row["vol_ratio"]), 2) if not pd.isna(row["vol_ratio"]) else None,
                    "price": entry,
                })
        return signals
    except Exception as e:
        print(f"    Error {ticker}: {e}", file=sys.stderr)
        return []


def main():
    args = sys.argv[1:]
    use_all = "--all" in args
    days_back = 2
    for a in args:
        if a.startswith("--days"):
            try:
                days_back = int(a.split("=")[1])
            except Exception:
                pass

    setups = list(bt.SETUPS.keys()) if use_all else TOP_SETUPS
    print(f"=== VIBE SCANNER: {len(setups)} Setups, letzte {days_back} Tage ===")
    print(f"Setups: {', '.join(setups)}\n")

    state = load_state()
    all_signals = []

    for label, tickers in (("US", US_TOP100), ("DAX", DAX_40)):
        print(f"--- {label} ---")
        for i, t in enumerate(tickers, 1):
            sigs = scan_symbol(t, label, setups, days_back, state)
            if sigs:
                for s in sigs:
                    all_signals.append(s)
                print(f"  {t}: {len(sigs)} Signal(e)")
            if i % 25 == 0:
                print(f"  ... {i}/{len(tickers)}")
            time.sleep(0.05)

    save_state(state)

    # Ausgabe
    with open(OUTPUT_JSON, "w") as f:
        json.dump(all_signals, f, indent=2)

    if not all_signals:
        msg = "📭 **Vibe Scan** — Keine neuen Signale (Noise gefiltert)."
    else:
        lines = [f"🔔 **Vibe Scan — {len(all_signals)} neue Signale**\n"]
        for s in all_signals:
            lines.append(
                f"🟢 **{s['symbol']}** ({s['market']}) — {s['setup']}\n"
                f"   Entry: {s['entry']} | SL: {s['sl']} | TP1: {s['tp1']} | TP2: {s['tp2']}\n"
                f"   RSI: {s['rsi']} | Noise: {s['noise']} | Vol: {s['vol_ratio']}x | Datum: {s['date']}"
            )
        msg = "\n\n".join(lines)

    with open(OUTPUT_TXT, "w") as f:
        f.write(msg)
    print(msg)


if __name__ == "__main__":
    main()
