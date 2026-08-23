"""NetraPi edge entry point: load config, build pipeline, run until stopped."""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

EDGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = EDGE_DIR.parents[2]
DEFAULT_CONFIG_DIR = EDGE_DIR / "config"


def _configure_import_path() -> None:
    main_str = str(EDGE_DIR.parent)
    edge_str = str(EDGE_DIR)
    if main_str not in sys.path:
        sys.path.insert(0, main_str)
    if edge_str not in sys.path:
        sys.path.insert(0, edge_str)


def _resolve_runtime_paths(app_config, repo_root: Path):
    recording_manager = app_config.recording_manager
    detector = app_config.detector
    knn = app_config.knn

    def resolve(path: Path) -> Path:
        return path.resolve() if path.is_absolute() else (repo_root / path).resolve()

    return replace(
        app_config,
        recording_manager=replace(recording_manager, clips_dir=resolve(recording_manager.clips_dir)),
        trip_recorder=replace(app_config.trip_recorder, segments_dir=resolve(app_config.trip_recorder.segments_dir)),
        detector=replace(
            detector,
            model_path=resolve(detector.model_path),
            labels_path=resolve(detector.labels_path),
        ),
        knn=replace(
            knn,
            stage1_model_path=resolve(knn.stage1_model_path),
            stage2_model_path=resolve(knn.stage2_model_path),
        ),
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the NetraPi edge capture and clip pipeline.")
    parser.add_argument(
        "--verify-tpu",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Load detector and verify Edge TPU before run (default: enabled)",
    )
    parser.add_argument(
        "--max-laps",
        type=int,
        default=None,
        help="Stop after N loop iterations (omit for continuous run)",
    )
    parser.add_argument(
        "--full-record",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable segmented full-trip recording (default: config value)",
    )
    jobs = parser.add_mutually_exclusive_group()
    jobs.add_argument(
        "--drain-trips",
        action="store_true",
        help="Upload pending trip segments to S3 (Wi-Fi). Does not run capture.",
    )
    jobs.add_argument(
        "--delete-uploaded-local",
        action="store_true",
        help=(
            "Delete local clip/trip MP4s already stored in S3. "
            "Updates SQLite and cloud flags. Does not delete S3 objects."
        ),
    )
    jobs.add_argument(
        "--delete-all-local",
        action="store_true",
        help=(
            "Delete all finished local clip/trip MP4s. "
            "Updates SQLite and cloud flags. Does not delete S3 objects."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    _configure_import_path()
    from config.loader import AppConfig, ConfigError
    from db.database import init_engine
    from netrapi import build_pipeline
    from netrapi.backend_auth import apply_edge_env
    from netrapi.exceptions import NetraPiError

    args = parse_args(argv)
    try:
        apply_edge_env()
        if args.drain_trips or args.delete_uploaded_local or args.delete_all_local:
            from netrapi.cloud_ingest import try_cloud_ingest

            init_engine()
            ingest = try_cloud_ingest()
            if ingest is None:
                print(
                    "NETRAPI_API_URL / NETRAPI_API_KEY missing; cannot run maintenance",
                    file=sys.stderr,
                )
                return 1
            if args.drain_trips:
                uploaded = ingest.drain_trip_segments()
                print(f"drained {uploaded} trip segment(s)")
                return 0
            if args.delete_uploaded_local:
                from netrapi.local_cleanup import delete_uploaded_local_media

                cleaned = delete_uploaded_local_media(ingest)
                print(f"deleted {cleaned} uploaded local file(s)")
                return 0
            app_config = AppConfig.load(DEFAULT_CONFIG_DIR.resolve())
            app_config = _resolve_runtime_paths(app_config, REPO_ROOT)
            from netrapi.local_cleanup import delete_all_local_media

            cleaned = delete_all_local_media(
                ingest,
                clips_dir=app_config.recording_manager.clips_dir,
                trips_dir=app_config.trip_recorder.segments_dir,
            )
            print(f"deleted {cleaned} local file(s)")
            return 0
        app_config = AppConfig.load(DEFAULT_CONFIG_DIR.resolve())
        app_config = _resolve_runtime_paths(app_config, REPO_ROOT)
        init_engine()
        pipeline = build_pipeline(app_config, verify_tpu=args.verify_tpu)
        run_kwargs = {}
        if args.max_laps is not None:
            run_kwargs["max_laps"] = args.max_laps
        if args.full_record is not None:
            run_kwargs["full_record"] = args.full_record
        pipeline.run(**run_kwargs)
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1
    except NetraPiError as exc:
        print(f"Pipeline error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
