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

    # ML - OPTIMIZED FOR MORE SIGNALS WITH QUALITY
    MIN_CONFIDENCE_THRESHOLD: float = 0.50  # Lowered for more signal generation
    MIN_NET_PROFIT_PCT: float = 1.0  # OPTIMIZED: Minimum 1% net profit (more signals pass)
    MIN_ACCURACY_TARGET: float = 0.60  # Target 60% accuracy for model training
    MIN_HISTORICAL_WIN_RATE: float = 0.40  # More lenient historical filter
    HISTORICAL_PERFORMANCE_SAMPLE: int = 250
    DEFAULT_LOOKBACK_YEARS: int = 4
    MODEL_REGISTRY_DIR: str = "./model_registry"
    PERFORMANCE_TRACKING_DIR: str = "./performance_tracking"

    # Auto-Training Configuration
    AUTO_TRAINING_ENABLED: bool = False  # Disabled by default, enable via API
    AUTO_TRAINING_INTERVAL_DAYS: int = 7  # Retrain every 12 hours
    QUICK_TRAINING_TEST_DAYS: int = 14  # Quick mode: 14 day test windows
    QUICK_TRAINING_MIN_DAYS: int = 90  # Quick mode: 90 days min training
    FULL_TRAINING_TEST_DAYS: int = 30  # Full mode: 30 day test windows
    FULL_TRAINING_MIN_DAYS: int = 180  # Full mode: 180 days min training

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

    # Risk Profiles - OPTIMIZED FOR BETTER RETURNS
    # Risk per trade = % of capital risked if SL is hit
    LOW_RISK_PER_TRADE: float = 0.02   # 2% - Conservative
    MED_RISK_PER_TRADE: float = 0.05   # 5% - Balanced (RECOMMENDED)
    HIGH_RISK_PER_TRADE: float = 0.10  # 10% - Aggressive

    # Leverage limits - AUTO-ADJUSTED based on market conditions
    LOW_MAX_LEV: int = 8
    MED_MAX_LEV: int = 20   # Higher leverage for bigger TP
    HIGH_MAX_LEV: int = 30  # For experienced traders
    AUTO_LEVERAGE: bool = True  # Enable automatic leverage adjustment

    # Max concurrent positions
    LOW_MAX_POSITIONS: int = 2
    MED_MAX_POSITIONS: int = 5
    HIGH_MAX_POSITIONS: int = 8

    # Monitoring
    DRIFT_PSI_THRESHOLD: float = 0.15
    DRIFT_KS_THRESHOLD: float = 0.1
    MAX_CONSECUTIVE_LOSSES: int = 5


settings = Settings()
