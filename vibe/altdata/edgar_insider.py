"""
Alt-Data-Layer: SEC EDGAR Form 4 Insider-Transaktionen.
Komplett kostenlos, kein API-Key nötig (SEC öffentliche Daten).

Nutzt data.sec.gov: /submissions/CIK{}.json (Filing-Liste) + Form 4 XML.
"""
import os
import re
import time
import json
import urllib.request
import xml.etree.ElementTree as ET

# SEC verlangt eine User-Agent mit Kontakt
USER_AGENT = os.environ.get("SEC_USER_AGENT", "vibe-trading research mohid@example.com")
BASE = "https://data.sec.gov"
ARCHIVES = "https://www.sec.gov/Archives"
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "altdata")
os.makedirs(CACHE_DIR, exist_ok=True)


def _get(url, cache_key=None, timeout=20):
    """GET mit Cache (vermeidet SEC-Rate-Limit)."""
    cache_path = None
    if cache_key:
        cache_path = os.path.join(CACHE_DIR, cache_key + ".json")
        if os.path.exists(cache_path):
            age = time.time() - os.path.getmtime(cache_path)
            if age < 3600:  # 1h Cache
                return json.load(open(cache_path))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read().decode("utf-8", "ignore")
    if cache_path:
        try:
            with open(cache_path, "w") as f:
                json.dump({"url": url, "raw": data}, f)
        except Exception:
            pass
    return data


def _txt(parent, path):
    """Namespace-toleranter Text-Abruf."""
    if parent is None:
        return None
    for el in parent.iter():
        if el.tag.split('}')[-1] == path.split('/')[-1]:
            v = el.find('value')
            if v is not None:
                return v.text
    return None


def _clean(root):
    for el in root.iter():
        if '}' in el.tag:
            el.tag = el.tag.split('}')[-1]
    return root


def cik_lookup(ticker):
    """Ticker -> CIK (via SEC company_tickers.json, gecacht)."""
    cache = os.path.join(CACHE_DIR, "cik_map.json")
    if os.path.exists(cache) and (time.time() - os.path.getmtime(cache)) < 86400 * 7:
        m = json.load(open(cache))
    else:
        raw = _get(BASE + "/company_tickers.json")
        m = json.loads(raw)
        with open(cache, "w") as f:
            json.dump(m, f)
    t = ticker.upper().replace(".", "-")
    for cik, info in m.items():
        if info.get("ticker", "").upper() == t or info.get("ticker", "").upper().replace(".", "-") == t:
            return str(info["cik_str"]).zfill(10)
    return None


def form4_filings(ticker, days=365, max_filings=20):
    """Liste der letzten Form 4 Filings für einen Ticker."""
    cik = cik_lookup(ticker)
    if not cik:
        return []
    raw = _get(f"{BASE}/submissions/CIK{cik}.json", cache_key=f"sub_{cik}")
    d = json.loads(raw)
    recent = d.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accs = recent.get("accessionNumber", [])
    out = []
    for i, f in enumerate(forms):
        if f == "4":
            out.append({"date": dates[i], "accession": accs[i], "cik": cik})
            if len(out) >= max_filings:
                break
    return out


def form4_transactions(ticker, days=365, max_filings=10):
    """Alle Form 4 Transaktionen (Buy/Sell) für einen Ticker, strukturiert."""
    filings = form4_filings(ticker, days=days, max_filings=max_filings)
    txs = []
    for f in filings:
        acc = f["accession"]
        cik = f["cik"]
        url = f"{ARCHIVES}/edgar/data/{int(cik)}/{acc.replace('-', '')}/form4.xml"
        try:
            raw = _get(url, cache_key=f"f4_{cik}_{acc}")
            root = _clean(ET.fromstring(raw))
            issuer = root.find("issuer")
            ticker_txt = _txt(issuer, "issuerTradingSymbol")
            for owner in root.findall("reportingOwner"):
                name = _txt(owner, "reportingOwnerId/rptOwnerName")
                title = _txt(owner, "reportingOwnerRelationship/officerTitle")
                for tx in owner.findall(".//nonDerivativeTransaction"):
                    acq = _txt(tx, "transactionAcquiredDisposedCode")
                    code = _txt(tx, "transactionCode")
                    shares = _txt(tx, "transactionShares")
                    price = _txt(tx, "transactionPricePerShare")
                    date = _txt(tx, "transactionDate")
                    if shares and price and acq:
                        txs.append({
                            "ticker": ticker_txt or ticker.upper(),
                            "insider": name,
                            "role": title,
                            "action": "BUY" if acq == "A" else "SELL",
                            "shares": float(shares),
                            "price": float(price),
                            "value": round(float(shares) * float(price), 2),
                            "date": date,
                            "filing_date": f["date"],
                        })
        except Exception as e:
            continue
    return txs


def insider_activity(ticker, days=365):
    """Aggregiert: Netto-Insider-Aktivität (Käufe - Verkäufe) für einen Ticker."""
    txs = form4_transactions(ticker, days=days)
    buys = sum(t["value"] for t in txs if t["action"] == "BUY")
    sells = sum(t["value"] for t in txs if t["action"] == "SELL")
    net = buys - sells
    return {
        "ticker": ticker.upper(),
        "n_transactions": len(txs),
        "buy_value": round(buys, 2),
        "sell_value": round(sells, 2),
        "net_value": round(net, 2),
        "bullish": net > 0,
        "transactions": txs,
    }


if __name__ == "__main__":
    # Test: AAPL + NVDA
    for t in ["AAPL", "NVDA"]:
        print(f"\n=== {t} Insider (365 Tage) ===")
        try:
            a = insider_activity(t)
            print(f"  Transaktionen: {a['n_transactions']} | Käufe: ${a['buy_value']:,.0f} | Verkäufe: ${a['sell_value']:,.0f} | Netto: ${a['net_value']:,.0f} | Bullish: {a['bullish']}")
            for tx in a["transactions"][:3]:
                print(f"    {tx['date']} {tx['action']} {tx['insider']} ({tx['role']}) {tx['shares']:.0f} @ ${tx['price']:.2f} = ${tx['value']:,.0f}")
        except Exception as e:
            print(f"  Fehler: {e}")
