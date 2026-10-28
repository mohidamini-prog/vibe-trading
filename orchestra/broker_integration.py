"""
Broker-Integration: verbindet den Orchestrator mit Alpaca Paper-Trading.

Jede BUY/SELL-Entscheidung des Conductors wird automatisch als Paper-Order
ausgeführt (simuliert, 0$ Risiko) und geloggt. HOLD = keine Aktion.

So wird die echte Performance der Strategie live gegen den Markt gemessen,
ohne echtes Geld zu riskieren.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestra.logging_setup import log_trade, log_error, orchestra_log


# --- Position-Sizing-Regeln (Go-Live) ---
MAX_POSITIONS = 5            # max 5 gleichzeitig
RISK_PER_TRADE_PCT = 0.07    # max 7% des Kapitals pro Trade
INSIDER_HOLD_DAYS = 30       # Buy & Hold bei Insider-Käufen (länger halten)
INSIDER_BUY_MIN_NET = 100000 # Mindest-Netto-Kaufwert in $ für Insider-Hold


def get_account_equity():
    """Aktuelles Equity aus dem Paper-Konto (Cash + Positionen)."""
    try:
        from orchestra.brokers.alpaca import get_account
        acct = get_account()
        if "error" in acct:
            return None
        return float(acct.get("equity", 0))
    except Exception:
        return None


def get_open_positions():
    """Liste der offenen Positionen (Symbole)."""
    try:
        from orchestra.brokers.alpaca import get_positions
        pos = get_positions()
        if isinstance(pos, list):
            return pos
        return []
    except Exception:
        return []


def is_insider_buy_hold(symbol):
    """
    Prüft, ob ein Symbol ein Insider-Buy&Hold-Kandidat ist:
      - EDGAR-Insider-Käufe mit Netto-Kaufwert >= Schwelle
      - und Richtung BUY
    Returns: (is_hold, net_value, n_transactions)
    """
    try:
        from orchestra.risk_robot import assess_risk
        risk = assess_risk(symbol)
        ins = risk.get("insider", {})
        net = ins.get("net_value", 0)
        n = ins.get("n_transactions", 0)
        direction = ins.get("direction", 0)
        is_hold = (direction > 0) and (net >= INSIDER_BUY_MIN_NET) and (n > 0)
        return (is_hold, net, n)
    except Exception as e:
        log_error(f"insider_hold check {symbol}", e)
        return (False, 0, 0)


def position_sizing(symbol, price, equity, risk_pct=RISK_PER_TRADE_PCT):
    """
    Berechnet die Positionsgröße:
      - max 7% des Equities als Kaufwert
      - gerundet auf ganze Aktien
    Returns: (qty, notional)
    """
    if not equity or equity <= 0 or not price or price <= 0:
        return (0, 0.0)
    budget = equity * risk_pct
    qty = int(budget / price)  # ganze Aktien
    notional = qty * price
    return (qty, round(notional, 2))


def can_open_position():
    """Prüft ob noch eine Position geöffnet werden kann (max 5)."""
    open_pos = get_open_positions()
    return len(open_pos) < MAX_POSITIONS, len(open_pos), MAX_POSITIONS


def manage_sltp_exits():
    """
    SL/TP-Exit-Verwaltung für offene Positionen:
      - Prüft gegen die gespeicherten SL/TP1/TP2-Level
      - SL getroffen -> voller Verkauf
      - TP1 getroffen -> Teilverkauf (50%)
      - TP2 getroffen -> Rest verkaufen
    Returns: Liste verkaufter Positionen.
    """
    try:
        from orchestra.data import cache
        from orchestra.brokers.alpaca import get_positions, fetch_bars, submit_order
        sltp_state = cache.get_state("sltp_levels", {})
        positions = get_positions()
        actions = []
        if not isinstance(positions, list):
            return actions
        for pos in positions:
            sym = pos.get("symbol")
            if sym not in sltp_state:
                continue
            lvl = sltp_state[sym]
            try:
                bars = fetch_bars(sym, "1Day", 1)
                current = bars[-1]["c"] if isinstance(bars, list) and bars else float(pos.get("current_price", 0))
            except Exception:
                current = float(pos.get("current_price", 0))
            qty = int(float(pos.get("qty", 0)))
            if qty <= 0 or current <= 0:
                continue
            sl, tp1, tp2 = lvl.get("sl"), lvl.get("tp1"), lvl.get("tp2")
            # SL getroffen -> alles verkaufen
            if sl is not None and current <= sl:
                order = submit_order(sym, qty, "sell")
                if "error" not in order:
                    log_trade(sym, "sell", qty, order.get("id", "?"), order.get("status", "?"),
                              price=current, extra=f"SL-TRIGGER (SL={sl:.2f})")
                    actions.append({"symbol": sym, "reason": "SL", "price": current, "qty": qty})
                    del sltp_state[sym]
                continue
            # TP2 getroffen -> Rest verkaufen
            if tp2 is not None and current >= tp2:
                order = submit_order(sym, qty, "sell")
                if "error" not in order:
                    log_trade(sym, "sell", qty, order.get("id", "?"), order.get("status", "?"),
                              price=current, extra=f"TP2-TRIGGER (TP2={tp2:.2f})")
                    actions.append({"symbol": sym, "reason": "TP2", "price": current, "qty": qty})
                    del sltp_state[sym]
                continue
            # TP1 getroffen -> Teilverkauf (50%)
            if tp1 is not None and current >= tp1:
                half = max(1, qty // 2)
                order = submit_order(sym, half, "sell")
                if "error" not in order:
                    log_trade(sym, "sell", half, order.get("id", "?"), order.get("status", "?"),
                              price=current, extra=f"TP1-TRIGGER (TP1={tp1:.2f}, 50% Teilgewinn)")
                    actions.append({"symbol": sym, "reason": "TP1", "price": current, "qty": half})
                    # TP1-Status aktualisieren (nur TP2 bleibt aktiv)
                    lvl["tp1_hit"] = True
                    sltp_state[sym] = lvl
        cache.set_state("sltp_levels", sltp_state)
        return actions
    except Exception as e:
        log_error("manage_sltp", e)
        return []


def manage_insider_holds():
    """
    Verwalten der Insider-Buy&Hold-Positionen:
      - Positionen, die als Insider-Hold markiert sind, werden NICHT bei
        jedem SELL-Signal verkauft, sondern gehalten bis:
          a) Gewinnziel erreicht (>= +15%) ODER
          b) 30 Tage gehalten ODER
          c) Stop-Loss (< -8%)
    Returns: Liste von verkauften Positionen (Aktionen).
    """
    import time
    from orchestra.data import cache
    holds = cache.get_state("insider_holds", {})
    positions = get_open_positions()
    actions = []
    for pos in positions:
        sym = pos.get("symbol")
        if sym not in holds:
            continue
        hold_info = holds[sym]
        entry = float(pos.get("avg_entry_price", 0))
        current = float(pos.get("current_price", entry))
        entry_time = hold_info.get("entry_time", time.time())
        if entry <= 0:
            continue
        pnl_pct = (current - entry) / entry * 100
        held_days = (time.time() - entry_time) / 86400
        # Ausstiegslogik
        exit_reason = None
        if pnl_pct >= 15:
            exit_reason = f"Gewinnziel +{pnl_pct:.1f}%"
        elif pnl_pct <= -8:
            exit_reason = f"Stop-Loss {pnl_pct:.1f}%"
        elif held_days >= INSIDER_HOLD_DAYS:
            exit_reason = f"30 Tage gehalten ({held_days:.0f} Tage, PnL {pnl_pct:+.1f}%)"
        if exit_reason:
            qty = int(float(pos.get("qty", 0)))
            if qty > 0:
                try:
                    from orchestra.brokers.alpaca import submit_order
                    order = submit_order(sym, qty, "sell")
                    if "error" not in order:
                        log_trade(sym, "sell", qty, order.get("id", "?"), order.get("status", "?"),
                                  price=order.get("filled_avg_price"),
                                  extra=f"INSIDER-HOLD AUSSTIEG: {exit_reason}")
                        actions.append({"symbol": sym, "action": "SELL", "reason": exit_reason, "qty": qty})
                        del holds[sym]  # Hold-Status entfernen
                    else:
                        log_error(f"Insider-Hold SELL {sym}", order["error"])
                except Exception as e:
                    log_error(f"Insider-Hold SELL {sym}", e)
    cache.set_state("insider_holds", holds)
    return actions


# Standard-Positionsgröße (Anzahl Aktien pro Trade) — konservativ fürs Paper-Trading
DEFAULT_QTY = 10


def execute_decision(decision, symbol, qty=DEFAULT_QTY, timeframe="1d"):
    """
    Führt eine Conductor-Entscheidung als Paper-Order aus.
    decision: dict (aus LayerDecision.to_dict()) oder String.
    Returns: Order-Bestätigung oder None (bei HOLD/Fehler).

    Regeln:
      - RISK-ROBOTER: Earnings/Insider-Veto blockt die Order
      - max 7% des Kapitals pro Trade
      - max 5 gleichzeitige Positionen
    """
    if isinstance(decision, dict):
        dec_str = decision.get("decision", "HOLD")
        strength = decision.get("strength", 0)
    else:
        dec_str = decision
        strength = 0

    # RISK-ROBOTER: Veto vor jeder Order prüfen (Earnings/Insider)
    try:
        from orchestra.risk_robot import assess_risk
        risk = assess_risk(symbol)
        if risk.get("veto"):
            orchestra_log().info(f"{symbol}: RISK-VETO blockt Order — {'; '.join(risk['reasons'])}")
            return None
    except Exception as e:
        log_error(f"risk pre-check {symbol}", e)

    # Nur bei ausreichender Stärke handeln (Qualität > Quantität)
    if dec_str == "BUY":
        if strength < 0.2:
            orchestra_log().info(f"{symbol}: BUY-Signal zu schwach (Stärke {strength:.2f}) -> keine Order")
            return None
        # Position-Limit prüfen (max 5)
        can_open, n_open, n_max = can_open_position()
        if not can_open:
            orchestra_log().info(f"{symbol}: Position-Limit erreicht ({n_open}/{n_max}) -> keine neue Position")
            return None
        # INSIDER BUY & HOLD: Prüfen ob Insider-Käufe vorliegen -> länger halten
        is_hold, net_val, n_tx = is_insider_buy_hold(symbol)
        hold_tag = ""
        if is_hold:
            hold_tag = f" INSIDER-HOLD ({n_tx} Txs, Netto ${net_val:,.0f})"
            orchestra_log().info(f"{symbol}: {hold_tag} -> Buy&Hold-Modus (länger halten)")
        # Position-Sizing: max 7% des Kapitals
        equity = get_account_equity()
        try:
            from orchestra.brokers.alpaca import fetch_bars
            bars = fetch_bars(symbol, "1Day", 1)
            price = bars[-1]["c"] if isinstance(bars, list) and bars else None
        except Exception:
            price = None
        if equity and price:
            sized_qty, notional = position_sizing(symbol, price, equity)
            if sized_qty > 0:
                qty = sized_qty
                orchestra_log().info(f"{symbol}: Position-Sizing -> qty={qty} (~${notional:.0f} = 7% von ${equity:.0f})")
            else:
                orchestra_log().info(f"{symbol}: Budget zu klein für 1 Aktie (${price:.2f}) -> keine Order")
                return None
        try:
            from orchestra.brokers.alpaca import submit_order
            order = submit_order(symbol, qty, "buy")
            if "error" in order:
                log_error(f"Order BUY {symbol}", order["error"])
                return None
            log_trade(symbol, "buy", qty, order.get("id", "?"), order.get("status", "?"),
                      price=order.get("filled_avg_price"),
                      extra=f"timeframe={timeframe} Stärke={strength:.2f}{hold_tag}")
            # SL/TP aus S/R + Fib berechnen (Einträge unverändert)
            try:
                from orchestra.layers.data import load_ohlcv
                from orchestra.layers.indicators import compute_indicators
                from orchestra.sl_tp import compute_sl_tp
                df = load_ohlcv(symbol, timeframe)
                if df is not None:
                    df = compute_indicators(df)
                    entry_px = order.get("filled_avg_price") or price or float(df["close"].iloc[-1])
                    sltp = compute_sl_tp(df, entry_px, direction=1)
                    if sltp:
                        log_trade(symbol, "info", qty, "SLTP", "set",
                                  price=entry_px,
                                  extra=f"SL={sltp['sl']} ({sltp['sl_source']}) TP1={sltp['tp1']} ({sltp['tp1_source']}) TP2={sltp['tp2']} ({sltp['tp2_source']}) RR1={sltp['rr1']} RR2={sltp['rr2']}")
                        # SL/TP-Level in Position-State speichern (für Exit-Verwaltung)
                        from orchestra.data import cache
                        sltp_state = cache.get_state("sltp_levels", {})
                        sltp_state[symbol] = sltp
                        cache.set_state("sltp_levels", sltp_state)
            except Exception as e:
                log_error(f"sltp calc {symbol}", e)
            # Wenn Insider-Hold: Position als Hold markieren (State-DB)
            if is_hold:
                import time
                from orchestra.data import cache
                holds = cache.get_state("insider_holds", {})
                holds[symbol] = {
                    "entry_time": time.time(),
                    "net_value": net_val,
                    "n_transactions": n_tx,
                    "entry_price": order.get("filled_avg_price") or price,
                }
                cache.set_state("insider_holds", holds)
            return order
        except Exception as e:
            log_error(f"Order BUY {symbol}", e)
            return None

    elif dec_str == "SELL":
        if strength < 0.2:
            orchestra_log().info(f"{symbol}: SELL-Signal zu schwach (Stärke {strength:.2f}) -> keine Order")
            return None
        # INSIDER-HOLD-Schutz: Wenn Position als Insider-Hold markiert ist,
        # NICHT bei normalem SELL-Signal verkaufen (wird von manage_insider_holds verwaltet)
        try:
            from orchestra.data import cache
            holds = cache.get_state("insider_holds", {})
            if symbol in holds:
                orchestra_log().info(f"{symbol}: INSIDER-HOLD aktiv -> SELL-Signal ignoriert (halten bis Ziel/Stop/30 Tage)")
                return None
        except Exception:
            pass
        try:
            from orchestra.brokers.alpaca import submit_order
            order = submit_order(symbol, qty, "sell")
            if "error" in order:
                log_error(f"Order SELL {symbol}", order["error"])
                return None
            log_trade(symbol, "sell", qty, order.get("id", "?"), order.get("status", "?"),
                      price=order.get("filled_avg_price"), extra=f"timeframe={timeframe} Stärke={strength:.2f}")
            return order
        except Exception as e:
            log_error(f"Order SELL {symbol}", e)
            return None

    # HOLD oder anderes -> keine Aktion
    return None


if __name__ == "__main__":
    # Test: Entscheidungen simulieren
    print("Test BUY mit ausreichender Stärke:")
    execute_decision({"decision": "BUY", "strength": 0.41}, "AAPL", qty=1)
    print("\nTest HOLD (keine Aktion):")
    execute_decision({"decision": "HOLD", "strength": 0.0}, "MSFT", qty=1)
    print("\nTest SELL zu schwach (keine Aktion):")
    execute_decision({"decision": "SELL", "strength": 0.1}, "NVDA", qty=1)
    print("\nLogs prüfen:")
    for line in (Path(__file__).parent / "logs" / "trades.log").read_text().splitlines()[-5:]:
        print(" ", line)
