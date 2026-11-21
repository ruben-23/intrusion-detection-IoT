
"""Model AI SIMULAT (heuristic, nu e antrenat).
predict(features) -> (label, confidence).
Se poate înlocui ulterior cu LightGBM/ONNX."""


class MockIDS:
    ATTACK_LABEL = "DoS-HTTP_Flood"
    SYN_LABEL = "SYN_Flood"

    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold

    def predict(self, f: dict):
        syn_count = f.get("syn_count", 0)
        rst_count = f.get("rst_flag_number", 0)

        # Regulă pentru identificarea SYN Flood
        if syn_count >= 15 and rst_count <= 0.1:
            confidence = min(
                round(0.7 + (syn_count / 100.0), 3),
                0.99
            )
            return self.SYN_LABEL, confidence

        # Scorul heuristic inițial
        score = (
            0.45 * min(f.get("Rate", 0) / 1000.0, 1.0)
            + 0.30 * min(rst_count / 0.5, 1.0)
            + 0.15 * min(syn_count / 15.0, 1.0)
            + 0.10 * (1.0 if f.get("IAT", 1) < 0.01 else 0.0)
        )

        score = round(min(score, 1.0), 3)

        return (
            self.ATTACK_LABEL if score >= self.threshold else "Benign",
            score
        )
