"""Verifiziere Signale: SAP.DE letzte Tage, alle Setups."""
import sys
sys.path.insert(0, '/root/forschung/vibe')
from engine import backtest as bt, data as dl

df = dl.load_ticker('SAP.DE', years=5, timeframe='1d')
prep = bt.prepare(df)
print('Letzte 3 Tage SAP.DE:')
for ts in prep.index[-3:]:
    row = prep.loc[ts]
    sig = bt.SETUPS['meanrev_oversold'](prep).loc[ts]
    print(f'  {ts.date()} RSI={row["rsi"]:.1f} Close={row["Close"]:.2f} bb_lower={row["bb_lower"]:.2f} Signal={sig}')

print()
last = prep.index[-1]
print(f'Signale am {last.date()}:')
for name, fn in bt.SETUPS.items():
    if fn(prep).loc[last]:
        print(f'  {name}')

print()
# Alle DAX-Signale von heute mit meanrev_oversold: warum RSI 80?
print('=== Prüfe alle DAX-Signale heute (meanrev_oversold) ===')
import json
sigs = json.load(open('/root/forschung/signals_latest.json'))
today = [s for s in sigs if s['date'] == '2026-10-27' and s['market'] == 'DAX' and s['setup'] == 'meanrev_oversold']
print(f'Anzahl: {len(today)}')
for s in today[:5]:
    print(f"  {s['symbol']} RSI={s['rsi']} Close={s['entry']}")
