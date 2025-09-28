# -*- coding: utf-8 -*-
from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Optional, List

import pandas as pd
from sqlalchemy import text, select
from sqlalchemy.orm import Session
from celery import shared_task

from apps.api.db.session import SessionLocal
from apps.api.db.models import Feature, OHLCV
from apps.api.config import settings
from apps.ml.ta_utils import ema, rsi, macd, atr, bollinger, stoch, ichimoku

UTC = timezone.utc

TF_VIEW = {
    "1m": "ohlcv",
    "15m": "ohlcv_15m",
    "1h": "ohlcv_1h",
    "4h": "ohlcv_4h",
    "1d": "ohlcv_1d",
}

def _fetch_ohlcv_df(db: Session, symbol: str, tf: str, start_iso: Optional[str], end_iso: Optional[str]) -> pd.DataFrame:
    bind = db.get_bind()
    if bind and bind.dialect.name == "sqlite":
        stmt = (
            select(OHLCV.ts, OHLCV.o, OHLCV.h, OHLCV.l, OHLCV.c, OHLCV.v)
            .where(OHLCV.symbol == symbol, OHLCV.tf == tf)
            .order_by(OHLCV.ts.asc())
        )
        rows = db.execute(stmt).all()
        if not rows:
            return pd.DataFrame(columns=["o", "h", "l", "c", "v"], index=pd.Index([], name="ts_time"))
        df = pd.DataFrame(rows, columns=["ts", "o", "h", "l", "c", "v"])
        df["ts_time"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
        df.set_index("ts_time", inplace=True)
        return df[["o", "h", "l", "c", "v"]]

    view = TF_VIEW[tf]
    if tf == "1m":
        sql = f"""
        SELECT ts_time, o, h, l, c, v
        FROM {view}
        WHERE symbol = :symbol AND tf = '1m'
          AND (:start IS NULL OR ts_time >= :start::timestamptz)
          AND (:end   IS NULL OR ts_time <= :end::timestamptz)
        ORDER BY ts_time
        """
    else:
        sql = f"""
        SELECT ts_time, o, h, l, c, v
        FROM {view}
        WHERE symbol = :symbol
          AND (:start IS NULL OR ts_time >= :start::timestamptz)
          AND (:end   IS NULL OR ts_time <= :end::timestamptz)
        ORDER BY ts_time
        """
    rows = db.execute(text(sql), {"symbol": symbol, "start": start_iso, "end": end_iso}).mappings().all()
    if not rows:
        return pd.DataFrame(columns=["ts_time","o","h","l","c","v"])
    df = pd.DataFrame(rows)
    df["ts_time"] = pd.to_datetime(df["ts_time"], utc=True)
    df.set_index("ts_time", inplace=True)
    return df

def _compute_features(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(index=df.index)

    work = df.rename(
        columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}
    ).copy()

    ema(work, 20)
    ema(work, 50)
    rsi(work, 14)
    macd(work, 12, 26, 9)
    atr(work, 14)
    bollinger(work, 20, 2.0)
    stoch(work, 14, 3)
    ichimoku(work)

    out = work[[
        "ema_20", "ema_50", "rsi",
        "macd", "macd_signal", "macd_hist",
        "atr", "bb_mid", "bb_up", "bb_low",
        "stoch_k", "stoch_d",
        "ichi_conv", "ichi_base", "ichi_span_a", "ichi_span_b",
    ]].copy()

    out["ret_1"] = work["close"].pct_change().fillna(0.0)
    out["rv_10"] = (work["close"].pct_change().rolling(10).std() * (10 ** 0.5)).fillna(0.0)
    return out

def _upsert_features(db: Session, symbol: str, tf: str, version: str, fdf: pd.DataFrame, chunk: int = 1000) -> int:
    total = 0
    cols = list(fdf.columns)
    bind = db.get_bind()
    is_sqlite = bool(bind and bind.dialect.name == "sqlite")
    for start in range(0, len(fdf), chunk):
        part = fdf.iloc[start:start+chunk]
        payload = [
            {
                "symbol": symbol,
                "tf": tf,
                "ts": int(idx.timestamp() * 1000),
                "f_vector": {k: (None if pd.isna(v) else float(v)) for k, v in row.items()},
                "version": version,
            }
            for idx, row in part[cols].iterrows()
        ]
        if not payload:
            continue
        if is_sqlite:
            serialised = [
                {
                    **row,
                    "f_vector": json.dumps(row["f_vector"]),
                }
                for row in payload
            ]
            db.execute(
                text(
                    """
                    INSERT OR REPLACE INTO features (symbol, tf, ts, f_vector, version)
                    VALUES (:symbol, :tf, :ts, :f_vector, :version)
                    """
                ),
                serialised,
            )
        else:
            db.execute(text("""
                INSERT INTO features (symbol, tf, ts, f_vector, version)
                VALUES (:symbol, :tf, :ts, :f_vector::jsonb, :version)
                ON CONFLICT (symbol, tf, ts, version)
                DO UPDATE SET f_vector = EXCLUDED.f_vector
            """), payload)
        db.commit()
        total += len(payload)
    return total

@shared_task
def run_features(
    symbols: Optional[List[str]] = None,
    tf: str = "15m",
    start_iso: Optional[str] = None,
    end_iso: Optional[str] = None,
    version: Optional[str] = None,
):
    """
    Oblicza features dla wskazanych symboli i TF (domyślnie 15m) w zakresie czasu.
    Wyniki zapisuje do tabeli `features` z wersją (version).
    """
    if tf not in TF_VIEW:
        raise ValueError(f"Unsupported tf {tf}")
    version = version or datetime.now(tz=UTC).strftime("v%Y%m%d%H%M%S")

    db = SessionLocal()
    try:
        syms = symbols or settings.pairs
        out = {}
        for sym in syms:
            df = _fetch_ohlcv_df(db, sym, tf, start_iso, end_iso)
            if df.empty:
                out[sym] = {"inserted": 0, "note": "no data"}
                continue
            feats = _compute_features(df)
            inserted = _upsert_features(db, sym, tf, version, feats)
            out[sym] = {"inserted": inserted, "version": version}
        return {"ok": True, "tf": tf, "version": version, "result": out}
    finally:
        db.close()
