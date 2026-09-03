from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
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
PutBytes = Callable[[str, bytes, str], None]

JSON_TIMEOUT_S = 30.0
PUT_TIMEOUT_S = 600.0
CLIP_CONTENT_TYPE = "video/mp4"
JSON_CONTENT_TYPE = "application/json"


def _iso(value: datetime) -> str:
    text = value.isoformat()
    if value.tzinfo is None:
        if not text.endswith("Z"):
            return text + "Z"
        return text
    return text.replace("+00:00", "Z")


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


def _http_put(url: str, payload: bytes, content_type: str) -> None:
    request = urllib.request.Request(
        url,
        data=payload,
        method="PUT",
        headers={"Content-Type": content_type},
    )
    try:
        with urllib.request.urlopen(request, timeout=PUT_TIMEOUT_S) as response:
            status = getattr(response, "status", 200)
            if status not in {200, 204}:
                raise CloudIngestError(f"PUT {url} -> {status}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise CloudIngestError(f"PUT -> {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise CloudIngestError(f"PUT failed: {exc}") from exc


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
        put_bytes: PutBytes | None = None,
    ) -> None:
        self._json_request = json_request or self._json_request_http
        self._put_bytes = put_bytes or _http_put

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
            print(
                f"[ingest] trip_segment {segment_id} already uploaded; skip S3",
                flush=True,
            )
            return True
        if not finished:
            print(
                f"[ingest] trip_segment {segment_id} not finished locally; skip S3",
                flush=True,
            )
            return False
        if not local_path:
            print(
                f"[ingest] trip_segment {segment_id} has no local path; skip S3",
                flush=True,
            )
            return False
        path = Path(local_path)
        if not path.is_file():
            print(
                f"[ingest] trip file missing on disk ({path}); skip S3",
                flush=True,
            )
            return False
        size_bytes = path.stat().st_size
        print(
            f"[ingest] trip_segment {segment_id}: PUT {path.name} "
            f"({size_bytes} bytes) ...",
            flush=True,
        )
        issued = self._json_request(
            "POST",
            "/api/netrapi/s3-upload-url",
            {"trip_segment_id": segment_id, "content_type": CLIP_CONTENT_TYPE},
        )
        put_url = issued.get("url")
        object_key = issued.get("object_key")
        if not put_url or not object_key:
            raise CloudIngestError(f"s3-upload-url missing url/object_key: {issued!r}")
        self._put_bytes(str(put_url), path.read_bytes(), CLIP_CONTENT_TYPE)
        self._json_request(
            "POST",
            "/api/netrapi/confirm-s3-upload",
            {"trip_segment_id": segment_id, "object_key": object_key},
        )
        self._mark_local_trip_uploaded(segment_id, str(object_key), path)
        print(
            f"[ingest] trip_segment {segment_id} uploaded ({object_key})",
            flush=True,
        )
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
        print(
            f"[drain] clips: {len(pending)} pending, {already} already in S3"
            + (f", {unfinished} without finished local file" if unfinished else ""),
            flush=True,
        )
        if pending:
            print(f"[drain] clip event ids: {pending}", flush=True)
        uploaded = 0
        for index, event_id in enumerate(pending, start=1):
            try:
                print(
                    f"[drain] clip {index}/{len(pending)}: sync_event({event_id})",
                    flush=True,
                )
                self.sync_event(event_id)
                uploaded += 1
            except Exception as exc:
                print(f"[ingest] event {event_id} drain failed: {exc}", flush=True)
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
        print(
            f"[drain] trips: {len(pending)} pending, {already} already in S3"
            + (f", {unfinished} unfinished (still open / not saved)" if unfinished else ""),
            flush=True,
        )
        if pending:
            print(f"[drain] trip_segment ids: {pending}", flush=True)
        uploaded = 0
        for index, segment_id in enumerate(pending, start=1):
            try:
                print(
                    f"[drain] trip {index}/{len(pending)}: upload_trip_segment({segment_id})",
                    flush=True,
                )
                if self.upload_trip_segment(segment_id):
                    uploaded += 1
            except Exception as exc:
                print(
                    f"[ingest] trip_segment {segment_id} drain failed: {exc}",
                    flush=True,
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
            print(
                f"[ingest] event {event_id} ({type_value}) has no clip yet; skip S3",
                flush=True,
            )
            return
        if already_stored:
            print(
                f"[ingest] event {event_id} ({type_value}) clip {clip_id} "
                f"already uploaded; skip S3",
                flush=True,
            )
            return
        if not clip_path:
            print(
                f"[ingest] event {event_id} ({type_value}) has no clip path; skip S3",
                flush=True,
            )
            return
        path = Path(clip_path)
        if not path.is_file():
            print(
                f"[ingest] event {event_id} ({type_value}) clip missing on disk "
                f"({path}); skip S3",
                flush=True,
            )
            return
        issued = self._json_request(
            "POST",
            "/api/netrapi/s3-upload-url",
            {"clip_id": clip_id, "content_type": CLIP_CONTENT_TYPE},
        )
        object_key = self._put_clip_objects(issued, path)
        self._json_request(
            "POST",
            "/api/netrapi/confirm-s3-upload",
            {"clip_id": clip_id, "object_key": object_key},
        )
        self._mark_local_clip_uploaded(clip_id, str(object_key), Path(clip_path))
        print(
            f"[ingest] event {event_id} ({type_value}) clip {clip_id} "
            f"uploaded ({object_key})",
            flush=True,
        )

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
                self._put_bytes(str(put_url), local.read_bytes(), content_type)
            if not object_key:
                raise CloudIngestError(f"s3-upload-url missing object_key: {issued!r}")
            return str(object_key)
        put_url = issued.get("url")
        if not put_url or not object_key:
            raise CloudIngestError(f"s3-upload-url missing url/object_key: {issued!r}")
        self._put_bytes(str(put_url), clip_path.read_bytes(), CLIP_CONTENT_TYPE)
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
