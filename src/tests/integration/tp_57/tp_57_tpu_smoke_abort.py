"""
TP-57: TPU smoke abort (integration).

Mocks a failed Coral dummy invoke and runs the capture path of
``src/main/edge/main.py``. Capture must not start.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _render import configure_import_path  # noqa: E402

configure_import_path()


def main() -> int:
    from main import main as edge_main
    from netrapi.health import HealthResult

    print("TP-57: TPU smoke abort", flush=True)
    print("  1. Mock boot health abort (TPU fail)", flush=True)
    print("  2. Run main() capture path", flush=True)

    health = HealthResult(mode="offline", abort=True, detector=None)
    with (
        patch("config.loader.AppConfig.load", return_value=MagicMock()),
        patch("db.database.init_engine"),
        patch("netrapi.build_pipeline") as build,
        patch("netrapi.backend_auth.apply_edge_env"),
        patch("netrapi.health.run_boot_health", return_value=health),
        patch("netrapi.health.KeepAlive") as keepalive_cls,
        patch("main._resolve_runtime_paths", side_effect=lambda cfg, _root: cfg),
    ):
        code = edge_main([])

    if code != 1:
        raise RuntimeError(f"expected exit 1, got {code}")
    if build.called:
        raise RuntimeError("build_pipeline should not run after TPU abort")
    if keepalive_cls.called:
        raise RuntimeError("KeepAlive should not start after TPU abort")
    print("PASS: TPU abort exits 1 without capture", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
