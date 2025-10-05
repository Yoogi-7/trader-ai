from pydantic import PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    # Database
    DATABASE_URL: PostgresDsn
    ASYNC_DATABASE_URL: PostgresDsn

    # Redis
    REDIS_URL: RedisDsn

    # Celery
    CELERY_BROKER_URL: RedisDsn
    CELERY_RESULT_BACKEND: RedisDsn

    # API
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080

    # Exchange
    EXCHANGE_ID: str = "binance"
    EXCHANGE_SANDBOX: bool = False
    EXCHANGE_API_KEY: str = ""
    EXCHANGE_SECRET: str = ""

    # ML
    MIN_CONFIDENCE_THRESHOLD: float = 0.55
    MIN_NET_PROFIT_PCT: float = 2.0
    MIN_HISTORICAL_WIN_RATE: float = 0.45
    HISTORICAL_PERFORMANCE_SAMPLE: int = 250
    DEFAULT_LOOKBACK_YEARS: int = 4
    MODEL_REGISTRY_DIR: str = "./model_registry"
    PERFORMANCE_TRACKING_DIR: str = "./performance_tracking"

    # LLM / Summaries
    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_API_KEY: str = ""
    LLM_MAX_TOKENS: int = 512
    LLM_SUMMARY_TEMPLATE: str = (
        "Signal $signal_id on $symbol recommends a $side position at $entry_price "
        "with expected profit of $expected_net_profit_pct% and confidence $confidence%."
    )

    # Costs
    MAKER_FEE_BPS: float = 2.0
    TAKER_FEE_BPS: float = 5.0
    SLIPPAGE_BPS: float = 3.0
    FUNDING_RATE_HOURLY_BPS: float = 1.0

    # Risk Profiles
    LOW_RISK_PER_TRADE: float = 0.01
    MED_RISK_PER_TRADE: float = 0.02
    HIGH_RISK_PER_TRADE: float = 0.03
    LOW_MAX_LEV: int = 5
    MED_MAX_LEV: int = 10
    HIGH_MAX_LEV: int = 20
    LOW_MAX_POSITIONS: int = 2
    MED_MAX_POSITIONS: int = 4
    HIGH_MAX_POSITIONS: int = 6

    # Monitoring
    DRIFT_PSI_THRESHOLD: float = 0.15
    DRIFT_KS_THRESHOLD: float = 0.1
    MAX_CONSECUTIVE_LOSSES: int = 5


settings = Settings()
