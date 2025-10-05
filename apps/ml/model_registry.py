import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union
import logging

from apps.api.config import settings
from apps.api.db.models import RiskProfile

logger = logging.getLogger(__name__)


class ModelRegistry:
    """
    Model registry for versioning and managing trained models.
    Tracks model performance, metadata, and enables model promotion/rollback.
    """

    def __init__(self, registry_dir: str = "./model_registry"):
        self.registry_dir = Path(registry_dir)
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.registry_dir / "index.json"
        self._load_index()

    def _load_index(self):
        """Load registry index from disk"""
        if self.index_file.exists():
            with open(self.index_file, 'r') as f:
                self.index = json.load(f)
        else:
            self.index = {
                'models': {},
                'deployments': {}
            }

    def _save_index(self):
        """Save registry index to disk"""
        with open(self.index_file, 'w') as f:
            json.dump(self.index, f, indent=2, default=str)

    def register_model(
        self,
        model_id: str,
        symbol: str,
        timeframe: str,
        model_path: Path,
        metrics: Dict,
        metadata: Dict = None
    ) -> str:
        """
        Register a trained model in the registry.

        Args:
            model_id: Unique model identifier
            symbol: Trading symbol
            timeframe: Timeframe
            model_path: Path to model files
            metrics: Model performance metrics
            metadata: Additional metadata

        Returns:
            version: Assigned version string
        """
        key = f"{symbol}_{timeframe}"

        if key not in self.index['models']:
            self.index['models'][key] = []

        version = len(self.index['models'][key]) + 1
        version_str = f"v{version}"

        # Copy model to registry
        registry_model_path = self.registry_dir / key / version_str
        registry_model_path.mkdir(parents=True, exist_ok=True)

        if model_path.exists():
            for item in model_path.iterdir():
                if item.is_file():
                    shutil.copy2(item, registry_model_path / item.name)
                elif item.is_dir():
                    shutil.copytree(item, registry_model_path / item.name, dirs_exist_ok=True)

        # Register in index
        model_entry = {
            'model_id': model_id,
            'version': version_str,
            'symbol': symbol,
            'timeframe': timeframe,
            'path': str(registry_model_path),
            'metrics': metrics,
            'metadata': metadata or {},
            'registered_at': datetime.utcnow().isoformat(),
            'status': 'registered'
        }

        self.index['models'][key].append(model_entry)
        self._save_index()

        logger.info(f"Model registered: {key} {version_str} with OOS AUC: {metrics.get('avg_roc_auc', 'N/A')}")

        return version_str

    def get_model(
        self,
        symbol: str,
        timeframe: str,
        version: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Get model by symbol, timeframe, and optionally version.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            version: Model version (default: latest)

        Returns:
            Model entry dict or None
        """
        key = f"{symbol}_{timeframe}"

        if key not in self.index['models'] or not self.index['models'][key]:
            return None

        models = self.index['models'][key]

        if version:
            for model in models:
                if model['version'] == version:
                    return model
            return None
        else:
            # Return latest
            return models[-1]

    def list_models(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None
    ) -> List[Dict]:
        """
        List all registered models, optionally filtered.

        Args:
            symbol: Filter by symbol
            timeframe: Filter by timeframe

        Returns:
            List of model entries
        """
        all_models = []

        for key, models in self.index['models'].items():
            for model in models:
                if symbol and model['symbol'] != symbol:
                    continue
                if timeframe and model['timeframe'] != timeframe:
                    continue
                all_models.append(model)

        return sorted(all_models, key=lambda x: x['registered_at'], reverse=True)

    def deploy_model(
        self,
        symbol: str,
        timeframe: str,
        version: str,
        environment: str = 'production',
        risk_profile: Union[RiskProfile, str, None] = None,
        capital_usd: Optional[float] = None
    ) -> bool:
        """
        Deploy a model version to an environment.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            version: Model version to deploy
            environment: Target environment (production/staging)
            risk_profile: Risk profile to apply for this deployment
            capital_usd: Available capital in USD for this deployment

        Returns:
            True if successful
        """
        model = self.get_model(symbol, timeframe, version)

        if not model:
            logger.error(f"Model not found: {symbol}_{timeframe} {version}")
            return False

        key = f"{symbol}_{timeframe}"
        deployment_key = f"{key}_{environment}"

        def _resolve_risk(value: Union[RiskProfile, str, None]) -> Optional[RiskProfile]:
            if isinstance(value, RiskProfile):
                return value

            if isinstance(value, str):
                try:
                    return RiskProfile(value)
                except ValueError:
                    try:
                        return RiskProfile(value.lower())
                    except ValueError:
                        return None

            return None

        default_risk = _resolve_risk(getattr(settings, 'DEFAULT_RISK_PROFILE', RiskProfile.MEDIUM)) or RiskProfile.MEDIUM
        deployment_risk = _resolve_risk(risk_profile) or default_risk

        default_capital = getattr(settings, 'DEFAULT_CAPITAL_USD', 1000.0)

        try:
            default_capital_value = float(default_capital)
        except (TypeError, ValueError):
            logger.warning("Invalid DEFAULT_CAPITAL_USD configuration value %r, falling back to 1000.0", default_capital)
            default_capital_value = 1000.0

        if capital_usd is None:
            capital_value = default_capital_value
        else:
            try:
                capital_value = float(capital_usd)
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid capital_usd provided for deployment %s, falling back to default %.2f",
                    deployment_key,
                    default_capital_value,
                )
                capital_value = default_capital_value

        # Update deployment
        self.index['deployments'][deployment_key] = {
            'symbol': symbol,
            'timeframe': timeframe,
            'version': version,
            'model_id': model['model_id'],
            'environment': environment,
            'deployed_at': datetime.utcnow().isoformat(),
            'deployed_by': 'system',
            'risk_profile': deployment_risk.value,
            'capital_usd': capital_value
        }

        # Update model status
        for m in self.index['models'][key]:
            if m['version'] == version:
                m['status'] = 'deployed'
                break

        self._save_index()

        logger.info(f"Model deployed: {deployment_key} -> {version}")

        return True

    def get_deployed_model(
        self,
        symbol: str,
        timeframe: str,
        environment: str = 'production'
    ) -> Optional[Dict]:
        """
        Get currently deployed model for symbol/timeframe/environment.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            environment: Environment

        Returns:
            Deployed model entry or None
        """
        deployment_key = f"{symbol}_{timeframe}_{environment}"

        if deployment_key not in self.index['deployments']:
            return None

        deployment = self.index['deployments'][deployment_key]
        return self.get_model(symbol, timeframe, deployment['version'])

    def rollback_deployment(
        self,
        symbol: str,
        timeframe: str,
        environment: str = 'production'
    ) -> bool:
        """
        Rollback deployment to previous version.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            environment: Environment

        Returns:
            True if successful
        """
        key = f"{symbol}_{timeframe}"

        if key not in self.index['models'] or len(self.index['models'][key]) < 2:
            logger.error(f"Cannot rollback: insufficient versions for {key}")
            return False

        current_deployment = self.get_deployed_model(symbol, timeframe, environment)

        if not current_deployment:
            logger.error(f"No current deployment found for {key}")
            return False

        # Find previous version
        models = sorted(self.index['models'][key], key=lambda x: x['version'])
        current_idx = next(i for i, m in enumerate(models) if m['version'] == current_deployment['version'])

        if current_idx == 0:
            logger.error(f"Already at earliest version for {key}")
            return False

        previous_model = models[current_idx - 1]

        # Deploy previous version
        return self.deploy_model(symbol, timeframe, previous_model['version'], environment)

    def compare_models(
        self,
        symbol: str,
        timeframe: str,
        version1: str,
        version2: str
    ) -> Dict:
        """
        Compare metrics between two model versions.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            version1: First version
            version2: Second version

        Returns:
            Comparison dict
        """
        model1 = self.get_model(symbol, timeframe, version1)
        model2 = self.get_model(symbol, timeframe, version2)

        if not model1 or not model2:
            return {'error': 'One or both models not found'}

        comparison = {
            'version1': version1,
            'version2': version2,
            'metrics_comparison': {}
        }

        metrics1 = model1.get('metrics', {})
        metrics2 = model2.get('metrics', {})

        for metric in set(metrics1.keys()) | set(metrics2.keys()):
            val1 = metrics1.get(metric, 0)
            val2 = metrics2.get(metric, 0)
            diff = val2 - val1
            pct_change = (diff / val1 * 100) if val1 != 0 else 0

            comparison['metrics_comparison'][metric] = {
                'version1': val1,
                'version2': val2,
                'diff': diff,
                'pct_change': pct_change
            }

        return comparison

    def get_best_model(
        self,
        symbol: str,
        timeframe: str,
        metric: str = 'avg_roc_auc'
    ) -> Optional[Dict]:
        """
        Get best model by a specific metric.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            metric: Metric to optimize

        Returns:
            Best model entry or None
        """
        models = self.list_models(symbol, timeframe)

        if not models:
            return None

        best_model = max(
            models,
            key=lambda x: x.get('metrics', {}).get(metric, 0)
        )

        return best_model

    def archive_model(
        self,
        symbol: str,
        timeframe: str,
        version: str
    ) -> bool:
        """
        Archive a model version (mark as archived, don't delete).

        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            version: Version to archive

        Returns:
            True if successful
        """
        key = f"{symbol}_{timeframe}"

        if key not in self.index['models']:
            return False

        for model in self.index['models'][key]:
            if model['version'] == version:
                model['status'] = 'archived'
                model['archived_at'] = datetime.utcnow().isoformat()
                self._save_index()
                logger.info(f"Model archived: {key} {version}")
                return True

        return False
