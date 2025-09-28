# -*- coding: utf-8 -*-
"""
Backfill 4y OHLCV (1m) z resume, gaps i metrykami.
- CCXT (Binance Futures) jako domyślne źródło
- Checkpointing w tabeli backfill_progress
- Retry + rate-limit friendly
- Wstrzykiwalny fetcher (na testy)
- Metryki: prędkość (świece/min), ETA, procent postępu, luki
"""
from __future__ import annotations

import math
import time
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import pandas as pd
from celery import shared_task
from loguru import logger
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

try:
    import ccxt  # type: ignore
except Exception:  # pragma: no cover
    ccxt = None  # pozwala uruchamiać testy bez CCXT

from apps.api.config import settings
from apps.api.db.models import BackfillProgress, OHLCV
from apps.api.db.session import SessionLocal

UTC = timezone.utc


# ---- Narzędzia czasu ----
def now_ms() -> int:
    return int(time.time() * 1000)


def parse_since(start_ts_ms: Optional[int]) -> int:
    """Jeśli brak start_ts: 4 lata wstecz od teraz."""
    if start_ts_ms is not None:
        return start_ts_ms
    dt = datetime.now(tz=UTC) - timedelta(days=365 * 4 + 1)
    return int(dt.timestamp() * 1000)


# ---- Fetcher CCXT ----
def ccxt_fetcher_factory(exchange_id: str = "binanceusdm", rate_limit_ms: int = 100) -> Callable:
    """
    Zwraca funkcję fetchera: fetch(symbol:str, tf:str, since_ms:int, limit:int)->List[dict]
    Domyślnie: Binance Futures USDⓈ-M.
    """
    if ccxt is None:
        raise RuntimeError("ccxt not available in environment")

    ex = getattr(ccxt, exchange_id)({"enableRateLimit": True})
    # W razie potrzeby skonfiguruj API keys z env
    # ex.apiKey = os.getenv("EXCHANGE_KEY")
    # ex.secret = os.getenv("EXCHANGE_SECRET")

    def fetch(symbol: str, tf: str, since_ms: int, limit: int) -> List[dict]:
        # retry-friendly
        for attempt in range(6):
            try:
                data = ex.fetch_ohlcv(symbol, timeframe=tf, since=since_ms, limit=limit)
                # Format: [ ts, o, h, l, c, v ]
                out = [
                    {
                        "ts": int(row[0]),
                        "o": float(row[1]),
                        "h": float(row[2]),
                        "l": float(row[3]),
                        "c": float(row[4]),
                        "v": float(row[5]),
                    }
                    for row in data
                ]
                return out
            except Exception as e:  # noqa
                sleep_s = (attempt + 1) * 1.5
                logger.warning(f"CCXT fetch retry {attempt+1}: {e}; sleep {sleep_s}s")
                time.sleep(sleep_s)
        return []

    return fetch


# ---- Gaps detection ----
def detect_gaps(timestamps_ms: List[int], tf_ms: int) -> List[Tuple[int, int]]:
    """Zwraca listę (start_ts, end_ts) dla luk dłuższych niż jedna świeca."""
    if not timestamps_ms:
        return []
    timestamps_ms = sorted(set(timestamps_ms))
    gaps: List[Tuple[int, int]] = []
    for prev, nxt in zip(timestamps_ms, timestamps_ms[1:]):
        if nxt - prev > tf_ms:
            gaps.append((prev + tf_ms, nxt - tf_ms))
    return gaps


