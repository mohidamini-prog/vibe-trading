"""
Alt-Data-Layer: SEC EDGAR Form 4 Insider-Transactions.
Komplett kostenlos, kein API-Key nötig (SEC öffentliche Daten).

Nutzt data.sec.gov: /submissions/CIK{}.json (Filing-Liste) + Form 4 XML.
"""
import os
import re
import time
import json
import urllib.request
import xml.etree.ElementTree as ET

USER_AGENT = os.environ.get("SEC_USER_AGENT", "vibe-trading research mohid@example.com")
BASE = "https://www.sec.gov"
DATA_BASE = "https://data.sec.gov"
ARCHIVES = "https://www.sec.gov/Archives"
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "altdata")
os.makedirs(CACHE_DIR, exist_ok=True)


def _get(url, cache_key=None, timeout=20):
    cache_path = None
    if cache_key:
        cache_path = os.path.join(CACHE_DIR, cache_key + ".json")
        if os.path.exists(cache_path):
            age = time.time() - os.path.getmtime(cache_path)
            if age < 3600:  # 1h Cache
                cached = json.load(open(cache_path))
                if isinstance(cached, dict) and "raw" in cached:
                    return cached["raw"]
                return cached
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


def _clean(root):
    for el in root.iter():
        if '}' in el.tag:
            el.tag = el.tag.split('}')[-1]
    return root


def cik_lookup(ticker):
    cache = os.path.join(CACHE_DIR, "cik_map.json")
    if os.path.exists(cache) and (time.time() - os.path.getmtime(cache)) < 86400 * 7:
        m = json.load(open(cache))
    else:
        raw = _get(BASE + "/files/company_tickers.json")
        m = json.loads(raw)
        with open(cache, "w") as f:
            json.dump(m, f)
    t = ticker.upper().replace(".", "-")
    for cik, info in m.items():
        if info.get("ticker", "").upper() == t or info.get("ticker", "").upper().replace(".", "-") == t:
            return str(info["cik_str"]).zfill(10)
    return None


def form4_filings(ticker, days=365, max_filings=40):
    cik = cik_lookup(ticker)
    if not cik:
        return []
    raw = _get(f"{DATA_BASE}/submissions/CIK{cik}.json", cache_key=f"sub_{cik}")
    d = json.loads(raw)
    recent = d.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accs = recent.get("accessionNumber", [])
    docs = recent.get("primaryDocument", [])
    out = []
    for i, f in enumerate(forms):
        if f in ("4", "4/A"):
            doc = docs[i] if i < len(docs) else "form4.xml"
            # If doc is xslF345X06/... or similar, the raw XML is usually named differently or we can try form4.xml or check filename
            # Actually SEC filing archives have the exact primaryDocument filename, e.g. wk-form4_1791579847.xml or form4.xml
            out.append({"date": dates[i], "accession": accs[i], "doc": doc, "cik": cik})
            if len(out) >= max_filings:
                break
    return out


