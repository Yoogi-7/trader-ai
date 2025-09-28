# apps/api/crud.py
# PL: Proste operacje CRUD używane przez routery. EN: Simple CRUD helpers for routers.

from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc, case
from apps.api.db import models
import time
import uuid


def _to_epoch_ms(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if hasattr(value, "timestamp"):
        return int(value.timestamp() * 1000)
    return None


def _max_drawdown(equity_curve: List[float]) -> float:
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    for value in equity_curve:
        if value > peak:
            peak = value
        drawdown = peak - value
        if drawdown > max_dd:
            max_dd = drawdown
    return float(max_dd)

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


# -------- Trading Journal --------

def trading_journal_summary(db: Session) -> Dict[str, Any]:
    rows = (
        db.execute(
            select(models.PnL, models.Signal)
            .join(models.Signal, models.PnL.signal_id == models.Signal.id)
            .order_by(models.Signal.ts.asc())
        )
        .all()
    )

    equity_curve = []
    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    total = 0
    wins = 0
    sum_pnl = 0.0
    best_trade = None
    worst_trade = None
    regime_stats: Dict[str, Dict[str, float]] = {}
    sentiments = []

    for pnl_row, sig in rows:
        realized = float(pnl_row.realized or 0.0)
        total += 1
        sum_pnl += realized
        if realized > 0:
            wins += 1

        if best_trade is None or realized > best_trade["pnl"]:
            best_trade = {
                "symbol": sig.symbol,
                "ts": sig.ts,
                "pnl": realized,
                "direction": sig.dir,
            }
        if worst_trade is None or realized < worst_trade["pnl"]:
            worst_trade = {
                "symbol": sig.symbol,
                "ts": sig.ts,
                "pnl": realized,
                "direction": sig.dir,
            }

        cum += realized
        peak = max(peak, cum)
        max_dd = max(max_dd, peak - cum)
        equity_curve.append({"ts": sig.ts, "equity": cum})

        regime = getattr(sig, "market_regime", None) or "unknown"
        stat = regime_stats.setdefault(regime, {"trades": 0.0, "wins": 0.0, "pnl": 0.0})
        stat["trades"] += 1
        stat["pnl"] += realized
        if realized > 0:
            stat["wins"] += 1

        sentiment_rating = getattr(sig, "sentiment_rating", None)
        if isinstance(sentiment_rating, (int, float)):
            sentiments.append(float(sentiment_rating))

    win_rate = (wins / total) if total > 0 else 0.0
    avg_pnl = (sum_pnl / total) if total > 0 else 0.0

    regime_breakdown = []
    for regime, stat in regime_stats.items():
        trades = int(stat["trades"])
        regime_breakdown.append(
            {
                "regime": regime,
                "trades": trades,
                "win_rate": (stat["wins"] / trades) if trades > 0 else 0.0,
                "pnl": stat["pnl"],
            }
        )
    regime_breakdown.sort(key=lambda x: x["pnl"], reverse=True)

    losses = [
        (pnl_row, sig)
        for pnl_row, sig in rows
        if (pnl_row.realized or 0.0) < 0
    ]
    losses.sort(key=lambda item: item[0].realized or 0.0)
    recent_mistakes = [
        {
            "symbol": sig.symbol,
            "ts": sig.ts,
            "pnl": float(pnl_row.realized or 0.0),
            "direction": sig.dir,
            "market_regime": getattr(sig, "market_regime", None),
            "sentiment_rating": getattr(sig, "sentiment_rating", None),
            "ai_summary": sig.ai_summary,
        }
        for pnl_row, sig in losses[:3]
    ]

    sentiment_summary = {
        "avg_rating": (sum(sentiments) / len(sentiments)) if sentiments else None,
        "positive_share": (
            sum(1 for s in sentiments if s >= 60) / len(sentiments)
            if sentiments else None
        ),
        "negative_share": (
            sum(1 for s in sentiments if s <= 40) / len(sentiments)
            if sentiments else None
        ),
    }

    return {
        "equity_curve": equity_curve,
        "metrics": {
            "total_trades": total,
            "win_rate": win_rate,
            "avg_pnl": avg_pnl,
            "max_drawdown": max_dd,
            "best_trade": best_trade,
            "worst_trade": worst_trade,
            "cumulative_pnl": sum_pnl,
        },
        "recent_mistakes": recent_mistakes,
        "regime_breakdown": regime_breakdown,
        "sentiment_summary": sentiment_summary,
    }

# -------- Risk Dashboard --------

def risk_metrics_backtest_latest(db: Session) -> Dict[str, Any]:
    row = (
        db.execute(
            select(models.Backtest)
            .where(models.Backtest.summary_json != None)  # noqa: E711
            .order_by(desc(models.Backtest.finished_at), desc(models.Backtest.started_at))
            .limit(1)
        )
        .scalars()
        .first()
    )

    base = {
        "source": "backtest",
        "max_drawdown": None,
        "max_drawdown_pct": None,
        "avg_profit_per_trade": None,
        "win_rate": None,
        "trades": 0,
        "pnl_total": None,
        "capital": None,
        "last_updated_ms": None,
    }

    if row is None or not row.summary_json:
        return base

    summary = row.summary_json or {}
    metrics = summary.get("metrics") if isinstance(summary, dict) else None
    if metrics is None:
        metrics = summary if isinstance(summary, dict) else {}

    params = summary.get("params") if isinstance(summary, dict) else {}
    if not isinstance(params, dict):
        params = {}

    capital = params.get("capital")
    if capital is None and isinstance(row.params_json, dict):
        capital = row.params_json.get("capital")

    trades = metrics.get("trades") or metrics.get("trade_count") or metrics.get("n_trades") or 0
    try:
        trades_int = int(trades)
    except Exception:
        trades_int = 0

    pnl_total_raw = metrics.get("pnl_total")
    pnl_total = float(pnl_total_raw) if pnl_total_raw is not None else None
    avg_profit = float(pnl_total / trades_int) if pnl_total is not None and trades_int > 0 else None

    max_dd = metrics.get("max_dd")
    if max_dd is None:
        equity_curve = summary.get("equity_curve") or metrics.get("equity_curve")
        if isinstance(equity_curve, list):
            numeric_curve = [float(v) for v in equity_curve if isinstance(v, (int, float))]
            if numeric_curve:
                max_dd = _max_drawdown(numeric_curve)
    max_dd_val = float(max_dd) if max_dd is not None else None

    max_dd_pct = metrics.get("max_dd_pct")
    if max_dd_pct is None and max_dd_val is not None and capital:
        try:
            capital_val = float(capital)
        except Exception:
            capital_val = None
        else:
            if capital_val > 0:
                max_dd_pct = max_dd_val / capital_val
    max_dd_pct_val = float(max_dd_pct) if max_dd_pct is not None else None

    win_rate = metrics.get("win_rate")
    if win_rate is None:
        win_rate = metrics.get("hit_rate_tp1")
    win_rate_val = float(win_rate) if win_rate is not None else None

    capital_val = None
    if capital is not None:
        try:
            capital_val = float(capital)
        except Exception:
            capital_val = None

    base.update(
        {
            "max_drawdown": max_dd_val,
            "max_drawdown_pct": max_dd_pct_val,
            "avg_profit_per_trade": avg_profit,
            "win_rate": win_rate_val,
            "trades": trades_int,
            "pnl_total": pnl_total,
            "capital": capital_val,
            "last_updated_ms": _to_epoch_ms(row.finished_at) or _to_epoch_ms(row.started_at),
        }
    )
    return base


def risk_metrics_live(db: Session) -> Dict[str, Any]:
    rows = (
        db.execute(
            select(models.Signal.ts, models.PnL.realized)
            .join(models.PnL, models.PnL.signal_id == models.Signal.id)
            .where(models.PnL.realized != None)  # noqa: E711
            .order_by(models.Signal.ts.asc())
        )
        .all()
    )

    base = {
        "source": "live",
        "max_drawdown": None,
        "max_drawdown_pct": None,
        "avg_profit_per_trade": None,
        "win_rate": None,
        "trades": 0,
        "pnl_total": None,
        "capital": None,
        "last_updated_ms": None,
    }

    if not rows:
        return base

    profits = [float(r.realized) for r in rows if r.realized is not None]
    if not profits:
        return base

    trades = len(profits)
    pnl_total = sum(profits)
    avg_profit = pnl_total / trades if trades > 0 else None
    wins = sum(1 for p in profits if p > 0)
    win_rate = wins / trades if trades > 0 else None

    equity = []
    running = 0.0
    for p in profits:
        running += p
        equity.append(running)
    equity_curve = [0.0] + equity
    max_dd = _max_drawdown(equity_curve)
    peak = max(equity_curve) if equity_curve else 0.0
    max_dd_pct = (max_dd / peak) if peak > 0 else None

    base.update(
        {
            "max_drawdown": float(max_dd),
            "max_drawdown_pct": float(max_dd_pct) if max_dd_pct is not None else None,
            "avg_profit_per_trade": float(avg_profit) if avg_profit is not None else None,
            "win_rate": float(win_rate) if win_rate is not None else None,
            "trades": trades,
            "pnl_total": float(pnl_total),
            "last_updated_ms": _to_epoch_ms(rows[-1].ts),
        }
    )
    return base

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
