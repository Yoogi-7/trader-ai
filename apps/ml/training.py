from sqlalchemy.orm import Session
from sqlalchemy import and_
from apps.ml.models import EnsembleModel, ConformalPredictor
from apps.ml.features import FeatureEngineering
from apps.ml.labeling import TripleBarrierLabeling
from apps.ml.walkforward import WalkForwardValidator
from apps.ml.model_registry import ModelRegistry
from apps.ml.performance_tracker import PerformanceTracker
from apps.api.db.models import OHLCV, TimeFrame, MarketMetrics
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
        test_period_days: int = 21,  # Reduced from 30 for faster training
        min_train_days: int = 120,  # Reduced from 180 (4 months minimum)
        purge_days: int = 2,
        embargo_days: int = 1,
        use_expanding_window: bool = True,
        tp_pct: float = 0.02,
        sl_pct: float = 0.01,
        time_bars: int = 24,
        use_atr_labeling: bool = True,
        tp_atr_multiplier: float = 1.0,
        sl_atr_multiplier: float = 1.5,
        target_confidence: float = 0.55,
        training_mode: str = 'full'  # 'quick' or 'full'
    ):
        """
        Initialize walk-forward training pipeline.

        Args:
            training_mode: 'quick' for fast validation (3-4h, ~5 folds),
                          'full' for complete training (35-45h, ~45 folds)
        """
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.training_mode = training_mode

        # Adjust parameters based on training mode
        if training_mode == 'quick':
            # Quick validation: 3-4 hours, ~5 folds
            # Use last 6 months of data only, larger test periods
            test_period_days = 60  # 2 months per fold
            min_train_days = 180  # Start with 6 months
            use_expanding_window = False  # Fixed window for speed
            logger.info("🚀 QUICK TRAINING MODE: ~5 folds, 3-4 hours, validation only")
        else:
            # Full training: use provided parameters (35-45h, ~45 folds)
            logger.info("📊 FULL TRAINING MODE: ~45 folds, 35-45 hours, production model")

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
            time_bars=time_bars,
            use_atr=use_atr_labeling,
            tp_atr_multiplier=3.5,  # Increased from 2.0 to 3.5 (match TP2 in signal_engine)
            sl_atr_multiplier=1.0   # Match signal_engine SL multiplier
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

    def fetch_market_metrics(
        self,
        db: Session,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Fetch market microstructure metrics"""
        logger.info(
            f"Fetching market metrics for {symbol} from {start_date} to {end_date}"
        )

        query = db.query(MarketMetrics).filter(
            and_(
                MarketMetrics.symbol == symbol,
                MarketMetrics.timestamp >= start_date,
                MarketMetrics.timestamp <= end_date
            )
        ).order_by(MarketMetrics.timestamp)

        data = query.all()

        if not data:
            logger.warning(f"No market metrics found for {symbol}")
            return pd.DataFrame()

        df = pd.DataFrame([
            {
                'timestamp': row.timestamp,
                'funding_rate': row.funding_rate,
                'open_interest': row.open_interest,
                'spread_bps': row.spread_bps,
                'depth_imbalance': row.depth_imbalance,
                'realized_volatility': row.realized_volatility
            }
            for row in data
        ])

        logger.info(f"Fetched {len(df)} market metric rows")
        return df

    def prepare_features_and_labels(
        self,
        df: pd.DataFrame,
        market_metrics: pd.DataFrame = None,
        side: str = 'long',
        labeling_progress_callback=None
    ) -> pd.DataFrame:
        """Compute features and labels"""
        logger.info("Computing features...")
        df_features = self.feature_eng.compute_all_features(df, market_metrics=market_metrics)

        logger.info("Computing labels...")
        labels_df = self.labeler.label_data(
            df_features,
            side=side,
            progress_callback=labeling_progress_callback
        )

        logger.info(f"Labeling produced {len(labels_df)} labeled rows")

        if labels_df.empty:
            logger.error("Labeling returned empty DataFrame - insufficient data for time barrier")
            raise ValueError("Labeling failed: insufficient data rows for time barrier")

        labels_df['label'] = self.labeler.create_binary_labels(labels_df)
        logger.info(f"Binary labels created, proceeding to merge...")

        # Merge on timestamp to avoid leaking unlabeled rows
        merged = pd.merge(
            df_features,
            labels_df[['timestamp', 'label', 'hit_barrier', 'return_pct', 'bars_to_hit']],
            on='timestamp',
            how='inner'
        )

        logger.info(f"After merge: {len(merged)} samples (from {len(df_features)} features, {len(labels_df)} labels)")

        if merged.empty:
            logger.error("Merged feature/label frame is empty after join - timestamp mismatch?")
            raise ValueError("Feature/label merge failed: no matching timestamps")

        # Ensure essential label columns are present and non-null
        label_cols = ['label', 'hit_barrier', 'return_pct', 'bars_to_hit']
        merged = merged.dropna(subset=label_cols)

        # Replace non-finite values that can appear after technical indicator calculations
        merged = merged.replace([float('inf'), float('-inf')], pd.NA)

        # Forward/backward fill remaining feature NaNs, then fallback to zero to keep rows
        feature_cols = [
            col
            for col in merged.columns
            if col not in label_cols + ['timestamp', 'symbol', 'timeframe']
        ]

        if feature_cols:
            merged[feature_cols] = merged[feature_cols].ffill().bfill().fillna(0)

        merged = merged.replace({pd.NA: 0})

        logger.info(f"Features and labels prepared: {len(merged)} samples")
        if not merged.empty:
            logger.info(f"Label distribution: {merged['label'].value_counts().to_dict()}")
        else:
            logger.info("Label distribution: {}")

        return merged

    def run_walk_forward_validation(
        self,
        db: Session,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        side: str = 'long',
        progress_callback=None,
        labeling_progress_callback=None
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

        # 1b. Fetch supplemental data
        market_metrics = self.fetch_market_metrics(db, symbol, start_date, end_date)

        # 2. Prepare features and labels
        df_prepared = self.prepare_features_and_labels(
            df,
            market_metrics=market_metrics,
            side=side,
            labeling_progress_callback=labeling_progress_callback
        )

        # 3. Generate walk-forward splits
        logger.info(f"Generating walk-forward splits from prepared data ({len(df_prepared)} samples)...")
        splits = self.validator.generate_splits(df_prepared, start_date, end_date)

        if not splits:
            logger.error("No walk-forward splits could be generated - insufficient data or date range too short")
            raise ValueError("No walk-forward splits generated - check data availability and date ranges")

        logger.info(f"Generated {len(splits)} walk-forward splits - starting training...")

        # 4. Train and evaluate on each split
        split_results = []
        best_model = None
        best_oos_auc = 0.0

        feature_cols = self.feature_eng.get_feature_columns(df_prepared)
        logger.info(f"Selected {len(feature_cols)} feature columns for training")

        def _train_on_split(train_df, test_df, split_index: int, total_splits: int, train_bounds, test_bounds):
            nonlocal best_model, best_oos_auc

            if len(train_df) < 50 or len(test_df) < 10:
                logger.warning(
                    "Insufficient data in split %s (train=%s, test=%s). Skipping...",
                    split_index,
                    len(train_df),
                    len(test_df)
                )
                return None

            # Split into features and labels
            X_train = train_df[feature_cols]
            y_train = train_df['label']
            X_test = test_df[feature_cols]
            y_test = test_df['label']

            # Further split train into train/val for early stopping
            train_size = max(int(len(X_train) * 0.8), 1)
            X_train_fit = X_train.iloc[:train_size]
            y_train_fit = y_train.iloc[:train_size]
            X_val = X_train.iloc[train_size:]
            y_val = y_train.iloc[train_size:]

            if len(X_val) == 0:
                X_val = X_train_fit
                y_val = y_train_fit

            model = EnsembleModel()

            try:
                logger.info(
                    "Training ensemble model for split %s/%s (train=%s, test=%s)",
                    split_index,
                    total_splits,
                    len(train_df),
                    len(test_df)
                )
                model.train(X_train_fit, y_train_fit, X_val, y_val)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error("Training failed for split %s: %s", split_index, exc)
                return None

            test_metrics = model.evaluate(X_test, y_test)
            logger.info("OOS Test Metrics: %s", test_metrics)

            conformal = ConformalPredictor(model, target_confidence=self.target_confidence)
            conformal.calibrate(X_val, y_val)

            preds, conf, mask = conformal.filter_by_confidence(X_test)
            filtered_metrics = model.evaluate(X_test[mask], y_test[mask]) if mask.sum() > 0 else {}

            hit_rate_tp1 = float(test_df['label'].mean()) if len(test_df) > 0 else 0.0

            split_result = {
                'split_id': split_index - 1,
                'train_start': train_bounds[0],
                'train_end': train_bounds[1],
                'test_start': test_bounds[0],
                'test_end': test_bounds[1],
                'train_samples': len(train_df),
                'test_samples': len(test_df),
                'oos_metrics': test_metrics,
                'hit_rate_tp1': hit_rate_tp1,
                'filtered_coverage': mask.sum() / len(mask) if len(mask) > 0 else 0,
                'filtered_metrics': filtered_metrics
            }

            if progress_callback:
                progress_callback(
                    progress_pct=min(100.0, (split_index / max(total_splits, 1)) * 100.0),
                    current_fold=split_index,
                    total_folds=total_splits
                )

            if test_metrics.get('roc_auc', 0) > best_oos_auc:
                best_oos_auc = test_metrics['roc_auc']
                best_model = model
                logger.info("New best model found! OOS AUC: %.4f", best_oos_auc)
            elif best_model is None:
                best_model = model

            return split_result

        for i, split in enumerate(splits):
            logger.info(f"\n{'='*60}")
            logger.info(f"Split {i+1}/{len(splits)}")
            logger.info(f"Train: {split['train'][0].date()} to {split['train'][1].date()}")
            logger.info(f"Test: {split['test'][0].date()} to {split['test'][1].date()}")

            # Update progress to show we're now training (not labeling)
            if i == 0 and progress_callback:
                progress_callback(
                    progress_pct=5.0,
                    current_fold=1,
                    total_folds=len(splits)
                )

            # Get train/test data
            train_df, test_df = self.validator.get_train_test_data(df_prepared, split)
            # Validate no leakage
            if not self.validator.validate_no_leakage(train_df, test_df):
                logger.error(f"Leakage detected in split {i+1}, skipping...")
                continue

            split_result = _train_on_split(
                train_df,
                test_df,
                split_index=i + 1,
                total_splits=len(splits),
                train_bounds=split['train'],
                test_bounds=split['test']
            )

            if split_result:
                split_results.append(split_result)

        # 5. Aggregate results
        if not split_results:
            logger.warning("No valid walk-forward splits completed. Falling back to chronological hold-out training.")

            total_samples = len(df_prepared)
            if total_samples < 120:
                raise ValueError(
                    "Insufficient labeled data for training after fallback (need >= 120 rows, got %d)" % total_samples
                )

            test_size = max(int(total_samples * 0.2), 10)
            train_size = total_samples - test_size

            if train_size < 50:
                raise ValueError(
                    "Insufficient training window size after fallback (train=%d, test=%d)" % (train_size, test_size)
                )

            fallback_train = df_prepared.iloc[:train_size].copy()
            fallback_test = df_prepared.iloc[train_size:].copy()

            fallback_train_bounds = (
                fallback_train['timestamp'].min(),
                fallback_train['timestamp'].max()
            )
            fallback_test_bounds = (
                fallback_test['timestamp'].min(),
                fallback_test['timestamp'].max()
            )

            split_result = _train_on_split(
                fallback_train,
                fallback_test,
                split_index=1,
                total_splits=1,
                train_bounds=fallback_train_bounds,
                test_bounds=fallback_test_bounds
            )

            if not split_result:
                raise ValueError("Fallback training split could not be completed")

            split_results.append(split_result)

        if progress_callback:
            completed_folds = len(split_results)
            if completed_folds == len(splits) and len(splits) > 0:
                reported_total = len(splits)
            else:
                reported_total = max(completed_folds, 1)

            progress_callback(
                progress_pct=100.0,
                current_fold=completed_folds,
                total_folds=reported_total
            )

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

        hit_rates = [s.get('hit_rate_tp1') for s in split_results if s.get('hit_rate_tp1') is not None]
        if hit_rates:
            avg_metrics['avg_hit_rate_tp1'] = float(sum(hit_rates) / len(hit_rates))
            avg_metrics['std_hit_rate_tp1'] = float(pd.Series(hit_rates).std()) if len(hit_rates) > 1 else 0.0
        else:
            avg_metrics['avg_hit_rate_tp1'] = 0.0
            avg_metrics['std_hit_rate_tp1'] = 0.0

        return avg_metrics


def train_model_pipeline(
    db: Session,
    symbol: str,
    timeframe: str,
    test_period_days: int = 30,
    min_train_days: int = 180,
    use_expanding_window: bool = True,
    training_mode: str = 'full',
    start_date: datetime = None,
    end_date: datetime = None,
    progress_callback=None
) -> dict:
    """
    Complete training pipeline with walk-forward validation.

    Args:
        db: Database session
        training_mode: 'quick' for fast validation (3-4h), 'full' for production (35-45h)
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
        use_expanding_window=use_expanding_window,
        training_mode=training_mode
    )

    results = pipeline.run_walk_forward_validation(
        db=db,
        symbol=symbol,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        side='long',
        progress_callback=progress_callback.get('training') if isinstance(progress_callback, dict) else progress_callback,
        labeling_progress_callback=progress_callback.get('labeling') if isinstance(progress_callback, dict) else None
    )

    logger.info(f"Training completed: {results['model_id']}")

    return results
