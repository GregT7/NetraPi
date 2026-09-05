from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Optional
from urllib.parse import urljoin

from sqlmodel import select

from db.config_snapshot import payload_from_db
from db.database import get_session
from db.models import (
    ApproachFailReason,
    ApproachParameters,
    AutoClassification,
    Classification,
    ClassificationType,
    Clip,
    DrivingSession,
    Event,
    EventTripLocation,
    KnnParameter,
    OperationalException,
    TripSegment,
)
from netrapi.backend_auth import ingest_api_url, ingest_headers, load_ingest_auth
from netrapi.exceptions import CloudIngestError, IngestAuthError

# Optional[...] (not X | None): this alias is evaluated at import time on Python 3.9.
JsonRequest = Callable[[str, str, Optional[dict[str, Any]]], dict[str, Any]]
PutFile = Callable[[str, Path, str], None]

JSON_TIMEOUT_S = 30.0
PUT_TIMEOUT_S = 600.0
PUT_PROGRESS_EVERY_BYTES = 5 * 1024 * 1024
PUT_PROGRESS_EVERY_S = 15.0
CLIP_CONTENT_TYPE = "video/mp4"
JSON_CONTENT_TYPE = "application/json"
UPLOAD_DONE_SEPARATOR = "-" * 72


def _iso(value: datetime) -> str:
    text = value.isoformat()
    if value.tzinfo is None:
        if not text.endswith("Z"):
            return text + "Z"
        return text
    return text.replace("+00:00", "Z")


def _format_mb(num_bytes: int) -> str:
    return f"{num_bytes / (1024 * 1024):.1f}"


def _format_mbps(num_bytes: int, elapsed_s: float) -> str:
    if elapsed_s <= 0:
        return "—"
    return f"{(num_bytes * 8) / (elapsed_s * 1_000_000):.2f}"


class _ProgressReader:
    """File-like wrapper that reports PUT upload progress via on_progress."""

    def __init__(
        self,
        fh: BinaryIO,
        *,
        size: int,
        label: str,
        on_progress: Callable[[str], None] | None,
        log_every_bytes: int = PUT_PROGRESS_EVERY_BYTES,
        log_every_s: float = PUT_PROGRESS_EVERY_S,
    ) -> None:
        self._fh = fh
        self._size = size
        self._label = label
        self._on_progress = on_progress
        self._sent = 0
        self._last_log_bytes = 0
        self._started = time.monotonic()
        self._last_log_at = self._started
        self._log_every_bytes = max(1, log_every_bytes)
        self._log_every_s = max(1.0, log_every_s)

    def read(self, size: int = -1) -> bytes:
        chunk = self._fh.read(size)
        if chunk:
            self._sent += len(chunk)
            self._maybe_log(force=self._sent >= self._size)
        return chunk

    def __len__(self) -> int:
        return self._size

    def _maybe_log(self, *, force: bool = False) -> None:
        if self._on_progress is None:
            return
        now = time.monotonic()
        bytes_due = self._sent - self._last_log_bytes >= self._log_every_bytes
        time_due = now - self._last_log_at >= self._log_every_s
        if not force and not bytes_due and not time_due:
            return
        elapsed = max(now - self._started, 1e-6)
        pct = (100.0 * self._sent / self._size) if self._size else 100.0
        self._on_progress(
            f"[ingest] PUT progress {self._label}: "
            f"{_format_mb(self._sent)}/{_format_mb(self._size)} MB "
            f"({pct:.0f}%) {_format_mbps(self._sent, elapsed)} Mbps "
            f"elapsed={elapsed:.0f}s"
        )
        self._last_log_bytes = self._sent
        self._last_log_at = now


