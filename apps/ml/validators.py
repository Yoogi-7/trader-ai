from __future__ import annotations
import os, time, json
from typing import Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
import redis

from apps.api.config import settings
from apps.api.models import OHLCV, FundingRate, OrderBookSnapshot, Position, User

rds = redis.from_url(settings.REDIS_URL)

def get_kill_switch() -> bool:
    return rds.get("kill_switch:on") == "1"

def set_kill_switch(on: bool):
    rds.set("kill_switch:on", "1" if on else "0", ex=None)

def record_loss(result: float):
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
    # funding extremum
    fr = db.query(FundingRate).filter(FundingRate.symbol==symbol).order_by(FundingRate.ts.desc()).first()
    if fr and abs(fr.rate_bps) > int(os.getenv("MAX_FUNDING_ABS_BPS","30")):
        return False, "funding_extreme"

    # orderbook spread / depth
    ob = db.query(OrderBookSnapshot).filter(OrderBookSnapshot.symbol==symbol).order_by(OrderBookSnapshot.ts.desc()).first()
    if ob:
        min_spread_bps = float(os.getenv("MIN_SPREAD_BPS","2"))
        min_depth_usd = float(os.getenv("MIN_DEPTH_USD_1PCT","100000"))
        if ob.spread_bps > min_spread_bps:
            return False, "wide_spread"
        if ob.depth_usd_1pct < min_depth_usd:
            return False, "low_depth"
    else:
        # fallback: użyj wolumenu 1m
        rows = db.query(OHLCV).filter(OHLCV.symbol==symbol, OHLCV.tf=="1m").order_by(OHLCV.ts.desc()).limit(60).all()
        if len(rows) >= 10:
            avg_vol = sum(r.v or 0 for r in rows) / len(rows)
            if avg_vol * (rows[0].c or 0) < float(os.getenv("MIN_LIQ_USD","50000")):
                return False, "low_liquidity"

    return True, None

def correlation_cap(db: Session, user_capital: float) -> Tuple[bool, Optional[str]]:
    """
    Realny cap: suma ekspozycji USD na BTC+ETH nie może przekraczać CORR_CAP_BTC_ETH_PCT * capital.
    """
    cap = float(os.getenv("CORR_CAP_BTC_ETH_PCT","0.35"))
    limit = cap * user_capital
    rows = db.query(Position).filter(Position.status=="open").all()
    exp = 0.0
    for p in rows:
        if p.symbol in ("BTCUSDT","ETHUSDT"):
            exp += abs(p.exposure_usd)
    if exp > limit:
        return False, "corr_cap_btc_eth"
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
