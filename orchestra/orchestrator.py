"""
Orchestrator — verbindet alle Layer zu einer robusten Pipeline.

Ablauf pro Scan:
  1. Daten (Layer 0): OHLCV für alle Symbole auf 1d & 4h
  2. Indikatoren (Layer 1): einmalig, zentral
  3. Signale (Layer 2): alle Modelle
  4. Filter (Layer 3): Smart-Money-Gates
  5. Conductor (Layer 4): gewichtete Aggregation + Konfidenz-Modulation
  6. Output (Layer 5): Signale in Pfade schreiben

Robustheit:
  - Jeder Schritt in try/except (ein fehlerhaftes Symbol killt nicht den Scan)
  - Fehler werden in den Output geschrieben (diagnostizierbar)
  - Cache-freundlich, ARM-tauglich
"""
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestra.config import get, load_config
from orchestra.config import paths

# Universe: US + DE
US = ["AAPL", "MSFT", "NVDA", "META", "GOOGL", "AMZN", "TSLA"]
DE = ["SAP.DE", "SIE.DE", "ALV.DE", "BMW.DE", "DTE.DE", "MBG.DE", "VOW3.DE"]
UNIVERSE = US + DE

# Timeframes + Frequenzen
TIMEFRAMES = ["1d", "4h"]

# Modell-Gewichte (aus Backtesting, Qualität > Quantität)
DEFAULT_WEIGHTS = {
    "new_52w_high_momentum": 0.45,
    "sr_flip_breakout": 0.35,
    "deep_value_bounce_52w": 0.15,
    "fib_pullback_confluence": 0.05,
    "meanrev_bb": 0.0,
}


def run_symbol(symbol, timeframe, conductor):
    """Ein Symbol + Timeframe durch alle Layer. Returns dict."""
    try:
        from orchestra.logging_setup import log_signal, log_decision, log_error
        from orchestra.layers.data import load_ohlcv
        from orchestra.layers.indicators import compute_indicators, get_snapshot
        from orchestra.layers.signals import compute_all_signals
        from orchestra.layers.filters import apply_filters

        df = load_ohlcv(symbol, timeframe)
        if df is None or len(df) < 60:
            return {"error": f"keine Daten ({len(df) if df is not None else 0} Kerzen)", "symbol": symbol}

        df = compute_indicators(df)
        signals = compute_all_signals(df)
        # Jedes Signal loggen (Springer-Infos)
        for s in signals:
            if s["a"] != 0:
                log_signal(symbol, timeframe, s["model"], s["a"], s["conf"], s["reason"])
        passed, filter_report = apply_filters(df)

        dec = conductor.conduct(symbol, timeframe, signals, passed, filter_report)
        d = dec.to_dict()
        # Entscheidung loggen
        log_decision(symbol, timeframe, d["decision"], d["S"], d["strength"], d["avg_confidence"])

        # RISK-ROBOTER: Earnings + EDGAR-Insider prüfen (nur auf 1d, um API-Last zu sparen)
        if timeframe == "1d":
            try:
                from orchestra.risk_robot import assess_risk
                risk = assess_risk(symbol)
                d["risk"] = risk
                if risk.get("veto"):
                    # Veto: Entscheidung abschwächen -> HOLD, Signal dämpfen
                    d["vetoed"] = True
                    d["decision"] = "HOLD"
                    d["risk_veto"] = risk["reasons"]
                    log_error(f"RISK-VETO {symbol}", " | ".join(risk["reasons"]))
                elif risk.get("direction") != 0:
                    # Insider-Richtung als Verstärker (kein Veto)
                    d["insider_direction"] = risk["direction"]
                    d["insider_confidence"] = risk["confidence"]
            except Exception as e:
                log_error(f"risk_robot {symbol}", e)

        # Springer-Infos: Indikator-Snapshot der letzten Kerze
        d["snapshot"] = get_snapshot(df)
        return d
    except Exception as e:
        log_error(f"run_symbol {symbol} {timeframe}", e)
        return {"error": str(e), "symbol": symbol}


def run_scan(symbols=None, timeframes=None, verbose=True):
    """Kompletter Scan über Universum × Timeframes. Returns results dict."""
    load_config()
    paths.ensure_dirs()

    symbols = symbols or get("universe.symbols", UNIVERSE)
    timeframes = timeframes or TIMEFRAMES

    from orchestra.layers.conductor import Conductor
    conductor = Conductor()

    results = {}
    t0 = time.time()
    for tf in timeframes:
        for sym in symbols:
            d = run_symbol(sym, tf, conductor)
            # Schlüssel: "SYMBOL:TF" — eindeutig für beide Timeframes
            results[f"{sym}:{tf}"] = d
            if verbose and "error" not in d:
                print(f"  {sym:8s} {tf}: {d['decision']} (S={d['S']:+.2f})")

    # Output-Layer
    from orchestra.layers.output import write_signals
    write_signals(results)

    elapsed = time.time() - t0
    if verbose:
        print(f"\nScan fertig: {len(results)} Ergebnisse in {elapsed:.1f}s")
    return results


if __name__ == "__main__":
    # Ping-Lauf: einmal alle Layer durch, Ausgabe prüfen
    print("PING-LAUF: Alle Layer werden durchlaufen...")
    res = run_scan(verbose=True)
    print("\nSignale geschrieben. Stichprobe:")
    for k in list(res.keys())[:5]:
        v = res[k]
        if "error" in v:
            print(f"  {k}: FEHLER {v['error']}")
        else:
            print(f"  {k}: {v['decision']} S={v['S']:+.3f} conf={v['avg_confidence']:.2f}")
