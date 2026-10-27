# Orchestra — leichtes Quant-Trading-Orchester (Linux Phone, ARM)

**Idee:** Kein fetter Transformer, sondern ein **leichtes Orchester** aus 5 isolierten
Subagenten, die auf kleinen, zugeschnittenen Datensätzen arbeiten und über einen
**Dirigenten** gewichtet abstimmen. Datensparsam (<10MB/Tag), ARM-tauglich (numpy-only),
kein Auto-Trade am Anfang — nur Signale.

## Architektur (Baum + Layer)

```
orchestra/
├── config/            # FUNDAMENT: zentrale Pfade + Einstellungen (EINE Quelle)
│   ├── paths.py       #   alle Dateipfade, kein Hardcode anderswo
│   └── settings.yaml  #   Symbole, Tiers, Gewichte, Agenten-Parameter
├── tiers/             # LAYER 1: Daten-Tiers (datenarm)
│   ├── tier1.py       #   OHLCV (60%, immer, max 100 Kerzen, ~2KB/5min)
│   ├── tier2.py       #   Vola/Spread (25%, bei Bedarf)
│   └── tier3.py       #   News/Earnings/EDGAR (15%, stündlich, nur Filter)
├── data/              # LAYER 2: SQLite-Cache (candles.db, max 10MB)
│   └── cache.py       #   speichert nur close, volume, ema9, ema21, z_score
├── agents/            # LAYER 3: 5 isolierte Subagenten
│   ├── base.py        #   gemeinsames Interface (a, confidence, reason)
│   ├── a1_momentum.py #   A1 Trend-Folger (25%) — surft die Trend-Welle
│   ├── a2_meanrev.py  #   A2 Mean-Reversion (20%) — nur Beifang IM Trend
│   ├── a3_vola.py     #   A3 Vola/Risk (15%) — Bremser, VETO
│   ├── a4_quant.py    #   A4 Quant QNN (25%) — Quant-Subagent
│   └── a5_news.py     #   A5 News/Kalender/EDGAR (15%) — Event-Filter, VETO
├── quant/             # LAYER 4: QNN-Simulation (der "Baum")
│   └── qnn.py         #   |0> -> Encoding -> variational Layers + Entanglement -> Measure
├── conductor/         # LAYER 5: der Dirigent (Herzstück)
│   └── conductor.py   #   S=Σ(w·a·conf)/Σw, Schwellen ±0.5, dynamische Gewichte
└── utils/             #   Indikatoren (EMA, RSI, ATR, ADX, Chop, zscore) — numpy-only
```

## Gewichtung (Summe = 100%)

| Agent | Gewicht | Rolle | Datensatz (isoliert, zugeschnitten) |
|---|---|---|---|
| A1 Momentum | 25% | Trend-Folger (Wellenreiter) | EMA9/21, RSI, ADX, Chop |
| A2 MeanRev | 20% | Dip-Beifang IM Trend | z-score, SMA20 |
| A3 Vola/Risk | 15% | Bremser / VETO | ATR(14), Spread, Regime |
| A4 Quant (QNN) | 25% | Quant-Meinung | 4 Features: ret, vola, rsi, vol_z |
| A5 News/EDGAR | 15% | Event-Filter / VETO | Sentiment, Kalender, Form 4 |

## Dirigent-Formel

```
S = Σ(w_i · a_i · conf_i) / Σ(w_i)
    S > +0.5  => BUY
    S < -0.5  => SELL
    sonst     => HOLD
Stärke = |S| · avg_confidence

Dynamische Gewichte (nachts, offline):
    w_i_neu = w_i_alt · (1 + α · Sharpe_i)   # α = 0.05, Sharpe der letzten 20 Trades
```

## Ausführen

```bash
cd /root/forschung
.venv/bin/python -m orchestra                 # Einzel-Test (AAPL)
.venv/bin/python -m orchestra --universe     # ganzes Universum (schreibt signals_latest.txt)
```

## Daten-Tiers (Datensparsamkeit)

- **Tier 1** (60%, immer): OHLCV 5min, max 100 Kerzen, nur Close+Volume. ~2KB/Aktie/5min.
- **Tier 2** (25%, bei Bedarf): Vola-Regime, Spread. Alle 15-30min oder bei Tier-1-Alarm.
- **Tier 3** (15%, stündlich): News-Sentiment (nur Titel), Earnings-Kalender, SEC EDGAR Form 4.

## Status: MVP

- ✅ Fundament (Pfade, Config)
- ✅ Daten-Tiers + SQLite-Cache
- ✅ 5 isolierte Agenten + QNN
- ✅ Dirigent mit gewichteter Abstimmung
- ✅ Haupt-Entrypoint läuft über Universum
- ⏳ Nächste Schritte: Backtesting-Integration (Parameter-Feed in Agenten),
  dynamische Gewichts-Optimierung, echte Orderbook/Spread-Quelle, Auto-Trade (später)
