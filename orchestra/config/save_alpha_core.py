import sys
from pathlib import Path
REPO_ROOT = Path("/root/forschung")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import json
from datetime import datetime

MASTER_FILE = REPO_ROOT / "orchestra" / "config" / "alpha_core_master.json"

alpha_core_master = {
    "version": "3.0",
    "updated_at": datetime.now().isoformat(),
    "philosophy": "Quality over Quantity: High-conviction Swing Trading on 4h & Daily charts.",
    "core_engines": [
        {
            "name": "New 52W High Momentum",
            "weight": 0.60,
            "timeframe": "1d",
            "rationale": "Reitet institutionelle Trend-Wellen und Allzeithochs (76%+ historische Rendite im Backtest)."
        },
        {
            "name": "SR Flip Breakout",
            "weight": 0.40,
            "timeframe": "1d",
            "rationale": "Sauberste Trefferquote (54.1%) an getesteten Support/Resistance-Zonen mit Volumen-Konfirmation."
        }
    ],
    "master_indicators": {
        "trend": ["EMA 50", "EMA 200", "52-Week High/Low"],
        "momentum": ["RSI (14 & 2)", "MACD Histogram"],
        "volume_quality": ["Volume > 20-period Median (keine Low-Volume-Fakes)"]
    }
}

with open(MASTER_FILE, "w") as f:
    json.dump(alpha_core_master, f, indent=4)

print(f"Alpha-Core Master-Konfiguration erfolgreich gespeichert unter {MASTER_FILE}!")
print(json.dumps(alpha_core_master, indent=4))
