import sys
from pathlib import Path
REPO_ROOT = Path("/root/forschung")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import json
from datetime import datetime
import pandas as pd
import numpy as np
from orchestra.backtest.engine import US_SYMBOLS, DE_SYMBOLS, fetch_data, add_indicators

# Speichern der finalen besten Modelle & Konfiguration im Repo
CONFIG_PATH = REPO_ROOT / "orchestra" / "config" / "best_models.json"

best_config = {
    "updated_at": datetime.now().isoformat(),
    "top_models": [
        {
            "name": "sr_flip_breakout",
            "timeframe": "1d",
            "hit_rate": 0.541,
            "sharpe": 0.29,
            "description": "Support/Resistance Flip mit Volumenbestätigung im Trend"
        },
        {
            "name": "bb_squeeze_expansion",
            "timeframe": "1d",
            "hit_rate": 0.520,
            "sharpe": 0.19,
            "description": "Bollinger Squeeze & Volatilitäts-Breakout"
        },
        {
            "name": "momentum_rsi",
            "timeframe": "1d",
            "hit_rate": 0.507,
            "sharpe": 0.40,
            "description": "Klassischer Momentum-RSI (55%+ Gesamtrendite)"
        },
        {
            "name": "meanrev_bb",
            "timeframe": "1d",
            "hit_rate": 0.519,
            "sharpe": 0.35,
            "description": "Mean Reversion Bollinger Dip-Kauf"
        }
    ],
    "ensemble_weights": {
        "sr_flip_breakout": 0.35,
        "bb_squeeze_expansion": 0.25,
        "momentum_rsi": 0.25,
        "meanrev_bb": 0.15
    }
}

with open(CONFIG_PATH, "w") as f:
    json.dump(best_config, f, indent=4)

print(f"Erfolgreich gespeichert unter {CONFIG_PATH}!")
print(json.dumps(best_config, indent=4))
