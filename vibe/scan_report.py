"""Scanner-Signale auswerten: deduplizieren und ausgeben."""
import json
from collections import defaultdict

sigs = json.load(open('/root/forschung/signals_latest.json'))
print('Rohe Signale:', len(sigs))

by_key = defaultdict(list)
for s in sigs:
    by_key[(s['symbol'], s['date'], s['direction'])].append(s)

deduped = []
for k, v in by_key.items():
    best = min(v, key=lambda x: (x['rsi'] if x['rsi'] is not None else 999))
    best['setups'] = len(v)
    deduped.append(best)

deduped.sort(key=lambda x: x['date'], reverse=True)
print('Eindeutige Signale:', len(deduped))
print()
for s in deduped[:30]:
    print(f"{s['date']} {s['symbol']:<8} {s['market']:<4} {s['setup']:<30} RSI={s['rsi']} Noise={s['noise']} Vol={s['vol_ratio']}x Entry={s['entry']}")
