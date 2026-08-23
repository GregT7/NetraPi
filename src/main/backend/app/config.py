from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    database_url: str = Field(min_length=1)
    netrapi_api_key: str = Field(min_length=1)
    aws_access_key_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("AWS_ACCESS_KEY_ID", "AWS_ACCESS_KEY"),
    )
    aws_secret_access_key: Optional[str] = None
    aws_region: Optional[str] = Field(
        default="us-east-2",
        validation_alias=AliasChoices("AWS_REGION", "AWS_DEFAULT_REGION"),
    )
    aws_s3_bucket: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("AWS_S3_BUCKET", "S3_BUCKET"),
    )
    supabase_db_host: Optional[str] = None
    supabase_db_port: Optional[str] = None
    supabase_db_name: Optional[str] = None
    supabase_db_user: Optional[str] = None
    supabase_db_password: Optional[str] = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
