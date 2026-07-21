from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PCB_CDSO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = "pcb-cdso-api"
    version: str = "0.6.0"
    environment: str = "development"
    database_url: str = Field(
        default="mysql+pymysql://pcb_cdso:pcb_cdso@mysql:3306/pcb_cdso",
        repr=False,
    )
    redis_url: str = "redis://redis:6379/0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
