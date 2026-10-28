"""
DE-Paper-Broker 🇩🇪 — lokaler Simulator für deutsche Aktien.

Problem: Alpaca kann keine deutschen Aktien (nur US). Damit die deutsche
Börse voll im Live-Loop mitläuft, simulieren wir DE-Trades lokal (Paper,
0€ Risiko) — gleiche Regeln wie US: max 7% pro Trade, max 5 Positionen.

Zustand wird in der State-DB gespeichert (orchestra/data/cache).
Preise kommen von yfinance (XETRA-Schlusskurse).

Später kann hier ein echter DE-Broker (IBKR etc.) angedockt werden —
die Schnittstelle (open/sell/get_positions) bleibt gleich.
"""
import sys
import time
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestra.logging_setup import log_trade, log_error, orchestra_log

# Regeln (identisch zu US)
MAX_POSITIONS = 5
RISK_PCT = 0.07
TARGET_PCT = 15.0
STOP_PCT = -8.0
HOLD_DAYS = 30


def _get_state():
    try:
        from orchestra.data import cache
        return cache.get_state("de_paper", {})
    except Exception:
        return {}


def _save_state(state):
    try:
        from orchestra.data import cache
        cache.set_state("de_paper", state)
    except Exception as e:
        log_error("de_paper save", e)


def _price(symbol):
    """Aktueller XETRA-Schlusskurs via yfinance."""
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        h = t.history(period="1d")
        if h is not None and len(h) > 0:
            return float(h["Close"].iloc[-1])
    except Exception as e:
        log_error(f"de_price {symbol}", e)
    return None


def get_positions():
    """Offene DE-Paper-Positionen als Liste."""
    state = _get_state()
    return list(state.values())


def get_account_equity():
    """Startkapital + unrealisierte Gewinne (simuliert)."""
    state = _get_state()
    return float(state.get("_equity", 100000))


def open_position(symbol, qty, price, extra=""):
    """Öffnet eine DE-Paper-Position."""
    state = _get_state()
    positions = {k: v for k, v in state.items() if not k.startswith("_")}
    if len(positions) >= MAX_POSITIONS:
        orchestra_log().info(f"DE {symbol}: Position-Limit erreicht ({len(positions)}/{MAX_POSITIONS})")
        return None
    if symbol in positions:
        orchestra_log().info(f"DE {symbol}: Position bereits offen")
        return None
    state[symbol] = {
        "symbol": symbol, "qty": qty, "entry_price": price,
        "entry_time": time.time(), "current_price": price,
    }
    _save_state(state)
    log_trade(symbol, "buy", qty, "DE-PAPER", "filled",
              price=price, extra=f"DE-PAPER-BROKER {extra}")
    orchestra_log().info(f"DE-BROKER BUY {symbol}: qty={qty} @ {price:.2f} € ({extra})")
    return state[symbol]


def sell_position(symbol, qty, price, extra=""):
    """Schließt eine DE-Paper-Position."""
    state = _get_state()
    if symbol not in state:
        return None
    log_trade(symbol, "sell", qty, "DE-PAPER", "filled",
              price=price, extra=f"DE-PAPER-BROKER {extra}")
    orchestra_log().info(f"DE-BROKER SELL {symbol}: qty={qty} @ {price:.2f} € ({extra})")
    del state[symbol]
    _save_state(state)
    return {"symbol": symbol, "qty": qty}


def execute_decision(decision, symbol, timeframe="1d"):
    """
    Führt eine Conductor-Entscheidung für DE-Aktien aus.
    Gleiche Logik wie US: max 7% pro Trade, max 5 Positionen, Insider-Hold.
    """
    if isinstance(decision, dict):
        dec_str = decision.get("decision", "HOLD")
        strength = decision.get("strength", 0)
    else:
        dec_str = decision
        strength = 0

    price = _price(symbol)
    if not price:
        orchestra_log().info(f"DE {symbol}: kein Preis verfügbar")
        return None

    state = _get_state()
    positions = {k: v for k, v in state.items() if not k.startswith("_")}

    # Layer-System (1d/4h) hat kleinere strength-Werte (~0.05-0.18) als das alte
    # 5-Agenten-System (0.2-0.4). Schwelle daher auf 0.05 gesetzt (28.10.).
    MIN_STRENGTH = 0.05
    if dec_str == "BUY" and strength >= MIN_STRENGTH:
        if symbol in positions:
            return None
        if len(positions) >= MAX_POSITIONS:
            orchestra_log().info(f"DE {symbol}: Limit {len(positions)}/{MAX_POSITIONS}")
            return None
        equity = get_account_equity()
        budget = equity * RISK_PCT
        qty = int(budget / price)
        if qty <= 0:
            orchestra_log().info(f"DE {symbol}: Budget zu klein (${price:.2f})")
            return None
        # Insider-Hold prüfen (EDGAR nur US — DE hat kein EDGAR, daher normal halten)
        return open_position(symbol, qty, price, extra=f"timeframe={timeframe} Stärke={strength:.2f}")

    elif dec_str == "SELL" and strength >= MIN_STRENGTH:
        if symbol in positions:
            return sell_position(symbol, positions[symbol]["qty"], price,
                                 extra=f"timeframe={timeframe} Stärke={strength:.2f}")
        return None

    return None


def manage_positions():
    """Ausstiegslogik für DE-Positionen (Ziel +15% / Stop -8% / 30 Tage)."""
    state = _get_state()
    actions = []
    for sym, pos in list(state.items()):
        if sym.startswith("_"):
            continue
        entry = pos["entry_price"]
        current = _price(sym) or entry
        pos["current_price"] = current
        pnl_pct = (current - entry) / entry * 100
        held_days = (time.time() - pos["entry_time"]) / 86400
        exit_reason = None
        if pnl_pct >= TARGET_PCT:
            exit_reason = f"Gewinnziel +{pnl_pct:.1f}%"
        elif pnl_pct <= STOP_PCT:
            exit_reason = f"Stop-Loss {pnl_pct:.1f}%"
        elif held_days >= HOLD_DAYS:
            exit_reason = f"{HOLD_DAYS} Tage ({pnl_pct:+.1f}%)"
        if exit_reason:
            actions.append(sell_position(sym, pos["qty"], current, extra=exit_reason))
        else:
            _save_state(state)
    return actions


if __name__ == "__main__":
    print("DE-Paper-Broker Test:")
    print("  Preis SAP.DE:", _price("SAP.DE"))
    print("  Preis SIE.DE:", _price("SIE.DE"))
    print("  Positionen:", get_positions())
