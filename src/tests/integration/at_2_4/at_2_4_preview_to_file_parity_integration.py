"""
AT-2.4: Deterministic preview-to-file parity (integration).

Stamps each ``display`` frame with a deterministic solid marker block, captures
frames shown via ``PreviewUI.show``, saves one event clip, and compares marker
blocks in preview captures vs the written MP4 (lossy ``mp4v`` needs a block, not
a single pixel).

Usage (from repo root, Pi edge venv with camera + display for preview):

    python src/tests/integration/at_2_4/at_2_4_preview_to_file_parity_integration.py
"""

from __future__ import annotations

import math
import sys
from dataclasses import replace
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
EDGE_DIR = SCRIPT_DIR.parents[2] / "main" / "edge"

PRE_ROLL_SECONDS = 2.0
POST_ROLL_SECONDS = 2.0
PRE_FILL_LAP_BUDGET = 150
VERIFY_TPU = True
FULL_RECORD = False
MARKER_LAP_LIMIT = 8
MARKER_BLOCK_SIZE = 32
MARKER_PIXEL_TOLERANCE = 8


def _configure_import_path() -> None:
    edge_str = str(EDGE_DIR)
    if edge_str not in sys.path:
        sys.path.insert(0, edge_str)


def _clip_files(clips_dir: Path) -> set[Path]:
    if not clips_dir.is_dir():
        return set()
    return {path.resolve() for path in clips_dir.glob("clip_*.mp4")}


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
    return _pre_buffer_time_span(pre_buffer) >= config.pre_roll_seconds * config.coverage_tolerance


def _apply_test_config(app_config, *, repo_root: Path, resolve_runtime_paths):
    app_config = resolve_runtime_paths(app_config, repo_root)
    recording = app_config.recording_manager
    return replace(
        app_config,
        preview=replace(app_config.preview, enabled=True),
        recording_manager=replace(
            recording,
            pre_roll_seconds=PRE_ROLL_SECONDS,
            post_roll_seconds=POST_ROLL_SECONDS,
        ),
    )


def _post_roll_lap_budget(capture_fps: float) -> int:
    return max(1, math.ceil(POST_ROLL_SECONDS * capture_fps - 1e-9))


