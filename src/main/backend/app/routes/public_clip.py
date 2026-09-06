from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from sqlmodel import SQLModel, select

from app.public_limits import (
    PUBLIC_MAX_LIVE_URLS,
    PublicMintLimitError,
    acquire_live_slot,
    live_slot_count,
    record_mint_request,
    release_live_slot,
)
from app.s3 import (
    CLIP_AREAS_NAME,
    CLIP_MOTION_NAME,
    CLIP_SIDECAR_NAMES,
    CLIP_TRANSITIONS_NAME,
    PUBLIC_CLIP_EXPIRES_SECONDS,
    S3NotConfiguredError,
    clip_sidecar_key,
    get_object_json,
    presign_get,
)
from db.database import get_session
from db.models import Classification, ClassificationType, Clip, Event

router = APIRouter(prefix="/api/public")

_TYPE_LABELS = {
    "complete-stop": "Complete Stop",
    "false_negative": "Missed stop",
    "false_positive": "Unrelated",
    "rolling-or-run-through": "Unsafe",
    "rolling-stop": "Rolling Stop",
    "run-through": "Run-through Stop",
}


class PublicClipDownloadIn(SQLModel):
    clip_id: int


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client is not None and request.client.host:
        return request.client.host
    return "unknown"


def _http_limit(exc: PublicMintLimitError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=exc.detail,
        headers={"Retry-After": str(exc.retry_after)},
    )


def _display_type(value: str) -> str:
    return _TYPE_LABELS.get(value, value.replace("_", " ").replace("-", " ").title())


def _type_values(session) -> dict[int, str]:
    return {
        row.id: row.value
        for row in session.exec(select(ClassificationType)).all()
        if row.id is not None
    }


def _clip_labels(session, event_id: int, types: dict[int, str]) -> tuple[str, str]:
    rows = session.exec(
        select(Classification).where(Classification.event_id == event_id)
    ).all()
    auto = ""
    manual = ""
    for row in rows:
        label = _display_type(types.get(row.classification_type_id, ""))
        if row.kind == "auto":
            auto = label
        elif row.kind == "manual":
            manual = label
    prediction = auto or "—"
    return (manual or "-", prediction)


def _format_clip_time(value) -> str:
    return value.strftime("%Y-%m-%d %I:%M %p")


def _live_url_status() -> dict[str, int]:
    return {
        "live_urls": live_slot_count(),
        "live_url_max": PUBLIC_MAX_LIVE_URLS,
    }


def _sidecar_json(object_key: str, name: str) -> dict | None:
    sidecar_key = clip_sidecar_key(object_key, name)
    if sidecar_key is None:
        return None
    try:
        return get_object_json(sidecar_key)
    except Exception:
        return None


@router.get("/clips")
def list_public_clips():
    with get_session() as session:
        types = _type_values(session)
        clips = session.exec(
            select(Clip, Event)
            .join(Event, Event.id == Clip.event_id)
            .where(Clip.s3_stored.is_(True))
            .where(Clip.s3_key.is_not(None))
            .order_by(Event.time.desc())
            .limit(50)
        ).all()
        body = []
        for clip, event in clips:
            if not clip.s3_key or clip.id is None:
                continue
            label, prediction = _clip_labels(session, clip.event_id, types)
            body.append(
                {
                    "clip_id": clip.id,
                    "id": f"clip-{clip.id}",
                    "dateTime": _format_clip_time(event.time),
                    "label": label,
                    "classification": prediction,
                }
            )
        return {"clips": body, **_live_url_status()}


@router.post("/clip-download-url")
def issue_public_clip_download_url(payload: PublicClipDownloadIn, request: Request):
    try:
        record_mint_request(_client_ip(request))
    except PublicMintLimitError as exc:
        raise _http_limit(exc) from exc

    with get_session() as session:
        clip = session.get(Clip, payload.clip_id)
        if clip is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"clip {payload.clip_id} not found",
            )
        if clip.s3_stored is not True or not clip.s3_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="object is not confirmed in S3",
            )
        object_key = clip.s3_key
        clip_id = clip.id

    try:
        expiry = acquire_live_slot(PUBLIC_CLIP_EXPIRES_SECONDS)
    except PublicMintLimitError as exc:
        raise _http_limit(exc) from exc

    try:
        url = presign_get(object_key, expires_in=PUBLIC_CLIP_EXPIRES_SECONDS)
        sidecars = {name: _sidecar_json(object_key, name) for name in CLIP_SIDECAR_NAMES}
    except S3NotConfiguredError as exc:
        release_live_slot(expiry)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception:
        release_live_slot(expiry)
        raise

    return {
        "url": url,
        "object_key": object_key,
        "method": "GET",
        "clip_id": clip_id,
        "expires_in": PUBLIC_CLIP_EXPIRES_SECONDS,
        "areas": sidecars.get(CLIP_AREAS_NAME),
        "motion": sidecars.get(CLIP_MOTION_NAME),
        "transitions": sidecars.get(CLIP_TRANSITIONS_NAME),
        **_live_url_status(),
    }
