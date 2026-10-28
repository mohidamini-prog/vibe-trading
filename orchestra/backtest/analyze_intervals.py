import sys
from pathlib import Path
REPO_ROOT = Path("/root/forschung")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd
import numpy as np
from orchestra.backtest.engine import US_SYMBOLS, DE_SYMBOLS, fetch_data, add_indicators, backtest
from run_enhanced import enhanced_strategy_signals

symbols = US_SYMBOLS + DE_SYMBOLS
intervals = ["4h", "1d"]
models = [
    "trend_ema", "momentum_rsi", "meanrev_bb", "adx_trend",
    "breakout_donchian", "support_bounce", "pullback_entry", "liquidity_sweep"
]

all_res = []
for symbol in symbols:
    for interval in intervals:
        period = "730d" if interval == "4h" else "max"
        df = fetch_data(symbol, interval, period)
        if df is None or len(df) < 60:
            continue
        df = add_indicators(df)
        for model in models:
            sig = enhanced_strategy_signals(df, model)
            res = backtest(df, sig)
            if res and res["n_trades"] > 0:
                res["symbol"] = symbol
                res["interval"] = interval
                res["model"] = model
                all_res.append(res)

df_all = pd.DataFrame(all_res)

# Wir testen verschiedene Agenten-Kombinationen (Gewichtungen w_i)
# Agenten: 
# 1. Momentum (trend_ema + momentum_rsi)
# 2. MeanRev (meanrev_bb + support_bounce)
# 3. Breakout (breakout_donchian + adx_trend)
# 4. Sweep/Risk (liquidity_sweep + pullback_entry)

# Wir simulieren ein Ensemble, indem wir die Signale (votes +1/-1/0) gewichtet aufsummieren
# und prüfen, welche Kombination die beste Sharpe-Ratio & Hit-Rate liefert.

print("Suche optimale Agenten-Gewichte (Ensemble)...")
best_score = -999
best_weights = None

# Grid search über Gewichte w1, w2, w3, w4
np.random.seed(42)
for _ in range(100):
    w = np.random.dirichlet(np.ones(4)) # Summiert zu 1
    
    # Pivotieren für jedes Symbol/Intervall
    # Wir berechnen den gewichteten Score pro Bar über alle Symbole
    # Vereinfacht: wir aggregieren die Metriken der Modelle nach den 4 Kategorien
    
print("\n--- ERGEBNISSE NACH INTERVALLE (4h vs 1D) ---")
print(df_all.groupby(["interval", "model"])[["hit_rate", "total_ret", "sharpe"]].mean().to_string())
