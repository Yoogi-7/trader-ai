# apps/api/config.py

import os
from pydantic import BaseModel, Field

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

settings = Settings()
