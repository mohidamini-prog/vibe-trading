import urllib.request
import json
import pandas as pd

class SecEdgarClient:
    def __init__(self, user_agent: str = "VibeTradingResearch admin@vibe-trading.local"):
        self.user_agent = user_agent
        self.headers = {'User-Agent': user_agent}
        self.ticker_to_cik = self._load_ticker_mapping()

    def _load_ticker_mapping(self):
        url = "https://www.sec.gov/files/company_tickers.json"
        req = urllib.request.Request(url, headers=self.headers)
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
                mapping = {}
                for item in data.values():
                    ticker = item['ticker'].upper()
                    cik = str(item['cik_str']).zfill(10)
                    mapping[ticker] = {
                        'cik': cik,
                        'title': item['title']
                    }
                return mapping
        except Exception as e:
            print(f"Warnung: Konnte Ticker-Mapping nicht laden: {e}")
            return {}

    def get_cik_for_ticker(self, ticker: str):
        return self.ticker_to_cik.get(ticker.upper(), {}).get('cik')

    def get_company_filings(self, ticker_or_cik: str, form_filter=None):
        cik = self.get_cik_for_ticker(ticker_or_cik) if not ticker_or_cik.isdigit() else ticker_or_cik.zfill(10)
        if not cik:
            print(f"Keine CIK gefunden für {ticker_or_cik}")
            return None

        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        req = urllib.request.Request(url, headers=self.headers)
        
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
                recent = data.get('filings', {}).get('recent', {})
                
                df = pd.DataFrame({
                    'form': recent.get('form', []),
                    'filingDate': recent.get('filingDate', []),
                    'reportDate': recent.get('reportDate', []),
                    'acceptanceDateTime': recent.get('acceptanceDateTime', []),
                    'accessionNumber': recent.get('accessionNumber', []),
                    'primaryDocument': recent.get('primaryDocument', [])
                })
                
                if form_filter:
                    df = df[df['form'].isin(form_filter)]
                
                return {
                    'name': data.get('name'),
                    'cik': cik,
                    'tickers': data.get('tickers'),
                    'filings': df
                }
        except Exception as e:
            print(f"Fehler beim Abrufen der SEC-Filings für {ticker_or_cik}: {e}")
            return None

    def get_recent_insider_trades(self, ticker_or_cik: str, limit: int = 20):
        """
        Holt die neuesten Form-4 Meldungen (Insider Transaktionen: Kauf/Verkauf).
        Da Form-4 XML-Daten direkt enthält oder verlinkt, listen wir hier 
        die Einreichungen mit Datum, accessionNumber und Dokumenten-Link.
        """
        result = self.get_company_filings(ticker_or_cik, form_filter=['4'])
        if not result or result['filings'].empty:
            return None
            
        df = result['filings'].head(limit).copy()
        # Hilfreicher Link direkt zum SEC-Dokument
        # Format: https://www.sec.gov/Archives/edgar/data/{cik}/{accessionNumber_ohne_Bindestriche}/{primaryDocument}
        cik_clean = result['cik'].lstrip('0')
        links = []
        for _, row in df.iterrows():
            acc_no_clean = row['accessionNumber'].replace('-', '')
            doc = row['primaryDocument']
            link = f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{acc_no_clean}/{doc}"
            links.append(link)
            
        df['sec_url'] = links
        return {
            'name': result['name'],
            'cik': result['cik'],
            'trades': df
        }

if __name__ == "__main__":
    client = SecEdgarClient()
    print("Teste Insider-Trades Abruf für NVDA (NVIDIA)...")
    insider_data = client.get_recent_insider_trades("NVDA", limit=5)
    if insider_data:
        print(f"\nFirma: {insider_data['name']}")
        print(insider_data['trades'][['filingDate', 'form', 'sec_url']])
