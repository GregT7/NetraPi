from pathlib import Path

import pytest

from netrapi.backend_auth import (
    apply_edge_env,
    clear_ingest_auth,
    ingest_api_url,
    ingest_headers,
    load_ingest_auth,
)
from netrapi.exceptions import IngestAuthError
import netrapi.backend_auth as backend_auth


@pytest.fixture(autouse=True)
def _reset_ingest_auth() -> None:
    clear_ingest_auth()
    yield
    clear_ingest_auth()


def test_load_ingest_auth_reads_process_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NETRAPI_API_URL", "https://netrapi.onrender.com/")
    monkeypatch.setenv("NETRAPI_API_KEY", "from-process")
    auth = load_ingest_auth()
    assert auth.api_url == "https://netrapi.onrender.com"
    assert auth.api_key == "from-process"
    assert ingest_api_url() == "https://netrapi.onrender.com"
    assert ingest_headers() == {"X-API-Key": "from-process"}


def test_load_ingest_auth_does_not_reread_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NETRAPI_API_URL", "https://first.example")
    monkeypatch.setenv("NETRAPI_API_KEY", "first")
    load_ingest_auth()
    monkeypatch.setenv("NETRAPI_API_KEY", "second")
    assert load_ingest_auth().api_key == "first"
    assert ingest_headers() == {"X-API-Key": "first"}


def test_apply_edge_env_fills_unset_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "NETRAPI_API_URL=https://from-file.example\nNETRAPI_API_KEY=from-file\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(backend_auth, "ENV_PATH", env_path)
    monkeypatch.delenv("NETRAPI_API_URL", raising=False)
    monkeypatch.delenv("NETRAPI_API_KEY", raising=False)
    apply_edge_env()
    load_ingest_auth()
    assert ingest_api_url() == "https://from-file.example"
    assert ingest_headers() == {"X-API-Key": "from-file"}


def test_apply_edge_env_does_not_overwrite_process_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("NETRAPI_API_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setattr(backend_auth, "ENV_PATH", env_path)
    monkeypatch.setenv("NETRAPI_API_URL", "https://from-process.example")
    monkeypatch.setenv("NETRAPI_API_KEY", "from-process")
    apply_edge_env()
    load_ingest_auth()
    assert ingest_headers() == {"X-API-Key": "from-process"}


def test_headers_before_load_raises() -> None:
    with pytest.raises(IngestAuthError, match="not loaded"):
        ingest_headers()


def test_load_ingest_auth_missing_vars_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NETRAPI_API_URL", raising=False)
    monkeypatch.delenv("NETRAPI_API_KEY", raising=False)
    with pytest.raises(IngestAuthError, match="NETRAPI_API_URL"):
        load_ingest_auth()
