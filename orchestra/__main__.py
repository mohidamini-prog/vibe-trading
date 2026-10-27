"""
Orchestra — Haupt-Entrypoint (der "Taktstock").

Ablauf alle 5 min:
    1. Tier1 ziehen (OHLCV, 2KB, gecached)
    2. 5 Agenten rechnen ISOLIERT (eigene, zugeschnittene Datensätze)
    3. Dirigent aggregiert gewichtet -> BUY/HOLD/SELL
    4. Entscheidung ausgeben + (optional) Notification

Kein Auto-Trade am Anfang! Nur Signal.
Läuft auf ARM (numpy-only, kein pandas/torch im Hot-Path).
"""
import sys
from pathlib import Path

# Repo-Wurzel in sys.path (damit 'orchestra' importierbar ist, auch aus scripts/)
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestra.config import get, load_config
from orchestra.config import paths
from orchestra.tiers import tier1, tier2, tier3
from orchestra.data import cache
from orchestra.agents.a1_momentum import MomentumAgent
from orchestra.agents.a2_meanrev import MeanRevAgent
from orchestra.agents.a3_vola import VolaRiskAgent
from orchestra.agents.a4_quant import QuantAgent
from orchestra.agents.a5_news import NewsAgent
from orchestra.conductor.conductor import Conductor


def build_agents():
    return [MomentumAgent(), MeanRevAgent(), VolaRiskAgent(), QuantAgent(), NewsAgent()]


def run_cycle(symbol, verbose=False):
    """Ein kompletter Zyklus für ein Symbol. Liefert ConductorDecision."""
    # 1. Daten: Tier1 (OHLCV, datenarm, gecached) — nur close/high/low/volume für die Agenten
    candles = tier1.fetch_tier1(symbol)
    if isinstance(candles, dict) or not candles:
        return {"error": f"Keine Daten für {symbol}", "symbol": symbol}

    # candle = (ts, close, volume, ema9, ema21, z_score) — wir brauchen high/low für ATR/ADX
    # Für den MVP: high/low aus close abgeleitet (yfinance liefert OHLC, aber wir cachen nur close+vol)
    # TODO: high/low mitcachen für präzisere ATR/ADX
    closes = [c[1] for c in candles]
    volumes = [c[2] for c in candles]
    # high/low approximieren (da nicht gecacht) — für ATR/ADX ausreichend
    highs = [c + 0.001 * c for c in closes]
    lows = [c - 0.001 * c for c in closes]

    data = {
        "close": closes, "high": highs, "low": lows, "volume": volumes,
        "symbol": symbol,
    }

    # 2. Agenten: jeder ISOLIERT mit seinen eigenen Parametern
    agents = build_agents()
    results = [a.vote(data) for a in agents]

    # 3. Dirigent aggregiert
    conductor = Conductor(agents)
    decision = conductor.conduct(symbol, results)

    # 4. Ausgabe
    if verbose:
        print(f"\n=== {symbol} @ {decision.timestamp} ===")
        for r in results:
            print(f"  {r.agent:10s} a={r.a:+d} conf={r.confidence:.2f} w={r.weight:.2f}  {r.reason}")
        print(f"  -> S={decision.S:+.3f} | {decision.decision} | Stärke={decision.strength:.3f}")
        if decision.vetoed:
            print("  ⚠️ VETO aktiv (Risiko/News) — Signal abgeschwächt")
    return decision


def run_universe(verbose=True):
    """Über das ganze Universum laufen."""
    symbols = get("universe.symbols", ["AAPL", "MSFT", "NVDA"])
    results = {}
    for sym in symbols:
        try:
            dec = run_cycle(sym, verbose=verbose)
            results[sym] = dec.to_dict() if hasattr(dec, "to_dict") else dec
        except Exception as e:
            results[sym] = {"error": str(e)}
    # Kompakte Ausgabe in signals_latest.txt (wie gehabt)
    _write_signal_file(results)
    return results


def _write_signal_file(results):
    lines = []
    for sym, d in results.items():
        if "error" in d:
            lines.append(f"{sym}: FEHLER {d['error']}")
            continue
        lines.append(f"{sym}: {d['decision']} (S={d['S']:+.2f}, Stärke={d['strength']:.2f})")
    text = "\n".join(lines) if lines else "Keine neuen Signale"
    paths.SIGNALS_FILE.write_text(text)


if __name__ == "__main__":
    load_config()
    paths.ensure_dirs()
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    print("🎼 Orchestra startet — Einzel-Symbol-Test (AAPL)")
    dec = run_cycle("AAPL", verbose=True)
    if hasattr(dec, "to_dict"):
        print("\nFertig. Entscheidung:", dec.decision, "| S =", round(dec.S, 3))
