"""
Tier 2 — WENIGER WICHTIG (25%), nur bei Bedarf (alle 15-30min oder bei Tier-1-Alarm).

Orderbook-Spread, Volatilitäts-Regime (wild vs. ruhig), ggf. Funding Rate (Crypto).
"""
from orchestra.config import get
import numpy as np


def _regime(atr_value, atr_baseline):
    """Volatilitäts-Regime: 'calm', 'normal', 'wild'. Basierend auf ATR vs. Baseline."""
    if atr_baseline <= 0 or atr_value is None:
        return "normal"
    ratio = atr_value / atr_baseline
    if ratio > get("agents.vola.atr_spike_mult", 2.5):
        return "wild"
    if ratio < 0.7:
        return "calm"
    return "normal"


def fetch_tier2(symbol, atr_value=None, atr_baseline=None):
    """
    Liefert Tier-2-Metadaten. Bei echten Daten: Spread aus Orderbook (z.B. Alpaca/Tradegate),
    sonst aus ATR-Verhältnis abgeleitet (Offline-Fallback).
    """
    regime = _regime(atr_value, atr_baseline)
    return {
        "symbol": symbol,
        "vola_regime": regime,
        "spread_pct": None,          # bei echter API: (ask-bid)/mid*100
        "funding_rate": None,        # nur Crypto
        "needs_refresh": regime == "wild",   # wild => nächsten Tick schneller ziehen
    }


if __name__ == "__main__":
    print(fetch_tier2("AAPL", atr_value=3.1, atr_baseline=1.2))
    print(fetch_tier2("AAPL", atr_value=1.0, atr_baseline=1.2))
