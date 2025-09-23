# apps/ml/features.py
# PL: Pipeline feature engineering + labeling + upsert do tabeli 'features' (JSONB) z wersjonowaniem.
# EN: Feature pipeline + labeling + upsert into 'features' (JSONB) with versioning.

from __future__ import annotations
import os
from typing import List, Dict, Optional

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from apps.api.db.session import SessionLocal
from apps.api.db import models
from apps.ml.ta_utils import (
    ema, rsi, stoch, macd, atr, bollinger, ichimoku,
    pivot_points, fibonacci_levels, realized_vol, microstructure, adx_regime
)
from apps.ml.labeling import triple_barrier_labels
from apps.ml.sentiment_plugin import load_provider

FEATURES_VERSION = int(os.getenv("FEATURES_VERSION", "1"))
LABEL_TP_PCT = float(os.getenv("LABEL_TP_PCT", "0.02"))
LABEL_SL_PCT = float(os.getenv("LABEL_SL_PCT", "0.01"))
LABEL_MAX_HORIZON = int(os.getenv("LABEL_MAX_HORIZON", "60"))

def _fetch_ohlcv(db: Session, symbol: str, tf: str, start_ts: Optional[int], end_ts: Optional[int]) -> pd.DataFrame:
    q = select(models.OHLCV).where(
        models.OHLCV.symbol == symbol,
        models.OHLCV.tf == tf,
    )
    if start_ts is not None:
        q = q.where(models.OHLCV.ts >= start_ts)
    if end_ts is not None:
        q = q.where(models.OHLCV.ts <= end_ts)
    q = q.order_by(models.OHLCV.ts.asc())
    rows = db.execute(q).scalars().all()
    if not rows:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"]).astype({
            "ts": "int64", "open": "float64", "high": "float64", "low": "float64", "close": "float64", "volume": "float64"
        })
    data = {
        "ts": [r.ts for r in rows],
        "open": [r.o for r in rows],
        "high": [r.h for r in rows],
        "low": [r.l for r in rows],
        "close": [r.c for r in rows],
        "volume": [r.v for r in rows],
    }
    df = pd.DataFrame(data)
    return df

def _build_feature_vector(df: pd.DataFrame, symbol: str, tf: str) -> pd.DataFrame:
    # Basic technicals
    ema(df, 9); ema(df, 20); ema(df, 50); ema(df, 200)
    rsi(df, 14)
    stoch(df, 14, 3)
    macd(df, 12, 26, 9)
    atr(df, 14)
    bollinger(df, 20, 2.0)
    ichimoku(df)

    # Derived/micro/momentum/vol
    realized_vol(df, 30)
    microstructure(df)

    # Regime detection uses rv computed above
    adx_regime(df, 14)

    # Fibonacci & pivots
    fibonacci_levels(df, lookback=120)
    pivot_points(df)

    # Returns and normalized distances
    df["ret_1"] = df["close"].pct_change()
    df["ret_5"] = df["close"].pct_change(5)
    df["dist_bb_up"] = (df["close"] - df["bb_up"]) / (df["bb_up"].abs() + 1e-12)
    df["dist_bb_low"] = (df["close"] - df["bb_low"]) / (df["bb_low"].abs() + 1e-12)
    df["atr_p"] = df["atr"] / (df["close"].abs() + 1e-12)

    # Sentiment plugin
    sent = load_provider()
    # for performance, compute sparse (optional); here simple loop
    df["sentiment"] = 0.0
    for i in range(len(df)):
        ts_ms = int(df["ts"].iat[i])
        try:
            df.at[i, "sentiment"] = float(sent.get_score(symbol, ts_ms))
        except Exception:
            df.at[i, "sentiment"] = 0.0

    # Labels (triple-barrier) on same TF
    lbl = triple_barrier_labels(df.copy(), tp_pct=LABEL_TP_PCT, sl_pct=LABEL_SL_PCT, max_horizon=LABEL_MAX_HORIZON)
    df["label_y"] = lbl["label_y"]
    df["label_tp_hit"] = lbl["label_tp_hit"]
    df["label_sl_hit"] = lbl["label_sl_hit"]
    df["label_tte"] = lbl["label_tte"]
    df["meta_label"] = lbl["meta_label"]

    return df

def _df_to_records(df: pd.DataFrame) -> List[Dict]:
    # Construct compact f_vector dict per row
    cols_keep = [c for c in df.columns if c not in ("open", "high", "low", "close", "volume")]
    recs: List[Dict] = []
    for _, r in df.iterrows():
        fvec = {k: (None if pd.isna(r[k]) else float(r[k]) if isinstance(r[k], (np.floating, float)) else (int(r[k]) if isinstance(r[k], (np.integer, int)) else r[k]))
                for k in cols_keep if k != "ts"}
        recs.append({
            "ts": int(r["ts"]),
            "f_vector": fvec
        })
    return recs

def upsert_features(db: Session, symbol: str, tf: str, version: int, records: List[Dict]) -> int:
    if not records:
        return 0
    values = [{"symbol": symbol, "tf": tf, "ts": r["ts"], "version": version, "f_vector": r["f_vector"]} for r in records]
    stmt = pg_insert(models.Features.__table__).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["symbol", "tf", "ts", "version"],
        set_={"f_vector": stmt.excluded.f_vector}
    )
    db.execute(stmt)
    return len(values)

def compute_and_store_features(symbol: str, tf: str, start_ts: Optional[int] = None, end_ts: Optional[int] = None) -> int:
    """
    PL: Liczy featury i etykiety na (symbol, tf, [start_ts..end_ts]) i upsertuje do DB w wersji FEATURES_VERSION.
    EN: Computes features+labels for (symbol, tf, [start_ts..end_ts]) and upserts to DB with FEATURES_VERSION.
    Returns number of upserted rows.
    """
    with SessionLocal() as db:
        df = _fetch_ohlcv(db, symbol, tf, start_ts, end_ts)
        if df.empty:
            return 0
        feat_df = _build_feature_vector(df, symbol, tf)
        records = _df_to_records(feat_df)
        n = upsert_features(db, symbol, tf, FEATURES_VERSION, records)
        db.commit()
        return n

# CLI usage: python -m apps.ml.features BTC/USDT 15m 1700000000000 1710000000000
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python -m apps.ml.features SYMBOL TF [START_TS] [END_TS]")
        sys.exit(1)
    sym = sys.argv[1]
    tf = sys.argv[2]
    s_ts = int(sys.argv[3]) if len(sys.argv) > 3 else None
    e_ts = int(sys.argv[4]) if len(sys.argv) > 4 else None
    rows = compute_and_store_features(sym, tf, s_ts, e_ts)
    print(f"[features] upserted rows: {rows} for {sym} {tf} v{FEATURES_VERSION}")
