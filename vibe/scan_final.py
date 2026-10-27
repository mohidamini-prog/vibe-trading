"""Finale Scanner-Signale auswerten."""
import json
from collections import defaultdict

sigs = json.load(open('/root/forschung/signals_latest.json'))
print('Signale im JSON:', len(sigs))

by_key = defaultdict(list)
for s in sigs:
    by_key[(s['symbol'], s['date'], s['direction'])].append(s)
print('Eindeutige Signale:', len(by_key))
print()

for s in sorted(sigs, key=lambda x: x['date'], reverse=True)[:30]:
    print(f"{s['date']} {s['symbol']:<8} {s['market']:<4} {s['setup']:<20} RSI={s['rsi']} Noise={s['noise']} Vol={s['vol_ratio']}x Entry={s['entry']}")
