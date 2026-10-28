"""
Insider-Handler 🤖 — SEPARATE Behandlung von EDGAR-Insider-Signalen.

Prinzip (User-Vorgabe):
  Insider-Signale werden NICHT wie normale Signale behandelt.
  Sie werden EINMALIG gekauft und dann ABGEWARTET — kein wiederholtes
  Abchecken, keine mehrfachen Prüfungen pro Zyklus.

Logik:
  1. Einmal pro Tag (oder wenn noch nicht gekauft): EDGAR-Insider-Käufe prüfen
     -> wenn BUY-Cluster: Position öffnen (max 7% Kapital, max 5 Positionen)
  2. Danach NUR Ausstiegslogik verwalten (Gewinnziel +15%, Stop -8%, 30 Tage)
  3. Kein erneutes Scannen/Abschwächen der Insider-Position in Folge-Zyklen

Unterschied zu normalen Signalen:
  - Normale Signale: BUY/SELL je nach Conductor-Entscheidung (4h + 1d)
  - Insider-Signale: EINMAL kaufen, dann halten bis Ziel/Stop/30 Tage
"""
import sys
import time
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestra.logging_setup import log_trade, log_error, orchestra_log

# Regeln
INSIDER_MAX_POSITIONS = 5
INSIDER_RISK_PCT = 0.07       # max 7% pro Trade
INSIDER_TARGET_PCT = 15.0     # Gewinnziel +15%
INSIDER_STOP_PCT = -8.0       # Stop-Loss -8%
INSIDER_HOLD_DAYS = 30        # max 30 Tage halten
INSIDER_BUY_MIN_NET = 100000  # Mindest-Netto-Kaufwert $ für Relevanz
INSIDER_CHECK_INTERVAL = 86400  # einmal pro Tag prüfen (24h)


def get_insider_state():
    """Liest den Insider-Hold-Status aus der State-DB."""
    try:
        from orchestra.data import cache
        return cache.get_state("insider_holds", {})
    except Exception:
        return {}


def save_insider_state(state):
    """Speichert den Insider-Hold-Status."""
    try:
        from orchestra.data import cache
        cache.set_state("insider_holds", state)
    except Exception as e:
        log_error("save insider_state", e)


def scan_insider_buys(symbols):
    """
    Einmalige Prüfung: Welche Symbole haben frische Insider-Käufe?
    Returns: Liste von {symbol, net_value, n_transactions, direction}
    """
    from orchestra.risk_robot import assess_risk
    buys = []
    for sym in symbols:
        try:
            r = assess_risk(sym)
            ins = r.get("insider", {})
            net = ins.get("net_value", 0)
            n = ins.get("n_transactions", 0)
            direction = ins.get("direction", 0)
            if direction > 0 and net >= INSIDER_BUY_MIN_NET and n > 0:
                buys.append({
                    "symbol": sym, "net_value": net,
                    "n_transactions": n, "direction": direction,
                })
                orchestra_log().info(f"INSIDER-BUY entdeckt: {sym} (Netto ${net:,.0f}, {n} Txs)")
        except Exception as e:
            log_error(f"insider scan {sym}", e)
    return buys


def open_insider_position(symbol, net_value, n_transactions):
    """
    Öffnet EINE Insider-Position (max 7% Kapital, max 5 Positionen).
    Returns: order oder None.
    """
    from orchestra.brokers.alpaca import get_account, get_positions, submit_order, fetch_bars

    # Position-Limit prüfen
    positions = get_positions()
    if isinstance(positions, list) and len(positions) >= INSIDER_MAX_POSITIONS:
        orchestra_log().info(f"INSIDER {symbol}: Position-Limit erreicht ({len(positions)}/{INSIDER_MAX_POSITIONS}) -> übersprungen")
        return None

    # Bereits offen?
    if isinstance(positions, list) and any(p.get("symbol") == symbol for p in positions):
        orchestra_log().info(f"INSIDER {symbol}: Position bereits offen -> nicht erneut kaufen")
        return None

    # Position-Sizing (max 7%)
    acct = get_account()
    if "error" in acct:
        log_error("insider account", acct["error"])
        return None
    equity = float(acct.get("equity", 0))
    try:
        bars = fetch_bars(symbol, "1Day", 1)
        price = bars[-1]["c"] if isinstance(bars, list) and bars else None
    except Exception:
        price = None
    if not equity or not price:
        log_error("insider sizing", "kein Preis/Equity")
        return None
    budget = equity * INSIDER_RISK_PCT
    qty = int(budget / price)
    if qty <= 0:
        orchestra_log().info(f"INSIDER {symbol}: Budget zu klein für 1 Aktie (${price:.2f})")
        return None

    order = submit_order(symbol, qty, "buy")
    if "error" in order:
        log_error(f"INSIDER BUY {symbol}", order["error"])
        return None
    log_trade(symbol, "buy", qty, order.get("id", "?"), order.get("status", "?"),
              price=order.get("filled_avg_price"),
              extra=f"INSIDER-HOLD KAUF (Netto ${net_value:,.0f}, {n_transactions} Txs)")
    orchestra_log().info(f"INSIDER BUY {symbol}: qty={qty} (${qty*price:,.0f} = 7% von ${equity:,.0f})")

    # Als Insider-Hold markieren (separate Behandlung)
    state = get_insider_state()
    state[symbol] = {
        "entry_time": time.time(),
        "net_value": net_value,
        "n_transactions": n_transactions,
        "entry_price": order.get("filled_avg_price") or price,
        "last_check": time.time(),
    }
    save_insider_state(state)
    return order


