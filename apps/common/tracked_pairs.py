from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from apps.api.db.models import SystemConfig, TimeFrame, TrackedPair

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrackedPairConfig:
    symbol: str
    timeframe: TimeFrame


DEFAULT_TRACKED_PAIRS: List[TrackedPairConfig] = [
    TrackedPairConfig("BTC/USDT", TimeFrame.M15),
    TrackedPairConfig("ETH/USDT", TimeFrame.M15),
    TrackedPairConfig("BNB/USDT", TimeFrame.M15),
    TrackedPairConfig("XRP/USDT", TimeFrame.M15),
    TrackedPairConfig("ADA/USDT", TimeFrame.M15),
    TrackedPairConfig("SOL/USDT", TimeFrame.M15),
    TrackedPairConfig("DOGE/USDT", TimeFrame.M15),
    TrackedPairConfig("POL/USDT", TimeFrame.M15),
    TrackedPairConfig("DOT/USDT", TimeFrame.M15),
    TrackedPairConfig("AVAX/USDT", TimeFrame.M15),
    TrackedPairConfig("LINK/USDT", TimeFrame.M15),
    TrackedPairConfig("UNI/USDT", TimeFrame.M15),
]

_CACHE_TTL_SECONDS = 300
_CACHE_STATE = {
    "pairs": None,
    "version": None,
    "expires_at": None,
}
_VERSION_KEY = "tracked_pairs_version"


def invalidate_tracked_pairs_cache() -> None:
    """Clear the in-process cache for tracked pairs."""

    _CACHE_STATE["pairs"] = None
    _CACHE_STATE["version"] = None
    _CACHE_STATE["expires_at"] = None


def _parse_version(value: Optional[object]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, dict):
        raw_value = value.get("version")
        if raw_value is None:
            return None
        return str(raw_value)
    return str(value)


def _load_version(db: Session) -> Optional[str]:
    entry = (
        db.query(SystemConfig)
        .filter(SystemConfig.key == _VERSION_KEY)
        .first()
    )
    if entry is None:
        return None
    return _parse_version(entry.value)


def bump_tracked_pairs_version(db: Session, *, commit: bool = False) -> str:
    """Increment the configuration version for tracked pairs.

    Returns the new version string.
    """

    version_value = datetime.utcnow().isoformat()
    payload = {"version": version_value}

    entry = (
        db.query(SystemConfig)
        .filter(SystemConfig.key == _VERSION_KEY)
        .first()
    )

    if entry is None:
        entry = SystemConfig(
            key=_VERSION_KEY,
            value=payload,
            description="Version marker for tracked pairs configuration",
        )
        db.add(entry)
    else:
        entry.value = payload

    if commit:
        db.commit()
    else:
        db.flush()

    return version_value


def get_tracked_pairs(db: Session, *, use_cache: bool = True) -> List[TrackedPairConfig]:
    """Return the list of active tracked pairs with optional caching."""

    now = datetime.utcnow()
    version = _load_version(db)

    if use_cache:
        cached_pairs = _CACHE_STATE.get("pairs")
        cached_version = _CACHE_STATE.get("version")
        expires_at = _CACHE_STATE.get("expires_at")

        if (
            cached_pairs is not None
            and cached_version == version
            and expires_at is not None
            and now < expires_at
        ):
            return cached_pairs

    try:
        rows: List[TrackedPair] = (
            db.query(TrackedPair)
            .filter(TrackedPair.is_active.is_(True))
            .order_by(TrackedPair.symbol.asc())
            .all()
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to load tracked pairs from database: %s", exc)
        rows = []

    if not rows:
        pairs = list(DEFAULT_TRACKED_PAIRS)
    else:
        pairs = [
            TrackedPairConfig(
                symbol=row.symbol,
                timeframe=row.timeframe
                if isinstance(row.timeframe, TimeFrame)
                else TimeFrame(row.timeframe),
            )
            for row in rows
        ]

    if use_cache:
        _CACHE_STATE["pairs"] = pairs
        _CACHE_STATE["version"] = version
        _CACHE_STATE["expires_at"] = now + timedelta(seconds=_CACHE_TTL_SECONDS)

    return pairs
