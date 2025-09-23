# apps/ml/models/conformal.py
from __future__ import annotations
import numpy as np
from typing import Tuple

class InductiveConformal:
    """
    Simple ICP for binary classification to yield calibrated confidence.
    """
    def __init__(self):
        self.cal_scores = None

    def fit(self, y_val: np.ndarray, p_val: np.ndarray):
        # nonconformity: 1 - p(true_class)
        sc = 1.0 - (p_val[:,1] * y_val + (1 - p_val[:,1]) * (1 - y_val))
        self.cal_scores = np.sort(sc)

    def confidence(self, p: np.ndarray) -> np.ndarray:
        # translate probability to conformal "confidence" ~ (1 - quantile)
        if self.cal_scores is None or len(self.cal_scores) == 0:
            return p[:,1]
        sc = 1.0 - np.maximum(p[:,1], 1 - p[:,1])
        rank = np.searchsorted(self.cal_scores, sc, side="right")
        conf = 1.0 - (rank / (len(self.cal_scores) + 1.0))
        return conf
