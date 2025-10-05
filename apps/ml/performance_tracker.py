import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
import json
import logging

from apps.api.config import settings

logger = logging.getLogger(__name__)


class PerformanceTracker:
    """
    Track and analyze model performance over time.
    Monitor for degradation, drift, and generate performance reports.
    """

    def __init__(self, tracking_dir: Optional[str] = None):
        self.tracking_dir = Path(tracking_dir or settings.PERFORMANCE_TRACKING_DIR)
        self.tracking_dir.mkdir(parents=True, exist_ok=True)

    def log_prediction_batch(
        self,
        model_id: str,
        symbol: str,
        timeframe: str,
        predictions: pd.DataFrame,
        actuals: Optional[pd.DataFrame] = None,
        metadata: Dict = None
    ):
        """
        Log a batch of predictions for tracking.

        Args:
            model_id: Model identifier
            symbol: Trading symbol
            timeframe: Timeframe
            predictions: DataFrame with predictions and probabilities
            actuals: DataFrame with actual outcomes (if available)
            metadata: Additional metadata
        """
        batch_id = f"{model_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        batch_dir = self.tracking_dir / model_id / "batches"
        batch_dir.mkdir(parents=True, exist_ok=True)

        batch_data = {
            'batch_id': batch_id,
            'model_id': model_id,
            'symbol': symbol,
            'timeframe': timeframe,
            'timestamp': datetime.utcnow().isoformat(),
            'num_predictions': len(predictions),
            'metadata': metadata or {}
        }

        # Save predictions
        predictions_path = batch_dir / f"{batch_id}_predictions.csv"
        predictions.to_csv(predictions_path, index=False)
        batch_data['predictions_path'] = str(predictions_path)

        # Save actuals if available
        if actuals is not None:
            actuals_path = batch_dir / f"{batch_id}_actuals.csv"
            actuals.to_csv(actuals_path, index=False)
            batch_data['actuals_path'] = str(actuals_path)

            # Calculate immediate metrics
            batch_data['metrics'] = self._calculate_batch_metrics(predictions, actuals)

        # Save batch metadata
        batch_meta_path = batch_dir / f"{batch_id}_metadata.json"
        with open(batch_meta_path, 'w') as f:
            json.dump(batch_data, f, indent=2, default=str)

        logger.info(f"Prediction batch logged: {batch_id}")

    def _calculate_batch_metrics(
        self,
        predictions: pd.DataFrame,
        actuals: pd.DataFrame
    ) -> Dict:
        """Calculate metrics for a prediction batch"""
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score

        # Merge predictions and actuals
        merged = pd.merge(
            predictions,
            actuals,
            on='timestamp',
            how='inner'
        )

        if len(merged) == 0:
            return {}

        y_true = merged['actual']
        y_pred = merged['prediction']
        y_proba = merged.get('probability', y_pred)

        metrics = {
            'accuracy': accuracy_score(y_true, y_pred),
            'precision': precision_score(y_true, y_pred, zero_division=0),
            'recall': recall_score(y_true, y_pred, zero_division=0),
            'f1_score': f1_score(y_true, y_pred, zero_division=0)
        }

        if len(np.unique(y_true)) > 1:
            metrics['roc_auc'] = roc_auc_score(y_true, y_proba)

        return metrics

    def update_actuals(
        self,
        model_id: str,
        batch_id: str,
        actuals: pd.DataFrame
    ):
        """
        Update actuals for a previously logged prediction batch.

        Args:
            model_id: Model identifier
            batch_id: Batch identifier
            actuals: DataFrame with actual outcomes
        """
        batch_dir = self.tracking_dir / model_id / "batches"
        batch_meta_path = batch_dir / f"{batch_id}_metadata.json"

        if not batch_meta_path.exists():
            logger.error(f"Batch metadata not found: {batch_id}")
            return

        # Load batch metadata
        with open(batch_meta_path, 'r') as f:
            batch_data = json.load(f)

        # Load predictions
        predictions = pd.read_csv(batch_data['predictions_path'])

        # Save actuals
        actuals_path = batch_dir / f"{batch_id}_actuals.csv"
        actuals.to_csv(actuals_path, index=False)
        batch_data['actuals_path'] = str(actuals_path)

        # Calculate metrics
        batch_data['metrics'] = self._calculate_batch_metrics(predictions, actuals)
        batch_data['actuals_updated_at'] = datetime.utcnow().isoformat()

        # Save updated metadata
        with open(batch_meta_path, 'w') as f:
            json.dump(batch_data, f, indent=2, default=str)

        logger.info(f"Actuals updated for batch: {batch_id}")

    def get_performance_summary(
        self,
        model_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict:
        """
        Get performance summary for a model over a time period.

        Args:
            model_id: Model identifier
            start_date: Start date (default: all time)
            end_date: End date (default: now)

        Returns:
            Performance summary dict
        """
        batch_dir = self.tracking_dir / model_id / "batches"

        if not batch_dir.exists():
            return {'error': f'No performance data for model: {model_id}'}

        batches = []
        for meta_file in batch_dir.glob("*_metadata.json"):
            with open(meta_file, 'r') as f:
                batch = json.load(f)

            batch_ts = datetime.fromisoformat(batch['timestamp'])

            if start_date and batch_ts < start_date:
                continue
            if end_date and batch_ts > end_date:
                continue

            if 'metrics' in batch:
                batches.append(batch)

        if not batches:
            return {'error': 'No batches with metrics found in specified period'}

        # Aggregate metrics
        metrics_df = pd.DataFrame([b['metrics'] for b in batches])

        summary = {
            'model_id': model_id,
            'num_batches': len(batches),
            'total_predictions': sum(b['num_predictions'] for b in batches),
            'period': {
                'start': min(b['timestamp'] for b in batches),
                'end': max(b['timestamp'] for b in batches)
            },
            'metrics': {
                'accuracy': {
                    'mean': metrics_df['accuracy'].mean(),
                    'std': metrics_df['accuracy'].std(),
                    'min': metrics_df['accuracy'].min(),
                    'max': metrics_df['accuracy'].max()
                },
                'precision': {
                    'mean': metrics_df['precision'].mean(),
                    'std': metrics_df['precision'].std(),
                    'min': metrics_df['precision'].min(),
                    'max': metrics_df['precision'].max()
                },
                'recall': {
                    'mean': metrics_df['recall'].mean(),
                    'std': metrics_df['recall'].std(),
                    'min': metrics_df['recall'].min(),
                    'max': metrics_df['recall'].max()
                },
                'f1_score': {
                    'mean': metrics_df['f1_score'].mean(),
                    'std': metrics_df['f1_score'].std(),
                    'min': metrics_df['f1_score'].min(),
                    'max': metrics_df['f1_score'].max()
                }
            }
        }

        if 'roc_auc' in metrics_df.columns:
            summary['metrics']['roc_auc'] = {
                'mean': metrics_df['roc_auc'].mean(),
                'std': metrics_df['roc_auc'].std(),
                'min': metrics_df['roc_auc'].min(),
                'max': metrics_df['roc_auc'].max()
            }

        return summary

    def detect_performance_degradation(
        self,
        model_id: str,
        metric: str = 'roc_auc',
        window_days: int = 7,
        threshold_pct: float = 10.0
    ) -> Dict:
        """
        Detect if model performance has degraded.

        Args:
            model_id: Model identifier
            metric: Metric to monitor
            window_days: Rolling window in days
            threshold_pct: Degradation threshold in percentage

        Returns:
            Degradation detection result
        """
        batch_dir = self.tracking_dir / model_id / "batches"

        if not batch_dir.exists():
            return {'degraded': False, 'error': 'No performance data'}

        batches = []
        for meta_file in batch_dir.glob("*_metadata.json"):
            with open(meta_file, 'r') as f:
                batch = json.load(f)
            if 'metrics' in batch and metric in batch['metrics']:
                batches.append({
                    'timestamp': datetime.fromisoformat(batch['timestamp']),
                    'value': batch['metrics'][metric]
                })

        if len(batches) < 2:
            return {'degraded': False, 'error': 'Insufficient data'}

        df = pd.DataFrame(batches).sort_values('timestamp')

        # Calculate baseline (first window_days)
        baseline_end = df['timestamp'].min() + timedelta(days=window_days)
        baseline_values = df[df['timestamp'] <= baseline_end]['value']

        if len(baseline_values) == 0:
            return {'degraded': False, 'error': 'No baseline data'}

        baseline_mean = baseline_values.mean()

        # Calculate recent performance (last window_days)
        recent_start = df['timestamp'].max() - timedelta(days=window_days)
        recent_values = df[df['timestamp'] >= recent_start]['value']

        if len(recent_values) == 0:
            return {'degraded': False, 'error': 'No recent data'}

        recent_mean = recent_values.mean()

        # Calculate degradation
        degradation_pct = ((baseline_mean - recent_mean) / baseline_mean) * 100

        degraded = degradation_pct > threshold_pct

        result = {
            'degraded': degraded,
            'metric': metric,
            'baseline_mean': baseline_mean,
            'recent_mean': recent_mean,
            'degradation_pct': degradation_pct,
            'threshold_pct': threshold_pct,
            'baseline_period': {
                'start': df['timestamp'].min().isoformat(),
                'end': baseline_end.isoformat()
            },
            'recent_period': {
                'start': recent_start.isoformat(),
                'end': df['timestamp'].max().isoformat()
            }
        }

        if degraded:
            logger.warning(
                f"Performance degradation detected for {model_id}: "
                f"{metric} dropped {degradation_pct:.2f}% "
                f"(from {baseline_mean:.4f} to {recent_mean:.4f})"
            )

        return result

    def generate_performance_report(
        self,
        model_id: str,
        output_path: Optional[str] = None
    ) -> str:
        """
        Generate comprehensive performance report.

        Args:
            model_id: Model identifier
            output_path: Path to save report (default: auto-generate)

        Returns:
            Path to generated report
        """
        summary = self.get_performance_summary(model_id)

        if 'error' in summary:
            logger.error(f"Cannot generate report: {summary['error']}")
            return None

        # Check for degradation on key metrics
        degradation_checks = []
        for metric in ['accuracy', 'precision', 'recall', 'f1_score', 'roc_auc']:
            if metric in summary['metrics']:
                deg = self.detect_performance_degradation(model_id, metric=metric)
                if not ('error' in deg):
                    degradation_checks.append(deg)

        report = {
            'model_id': model_id,
            'generated_at': datetime.utcnow().isoformat(),
            'summary': summary,
            'degradation_checks': degradation_checks,
            'alerts': []
        }

        # Generate alerts
        for check in degradation_checks:
            if check.get('degraded'):
                report['alerts'].append({
                    'severity': 'warning',
                    'metric': check['metric'],
                    'message': f"{check['metric']} degraded by {check['degradation_pct']:.2f}%"
                })

        # Save report
        if not output_path:
            report_dir = self.tracking_dir / model_id / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            output_path = report_dir / f"report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Performance report generated: {output_path}")

        return str(output_path)

    def compare_models_performance(
        self,
        model_id1: str,
        model_id2: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict:
        """
        Compare performance between two models.

        Args:
            model_id1: First model ID
            model_id2: Second model ID
            start_date: Start date
            end_date: End date

        Returns:
            Comparison dict
        """
        summary1 = self.get_performance_summary(model_id1, start_date, end_date)
        summary2 = self.get_performance_summary(model_id2, start_date, end_date)

        if 'error' in summary1 or 'error' in summary2:
            return {'error': 'One or both models have insufficient data'}

        comparison = {
            'model1_id': model_id1,
            'model2_id': model_id2,
            'period': summary1['period'],
            'metrics_comparison': {}
        }

        for metric in summary1['metrics']:
            if metric in summary2['metrics']:
                mean1 = summary1['metrics'][metric]['mean']
                mean2 = summary2['metrics'][metric]['mean']
                diff = mean2 - mean1
                pct_change = (diff / mean1 * 100) if mean1 != 0 else 0

                comparison['metrics_comparison'][metric] = {
                    'model1_mean': mean1,
                    'model2_mean': mean2,
                    'diff': diff,
                    'pct_change': pct_change,
                    'winner': model_id1 if mean1 > mean2 else model_id2
                }

        return comparison
