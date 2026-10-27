"""
--------------------------------------------------------------------------------
OFFIZIELLE FORSCHUNGSSTRATEGIE (MOHID & HERMES)
--------------------------------------------------------------------------------
ERKENNTNIS / FAZIT ZU KERZENMUSTERN (Hammer, Engulfing etc.):
Die Nutzung von klassischen Kerzenmustern auf 1h- und 4h-Timeframes wurde DEAKTIVIERT.
Begründung:
1. Extrem viel Rauschen (Noise) im Intraday/4h-Bereich.
2. Hohe Anfälligkeit für Fakeouts und Bull Traps (Whipsaws).
3. Muster sind zu restriktiv und lassen die profitablen Haupt-Trendbewegungen aus.
Muster sind reiner Unsinn für diese Zeitfenster.

EFFEKTIVER ANSATZ:
Wir nutzen ausschließlich reinen Trend- und Momentum-Filter (EMA-Ausrichtung + RSI).
--------------------------------------------------------------------------------
"""

import yfinance as pd_yf
import pandas as pd
import numpy as np

def run_effective_scan(ticker="ALV.DE", name="Allianz"):
    print(f"\n--- Effektiver Trend-Scan für {name} ({ticker}) ---")
    data = pd_yf.download(ticker, period="1y", interval="1d", progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(1)
        
    c = data['Close']
    data['EMA20'] = c.ewm(span=20, adjust=False).mean()
    data['EMA50'] = c.ewm(span=50, adjust=False).mean()
    data['EMA200'] = c.ewm(span=200, adjust=False).mean()
    
    # RSI
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    data['RSI'] = 100 - (100 / (1 + rs))
    
    # Trend & Momentum
    uptrend = (data['EMA50'] > data['EMA200']) & (c > data['EMA20'])
    momentum_ok = (data['RSI'] > 45) & (data['RSI'] < 75)
    
    signal = uptrend & momentum_ok
    data['Signal'] = np.where(signal, 1, 0)
    data['Returns'] = c.pct_change() * data['Signal'].shift(1)
    
    ret = (1 + data['Returns'].dropna()).prod() - 1
    trades = int(data['Signal'].diff().abs().sum() / 2)
    
    print(f"Letzter Kurs: {c.iloc[-1]:.2f} | RSI: {data['RSI'].iloc[-1]:.1f}")
    print(f"Trend-Status: {'BULLISCH (Long)' if uptrend.iloc[-1] else 'NEUTRAL/BÄRISCH'}")
    print(f"1-Jahres-Backtest (Reiner Trend): {ret:.2%}")
    print(f"Anzahl Trades: {trades}")

if __name__ == "__main__":
    assets = [("ALV.DE", "Allianz"), ("SIE.DE", "Siemens"), ("SAP.DE", "SAP"), ("BTC-USD", "Bitcoin")]
    for t, n in assets:
        run_effective_scan(t, n)
