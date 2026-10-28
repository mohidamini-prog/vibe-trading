import json
import sys
from pathlib import Path

REPO_ROOT = Path("/root/forschung")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np

from orchestra.layers.data import load_batch
from orchestra.layers.indicators import compute_indicators
from orchestra.layers.signals import compute_all_signals

_cfg = Path("/root/forschung/index_constituents.json")
_d = json.loads(_cfg.read_text())
_us = list(dict.fromkeys(_d.get("NASDAQ100", [])))
_de = []
for _k in ("DAX", "MDAX"):
    _de += [t for t in _d.get(_k, []) if t.endswith(".DE")]
SYMBOLS = _us + _de

MODEL_WEIGHTS = {
    "new_52w_high_momentum": 0.45,
    "sr_flip_breakout": 0.35,
    "deep_value_bounce_52w": 0.15,
    "fib_pullback_confluence": 0.05,
    "meanrev_bb": 0.0,
}

data = load_batch(SYMBOLS, "1d", period="5y", force=True)
print(f"Geladen: {len(data)} Symbole")

# Signal-Statistik über ALLE Bars aller Symbole
stat = {}
total_bars = 0
signals_fired = 0
high_conf = 0
sample_symbols = {}
for sym, df_raw in data.items():
    if df_raw is None or len(df_raw) < 60:
        continue
    df = compute_indicators(df_raw)
    for i in range(60, len(df)):
        total_bars += 1
        signals = compute_all_signals(df, i=i)
        for s in signals:
            stat[s["model"]] = stat.get(s["model"], 0) + 1
            if s["a"] != 0:
                signals_fired += 1
                if s["conf"] >= 0.80:
                    high_conf += 1
                    if len(sample_symbols) < 10:
                        sample_symbols[sym] = (s["model"], s["conf"], s["reason"])

print(f"Total Bars: {total_bars}")
print(f"Signale gesamt (alle Modelle, alle Bars): {sum(stat.values())}")
print(f"Signale mit a!=0 (gefeuert): {signals_fired}")
print(f"Signale conf>=0.80 (ODER-Logik greift): {high_conf}")
print("\nVerteilung nach Modell:")
for m, c in sorted(stat.items(), key=lambda x: -x[1]):
    print(f"  {m}: {c}")
print("\nBeispiele hoher Konfidenz:")
for sym, (m, conf, reason) in sample_symbols.items():
    print(f"  {sym}: {m} conf={conf:.2f} | {reason}")
