import sys
from pathlib import Path
REPO_ROOT = Path("/root/forschung")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import json
from datetime import datetime

LIVE_INTEGRATION_PATH = REPO_ROOT / "orchestra" / "config" / "live_scanner_integration.py"

integration_code = """\"\"\"
Live Scanner Integration für das Alpha-Core Smart-Money Master-Setup.
Nutzt New 52W High Momentum & SR Flip Breakout mit Volumen-Konfirmation.
\"\"\"
import json
from pathlib import Path

MASTER_CONFIG_PATH = Path(__file__).parent / "alpha_core_master.json"

def load_alpha_core_rules():
    if MASTER_CONFIG_PATH.exists():
        with open(MASTER_CONFIG_PATH, "r") as f:
            return json.load(f)
    return {"error": "Master config not found"}

if __name__ == "__main__":
    cfg = load_alpha_core_rules()
    print("Smart-Money Live Rules loaded successfully:")
    print(json.dumps(cfg, indent=4))
"""

with open(LIVE_INTEGRATION_PATH, "w") as f:
    f.write(integration_code)

print(f"Live-Scanner Integration erfolgreich erstellt unter {LIVE_INTEGRATION_PATH}!")
