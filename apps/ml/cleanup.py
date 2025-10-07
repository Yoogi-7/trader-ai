"""
Performance Tracking Cleanup System

This module provides automatic cleanup for old performance tracking files
to prevent disk space issues.
"""

import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)


class PerformanceTrackingCleanup:
    """
    Automatic cleanup for performance tracking directories.

    Performance tracking creates directories with predictions and metrics
    for each model. These can accumulate over time and consume disk space.

    This cleanup system:
    - Keeps only the N most recent model directories
    - Deletes directories older than X days
    - Preserves currently deployed models
    """

    def __init__(
        self,
        tracking_dir: str = "./performance_tracking",
        max_age_days: int = 30,
        max_models_per_symbol: int = 5
    ):
        self.tracking_dir = Path(tracking_dir)
        self.max_age_days = max_age_days
        self.max_models_per_symbol = max_models_per_symbol

    def cleanup(self) -> Dict:
        """
        Run cleanup process.

        Returns:
            Dictionary with cleanup statistics
        """
        if not self.tracking_dir.exists():
            logger.info(f"Performance tracking directory {self.tracking_dir} does not exist, skipping cleanup")
            return {
                "status": "skipped",
                "reason": "directory_not_found"
            }

        deleted_count = 0
        deleted_size_mb = 0
        kept_count = 0
        errors = []

        # Get all model directories
        model_dirs = [d for d in self.tracking_dir.iterdir() if d.is_dir()]

        if not model_dirs:
            logger.info("No model directories found in performance tracking")
            return {
                "status": "completed",
                "deleted": 0,
                "kept": 0,
                "deleted_size_mb": 0
            }

        logger.info(f"Found {len(model_dirs)} model directories")

        # Group directories by symbol
        by_symbol = {}
        for model_dir in model_dirs:
            # Extract symbol from directory name (format: SYMBOL_TIMEFRAME_TIMESTAMP)
            parts = model_dir.name.split('_')
            if len(parts) >= 2:
                symbol = '_'.join(parts[:-2])  # Handle symbols with underscores
                if symbol not in by_symbol:
                    by_symbol[symbol] = []
                by_symbol[symbol].append(model_dir)

        # Cleanup for each symbol
        for symbol, dirs in by_symbol.items():
            logger.info(f"Cleaning up {len(dirs)} directories for {symbol}")

            # Sort by modification time (newest first)
            dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)

            # Keep N most recent
            to_keep = dirs[:self.max_models_per_symbol]
            to_check = dirs[self.max_models_per_symbol:]

            # Keep recent directories
            for d in to_keep:
                kept_count += 1
                logger.debug(f"Keeping recent directory: {d.name}")

            # Check age for remaining directories
            cutoff_time = datetime.now().timestamp() - (self.max_age_days * 24 * 3600)

            for d in to_check:
                mtime = d.stat().st_mtime

                if mtime < cutoff_time:
                    try:
                        # Calculate size before deletion
                        size_bytes = sum(
                            f.stat().st_size for f in d.rglob('*') if f.is_file()
                        )
                        size_mb = size_bytes / (1024 * 1024)

                        logger.info(
                            f"Deleting old directory: {d.name} "
                            f"(age: {(datetime.now().timestamp() - mtime) / 86400:.1f} days, "
                            f"size: {size_mb:.2f} MB)"
                        )

                        shutil.rmtree(d)

                        deleted_count += 1
                        deleted_size_mb += size_mb

                    except Exception as e:
                        logger.error(f"Failed to delete directory {d.name}: {e}")
                        errors.append({
                            "directory": d.name,
                            "error": str(e)
                        })
                else:
                    # Directory is recent but exceeded max_models_per_symbol limit
                    # Still keep it if it's not too old
                    kept_count += 1
                    logger.debug(f"Keeping directory (within age limit): {d.name}")

        result = {
            "status": "completed",
            "deleted": deleted_count,
            "kept": kept_count,
            "deleted_size_mb": round(deleted_size_mb, 2),
            "errors": errors
        }

        logger.info(
            f"Cleanup completed: deleted {deleted_count} directories "
            f"({deleted_size_mb:.2f} MB), kept {kept_count}"
        )

        return result

    def get_tracking_stats(self) -> Dict:
        """
        Get statistics about performance tracking directories.

        Returns:
            Dictionary with directory statistics
        """
        if not self.tracking_dir.exists():
            return {
                "exists": False,
                "total_directories": 0,
                "total_size_mb": 0
            }

        model_dirs = [d for d in self.tracking_dir.iterdir() if d.is_dir()]

        total_size = 0
        for d in model_dirs:
            total_size += sum(
                f.stat().st_size for f in d.rglob('*') if f.is_file()
            )

        by_symbol = {}
        for model_dir in model_dirs:
            parts = model_dir.name.split('_')
            if len(parts) >= 2:
                symbol = '_'.join(parts[:-2])
                if symbol not in by_symbol:
                    by_symbol[symbol] = 0
                by_symbol[symbol] += 1

        return {
            "exists": True,
            "total_directories": len(model_dirs),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "by_symbol": by_symbol
        }
