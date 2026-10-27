"""
Kombi-Matrix: definierte Indikator-Setups + Backtest-Engine.

Jedes Setup ist eine Kombination aus Indikatoren, die eine Long-Signal-Regel
und (optional) eine Exit-Regel definiert. Der Backtest fährt jede Kombination
über das gesamte Universum (Top-100 US + DAX-40), 3-5 Jahre Tagesdaten.
"""
import numpy as np
import pandas as pd

from . import indicators as ind


# ============================================================
# INDICATOR-SETUPS (Kombinationen)
# ============================================================
# Jedes Setup bekommt einen DataFrame mit OHLCV + berechneten Indikatoren
# und liefert ein Long-Signal (bool), einen Stop-Loss-Puffer und TPs (in ATR).

def setup_trend_ema_rsi(df):
    """EMA-Stack (20>50>200) + RSI-Fenster + Supertrend bestätigt."""
    up = (df["ema20"] > df["ema50"]) & (df["ema50"] > df["ema200"])
    rsi_ok = (df["rsi"] > 50) & (df["rsi"] < 70)
    st_ok = df["st_dir"] == 1
    return up & rsi_ok & st_ok


def setup_momentum_breakout(df):
    """Donchian-20-Breakout + MACD-Hist > 0 + RSI > 55 + Volumen bestätigt."""
    bo = df["Close"] > df["dc_upper"].shift(1)
    macd_ok = df["macd_hist"] > 0
    rsi_ok = df["rsi"] > 55
    vol_ok = df["vol_ratio"] > 1.2
    return bo & macd_ok & rsi_ok & vol_ok


def setup_pullback_trend(df):
    """Pullback in Uptrend: EMA50>EMA200 + RSI-Rücksetzer (50->55) + über EMA20."""
    trend = df["ema50"] > df["ema200"]
    pull = (df["rsi"].shift(1) < 55) & (df["rsi"] > 55)
    above20 = df["Close"] > df["ema20"]
    return trend & pull & above20


def setup_meanrev_oversold(df):
    """Mean-Reversion: RSI < 32 + unteres Bollinger-Band + über VWAP-artigem EMA20."""
    oversold = df["rsi"] < 32
    at_lower = df["Close"] <= df["bb_lower"]
    bounce = df["Close"].shift(1) < df["bb_lower"].shift(1)
    return oversold & (at_lower | bounce)


def setup_supertrend_rsi(df):
    """Supertrend-Up + RSI 45-65 + MACD-Hist positiv."""
    st_ok = df["st_dir"] == 1
    rsi_ok = (df["rsi"] > 45) & (df["rsi"] < 65)
    macd_ok = df["macd_hist"] > 0
    return st_ok & rsi_ok & macd_ok


def setup_adx_trend(df):
    """Starke Trendbestätigung: ADX > 25 + EMA50>EMA200 + RSI > 55."""
    strong = df["adx"] > 25
    trend = df["ema50"] > df["ema200"]
    rsi_ok = df["rsi"] > 55
    return strong & trend & rsi_ok


def setup_breakout_pullback_combo(df):
    """Breakout ODER Pullback in Trend — kombiniert beide Auslöser."""
    bo = (df["Close"] > df["dc_upper"].shift(1)) & (df["rsi"] > 55)
    pb = (df["ema50"] > df["ema200"]) & (df["rsi"].shift(1) < 55) & (df["rsi"] > 55)
    return bo | pb


# Registry: Name -> Funktion
SETUPS = {
    "trend_ema_rsi": setup_trend_ema_rsi,
    "momentum_breakout": setup_momentum_breakout,
    "pullback_trend": setup_pullback_trend,
    "meanrev_oversold": setup_meanrev_oversold,
    "supertrend_rsi": setup_supertrend_rsi,
    "adx_trend": setup_adx_trend,
    "breakout_pullback_combo": setup_breakout_pullback_combo,
}


# ============================================================
# INDICATOR PREPARATION
# ============================================================
def prepare(df):
    """Berechne alle Indikatoren, die Setups brauchen."""
    df = df.copy()
    c = df["Close"]
    h = df["High"]
    l = df["Low"]
    v = df["Volume"]

    df["ema20"] = ind.ema(c, 20)
    df["ema50"] = ind.ema(c, 50)
    df["ema200"] = ind.ema(c, 200)
    df["rsi"] = ind.rsi(c, 14)
    df["macd_line"], df["macd_sig"], df["macd_hist"] = ind.macd(c)
    df["bb_upper"], df["bb_mid"], df["bb_lower"] = ind.bollinger(c, 20, 2.0)
    df["atr"] = ind.atr(h, l, c, 14)
    df["adx"] = ind.adx(h, l, c, 14)
    df["st_line"], df["st_dir"] = ind.supertrend(h, l, c, 10, 3.0)
    df["dc_upper"], df["dc_lower"] = ind.donchian(h, l, 20)
    df["vol_avg"] = v.rolling(20).mean()
    df["vol_ratio"] = v / df["vol_avg"].replace(0, np.nan)
    return df


