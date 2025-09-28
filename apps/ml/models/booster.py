# apps/ml/models/booster.py
from __future__ import annotations
import numpy as np
from typing import Dict, Any, Tuple

class BoosterModel:
    """
    LightGBM/XGBoost-like interface with safe fallbacks.
    """
    def __init__(self, params: Dict[str, Any] | None = None):
        self.params = params or {}
        self.model = None
        self.backend = None

    def fit(self, X: np.ndarray, y: np.ndarray):
        try:
            import lightgbm as lgb  # type: ignore
            ds = lgb.Dataset(X, label=y)
            self.model = lgb.train({"objective": "binary", "verbose": -1, **self.params}, ds, num_boost_round=200)
            self.backend = "lightgbm"
            return
        except Exception:
            pass
        try:
            import xgboost as xgb  # type: ignore
            d = xgb.DMatrix(X, label=y)
            self.model = xgb.train({"objective": "binary:logistic", **self.params}, d, num_boost_round=200)
            self.backend = "xgboost"
            return
        except Exception:
            pass
        # fallback: sklearn
        from sklearn.ensemble import GradientBoostingClassifier  # type: ignore
        self.model = GradientBoostingClassifier()
        self.model.fit(X, y)
        self.backend = "sklearn"

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.backend == "lightgbm":
            p = self.model.predict(X)
            return np.vstack([1 - p, p]).T
        if self.backend == "xgboost":
            import xgboost as xgb  # type: ignore
            d = xgb.DMatrix(X)
            p = self.model.predict(d)
            return np.vstack([1 - p, p]).T
        # sklearn
        return self.model.predict_proba(X)