def _http_json(method: str, url: str, body: dict[str, Any] | None) -> dict[str, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {
        **ingest_headers(),
        "Accept": "application/json",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=JSON_TIMEOUT_S) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise CloudIngestError(f"{method} {url} -> {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise CloudIngestError(f"{method} {url} failed: {exc}") from exc
    if not raw:
        return {}
    parsed = json.loads(raw.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise CloudIngestError(f"{method} {url} returned a non-object JSON body")
    return parsed


def _http_put_file(
    url: str,
    path: Path,
    content_type: str,
    *,
    on_progress: Callable[[str], None] | None = None,
    timeout_s: float = PUT_TIMEOUT_S,
) -> None:
    size = path.stat().st_size
    label = path.name
    started = time.monotonic()
    if on_progress is not None:
        on_progress(
            f"[ingest] PUT start {label}: {_format_mb(size)} MB "
            f"({size} bytes), streaming, timeout={timeout_s:.0f}s"
        )
    with path.open("rb") as fh:
        body = _ProgressReader(
            fh,
            size=size,
            label=label,
            on_progress=on_progress,
        )
        request = urllib.request.Request(
            url,
            data=body,
            method="PUT",
            headers={
                "Content-Type": content_type,
                "Content-Length": str(size),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                status = getattr(response, "status", 200)
                if status not in {200, 204}:
                    raise CloudIngestError(f"PUT {url} -> {status}")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise CloudIngestError(f"PUT -> {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise CloudIngestError(f"PUT failed: {exc}") from exc
    elapsed = max(time.monotonic() - started, 1e-6)
    if on_progress is not None:
        on_progress(
            f"[ingest] PUT done {label}: {_format_mb(size)} MB in {elapsed:.0f}s "
            f"({_format_mbps(size, elapsed)} Mbps avg)"
        )


class CloudIngest:
    """POST local SQLite rows to FastAPI; PUT media via presigned URL.

    `sync_session` POSTs `master-config` first so `driving_session.master_config_id`
    exists. Event metadata POSTs on evaluate (`sync_event`); clip bytes PUT when a
    local clip row exists with a file path. Trip segments are JSON-primed only then
    (`sync_trip_segment`); `upload_trip_segment` / `drain_trip_segments` PUT them
    later on Wi-Fi. After confirm, writes `s3_key` / `s3_stored` on the matching
    local clip or trip_segment row.
    """

    def __init__(
        self,
        *,
        json_request: JsonRequest | None = None,
        put_file: PutFile | None = None,
        put_bytes: PutFile | None = None,
        on_log: Callable[[str], None] | None = None,
    ) -> None:
        self._json_request = json_request or self._json_request_http
        # put_bytes kept as a deprecated alias for put_file (tests / call sites).
        self._put_file = put_file or put_bytes
        self._on_log = on_log

    def set_log(self, on_log: Callable[[str], None] | None) -> None:
        self._on_log = on_log

    def _emit(self, message: str) -> None:
        if self._on_log is not None:
            self._on_log(message)
        else:
            print(message, flush=True)

    def _emit_upload_separator(self) -> None:
        self._emit(UPLOAD_DONE_SEPARATOR)

    def _put_path(self, url: str, path: Path, content_type: str) -> None:
        """Stream a local file to a presigned PUT URL (or call injected put_file)."""
        if self._put_file is not None:
            self._put_file(url, path, content_type)
            return
        _http_put_file(
            url,
            path,
            content_type,
            on_progress=self._emit,
            timeout_s=PUT_TIMEOUT_S,
        )

    def _json_request_http(
        self, method: str, path: str, body: dict[str, Any] | None
    ) -> dict[str, Any]:
        url = urljoin(ingest_api_url() + "/", path.lstrip("/"))
        return _http_json(method, url, body)

    def sync_master_config(self, master_config_id: int) -> None:
        with get_session() as session:
            payload = payload_from_db(session, master_config_id)
        self._json_request("POST", "/api/netrapi/master-config", payload)

    def sync_session(self, session_id: int) -> None:
        with get_session() as session:
            row = session.get(DrivingSession, session_id)
            if row is None:
                raise CloudIngestError(f"driving_session {session_id} not in local SQLite")
            master_config_id = row.master_config_id
            payload = {
                "id": row.id,
                "master_config_id": row.master_config_id,
                "start_time": _iso(row.start_time),
            }
            if row.end_time is not None:
                payload["end_time"] = _iso(row.end_time)
        self.sync_master_config(master_config_id)
        self._json_request("POST", "/api/netrapi/driving-session", payload)

    def sync_trip_segment(self, segment_id: int) -> None:
        with get_session() as session:
            row = session.get(TripSegment, segment_id)
            if row is None:
                raise CloudIngestError(f"trip_segment {segment_id} not in local SQLite")
            payload = {
                "id": row.id,
                "driving_session_id": row.driving_session_id,
                "local_path": row.local_path,
                "init_local_stored": row.init_local_stored,
                "file_size_bytes": row.file_size_bytes,
                "start_time": _iso(row.start_time),
                "end_time": _iso(row.end_time),
                "order_number": row.order_number,
            }
        self._json_request("POST", "/api/netrapi/trip-segment", payload)

    def upload_trip_segment(self, segment_id: int) -> bool:
        """Prime JSON, then PUT + confirm one finished trip file (Wi-Fi drain).

        Returns True when this call uploaded (or already had) an S3 object.
        Skips PUT when the local file is not finished or is missing.
        """
        with get_session() as session:
            row = session.get(TripSegment, segment_id)
            if row is None:
                raise CloudIngestError(f"trip_segment {segment_id} not in local SQLite")
            session_id = row.driving_session_id
            local_path = row.local_path
            finished = row.init_local_stored is True
            already_stored = row.s3_stored is True and bool(row.s3_key)
        self.sync_session(session_id)
        self.sync_trip_segment(segment_id)
        if already_stored:
            self._emit(
                f"[ingest] trip_segment {segment_id} already uploaded; skip S3",
            )
            return True
        if not finished:
            self._emit(
                f"[ingest] trip_segment {segment_id} not finished locally; skip S3",
            )
            return False
        if not local_path:
            self._emit(
                f"[ingest] trip_segment {segment_id} has no local path; skip S3",
            )
            return False
        path = Path(local_path)
        if not path.is_file():
            self._emit(
                f"[ingest] trip file missing on disk ({path}); skip S3",
            )
            return False
        size_bytes = path.stat().st_size
        issued = self._json_request(
            "POST",
            "/api/netrapi/s3-upload-url",
            {"trip_segment_id": segment_id, "content_type": CLIP_CONTENT_TYPE},
        )
        put_url = issued.get("url")
        object_key = issued.get("object_key")
        if not put_url or not object_key:
            raise CloudIngestError(f"s3-upload-url missing url/object_key: {issued!r}")
        self._emit(
            f"[ingest] trip_segment {segment_id}: uploading {path.name} "
            f"({size_bytes} bytes) -> s3 key {object_key}"
        )
        self._put_path(str(put_url), path, CLIP_CONTENT_TYPE)
        self._json_request(
            "POST",
            "/api/netrapi/confirm-s3-upload",
            {"trip_segment_id": segment_id, "object_key": object_key},
        )
        self._mark_local_trip_uploaded(segment_id, str(object_key), path)
        self._emit(
            f"[ingest] trip_segment {segment_id} uploaded ({object_key})",
        )
        self._emit_upload_separator()
        return True

    def drain_clips(self) -> int:
        """POST pending event JSON and PUT finished clips that are not yet in S3."""
        with get_session() as session:
            events = session.exec(select(Event).order_by(Event.id)).all()
            pending: list[int] = []
            already = 0
            unfinished = 0
            for event in events:
                if event.id is None:
                    continue
                clip = session.exec(select(Clip).where(Clip.event_id == event.id)).first()
                if clip is None:
                    continue
                if clip.s3_stored is True and bool(clip.s3_key):
                    already += 1
                    continue
                if clip.init_local_stored is True:
                    pending.append(event.id)
                else:
                    unfinished += 1
        self._emit(
            f"[drain] clips: {len(pending)} pending, {already} already in S3"
            + (f", {unfinished} without finished local file" if unfinished else ""),
        )
        if pending:
            self._emit(f"[drain] clip event ids: {pending}")
        uploaded = 0
        for index, event_id in enumerate(pending, start=1):
            try:
                self._emit(
                    f"[drain] clip {index}/{len(pending)}: sync_event({event_id})",
                )
                self.sync_event(event_id)
                uploaded += 1
            except Exception as exc:
                self._emit(f"[ingest] event {event_id} drain failed: {exc}")
        return uploaded

    def drain_trip_segments(self) -> int:
        """Upload finished trip files that are not yet in S3, one at a time."""
        with get_session() as session:
            rows = session.exec(select(TripSegment).order_by(TripSegment.id)).all()
            pending: list[int] = []
            already = 0
            unfinished = 0
            for row in rows:
                if row.id is None:
                    continue
                if row.s3_stored is True and bool(row.s3_key):
                    already += 1
                    continue
                if row.init_local_stored is True:
                    pending.append(row.id)
                else:
                    unfinished += 1
        self._emit(
            f"[drain] trips: {len(pending)} pending, {already} already in S3"
            + (f", {unfinished} unfinished (still open / not saved)" if unfinished else ""),
        )
        if pending:
            self._emit(f"[drain] trip_segment ids: {pending}")
        uploaded = 0
        for index, segment_id in enumerate(pending, start=1):
            try:
                self._emit(
                    f"[drain] trip {index}/{len(pending)}: upload_trip_segment({segment_id})",
                )
                if self.upload_trip_segment(segment_id):
                    uploaded += 1
            except Exception as exc:
                self._emit(
                    f"[ingest] trip_segment {segment_id} drain failed: {exc}",
                )
        return uploaded

    def sync_operational_exception(self, exception_id: int) -> None:
        with get_session() as session:
            row = session.get(OperationalException, exception_id)
            if row is None:
                raise CloudIngestError(
                    f"operational_exception {exception_id} not in local SQLite"
                )
            payload = {
                "id": row.id,
                "driving_session_id": row.driving_session_id,
                "message": row.message,
                "time": _iso(row.time),
                "is_fatal": row.is_fatal,
            }
        self._json_request("POST", "/api/netrapi/operational-exception", payload)

    def sync_event(self, event_id: int) -> None:
        with get_session() as session:
            event = session.get(Event, event_id)
            if event is None:
                raise CloudIngestError(f"event {event_id} not in local SQLite")
            clip = session.exec(select(Clip).where(Clip.event_id == event_id)).first()
            classification = session.exec(
                select(Classification).where(
                    Classification.event_id == event_id,
                    Classification.kind == "auto",
                )
            ).first()
            if classification is None:
                raise CloudIngestError(
                    f"auto classification for event {event_id} not in local SQLite"
                )
            auto = session.exec(
                select(AutoClassification).where(
                    AutoClassification.classification_id == classification.id
                )
            ).first()
            if auto is None:
                raise CloudIngestError(
                    f"auto_classification for event {event_id} not in local SQLite"
                )
            type_row = session.get(
                ClassificationType, classification.classification_type_id
            )
            type_value = type_row.value if type_row is not None else "unknown"
            payload: dict[str, Any] = {
                "id": event.id,
                "driving_session_id": event.driving_session_id,
                "time": _iso(event.time),
                "auto_classification": {
                    "kind": "auto",
                    "classification_type_id": classification.classification_type_id,
                    "stage1_classification_type_id": auto.stage1_classification_type_id,
                    "stage2_classification_type_id": auto.stage2_classification_type_id,
                },
            }
            if clip is not None and clip.id is not None:
                payload["clip"] = {
                    "id": clip.id,
                    "fps": clip.fps,
                    "order_number": clip.order_number,
                    "num_frames": clip.num_frames,
                    "start_time": _iso(clip.start_time),
                    "end_time": _iso(clip.end_time),
                    "init_local_stored": clip.init_local_stored,
                    "local_path": clip.local_path,
                    "file_size_bytes": clip.file_size_bytes,
                }
            knn_rows = session.exec(
                select(KnnParameter).where(
                    KnnParameter.auto_classification_id == auto.id
                )
            ).all()
            if knn_rows:
                payload["knn_parameters"] = [
                    {"knn_feature_id": row.knn_feature_id, "value": row.value}
                    for row in knn_rows
                ]
            approach = session.exec(
                select(ApproachParameters).where(
                    ApproachParameters.auto_classification_id == auto.id
                )
            ).first()
            if approach is not None:
                reasons = session.exec(
                    select(ApproachFailReason).where(
                        ApproachFailReason.approach_parameters_id == approach.id
                    )
                ).all()
                payload["approach_parameters"] = {
                    "peak_area_pct": approach.peak_area_pct,
                    "approach_duration_s": approach.approach_duration_s,
                    "increasing_fraction": approach.increasing_fraction,
                    "log_linear_r2": approach.log_linear_r2,
                    "drop_duration_s": approach.drop_duration_s,
                    "post_drop_holds": approach.post_drop_holds,
                    "fail_reasons": [row.reason for row in reasons],
                }
            location = session.exec(
                select(EventTripLocation).where(EventTripLocation.event_id == event_id)
            ).first()
            if location is not None:
                payload["event_trip_location"] = {
                    "trip_segment_id": location.trip_segment_id,
                    "trip_offset_seconds": location.trip_offset_seconds,
                }
            clip_id = clip.id if clip is not None else None
            clip_path = clip.local_path if clip is not None else None
            already_stored = (
                clip is not None
                and clip.s3_stored is True
                and bool(clip.s3_key)
            )
        self._json_request("POST", "/api/netrapi/driving-event", payload)
        if clip_id is None:
            self._emit(
                f"[ingest] event {event_id} ({type_value}) has no clip yet; skip S3",
            )
            return
        if already_stored:
            self._emit(
                f"[ingest] event {event_id} ({type_value}) clip {clip_id} "
                f"already uploaded; skip S3",
            )
            return
        if not clip_path:
            self._emit(
                f"[ingest] event {event_id} ({type_value}) has no clip path; skip S3",
            )
            return
        path = Path(clip_path)
        if not path.is_file():
            self._emit(
                f"[ingest] event {event_id} ({type_value}) clip missing on disk "
                f"({path}); skip S3",
            )
            return
        issued = self._json_request(
            "POST",
            "/api/netrapi/s3-upload-url",
            {"clip_id": clip_id, "content_type": CLIP_CONTENT_TYPE},
        )
        object_key = issued.get("object_key")
        if object_key:
            self._emit(
                f"[ingest] event {event_id} ({type_value}) clip {clip_id}: "
                f"uploading {path.name} -> s3 key {object_key}"
            )
        object_key = self._put_clip_objects(issued, path)
        self._json_request(
            "POST",
            "/api/netrapi/confirm-s3-upload",
            {"clip_id": clip_id, "object_key": object_key},
        )
        self._mark_local_clip_uploaded(clip_id, str(object_key), Path(clip_path))
        self._emit(
            f"[ingest] event {event_id} ({type_value}) clip {clip_id} "
            f"uploaded ({object_key})",
        )
        self._emit_upload_separator()

    def _put_clip_objects(self, issued: dict[str, Any], clip_path: Path) -> str:
        object_key = issued.get("object_key")
        objects = issued.get("objects")
        if isinstance(objects, list) and objects:
            for item in objects:
                if not isinstance(item, dict):
                    raise CloudIngestError(f"s3-upload-url object entry invalid: {item!r}")
                name = item.get("name")
                put_url = item.get("url")
                content_type = str(item.get("content_type") or CLIP_CONTENT_TYPE)
                if not put_url or not name:
                    raise CloudIngestError(
                        f"s3-upload-url object missing url/name: {item!r}"
                    )
                local = (
                    clip_path
                    if name == clip_path.name
                    else clip_path.with_name(str(name))
                )
                if not local.is_file():
                    raise CloudIngestError(f"missing local clip file ({local})")
                self._put_path(str(put_url), local, content_type)
            if not object_key:
                raise CloudIngestError(f"s3-upload-url missing object_key: {issued!r}")
            return str(object_key)
        put_url = issued.get("url")
        if not put_url or not object_key:
            raise CloudIngestError(f"s3-upload-url missing url/object_key: {issued!r}")
        self._put_path(str(put_url), clip_path, CLIP_CONTENT_TYPE)
        return str(object_key)

    def _mark_local_clip_uploaded(
        self, clip_id: int, object_key: str, clip_path: Path
    ) -> None:
        with get_session() as session:
            row = session.get(Clip, clip_id)
            if row is None:
                raise CloudIngestError(
                    f"clip {clip_id} not in local SQLite after confirm"
                )
            row.s3_key = object_key
            row.s3_stored = True
            if clip_path.is_file():
                row.file_size_bytes = clip_path.stat().st_size
            session.add(row)
            session.commit()

    def _mark_local_trip_uploaded(
        self, segment_id: int, object_key: str, trip_path: Path
    ) -> None:
        with get_session() as session:
            row = session.get(TripSegment, segment_id)
            if row is None:
                raise CloudIngestError(
                    f"trip_segment {segment_id} not in local SQLite after confirm"
                )
            row.s3_key = object_key
            row.s3_stored = True
            if trip_path.is_file():
                row.file_size_bytes = trip_path.stat().st_size
            session.add(row)
            session.commit()

    def confirm_local_delete(
        self, *, clip_id: int | None = None, trip_segment_id: int | None = None
    ) -> None:
        if (clip_id is None) == (trip_segment_id is None):
            raise CloudIngestError(
                "exactly one of clip_id or trip_segment_id is required"
            )
        body: dict[str, Any] = {}
        if clip_id is not None:
            body["clip_id"] = clip_id
        else:
            body["trip_segment_id"] = trip_segment_id
        self._json_request("POST", "/api/netrapi/confirm-local-delete", body)


def try_cloud_ingest() -> CloudIngest | None:
    try:
        load_ingest_auth()
    except IngestAuthError:
        return None
    return CloudIngest()
