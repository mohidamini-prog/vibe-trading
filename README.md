# vibe-trading

Mohids quantitatives Trading-Forschungsrepo: Multi-Timeframe-Backtests, Kerzen-/Smart-Money-Muster-Scanner,
Live-Hourly-Scanner (Kraken Crypto + Yahoo Stocks) und Pine-Script für TradingView.

## Struktur

| Ordner / Datei | Inhalt |
|---|---|
| `hourly_scan.py` | Live-Hourly-Scanner v8 (Kraken + Yahoo, 4h/1D, nur NEUE Signale) |
| `hourly_scan_v9.py` | Live-Scanner v9.1 (Pivot-Breakouts, Volumen- und Fakeout-Filter) |
| `strategy_backtest.py` | Haupt-Backtest: Trend / Breakout / Pullback mit ADX+Chop+BB-Seitwärts-Filter |
| `effective_strategy.py` | **Fazit-Strategie**: reiner Trend-Momentum, Kerzenmuster deaktiviert |
| `trend_only_backtest.py` | Rein-EMA+RSI-Test (belegt den Muster-Noise-Befund) |
| `pattern_detector.py`, `full_pattern_suite.py`, `scanner_50.py` | Muster-Erkennung (Hammer, Engulfing, FVG, Order Blocks, Liquidity Sweeps) |
| `multitimeframe_backtest*.py` | 4h-Trigger mit 1D-Trendfilter |
| `german_stocks_backtest.py`, `scan_german_stocks.py`, `hourly_german_backtest.py` | DAX / DAX-Blue-Chips (.DE) |
| `us_stocks_pattern_backtest.py`, `crypto_pattern_backtest.py` | US-Tech & Krypto |
| `backtest_dax.py`, `backtest_dax_meanrev.py`, `adaptive_strategy.py` | DAX-Momentum vs. Mean-Reversion |
| `strategy.pine`, `muster_scanner_mohid.pine` | TradingView-Pine-Script (v5) |
| `news_fetcher.py` | Yahoo-RSS-News für Ticker |
| `blender_test/`, `render_*.py`, `create_kitchen_scene.py` | Headless-Blender-Animationen |
| `CRON_SETUP.md`, `WERKZEUGE.md` | Betriebs- und Werkzeug-Doku |

## Installation

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Dann z. B.:

```bash
python strategy_backtest.py     # Backtest über 10 Kraken-Pairs
python hourly_scan.py           # Einmaliger Live-Scan
python effective_strategy.py    # Fazit-Strategie auf DE-Blue-Chips + BTC
```

## Strategie-Status

- **4h / 1h Kerzenmuster (Hammer, Engulfing) sind deaktiviert** — sie erzeugen in Intraday zu viel
  Rauschen, Fakeouts und Bull-Traps und lassen die Haupt-Trendbewegungen aus (siehe
  `effective_strategy.py` und `trend_only_backtest.py`).
- Aktiv ist der reine Trend-/Momentum-Ansatz (EMA-Stack + RSI) plus ein hartes Seitwärts-Filter
  (ADX > 25, Chop < 55, BB-Width nicht im untersten Dezil, RSI nicht 40–60).

## Hinweise

- `yfinance` ist inoffiziell und wird bei vielen Abfragen gedrosselt — die Skripte legen deshalb
  0.2–0.3 s Delays ein.
- Der Scanner schreibt `scanner_state.json`, `signals_latest.json` bzw. `.txt` und `cron.log`
  in den Repo-Root (in `.gitignore`).
