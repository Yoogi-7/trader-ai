from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

import ccxt  # synchroniczne API
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from apps.worker.db import async_session, ohlcv_table, backfill_table
from apps.api.config import get_settings

settings = get_settings()
logger = logging.getLogger("data_fetcher")
logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))

# Binance Futures (USDT-M)
exchange = ccxt.binanceusdm({
    "enableRateLimit": True,
    "options": {"adjustForTimeDifference": True},
})

# mapowanie TF -> przesunięcie w ms
TF_MS = {
    "15m": 15 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000,
}

def _symbol_to_ccxt(sym: str) -> str:
    """BTCUSDT -> BTC/USDT"""
    sym = sym.upper().strip()
    if sym.endswith("USDT") and "/" not in sym:
        base = sym[:-4]
        return f"{base}/USDT"
    return sym

def _utc(ts_ms: int) -> datetime:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)

async def backfill_symbol_tf(symbol: str, tf: str, years: int = 4) -> None:
    """
    Backfill OHLCV dla pary i interwału:
    - start: 'now - years'
    - resume: od last_ts z tabeli backfill_progress
    - zapis: upsert do ohlcv, checkpoint do backfill_progress
    """
    ccxt_symbol = _symbol_to_ccxt(symbol)
    step_ms = TF_MS[tf]
    start_ms = int((datetime.now(tz=timezone.utc) - timedelta(days=365 * years)).timestamp() * 1000)

    async with async_session() as session:
        # checkpoint
        res = await session.execute(
            select(backfill_table.c.last_ts).where(
                (backfill_table.c.symbol == symbol) & (backfill_table.c.tf == tf)
            )
        )
        last_ts = res.scalar_one_or_none()
        if last_ts:
            start_ms = int(last_ts.replace(tzinfo=timezone.utc).timestamp() * 1000)

        logger.info(f"[{symbol} {tf}] start from {_utc(start_ms).isoformat()}")

        # pobieraj porcjami (limit 1500, Binance zwykle akceptuje do 1500)
        limit = 1000
        since_ms = start_ms

        while True:
            # fetch_ohlcv jest synchroniczne – trzymamy pętlę bez asyncio równoległości (stabilniej)
            candles = exchange.fetch_ohlcv(ccxt_symbol, timeframe=tf, since=since_ms, limit=limit)
            if not candles:
                logger.info(f"[{symbol} {tf}] no more candles, done.")
                break

            rows = []
            for ts, o, h, l, c, v in candles:
                rows.append({
                    "symbol": symbol,
                    "tf": tf,
                    "ts": _utc(ts).replace(tzinfo=None),  # zapis jako naive UTC do PG
                    "o": float(o),
                    "h": float(h),
                    "l": float(l),
                    "c": float(c),
                    "v": float(v),
                    "source_hash": f"{symbol}-{tf}-{ts}",
                })

            # upsert do ohlcv (ON CONFLICT DO NOTHING – mamy PK (symbol, tf, ts))
            stmt = pg_insert(ohlcv_table).values(rows).on_conflict_do_nothing(
                index_elements=["symbol", "tf", "ts"]
            )
            await session.execute(stmt)

            # checkpoint: ostatnia świeca
            last_ts_ms = candles[-1][0]
            chk_stmt = pg_insert(backfill_table).values(
                symbol=symbol, tf=tf, last_ts=_utc(last_ts_ms).replace(tzinfo=None)
            ).on_conflict_do_update(
                index_elements=["symbol", "tf"],
                set_={"last_ts": _utc(last_ts_ms).replace(tzinfo=None)}
            )
            await session.execute(chk_stmt)
            await session.commit()

            logger.info(f"[{symbol} {tf}] up to {_utc(last_ts_ms).isoformat()} ({len(candles)} candles)")

            # kolejna porcja
            next_ms = last_ts_ms + step_ms
            # zabezpieczenie: jeżeli nic nie przesunęło okna (np. pojedyncza świeca)
            if next_ms <= since_ms:
                next_ms = since_ms + step_ms
            since_ms = next_ms

            # proste rate-limit friendly
            time.sleep(0.3)

async def run_backfill() -> None:
    pairs = settings.pairs_list
    tfs = ["15m", "1h", "4h", "1d"]

    for p in pairs:
        for tf in tfs:
            try:
                await backfill_symbol_tf(p, tf, years=settings.backfill_years)
            except Exception as e:
                logger.exception(f"[{p} {tf}] error: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_backfill())
