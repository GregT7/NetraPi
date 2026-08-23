from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import SQLModel, select

from app.auth.api_key import require_api_key
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
    KnnFeature,
    KnnParameter,
    ManualClassification,
    TripSegment,
)

router = APIRouter(
    prefix="/api/netrapi",
    dependencies=[Depends(require_api_key)],
)


class ClipIn(SQLModel):
    id: int
    fps: int
    order_number: int
    num_frames: int
    start_time: datetime
    end_time: datetime
    init_local_stored: Optional[bool] = None
    local_path: Optional[str] = None
    file_size_bytes: Optional[int] = None


class AutoClassificationIn(SQLModel):
    kind: str = "auto"
    classification_type_id: int
    stage1_classification_type_id: int
    stage2_classification_type_id: Optional[int] = None


class KnnParameterIn(SQLModel):
    knn_feature_id: int
    value: float


class ApproachParametersIn(SQLModel):
    peak_area_pct: float
    approach_duration_s: float
    increasing_fraction: float
    log_linear_r2: float
    drop_duration_s: float
    post_drop_holds: bool
    fail_reasons: Optional[list[str]] = None


class EventTripLocationIn(SQLModel):
    trip_segment_id: int
    trip_offset_seconds: float


class ManualClassificationIn(SQLModel):
    classification_type_id: int
    time_of_review: datetime


class DrivingEventIn(SQLModel):
    id: int
    driving_session_id: int
    time: datetime
    clip: Optional[ClipIn] = None
    auto_classification: AutoClassificationIn
    knn_parameters: Optional[list[KnnParameterIn]] = None
    approach_parameters: Optional[ApproachParametersIn] = None
    event_trip_location: Optional[EventTripLocationIn] = None
    manual_classification: Optional[ManualClassificationIn] = None


def _require_classification_type(session, type_id: int) -> None:
    if session.get(ClassificationType, type_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"classification_type {type_id} not found",
        )


