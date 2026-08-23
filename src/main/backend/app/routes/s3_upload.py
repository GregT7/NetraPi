from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import SQLModel

from app.auth.api_key import require_api_key
from app.s3 import (
    CLIP_EXPIRES_SECONDS,
    DEFAULT_CONTENT_TYPE,
    TRIP_EXPIRES_SECONDS,
    S3NotConfiguredError,
    head_object,
    media_object_key,
    presign_get,
    presign_put,
)
from db.database import get_session
from db.models import Clip, DrivingSession, Event, TripSegment

router = APIRouter(
    prefix="/api/netrapi",
    dependencies=[Depends(require_api_key)],
)


class S3UploadUrlIn(SQLModel):
    clip_id: Optional[int] = None
    trip_segment_id: Optional[int] = None
    content_type: str = DEFAULT_CONTENT_TYPE


class ConfirmS3UploadIn(SQLModel):
    clip_id: Optional[int] = None
    trip_segment_id: Optional[int] = None
    object_key: str


class S3DownloadUrlIn(SQLModel):
    clip_id: Optional[int] = None
    trip_segment_id: Optional[int] = None


class ConfirmLocalDeleteIn(SQLModel):
    clip_id: Optional[int] = None
    trip_segment_id: Optional[int] = None


def _xor_media(session, clip_id: int | None, trip_segment_id: int | None):
    if (clip_id is None) == (trip_segment_id is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="exactly one of clip_id or trip_segment_id is required",
        )
    if clip_id is not None:
        row = session.get(Clip, clip_id)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"clip {clip_id} not found",
            )
        return "clip", row
    row = session.get(TripSegment, trip_segment_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"trip_segment {trip_segment_id} not found",
        )
    return "trip", row


def _driving_session_for_media(session, kind: str, row):
    if kind == "clip":
        event = session.get(Event, row.event_id)
        if event is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"event {row.event_id} not found",
            )
        session_id = event.driving_session_id
    else:
        session_id = row.driving_session_id
    driving = session.get(DrivingSession, session_id)
    if driving is None or driving.id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"driving_session {session_id} not found",
        )
    return driving


def _assigned_object_key(session, kind: str, row) -> str:
    driving = _driving_session_for_media(session, kind, row)
    return media_object_key(
        kind=kind,
        row_id=row.id,
        session_id=driving.id,
        start_time=driving.start_time,
    )


@router.post("/s3-upload-url")
def issue_s3_upload_url(payload: S3UploadUrlIn):
    with get_session() as session:
        kind, row = _xor_media(session, payload.clip_id, payload.trip_segment_id)
        object_key = _assigned_object_key(session, kind, row)
        expires_in = (
            CLIP_EXPIRES_SECONDS if kind == "clip" else TRIP_EXPIRES_SECONDS
        )
        try:
            url = presign_put(
                object_key,
                content_type=payload.content_type,
                expires_in=expires_in,
            )
        except S3NotConfiguredError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        return {"url": url, "object_key": object_key, "method": "PUT"}


@router.post("/confirm-s3-upload")
def confirm_s3_upload(payload: ConfirmS3UploadIn):
    with get_session() as session:
        kind, row = _xor_media(session, payload.clip_id, payload.trip_segment_id)
        expected = _assigned_object_key(session, kind, row)
        if payload.object_key != expected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="object_key does not match assigned key",
            )
        try:
            found = head_object(payload.object_key)
        except S3NotConfiguredError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        if found is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"S3 object not found: {payload.object_key}",
            )
        row.s3_key = payload.object_key
        row.s3_stored = True
        size = found.get("ContentLength")
        if size is not None:
            row.file_size_bytes = int(size)
        session.add(row)
        session.commit()
        session.refresh(row)
        body = {"object_key": payload.object_key, "s3_stored": True}
        if row.file_size_bytes is not None:
            body["file_size_bytes"] = row.file_size_bytes
        if kind == "clip":
            body["clip_id"] = row.id
        else:
            body["trip_segment_id"] = row.id
        return body


@router.post("/s3-download-url")
def issue_s3_download_url(payload: S3DownloadUrlIn):
    with get_session() as session:
        kind, row = _xor_media(session, payload.clip_id, payload.trip_segment_id)
        if row.s3_stored is not True or not row.s3_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="object is not confirmed in S3",
            )
        expires_in = (
            CLIP_EXPIRES_SECONDS if kind == "clip" else TRIP_EXPIRES_SECONDS
        )
        try:
            url = presign_get(row.s3_key, expires_in=expires_in)
        except S3NotConfiguredError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        body = {"url": url, "object_key": row.s3_key, "method": "GET"}
        if kind == "clip":
            body["clip_id"] = row.id
        else:
            body["trip_segment_id"] = row.id
        return body


@router.post("/confirm-local-delete")
def confirm_local_delete(payload: ConfirmLocalDeleteIn):
    with get_session() as session:
        kind, row = _xor_media(session, payload.clip_id, payload.trip_segment_id)
        row.init_local_deleted = True
        row.local_path = None
        session.add(row)
        session.commit()
        session.refresh(row)
        body = {"init_local_deleted": True, "local_path": None}
        if kind == "clip":
            body["clip_id"] = row.id
        else:
            body["trip_segment_id"] = row.id
        return body
