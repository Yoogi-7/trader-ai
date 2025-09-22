import numpy as np

def calibrate_threshold(probs: np.ndarray, labels: np.ndarray, target_hit: float = 0.55) -> float:
    # szukamy progu p*, który daje hit-rate >= 55% na walidacji
    for thr in np.linspace(0.5, 0.8, 61):
        hit = (probs >= thr).astype(int)
        hr = (hit == labels).mean()
        if hr >= target_hit:
            return float(thr)
    return 0.58
