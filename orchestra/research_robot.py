"""
Research-Roboter 📊 — Analysten-Prognosen, Bewertung & EPS-Schätzungen.

Der Research-Roboter ist eine EIGENSTÄNDIGE Komponente, die dem Risk-Roboter
und dem Conductor Research-Kontext liefert. Er liest echte Daten via yfinance:
  1. ANALYST PRICE TARGETS  : targetMean/High/Low/Median vs. aktueller Preis
  2. RECOMMENDATIONS        : strongBuy/buy/hold/sell/strongSell (20 Analysten)
  3. EARNINGS ESTIMATE      : EPS-Schätzung aktuell vs. Vorjahr (Wachstum)
  4. INFO-KERN              : recommendationMean/Key, numberOfAnalystOpinions

Output: {
  "symbol", "direction": +1/-1/0, "confidence": 0..1,
  "upside_pct": float,           # Kursziel-Upside vs. aktueller Preis
  "recommendation_key": str,     # buy/hold/sell/strong_buy/...
  "recommendation_mean": float,  # 1=strongBuy .. 5=strongSell
  "n_analysts": int,
  "target_mean": float, "target_high": float, "target_low": float,
  "eps_growth": float,           # % EPS-Wachstum aktuelles Jahr vs. Vorjahr
  "reasons": [str]
}
Der Risk-Roboter nutzt das, um Earnings-Vetos mit Research-Kontext zu
kontextualisieren; der Conductor kann es als Verstärker nutzen.
"""
import sys
import re
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestra.logging_setup import log_error

# Yahoo-Finance-RSS-Feed pro Ticker (funktioniert zuverlässiger als t.news)
NEWS_FEED_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region={region}&lang={lang}"


def fetch_headlines(symbol, limit=8, region="US", lang="en-US", timeout=15):
    """
    Holt die letzten Headlines via Yahoo-Finance-RSS-Feed.
    Returns: Liste von Titeln (max `limit`). Leere Liste bei Fehler.
    """
    try:
        url = NEWS_FEED_URL.format(symbol=symbol, region=region, lang=lang)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            xml = resp.read().decode("utf-8", errors="replace")
        titles = re.findall(r"<title>(.*?)</title>", xml, re.S)
        # Erster Title ist der Feed-Name ("... AAPL News"), Rest sind Headlines
        headlines = []
        for t in titles[1:]:
            clean = re.sub(r"<[^>]+>", "", t).strip()
            if clean and len(clean) > 15:
                headlines.append(clean)
            if len(headlines) >= limit:
                break
        return headlines
    except Exception as e:
        log_error(f"news_fetch {symbol}", e)
        return []


# --- Sentiment-Wörterbuch (leicht, datenarm) ---
POSITIVE = {"beat", "surge", "record", "upgrade", "buy", "bullish", "growth", "profit",
            "strong", "rally", "top", "outperform", "wins", "raise", "boost",
            "soar", "jump", "gain", "climb", "rise", "hit", "best", "ahead", "beats"}
NEGATIVE = {"miss", "cut", "downgrade", "sell", "bearish", "drop", "loss", "weak",
            "fall", "plunge", "sink", "slump", "layoff", "probe", "lawsuit", "crash",
            "slip", "slide", "decline", "worst", "warn", "warning", "concern"}


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
    return float(sum(scores) / len(scores)), len(scores)


def news_sentiment(symbol, limit=8):
    """Headlines fetchen + Sentiment berechnen. Returns (sentiment, n_headlines, headlines)."""
    headlines = fetch_headlines(symbol, limit=limit)
    sent, n = headline_sentiment(headlines)
    return sent, n, headlines


def _safe(fn, default=None):
    """yfinance-Aufruf abfangen (Netz/API-Fehler killen nie den Scan)."""
    try:
        return fn()
    except Exception:
        return default


