"""
Alpaca-Anbindung für US-Aktien.

Zwei Funktionen:
  1. Daten (Layer 0 Erweiterung): Echtzeit-OHLCV für US-Aktien von Alpaca.
     Alpaca liefert sauberere, aktuellere Daten als yfinance (Echtzeit, Pre/After-Market).
  2. Paper-Trading: Der Orchestrator gibt Signale -> Alpaca führt sie SIMULIERT aus
     (0$ Risiko) -> wir messen echte Performance gegen den Markt.

API-Key wird aus ~/.hermes/.env (ALPACA_API_KEY, ALPACA_SECRET_KEY) oder aus
orchestra/config/alpaca.json gelesen. Paper-Basis-URL ist Standard (kein echtes Geld).

Setup:
  1. Kostenlosen Paper-Account anlegen: https://app.alpaca.markets/paper
  2. API-Key + Secret kopieren
  3. In ~/.hermes/.env eintragen:
       ALPACA_API_KEY=PK...
       ALPACA_SECRET_KEY=...
"""
import sys
import os
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_keys():
    """Liest API-Key aus .env oder config/alpaca.json."""
    # 1. Env-Variablen
    api_key = os.environ.get("ALPACA_API_KEY")
    secret = os.environ.get("ALPACA_SECRET_KEY")
    if api_key and secret:
        return api_key, secret
    # 2. ~/.hermes/.env
    env_file = Path.home() / ".hermes" / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("ALPACA_API_KEY="):
                api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("ALPACA_SECRET_KEY="):
                secret = line.split("=", 1)[1].strip().strip('"').strip("'")
    if api_key and secret:
        return api_key, secret
    # 3. config/alpaca.json
    cfg_file = Path(__file__).parent.parent / "config" / "alpaca.json"
    if cfg_file.exists():
        cfg = json.loads(cfg_file.read_text())
        return cfg.get("api_key"), cfg.get("secret_key")
    return None, None


def is_configured():
    api_key, _ = _load_keys()
    return bool(api_key)


def _headers():
    api_key, secret = _load_keys()
    if not api_key:
        return None
    return {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": secret,
    }


# ---------------- DATA (Echtzeit-OHLCV für US-Aktien) ----------------
def fetch_bars(symbol, timeframe="1Day", limit=300, feed="iex"):
    """
    Holt OHLCV-Bars von Alpaca.
    timeframe: "1Min","5Min","15Min","1Hour","4Hour","1Day"
    feed: "iex" (kostenlos) oder "sip" (Echtzeit-Stream).
    Returns: list[dict] mit {t,o,h,l,c,v} oder None.
    """
    import requests
    h = _headers()
    if not h:
        return {"error": "Alpaca nicht konfiguriert — Key in ~/.hermes/.env eintragen"}
    base = "https://data.alpaca.markets/v2"
    # 4Hour unterstützt Alpaca nicht als "4Hour" — wir nehmen 1Hour und gruppieren (oder "1Day")
    if timeframe == "4Hour":
        timeframe = "1Hour"
    url = f"{base}/stocks/{symbol}/bars"
    params = {"timeframe": timeframe, "limit": limit, "feed": feed, "adjustment": "all"}
    try:
        r = requests.get(url, headers=h, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        bars = data.get("bars", [])
        return bars
    except Exception as e:
        return {"error": str(e)}


# ---------------- PAPER TRADING (simuliert, 0$ Risiko) ----------------
def get_account():
    """Aktuelles Paper-Konto (Cash, Equity, Kaufkraft)."""
    import requests
    h = _headers()
    if not h:
        return {"error": "Alpaca nicht konfiguriert"}
    try:
        r = requests.get("https://paper-api.alpaca.markets/v2/account", headers=h, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def submit_order(symbol, qty, side, order_type="market", time_in_force="day"):
    """
    Paper-Order senden.
    side: "buy" oder "sell".
    Returns: Order-Bestätigung oder error.
    """
    import requests
    h = _headers()
    if not h:
        return {"error": "Alpaca nicht konfiguriert"}
    payload = {
        "symbol": symbol, "qty": str(qty), "side": side,
        "type": order_type, "time_in_force": time_in_force,
    }
    try:
        r = requests.post("https://paper-api.alpaca.markets/v2/orders",
                          headers=h, json=payload, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def get_positions():
    """Offene Paper-Positionen."""
    import requests
    h = _headers()
    if not h:
        return {"error": "Alpaca nicht konfiguriert"}
    try:
        r = requests.get("https://paper-api.alpaca.markets/v2/positions", headers=h, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


# ---------------- Orchestrator-Anbindung ----------------
def apply_decision_to_paper(decision, symbol, qty=10):
    """
    Nimmt eine Conductor/LayerDecision und setzt sie als Paper-Order um.
    decision: "BUY" | "SELL" | "HOLD"
    """
    if decision == "BUY":
        return submit_order(symbol, qty, "buy")
    elif decision == "SELL":
        return submit_order(symbol, qty, "sell")
    return {"decision": "HOLD", "action": "none"}


if __name__ == "__main__":
    if not is_configured():
        print("⚠️  Alpaca NICHT konfiguriert.")
        print("    So geht's (kostenlos, Paper = kein echtes Geld):")
        print("    1. Account: https://app.alpaca.markets/paper")
        print("    2. API-Key + Secret kopieren")
        print("    3. In ~/.hermes/.env eintragen:")
        print("       ALPACA_API_KEY=PK...")
        print("       ALPACA_SECRET_KEY=...")
    else:
        print("Alpaca konfiguriert ✓")
        acct = get_account()
        if "error" not in acct:
            print(f"  Cash: ${float(acct.get('cash', 0)):.2f} | Equity: ${float(acct.get('equity', 0)):.2f}")
        else:
            print("  Account-Fehler:", acct["error"])
