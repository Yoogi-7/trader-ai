from __future__ import annotations
import os, time, json
from typing import Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
import redis

from apps.api.config import settings
from apps.api.models import OHLCV, FundingRate

rds = redis.from_url(settings.REDIS_URL)

def get_kill_switch() -> bool:
    return rds.get("kill_switch:on") == "1"

def set_kill_switch(on: bool):
    rds.set("kill_switch:on", "1" if on else "0", ex=None)

def record_loss(result: float):
    # result < 0 traktujemy jako strata (bardzo uproszczone)
    key = "loss_streak"
    if result < 0:
        val = int(rds.get(key) or 0) + 1
        rds.set(key, str(val), ex=24*3600)
    else:
        rds.set(key, "0", ex=24*3600)

def get_loss_streak() -> int:
    return int(rds.get("loss_streak") or 0)

def in_cooldown() -> bool:
    ts = rds.get("cooldown_until_ts")
    return ts is not None and int(ts) > int(time.time())

def set_cooldown(minutes: int):
    until = int(time.time()) + minutes*60
    rds.set("cooldown_until_ts", str(until), ex=minutes*60)

def basic_market_checks(db: Session, symbol: str) -> Tuple[bool, Optional[str]]:
    """
    Proste walidacje ex-ante: spread, płynność (na bazie świec), funding-extremum.
    Uwaga: spread_bps/liq wymagają realnych danych z order book — tutaj przybliżamy płynność wolumenem z 1m.
    """
    # 1) funding extremum (ostatnia wartość)
    fr = db.query(FundingRate).filter(FundingRate.symbol==symbol).order_by(FundingRate.ts.desc()).first()
    if fr and abs(fr.rate_bps) > int(os.getenv("MAX_FUNDING_ABS_BPS","30")):
        return False, "funding_extreme"

    # 2) płynność: średni wolumen z ostatnich 60 świec 1m
    rows = db.query(OHLCV).filter(OHLCV.symbol==symbol, OHLCV.tf=="1m").order_by(OHLCV.ts.desc()).limit(60).all()
    if len(rows) >= 10:
        avg_vol = sum(r.v or 0 for r in rows) / len(rows)
        if avg_vol * (rows[0].c or 0) < float(os.getenv("MIN_LIQ_USD","50000")):
            return False, "low_liquidity"

    # 3) spread — w tym szkielecie brak order book; pomijamy lub zakładamy > MIN_SPREAD_BPS jest OK
    # Można uzupełnić po dodaniu order book.

    return True, None

def correlation_cap(db: Session, user_capital: float) -> Tuple[bool, Optional[str]]:
    """
    Korelacyjny cap BTC/ETH — łączna ekspozycja nie przekracza CORR_CAP_BTC_ETH_PCT*capital.
    W tej wersji bazujemy na stubie ekspozycji (brak realnych pozycji) — zwracamy True.
    Docelowo należy agregować otwarte pozycje (qty*px) i porównać z limitem.
    """
    # Placeholder pass-through, logicę pozycji dodamy przy module egzekucyjnym.
    return True, None

def risk_profile_limits(profile: str, requested_lev: int, current_parallel: int) -> Tuple[bool, Optional[str]]:
    mp = {
        "LOW":  (int(os.getenv("MAX_LEV_LOW","5")),  int(os.getenv("MAX_PARALLEL_POS_LOW","2"))),
        "MED":  (int(os.getenv("MAX_LEV_MED","10")), int(os.getenv("MAX_PARALLEL_POS_MED","4"))),
        "HIGH": (int(os.getenv("MAX_LEV_HIGH","20")),int(os.getenv("MAX_PARALLEL_POS_HIGH","6"))),
    }
    max_lev, max_par = mp.get(profile.upper(), mp["LOW"])
    if requested_lev > max_lev:
        return False, "lev_exceeds_profile"
    if current_parallel >= max_par:
        return False, "parallel_cap_reached"
    return True, None
