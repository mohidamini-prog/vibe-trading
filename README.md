# vibe-trading

Mohids quantitatives Trading-Forschungsrepo: Multi-Timeframe-Backtests, Kerzen-/Smart-Money-Muster-Scanner,
Live-Hourly-Scanner (Kraken Crypto + Yahoo Stocks), Pine-Script für TradingView und Blender-Animationen.

## Struktur

| Ordner | Inhalt |
|---|---|
| `scripts/scanners/` | Live-Scanner: `hourly_scan.py` (v8, 4h/1D, nur NEUE Signale), `hourly_scan_v9.py` (v9.1, Pivot-Breakouts + Volumen/Fakeout-Filter), `scan_german_stocks.py`, `news_fetcher.py` |
| `scripts/backtests/` | `strategy_backtest.py` (Haupt-Backtest: Trend/Breakout/Pullback mit ADX+Chop+BB-Seitwärts-Filter), `effective_strategy.py` (Fazit-Strategie: reiner Trend-Momentum), `trend_only_backtest.py`, alle Muster-/Multi-Timeframe-/DAX-/US-/Crypto-Backtests |
| `scripts/patterns/` | `pattern_detector.py`, `full_pattern_suite.py`, `scanner_50.py`, `strategy.pine`, `muster_scanner_mohid.pine` |
| `scripts/blender/` | `create_kitchen_scene.py`, `render_frames.py`, `render_full_animation.py`, `wuerfel_test.py` |
| `utils/` | `export_workspace.py` (Packt den Ordner als Zip) |
| `CRON_SETUP.md` | Betriebsanleitung für den Hourly-Scanner |
| `WERKZEUGE.md` | Werkzeug-Doku (lipsync, Blender, yfinance) |

## Installation

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Dann z. B.:

```bash
cd scripts/backtests && python strategy_backtest.py   # Backtest über 10 Kraken-Pairs
cd ../scanners && python hourly_scan.py               # Einmaliger Live-Scan
python effective_strategy.py                          # Fazit-Strategie auf DE-Blue-Chips + BTC
```

## Strategie-Status

- **4h/1h Kerzenmuster (Hammer, Engulfing) sind deaktiviert** — sie erzeugen in Intraday zu viel
  Rauschen, Fakeouts und Bull-Traps und lassen die Haupt-Trendbewegungen aus (siehe
  `scripts/backtests/effective_strategy.py` und `trend_only_backtest.py`).
- Aktiv ist der reine Trend-/Momentum-Ansatz (EMA-Stack + RSI) plus ein hartes Seitwärts-Filter
  (ADX > 25, Chop < 55, BB-Width nicht im untersten Dezil, RSI nicht 40–60).

## Hinweise

- `yfinance` ist inoffiziell und wird bei vielen Abfragen gedrosselt — die Skripte legen deshalb
  0.2–0.3 s Delays ein.
- Der Scanner schreibt `scanner_state*.json`, `signals_*.json`/`.txt` und `cron.log`
  in `/root/forschung` (in `.gitignore`).