def form4_transactions(ticker, days=365, max_filings=20):
    filings = form4_filings(ticker, days=days, max_filings=max_filings)
    txs = []
    for f in filings:
        acc = f["accession"]
        cik = f["cik"]
        doc = f["doc"]
        acc_no_dash = acc.replace('-', '')
        
        # Try primaryDocument first, fallback to form4.xml
        urls = [
            f"{ARCHIVES}/edgar/data/{int(cik)}/{acc_no_dash}/{doc}",
            f"{ARCHIVES}/edgar/data/{int(cik)}/{acc_no_dash}/form4.xml"
        ]
        raw = None
        for url in urls:
            try:
                raw = _get(url, cache_key=f"f4_{cik}_{acc}_{os.path.basename(doc)}")
                if raw and "<ownershipDocument>" in raw:
                    break
            except Exception:
                continue
        
        if not raw:
            continue

        try:
            root = _clean(ET.fromstring(raw))

            def _val(el):
                if el is None:
                    return None
                for v in el.iter():
                    if v.tag.split('}')[-1] == 'value' and v.text and v.text.strip():
                        return v.text.strip()
                if el.text and el.text.strip():
                    return el.text.strip()
                return None

            def _first_tag(tag):
                for el in root.iter():
                    if el.tag.split('}')[-1] == tag:
                        return _val(el)
                return None

            issuer_name = _first_tag("issuerName")
            issuer_symbol = _first_tag("issuerTradingSymbol")

            for owner in root.iter():
                if owner.tag.split('}')[-1] != "reportingOwner":
                    continue
                name = None
                title = None
                for el in owner.iter():
                    tag = el.tag.split('}')[-1]
                    if tag == 'rptOwnerName' and name is None:
                        name = _val(el)
                    if tag == 'officerTitle' and title is None:
                        title = _val(el)

            # Strukturiertes Parsen über nonDerivativeTable
            nd_table = root.find('nonDerivativeTable')
            if nd_table is not None:
                for tx in nd_table.findall('nonDerivativeTransaction'):
                    code, shares, price, acq, date = None, None, None, None, None
                    
                    tc = tx.find('transactionCoding')
                    if tc is not None:
                        c_el = tc.find('transactionCode')
                        if c_el is not None:
                            code = c_el.text
                    
                    td = tx.find('transactionDate')
                    if td is not None:
                        v_el = td.find('value')
                        if v_el is not None:
                            date = v_el.text

                    ta = tx.find('transactionAmounts')
                    if ta is not None:
                        sh_el = ta.find('transactionShares/value')
                        if sh_el is not None:
                            shares = sh_el.text
                        else:
                            # fallback iter
                            for el in ta.iter():
                                if el.tag.split('}')[-1] == 'transactionShares':
                                    for sub in el.iter():
                                        if sub.tag.split('}')[-1] == 'value':
                                            shares = sub.text
                        
                        pr_el = ta.find('transactionPricePerShare/value')
                        if pr_el is not None:
                            price = pr_el.text
                        else:
                            for el in ta.iter():
                                if el.tag.split('}')[-1] == 'transactionPricePerShare':
                                    for sub in el.iter():
                                        if sub.tag.split('}')[-1] == 'value':
                                            price = sub.text

                        ad_el = ta.find('transactionAcquiredDisposedCode/value')
                        if ad_el is not None:
                            acq = ad_el.text
                        else:
                            for el in ta.iter():
                                if el.tag.split('}')[-1] == 'transactionAcquiredDisposedCode':
                                    for sub in el.iter():
                                        if sub.tag.split('}')[-1] == 'value':
                                            acq = sub.text

                    if shares and acq and code in ('P', 'S', 'A', 'M'):
                        try:
                            sh_float = float(shares)
                            pr_float = float(price) if price else 0.0
                            val = sh_float * pr_float
                            if code in ('P', 'A') or (code == 'M' and acq == 'A'):
                                action = "BUY"
                            elif code == 'S' or acq == 'D':
                                action = "SELL"
                            else:
                                continue

                            txs.append({
                                "ticker": issuer_symbol or ticker.upper(),
                                "issuer": issuer_name,
                                "insider": name,
                                "role": title,
                                "action": action,
                                "code": code,
                                "shares": sh_float,
                                "price": pr_float,
                                "value": round(val, 2),
                                "date": date,
                                "filing_date": f["date"],
                            })
                        except Exception:
                            continue
        except Exception:
            continue
    return txs


def insider_activity(ticker, days=365):
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
    for t in ["AAPL", "NVDA"]:
        print(f"\n=== {t} Insider (365 Tage) ===")
        a = insider_activity(t)
        print(f"  Transaktionen: {a['n_transactions']} | Käufe: ${a['buy_value']:,.0f} | Verkäufe: ${a['sell_value']:,.0f} | Netto: ${a['net_value']:,.0f} | Bullish: {a['bullish']}")
        for tx in a['transactions'][:5]:
            print(f"    {tx['date']} [{tx['code']}] {tx['action']} {tx['insider']} ({tx['role'] or 'Insider'}) {tx['shares']:,.0f} @ ${tx['price']:.2f} = ${tx['value']:,.0f}")
