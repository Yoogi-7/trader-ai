# apps/api/crud.py
# PL: Proste operacje CRUD używane przez routery. EN: Simple CRUD helpers for routers.

from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc, case
from apps.api.db import models
import time
import uuid

# -------- Backfill --------

def backfill_start(db: Session, symbols: List[str], tf: str, from_ts: Optional[int], to_ts: Optional[int]) -> List[models.BackfillProgress]:
    now_ms = int(time.time() * 1000)
    items: List[models.BackfillProgress] = []
    for s in symbols:
        bp = db.execute(select(models.BackfillProgress).where(models.BackfillProgress.symbol == s, models.BackfillProgress.tf == tf)).scalar_one_or_none()
        if bp is None:
            bp = models.BackfillProgress(
                symbol=s,
                tf=tf,
                last_ts_completed=from_ts,
                chunk_start_ts=from_ts,
                chunk_end_ts=to_ts,
                retry_count=0,
                status="running",
                updated_at=now_ms,
            )
            db.add(bp)
        else:
            bp.chunk_start_ts = from_ts
            bp.chunk_end_ts = to_ts
            bp.status = "running"
            bp.updated_at = now_ms
        items.append(bp)
    db.commit()
    for b in items:
        db.refresh(b)
    return items

def backfill_list(db: Session, limit: int, offset: int) -> Tuple[int, List[models.BackfillProgress]]:
    total = db.execute(select(func.count(models.BackfillProgress.id))).scalar_one()
    rows = db.execute(
        select(models.BackfillProgress).order_by(desc(models.BackfillProgress.updated_at)).limit(limit).offset(offset)
    ).scalars().all()
    return total, rows

# -------- Train --------

def train_run_create(db: Session, params: Dict[str, Any]) -> int:
    now_ms = int(time.time() * 1000)
    tr = models.TrainingRun(started_at=now_ms, status="running", params_json=params)
    db.add(tr)
    db.commit()
    db.refresh(tr)
    return tr.id

def train_list(db: Session, limit: int, offset: int) -> Tuple[int, List[models.TrainingRun]]:
    total = db.execute(select(func.count(models.TrainingRun.id))).scalar_one()
    rows = db.execute(
        select(models.TrainingRun).order_by(desc(models.TrainingRun.started_at)).limit(limit).offset(offset)
    ).scalars().all()
    return total, rows

# -------- Backtest --------

def backtest_run_create(db: Session, params: Dict[str, Any]) -> int:
    now_ms = int(time.time() * 1000)
    bt = models.Backtest(started_at=now_ms, summary_json=None, params_json=params)
    db.add(bt)
    db.commit()
    db.refresh(bt)
    return bt.id

def backtest_list(db: Session, limit: int, offset: int) -> Tuple[int, List[models.Backtest]]:
    total = db.execute(select(func.count(models.Backtest.id))).scalar_one()
    rows = db.execute(
        select(models.Backtest).order_by(desc(models.Backtest.started_at)).limit(limit).offset(offset)
    ).scalars().all()
    return total, rows

# -------- Signals --------

