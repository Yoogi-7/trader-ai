#!/usr/bin/env python3
"""
Example script demonstrating walk-forward validation pipeline usage.

This script shows how to:
1. Train a model using walk-forward validation
2. Register and deploy models
3. Track model performance
4. Compare model versions
5. Detect performance degradation
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from apps.api.db.session import SessionLocal
from apps.ml.training import train_model_pipeline, WalkForwardPipeline
from apps.ml.model_registry import ModelRegistry
from apps.ml.performance_tracker import PerformanceTracker
from datetime import datetime, timedelta
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def example_train_model():
    """Example: Train a model using walk-forward validation"""
    logger.info("="*80)
    logger.info("EXAMPLE 1: Train Model with Walk-Forward Validation")
    logger.info("="*80)

    db = SessionLocal()

    try:
        # Train model with walk-forward validation
        results = train_model_pipeline(
            db=db,
            symbol="BTC/USDT",
            timeframe="1h",
            lookback_days=365,  # 1 year of data
            train_period_days=180,  # 6 months training window
            test_period_days=30  # 1 month test window
        )

        logger.info(f"\nTraining Results:")
        logger.info(f"Model ID: {results['model_id']}")
        logger.info(f"Registry Version: {results['registry_version']}")
        logger.info(f"Number of Splits: {results['num_splits']}")
        logger.info(f"\nAverage OOS Metrics:")
        for metric, value in results['avg_metrics'].items():
            logger.info(f"  {metric}: {value:.4f}")

        return results['model_id'], results['registry_version']

    finally:
        db.close()


def example_list_models():
    """Example: List all registered models"""
    logger.info("\n" + "="*80)
    logger.info("EXAMPLE 2: List Registered Models")
    logger.info("="*80)

    registry = ModelRegistry()

    # List all models for BTC/USDT
    models = registry.list_models(symbol="BTC/USDT")

    logger.info(f"\nFound {len(models)} models for BTC/USDT:")
    for model in models[:5]:  # Show first 5
        logger.info(f"\n  Model: {model['model_id']}")
        logger.info(f"  Version: {model['version']}")
        logger.info(f"  Timeframe: {model['timeframe']}")
        logger.info(f"  Status: {model['status']}")
        logger.info(f"  OOS AUC: {model['metrics'].get('avg_roc_auc', 'N/A'):.4f}")


def example_deploy_model(symbol: str, timeframe: str, version: str):
    """Example: Deploy a model to production"""
    logger.info("\n" + "="*80)
    logger.info("EXAMPLE 3: Deploy Model to Production")
    logger.info("="*80)

    registry = ModelRegistry()

    # Deploy to production
    success = registry.deploy_model(
        symbol=symbol,
        timeframe=timeframe,
        version=version,
        environment="production"
    )

    if success:
        logger.info(f"\n✓ Model {version} deployed to production")

        # Get deployed model info
        deployed = registry.get_deployed_model(symbol, timeframe, "production")
        logger.info(f"\nCurrently Deployed:")
        logger.info(f"  Model: {deployed['model_id']}")
        logger.info(f"  Version: {deployed['version']}")
    else:
        logger.error("✗ Deployment failed")


def example_compare_models(symbol: str, timeframe: str):
    """Example: Compare model versions"""
    logger.info("\n" + "="*80)
    logger.info("EXAMPLE 4: Compare Model Versions")
    logger.info("="*80)

    registry = ModelRegistry()

    # Get two versions to compare
    models = registry.list_models(symbol=symbol, timeframe=timeframe)

    if len(models) < 2:
        logger.warning("Need at least 2 models to compare")
        return

    v1 = models[-2]['version']  # Second latest
    v2 = models[-1]['version']  # Latest

    comparison = registry.compare_models(symbol, timeframe, v1, v2)

    logger.info(f"\nComparing {v1} vs {v2}:")
    logger.info(f"\nMetrics Comparison:")

    for metric, data in comparison['metrics_comparison'].items():
        logger.info(f"\n  {metric}:")
        logger.info(f"    {v1}: {data['version1']:.4f}")
        logger.info(f"    {v2}: {data['version2']:.4f}")
        logger.info(f"    Change: {data['pct_change']:+.2f}%")
        logger.info(f"    Winner: {data.get('winner', 'N/A')}")


def example_get_best_model(symbol: str, timeframe: str):
    """Example: Get best model by metric"""
    logger.info("\n" + "="*80)
    logger.info("EXAMPLE 5: Get Best Model by Metric")
    logger.info("="*80)

    registry = ModelRegistry()

    best = registry.get_best_model(symbol, timeframe, metric='avg_roc_auc')

    if best:
        logger.info(f"\nBest Model (by avg_roc_auc):")
        logger.info(f"  Model: {best['model_id']}")
        logger.info(f"  Version: {best['version']}")
        logger.info(f"  Status: {best['status']}")
        logger.info(f"  Metrics:")
        for metric, value in best['metrics'].items():
            logger.info(f"    {metric}: {value:.4f}")


def example_track_performance(model_id: str):
    """Example: Track model performance over time"""
    logger.info("\n" + "="*80)
    logger.info("EXAMPLE 6: Track Model Performance")
    logger.info("="*80)

    tracker = PerformanceTracker()

    # Note: In production, you would have logged prediction batches
    # This is just demonstrating the API

    summary = tracker.get_performance_summary(model_id)

    if 'error' not in summary:
        logger.info(f"\nPerformance Summary for {model_id}:")
        logger.info(f"  Number of Batches: {summary['num_batches']}")
        logger.info(f"  Total Predictions: {summary['total_predictions']}")
        logger.info(f"\nMetrics:")
        for metric, stats in summary['metrics'].items():
            logger.info(f"\n  {metric}:")
            logger.info(f"    Mean: {stats['mean']:.4f}")
            logger.info(f"    Std: {stats['std']:.4f}")
            logger.info(f"    Range: [{stats['min']:.4f}, {stats['max']:.4f}]")
    else:
        logger.info(f"\n{summary['error']}")


def example_detect_degradation(model_id: str):
    """Example: Detect performance degradation"""
    logger.info("\n" + "="*80)
    logger.info("EXAMPLE 7: Detect Performance Degradation")
    logger.info("="*80)

    tracker = PerformanceTracker()

    degradation = tracker.detect_performance_degradation(
        model_id=model_id,
        metric='roc_auc',
        window_days=7,
        threshold_pct=10.0
    )

    if 'error' not in degradation:
        logger.info(f"\nDegradation Check for {model_id}:")
        logger.info(f"  Metric: {degradation['metric']}")
        logger.info(f"  Degraded: {'⚠️  YES' if degradation['degraded'] else '✓ NO'}")
        logger.info(f"  Baseline Mean: {degradation['baseline_mean']:.4f}")
        logger.info(f"  Recent Mean: {degradation['recent_mean']:.4f}")
        logger.info(f"  Degradation: {degradation['degradation_pct']:.2f}%")
        logger.info(f"  Threshold: {degradation['threshold_pct']:.2f}%")

        if degradation['degraded']:
            logger.warning("\n⚠️  Performance degradation detected! Consider retraining or rollback.")
    else:
        logger.info(f"\n{degradation['error']}")


def example_rollback(symbol: str, timeframe: str):
    """Example: Rollback deployment"""
    logger.info("\n" + "="*80)
    logger.info("EXAMPLE 8: Rollback Deployment")
    logger.info("="*80)

    registry = ModelRegistry()

    # Get current deployment
    current = registry.get_deployed_model(symbol, timeframe, "production")
    if current:
        logger.info(f"\nCurrent Deployment: {current['version']}")

    # Rollback
    success = registry.rollback_deployment(symbol, timeframe, "production")

    if success:
        # Get new deployment
        new = registry.get_deployed_model(symbol, timeframe, "production")
        logger.info(f"✓ Rolled back to: {new['version']}")
    else:
        logger.error("✗ Rollback failed")


def main():
    """Run all examples"""
    logger.info("\n" + "🚀 "*40)
    logger.info("WALK-FORWARD VALIDATION PIPELINE EXAMPLES")
    logger.info("🚀 "*40 + "\n")

    # Note: These examples assume you have OHLCV data in the database
    # If not, you'll need to run the backfill process first

    try:
        # Example 1: Train a model
        # Uncomment to run (requires OHLCV data):
        # model_id, version = example_train_model()

        # For demonstration, use a mock model_id
        model_id = "BTC_USDT_1h_20240101_120000"
        version = "v1"

        # Example 2: List models
        example_list_models()

        # Example 3: Deploy model (if you have trained one)
        # example_deploy_model("BTC/USDT", "1h", version)

        # Example 4: Compare models (if you have multiple)
        # example_compare_models("BTC/USDT", "1h")

        # Example 5: Get best model
        # example_get_best_model("BTC/USDT", "1h")

        # Example 6: Track performance
        example_track_performance(model_id)

        # Example 7: Detect degradation
        example_detect_degradation(model_id)

        # Example 8: Rollback (if deployed)
        # example_rollback("BTC/USDT", "1h")

        logger.info("\n" + "="*80)
        logger.info("✓ Examples completed successfully")
        logger.info("="*80 + "\n")

    except Exception as e:
        logger.error(f"Error running examples: {e}", exc_info=True)


if __name__ == "__main__":
    main()