def manage_insider_positions():
    """
    Verwaltet bestehende Insider-Positionen:
      - Nur Ausstiegslogik (Ziel +15% / Stop -8% / 30 Tage)
      - KEIN erneutes Abchecken der Signale
    Returns: Liste verkaufter Positionen.
    """
    from orchestra.brokers.alpaca import get_positions, submit_order
    state = get_insider_state()
    positions = get_positions()
    actions = []
    if not isinstance(positions, list):
        return actions
    for pos in positions:
        sym = pos.get("symbol")
        if sym not in state:
            continue
        info = state[sym]
        entry = float(pos.get("avg_entry_price", 0))
        current = float(pos.get("current_price", entry))
        entry_time = info.get("entry_time", time.time())
        if entry <= 0:
            continue
        pnl_pct = (current - entry) / entry * 100
        held_days = (time.time() - entry_time) / 86400
        exit_reason = None
        if pnl_pct >= INSIDER_TARGET_PCT:
            exit_reason = f"Gewinnziel +{pnl_pct:.1f}%"
        elif pnl_pct <= INSIDER_STOP_PCT:
            exit_reason = f"Stop-Loss {pnl_pct:.1f}%"
        elif held_days >= INSIDER_HOLD_DAYS:
            exit_reason = f"{INSIDER_HOLD_DAYS} Tage gehalten ({pnl_pct:+.1f}%)"
        if exit_reason:
            qty = int(float(pos.get("qty", 0)))
            if qty > 0:
                order = submit_order(sym, qty, "sell")
                if "error" not in order:
                    log_trade(sym, "sell", qty, order.get("id", "?"), order.get("status", "?"),
                              price=order.get("filled_avg_price"),
                              extra=f"INSIDER-HOLD EXIT: {exit_reason}")
                    actions.append({"symbol": sym, "reason": exit_reason, "qty": qty})
                    del state[sym]
                    orchestra_log().info(f"INSIDER EXIT {sym}: {exit_reason}")
                else:
                    log_error(f"INSIDER EXIT {sym}", order["error"])
    save_insider_state(state)
    return actions


def run_insider_cycle(symbols, force_check=False):
    """
    Kompletter Insider-Zyklus:
      1. Nur wenn frisch (alle 24h): Insider-Käufe scannen -> kaufen
      2. Bestehende Positionen verwalten (Ausstiegslogik)
    Returns: {new_buys: [...], exits: [...]}
    """
    now = time.time()
    state = get_insider_state()
    # Nur einmal pro Tag frisch scannen (nicht jeden Zyklus)
    need_scan = force_check
    if not need_scan:
        for sym, info in state.items():
            if now - info.get("last_check", 0) > INSIDER_CHECK_INTERVAL:
                need_scan = True
                break
        if not state:
            need_scan = True  # noch nie gescannt

    new_buys = []
    if need_scan:
        orchestra_log().info("INSIDER-SCAN: Prüfe EDGAR-Insider-Käufe (einmal pro Tag)")
        buys = scan_insider_buys(symbols)
        for b in buys:
            order = open_insider_position(b["symbol"], b["net_value"], b["n_transactions"])
            if order and "error" not in order:
                new_buys.append({"symbol": b["symbol"], "net_value": b["net_value"],
                                 "n_transactions": b["n_transactions"]})
        # last_check für alle aktualisieren
        state = get_insider_state()
        for sym in state:
            state[sym]["last_check"] = now
        save_insider_state(state)

    # Bestehende verwalten (Ausstiegslogik)
    exits = manage_insider_positions()
    return {"new_buys": new_buys, "exits": exits}


if __name__ == "__main__":
    print("INSIDER-HANDLER Testlauf...")
    symbols = ["AAPL", "MSFT", "NVDA", "META", "GOOGL", "AMZN", "TSLA"]
    res = run_insider_cycle(symbols, force_check=True)
    print(f"Neue Insider-Käufe: {len(res['new_buys'])}")
    for b in res["new_buys"]:
        print(f"  {b['symbol']}: Netto ${b['net_value']:,.0f}, {b['n_transactions']} Txs")
    print(f"Exits: {len(res['exits'])}")
    for e in res["exits"]:
        print(f"  {e['symbol']}: {e['reason']}")