def signal_create(db: Session, payload: Dict[str, Any]) -> models.Signal:
    # Wymaganie: filtrowanie < 2% net zostanie domknięte w P5 (tu przyjmujemy, że payload już przeszedł filtr).
    sid = payload.get("id") or str(uuid.uuid4())
    s = models.Signal(
        id=sid,
        symbol=payload["symbol"],
        tf_base=payload["tf_base"],
        ts=payload["ts"],
        dir=payload["dir"],
        entry=float(payload["entry"]),
        tp=payload.get("tp"),
        sl=float(payload["sl"]),
        lev=float(payload["lev"]),
        risk=payload.get("risk", "LOW"),
        margin_mode=payload.get("margin_mode", "ISOLATED"),
        expected_net_pct=float(payload["expected_net_pct"]),
        confidence=payload.get("confidence"),
        model_ver=payload.get("model_ver"),
        reason_discard=payload.get("reason_discard"),
        status="published" if payload.get("reason_discard") is None else "cancelled",
        ai_summary=payload.get("ai_summary"),
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s

def signals_list(db: Session, symbol: Optional[str], status: Optional[str], limit: int, offset: int) -> Tuple[int, List[models.Signal]]:
    stmt = select(models.Signal)
    if symbol:
        stmt = stmt.where(models.Signal.symbol == symbol)
    if status:
        stmt = stmt.where(models.Signal.status == status)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(stmt.order_by(desc(models.Signal.ts)).limit(limit).offset(offset)).scalars().all()
    return total, rows


def leaderboard_overall(db: Session, cutoff_ts_ms: int) -> Dict[str, Any]:
    stmt = (
        select(
            func.coalesce(func.count(models.PnL.id), 0).label("total"),
            func.coalesce(
                func.sum(
                    case((models.PnL.realized > 0.0, 1), else_=0)
                ),
                0,
            ).label("wins"),
        )
        .select_from(models.PnL)
        .join(models.Signal, models.PnL.signal_id == models.Signal.id)
        .where(models.Signal.ts >= cutoff_ts_ms)
    )
    result = db.execute(stmt).mappings().first()
    total = int(result["total"]) if result and result["total"] is not None else 0
    wins = int(result["wins"]) if result and result["wins"] is not None else 0
    win_rate = float(wins / total) if total > 0 else 0.0
    return {"win_rate": win_rate, "wins": wins, "total": total}


def leaderboard_users(db: Session, limit: int = 10) -> List[Dict[str, Any]]:
    users = (
        db.execute(select(models.User).order_by(models.User.capital.desc(), models.User.id).limit(limit))
        .scalars()
        .all()
    )
    leaderboard = []
    for idx, user in enumerate(users, start=1):
        leaderboard.append(
            {
                "rank": idx,
                "user_id": user.id,
                "email": user.email,
                "capital": float(user.capital),
                "risk_profile": user.risk_profile,
            }
        )
    return leaderboard

# -------- Users / Settings --------

def user_upsert_settings(db: Session, user_id: int, risk_profile: str, capital: float, prefs: Dict[str, Any]) -> bool:
    user = db.get(models.User, user_id)
    if user is None:
        raise ValueError('user not found')
    user_update_settings(db, user, risk_profile, capital, prefs)
    return True

def user_set_capital(db: Session, user_id: int, capital: float) -> bool:
    u = db.get(models.User, user_id)
    if u is None:
        u = models.User(id=user_id, capital=capital)
        db.add(u)
    else:
        u.capital = capital
    db.commit()
    return True

# -------- Users / Auth --------

def user_get_by_email(db: Session, email: str) -> Optional[models.User]:
    return db.execute(select(models.User).where(models.User.email == email.lower())).scalars().first()

def user_list(db: Session) -> List[models.User]:
    return db.execute(select(models.User).order_by(models.User.id)).scalars().all()

def user_create(db: Session, email: str, password_hash: str, role: str = 'USER', risk_profile: str = 'LOW', capital: float = 100.0, prefs: Dict[str, Any] | None = None) -> models.User:
    now_ms = int(time.time() * 1000)
    user = models.User(
        email=email.lower(),
        password_hash=password_hash,
        role=role,
        risk_profile=risk_profile,
        capital=capital,
        prefs=prefs,
        created_at=now_ms,
        updated_at=now_ms,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def user_update(db: Session, user: models.User, **fields) -> models.User:
    user = db.merge(user)
    for key, value in fields.items():
        if value is None:
            continue
        setattr(user, key, value)
    user.updated_at = int(time.time() * 1000)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def user_update_settings(db: Session, user: models.User, risk_profile: str, capital: float, prefs: Dict[str, Any]) -> models.User:
    user = db.merge(user)
    user.risk_profile = risk_profile
    user.capital = capital
    user.prefs = prefs
    user.updated_at = int(time.time() * 1000)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
