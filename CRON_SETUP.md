# Hourly Scanner - Cron Setup Guide

## 1. Install Dependencies
```bash
cd /root/forschung
pip3 install -r requirements.txt
```

## 2. Test Run (Manual)
```bash
cd /root/forschung
python3 hourly_scan.py
```
Expected output: Shows scanning progress, then either "No new signals" or formatted signal cards.

## 3. Install Cron Job (runs every hour at minute 5)
```bash
# Edit crontab
crontab -e

# Add this line:
5 * * * * /usr/bin/python3 /root/forschung/hourly_scan.py >> /root/forschung/cron.log 2>&1
```

## 4. Verify Cron is Running
```bash
# Check cron logs
tail -f /root/forschung/cron.log

# Check last signals
cat /root/forschung/signals_latest.txt
```

## 5. Telegram Integration (Optional)
To send signals to Telegram automatically, add a bot token and chat ID:

1. Create bot via @BotFather
2. Get chat ID: `curl "https://api.telegram.org/bot<TOKEN>/getUpdates"`
3. Add to hourly_scan.py (in main()):
```python
import requests
TELEGRAM_TOKEN = "YOUR_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"
requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
              json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
```

## 6. Files Created
- `/root/forschung/hourly_scan.py` — Main scanner
- `/root/forschung/strategy_backtest.py` — Backtest engine
- `/root/forschung/requirements.txt` — Python deps
- `/root/forschung/scanner_state.json` — Tracks last signals (auto-created)
- `/root/forschung/signals_latest.json` — Latest signals (JSON)
- `/root/forschung/signals_latest.txt` — Latest signals (human readable)
- `/root/forschung/cron.log` — Cron execution log

## 7. Strategy Summary
- **Timeframe**: 4h candles, 1D HTF filter
- **Universe**: 10 Kraken crypto pairs + 15 major US stocks
- **Strategy Mix**: TrendFollow + Breakout + Pullback (mean reversion only in trend direction)
- **Sideways Filter**: ADX>25, Chop<55, BB Width>P30, RSI not 40-60
- **Risk**: SL=2×ATR, TP=1.5R/2.5R/4R, Min Confidence 65%
- **Output**: Only NEW signals since last hourly run

## 8. Troubleshooting
- **yfinance rate limits**: Script has 0.2s delay between stocks
- **Kraken rate limits**: 0.3s delay between pairs
- **Missing data**: Check cron.log for errors
- **Timezone**: Cron runs in server timezone (UTC). Adjust cron time if needed.