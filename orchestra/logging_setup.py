"""
Zentrales Logging-System für das Vibe-Trading Orchester.

Speichert ALLES:
  - logs/orchestra.log      : Hauptlog (Entscheidungen, Fehler, System)
  - logs/trades.log         : Jede Paper-Order + Position
  - logs/signals.log        : Jedes Signal (Modell, a, conf, reason)
  - logs/errors.log         : Nur Fehler (schnelles Debugging)

Log-Rotation: automatisch bei 5MB (älteste behalten wir).
Alle Layer + Broker + Orchestrator loggen hierher — ein einziger Ort für alles.
"""
import sys
import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Log-Verzeichnis unter orchestra/logs
LOGS_DIR = Path(__file__).resolve().parent / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Standard-Format: Zeit | Level | Modul | Nachricht
FMT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
DATE_FMT = "%Y-%m-%d %H:%M:%S"


def _get_logger(name, filename, level=logging.INFO):
    """Erstellt/liest einen RotatingFileLogger für eine Datei."""
    logger = logging.getLogger(f"vibe.{name}")
    if not logger.handlers:  # nur einmal Handler hinzufügen
        logger.setLevel(level)
        handler = RotatingFileHandler(
            LOGS_DIR / filename, maxBytes=5 * 1024 * 1024,
            backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter(FMT, DATE_FMT))
        logger.addHandler(handler)
        # Auch auf Konsole (wenn -v)
        if "-v" in sys.argv or "--verbose" in sys.argv:
            console = logging.StreamHandler()
            console.setFormatter(logging.Formatter(FMT, DATE_FMT))
            logger.addHandler(console)
    return logger


# Singleton-Logger
_orchestra = None
_trades = None
_signals = None
_errors = None


def orchestra_log():
    global _orchestra
    if _orchestra is None:
        _orchestra = _get_logger("orchestra", "orchestra.log")
    return _orchestra


def trades_log():
    global _trades
    if _trades is None:
        _trades = _get_logger("trades", "trades.log")
    return _trades


def signals_log():
    global _signals
    if _signals is None:
        _signals = _get_logger("signals", "signals.log")
    return _signals


def errors_log():
    global _errors
    if _errors is None:
        _errors = _get_logger("errors", "errors.log", level=logging.ERROR)
    return _errors


# --- Komfort-Funktionen ---
def log_decision(symbol, timeframe, decision, S, strength, avg_conf):
    """Entscheidung loggen."""
    orchestra_log().info(
        f"ENTSCHEIDUNG {symbol} [{timeframe}] -> {decision} | S={S:+.3f} | "
        f"Stärke={strength:.3f} | avg_conf={avg_conf:.2f}"
    )


def log_signal(symbol, timeframe, model, a, conf, reason):
    """Einzelnes Signal loggen."""
    signals_log().info(
        f"{symbol} [{timeframe}] {model}: a={a:+d} conf={conf:.2f} | {reason}"
    )


def log_trade(symbol, side, qty, order_id, status, price=None, extra=None):
    """Paper-Order loggen."""
    msg = f"ORDER {symbol} {side.upper()} qty={qty} | id={order_id} status={status}"
    if price:
        msg += f" price={price}"
    if extra:
        msg += f" | {extra}"
    trades_log().info(msg)


def log_error(where, error):
    """Fehler loggen (in errors.log + orchestra.log)."""
    errors_log().error(f"{where}: {error}")
    orchestra_log().error(f"{where}: {error}")


if __name__ == "__main__":
    log_decision("AAPL", "1d", "BUY", 0.62, 0.41, 0.66)
    log_signal("AAPL", "1d", "new_52w_high_momentum", 1, 0.81, "52W-High Ausbruch (MACD+, Vol 1.8x)")
    log_trade("AAPL", "buy", 10, "ec4c5899", "accepted", price=347.10)
    log_error("Test", "Das ist ein Testfehler")
    print("Logs geschrieben nach:", LOGS_DIR)
    for f in sorted(LOGS_DIR.glob("*.log")):
        print(f"  {f.name} ({f.stat().st_size} bytes)")
