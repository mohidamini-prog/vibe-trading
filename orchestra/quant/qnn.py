"""
Quant-Subagent — kleine QNN-Simulation (Variational Quantum Circuit).

Kein qiskit nötig: eigene, leichte Simulation für ARM (numpy-only).
Konzept (der "Baum"):
    |0> -> Encoding (RY/RX) -> variational Layers (Rotation + CNOT-Entanglement)
          -> Measurement -> Klassifikation.

4 Qubits => 2^4 = 16 Zustände (Superposition). 2 Layers = Tiefe 2.
Datenarm: nur 4 Features (ret, vola, rsi, vol_z). Kein 100-Feature-Vektor.
"""
import numpy as np


def _ry(theta):
    c, s = np.cos(theta / 2), np.sin(theta / 2)
    return np.array([[c, -s], [s, c]], dtype=complex)


def _rx(theta):
    c, s = np.cos(theta / 2), -1j * np.sin(theta / 2)
    return np.array([[c, s], [s, c]], dtype=complex)


def _cx(n_qubits, control, target):
    """CNOT-Gate auf n-Qubit-Zustand (Kontroll-/Target-Qubit)."""
    dim = 2 ** n_qubits
    U = np.eye(dim, dtype=complex)
    for i in range(dim):
        # Bit-Kontrolle prüfen (MSB-first: Qubit 0 = höchstes Bit)
        if (i >> (n_qubits - 1 - control)) & 1:
            j = i ^ (1 << (n_qubits - 1 - target))
            U[i, i], U[j, j] = 0, 0
            U[i, j], U[j, i] = 1, 1
    return U


def _measure_probabilities(state):
    """Wahrscheinlichkeiten der Basiszustände |0..2^n-1> (Superposition kollabiert)."""
    probs = np.abs(state) ** 2
    return probs / probs.sum()


class QNN:
    """
    Variational Quantum Circuit (Ansatz):
        |0>^n -> Encoding(features) -> [Layers: Rotation + Entanglement]^depth -> Measure
    Klassisches Training: Optimizer ändert die theta-Winkel AUSSEN (hybrid).
    """

    def __init__(self, n_qubits=4, n_layers=2, n_features=4, seed=42):
        self.n = n_qubits
        self.depth = n_layers
        self.nf = n_features
        self.rng = np.random.default_rng(seed)
        # Trainierbare Parameter: pro Layer 2 Winkel pro Qubit (RY, RZ)
        self.theta = self.rng.uniform(-np.pi, np.pi, (self.depth, self.n, 2))
        self.encoding_scale = 0.5  # Feature->Winkel Skalierung

    def _encode(self, features):
        """Encoding Layer: klassische Daten -> Rotationen RY(theta), RX(theta)."""
        state = np.zeros(2 ** self.n, dtype=complex)
        state[0] = 1.0  # Init |0...0>
        for q in range(self.n):
            f = features[q % self.nf] if len(features) else 0.0
            theta = self.encoding_scale * f
            # RY auf Qubit q
            I = np.eye(2 ** self.n, dtype=complex)
            for i in range(2 ** self.n):
                if (i >> (self.n - 1 - q)) & 1:
                    pass  # oberes Bit gesetzt => anderes Subspace
            # Einfach: 1-Qubit-Rotation als Kronecker-Produkt (vereinfacht)
        # Vereinfachtes Encoding: direkte Zustands-Phase pro Qubit
        for q in range(self.n):
            f = features[q % self.nf] if len(features) else 0.0
            theta = self.encoding_scale * f
            # RY(2*theta) auf einzelnes Qubit q
            g = _ry(2 * theta)
            # In den vollen Raum einbetten
            I_left = np.eye(2 ** q, dtype=complex)
            I_right = np.eye(2 ** (self.n - q - 1), dtype=complex)
            Uq = np.kron(np.kron(I_left, g), I_right)
            state = Uq @ state
        return state

    def _layer(self, state, layer_idx):
        """Variational Layer: Rotationen + Entanglement (der Baum)."""
        theta_l = self.theta[layer_idx]
        for q in range(self.n):
            # RY(θ1) dann RZ(θ2) — trainierbare Winkel
            g = _ry(theta_l[q, 0]) @ _rx(theta_l[q, 1])
            I_left = np.eye(2 ** q, dtype=complex)
            I_right = np.eye(2 ** (self.n - q - 1), dtype=complex)
            Uq = np.kron(np.kron(I_left, g), I_right)
            state = Uq @ state
        # Entanglement: CNOT-Kette (Qubit q -> q+1). DAS ist die Baum-Struktur.
        for q in range(self.n - 1):
            state = _cx(self.n, q, q + 1) @ state
        return state

    def forward(self, features):
        """Durchlauf: |0> -> encode -> layers -> measurement. Liefert Prob-Verteilung."""
        state = self._encode(np.asarray(features, dtype=float))
        for l in range(self.depth):
            state = self._layer(state, l)
        return _measure_probabilities(state)

    def predict(self, features):
        """
        Klassifikation: misst die Superposition. Liefert BUY/SELL/HOLD aus der
        Wahrscheinlichkeitsverteilung über die 16 Basiszustände.
        """
        probs = self.forward(features)
        # Obere Hälfte der Zustände => bullish, untere => bearish (Heuristik)
        mid = 2 ** (self.n - 1)
        p_buy = probs[mid:].sum()
        p_sell = probs[:mid].sum()
        net = p_buy - p_sell  # -1..+1
        if net > 0.25:
            return 1, abs(net), p_buy
        if net < -0.25:
            return -1, abs(net), p_sell
        return 0, 0.5 - abs(net) * 0.5, max(p_buy, p_sell)


if __name__ == "__main__":
    qnn = QNN(n_qubits=4, n_layers=2, n_features=4)
    for feats in ([0.5, 0.3, 0.2, 0.1], [-0.5, 0.1, 0.3, 0.4], [0.0, 0.0, 0.0, 0.0]):
        a, conf, p = qnn.predict(feats)
        print(f"features={feats} -> a={a}, conf={conf:.2f}, p_buy={p:.2f}")