# ============================================================
# BACKTEST ENGINE (Long-only, ATR-basierter Stop)
# ============================================================
def backtest(df, signal_fn, atr_mult_sl=2.0, rr=[1.5, 2.5, 4.0],
             max_hold=30, cost_bps=5.0, position_pct=0.10,
             equity_start=100000.0):
    """
    Einfacher Long-Backtest über einen vorbereiteten DataFrame.

    Kostet cost_bps pro Trade (Basis-Punkte, round-trip).
    position_pct = Anteil des Eigenkapitals pro Position (Kapitalbegrenzung).
    Returns: dict mit Trades, Statistik.
    """
    df = prepare(df)
    sig = signal_fn(df).fillna(False).values
    close = df["Close"].values
    high = df["High"].values
    low = df["Low"].values
    atr_v = df["atr"].values
    dates = df.index

    trades = []
    equity = equity_start
    i = 0
    n = len(df)
    while i < n:
        if sig[i] and not np.isnan(atr_v[i]) and atr_v[i] > 0:
            entry = close[i]
            sl = entry - atr_mult_sl * atr_v[i]
            tps = [entry + r * atr_mult_sl * atr_v[i] for r in rr]
            result = None
            exit_price = entry
            exit_reason = "HOLD"
            bars = 0
            for j in range(i + 1, min(i + 1 + max_hold, n)):
                bars = j - i
                # Stop-Loss zuerst (konservativ)
                if low[j] <= sl:
                    exit_price = sl
                    exit_reason = "SL"
                    break
                # Take-Profit
                hit = False
                for tp in tps:
                    if high[j] >= tp:
                        exit_price = tp
                        exit_reason = "TP"
                        hit = True
                        break
                if hit:
                    break
            else:
                exit_price = close[min(i + max_hold, n - 1)]
                exit_reason = "TIME"

            pnl_pct = (exit_price - entry) / entry
            pnl_pct -= cost_bps / 10000.0  # Kosten (round-trip)
            # Kapitalbegrenzung: nur position_pct des Eigenkapitals eingesetzt
            position_value = equity * position_pct
            pnl_abs = position_value * pnl_pct
            equity += pnl_abs
            trades.append({
                "entry_date": dates[i],
                "exit_date": dates[min(i + bars, n - 1)],
                "entry": entry,
                "exit": exit_price,
                "pnl": pnl_pct,
                "pnl_abs": pnl_abs,
                "bars": bars,
                "reason": exit_reason,
            })
            i += max(1, bars + 1)  # nächster Trade erst nach diesem
        else:
            i += 1

    return summarize(trades, equity_start=equity_start)


def summarize(trades, equity_start=100000.0):
    if not trades:
        return {"n": 0, "win_rate": 0, "avg_pnl": 0, "total_pnl": 0,
                "profit_factor": 0, "max_drawdown": 0, "expectancy": 0,
                "equity_final": equity_start, "net_return_pct": 0}
    df = pd.DataFrame(trades)
    wins = df[df["pnl"] > 0]
    losses = df[df["pnl"] <= 0]
    total = df["pnl"].sum()
    # Max Drawdown aus kumulierter Equity-Kurve
    eq = (1 + df["pnl"]).cumprod()
    dd = (eq / eq.cummax() - 1).min()
    pf = wins["pnl"].sum() / abs(losses["pnl"].sum()) if losses["pnl"].sum() != 0 else float("inf")
    # Kapitalbasiert: kumulierte Rendite aufs eingesetzte Kapital
    equity_final = equity_start + df["pnl_abs"].sum() if "pnl_abs" in df else equity_start
    net_return = (equity_final / equity_start - 1) * 100
    return {
        "n": len(df),
        "win_rate": len(wins) / len(df) * 100,
        "avg_pnl": df["pnl"].mean() * 100,
        "total_pnl": total * 100,
        "profit_factor": pf,
        "max_drawdown": dd * 100,
        "expectancy": (len(wins) / len(df) * wins["pnl"].mean() +
                       len(losses) / len(df) * losses["pnl"].mean()) * 100,
        "equity_final": equity_final,
        "net_return_pct": net_return,
    }
