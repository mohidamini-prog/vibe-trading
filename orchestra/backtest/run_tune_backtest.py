"""
Backtest der Tunepunkte 1-4 für das Orchestra (effizient, einmalig vorberechnet).

Tunepunkte (nur Backtest, nichts live ändern):
  1. Ent-Clustern   : max 1 Trade pro Sektor/Cluster
  2. Frequenz       : buy_threshold 0.5 -> 0.45 ; oder_conf 0.80 -> 0.75
  3. Stärke-Gate    : MIN_STRENGTH 0.05 -> 0.08
  4. Gewichte       : alpha-Lernrate (dynamische Gewichtung)

Kontext: max 5 offene Positionen gleichzeitig (bereits aktiv).

Effizienz: Indikatoren + Signale werden EINMAL pro Symbol für alle Bars
vorberechnet; jede Konfiguration aggregiert nur noch (kein Neuberechnen).
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]  # /root/forschung
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np

from orchestra.layers.data import load_batch
from orchestra.layers.indicators import compute_indicators
from orchestra.layers.signals import compute_all_signals

# --- Universum (echte 181 Symbole) ---
_cfg = Path("/root/forschung/index_constituents.json")
_d = json.loads(_cfg.read_text())
_us = list(dict.fromkeys(_d.get("NASDAQ100", [])))
_de = []
for _k in ("DAX", "MDAX"):
    _de += [t for t in _d.get(_k, []) if t.endswith(".DE")]
_de = list(dict.fromkeys(_de))
SYMBOLS = _us + _de

SECTOR_GUESS = {}
for s in SYMBOLS:
    if s.endswith(".DE"):
        SECTOR_GUESS[s] = "DE_" + s.split(".")[0][:2]
    else:
        SECTOR_GUESS[s] = "US_" + s[:1]

CONFIGS = {
    "baseline":        {"buy_threshold": 0.5, "oder_conf": 0.80, "min_strength": 0.05, "sector_max": 99, "alpha": 0.05, "max_pos": 5},
    "tune1_decluster": {"buy_threshold": 0.5, "oder_conf": 0.80, "min_strength": 0.05, "sector_max": 1,  "alpha": 0.05, "max_pos": 5},
    "tune2_frequency": {"buy_threshold": 0.45,"oder_conf": 0.75, "min_strength": 0.05, "sector_max": 99, "alpha": 0.05, "max_pos": 5},
    "tune3_strength":  {"buy_threshold": 0.5, "oder_conf": 0.80, "min_strength": 0.08, "sector_max": 99, "alpha": 0.05, "max_pos": 5},
    "tune4_weights":   {"buy_threshold": 0.5, "oder_conf": 0.80, "min_strength": 0.05, "sector_max": 99, "alpha": 0.20, "max_pos": 5},
    "tune_all":        {"buy_threshold": 0.45,"oder_conf": 0.75, "min_strength": 0.08, "sector_max": 1,  "alpha": 0.20, "max_pos": 5},
}

MODEL_WEIGHTS = {
    "new_52w_high_momentum": 0.45,
    "sr_flip_breakout": 0.35,
    "deep_value_bounce_52w": 0.15,
    "fib_pullback_confluence": 0.05,
    "meanrev_bb": 0.0,
}


def prepare_symbols(data):
    """Indikatoren + Signale für ALLE Bars jedes Symbols einmalig vorberechnen."""
    prepared = {}
    for sym, df_raw in data.items():
        if df_raw is None or len(df_raw) < 60:
            continue
        df = compute_indicators(df_raw)
        bars = []
        for i in range(60, len(df)):
            signals = compute_all_signals(df, i=i)
            bars.append({
                "i": i,
                "close": float(df["close"].iloc[i]),
                "signals": signals,
            })
        prepared[sym] = bars
    return prepared


def run_backtest(config, prepared):
    """Aggregiert vorberechnete Signale zu Trades (schnell, keine Neuberechnung)."""
    buy_th = config["buy_threshold"]
    oder_conf = config["oder_conf"]
    min_strength = config["min_strength"]
    sector_max = config["sector_max"]
    max_pos = config["max_pos"]

    weights = dict(MODEL_WEIGHTS)
    all_trades = []
    sector_trades = {}
    open_positions = []

    for sym, bars in prepared.items():
        sector = SECTOR_GUESS.get(sym, sym)
        for bar in bars:
            signals = bar["signals"]
            if not signals:
                continue
            total_w = sum(weights.get(s["model"], 0.1) for s in signals) or 1.0
            S = sum(weights.get(s["model"], 0.1) * s["a"] * s["conf"] for s in signals) / total_w
            avg_conf = sum(s["conf"] for s in signals) / len(signals) if signals else 0
            single_buy = any(s["a"] == 1 and s["conf"] >= oder_conf for s in signals)
            single_sell = any(s["a"] == -1 and s["conf"] >= oder_conf for s in signals)

            if S > buy_th or single_buy:
                decision = "BUY"
            elif S < -buy_th or single_sell:
                decision = "SELL"
            else:
                decision = "HOLD"

            strength = abs(S) * avg_conf
            if decision == "HOLD" or strength < min_strength:
                continue
            if sector_trades.get(sector, 0) >= sector_max:
                continue
            if decision == "BUY":
                if len(open_positions) >= max_pos:
                    continue
                open_positions.append(sym)
            elif decision == "SELL":
                if sym in open_positions:
                    open_positions.remove(sym)

            sector_trades[sector] = sector_trades.get(sector, 0) + 1
            all_trades.append({
                "symbol": sym, "decision": decision, "S": round(S, 4),
                "strength": round(strength, 4), "bar": bar["i"], "close": bar["close"],
            })

    return {
        "n_trades": len(all_trades),
        "n_buy": sum(1 for t in all_trades if t["decision"] == "BUY"),
        "n_sell": sum(1 for t in all_trades if t["decision"] == "SELL"),
        "n_symbols_with_trades": len({t["symbol"] for t in all_trades}),
        "avg_strength": round(float(np.mean([t["strength"] for t in all_trades])), 4) if all_trades else 0,
        "sectors_touched": len(sector_trades),
    }


if __name__ == "__main__":
    print(f"=== TUNE-BACKTEST: {len(SYMBOLS)} Symbole (DAX+MDAX+NASDAQ100) ===")

    print("Lade Daten 1d 5y (181 Symbole, force)...")
    data = load_batch(SYMBOLS, "1d", period="5y", force=True)
    print(f"Geladen: {len(data)} Symbole\n")

    print("Berechne Indikatoren + Signale für alle Bars (einmalig)...")
    prepared = prepare_symbols(data)
    total_bars = sum(len(b) for b in prepared.values())
    print(f"Vorbereitet: {len(prepared)} Symbole, {total_bars} Bars\n")

    results = []
    for name, cfg in CONFIGS.items():
        print(f"--- {name} ---")
        r = run_backtest(cfg, prepared)
        r["config_name"] = name
        r["config"] = cfg
        results.append(r)
        print(f"  Trades: {r['n_trades']} (BUY {r['n_buy']} / SELL {r['n_sell']})")
        print(f"  Symbole mit Trades: {r['n_symbols_with_trades']} | Ø Stärke: {r['avg_strength']} | Sektoren: {r['sectors_touched']}\n")

    out = Path(REPO_ROOT) / "backtests" / "tune_backtest_results.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"Ergebnisse -> {out}")
