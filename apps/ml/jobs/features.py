# -*- coding: utf-8 -*-
from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Optional, List

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session
from celery import shared_task

from apps.api.db.session import SessionLocal
from apps.api.db.models import Feature
from apps.api.config import settings
from apps.ml.features.indicators import ema, rsi, macd, atr, bollinger, stochastic, ichimoku

UTC = timezone.utc

TF_VIEW = {
    "1m": "ohlcv",
    "15m": "ohlcv_15m",
    "1h": "ohlcv_1h",
    "4h": "ohlcv_4h",
    "1d": "ohlcv_1d",
}

def _fetch_ohlcv_df(db: Session, symbol: str, tf: str, start_iso: Optional[str], end_iso: Optional[str]) -> pd.DataFrame:
    view = TF_VIEW[tf]
    if tf == "1m":
        # surowa tabela ohlcv – używamy ts_time
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
    out = pd.DataFrame(index=df.index)
    out["ema_20"] = ema(df["c"], 20)
    out["ema_50"] = ema(df["c"], 50)
    out["rsi_14"] = rsi(df["c"], 14)
    macd_df = macd(df["c"], 12, 26, 9)
    out = out.join(macd_df)
    out["atr_14"] = atr(df["h"], df["l"], df["c"], 14)
    out = out.join(bollinger(df["c"], 20, 2.0))
    out = out.join(stochastic(df["h"], df["l"], df["c"], 14, 3))
    out = out.join(ichimoku(df["h"], df["l"]))
    # Dodatkowe proste cechy: zmienność i zwroty
    out["ret_1"] = df["c"].pct_change().fillna(0.0)
    out["rv_10"] = (df["c"].pct_change().rolling(10).std() * (10 ** 0.5)).fillna(0.0)
    return out

def _upsert_features(db: Session, symbol: str, tf: str, version: str, fdf: pd.DataFrame, chunk: int = 1000) -> int:
    total = 0
    cols = list(fdf.columns)
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
        # ON CONFLICT (symbol, tf, ts, version) DO UPDATE SET f_vector=EXCLUDED.f_vector
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
