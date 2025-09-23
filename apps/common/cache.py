# apps/common/cache.py
# PL: Minimalny wrapper na Redis (cache JSON).
# EN: Minimal Redis wrapper (JSON cache).

from __future__ import annotations
import os, json, time
from typing import Any, Optional

import redis  # type: ignore

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CACHE_TTL = int(os.getenv("CACHE_TTL", "60"))

_pool: Optional[redis.Redis] = None

def _client() -> redis.Redis:
    global _pool
    if _pool is None:
        _pool = redis.from_url(REDIS_URL, decode_responses=True)
    return _pool

def set_json(key: str, value: Any, ttl: Optional[int] = None) -> None:
    c = _client()
    c.set(key, json.dumps(value, separators=(",", ":")), ex=ttl or CACHE_TTL)

def get_json(key: str) -> Optional[Any]:
    c = _client()
    val = c.get(key)
    if val is None:
        return None
    try:
        return json.loads(val)
    except Exception:
        return None
