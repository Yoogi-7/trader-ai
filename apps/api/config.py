
from pydantic import BaseModel
import os

class Settings(BaseModel):
    env: str = os.getenv("ENV", "dev")
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))

    db_host: str = os.getenv("DB_HOST", "db")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_user: str = os.getenv("DB_USER", "trader")
    db_password: str = os.getenv("DB_PASSWORD", "trader")
    db_name: str = os.getenv("DB_NAME", "trader_ai")

    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")

    kafka_brokers: str = os.getenv("KAFKA_BROKERS", "redpanda:9092")
    kafka_signals_topic: str = os.getenv("KAFKA_SIGNALS_TOPIC", "signals")
    kafka_backfill_topic: str = os.getenv("KAFKA_BACKFILL_TOPIC", "backfill")

    fee_maker_bps: int = int(os.getenv("FEE_MAKER_BPS", "2"))
    fee_taker_bps: int = int(os.getenv("FEE_TAKER_BPS", "6"))
    slippage_bps: int = int(os.getenv("SLIPPAGE_BPS", "5"))
    funding_on: bool = os.getenv("FUNDING_ON", "true").lower() == "true"

    base_tf: str = os.getenv("BASE_TF", "15m")
    confirm_tfs: list[str] = os.getenv("CONFIRM_TFS", "1h,4h,1d").split(",")
    pairs: list[str] = os.getenv("PAIRS", "BTCUSDT,ETHUSDT").split(",")

    jwt_secret: str = os.getenv("JWT_SECRET", "devsecret")

settings = Settings()
