import yfinance as pd_yf
import pandas as pd
import numpy as np

def scan_german_stocks(tickers, period="1y"):
    print(f"--- Pattern Scan Deutsche Aktien ({period}) ---")
    results = {}
    
    for ticker in tickers:
        data = pd_yf.download(ticker, period=period, interval="1d", progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(1)
            
        o, h, l, c = data['Open'], data['High'], data['Low'], data['Close']
        body = (c - o).abs()
        
        # Bullish Pattern
        bullish_engulfing = (c > o) & (c.shift(1) < o.shift(1)) & (c >= o.shift(1)) & (o <= c.shift(1))
        hammer = (l - o.combine(c, min) >= 2*body) & (h - o.combine(c, max) < 0.5*body)
        
        last_signal = ""
        if bullish_engulfing.iloc[-1]: last_signal = "Bullish Engulfing"
        elif hammer.iloc[-1]: last_signal = "Hammer"
        
        if last_signal:
            results[ticker] = last_signal
            
    return results

if __name__ == "__main__":
    # DAX Blue Chips
    german_tickers = ["SAP.DE", "SIE.DE", "VOW3.DE", "ADS.DE", "ALV.DE"]
    signals = scan_german_stocks(german_tickers)
    
    if not signals:
        print("Keine bullischen Muster in den letzten 24h gefunden.")
    else:
        for t, s in signals.items():
            print(f"{t}: {s}")
