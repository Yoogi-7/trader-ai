from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_csv_or_json_list(val: str) -> List[str]:
    if val is None:
        return []
    s = str(val).strip()
    if s == "":
        return []
    if s.startswith("["):
        import json
        try:
            data = json.loads(s)
            if isinstance(data, list):
                return [str(x).strip() for x in data if str(x).strip()]
            return []
        except Exception:
            return [x.strip() for x in s.split(",") if x.strip()]
    return [x.strip() for x in s.split(",") if x.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API
    log_level: str = Field(default="INFO")
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    cors_origins_raw: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="cors_origins",
    )

    # DB
    db_host: str = Field(default="db")
    db_port: int = Field(default=5432)
    db_user: str = Field(default="trader")
    db_password: str = Field(default="trader")
    db_name: str = Field(default="trader_ai")
    database_url: Optional[str] = None
    timescale_twox: bool = Field(default=True)

    # Redis
    redis_url: str = Field(default="redis://redis:6379/0")

    # Kafka
    kafka_broker: str = Field(default="kafka:9092")
    kafka_topic_signals: str = Field(default="signals")

    # Trading / dane
    pairs: str = Field(default="BTCUSDT,ETHUSDT")
    backfill_years: int = Field(default=4)
    maker_first: bool = Field(default=True)
    shadow_paper: bool = Field(default=True)

    # Koszty
    fee_maker_bps: float = Field(default=7.0)
    fee_taker_bps: float = Field(default=10.0)
    slippage_bps: float = Field(default=5.0)
    funding_on: bool = Field(default=True)

    @property
    def cors_origins(self) -> List[str]:
        return _parse_csv_or_json_list(self.cors_origins_raw)

    @property
    def sqlalchemy_dsn(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def sqlalchemy_dsn_async(self) -> str:
        """DSN do async engine (asyncpg)."""
        if self.database_url:
            # jeżeli podasz DATABASE_URL, a chcesz async – podaj od razu z driverem async
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def pairs_list(self) -> List[str]:
        return [p.strip() for p in self.pairs.split(",") if p.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
