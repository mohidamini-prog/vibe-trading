"""
A4 — Quant Agent (25% Gewicht): der Quant-Subagent.

Eigener, zugeschnittener Datensatz: nur 4 Features (ret, vola, rsi, vol_z).
Kein 100-Feature-Vektor. Läuft über die QNN-Simulation (baum-artig).
"""
import numpy as np

from orchestra.agents.base import BaseAgent
from orchestra.config import get
from orchestra.utils import indicators
from orchestra.quant.qnn import QNN


class QuantAgent(BaseAgent):
    name = "quant"

    def __init__(self, config=None, qnn=None):
        super().__init__(config)
        nq = get("agents.quant.n_qubits", 4)
        nl = get("agents.quant.n_layers", 2)
        self.qnn = qnn if qnn is not None else QNN(n_qubits=nq, n_layers=nl,
                                                   n_features=len(get("agents.quant.features", ["ret", "vola", "rsi", "vol_z"])))
        self.features = get("agents.quant.features", ["ret", "vola", "rsi", "vol_z"])

    def _feature_vector(self, close, high, low, volume):
        """Nur 4 Features, datenarm."""
        if len(close) < 30:
            return np.zeros(4)
        ret = (close[-1] - close[-2]) / close[-2] if close[-2] != 0 else 0
        atr = indicators.atr(high, low, close, 14)[-1]
        vola = atr / close[-1] if close[-1] != 0 else 0
        rsi = indicators.rsi(close, 14)[-1] / 100.0 - 0.5  # -0.5..0.5
        vol = np.asarray(volume, dtype=float)
        v_mean = vol[-20:].mean() if len(vol) >= 20 else vol.mean() if len(vol) else 1
        v_std = vol[-20:].std() if len(vol) >= 20 else 1
        vol_z = (vol[-1] - v_mean) / v_std if v_std > 0 else 0
        return np.array([ret * 10, vola * 10, rsi, vol_z * 0.5], dtype=float)

    def vote(self, data):
        close = np.asarray(data.get("close", []), dtype=float)
        high = np.asarray(data.get("high", close), dtype=float)
        low = np.asarray(data.get("low", close), dtype=float)
        volume = np.asarray(data.get("volume", []), dtype=float)
        if len(close) < 30:
            return self._make(0, 0.1, "zu wenig Daten")

        features = self._feature_vector(close, high, low, volume)
        a, conf, p = self.qnn.predict(features)
        reason = f"QNN: a={a}, p_buy={p:.2f}"
        return self._make(a, conf, reason, features=features.round(3).tolist())


if __name__ == "__main__":
    np.random.seed(4)
    close = np.cumsum(np.random.randn(80) * 0.3) + 100 + np.linspace(0, 15, 80)
    high, low = close + 0.5, close - 0.5
    volume = np.abs(np.random.randn(80) * 1000) + 500
    a = QuantAgent()
    print(a.vote({"close": close, "high": high, "low": low, "volume": volume}))
