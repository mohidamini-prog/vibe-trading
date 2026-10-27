import sys
import os

# Füge den engine-Ordner explizit zum Python-Pfad hinzu
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'engine'))
from sec_edgar import SecEdgarClient

def run_sec_pipeline():
    print("=== VIBE TRADING: SEC EDGAR SCANNER ===")
    client = SecEdgarClient()
    
    # Beispiel-Universe für den Scan
    watchlist = ["AAPL", "TSLA", "NVDA", "MSFT"]
    
    for ticker in watchlist:
        print(f"\nAnalysiere {ticker}...")
        insider = client.get_recent_insider_trades(ticker, limit=3)
        if insider:
            print(f" -> {insider['name']} (CIK: {insider['cik']})")
            for _, row in insider['trades'].iterrows():
                print(f"    [Form {row['form']}] gemeldet am {row['filingDate']} -> {row['sec_url']}")
        else:
            print(f" -> Keine aktuellen Insider-Daten gefunden.")

if __name__ == "__main__":
    run_sec_pipeline()
