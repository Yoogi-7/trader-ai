# apps/ml/backfill.py
# (fragment header bez zmian opisowych)
import logging
import os
import sys
import time
import math
from typing import List, Dict, Optional, Tuple

import pandas as pd
from sqlalchemy import select, desc
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from apps.api.db.session import SessionLocal
from apps.api.db import models
from apps.ml.ccxt_client import CcxtClient
from apps.ml.resample import resample_candles
from apps.common.event_bus import publish
from apps.ml.features import compute_and_store_features
from apps.ml.ta_utils import ema as ta_ema, atr as ta_atr, fibonacci_levels
from apps.api.services.signals_service import evaluate_signal
from apps.ml.jobs.train import run_training as training_task

logger = logging.getLogger(__name__)

SYMBOLS = [s.strip() for s in os.getenv("SYMBOLS", "BTC/USDT,ETH/USDT,BNB/USDT,ADA/USDT,SOL/USDT,XRP/USDT,DOGE/USDT,MATIC/USDT,ARB/USDT,OP/USDT").split(",")]
BASE_TF = "1m"
RESAMPLE_TFS = [tf.strip() for tf in os.getenv("RESAMPLE_TFS", "15m,1h,4h,1d").split(",") if tf.strip()]
CHUNK_MINUTES = int(os.getenv("CHUNK_MINUTES", "43200"))
RETRY_MAX = int(os.getenv("RETRY_MAX", "5"))
RETRY_BASE_SEC = float(os.getenv("RETRY_BASE_SEC", "1.0"))
PRINT_PROGRESS_EVERY = int(os.getenv("PRINT_PROGRESS_EVERY", "20000"))
MS_IN_MIN = 60_000

FEATURE_TFS = [tf.strip() for tf in os.getenv("AUTO_FEATURE_TFS", "15m,1h").split(",") if tf.strip()]
FEATURE_LOOKBACK_MIN = int(os.getenv("AUTO_FEATURE_LOOKBACK_MIN", "1440"))

SIGNAL_TF = os.getenv("AUTO_SIGNAL_TF", "15m")
SIGNAL_LOOKBACK_BARS = int(os.getenv("AUTO_SIGNAL_LOOKBACK_BARS", "240"))
SIGNAL_EMA_FAST = int(os.getenv("AUTO_SIGNAL_EMA_FAST", "21"))
SIGNAL_EMA_SLOW = int(os.getenv("AUTO_SIGNAL_EMA_SLOW", "55"))
SIGNAL_MIN_ATR = float(os.getenv("AUTO_SIGNAL_MIN_ATR", "0.0"))
SIGNAL_RISK_PROFILE = os.getenv("AUTO_SIGNAL_RISK", "MED")
SIGNAL_CAPITAL = float(os.getenv("AUTO_SIGNAL_CAPITAL", "1000"))
SIGNAL_MAX_ALLOCATION = float(os.getenv("AUTO_SIGNAL_MAX_PCT", "0.1"))
SIGNAL_FUNDING_RATE = float(os.getenv("AUTO_SIGNAL_FUNDING_RATE", "0.0"))
SIGNAL_COOLDOWN_MIN = int(os.getenv("AUTO_SIGNAL_COOLDOWN_MIN", "30"))
TRAIN_INTERVAL_MIN = int(os.getenv("AUTO_TRAIN_INTERVAL_MIN", "60"))
TRAIN_LOOKBACK_MIN = int(os.getenv("AUTO_TRAIN_LOOKBACK_MIN", "10080"))
TRAIN_SYMBOL = os.getenv("AUTO_TRAIN_SYMBOL", SYMBOLS[0] if SYMBOLS else "BTC/USDT")
TRAIN_TF = os.getenv("AUTO_TRAIN_TF", SIGNAL_TF)
TRAIN_CAPITAL = float(os.getenv("AUTO_TRAIN_CAPITAL", "1000"))
TRAIN_RISK = os.getenv("AUTO_TRAIN_RISK", "MED")
TRAIN_FOLDS = int(os.getenv("AUTO_TRAIN_FOLDS", "5"))


def _recent_start_ts(minutes: int) -> int:
    return now_ms() - minutes * MS_IN_MIN


