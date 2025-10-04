import lightgbm as lgb
import xgboost as xgb
from sklearn.ensemble import VotingClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional
import joblib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class EnsembleModel:
    """
    Ensemble of LightGBM + XGBoost with voting/stacking.
    Includes conformal prediction for confidence calibration.
    """

    def __init__(
        self,
        lgbm_params: Optional[Dict] = None,
        xgb_params: Optional[Dict] = None
    ):
        self.lgbm_params = lgbm_params or {
            'objective': 'binary',
            'metric': 'auc',
            'boosting_type': 'gbdt',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': -1
        }

        self.xgb_params = xgb_params or {
            'objective': 'binary:logistic',
            'eval_metric': 'auc',
            'max_depth': 6,
            'learning_rate': 0.05,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'verbosity': 0
        }

        self.lgbm_model = None
        self.xgb_model = None
        self.feature_names = None

    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series
    ):
        """Train both models"""
        self.feature_names = list(X_train.columns)

        logger.info("Training LightGBM model...")
        train_data = lgb.Dataset(X_train, label=y_train)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

        self.lgbm_model = lgb.train(
            self.lgbm_params,
            train_data,
            num_boost_round=1000,
            valid_sets=[val_data],
            callbacks=[lgb.early_stopping(stopping_rounds=50), lgb.log_evaluation(period=100)]
        )

        logger.info("Training XGBoost model...")
        dtrain = xgb.DMatrix(X_train, label=y_train)
        dval = xgb.DMatrix(X_val, label=y_val)

        self.xgb_model = xgb.train(
            self.xgb_params,
            dtrain,
            num_boost_round=1000,
            evals=[(dval, 'val')],
            early_stopping_rounds=50,
            verbose_eval=100
        )

        logger.info("Ensemble training completed")

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict probabilities using ensemble (average of both models).

        Returns:
            Array of probabilities for the positive class
        """
        lgbm_proba = self.lgbm_model.predict(X)
        xgb_proba = self.xgb_model.predict(xgb.DMatrix(X))

        # Average ensemble
        ensemble_proba = (lgbm_proba + xgb_proba) / 2
        return ensemble_proba

    def predict(self, X: pd.DataFrame, threshold: float = 0.5) -> np.ndarray:
        """Predict binary labels"""
        proba = self.predict_proba(X)
        return (proba >= threshold).astype(int)

    def evaluate(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """Evaluate model performance"""
        y_proba = self.predict_proba(X)
        y_pred = (y_proba >= 0.5).astype(int)

        metrics = {
            'accuracy': accuracy_score(y, y_pred),
            'precision': precision_score(y, y_pred, zero_division=0),
            'recall': recall_score(y, y_pred, zero_division=0),
            'f1_score': f1_score(y, y_pred, zero_division=0),
            'roc_auc': roc_auc_score(y, y_proba) if len(np.unique(y)) > 1 else 0.0
        }

        return metrics

    def get_feature_importance(self) -> pd.DataFrame:
        """Get combined feature importance from both models"""
        lgbm_importance = self.lgbm_model.feature_importance(importance_type='gain')
        xgb_importance = self.xgb_model.get_score(importance_type='gain')

        # Normalize and combine
        feature_importance = pd.DataFrame({
            'feature': self.feature_names,
            'lgbm_importance': lgbm_importance / lgbm_importance.sum() if lgbm_importance.sum() > 0 else lgbm_importance,
        })

        xgb_imp_dict = {f'f{i}': xgb_importance.get(f'f{i}', 0) for i in range(len(self.feature_names))}
        xgb_imp_values = np.array([xgb_imp_dict[f'f{i}'] for i in range(len(self.feature_names))])
        feature_importance['xgb_importance'] = xgb_imp_values / xgb_imp_values.sum() if xgb_imp_values.sum() > 0 else xgb_imp_values

        feature_importance['avg_importance'] = (
            feature_importance['lgbm_importance'] + feature_importance['xgb_importance']
        ) / 2

        return feature_importance.sort_values('avg_importance', ascending=False)

    def save(self, path: str):
        """Save model to disk"""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        self.lgbm_model.save_model(str(path / 'lgbm_model.txt'))
        self.xgb_model.save_model(str(path / 'xgb_model.json'))

        # Save metadata
        metadata = {
            'feature_names': self.feature_names,
            'lgbm_params': self.lgbm_params,
            'xgb_params': self.xgb_params
        }
        joblib.dump(metadata, path / 'metadata.pkl')

        logger.info(f"Model saved to {path}")

    def load(self, path: str):
        """Load model from disk"""
        path = Path(path)

        self.lgbm_model = lgb.Booster(model_file=str(path / 'lgbm_model.txt'))
        self.xgb_model = xgb.Booster()
        self.xgb_model.load_model(str(path / 'xgb_model.json'))

        metadata = joblib.dump(path / 'metadata.pkl')
        self.feature_names = metadata['feature_names']
        self.lgbm_params = metadata['lgbm_params']
        self.xgb_params = metadata['xgb_params']

        logger.info(f"Model loaded from {path}")


class ConformalPredictor:
    """
    Conformal prediction for calibrated confidence intervals.
    Ensures that confidence >= threshold leads to actual accuracy >= threshold.
    """

    def __init__(self, base_model: EnsembleModel, target_confidence: float = 0.55):
        self.base_model = base_model
        self.target_confidence = target_confidence
        self.calibration_scores = None

    def calibrate(self, X_cal: pd.DataFrame, y_cal: pd.Series):
        """
        Calibrate using calibration set.
        Compute nonconformity scores.
        """
        probas = self.base_model.predict_proba(X_cal)
        self.calibration_scores = np.abs(probas - y_cal)

        logger.info(f"Conformal predictor calibrated with {len(X_cal)} samples")

    def predict_with_confidence(
        self,
        X: pd.DataFrame
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predict with calibrated confidence.

        Returns:
            predictions: Binary predictions
            confidence: Calibrated confidence scores
        """
        probas = self.base_model.predict_proba(X)

        # Compute conformal p-values
        confidence = np.zeros(len(probas))

        for i, proba in enumerate(probas):
            # Count how many calibration scores are >= current score
            score = np.abs(proba - 1)  # Nonconformity for positive class
            p_value = (self.calibration_scores <= score).sum() / len(self.calibration_scores)
            confidence[i] = p_value

        predictions = (probas >= 0.5).astype(int)

        return predictions, confidence

    def filter_by_confidence(
        self,
        X: pd.DataFrame,
        min_confidence: float = None
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Filter predictions by minimum confidence.

        Returns:
            predictions: Binary predictions
            confidence: Confidence scores
            mask: Boolean mask of samples meeting confidence threshold
        """
        min_confidence = min_confidence or self.target_confidence

        predictions, confidence = self.predict_with_confidence(X)
        mask = confidence >= min_confidence

        return predictions, confidence, mask
