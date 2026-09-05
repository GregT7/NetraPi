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
        trip_recorder=replace(
            app_config.trip_recorder,
            segments_dir=resolve(app_config.trip_recorder.segments_dir),
            logs_dir=resolve(app_config.trip_recorder.logs_dir),
        ),
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
        "--full-record",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable segmented full-trip recording (default: config value)",
    )
    jobs = parser.add_mutually_exclusive_group()
    jobs.add_argument(
        "--drain-trips",
        choices=["clips", "trips", "both"],
        help="Upload pending clips, trip segments, or both (Wi-Fi). Does not run capture.",
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
    parser.add_argument(
        "--delete-after-drain",
        choices=["clips", "trips", "both"],
        default=None,
        help=(
            "After a successful --drain-trips, delete local MP4s already in S3 "
            "(clips, trips, or both). Does not delete S3 objects."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    _configure_import_path()
    from config.loader import AppConfig, ConfigError
    from db.database import DatabaseUrlError, ensure_sqlite_schema
    from netrapi import build_pipeline
    from netrapi.backend_auth import apply_edge_env
    from netrapi.exceptions import NetraPiError

    args = parse_args(argv)
    if args.delete_after_drain and not args.drain_trips:
        print("--delete-after-drain requires --drain-trips", file=sys.stderr)
        return 1
    try:
        apply_edge_env()
        if args.drain_trips or args.delete_uploaded_local or args.delete_all_local:
            from netrapi.cloud_ingest import try_cloud_ingest

            ensure_sqlite_schema()
            ingest = try_cloud_ingest()
            if ingest is None:
                print(
                    "NETRAPI_API_URL / NETRAPI_API_KEY missing; cannot run maintenance",
                    file=sys.stderr,
                )
                return 1
            if args.drain_trips:
                from config.loader import AppConfig
                from netrapi.health import wake_render

                app_config = AppConfig.load(DEFAULT_CONFIG_DIR.resolve())
                print(
                    f"[drain] target={args.drain_trips}; waking Render via GET /health ...",
                    flush=True,
                )
                if not wake_render(app_config):
                    print("Render GET /health failed; drain aborted", file=sys.stderr)
                    return 1
                print("[drain] Render is up", flush=True)
                if args.drain_trips in ("clips", "both"):
                    clips = ingest.drain_clips()
                    print(f"[drain] finished clips: uploaded {clips}", flush=True)
                if args.drain_trips in ("trips", "both"):
                    trips = ingest.drain_trip_segments()
                    print(f"[drain] finished trips: uploaded {trips}", flush=True)
                if args.delete_after_drain:
                    from netrapi.local_cleanup import delete_uploaded_local_media

                    print(
                        f"[drain] delete-after-drain target={args.delete_after_drain}",
                        flush=True,
                    )
                    cleaned = delete_uploaded_local_media(
                        ingest, target=args.delete_after_drain
                    )
                    print(f"[drain] deleted {cleaned} uploaded local file(s)", flush=True)
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
        ensure_sqlite_schema()
        from netrapi.health import KeepAlive, run_boot_health

        health = run_boot_health(app_config)
        if health.abort:
            print("Boot health failed: Coral TPU is required. Exiting.", file=sys.stderr)
            return 1
        pipeline = build_pipeline(
            app_config,
            cloud_enabled=health.mode == "online",
            detector=health.detector,
        )
        pipeline.manager.set_boot_issues(health.persist_messages)
        keepalive = None
        if health.mode == "online":
            keepalive = KeepAlive(
                app_config.health,
                on_give_up=pipeline.manager.disable_cloud,
            )
            keepalive.start()
        run_kwargs = {}
        if args.full_record is not None:
            run_kwargs["full_record"] = args.full_record
        try:
            pipeline.run(**run_kwargs)
        finally:
            if keepalive is not None:
                keepalive.stop()
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1
    except DatabaseUrlError as exc:
        print(f"Database error: {exc}", file=sys.stderr)
        return 1
    except NetraPiError as exc:
        print(f"Pipeline error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