def _to_float(v):
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def assess_research(symbol):
    """
    Komplette Research-Bewertung für ein Symbol.
    Returns dict (siehe Docstring). Bei Fehlern: neutrale Werte.
    """
    import yfinance as yf

    out = {
        "symbol": symbol,
        "direction": 0,
        "confidence": 0.0,
        "upside_pct": None,
        "recommendation_key": None,
        "recommendation_mean": None,
        "n_analysts": 0,
        "target_mean": None,
        "target_high": None,
        "target_low": None,
        "target_current": None,
        "eps_growth": None,
        "news_sentiment": None,
        "n_headlines": 0,
        "headlines": [],
        "reasons": [],
    }

    try:
        # 0. News-Headlines + Sentiment (Yahoo-RSS-Feed)
        sent, n_head, headlines = news_sentiment(symbol)
        out["news_sentiment"] = round(sent, 3)
        out["n_headlines"] = n_head
        out["headlines"] = headlines[:5]
        if headlines:
            out["reasons"].append(
                f"News-Sentiment {sent:+.2f} ({n_head} Headlines)"
            )
            if abs(sent) > 0.3 and out["direction"] == 0:
                out["direction"] = 1 if sent > 0 else -1
                out["confidence"] = max(out["confidence"], min(1.0, abs(sent)))

        t = yf.Ticker(symbol)

        # 1. Analyst Price Targets
        apt = _safe(lambda: t.analyst_price_targets, {}) or {}
        target_mean = _to_float(apt.get("mean"))
        target_high = _to_float(apt.get("high"))
        target_low = _to_float(apt.get("low"))
        target_current = _to_float(apt.get("current"))
        out["target_mean"] = target_mean
        out["target_high"] = target_high
        out["target_low"] = target_low
        out["target_current"] = target_current

        # 2. Recommendations Summary
        rec = _safe(lambda: t.recommendations_summary, None)
        n_analysts = 0
        if rec is not None and len(rec) > 0:
            row = rec.iloc[0]
            for col in ["strongBuy", "buy", "hold", "sell", "strongSell"]:
                if col in rec.columns:
                    try:
                        n_analysts += int(row.get(col, 0) or 0)
                    except (TypeError, ValueError):
                        pass
        out["n_analysts"] = n_analysts

        # 3. Info-Kern (recommendationMean/Key, aktueller Preis)
        info = _safe(lambda: t.info, {}) or {}
        rec_mean = _to_float(info.get("recommendationMean"))
        rec_key = info.get("recommendationKey")
        out["recommendation_mean"] = rec_mean
        out["recommendation_key"] = rec_key
        current = _to_float(info.get("currentPrice")) or _to_float(info.get("regularMarketPrice"))
        if current is None:
            current = target_current

        # 4. Earnings Estimate (EPS-Wachstum aktuelles JAHR vs. Vorjahr)
        # Bevorzuge die Zeile mit period == "0y" (Jahr). `period` ist der Index,
        # nicht zwingend eine Spalte — beides prüfen.
        ee = _safe(lambda: t.earnings_estimate, None)
        eps_growth = None
        if ee is not None and len(ee) > 0:
            try:
                row0 = ee.iloc[0]
                # Index-basierte Suche nach "0y"
                idx_vals = [str(v).strip() for v in ee.index]
                for pos, p in enumerate(idx_vals):
                    if p in ("0y", "0Y"):
                        row0 = ee.iloc[pos]
                        break
                # Fallback: Spalte "period" falls vorhanden
                if "period" in ee.columns:
                    for idx, period in enumerate(ee["period"]):
                        if str(period).strip() in ("0y", "0Y"):
                            row0 = ee.iloc[idx]
                            break
                avg = _to_float(row0.get("avg"))
                ago = _to_float(row0.get("yearAgoEps"))
                if avg and ago:
                    eps_growth = (avg - ago) / abs(ago) * 100.0
            except (KeyError, IndexError, TypeError):
                pass
        out["eps_growth"] = eps_growth

        # 5. Upside & Richtung/Konfidenz
        if target_mean and current:
            upside = (target_mean - current) / current * 100.0
            out["upside_pct"] = round(upside, 2)
            if upside > 5:
                out["direction"] = 1
                out["confidence"] = max(out["confidence"], min(1.0, upside / 50.0))
                out["reasons"].append(
                    f"Analysten-Ziel {target_mean:.2f} vs. Kurs {current:.2f} = +{upside:.1f}% Upside"
                )
            elif upside < -5:
                out["direction"] = -1
                out["confidence"] = max(out["confidence"], min(1.0, abs(upside) / 50.0))
                out["reasons"].append(
                    f"Analysten-Ziel {target_mean:.2f} vs. Kurs {current:.2f} = {upside:.1f}% Downside"
                )
            else:
                out["reasons"].append(
                    f"Analysten-Ziel {target_mean:.2f} vs. Kurs {current:.2f} = {upside:+.1f}% (neutral)"
                )

        # Empfehlungs-Key verstärkt Richtung
        if rec_key:
            key_map = {
                "strong_buy": 1, "buy": 1, "hold": 0,
                "sell": -1, "strong_sell": -1,
            }
            kd = key_map.get(str(rec_key).lower())
            if kd is not None and kd != 0 and out["direction"] == 0:
                out["direction"] = kd
                out["confidence"] = max(out["confidence"], 0.4)
            out["reasons"].append(
                f"Empfehlung: {rec_key} (Mean {rec_mean if rec_mean else 'n/a'}, {n_analysts} Analysten)"
            )

        # EPS-Wachstum als Bestätigung
        if eps_growth is not None:
            out["reasons"].append(
                f"EPS-Wachstum {eps_growth:+.1f}% (aktuelles Jahr vs. Vorjahr)"
            )
            if eps_growth > 10 and out["direction"] == 0:
                out["direction"] = 1
                out["confidence"] = max(out["confidence"], 0.3)

    except Exception as e:
        log_error(f"research {symbol}", e)
        out["reasons"].append(f"Research-Fehler: {e}")

    return out


if __name__ == "__main__":
    print("RESEARCH-ROBOTER Testlauf:")
    for sym in ["MBG.DE", "AAPL", "NVDA"]:
        r = assess_research(sym)
        print(f"\n=== {sym} ===")
        print(f"  Richtung: {r['direction']:+d} | Konfidenz: {r['confidence']:.2f} | Upside: {r['upside_pct']}%")
        print(f"  Empfehlung: {r['recommendation_key']} (Mean {r['recommendation_mean']}) | {r['n_analysts']} Analysten")
        print(f"  Ziel: {r['target_mean']} (High {r['target_high']} / Low {r['target_low']}) | EPS-Growth: {r['eps_growth']}%")
        print(f"  News-Sentiment: {r['news_sentiment']} ({r['n_headlines']} Headlines)")
        if r.get("headlines"):
            for h in r["headlines"][:3]:
                print(f"      📰 {h[:80]}")
        for reason in r["reasons"]:
            print(f"    📊 {reason}")
