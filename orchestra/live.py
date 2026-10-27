"""
Live-Loop — koppelt den Scanner an den Visualizer.

Fährt periodisch das Orchester über das Universum und schreibt die Entscheidungen
in die State-DB (macht der Conductor automatisch). Der Visualizer liest daraus
live (alle 3s polling) — keine weitere Verdrahtung nötig.

Modi:
    --once        Einmal fahren (für Tests / manuelle Aktualisierung)
    --loop        Dauerhaft alle N Minuten (Default 5)
    --interval N  Intervall in Minuten (Default 5)
"""
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestra.config import load_config, get
from orchestra.config import paths
from orchestra import __main__ as engine


def run_once(verbose=True):
    load_config()
    paths.ensure_dirs()
    res = engine.run_universe(verbose=verbose)
    # Signal-Datei (kompakte Ausgabe) wird von run_universe geschrieben
    return res


def run_loop(interval_min=5):
    print(f"🎼 Orchestra Live-Loop: alle {interval_min} min. Visualizer liest automatisch.")
    while True:
        t0 = time.time()
        try:
            run_once(verbose=True)
        except Exception as e:
            print(f"  Fehler im Zyklus: {e}")
        elapsed = time.time() - t0
        wait = max(1, interval_min * 60 - elapsed)
        print(f"  Nächster Scan in {wait/60:.1f} min …\n")
        time.sleep(wait)


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--once" in args:
        run_once(verbose=True)
        print("\nFertig. State-DB aktualisiert — Visualizer zeigt die neuen Votes.")
    elif "--loop" in args:
        interval = 5
        if "--interval" in args:
            try:
                interval = int(args[args.index("--interval") + 1])
            except (ValueError, IndexError):
                pass
        run_loop(interval)
    else:
        run_once(verbose=True)
        print("\nTipp: --loop für dauerhaften Betrieb, --interval N für Minuten.")
