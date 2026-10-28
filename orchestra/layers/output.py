"""
Layer 5 — Output-Layer.

Schreibt Ergebnisse in saubere, konsistente Pfade:
  - signals_latest.json  : maschinenlesbare Signale (strukturiert)
  - signals_latest.txt   : kompakte Mensch-Ausgabe
  - Layer-Historie       : für Gegenprüfung/Ping

Signale-Frequenz: 1d = nach jedem Börsentag, 4h = alle 4h. Wir scannen beide
Timeframes und schreiben pro Symbol das höchste Konfidenz-Signal.
"""
import sys
import json
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestra.config import paths
from orchestra.layers.filters import apply_filters


def write_signals(results):
    """
    results: {symbol: LayerDecision.to_dict()}
    Schreibt signals_latest.json + signals_latest.txt.
    """
    # JSON (maschinenlesbar)
    payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "signals": results,
    }
    paths.SIGNALS_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    # TXT (Mensch)
    lines = [f"# Vibe-Trading Signale — {datetime.utcnow().isoformat()}", ""]
    for sym, d in results.items():
        if "error" in d:
            lines.append(f"{sym}: FEHLER {d['error']}")
            continue
        dec = d.get("decision", "HOLD")
        s = d.get("S", 0)
        st = d.get("strength", 0)
        lines.append(f"{sym} [{d.get('timeframe','1d')}]: {dec} (S={s:+.2f}, Stärke={st:.2f})")
        # Bestes Signal als Springer-Info
        for sig in d.get("signals", []):
            if sig["a"] != 0:
                lines.append(f"   ├─ {sig['model']}: {sig['reason']} (conf {sig['conf']:.2f})")
        # Nur tatsächlich BLOCKIERENDE Filter anzeigen (pass=true wird nicht als Block gemeldet)
        fr = d.get("filter_report", {})
        blocks = fr.get("blocks", {}) if isinstance(fr, dict) else {}
        if blocks:
            lines.append(f"   └─ Filter-Block: {', '.join(f'{g} ({r})' for g, r in blocks.items())}")
        lines.append("")
    paths.SIGNALS_FILE.write_text("\n".join(lines))
    return payload


if __name__ == "__main__":
    # Testlauf mit Beispiel
    sample = {
        "AAPL": {
            "symbol": "AAPL", "timeframe": "1d", "decision": "BUY", "S": 0.62,
            "strength": 0.41, "avg_confidence": 0.66,
            "weights": {"new_52w_high_momentum": 0.45},
            "signals": [{"model": "new_52w_high_momentum", "a": 1, "conf": 0.72, "reason": "52W-High Ausbruch (MACD+, Vol 1.8x)"}],
            "filter_report": {"volume_quality": "Vol 1.80x", "trend_macro": "Trend OK"},
            "vetoed": False, "timestamp": datetime.utcnow().isoformat(),
        }
    }
    write_signals(sample)
    print("Test geschrieben nach", paths.SIGNALS_JSON, "und", paths.SIGNALS_FILE)
    print(paths.SIGNALS_FILE.read_text())
