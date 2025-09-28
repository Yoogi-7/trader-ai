# apps/api/config.py

import os
from typing import Iterable, List, Optional, Union

from pydantic import BaseModel, Field, field_validator

DEFAULT_PAIRS = "BTC/USDT,ETH/USDT,BNB/USDT,ADA/USDT,SOL/USDT"

def _coerce_pairs(value: Optional[Union[str, Iterable[str]]]) -> List[str]:
    """Normalise pairs input from env/string/list into a clean list."""
    if value is None:
        return []
    if isinstance(value, str):
        items = value.split(",")
    else:
        items = list(value)
    cleaned: List[str] = []
    for item in items:
        text = str(item).strip()
        if text:
            cleaned.append(text)
    return cleaned

class Settings(BaseModel):
    app_name: str = Field(default=os.getenv("APP_NAME", "Trader AI API"))
    version: str = Field(default=os.getenv("APP_VERSION", "0.1.0"))
    database_url: str = Field(
        default=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://trader:traderpass@db:5432/traderai",
        )
    )
    api_prefix: str = Field(default=os.getenv("API_PREFIX", ""))
    default_page_size: int = Field(default=int(os.getenv("DEFAULT_PAGE_SIZE", "50")))
    max_page_size: int = Field(default=int(os.getenv("MAX_PAGE_SIZE", "500")))
    pairs: List[str] = Field(
        default_factory=lambda: _coerce_pairs(os.getenv("PAIRS", DEFAULT_PAIRS))
    )
    jwt_secret: str = Field(default=os.getenv("JWT_SECRET", "change-me"))
    jwt_exp_minutes: int = Field(default=int(os.getenv("JWT_EXP_MINUTES", "60")))
    admin_email: str = Field(default=os.getenv("ADMIN_EMAIL", "admin@example.com"))
    admin_password: str = Field(default=os.getenv("ADMIN_PASSWORD", "admin123"))

    @field_validator("pairs", mode="before")
    @classmethod
    def _parse_pairs(cls, value: Optional[Union[str, Iterable[str]]]) -> List[str]:
        parsed = _coerce_pairs(value)
        if not parsed:
            return _coerce_pairs(DEFAULT_PAIRS.split(","))
        return parsed

settings = Settings()
