"""
Zentraler Live-Loop — verbindet normale Signale + Insider-Handler.

Pro Zyklus (automatisch, z.B. alle 30 Min während US-Börsenzeiten):
  1. INSIDER-HANDLER (separat): Einmal pro Tag EDGAR-Käufe scannen -> kaufen & halten
  2. NORMALE SIGNALE: Orchestrator scannt 4h + 1d -> BUY/SELL per Conductor
  3. Beides loggen; bei Trades Telegram/Hermes benachrichtigen

Dieses Skript wird als zeitgesteuerter Job (cron) ausgeführt.
"""
import sys
import json
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestra.logging_setup import orchestra_log, trades_log, log_trade, log_error

# US-Symbole (Alpaca-handelbar) — Kern-Universe
US_SYMBOLS = ["AAPL", "MSFT", "NVDA", "META", "GOOGL", "AMZN", "TSLA"]
# DE-Symbole (yfinance, nur Signale)
DE_SYMBOLS = ["SAP.DE", "SIE.DE", "BMW.DE", "MBG.DE"]


def load_universe():
    """Lädt das Scan-Universum: DAX + MDAX (Xetra) + NASDAQ100 (28.10., User-Wunsch).
    Returns: (us_symbols, de_symbols) dedupliziert.
    """
    import json
    from pathlib import Path
    cfg = Path(__file__).resolve().parent.parent / "index_constituents.json"
    us, de = [], []
    if cfg.exists():
        try:
            d = json.loads(cfg.read_text())
            # US-Ticker (nur NASDAQ100)
            us += d.get("NASDAQ100", [])
            # DE-Ticker (DAX + MDAX, nur .DE = Xetra)
            for key in ("DAX", "MDAX"):
                de += [t for t in d.get(key, []) if t.endswith(".DE")]
        except Exception:
            pass
    # Dedupe + Reihenfolge stabil
    us = list(dict.fromkeys(us))
    de = list(dict.fromkeys(de))
    return us or US_SYMBOLS, de or DE_SYMBOLS


def run_cycle(verbose=False):
    """Ein kompletter Live-Zyklus."""
    from orchestra.orchestrator import run_scan
    from orchestra.broker_integration import execute_decision
    from orchestra.insider_handler import run_insider_cycle
    from orchestra.layers.data import load_batch

    # Scan-Universum laden (DAX + MDAX/Xetra + NASDAQ100)
    us_all, de_all = load_universe()

    # Daten effizient per Batch-Download vorladen (Cache füllen)
    orchestra_log().info(f"Batch-Download {len(us_all)+len(de_all)} Symbole (1d)...")
    try:
        load_batch(us_all + de_all, timeframe="1d")
    except Exception as e:
        log_error("batch download 1d", e)
    orchestra_log().info(f"Batch-Download 4h...")
    try:
        load_batch(us_all + de_all, timeframe="4h")
    except Exception as e:
        log_error("batch download 4h", e)

    t0 = time.time()
    orchestra_log().info(f"=== LIVE-ZYKLUS START (US {len(us_all)}, DE {len(de_all)}) ===")
    trades = []

    # 1. Insider separat behandeln (einmal kaufen, dann abwarten)
    orchestra_log().info("Schritt 1/3: Insider-Signale (separat, einmal kaufen + abwarten)")
    try:
        ins_res = run_insider_cycle(us_all[:20])  # nur Top-20 US für API-Last
        for b in ins_res["new_buys"]:
            trades.append({"type": "insider_buy", **b})
        for e in ins_res["exits"]:
            trades.append({"type": "insider_exit", **e})
    except Exception as e:
        log_error("insider cycle", e)

    # 2. SL/TP-Exits verwalten (aus S/R + Fib, automatisch)
    orchestra_log().info("Schritt 2/4: SL/TP-Exits verwalten (S/R + Fib)")
    try:
        from orchestra.broker_integration import manage_sltp_exits
        sltp_actions = manage_sltp_exits()
        for a in sltp_actions:
            trades.append({"type": "sltp_exit", **a})
            if verbose:
                print(f"  🎯 SL/TP-EXIT: {a['symbol']} {a['reason']} @ {a.get('price', 0):.2f} (qty {a['qty']})")
    except Exception as e:
        log_error("sltp exits", e)

    # 3. DE-Positionen verwalten (Ausstiegslogik)
    orchestra_log().info("Schritt 3/4: DE-Positionen verwalten")
    try:
        from orchestra.brokers.de_paper import manage_positions as de_manage
        de_exits = de_manage()
        for e in de_exits:
            if e:
                trades.append({"type": "de_exit", **e})
    except Exception as e:
        log_error("de manage", e)

    # 4. Normale Signale auf 4h + 1d (über das erweiterte Universum)
    orchestra_log().info(f"Schritt 4/4: Normale Signale (4h + 1d, {len(us_all)+len(de_all)} Symbole)")
    try:
        results = run_scan(symbols=us_all + de_all, verbose=False)
        for key, d in results.items():
            if "error" in d:
                continue
            symbol, _, timeframe = key.partition(":")
            dec = d.get("decision", "HOLD")
            strength = d.get("strength", 0)
            if dec not in ("BUY", "SELL"):
                continue
            if ".DE" in symbol:
                # DE-Aktien über den lokalen DE-Paper-Broker handeln
                try:
                    from orchestra.brokers.de_paper import execute_decision as de_exec
                    order = de_exec({"decision": dec, "strength": strength}, symbol, timeframe=timeframe)
                    if order:
                        trades.append({"type": "signal_de", "symbol": symbol, "timeframe": timeframe,
                                       "decision": dec, "order_id": "DE-PAPER"})
                except Exception as e:
                    log_error(f"de trade {symbol}", e)
            else:
                order = execute_decision({"decision": dec, "strength": strength}, symbol, timeframe=timeframe)
                if order and "error" not in order:
                    trades.append({"type": "signal", "symbol": symbol, "timeframe": timeframe,
                                   "decision": dec, "order_id": order.get("id")})
    except Exception as e:
        log_error("signal cycle", e)

    dur = time.time() - t0
    orchestra_log().info(f"=== LIVE-ZYKLUS FERTIG in {dur:.1f}s ({len(trades)} Aktionen) ===")

    # Rückgabe für Benachrichtigung
    return {"trades": trades, "duration": dur}


if __name__ == "__main__":
    res = run_cycle()
    print(json.dumps(res, indent=2, default=str))
