"""
Live-Trading-Engine — verbindet Orchestrator + Risk-Roboter + Broker.

Go-Live-Logik pro Zyklus:
  1. Alle Symbole auf 1d & 4h scannen (Orchestrator)
  2. Für jede BUY/SELL-Entscheidung: Risk-Roboter prüfen, dann Paper-Order
     (max 7% pro Trade, max 5 Positionen, Insider-Hold-Schutz)
  3. Insider-Hold-Positionen verwalten (Gewinnziel/Stop/30 Tage)
  4. Alles loggen + bei Trade-Meldung an Telegram/Hermes

Nutzt die bestehende Layer-Pipeline und Alpaca Paper-Trading.
"""
import sys
import json
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestra.logging_setup import orchestra_log, trades_log, log_trade, log_error


def run_live_cycle(symbols=None, verbose=True):
    """
    Ein kompletter Live-Zyklus:
    - Scan (Orchestrator)
    - Trades ausführen (Broker-Integration mit Risk-Roboter)
    - Insider-Holds verwalten
    Returns: {trades: [...], decisions: {...}}
    """
    from orchestra.orchestrator import run_scan
    from orchestra.broker_integration import execute_decision, manage_insider_holds

    trades = []

    # 1. Insider-Holds zuerst verwalten (verkaufen wenn Ziel/Stop/30 Tage)
    if verbose:
        print("→ Insider-Holds verwalten...")
    hold_actions = manage_insider_holds()
    for a in hold_actions:
        trades.append({"type": "insider_hold_exit", **a})
        print(f"  💰 Insider-Hold EXIT: {a['symbol']} {a['reason']} (qty {a['qty']})")

    # 2. Scan über Universum × Timeframes
    if verbose:
        print("→ Universum scannen (1d + 4h)...")
    results = run_scan(symbols=symbols, verbose=verbose)

    # 3. Entscheidungen als Paper-Orders ausführen
    if verbose:
        print("\n→ Entscheidungen ausführen (Paper, 0$ Risiko)...")
    executed = []
    for key, d in results.items():
        if "error" in d:
            continue
        # Key ist "SYMBOL:TF"
        symbol, _, timeframe = key.partition(":")
        # Nur US-Symbole über Alpaca (DE-Symbole hat Alpaca nicht)
        if ".DE" in symbol or symbol not in _alpaca_symbols():
            continue
        dec = {"decision": d.get("decision", "HOLD"), "strength": d.get("strength", 0)}
        # Nur bei BUY/SELL etwas tun
        if dec["decision"] in ("BUY", "SELL"):
            order = execute_decision(dec, symbol, timeframe=timeframe)
            if order and "error" not in order:
                executed.append({"symbol": symbol, "timeframe": timeframe,
                                 "decision": dec["decision"], "order_id": order.get("id")})
                if verbose:
                    print(f"  ✅ {symbol} {timeframe}: {dec['decision']} Order {order.get('id','')[:8]}")
            elif verbose:
                print(f"  ⏭️  {symbol} {timeframe}: {dec['decision']} (keine Order — Filter/Stärke/Position)")
    trades.extend(executed)

    if verbose:
        print(f"\n→ Zyklus fertig: {len(trades)} Aktionen")
    return {"trades": trades, "decisions": results}


def _alpaca_symbols():
    """US-Symbole, die Alpaca handeln kann (ohne .DE)."""
    return {"AAPL", "MSFT", "NVDA", "META", "GOOGL", "AMZN", "TSLA"}


if __name__ == "__main__":
    print("🚀 GO-LIVE Zyklus startet (Paper-Trading)...")
    res = run_live_cycle(verbose=True)
    print("\nZusammenfassung:")
    for t in res["trades"]:
        print(f"  {t}")
    print("\nLogs:")
    for line in (Path(__file__).parent / "logs" / "trades.log").read_text().splitlines()[-8:]:
        print(" ", line)