def _marker_for_lap(lap_index: int) -> tuple[int, int, int]:
    return (lap_index % 256, (lap_index // 256) % 256, (lap_index // 65536) % 256)


def _stamp_display(display, lap_index: int):
    import numpy as np

    stamped = np.asarray(display).copy()
    color = np.array(_marker_for_lap(lap_index), dtype=stamped.dtype)
    height = min(MARKER_BLOCK_SIZE, stamped.shape[0])
    width = min(MARKER_BLOCK_SIZE, stamped.shape[1])
    stamped[0:height, 0:width, :] = color
    return stamped


def _read_marker_from_frame(frame) -> tuple[int, int, int]:
    import numpy as np

    block = np.asarray(frame)[0:MARKER_BLOCK_SIZE, 0:MARKER_BLOCK_SIZE]
    median = np.median(block.reshape(-1, 3), axis=0)
    return (int(median[0]), int(median[1]), int(median[2]))


def _markers_match(
    preview: tuple[int, int, int],
    mp4: tuple[int, int, int],
    *,
    tolerance: int,
) -> bool:
    return all(abs(p - m) <= tolerance for p, m in zip(preview, mp4))


def _read_mp4_markers(path: Path, *, max_frames: int) -> list[tuple[int, int, int]]:
    import cv2

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"unable to open MP4: {path}")

    markers: list[tuple[int, int, int]] = []
    try:
        for _ in range(max_frames):
            ok, frame = capture.read()
            if not ok or frame is None:
                break
            markers.append(_read_marker_from_frame(frame))
    finally:
        capture.release()
    return markers


def _install_marker_hooks(manager, *, preview_frames: list) -> None:
    lap_counter = {"n": 0}
    original_prepare = manager._prepare_display
    original_show = manager._preview.show

    def _prepare_with_marker(frame):
        display = original_prepare(frame)
        if not manager.clip_active:
            return display
        stamped = _stamp_display(display, lap_counter["n"])
        lap_counter["n"] += 1
        return stamped

    def _show_and_capture(frame):
        original_show(frame)
        if manager._preview.enabled and manager.clip_active:
            preview_frames.append(_read_marker_from_frame(frame))

    manager._prepare_display = _prepare_with_marker  # type: ignore[method-assign]
    manager._preview.show = _show_and_capture  # type: ignore[method-assign]


def main() -> int:
    _configure_import_path()
    from config.loader import AppConfig, ConfigError
    from main import DEFAULT_CONFIG_DIR, REPO_ROOT, _resolve_runtime_paths
    from netrapi import build_pipeline
    from netrapi.exceptions import NetraPiError

    config_dir = DEFAULT_CONFIG_DIR.resolve()

    try:
        app_config = AppConfig.load(config_dir)
        app_config = _apply_test_config(
            app_config,
            repo_root=REPO_ROOT,
            resolve_runtime_paths=_resolve_runtime_paths,
        )
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1

    clips_dir = app_config.recording_manager.clips_dir
    clips_before = _clip_files(clips_dir)
    preview_markers: list[tuple[int, int, int]] = []
    phase = "prefill"
    idle_laps = 0
    pre_frame_count_at_trigger = 0

    print("AT-2.4: Deterministic preview-to-file parity")
    print(f"  config_dir: {config_dir}")
    print(f"  clips_dir: {clips_dir}")
    print(f"  preview window: {app_config.preview.window_name!r}")
    print(f"  marker_lap_limit: {MARKER_LAP_LIMIT}")

    try:
        pipeline = build_pipeline(app_config, verify_tpu=VERIFY_TPU)
        manager = pipeline.manager
        _install_marker_hooks(manager, preview_frames=preview_markers)

        post_lap_budget = _post_roll_lap_budget(float(app_config.camera.recommended_fps))
        max_laps = PRE_FILL_LAP_BUDGET + post_lap_budget + 60

        def should_stop() -> bool:
            nonlocal phase, idle_laps, pre_frame_count_at_trigger
            if _clip_files(clips_dir) - clips_before:
                return True
            if phase == "prefill":
                idle_laps += 1
                if idle_laps > PRE_FILL_LAP_BUDGET:
                    return True
                if _pre_roll_window_full(manager.pre_buffer):
                    print(f"\n  begin_clip() after {idle_laps} idle lap(s) ...")
                    manager.begin_clip()
                    pre_frame_count_at_trigger = len(manager.pre_buffer)
                    phase = "post"
                return False
            if phase == "post" and not manager.clip_active:
                return True
            return False

        print("\nRunning clip cycle with stamped display frames ...")
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
        mp4_markers = _read_mp4_markers(clip_path, max_frames=5000)
        if pre_frame_count_at_trigger > len(mp4_markers):
            raise RuntimeError(
                f"pre-roll frame count ({pre_frame_count_at_trigger}) exceeds MP4 length "
                f"({len(mp4_markers)})"
            )
        post_mp4_markers = mp4_markers[pre_frame_count_at_trigger:]
        if len(post_mp4_markers) != len(preview_markers):
            raise RuntimeError(
                "post-roll frame count mismatch between preview and MP4: "
                f"preview={len(preview_markers)}, mp4_post={len(post_mp4_markers)}, "
                f"pre_frames={pre_frame_count_at_trigger}, mp4_total={len(mp4_markers)}"
            )

        compare_count = min(len(preview_markers), MARKER_LAP_LIMIT)
        if compare_count < 3:
            raise RuntimeError(
                f"insufficient post-roll marker frames for comparison "
                f"(preview={len(preview_markers)}, mp4_post={len(post_mp4_markers)})"
            )

        mismatches = []
        for index in range(compare_count):
            preview = preview_markers[index]
            mp4 = post_mp4_markers[index]
            if not _markers_match(preview, mp4, tolerance=MARKER_PIXEL_TOLERANCE):
                mismatches.append(
                    f"post lap {index}: preview={preview} mp4={mp4}"
                )

        print("\nResults:")
        print(f"  camera recommended_fps: {app_config.camera.recommended_fps:.2f}")
        print(f"  pre-roll frames at trigger: {pre_frame_count_at_trigger}")
        print(f"  preview marker frames: {len(preview_markers)}")
        print(f"  mp4 marker frames read: {len(mp4_markers)}")
        print(f"  mp4 post-roll markers compared: {compare_count}")
        print(f"  clip_path: {clip_path}")

        if mismatches:
            detail = "; ".join(mismatches[:5])
            raise RuntimeError(f"preview/MP4 marker mismatch: {detail}")
    except NetraPiError as exc:
        print(f"NetraPi error: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 1

    print("\nAT-2.4: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
