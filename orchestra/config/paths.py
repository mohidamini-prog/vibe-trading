"""
Zentrale Pfade — EINZIGE Quelle für alle Dateipfade im Orchestra.

Kein Hardcode irgendwo anders. Alle Module importieren von hier.
"""
from pathlib import Path

# --- Wurzel: /root/forschung (das vibe-trading Repo) ---
REPO_ROOT = Path(__file__).resolve().parents[2]      # orchestra/config/paths.py -> /root/forschung
ORCHESTRA_ROOT = REPO_ROOT / "orchestra"

# --- Kern-Verzeichnisse ---
DATA_DIR = ORCHESTRA_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"          # SQLite candles.db + Fetch-Cache
REPORTS_DIR = DATA_DIR / "reports"      # Signal-Ausgaben
STATE_DIR = DATA_DIR / "state"          # Agenten-Gewichte, Dirigent-Zustand

# --- Datenbanken ---
DB_CANDLES = CACHE_DIR / "candles.db"   # OHLCV-Cache (max ~10MB)
DB_STATE = STATE_DIR / "orchestra_state.db"  # Gewichte, Performance, Konfiguration

# --- Agenten-spezifisch ---
AGENTS_DIR = ORCHESTRA_ROOT / "agents"
AGENT_WEIGHTS_FILE = STATE_DIR / "agent_weights.json"   # dynamische Gewichte w_i
AGENT_PERF_FILE = STATE_DIR / "agent_performance.json"  # Sharpe je Agent

# --- Bestehende Altlast (vibe/ Repo) für Anbindung ---
VIBE_DIR = REPO_ROOT / "vibe"
ALT_DATA_DIR = VIBE_DIR / "altdata"
EDGAR_SCRIPT = ALT_DATA_DIR / "edgar_insider.py"   # SEC EDGAR Form 4

# --- Ausgabe ---
SIGNALS_FILE = REPO_ROOT / "signals_latest.txt"     # kompakte Signal-Ausgabe
SIGNALS_JSON = REPO_ROOT / "signals_latest.json"

# --- Hilfsfunktionen: Verzeichnisse sicher anlegen ---
def ensure_dirs() -> None:
    for d in (CACHE_DIR, REPORTS_DIR, STATE_DIR):
        d.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    ensure_dirs()
    print("REPO_ROOT   :", REPO_ROOT)
    print("ORCHESTRA   :", ORCHESTRA_ROOT)
    print("DB_CANDLES  :", DB_CANDLES)
    print("DB_STATE    :", DB_STATE)
    print("EDGAR       :", EDGAR_SCRIPT)
