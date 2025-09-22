from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_csv_or_json_list(val: str) -> List[str]:
    """
    Akceptuj:
      - pusty string -> []
      - CSV: "http://a,http://b"
      - JSON list: '["http://a","http://b"]'
    Zwracaj listę stringów bez pustych elementów.
    """
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
    """
    Centralna konfiguracja aplikacji.
    - Czyta z .env
    - Ignoruje nadmiarowe klucze (extra="ignore")
    - CORS: czytamy jako string (alias 'cors_origins') i parsujemy ręcznie.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- API / ogólne ---
    log_level: str = Field(default="INFO")
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    # Surowa wartość z .env (alias 'cors_origins'); lista w property 'cors_origins'
    cors_origins_raw: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="cors_origins",
        description="CSV lub JSON list stringów do CORS; parsowane do listy w property 'cors_origins'.",
    )

    # --- DB / Timescale ---
    db_host: str = Field(default="db")
    db_port: int = Field(default=5432)
    db_user: str = Field(default="trader")
    db_password: str = Field(default="trader")
    db_name: str = Field(default="trader_ai")
    database_url: Optional[str] = None
    timescale_twox: bool = Field(default=True)

    # --- Redis ---
    redis_url: str = Field(default="redis://redis:6379/0")

    # --- Kafka / Redpanda ---
    kafka_broker: str = Field(default="kafka:9092")
    kafka_topic_signals: str = Field(default="signals")

    # --- Trading / parametry biznesowe ---
    pairs: str = Field(
        default="BTCUSDT,ETHUSDT",
        description="Comma-separated symbols, e.g. 'BTCUSDT,ETHUSDT'",
    )
    backfill_years: int = Field(default=4)
    maker_first: bool = Field(default=True)
    shadow_paper: bool = Field(default=True)

    # --- Koszty / domyślne ---
    fee_maker_bps: float = Field(default=7.0)
    fee_taker_bps: float = Field(default=10.0)
    slippage_bps: float = Field(default=5.0)
    funding_on: bool = Field(default=True)

    @property
    def cors_origins(self) -> List[str]:
        return _parse_csv_or_json_list(self.cors_origins_raw)

    @property
    def sqlalchemy_dsn(self) -> str:
        """Złóż DSN jeśli DATABASE_URL nie jest podane wprost."""
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def pairs_list(self) -> List[str]:
        """Lista symboli z CSV (z .env)."""
        return [p.strip() for p in self.pairs.split(",") if p.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
