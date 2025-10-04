from sqlalchemy.orm import Session
from sqlalchemy import and_
from apps.ml.models import EnsembleModel, ConformalPredictor
from apps.ml.features import FeatureEngineering
from apps.ml.labeling import TripleBarrierLabeling
from apps.ml.walkforward import WalkForwardValidator
from apps.ml.model_registry import ModelRegistry
from apps.ml.performance_tracker import PerformanceTracker
from apps.api.db.models import OHLCV, TimeFrame
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


class WalkForwardPipeline:
    """
    Complete walk-forward validation pipeline for ML model training.
    """

    def __init__(
        self,
        model_dir: str = "./models",
        test_period_days: int = 30,
        min_train_days: int = 180,
        purge_days: int = 2,
        embargo_days: int = 1,
        use_expanding_window: bool = True,
        tp_pct: float = 0.02,
        sl_pct: float = 0.01,
        time_bars: int = 24,
        target_confidence: float = 0.55
    ):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        self.validator = WalkForwardValidator(
            test_period_days=test_period_days,
            min_train_days=min_train_days,
            purge_days=purge_days,
            embargo_days=embargo_days,
            use_expanding_window=use_expanding_window
        )

        self.feature_eng = FeatureEngineering()
        self.labeler = TripleBarrierLabeling(
            tp_pct=tp_pct,
            sl_pct=sl_pct,
            time_bars=time_bars
        )
        self.target_confidence = target_confidence

        self.results = []

    def fetch_ohlcv_data(
        self,
        db: Session,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Fetch OHLCV data from database"""
        logger.info(f"Fetching OHLCV data for {symbol} {timeframe} from {start_date} to {end_date}")

        query = db.query(OHLCV).filter(
            and_(
                OHLCV.symbol == symbol,
                OHLCV.timeframe == timeframe,
                OHLCV.timestamp >= start_date,
                OHLCV.timestamp <= end_date
            )
        ).order_by(OHLCV.timestamp)

        data = query.all()

        if not data:
            raise ValueError(f"No OHLCV data found for {symbol} {timeframe}")

        df = pd.DataFrame([{
            'timestamp': row.timestamp,
            'open': row.open,
            'high': row.high,
            'low': row.low,
            'close': row.close,
            'volume': row.volume
        } for row in data])

        logger.info(f"Fetched {len(df)} OHLCV bars")
        return df

    def prepare_features_and_labels(
        self,
        df: pd.DataFrame,
        side: str = 'long'
    ) -> pd.DataFrame:
        """Compute features and labels"""
        logger.info("Computing features...")
        df_features = self.feature_eng.compute_all_features(df)

        logger.info("Computing labels...")
        labels_df = self.labeler.label_data(df_features, side=side)
        binary_labels = self.labeler.create_binary_labels(labels_df)

        # Merge features and labels
        df_features['label'] = 0
        df_features.loc[labels_df.index, 'label'] = binary_labels.values

        # Drop rows with NaN (from feature engineering)
        df_features = df_features.dropna()

        logger.info(f"Features and labels prepared: {len(df_features)} samples")
        logger.info(f"Label distribution: {df_features['label'].value_counts().to_dict()}")

        return df_features

    def run_walk_forward_validation(
        self,
        db: Session,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        side: str = 'long'
    ) -> dict:
        """
        Run complete walk-forward validation pipeline.

        Returns:
            Dictionary with validation results and model metrics
        """
        logger.info(f"Starting walk-forward validation for {symbol} {timeframe}")
        logger.info(f"Period: {start_date.date()} to {end_date.date()}")

        # 1. Fetch data
        df = self.fetch_ohlcv_data(db, symbol, timeframe, start_date, end_date)

        # 2. Prepare features and labels
        df_prepared = self.prepare_features_and_labels(df, side=side)

        # 3. Generate walk-forward splits
        splits = self.validator.generate_splits(df_prepared, start_date, end_date)

        if not splits:
            raise ValueError("No walk-forward splits generated")

        logger.info(f"Generated {len(splits)} walk-forward splits")

        # 4. Train and evaluate on each split
        split_results = []
        best_model = None
        best_oos_auc = 0.0

        feature_cols = self.feature_eng.get_feature_columns(df_prepared)

        for i, split in enumerate(splits):
            logger.info(f"\n{'='*60}")
            logger.info(f"Split {i+1}/{len(splits)}")
            logger.info(f"Train: {split['train'][0].date()} to {split['train'][1].date()}")
            logger.info(f"Test: {split['test'][0].date()} to {split['test'][1].date()}")

            # Get train/test data
            train_df, test_df = self.validator.get_train_test_data(df_prepared, split)

            # Validate no leakage
            if not self.validator.validate_no_leakage(train_df, test_df):
                logger.error(f"Leakage detected in split {i+1}, skipping...")
                continue

            if len(train_df) < 100 or len(test_df) < 10:
                logger.warning(f"Insufficient data in split {i+1}, skipping...")
                continue

            # Split into features and labels
            X_train = train_df[feature_cols]
            y_train = train_df['label']
            X_test = test_df[feature_cols]
            y_test = test_df['label']

            # Further split train into train/val for early stopping
            train_size = int(len(X_train) * 0.8)
            X_train_fit = X_train.iloc[:train_size]
            y_train_fit = y_train.iloc[:train_size]
            X_val = X_train.iloc[train_size:]
            y_val = y_train.iloc[train_size:]

            # Train model
            logger.info(f"Training ensemble model...")
            model = EnsembleModel()

            try:
                model.train(X_train_fit, y_train_fit, X_val, y_val)
            except Exception as e:
                logger.error(f"Training failed for split {i+1}: {e}")
                continue

            # Evaluate on OOS test set
            test_metrics = model.evaluate(X_test, y_test)
            logger.info(f"OOS Test Metrics: {test_metrics}")

            # Calibrate conformal predictor on validation set
            conformal = ConformalPredictor(model, target_confidence=self.target_confidence)
            conformal.calibrate(X_val, y_val)

            # Test conformal predictions
            preds, conf, mask = conformal.filter_by_confidence(X_test)
            filtered_test_metrics = model.evaluate(X_test[mask], y_test[mask]) if mask.sum() > 0 else {}

            split_result = {
                'split_id': i,
                'train_start': split['train'][0],
                'train_end': split['train'][1],
                'test_start': split['test'][0],
                'test_end': split['test'][1],
                'train_samples': len(train_df),
                'test_samples': len(test_df),
                'oos_metrics': test_metrics,
                'filtered_coverage': mask.sum() / len(mask) if len(mask) > 0 else 0,
                'filtered_metrics': filtered_test_metrics
            }

            split_results.append(split_result)

            # Track best model (by OOS AUC)
            if test_metrics['roc_auc'] > best_oos_auc:
                best_oos_auc = test_metrics['roc_auc']
                best_model = model
                logger.info(f"New best model found! OOS AUC: {best_oos_auc:.4f}")

        # 5. Aggregate results
        if not split_results:
            raise ValueError("No valid splits completed")

        avg_metrics = self._aggregate_split_results(split_results)

        # 6. Save best model
        model_id = f"{symbol.replace('/', '_')}_{timeframe}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        model_path = self.model_dir / model_id

        if best_model:
            best_model.save(str(model_path))
            logger.info(f"Best model saved to {model_path}")

        # 7. Save validation results
        results = {
            'model_id': model_id,
            'symbol': symbol,
            'timeframe': timeframe,
            'side': side,
            'validation_period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'num_splits': len(split_results),
            'avg_metrics': avg_metrics,
            'split_results': split_results,
            'best_oos_auc': best_oos_auc,
            'feature_importance': best_model.get_feature_importance().to_dict() if best_model else {}
        }

        results_path = model_path / 'validation_results.json'
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        logger.info(f"Validation results saved to {results_path}")

        # 8. Register model in registry
        registry = ModelRegistry()
        version = registry.register_model(
            model_id=model_id,
            symbol=symbol,
            timeframe=timeframe,
            model_path=model_path,
            metrics=avg_metrics,
            metadata={
                'validation_period': results['validation_period'],
                'num_splits': len(split_results),
                'feature_importance_top10': best_model.get_feature_importance().head(10).to_dict() if best_model else {}
            }
        )

        results['registry_version'] = version

        logger.info(f"\n{'='*60}")
        logger.info(f"WALK-FORWARD VALIDATION COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"Model ID: {model_id}")
        logger.info(f"Registry Version: {version}")
        logger.info(f"Average OOS Metrics:")
        for metric, value in avg_metrics.items():
            logger.info(f"  {metric}: {value:.4f}")

        return results

    def _aggregate_split_results(self, split_results: list) -> dict:
        """Aggregate metrics across all splits"""
        metrics_keys = ['accuracy', 'precision', 'recall', 'f1_score', 'roc_auc']

        avg_metrics = {}
        for key in metrics_keys:
            values = [s['oos_metrics'].get(key, 0) for s in split_results if key in s['oos_metrics']]
            avg_metrics[f'avg_{key}'] = sum(values) / len(values) if values else 0.0
            avg_metrics[f'std_{key}'] = pd.Series(values).std() if len(values) > 1 else 0.0

        return avg_metrics


def train_model_pipeline(
    db: Session,
    symbol: str,
    timeframe: str,
    test_period_days: int = 30,
    min_train_days: int = 180,
    use_expanding_window: bool = True,
    start_date: datetime = None,
    end_date: datetime = None
) -> dict:
    """
    Complete training pipeline with walk-forward validation using expanding windows.

    Args:
        db: Database session
        symbol: Trading pair
        timeframe: Timeframe
        test_period_days: OOS test window size (default: 30 days)
        min_train_days: Minimum training data required (default: 180 days)
        use_expanding_window: Use expanding windows (trains on all history)
        start_date: Start date (default: earliest available data)
        end_date: End date (default: latest available data)

    Returns:
        Dictionary with training results
    """
    logger.info(f"Starting training pipeline for {symbol} {timeframe}")
    logger.info(f"Mode: {'Expanding' if use_expanding_window else 'Sliding'} window")

    # If dates not provided, fetch all available data
    if not start_date or not end_date:
        from sqlalchemy import func
        from apps.api.db.models import OHLCV

        date_range = db.query(
            func.min(OHLCV.timestamp).label('min_date'),
            func.max(OHLCV.timestamp).label('max_date')
        ).filter(
            OHLCV.symbol == symbol,
            OHLCV.timeframe == timeframe
        ).first()

        if not date_range or not date_range.min_date:
            raise ValueError(f"No OHLCV data found for {symbol} {timeframe}")

        start_date = start_date or date_range.min_date
        end_date = end_date or date_range.max_date

    logger.info(f"Using data from {start_date.date()} to {end_date.date()}")

    pipeline = WalkForwardPipeline(
        test_period_days=test_period_days,
        min_train_days=min_train_days,
        use_expanding_window=use_expanding_window
    )

    results = pipeline.run_walk_forward_validation(
        db=db,
        symbol=symbol,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        side='long'
    )

    logger.info(f"Training completed: {results['model_id']}")

    return results
