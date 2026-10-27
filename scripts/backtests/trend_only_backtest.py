"""
STRATEGIE-ERKENNTNIS (BACKTEST-TESTING):
Kerzenmuster (Hammer, Bullish Engulfing) auf 1h- und 4h-Timeframes erzeugen zu viel Rauschen
und Fehlsignale (Whipsaws). Sie bremsen die Performance aus.

Dieses Skript testet einen REINEN Trend- und Momentum-Ansatz (EMA50/200 + RSI) OHNE Muster.
"""

import yfinance as pd_yf
import pandas as pd
import numpy as np

def run_pure_trend_backtest(ticker="SAP.DE", name="SAP", interval="1h"):
    data = pd_yf.download(ticker, start="2025-10-26", end="2026-10-26", interval=interval, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(1)
    if len(data) < 100:
        return
        
    c = data['Close']
    
    # Reiner Trend & Momentum Filter
    data['EMA20'] = c.ewm(span=20, adjust=False).mean()
    data['EMA50'] = c.ewm(span=50, adjust=False).mean()
    data['Trend'] = data['EMA20'] > data['EMA50']
    
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    data['RSI'] = 100 - (100 / (1 + rs))
    
    # Einstieg rein über Trend + RSI Momentum (OHNE Muster)
    long_cond = data['Trend'] & (data['RSI'] > 50) & (data['RSI'] < 70)
    data['Signal'] = np.where(long_cond, 1, 0)
    data['Returns'] = c.pct_change() * data['Signal'].shift(1)
    
    ret = (1 + data['Returns'].dropna()).prod() - 1
    trades = int(data['Signal'].diff().abs().sum() / 2)
    print(f"[{name}] Reiner Trend ({interval}): Rendite = {ret:.2%}, Trades = {trades}")

if __name__ == "__main__":
    print("=== BACKTEST: REINER TREND OHNE MUSTER ===")
    german_stocks = [("SAP.DE", "SAP"), ("SIE.DE", "Siemens"), ("ALV.DE", "Allianz"), ("BAS.DE", "BASF")]
    for ticker, name in german_stocks:
        run_pure_trend_backtest(ticker, name, "1h")
