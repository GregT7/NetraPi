from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings


def test_settings_requires_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_rejects_empty_database_url() -> None:
    with pytest.raises(ValidationError):
        Settings(database_url="", netrapi_api_key="k", _env_file=None)


def test_settings_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NETRAPI_API_KEY", raising=False)
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        Settings(database_url="sqlite:///:memory:", _env_file=None)


def test_settings_rejects_empty_api_key() -> None:
    with pytest.raises(ValidationError):
        Settings(database_url="sqlite:///:memory:", netrapi_api_key="", _env_file=None)


def test_settings_aws_access_key_alias() -> None:
    settings = Settings(
        database_url="sqlite:///:memory:",
        netrapi_api_key="k",
        AWS_ACCESS_KEY="from-alias",
        _env_file=None,
    )
    assert settings.aws_access_key_id == "from-alias"


def test_settings_default_region() -> None:
    settings = Settings(
        database_url="sqlite:///:memory:",
        netrapi_api_key="k",
        _env_file=None,
    )
    assert settings.aws_region == "us-east-2"