# ---- Runner ----
class BackfillRunner:
    def __init__(
        self,
        db: Session,
        fetcher: Callable[[str, str, int, int], List[dict]],
        tf: str = "1m",
        pairs: Optional[List[str]] = None,
        start_ts_ms: Optional[int] = None,
        end_ts_ms: Optional[int] = None,
        batch_limit: int = 1000,
    ):
        self.db = db
        self.fetcher = fetcher
        self.tf = tf
        self.pairs = pairs or settings.pairs
        self.start_ts_ms = parse_since(start_ts_ms)
        self.end_ts_ms = end_ts_ms or now_ms()
        self.batch_limit = batch_limit
        self.tf_ms = self._tf_to_ms(tf)
        self.metrics: Dict[str, dict] = {}

    @staticmethod
    def _tf_to_ms(tf: str) -> int:
        unit = tf[-1]
        val = int(tf[:-1])
        if unit == "m":
            return val * 60_000
        if unit == "h":
            return val * 60 * 60_000
        if unit == "d":
            return val * 24 * 60 * 60_000
        raise ValueError(f"Unsupported timeframe {tf}")

    def _progress_row(self, symbol: str) -> BackfillProgress:
        row = (
            self.db.execute(
                select(BackfillProgress).where(
                    BackfillProgress.symbol == symbol, BackfillProgress.tf == self.tf
                )
            )
            .scalars()
            .first()
        )
        if not row:
            row = BackfillProgress(
                symbol=symbol,
                tf=self.tf,
                last_ts_completed=None,
                chunk_start_ts=None,
                chunk_end_ts=None,
                retry_count=0,
                status="idle",
                updated_at=datetime.now(tz=UTC),
                gaps=[],
            )
            self.db.add(row)
            self.db.commit()
            self.db.refresh(row)
        return row

    def _upsert_ohlcv_batch(self, symbol: str, rows: List[dict]) -> int:
        if not rows:
            return 0
        stmt = insert(OHLCV).values(
            [
                dict(
                    symbol=symbol,
                    tf=self.tf,
                    ts=row["ts"],
                    o=row["o"],
                    h=row["h"],
                    l=row["l"],
                    c=row["c"],
                    v=row["v"],
                    source_hash=None,
                )
                for row in rows
            ]
        )
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["symbol", "tf", "ts"]
        )  # Upsert: pomiń duplikaty
        res = self.db.execute(stmt)
        self.db.commit()
        return res.rowcount or 0

    def _update_progress(
        self, row: BackfillProgress, **fields
    ) -> None:
        for k, v in fields.items():
            setattr(row, k, v)
        row.updated_at = datetime.now(tz=UTC)
        self.db.add(row)
        self.db.commit()

    def run_symbol(self, symbol: str) -> dict:
        row = self._progress_row(symbol)
        status = "running"
        resumed_from = row.last_ts_completed
        since = max(self.start_ts_ms, (resumed_from + self.tf_ms) if resumed_from else self.start_ts_ms)
        until = self.end_ts_ms

        total_needed = max(0, ((until - since) // self.tf_ms) + 1)
        done = 0
        started_at = time.time()
        seen_ts: List[int] = []

        self._update_progress(row, status=status, chunk_start_ts=since, chunk_end_ts=until)

        while since <= until:
            batch = self.fetcher(symbol, self.tf, since, self.batch_limit)
            if not batch:
                # brak danych – przejdź o jeden interwał, rejestruj lukę
                seen_ts.append(since)
                since += self.batch_limit * self.tf_ms
                continue

            inserted = self._upsert_ohlcv_batch(symbol, batch)
            last_ts = batch[-1]["ts"]
            seen_ts.extend([b["ts"] for b in batch])

            since = last_ts + self.tf_ms
            done = int(((since - self._progress_row(symbol).chunk_start_ts) // self.tf_ms))  # type: ignore
            elapsed = max(1e-6, time.time() - started_at)
            speed = done / elapsed * 60.0  # candles per minute
            remaining = max(0, total_needed - done)
            eta_min = remaining / speed if speed > 0 else None
            pct = (done / total_needed * 100.0) if total_needed > 0 else 100.0

            self._update_progress(
                row,
                last_ts_completed=last_ts,
                status="running",
            )
            self.metrics[symbol] = {
                "symbol": symbol,
                "tf": self.tf,
                "progress_pct": round(pct, 2),
                "speed_cpm": round(speed, 2),
                "eta_min": round(eta_min, 2) if eta_min is not None and math.isfinite(eta_min) else None,
                "done": done,
                "total": total_needed,
            }

            # delikatny rate-limit
            time.sleep(0.05)

        # final gaps
        gaps = detect_gaps(seen_ts, self.tf_ms)
        self._update_progress(row, status="done", gaps=gaps)
        return {"symbol": symbol, "status": "done", "gaps": gaps, "metrics": self.metrics.get(symbol)}

    def run(self) -> dict:
        out = {}
        for sym in self.pairs:
            try:
                out[sym] = self.run_symbol(sym)
            except Exception as e:  # noqa
                logger.exception(f"Backfill error for {sym}: {e}")
                row = self._progress_row(sym)
                self._update_progress(row, status="failed")
                out[sym] = {"symbol": sym, "status": "failed", "error": str(e)}
        return out


# ===== Celery task API =====

@shared_task
def run_backfill(
    pairs: Optional[List[str]] = None,
    tf: str = "1m",
    start_ts_ms: Optional[int] = None,
    end_ts_ms: Optional[int] = None,
    batch_limit: int = 1000,
    use_ccxt: bool = True,
):
    """
    Główny task. Domyślnie używa CCXT. W testach można wstrzyknąć fetche ręcznie (przez patch/run_local).
    """
    db = SessionLocal()
    try:
        fetcher = ccxt_fetcher_factory() if use_ccxt else None
        if fetcher is None:
            raise RuntimeError("Fetcher not provided and ccxt disabled")

        runner = BackfillRunner(
            db=db,
            fetcher=fetcher,
            tf=tf,
            pairs=pairs or settings.pairs,
            start_ts_ms=start_ts_ms,
            end_ts_ms=end_ts_ms,
            batch_limit=batch_limit,
        )
        result = runner.run()
        return {"ok": True, "result": result}
    finally:
        db.close()


# ===== Uruchomienie lokalne (np. debug) =====

def run_local(fetcher: Callable, **kwargs):
    db = SessionLocal()
    try:
        runner = BackfillRunner(db=db, fetcher=fetcher, **kwargs)
        return runner.run()
    finally:
        db.close()
