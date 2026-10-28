import sys
from pathlib import Path
REPO_ROOT = Path("/root/forschung")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import json
from datetime import datetime

FILTERS_PATH = REPO_ROOT / "orchestra" / "config" / "smart_money_filters.json"

filters_config = {
    "version": "1.0",
    "updated_at": datetime.now().isoformat(),
    "description": "Erweiterte Smart-Money Signalfilter für maximale Qualität (Null Rauschen)",
    "filters": {
        "volume_quality_filter": {
            "enabled": True,
            "rule": "Volume > 1.25 * rolling_median(Volume, 20)",
            "purpose": "Filtert Low-Volume Fakes und bestätigt institutionellen Block-Trade."
        },
        "trend_macro_filter": {
            "enabled": True,
            "rule": "Close > EMA_50 > EMA_200",
            "purpose": "Verhindert Short-Trades in Bullenmärkten und Long-Trades in Bärenmärkten."
        },
        "volatility_atr_filter": {
            "enabled": True,
            "rule": "ATR(14) > rolling_median(ATR(14), 50) * 0.8",
            "purpose": "Vermeidet Seitwärtsmärkte ohne Dynamik (schützt vor Chop-Losses)."
        },
        "spread_gap_guard": {
            "enabled": True,
            "rule": "Avoid entries on excessive opening gaps (> 2 * ATR)",
            "purpose": "Schützt vor unvorhersehbaren Earnings-Gaps bei US/DE Aktien."
        }
    }
}

with open(FILTERS_PATH, "w") as f:
    json.dump(filters_config, f, indent=4)

print(f"Smart-Money Signalfilter erfolgreich gespeichert unter {FILTERS_PATH}!")
print(json.dumps(filters_config, indent=4))
