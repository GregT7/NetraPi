from __future__ import annotations

from pathlib import Path

from sqlmodel import select

from db.database import get_session
from db.models import Clip, TripSegment
from netrapi.cloud_ingest import CloudIngest
from netrapi.exceptions import CloudIngestError
from netrapi.recording.playback_json import SIDECAR_NAMES


def _remove_file(path: str | None) -> bool:
    if not path:
        return True
    file = Path(path)
    if not file.is_file():
        return True
    try:
        file.unlink()
    except OSError as exc:
        print(f"[cleanup] could not delete {file}: {exc}", flush=True)
        return False
    return True


def _remove_empty_dir(path: Path) -> bool:
    try:
        next(path.iterdir())
    except StopIteration:
        pass
    except OSError as exc:
        print(f"[cleanup] could not inspect {path}: {exc}", flush=True)
        return False
    else:
        return False
    try:
        path.rmdir()
    except OSError as exc:
        print(f"[cleanup] could not delete empty dir {path}: {exc}", flush=True)
        return False
    print(f"[cleanup] empty dir removed ({path})", flush=True)
    return True


def _prune_empty_dirs(directory: Path | None) -> int:
    if directory is None or not directory.is_dir():
        return 0
    nested = [path for path in directory.rglob("*") if path.is_dir()]
    removed = 0
    for path in sorted(nested, key=lambda item: len(item.parts), reverse=True):
        if _remove_empty_dir(path):
            removed += 1
    return removed


def _remove_local(path: str | None) -> bool:
    if not path:
        return True
    file = Path(path)
    if file.name == "clip.mp4":
        parent = file.parent
        for name in SIDECAR_NAMES:
            sidecar = parent / name
            if sidecar.is_file() and not _remove_file(str(sidecar)):
                return False
        if not _remove_file(str(file)):
            return False
        if parent.name.startswith("clip_"):
            _remove_empty_dir(parent)
        return True
    return _remove_file(path)


def _finished(row: Clip | TripSegment) -> bool:
    return row.init_local_stored is True


def _uploaded(row: Clip | TripSegment) -> bool:
    return row.s3_stored is True and bool(row.s3_key)


def _cleanup_row(
    ingest: CloudIngest,
    *,
    kind: str,
    row_id: int,
    local_path: str | None,
) -> bool:
    if not _remove_local(local_path):
        return False
    try:
        if kind == "clip":
            ingest.confirm_local_delete(clip_id=row_id)
        else:
            ingest.confirm_local_delete(trip_segment_id=row_id)
    except CloudIngestError as exc:
        detail = str(exc)
        if "404" not in detail:
            print(f"[cleanup] {kind} {row_id} cloud flag failed: {exc}", flush=True)
            return False
        print(
            f"[cleanup] {kind} {row_id} not in cloud; marking local only",
            flush=True,
        )
    model = Clip if kind == "clip" else TripSegment
    with get_session() as session:
        row = session.get(model, row_id)
        if row is None:
            print(f"[cleanup] {kind} {row_id} missing after delete", flush=True)
            return False
        row.init_local_deleted = True
        row.local_path = None
        session.add(row)
        session.commit()
    print(f"[cleanup] {kind} {row_id} local file removed", flush=True)
    return True


def _iter_media(
    uploaded_only: bool, *, target: str = "both"
) -> list[tuple[str, int, str | None]]:
    if target not in {"clips", "trips", "both"}:
        raise ValueError(f"invalid cleanup target: {target}")
    include_clips = target in {"clips", "both"}
    include_trips = target in {"trips", "both"}
    refs: list[tuple[str, int, str | None]] = []
    with get_session() as session:
        clips = session.exec(select(Clip).order_by(Clip.id)).all() if include_clips else []
        trips = (
            session.exec(select(TripSegment).order_by(TripSegment.id)).all()
            if include_trips
            else []
        )
    for row in clips:
        if row.id is None or not _finished(row):
            continue
        if uploaded_only and not _uploaded(row):
            continue
        if row.init_local_deleted is True and not (
            row.local_path and Path(row.local_path).is_file()
        ):
            continue
        refs.append(("clip", row.id, row.local_path))
    for row in trips:
        if row.id is None or not _finished(row):
            continue
        if uploaded_only and not _uploaded(row):
            continue
        if row.init_local_deleted is True and not (
            row.local_path and Path(row.local_path).is_file()
        ):
            continue
        refs.append(("trip", row.id, row.local_path))
    return refs


def delete_uploaded_local_media(
    ingest: CloudIngest,
    *,
    target: str = "both",
    clips_dir: Path | None = None,
    trips_dir: Path | None = None,
) -> int:
    """Delete local clip/trip MP4s that are already in S3. Does not delete S3 objects."""
    cleaned = 0
    for kind, row_id, local_path in _iter_media(uploaded_only=True, target=target):
        if _cleanup_row(ingest, kind=kind, row_id=row_id, local_path=local_path):
            cleaned += 1
    if target in {"clips", "both"}:
        _prune_empty_dirs(clips_dir)
    if target in {"trips", "both"}:
        _prune_empty_dirs(trips_dir)
    return cleaned


def _sweep_orphans(directory: Path | None, keep: set[Path]) -> int:
    if directory is None or not directory.is_dir():
        return 0
    removed = 0
    candidates = list(directory.glob("*.mp4")) + list(directory.glob("*/clip.mp4"))
    for path in sorted({item.resolve() for item in candidates}):
        if path in keep:
            continue
        if _remove_local(str(path)):
            print(f"[cleanup] orphan removed ({path})", flush=True)
            removed += 1
    return removed


def delete_all_local_media(
    ingest: CloudIngest,
    *,
    clips_dir: Path | None = None,
    trips_dir: Path | None = None,
) -> int:
    """Delete all finished local clip/trip MP4s. Does not delete S3 objects."""
    keep: set[Path] = set()
    with get_session() as session:
        rows = list(session.exec(select(Clip)).all()) + list(
            session.exec(select(TripSegment)).all()
        )
        for row in rows:
            if row.init_local_stored is not True and row.local_path:
                keep.add(Path(row.local_path).resolve())
    cleaned = 0
    for kind, row_id, local_path in _iter_media(uploaded_only=False):
        if _cleanup_row(ingest, kind=kind, row_id=row_id, local_path=local_path):
            cleaned += 1
    cleaned += _sweep_orphans(clips_dir, keep)
    cleaned += _sweep_orphans(trips_dir, keep)
    _prune_empty_dirs(clips_dir)
    _prune_empty_dirs(trips_dir)
    return cleaned
