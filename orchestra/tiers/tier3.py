"""
Tier 3 — BEILAGE (15%), nur als Filter, läuft 1x pro Stunde.

News-Headline-Sentiment [-1, +1], nur Titel (kein Volltext).
Earnings-Kalender (heute/morgen ja/nein). SEC EDGAR Insider-Cluster (Form 4).
"""
from orchestra.config import get, load_config
from orchestra.config import paths
import json, re
from datetime import datetime, timedelta


# --- Sentiment-Wörterbuch (leicht, datenarm) ---
POSITIVE = {"beat", "surge", "record", "upgrade", "buy", "bullish", "growth", "profit",
            "strong", "rally", "top", "outperform", "wins", "raise", "boost"}
NEGATIVE = {"miss", "cut", "downgrade", "sell", "bearish", "drop", "loss", "weak",
            "fall", "plunge", "sink", "slump", "layoff", "probe", "lawsuit", "crash"}


def headline_sentiment(headlines):
    """Nur Titel. [-1, +1] pro Headline, gemittelt. Kein Volltext."""
    if not headlines:
        return 0.0, 0
    scores = []
    for h in headlines:
        words = re.findall(r"[a-z]+", h.lower())
        pos = sum(1 for w in words if w in POSITIVE)
        neg = sum(1 for w in words if w in NEGATIVE)
        if pos + neg > 0:
            scores.append((pos - neg) / (pos + neg))
    if not scores:
        return 0.0, 0
    return float(np_mean(scores)), len(scores)


def np_mean(x):
    return sum(x) / len(x)


# --- Earnings-Kalender (vereinfacht: aus Konfiguration, echte Quelle später) ---
def earnings_risk(symbol, days_ahead=None):
    days_ahead = days_ahead or get("agents.news.earnings_days_ahead", 1)
    # TODO: echte Earnings-Datenquelle anbinden (z.B. Alpaca Calendar)
    return {"earnings_soon": False, "days": None}


# --- SEC EDGAR Insider-Cluster (Form 4) ---
def insider_signal(symbol, window_days=None, min_cluster=None):
    """Nutzt vorhandenes vibe/altdata/edgar_insider.py. Cluster-Buy/Sell erkennen."""
    window_days = window_days or get("agents.news.insider_cluster_days", 7)
    min_cluster = min_cluster or get("agents.news.insider_cluster_min", 3)
    if not paths.EDGAR_SCRIPT.exists():
        return {"cluster": False, "direction": 0, "count": 0}
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("edgar", str(paths.EDGAR_SCRIPT))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # Falls das Skript eine Funktion liefert; sonst Datei-basiert
        if hasattr(mod, "recent_filings"):
            filings = mod.recent_filings(symbol, days=window_days)
            buys = sum(1 for f in filings if f.get("action") == "buy")
            sells = sum(1 for f in filings if f.get("action") == "sell")
            count = max(buys, sells)
            if count >= min_cluster:
                return {"cluster": True, "direction": 1 if buys > sells else -1, "count": count}
    except Exception:
        pass
    return {"cluster": False, "direction": 0, "count": 0}


def fetch_tier3(symbol, headlines=None):
    """Tier 3: News-Sentiment + Earnings + EDGAR-Cluster. Nur als Filter."""
    sentiment, n = headline_sentiment(headlines or [])
    earn = earnings_risk(symbol)
    ins = insider_signal(symbol)
    return {
        "symbol": symbol,
        "sentiment": round(sentiment, 3),
        "n_headlines": n,
        "earnings_soon": earn["earnings_soon"],
        "insider_cluster": ins["cluster"],
        "insider_direction": ins["direction"],
        "insider_count": ins["count"],
        "veto": earn["earnings_soon"],   # Earnings => Veto
    }


if __name__ == "__main__":
    t = fetch_tier3("AAPL", headlines=["Apple beats earnings, stock surges",
                                        "Apple faces antitrust probe"])
    print(json.dumps(t, indent=2))
