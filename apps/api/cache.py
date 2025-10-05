import json
import logging
from typing import Any, Optional

from redis import Redis

from apps.api.config import settings

logger = logging.getLogger(__name__)

_redis_client: Optional[Redis] = None


def get_redis_client() -> Optional[Redis]:
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    try:
        client = Redis.from_url(str(settings.REDIS_URL), decode_responses=True)
        # Validate connection eagerly to avoid using an unavailable backend
        client.ping()
        _redis_client = client
    except Exception as exc:  # pragma: no cover - connection failures are logged
        logger.warning("Redis cache unavailable: %s", exc)
        _redis_client = None

    return _redis_client


def get_cached_json(key: str) -> Optional[Any]:
    client = get_redis_client()
    if client is None:
        return None

    try:
        cached = client.get(key)
        if cached is None:
            return None
        return json.loads(cached)
    except Exception as exc:  # pragma: no cover - we fall back to live query
        logger.warning("Failed to read cache key %s: %s", key, exc)
        return None


def set_cached_json(key: str, value: Any, ttl_seconds: int) -> None:
    client = get_redis_client()
    if client is None:
        return

    try:
        payload = json.dumps(value)
        client.setex(key, ttl_seconds, payload)
    except Exception as exc:  # pragma: no cover - cache failures are non-fatal
        logger.warning("Failed to set cache key %s: %s", key, exc)
