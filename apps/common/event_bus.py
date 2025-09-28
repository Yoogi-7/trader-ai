# apps/common/event_bus.py
# PL: Publikacja zdarzeń bezpośrednio do API (HTTP webhook).
# EN: Publish events straight to the API via HTTP webhook.

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict

import requests

_logger = logging.getLogger(__name__)

_API_BASE = os.getenv("EVENT_API_URL") or os.getenv("API_INTERNAL_URL", "http://api:8000")
_API_BASE = _API_BASE.rstrip("/")
_TIMEOUT = float(os.getenv("EVENT_API_TIMEOUT", "3"))
_INTERNAL_SECRET = os.getenv("INTERNAL_SECRET", "changeme")

_session = requests.Session()


def publish(event_type: str, payload: Dict[str, Any]) -> None:
    """Deliver event payload to the API webhook. Failures are logged and ignored."""

    msg = {
        "type": event_type,
        "ts": int(time.time() * 1000),
        "payload": payload,
    }

    try:
        _session.post(
            f"{_API_BASE}/api/internal/events",
            json={"type": msg["type"], "payload": msg["payload"]},
            headers={"x-internal-secret": _INTERNAL_SECRET},
            timeout=_TIMEOUT,
        )
    except Exception as exc:  # pragma: no cover - network errors
        _logger.debug("event publish failed: %s", exc)


def flush() -> None:
    # HTTP transport does not require flushing; keep the function for backwards compatibility.
    return None
