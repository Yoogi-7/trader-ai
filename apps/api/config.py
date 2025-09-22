
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    API_TITLE: str = "Trader AI API"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:3000"

    POSTGRES_USER: str = "trader"
    POSTGRES_PASSWORD: str = "trader_pwd"
    POSTGRES_DB: str = "trader_ai"
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432

    REDIS_URL: str = "redis://redis:6379/0"

    MIN_NET_PCT: float = 2.0
    CONFIDENCE_THRESHOLD: float = 0.55
    MAKER_FEE_BPS: float = 7.0
    TAKER_FEE_BPS: float = 10.0
    SLIPPAGE_BPS: float = 5.0
    FUNDING_BPS: float = 1.0

    # risk caps
    MAX_PARALLEL_LOW: int = 2
    MAX_PARALLEL_MED: int = 4
    MAX_PARALLEL_HIGH: int = 8
    RISK_PCT_LOW: float = 0.01
    RISK_PCT_MED: float = 0.02
    RISK_PCT_HIGH: float = 0.03
    MAX_LEV_LOW: int = 5
    MAX_LEV_MED: int = 10
    MAX_LEV_HIGH: int = 20
    CORRELATION_CAP_BTC_ETH: float = 0.5

    EXCHANGE: str = "binanceusdm"
    BASE_TF: str = "15m"
    DATA_TF: str = "1m"
    FUNDING_ON: bool = True

    class Config:
        env_file = ".env"

@lru_cache
def get_settings() -> Settings:
    return Settings()
