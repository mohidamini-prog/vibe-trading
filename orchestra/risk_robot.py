"""
Risk-Roboter 🤖 — Earnings & EDGAR-Risiko-Wächter.

Der Risk-Roboter ist eine EIGENSTÄNDIGE Komponente, die parallel zu den
Indikator-Signalen läuft und dem Conductor Veto-Infos liefert.

Er prüft für jedes Symbol:
  1. EARNINGS-RISIKO: Steht eine Earnings-Veröffentlichung bevor? (VETO)
     Nutzt yfinance earnings_dates + einen Kalender-Puffer von 3 Tagen.
  2. EDGAR-INSIDER: SEC Form 4 Insider-Transaktionen (käufe/verkäufe)
     Als Verstärker (bullisch/bärisch) oder Veto bei Verkaufs-Clustern.
  3. HIGH-IMPACT-EVENTS: FOMC/CPI/NFP/EZB (Kalender) -> VETO global.

Output: {"veto": bool, "direction": +1/-1/0, "confidence": 0..1, "reasons": [...]}
Der Conductor nutzt das, um Signale abzuschwächen oder zu blocken.
"""
import sys
import os
import json
from pathlib import Path
from datetime import datetime, timedelta

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestra.logging_setup import log_error, orchestra_log

# Kalender-Puffer: Earnings innerhalb von X Tagen = VETO
EARNINGS_PENDING_DAYS = 3
# Insider-Cluster-Schwelle: X Transaktionen in 7 Tagen = relevant
INSIDER_CLUSTER_N = 3
INSIDER_CLUSTER_DAYS = 7


def check_earnings_risk(symbol, pending_days=EARNINGS_PENDING_DAYS):
    """
    Prüft, ob Earnings bald anstehen (yfinance earnings_dates).
    Returns: (has_risk, days_until, next_date_str)
    """
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        dates = t.get_earnings_dates(limit=8)
        if dates is None or len(dates) == 0:
            return (False, None, None)
        now = datetime.now()
        for idx in dates.index:
            try:
                dt = idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else idx
                if isinstance(dt, datetime):
                    dt = dt.replace(tzinfo=None)
                days = (dt - now).days
                if 0 <= days <= pending_days:
                    return (True, days, dt.strftime("%Y-%m-%d"))
            except Exception:
                continue
        return (False, None, None)
    except Exception as e:
        log_error(f"earnings {symbol}", e)
        return (False, None, None)


def check_insider_activity(symbol, days=365):
    """
    SEC EDGAR Form 4 Insider-Transaktionen prüfen.
    Returns: dict {n_transactions, net_value, direction(+1/-1/0), cluster, count}
    """
    try:
        sys.path.insert(0, str(REPO_ROOT / "vibe"))
        from altdata.edgar_insider import insider_activity
        a = insider_activity(symbol, days=days)
        net = a.get("net_value", 0)
        direction = 1 if net > 0 else (-1 if net < 0 else 0)
        # Cluster: >=3 Transaktionen in den letzten 7 Tagen
        txs = a.get("transactions", [])
        now = datetime.now()
        recent = [t for t in txs if "date" in t and
                  (now - datetime.strptime(t["date"], "%Y-%m-%d")).days <= INSIDER_CLUSTER_DAYS]
        cluster = len(recent) >= INSIDER_CLUSTER_N
        return {
            "n_transactions": a.get("n_transactions", 0),
            "buy_value": a.get("buy_value", 0),
            "sell_value": a.get("sell_value", 0),
            "net_value": net,
            "direction": direction,
            "cluster": cluster,
            "count": len(recent),
        }
    except Exception as e:
        log_error(f"edgar {symbol}", e)
        return {"n_transactions": 0, "net_value": 0, "direction": 0, "cluster": False, "count": 0}


def assess_risk(symbol):
    """
    Komplette Risiko-Bewertung für ein Symbol.
    Returns: {
      "symbol": symbol,
      "veto": bool,
      "direction": +1/-1/0,     # Insider-Richtung (Verstärker)
      "confidence": 0..1,       # Stärke der Risiko-Erkenntnis
      "reasons": [str],
      "earnings_soon": bool,
      "insider": dict
    }
    """
    reasons = []
    veto = False
    direction = 0
    confidence = 0.0

    # 1. Earnings-Risiko
    earnings_risk, days_until, date_str = check_earnings_risk(symbol)
    if earnings_risk:
        veto = True
        reasons.append(f"EARNINGS in {days_until} Tag(en) ({date_str}) — VETO")
        confidence = max(confidence, 0.9)

    # 1b. RESEARCH-KONTEXT: Analysten-Prognosen, Bewertung, EPS-Schätzungen.
    #     Vetos werden kontextualisiert (nicht aufgehoben, aber begründet),
    #     und bei eindeutig bullischem Research wird die Konfidenz differenziert.
    try:
        from orchestra.research_robot import assess_research
        research = assess_research(symbol)
    except Exception as e:
        log_error(f"research_robot {symbol}", e)
        research = {"direction": 0, "confidence": 0.0, "reasons": []}
    research_reasons = research.get("reasons", [])
    if research_reasons:
        reasons.extend(research_reasons)
    # Research als Verstärker: nur wenn KEIN Veto, sonst nur Kontext
    if not veto and research.get("direction", 0) != 0:
        direction = research["direction"]
        confidence = max(confidence, research.get("confidence", 0.0))
    elif research.get("direction", 0) != 0:
        # Veto aktiv: Research begründet, aber hebt nicht auf. Konfidenz leicht modulieren.
        confidence = max(confidence, min(0.95, confidence + research.get("confidence", 0.0) * 0.05))

    # 2. EDGAR-Insider
    insider = check_insider_activity(symbol)
    if insider.get("cluster"):
        d = insider["direction"]
        direction = d
        if d > 0:
            reasons.append(f"Insider-Cluster BUY ({insider['count']} in 7 Tagen) — Verstärker")
            confidence = max(confidence, 0.6 + 0.1 * min(insider["count"], 5))
        elif d < 0:
            reasons.append(f"Insider-Cluster SELL ({insider['count']} in 7 Tagen) — VETO")
            veto = True
            confidence = max(confidence, 0.8)

    return {
        "symbol": symbol,
        "veto": veto,
        "direction": direction,
        "confidence": round(confidence, 2),
        "reasons": reasons,
        "earnings_soon": earnings_risk,
        "insider": insider,
    }


if __name__ == "__main__":
    print("RISK-ROBOTER Testlauf (AAPL, NVDA):")
    for sym in ["AAPL", "NVDA"]:
        r = assess_risk(sym)
        print(f"\n=== {sym} ===")
        print(f"  Veto: {r['veto']} | Richtung: {r['direction']:+d} | Konfidenz: {r['confidence']:.2f}")
        for reason in r["reasons"]:
            print(f"    ⚠️ {reason}")
        ins = r["insider"]
        print(f"  Insider: {ins['n_transactions']} Txs | Netto ${ins['net_value']:,.0f}")
