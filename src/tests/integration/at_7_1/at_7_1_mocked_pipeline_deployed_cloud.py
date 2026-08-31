"""
AT-7.1: Mocked Pi pipeline to deployed cloud.

Builds the real edge pipeline (build_pipeline → RecordingManager.run_loop →
LocalStore → CloudIngest). Mocks camera + EventManager only. Persist and
ingest are the production path, not a seed harness.

Usage (from repo root, Pi edge venv — Coral + buzzer on BCM 18; no USB camera):

    python src/tests/integration/at_7_1/at_7_1_mocked_pipeline_deployed_cloud.py
"""

from __future__ import annotations

import math
import os
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Callable

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
INTEGRATION_DIR = SCRIPT_DIR.parent
MAIN_DIR = SCRIPT_DIR.parents[2] / "main"
EDGE_DIR = MAIN_DIR / "edge"
OUTPUT_DB_PATH = SCRIPT_DIR / "netrapi.db"
CLIPS_SUBDIR = "at_7_1"

PRE_ROLL_SECONDS = 1.0
POST_ROLL_SECONDS = 1.0
PRE_FILL_LAP_BUDGET = 150
VERIFY_TPU = False
PREVIEW_ENABLED = False
FULL_RECORD = False


class _FakeCamera:
    """Synthetic frames paced at capture_fps so pre-roll timestamps can fill."""

    def __init__(self, frame: np.ndarray, *, capture_fps: float = 30.0) -> None:
        self._frame = frame
        self.capture_fps = capture_fps
        self._period = 1.0 / capture_fps if capture_fps > 0 else 0.0

    def open(self) -> None:
        return None

    def close(self) -> None:
        return None

    def read(self) -> np.ndarray:
        if self._period > 0:
            time.sleep(self._period)
        return self._frame.copy()

    def measure_fps(self, *, apply: bool = False) -> float:
        if apply:
            self.capture_fps = 30.0
            self._period = 1.0 / self.capture_fps
        return self.capture_fps


class _DeferredEventStub:
    """Armed stub: ready_to_evaluate when set; evaluate returns the fixed event."""

    def __init__(self) -> None:
        self._event = None

    @property
    def needs_detection(self) -> bool:
        return False

    @property
    def ready_to_evaluate(self) -> bool:
        return self._event is not None

    def arm(self, event) -> None:
        self._event = event

    def clear(self) -> None:
        self._event = None

    def observe(self, pre_buffer, *, now=None) -> None:
        return None

    def evaluate(self):
        event = self._event
        self._event = None
        return event


def _configure_import_path() -> None:
    for path in (MAIN_DIR, EDGE_DIR, INTEGRATION_DIR):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


def _pre_buffer_time_span(pre_buffer) -> float:
    records = pre_buffer._records
    if len(records) < 2:
        return 0.0
    return records[-1][0] - records[0][0]


def _pre_roll_window_full(pre_buffer) -> bool:
    if len(pre_buffer) == 0:
        return False
    config = pre_buffer._recording_manager_config
    if config is None:
        return False
    span_seconds = _pre_buffer_time_span(pre_buffer)
    return span_seconds >= config.pre_roll_seconds * config.coverage_tolerance


def _post_roll_lap_budget(capture_fps: float) -> int:
    return max(1, math.ceil(POST_ROLL_SECONDS * capture_fps - 1e-9) + 30)


def _clip_files(clips_dir: Path) -> set[Path]:
    if not clips_dir.is_dir():
        return set()
    return {path.resolve() for path in clips_dir.rglob("*.mp4")}


def _apply_test_config(
    app_config,
    *,
    repo_root: Path,
    resolve_runtime_paths: Callable,
    clips_dir: Path,
):
    app_config = resolve_runtime_paths(app_config, repo_root)
    recording = app_config.recording_manager
    buzzer = app_config.buzzer
    app_config = replace(
        app_config,
        recording_manager=replace(
            recording,
            pre_roll_seconds=PRE_ROLL_SECONDS,
            post_roll_seconds=POST_ROLL_SECONDS,
            record_safe_events=False,
            clips_dir=clips_dir,
        ),
        buzzer=replace(
            buzzer,
            play_on=replace(buzzer.play_on, unsafe=True, safe=False),
        ),
    )
    if not PREVIEW_ENABLED:
        app_config = replace(
            app_config,
            preview=replace(app_config.preview, enabled=False),
        )
    return app_config


def _stub_rolling_stop(DrivingEvent, StopSignEnum, ApproachSnapshot):
    return DrivingEvent(
        type=StopSignEnum.ROLLING_STOP,
        knn_stage1=(0.4, 0.12, 0.9, 0.08),
        knn_stage2=(0.12, 4.2),
        approach=ApproachSnapshot(
            peak_area_pct=1.1,
            approach_duration_s=1.8,
            increasing_fraction=0.7,
            log_linear_r2=0.85,
            drop_duration_s=0.4,
            post_drop_holds=False,
            fail_reasons=(),
        ),
    )


