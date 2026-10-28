import sys
from pathlib import Path
REPO_ROOT = Path("/root/forschung")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import json
from datetime import datetime

CONFIG_PATH = REPO_ROOT / "orchestra" / "config" / "master_strategy.json"

master_config = {
    "version": "2.0",
    "updated_at": datetime.now().isoformat(),
    "description": "Master-Strategie für Vibe-Trading Orchester (RSI 2/50, MACD, Volume, 52W High/Low)",
    "primary_strategies": [
        {
            "id": "new_52w_high_momentum",
            "weight": 0.45,
            "params": {"window_52w": 252, "volume_multiplier": 1.0, "macd_required": True}
        },
        {
            "id": "deep_value_bounce_52w",
            "weight": 0.35,
            "params": {"window_52w": 252, "rsi2_threshold": 10, "volume_multiplier": 1.5}
        },
        {
            "id": "rsi_macd_vol_breakout",
            "weight": 0.20,
            "params": {"rsi50_min": 50, "rsi2_max": 15, "volume_multiplier": 1.2}
        }
    ],
    "target_universe": ["US", "DE"],
    "timeframes": ["1d"]
}

with open(CONFIG_PATH, "w") as f:
    json.dump(master_config, f, indent=4)

print(f"Master-Strategie erfolgreich als Standard gesetzt unter {CONFIG_PATH}!")
print(json.dumps(master_config, indent=4))
