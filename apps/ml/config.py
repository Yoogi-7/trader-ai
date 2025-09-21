from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "trader_ai"
    POSTGRES_USER: str = "trader"
    POSTGRES_PASSWORD: str = "trader_pw"
    REDIS_URL: str = "redis://redis:6379/0"
    KAFKA_BROKERS: str = "redpanda:9092"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    BACKFILL_CHUNK_MINUTES: int = 1440
    PAIRS: str = "BTCUSDT,ETHUSDT"
    FEE_TAKER_BPS: int = 10
    FEE_MAKER_BPS: int = 2
    DEFAULT_SLIPPAGE_BPS: int = 5
    FUNDING_TOGGLE: bool = True
    DEMO_MODE: bool = True
    DEMO_SEED_ROWS: int = 2000
    SECRET_KEY: str = "changeme"

    MAX_LEV_LOW: int = 5
    MAX_LEV_MED: int = 10
    MAX_LEV_HIGH: int = 20
    RISK_PER_TRADE_LOW: float = 0.003
    RISK_PER_TRADE_MED: float = 0.007
    RISK_PER_TRADE_HIGH: float = 0.015
    MAX_PARALLEL_POS_LOW: int = 2
    MAX_PARALLEL_POS_MED: int = 4
    MAX_PARALLEL_POS_HIGH: int = 6
    CORR_CAP_BTC_ETH_PCT: float = 0.35

settings = Settings()