def _inspect_uploaded_clip(session_id: int) -> tuple[int, str]:
    from sqlmodel import select

    from db.database import get_session
    from db.models import Clip, Event

    with get_session() as local:
        event = local.exec(
            select(Event)
            .where(Event.driving_session_id == session_id)
            .order_by(Event.id.desc())
        ).first()
        if event is None or event.id is None:
            raise RuntimeError("RecordingManager did not persist an event")
        clip = local.exec(select(Clip).where(Clip.event_id == event.id)).first()
        if clip is None:
            raise RuntimeError(f"clip missing for event {event.id}")
        if clip.s3_stored is not True or not clip.s3_key:
            raise RuntimeError(
                f"clip {clip.id} not uploaded "
                f"(s3_stored={clip.s3_stored!r} s3_key={clip.s3_key!r})"
            )
        return event.id, clip.s3_key


def main() -> int:
    _configure_import_path()
    from config.loader import AppConfig, ConfigError
    from main import DEFAULT_CONFIG_DIR, REPO_ROOT, _resolve_runtime_paths
    from netrapi import build_pipeline
    from netrapi.backend_auth import apply_edge_env, clear_ingest_auth
    from netrapi.events import DrivingEvent, StopSignEnum
    from netrapi.events.driving_event import ApproachSnapshot
    from netrapi.exceptions import NetraPiError

    from _render import api_origin, init_sqlite, sqlite_url, wait_health

    config_dir = DEFAULT_CONFIG_DIR.resolve()
    print("AT-7.1: Mocked Pi pipeline → deployed cloud", flush=True)
    print("  camera + EventManager: mocked", flush=True)
    print("  persist + ingest: RecordingManager / LocalStore / CloudIngest", flush=True)

    try:
        apply_edge_env()
        clear_ingest_auth()
        origin = api_origin()
        print(f"  origin: {origin}", flush=True)
        wait_health(origin)

        base_config = AppConfig.load(config_dir)
        resolved = _resolve_runtime_paths(base_config, REPO_ROOT)
        clips_dir = (resolved.recording_manager.clips_dir / CLIPS_SUBDIR).resolve()
        clips_dir.mkdir(parents=True, exist_ok=True)
        clips_before = _clip_files(clips_dir)

        if OUTPUT_DB_PATH.exists():
            OUTPUT_DB_PATH.unlink()
        url = sqlite_url(OUTPUT_DB_PATH)
        os.environ["DATABASE_URL"] = url
        init_sqlite(url)
        print(f"  sqlite: {OUTPUT_DB_PATH}", flush=True)
        print(f"  clips_dir: {clips_dir}", flush=True)

        app_config = _apply_test_config(
            base_config,
            repo_root=REPO_ROOT,
            resolve_runtime_paths=_resolve_runtime_paths,
            clips_dir=clips_dir,
        )
        pipeline = build_pipeline(app_config)
        manager = pipeline.manager
        if manager._local_store is None:
            raise RuntimeError("LocalStore not wired; init_engine must run before build_pipeline")
        if manager._cloud_ingest is None:
            raise RuntimeError(
                "CloudIngest not wired; set NETRAPI_API_URL and NETRAPI_API_KEY in "
                "src/main/edge/.env"
            )

        cam = app_config.camera
        frame = np.zeros((cam.height, cam.width, cam.channels), dtype=np.uint8)
        manager._camera = _FakeCamera(frame, capture_fps=float(cam.recommended_fps))
        stub = _DeferredEventStub()
        manager._event_manager = stub
        event = _stub_rolling_stop(DrivingEvent, StopSignEnum, ApproachSnapshot)

        manager._buzzer.open()
        if not manager._buzzer.available:
            raise RuntimeError(
                "Buzzer GPIO unavailable (RPi.GPIO / rpi-lgpio missing or pin busy)."
            )

        post_lap_budget = _post_roll_lap_budget(float(cam.recommended_fps))
        max_laps = PRE_FILL_LAP_BUDGET + post_lap_budget + 60
        phase = "prefill"
        idle_laps = 0

        def should_stop() -> bool:
            nonlocal phase, idle_laps
            if _clip_files(clips_dir) - clips_before:
                return True
            if phase == "prefill":
                idle_laps += 1
                if idle_laps > PRE_FILL_LAP_BUDGET:
                    return True
                if _pre_roll_window_full(manager.pre_buffer):
                    print(
                        f"  Arming ROLLING_STOP after {idle_laps} idle lap(s) ...",
                        flush=True,
                    )
                    stub.arm(event)
                    phase = "armed"
                return False
            if phase == "armed":
                if manager.clip_active:
                    phase = "post"
                return False
            if phase == "post":
                return not manager.clip_active
            return True

        manager.run_loop(
            max_laps=max_laps,
            should_stop=should_stop,
            full_record=FULL_RECORD,
        )

        new_clips = _clip_files(clips_dir) - clips_before
        if len(new_clips) != 1:
            names = ", ".join(path.name for path in sorted(new_clips))
            raise RuntimeError(f"expected 1 new clip, got {len(new_clips)}: {names}")
        clip_path = next(iter(new_clips))
        session_id = manager._driving_session_id
        if session_id is None:
            raise RuntimeError("driving_session_id missing after run_loop")
        event_id, s3_key = _inspect_uploaded_clip(session_id)
        print(f"  clip: {clip_path}", flush=True)
        print(f"  sqlite/postgres event {event_id} -> {s3_key}", flush=True)
        clear_ingest_auth()
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1
    except NetraPiError as exc:
        print(f"NetraPi error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print("PASS: stubbed rolling-stop persisted and uploaded via RecordingManager")
    print(f"  inspect sqlite: {OUTPUT_DB_PATH}")
    print("  inspect Postgres/S3/Render: see README")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