def _compute_recent_features(symbol: str) -> None:
    if not FEATURE_TFS:
        return
    start_ts = _recent_start_ts(FEATURE_LOOKBACK_MIN)
    for tf in FEATURE_TFS:
        try:
            rows = compute_and_store_features(symbol, tf, start_ts, None)
            logger.debug("features computed symbol=%s tf=%s rows=%s", symbol, tf, rows)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("feature computation failed for %s %s: %s", symbol, tf, exc)


def _load_recent_bars(db: Session, symbol: str, tf: str, limit: int) -> pd.DataFrame:
    rows = (
        db.execute(
            select(models.OHLCV)
            .where(models.OHLCV.symbol == symbol, models.OHLCV.tf == tf)
            .order_by(desc(models.OHLCV.ts))
            .limit(limit)
        )
        .scalars()
        .all()
    )
    if not rows:
        return pd.DataFrame()
    data = {
        "ts": [r.ts for r in reversed(rows)],
        "open": [r.o for r in reversed(rows)],
        "high": [r.h for r in reversed(rows)],
        "low": [r.l for r in reversed(rows)],
        "close": [r.c for r in reversed(rows)],
        "volume": [r.v for r in reversed(rows)],
    }
    return pd.DataFrame(data)


def _recent_signal_allowed(db: Session, symbol: str, ts: int) -> bool:
    last = (
        db.execute(
            select(models.Signal)
            .where(models.Signal.symbol == symbol)
            .order_by(models.Signal.ts.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    if last is None:
        return True
    if ts <= last.ts:
        return False
    return (ts - last.ts) >= SIGNAL_COOLDOWN_MIN * MS_IN_MIN


def _generate_signal(db: Session, symbol: str) -> None:
    df = _load_recent_bars(db, symbol, SIGNAL_TF, SIGNAL_LOOKBACK_BARS)
    if df.empty or len(df) < max(SIGNAL_EMA_FAST, SIGNAL_EMA_SLOW) + 2:
        return

    ta_df = df[["open", "high", "low", "close", "volume"]].copy()
    ta_ema(ta_df, SIGNAL_EMA_FAST, out="ema_fast")
    ta_ema(ta_df, SIGNAL_EMA_SLOW, out="ema_slow")
    ta_atr(ta_df, 14, out="atr")
    fibonacci_levels(ta_df, lookback=min(len(ta_df), 120))

    ema_fast = ta_df["ema_fast"]
    ema_slow = ta_df["ema_slow"]
    if ema_fast.isna().any() or ema_slow.isna().any():
        ema_fast = ema_fast.bfill().ffill()
        ema_slow = ema_slow.bfill().ffill()

    if len(ema_fast) < 2 or len(ema_slow) < 2:
        return

    cross_up = ema_fast.iloc[-1] > ema_slow.iloc[-1] and ema_fast.iloc[-2] <= ema_slow.iloc[-2]
    cross_down = ema_fast.iloc[-1] < ema_slow.iloc[-1] and ema_fast.iloc[-2] >= ema_slow.iloc[-2]

    direction: Optional[str] = None
    if cross_up:
        direction = "LONG"
    elif cross_down:
        direction = "SHORT"
    else:
        return

    atr_raw = ta_df["atr"].iloc[-1]
    if pd.isna(atr_raw):
        logger.debug("skip signal symbol=%s reason=atr_nan", symbol)
        return
    atr_val = float(atr_raw)
    if atr_val <= SIGNAL_MIN_ATR:
        logger.debug("skip signal symbol=%s reason=atr_too_low", symbol)
        return

    ts = int(df["ts"].iloc[-1])
    if not _recent_signal_allowed(db, symbol, ts):
        return

    if db.execute(
        select(models.Signal).where(models.Signal.symbol == symbol, models.Signal.ts == ts)
    ).scalars().first():
        return

    fibo_cols = {
        k: float(v)
        for k, v in ta_df.iloc[-1].items()
        if isinstance(k, str) and k.startswith("fibo_") and pd.notna(v)
    }
    fibo_payload = fibo_cols or None

    sig, reason = evaluate_signal(
        db=db,
        symbol=symbol,
        tf_base=SIGNAL_TF,
        ts=ts,
        direction=direction,
        close=float(df["close"].iloc[-1]),
        atr=atr_val,
        fibo=fibo_payload,
        risk_profile=SIGNAL_RISK_PROFILE,
        capital=SIGNAL_CAPITAL,
        funding_rate_hourly=SIGNAL_FUNDING_RATE,
        max_allocation_pct=SIGNAL_MAX_ALLOCATION,
    )
    if sig is None:
        logger.debug("signal rejected symbol=%s reason=%s", symbol, reason)
        return

    potential_accuracy = getattr(sig, "potential_accuracy", None)
    acc_score = getattr(sig, "potential_accuracy_score", None)
    if acc_score is None and isinstance(potential_accuracy, dict):
        acc_score = potential_accuracy.get("score")

    publish(
        "signal_published",
        {
            "id": sig.id,
            "symbol": sig.symbol,
            "tf": sig.tf_base,
            "dir": sig.dir,
            "entry": sig.entry,
            "sl": sig.sl,
            "tp": sig.tp,
            "confidence": sig.confidence,
            "confidence_rating": int(round(float(sig.confidence) * 100.0)) if sig.confidence is not None else None,
            "market_regime": getattr(sig, "market_regime", None),
            "sentiment_rating": getattr(sig, "sentiment_rating", None),
            "ai_summary": sig.ai_summary,
            "potential_accuracy": potential_accuracy,
        },
    )
    logger.info(
        "auto signal created symbol=%s dir=%s entry=%.4f conf=%.2f rating=%s regime=%s acc=%s",
        sig.symbol,
        sig.dir,
        sig.entry,
        sig.confidence or 0.0,
        getattr(sig, "confidence_rating", None) or int(round((sig.confidence or 0.0) * 100)),
        getattr(sig, "market_regime", None),
        acc_score,
    )


LAST_TRAINING_RUN = 0.0

def now_ms() -> int:
    return int(time.time() * 1000)

def upsert_ohlcv(db: Session, symbol: str, tf: str, rows: List[Dict]) -> int:
    if not rows:
        return 0
    values = [{"symbol": symbol, "tf": tf, "ts": r["ts"], "o": r["o"], "h": r["h"], "l": r["l"], "c": r["c"], "v": r["v"], "source_hash": None} for r in rows]
    stmt = pg_insert(models.OHLCV.__table__).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["symbol", "tf", "ts"],
        set_={
            "o": stmt.excluded.o,
            "h": stmt.excluded.h,
            "l": stmt.excluded.l,
            "c": stmt.excluded.c,
            "v": stmt.excluded.v,
            "source_hash": stmt.excluded.source_hash,
        },
    )
    db.execute(stmt)
    return len(values)

def update_progress(db: Session, symbol: str, tf: str, **fields) -> models.BackfillProgress:
    bp = db.execute(select(models.BackfillProgress).where(models.BackfillProgress.symbol == symbol, models.BackfillProgress.tf == tf)).scalar_one_or_none()
    if not bp:
        bp = models.BackfillProgress(symbol=symbol, tf=tf, last_ts_completed=None, chunk_start_ts=None, chunk_end_ts=None, retry_count=0, status="idle", updated_at=now_ms())
        db.add(bp)
        db.commit()
        db.refresh(bp)
    for k, v in fields.items():
        setattr(bp, k, v)
    bp.updated_at = now_ms()
    db.commit()
    db.refresh(bp)
    # publish progress event
    try:
        publish("backfill_progress", {
            "symbol": bp.symbol, "tf": bp.tf, "status": bp.status,
            "last_ts_completed": bp.last_ts_completed, "updated_at": bp.updated_at
        })
    except Exception:
        pass
    return bp

def _fetch_chunk_1m(client: CcxtClient, symbol: str, start_ms: int, end_ms: int) -> List[Dict]:
    raw = client.fetch_ohlcv(symbol, timeframe="1m", since_ms=start_ms, until_ms=end_ms)
    return [{"ts": r[0], "o": float(r[1]), "h": float(r[2]), "l": float(r[3]), "c": float(r[4]), "v": float(r[5])} for r in raw]

def _iter_chunks(start_ms: int, end_ms: int, chunk_minutes: int):
    chunk_ms = chunk_minutes * MS_IN_MIN
    cur = start_ms
    while cur < end_ms:
        nxt = min(cur + chunk_ms, end_ms)
        yield (cur, nxt)
        cur = nxt

def _detect_gap(expected_start: int, fetched_rows: List[Dict]) -> Optional[Tuple[int, int]]:
    if not fetched_rows:
        return (expected_start, expected_start + MS_IN_MIN)
    ts_sorted = [r["ts"] for r in fetched_rows]
    prev = ts_sorted[0]
    for t in ts_sorted[1:]:
        if t - prev > MS_IN_MIN:
            return (prev + MS_IN_MIN, t - MS_IN_MIN)
        prev = t
    return None

def backfill_symbol(db: Session, client: CcxtClient, symbol: str, tf: str, from_ts: Optional[int], to_ts: Optional[int]) -> None:
    start_ms = from_ts if from_ts else (now_ms() - 4 * 365 * 24 * 60 * MS_IN_MIN)
    end_ms = to_ts if to_ts else now_ms()

    bp = db.execute(select(models.BackfillProgress).where(models.BackfillProgress.symbol == symbol, models.BackfillProgress.tf == tf)).scalar_one_or_none()
    if bp and bp.last_ts_completed:
        start_ms = max(start_ms, bp.last_ts_completed + MS_IN_MIN)

    update_progress(db, symbol, tf, chunk_start_ts=start_ms, chunk_end_ts=end_ms, status="running")
    # event: start
    publish("backfill_started", {"symbol": symbol, "tf": tf, "start_ts": start_ms, "end_ts": end_ms})

    total_written = 0
    fetched_total = 0

    for a, b in _iter_chunks(start_ms, end_ms, CHUNK_MINUTES):
        attempt = 0
        while True:
            try:
                rows = _fetch_chunk_1m(client, symbol, a, b)
                fetched_total += len(rows)

                gap = _detect_gap(a, rows)
                if gap:
                    last_cont_ts = rows[0]["ts"] if rows else a - MS_IN_MIN
                    prev_ts = last_cont_ts
                    for r in rows[1:]:
                        if r["ts"] - prev_ts > MS_IN_MIN:
                            break
                        prev_ts = r["ts"]
                    last_cont_ts = prev_ts
                    cont_rows = [r for r in rows if r["ts"] <= last_cont_ts]
                    if cont_rows:
                        upsert_ohlcv(db, symbol, BASE_TF, cont_rows)
                        total_written += len(cont_rows)
                        update_progress(db, symbol, tf, last_ts_completed=last_cont_ts, status="running")
                    publish("backfill_gap", {"symbol": symbol, "tf": tf, "gap_from": gap[0], "gap_to": gap[1]})
                    time.sleep(0.2)
                else:
                    if rows:
                        upsert_ohlcv(db, symbol, BASE_TF, rows)
                        total_written += len(rows)
                        update_progress(db, symbol, tf, last_ts_completed=rows[-1]["ts"], status="running")
                break
            except Exception as e:
                if attempt >= RETRY_MAX:
                    update_progress(db, symbol, tf, status="error", retry_count=(bp.retry_count + 1 if bp else 1))
                    publish("backfill_error", {"symbol": symbol, "tf": tf, "error": str(e)})
                    return
                sleep_s = RETRY_BASE_SEC * (2 ** attempt)
                time.sleep(sleep_s)
                attempt += 1

        if total_written and total_written % PRINT_PROGRESS_EVERY == 0:
            publish("backfill_progress", {"symbol": symbol, "tf": tf, "written": total_written, "fetched": fetched_total})

    checkpoint = db.execute(select(models.BackfillProgress).where(models.BackfillProgress.symbol == symbol, models.BackfillProgress.tf == tf)).scalar_one()
    last_ts = checkpoint.last_ts_completed if checkpoint else None
    if last_ts:
        q = select(models.OHLCV).where(
            models.OHLCV.symbol == symbol,
            models.OHLCV.tf == BASE_TF,
            models.OHLCV.ts >= start_ms,
            models.OHLCV.ts <= last_ts,
        ).order_by(models.OHLCV.ts.asc())
        rows_db = db.execute(q).scalars().all()
        rows_1m = [{"ts": r.ts, "o": r.o, "h": r.h, "l": r.l, "c": r.c, "v": r.v} for r in rows_db]

        for tf_target in RESAMPLE_TFS:
            agg = resample_candles(rows_1m, tf_target)
            if agg:
                upsert_ohlcv(db, symbol, tf_target, agg)
                publish("backfill_resampled", {"symbol": symbol, "tf_target": tf_target, "rows": len(agg)})

    update_progress(db, symbol, tf, status="done")
    publish("backfill_finished", {"symbol": symbol, "tf": tf, "written": total_written, "fetched": fetched_total})


def _maybe_run_training() -> None:
    global LAST_TRAINING_RUN
    if TRAIN_INTERVAL_MIN <= 0:
        return
    interval_sec = TRAIN_INTERVAL_MIN * 60
    now = time.time()
    if now - LAST_TRAINING_RUN < interval_sec:
        return
    params = {
        "symbol": TRAIN_SYMBOL,
        "tf": TRAIN_TF,
        "start_ts": _recent_start_ts(max(1, TRAIN_LOOKBACK_MIN)),
        "end_ts": now_ms(),
        "capital": TRAIN_CAPITAL,
        "risk": TRAIN_RISK,
        "n_folds": max(1, TRAIN_FOLDS),
    }
    try:
        result = training_task.apply(kwargs={"params": params})
        logger.info("auto training triggered symbol=%s tf=%s folds=%s", params["symbol"], params["tf"], params["n_folds"])
        if getattr(result, "result", None) is not None:
            logger.debug("auto training result=%s", result.result)
    except Exception as exc:
        logger.warning("auto training failed: %s", exc)
    finally:
        LAST_TRAINING_RUN = now


def _parse_optional_int_env(name: str) -> Optional[int]:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    try:
        return int(value)
    except ValueError:
        logger.warning("Ignoring %s=%r (not an integer)", name, value)
    return None


def run_once(symbols: Optional[List[str]] = None, tf: str = BASE_TF, from_ts: Optional[int] = None, to_ts: Optional[int] = None) -> None:
    db = SessionLocal()
    client = CcxtClient()
    active_symbols = symbols or SYMBOLS
    try:
        for symbol in active_symbols:
            sym = symbol.strip()
            if not sym:
                continue
            try:
                logger.info("Backfill start symbol=%s tf=%s", sym, tf)
                backfill_symbol(db, client, sym, tf, from_ts, to_ts)
                logger.info("Backfill done symbol=%s", sym)
                _compute_recent_features(sym)
                try:
                    _generate_signal(db, sym)
                except Exception as exc:
                    logger.warning("signal generation failed for %s: %s", sym, exc)
            except Exception:
                logger.exception("Backfill failed for %s", sym)
        _maybe_run_training()
    finally:
        db.close()


def main() -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=os.getenv("BACKFILL_LOG_LEVEL", "INFO").upper())
    mode = os.getenv("BACKFILL_MODE", "once").strip().lower() or "once"
    sleep_seconds_raw = os.getenv("BACKFILL_SLEEP_SECONDS", "300")
    try:
        sleep_seconds = int(sleep_seconds_raw)
    except ValueError:
        logger.warning("Invalid BACKFILL_SLEEP_SECONDS=%r, defaulting to 300", sleep_seconds_raw)
        sleep_seconds = 300
    from_ts = _parse_optional_int_env("BACKFILL_FROM_TS")
    to_ts = _parse_optional_int_env("BACKFILL_TO_TS")

    logger.info(
        "ml.backfill service starting (mode=%s, symbols=%s, tf=%s, from_ts=%s, to_ts=%s)",
        mode,
        SYMBOLS,
        BASE_TF,
        from_ts,
        to_ts,
    )

    while True:
        started = time.time()
        run_once(tf=BASE_TF, from_ts=from_ts, to_ts=to_ts)
        elapsed = time.time() - started
        logger.info("ml.backfill iteration finished in %.2fs", elapsed)
        if mode != "loop":
            break
        if sleep_seconds > 0:
            logger.info("Sleeping %ss before next iteration", sleep_seconds)
            time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()