@router.post("/driving-event")
def upsert_driving_event(payload: DrivingEventIn):
    if payload.auto_classification.kind != "auto":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="auto_classification.kind must be 'auto'",
        )
    with get_session() as session:
        if session.get(DrivingSession, payload.driving_session_id) is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"driving_session {payload.driving_session_id} not found",
            )
        type_ids = [
            payload.auto_classification.classification_type_id,
            payload.auto_classification.stage1_classification_type_id,
        ]
        if payload.auto_classification.stage2_classification_type_id is not None:
            type_ids.append(payload.auto_classification.stage2_classification_type_id)
        if payload.manual_classification is not None:
            type_ids.append(payload.manual_classification.classification_type_id)
        for cid in type_ids:
            _require_classification_type(session, cid)

        event = session.get(Event, payload.id)
        if event is None:
            event = Event(
                id=payload.id,
                driving_session_id=payload.driving_session_id,
                time=payload.time,
            )
            session.add(event)
        else:
            event.driving_session_id = payload.driving_session_id
            event.time = payload.time
        session.flush()

        clip_id: int | None = None
        if payload.clip is not None:
            clip_id = payload.clip.id
            clip = session.get(Clip, payload.clip.id)
            if clip is None:
                clip = Clip(
                    id=payload.clip.id,
                    fps=payload.clip.fps,
                    order_number=payload.clip.order_number,
                    num_frames=payload.clip.num_frames,
                    start_time=payload.clip.start_time,
                    end_time=payload.clip.end_time,
                    s3_key=None,
                    s3_stored=None,
                    init_local_stored=payload.clip.init_local_stored,
                    local_path=payload.clip.local_path,
                    file_size_bytes=payload.clip.file_size_bytes,
                    event_id=payload.id,
                )
                session.add(clip)
            else:
                clip.fps = payload.clip.fps
                clip.order_number = payload.clip.order_number
                clip.num_frames = payload.clip.num_frames
                clip.start_time = payload.clip.start_time
                clip.end_time = payload.clip.end_time
                clip.init_local_stored = payload.clip.init_local_stored
                clip.event_id = payload.id
                if clip.init_local_deleted is not True:
                    clip.local_path = payload.clip.local_path
                if payload.clip.file_size_bytes is not None:
                    clip.file_size_bytes = payload.clip.file_size_bytes

        classification = session.exec(
            select(Classification).where(
                Classification.event_id == payload.id,
                Classification.kind == "auto",
            )
        ).first()
        if classification is None:
            classification = Classification(
                event_id=payload.id,
                kind="auto",
                classification_type_id=payload.auto_classification.classification_type_id,
            )
            session.add(classification)
            session.flush()
        else:
            classification.classification_type_id = (
                payload.auto_classification.classification_type_id
            )

        auto = session.exec(
            select(AutoClassification).where(
                AutoClassification.classification_id == classification.id
            )
        ).first()
        if auto is None:
            auto = AutoClassification(
                classification_id=classification.id,
                stage1_classification_type_id=(
                    payload.auto_classification.stage1_classification_type_id
                ),
                stage2_classification_type_id=(
                    payload.auto_classification.stage2_classification_type_id
                ),
            )
            session.add(auto)
        else:
            auto.stage1_classification_type_id = (
                payload.auto_classification.stage1_classification_type_id
            )
            auto.stage2_classification_type_id = (
                payload.auto_classification.stage2_classification_type_id
            )
        session.flush()

        if payload.knn_parameters is not None:
            seen: set[int] = set()
            for item in payload.knn_parameters:
                if session.get(KnnFeature, item.knn_feature_id) is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"knn_feature {item.knn_feature_id} not found",
                    )
                seen.add(item.knn_feature_id)
                param = session.exec(
                    select(KnnParameter).where(
                        KnnParameter.auto_classification_id == auto.id,
                        KnnParameter.knn_feature_id == item.knn_feature_id,
                    )
                ).first()
                if param is None:
                    session.add(
                        KnnParameter(
                            auto_classification_id=auto.id,
                            knn_feature_id=item.knn_feature_id,
                            value=item.value,
                        )
                    )
                else:
                    param.value = item.value
            extras = session.exec(
                select(KnnParameter).where(
                    KnnParameter.auto_classification_id == auto.id
                )
            ).all()
            for extra in extras:
                if extra.knn_feature_id not in seen:
                    session.delete(extra)

        if payload.approach_parameters is not None:
            incoming = payload.approach_parameters
            approach = session.exec(
                select(ApproachParameters).where(
                    ApproachParameters.auto_classification_id == auto.id
                )
            ).first()
            if approach is None:
                approach = ApproachParameters(
                    auto_classification_id=auto.id,
                    peak_area_pct=incoming.peak_area_pct,
                    approach_duration_s=incoming.approach_duration_s,
                    increasing_fraction=incoming.increasing_fraction,
                    log_linear_r2=incoming.log_linear_r2,
                    drop_duration_s=incoming.drop_duration_s,
                    post_drop_holds=incoming.post_drop_holds,
                )
                session.add(approach)
                session.flush()
            else:
                approach.peak_area_pct = incoming.peak_area_pct
                approach.approach_duration_s = incoming.approach_duration_s
                approach.increasing_fraction = incoming.increasing_fraction
                approach.log_linear_r2 = incoming.log_linear_r2
                approach.drop_duration_s = incoming.drop_duration_s
                approach.post_drop_holds = incoming.post_drop_holds
            if incoming.fail_reasons is not None:
                for row in session.exec(
                    select(ApproachFailReason).where(
                        ApproachFailReason.approach_parameters_id == approach.id
                    )
                ).all():
                    session.delete(row)
                for reason in incoming.fail_reasons:
                    session.add(
                        ApproachFailReason(
                            approach_parameters_id=approach.id,
                            reason=reason,
                        )
                    )

        if payload.event_trip_location is not None:
            loc_in = payload.event_trip_location
            if session.get(TripSegment, loc_in.trip_segment_id) is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"trip_segment {loc_in.trip_segment_id} not found",
                )
            loc = session.exec(
                select(EventTripLocation).where(
                    EventTripLocation.event_id == payload.id
                )
            ).first()
            if loc is None:
                session.add(
                    EventTripLocation(
                        event_id=payload.id,
                        trip_segment_id=loc_in.trip_segment_id,
                        trip_offset_seconds=loc_in.trip_offset_seconds,
                    )
                )
            else:
                loc.trip_segment_id = loc_in.trip_segment_id
                loc.trip_offset_seconds = loc_in.trip_offset_seconds

        if payload.manual_classification is not None:
            man_in = payload.manual_classification
            manual = session.exec(
                select(Classification).where(
                    Classification.event_id == payload.id,
                    Classification.kind == "manual",
                )
            ).first()
            if manual is None:
                manual = Classification(
                    event_id=payload.id,
                    kind="manual",
                    classification_type_id=man_in.classification_type_id,
                )
                session.add(manual)
                session.flush()
            else:
                manual.classification_type_id = man_in.classification_type_id
            extra = session.exec(
                select(ManualClassification).where(
                    ManualClassification.classification_id == manual.id
                )
            ).first()
            if extra is None:
                session.add(
                    ManualClassification(
                        classification_id=manual.id,
                        time_of_review=man_in.time_of_review,
                    )
                )
            else:
                extra.time_of_review = man_in.time_of_review

        session.commit()
        session.refresh(event)
        return {
            "id": event.id,
            "driving_session_id": event.driving_session_id,
            "time": event.time.isoformat(),
            "clip_id": clip_id,
        }
