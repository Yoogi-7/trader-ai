from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import MetaData, Table, Column, String, TIMESTAMP, Float

from apps.api.config import get_settings
settings = get_settings()

engine = create_async_engine(settings.sqlalchemy_dsn_async, echo=False, future=True)
async_session = async_sessionmaker(engine, expire_on_commit=False)

metadata = MetaData()

ohlcv_table = Table(
    "ohlcv", metadata,
    Column("symbol", String(20), primary_key=True),
    Column("tf", String(8), primary_key=True),
    Column("ts", TIMESTAMP, primary_key=True),
    Column("o", Float, nullable=False),
    Column("h", Float, nullable=False),
    Column("l", Float, nullable=False),
    Column("c", Float, nullable=False),
    Column("v", Float, nullable=False),
    Column("source_hash", String(64)),
)

backfill_table = Table(
    "backfill_progress", metadata,
    Column("symbol", String(20), primary_key=True),
    Column("tf", String(8), primary_key=True),
    Column("last_ts", TIMESTAMP),
)
