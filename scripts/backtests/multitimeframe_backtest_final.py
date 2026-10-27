import yfinance as pd_yf
import pandas as pd
import numpy as np

def run_mtf_backtest(ticker, name):
    print(f"\n--- Backtesting {name} ({ticker}) ---")
    try:
        # 1. Daily Data
        daily = pd_yf.download(ticker, period="1y", interval="1d", progress=False)
        if isinstance(daily.columns, pd.MultiIndex):
            daily.columns = daily.columns.droplevel(1)
        if daily.empty:
            print("DATEN FEHLEN (Daily)")
            return
        
        daily['EMA50'] = daily['Close'].ewm(span=50, adjust=False).mean()
        daily['EMA200'] = daily['Close'].ewm(span=200, adjust=False).mean()
        daily['Daily_Trend'] = daily['EMA50'] > daily['EMA200']
        daily = daily.reset_index()
        date_col = [c for c in daily.columns if 'date' in c.lower()][0]
        daily['DateOnly'] = pd.to_datetime(daily[date_col]).dt.date

        # 2. 4h Data (via 1h resample)
        h4 = pd_yf.download(ticker, period="60d", interval="1h", progress=False)
        if isinstance(h4.columns, pd.MultiIndex):
            h4.columns = h4.columns.droplevel(1)
        if h4.empty:
            print("DATEN FEHLEN (4h/1h)")
            return

        h4 = h4.resample('4h').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
        
        # 3. Indicators using pure numpy arrays
        o, h, l, c = h4['Open'].values, h4['High'].values, h4['Low'].values, h4['Close'].values
        body = np.abs(c - o)
        
        h4_close_series = h4['Close']
        h4['EMA20'] = h4_close_series.ewm(span=20, adjust=False).mean()
        
        delta = h4_close_series.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        h4['RSI'] = 100 - (100 / (1 + rs))
        
        # NumPy-based pattern detection
        c_prev = np.roll(c, 1)
        o_prev = np.roll(o, 1)
        c_prev[0] = c[0]
        o_prev[0] = o[0]
        
        bullish_engulfing = (c > o) & (c_prev < o_prev) & (c >= o_prev) & (o <= c_prev)
        hammer = (l - np.minimum(o, c) >= 2 * body) & (h - np.maximum(o, c) < 0.5 * body)
        
        h4 = h4.reset_index()
        h4_date_col = [col for col in h4.columns if 'date' in col.lower() or 'time' in col.lower()][0]
        h4['DateOnly'] = pd.to_datetime(h4[h4_date_col]).dt.date
        
        # Merge daily trend
        h4 = pd.merge(h4, daily[['DateOnly', 'Daily_Trend']], on='DateOnly', how='left')
        h4['Daily_Trend'] = h4['Daily_Trend'].ffill().fillna(False)
        
        ema20_vals = h4['EMA20'].values
        rsi_vals = h4['RSI'].values
        trend_vals = h4['Daily_Trend'].values
        
        long_cond = trend_vals & (c > ema20_vals) & (rsi_vals > 35) & (rsi_vals < 65) & (bullish_engulfing | hammer)
        h4['Signal'] = np.where(long_cond, 1, 0)
        
        h4['Returns'] = h4['Close'].pct_change() * h4['Signal'].shift(1)
        total_ret = (1 + h4['Returns'].fillna(0)).prod() - 1
        trades = h4['Signal'].sum()
        win_rate = (h4['Returns'] > 0).sum() / max(trades, 1)
        
        print(f"Ergebnis: Gesamt-Rendite = {total_ret:.2%}, Trades = {trades}, Win Rate = {win_rate:.2%}")
    except Exception as e:
        print(f"Fehler bei {name}: {e}")

if __name__ == "__main__":
    print("=== MULTI-TIMEFRAME BACKTEST (US & DE) ===")
    tickers = [
        ("^GDAXI", "DAX (Deutschland)"),
        ("SAP.DE", "SAP (Deutschland)"),
        ("SIE.DE", "Siemens (Deutschland)"),
        ("AAPL", "Apple (USA)"),
        ("MSFT", "Microsoft (USA)"),
        ("NVDA", "Nvidia (USA)")
    ]
    for ticker, name in tickers:
        run_mtf_backtest(ticker, name)
