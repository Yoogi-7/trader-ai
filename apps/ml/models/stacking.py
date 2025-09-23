# apps/ml/models/stacking.py
from __future__ import annotations
import numpy as np
from typing import Dict, Any
from .booster import BoosterModel
from .seq import SeqModel

class StackingEnsemble:
    """
    Simple soft-voting ensemble booster + seq.
    """
    def __init__(self, params: Dict[str, Any] | None = None):
        self.params = params or {}
        self.boost = BoosterModel(self.params.get("booster"))
        self.seq = SeqModel(self.params.get("seq"))
        self.calibrator = None  # optional Platt scaling

    def fit(self, X_tab: np.ndarray, X_seq: np.ndarray, y: np.ndarray):
        self.boost.fit(X_tab, y)
        self.seq.fit(X_seq, y)
        # Optional: calibrator (Platt) on validation – pomijamy tutaj dla zwięzłości

    def predict_proba(self, X_tab: np.ndarray, X_seq: np.ndarray) -> np.ndarray:
        p1 = self.boost.predict_proba(X_tab)[:,1]
        p2 = self.seq.predict_proba(X_seq)[:,1]
        p = 0.5 * p1 + 0.5 * p2
        return np.vstack([1 - p, p]).T
