import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class DriftDetector:
    """
    Drift detection using PSI (Population Stability Index) and KS statistic.
    """

    def __init__(
        self,
        psi_threshold: float = 0.15,
        ks_threshold: float = 0.1
    ):
        self.psi_threshold = psi_threshold
        self.ks_threshold = ks_threshold

    def calculate_psi(
        self,
        baseline: np.ndarray,
        current: np.ndarray,
        bins: int = 10
    ) -> float:
        """
        Calculate Population Stability Index (PSI).

        Args:
            baseline: Baseline distribution (training data)
            current: Current distribution (production data)
            bins: Number of bins for discretization

        Returns:
            PSI score (>0.15 indicates significant drift)
        """
        # Create bins based on baseline
        breakpoints = np.histogram(baseline, bins=bins)[1]

        baseline_counts = np.histogram(baseline, bins=breakpoints)[0]
        current_counts = np.histogram(current, bins=breakpoints)[0]

        # Normalize to get percentages
        baseline_pct = baseline_counts / len(baseline)
        current_pct = current_counts / len(current)

        # Avoid division by zero
        baseline_pct = np.where(baseline_pct == 0, 0.0001, baseline_pct)
        current_pct = np.where(current_pct == 0, 0.0001, current_pct)

        # Calculate PSI
        psi = np.sum((current_pct - baseline_pct) * np.log(current_pct / baseline_pct))

        return psi

    def calculate_ks_statistic(
        self,
        baseline: np.ndarray,
        current: np.ndarray
    ) -> Tuple[float, float]:
        """
        Calculate Kolmogorov-Smirnov statistic.

        Returns:
            (ks_statistic, p_value)
        """
        ks_stat, p_value = stats.ks_2samp(baseline, current)
        return ks_stat, p_value

    def detect_feature_drift(
        self,
        baseline_df: pd.DataFrame,
        current_df: pd.DataFrame
    ) -> Dict[str, Dict]:
        """
        Detect drift for each feature.

        Returns:
            Dict of {feature: {psi, ks_stat, drift_detected}}
        """
        drift_results = {}

        for col in baseline_df.columns:
            if col in current_df.columns:
                baseline_vals = baseline_df[col].dropna().values
                current_vals = current_df[col].dropna().values

                if len(baseline_vals) == 0 or len(current_vals) == 0:
                    continue

                psi = self.calculate_psi(baseline_vals, current_vals)
                ks_stat, ks_pval = self.calculate_ks_statistic(baseline_vals, current_vals)

                drift_detected = (psi > self.psi_threshold) or (ks_stat > self.ks_threshold)

                drift_results[col] = {
                    'psi': psi,
                    'ks_statistic': ks_stat,
                    'ks_pvalue': ks_pval,
                    'drift_detected': drift_detected
                }

        return drift_results

    def detect_prediction_drift(
        self,
        baseline_predictions: np.ndarray,
        current_predictions: np.ndarray
    ) -> Dict:
        """
        Detect drift in model predictions.

        Returns:
            Drift metrics dict
        """
        psi = self.calculate_psi(baseline_predictions, current_predictions)
        ks_stat, ks_pval = self.calculate_ks_statistic(baseline_predictions, current_predictions)

        drift_detected = (psi > self.psi_threshold) or (ks_stat > self.ks_threshold)

        return {
            'psi': psi,
            'ks_statistic': ks_stat,
            'ks_pvalue': ks_pval,
            'drift_detected': drift_detected
        }

    def check_drift(
        self,
        baseline_features: pd.DataFrame,
        current_features: pd.DataFrame,
        baseline_predictions: np.ndarray = None,
        current_predictions: np.ndarray = None
    ) -> Dict:
        """
        Comprehensive drift check.

        Returns:
            {
                'feature_drift': {...},
                'prediction_drift': {...},
                'overall_drift_detected': bool
            }
        """
        feature_drift = self.detect_feature_drift(baseline_features, current_features)

        prediction_drift = None
        if baseline_predictions is not None and current_predictions is not None:
            prediction_drift = self.detect_prediction_drift(baseline_predictions, current_predictions)

        # Overall drift if any feature or prediction has drift
        overall_drift = any(f['drift_detected'] for f in feature_drift.values())

        if prediction_drift and prediction_drift['drift_detected']:
            overall_drift = True

        return {
            'feature_drift': feature_drift,
            'prediction_drift': prediction_drift,
            'overall_drift_detected': overall_drift,
            'num_features_with_drift': sum(f['drift_detected'] for f in feature_drift.values()),
            'total_features': len(feature_drift)
        }
