import sys
from pathlib import Path
REPO_ROOT = Path("/root/forschung")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd
import numpy as np

# Wir fassen die bisherigen Ergebnisse zusammen und küren den absoluten Sieger
summary_data = {
    "Strategie": [
        "Momentum RSI (1D)",
        "Trend EMA (1D)",
        "Mean Reversion BB (1D)",
        "Support Bounce",
        "SR Flip Breakout (1D)",
        "BB Squeeze Expansion (1D)",
        "New 52W High Momentum (1D)",
        "Deep Value Bounce 52W (1D)",
        "Fibonacci Pullback Confluence"
    ],
    "Hit_Rate": [0.507, 0.506, 0.519, 0.506, 0.541, 0.520, 0.515, 0.520, 0.512],
    "Total_Return": [55.3, 25.4, 6.6, 0.03, 0.66, 0.29, 76.3, 6.1, -0.03],
    "Sharpe": [0.40, 0.42, 0.35, 0.05, 0.29, 0.19, 0.22, 0.05, 0.00],
    "Trades": [14306, 8922, 10914, 2736, 3802, 1960, 5815, 878, 962]
}

df_compare = pd.DataFrame(summary_data)
print("--- MODELL-VERGLEICH ---")
print(df_compare.sort_values(by="Hit_Rate", ascending=False).to_string(index=False))
