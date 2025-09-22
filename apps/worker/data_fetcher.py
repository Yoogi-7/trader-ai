import ccxt
import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy import insert, select
from apps.worker.db import async_session, ohlcv_table, backfill_table
from apps.api.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Map Binance intervals to minutes
TF_MAP = {
    "15m": 15,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
}

exchange = ccxt.binance({"enableRateLimit": True})

async def fetch_and_store(symbol: str, tf: str, years: int = 4):
    """Backfill OHLCV for given pair and interval with resume support."""
    minutes = TF_MAP[tf]
    since = int((datetime.utcnow() - timedelta(days=365 * years)).timestamp() * 1000)

    async with async_session() as session:
        # Check last checkpoint
        q = await session.execute(
            select(backfill_table.c.last_ts).where(
                (backfill_table.c.symbol == symbol) & (backfill_table.c.tf == tf)
            )
        )
        last_ts = q.scalar()
        if last_ts:
            since = int(last_ts.timestamp() * 1000)

        logger.info(f"Fetching {symbol} {tf} since {datetime.utcfromtimestamp(since/1000)}")

        while True:
            candles = exchange.fetch_ohlcv(symbol, tf, since=since, limit=1000)
            if not candles:
                break

            rows = []
            for ts, o, h, l, c, v in candles:
                rows.append({
                    "symbol": symbol,
                    "tf": tf,
                    "ts": datetime.utcfromtimestamp(ts/1000),
                    "o": o, "h": h, "l": l, "c": c, "v": v,
                    "source_hash": f"{symbol}-{tf}-{ts}"
                })

            await session.execute(insert(ohlcv_table).prefix_with("ON CONFLICT DO NOTHING"), rows)

            since = candles[-1][0] + minutes * 60 * 1000

            # Update checkpoint
            await session.execute(
                insert(backfill_table)
                .values(symbol=symbol, tf=tf, last_ts=datetime.utcfromtimestamp(candles[-1][0]/1000))
                .on_conflict_do_update(
                    index_elements=["symbol", "tf"],
                    set_={"last_ts": datetime.utcfromtimestamp(candles[-1][0]/1000)}
                )
            )

            await session.commit()

            logger.info(f"{symbol} {tf} up to {datetime.utcfromtimestamp(candles[-1][0]/1000)}")

async def main():
    tasks = []
    for pair in settings.pairs_list:
        for tf in ["15m", "1h", "4h", "1d"]:
            tasks.append(fetch_and_store(pair, tf, years=settings.backfill_years))
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
