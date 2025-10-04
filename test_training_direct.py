#!/usr/bin/env python3
"""
Test training pipeline directly without Celery
"""
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from apps.api.db.session import SessionLocal
from apps.ml.training import train_model_pipeline
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_training():
    db = SessionLocal()
    try:
        logger.info("Testing training pipeline...")

        results = train_model_pipeline(
            db=db,
            symbol="BTC/USDT",
            timeframe="1h",
            test_period_days=30,
            min_train_days=180,
            use_expanding_window=True
        )

        logger.info(f"Success! Model ID: {results['model_id']}")
        logger.info(f"Version: {results.get('registry_version')}")
        logger.info(f"Metrics: {results.get('avg_metrics')}")

    except Exception as e:
        logger.error(f"Training failed: {e}", exc_info=True)
    finally:
        db.close()

if __name__ == "__main__":
    test_training()
