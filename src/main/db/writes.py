from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, select

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
    KnnConfig,
    KnnFeature,
    KnnParameter,
    OperationalException,
    TripSegment,
)

SEEDED_MASTER_CONFIG_ID = 1
COMPLETE_STOP = "complete-stop"
STAGE1_UNSAFE = "rolling-or-run-through"
KNN_STAGE1_NAMES = (
    "post_drop_mean_motion",
    "post_drop_min_motion",
    "post_drop_p95_motion",
    "post_drop_stop_fraction",
)
KNN_STAGE2_NAMES = (
    "post_drop_min_motion",
    "approach_area_sum_pct",
)


def knn_feature_ids(
    session: Session, *, driving_session_id: int | None = None
) -> dict[tuple[int, str], int]:
    query = select(KnnFeature)
    if driving_session_id is not None:
        driving = session.get(DrivingSession, driving_session_id)
        if driving is None:
            raise RuntimeError(f"driving_session {driving_session_id} not found")
        knn = session.exec(
            select(KnnConfig).where(KnnConfig.master_config_id == driving.master_config_id)
        ).first()
        if knn is None or knn.id is None:
            raise RuntimeError(
                f"knn_config missing for master_config {driving.master_config_id}"
            )
        query = select(KnnFeature).where(KnnFeature.knn_config_id == knn.id)
    mapping: dict[tuple[int, str], int] = {}
    for row in session.exec(query).all():
        if row.id is None:
            continue
        mapping[(row.stage, row.feature_name)] = row.id
    return mapping


def local_file_size_bytes(path: Path | str) -> int | None:
    file_path = Path(path)
    if not file_path.is_file():
        return None
    return file_path.stat().st_size


def classification_type_id(session: Session, value: str) -> int:
    row = session.exec(
        select(ClassificationType).where(ClassificationType.value == value)
    ).first()
    if row is None or row.id is None:
        raise RuntimeError(f"classification_type {value!r} is not seeded")
    return row.id


def insert_driving_session(
    session: Session,
    *,
    master_config_id: int = SEEDED_MASTER_CONFIG_ID,
    start_time: datetime,
    end_time: datetime | None = None,
    row_id: int | None = None,
) -> DrivingSession:
    row = DrivingSession(
        id=row_id,
        master_config_id=master_config_id,
        start_time=start_time,
        end_time=end_time,
    )
    session.add(row)
    session.flush()
    if row.id is None:
        raise RuntimeError("driving_session insert did not assign an id")
    return row


def end_driving_session(
    session: Session,
    session_id: int,
    *,
    end_time: datetime,
) -> DrivingSession:
    row = session.get(DrivingSession, session_id)
    if row is None:
        raise RuntimeError(f"driving_session {session_id} not found")
    row.end_time = end_time
    session.add(row)
    session.flush()
    return row


def insert_local_event(
    session: Session,
    *,
    driving_session_id: int,
    time: datetime,
    type_value: str,
    clip_path: Path | str | None = None,
    fps: int | None = None,
    order_number: int | None = None,
    num_frames: int | None = None,
    clip_start: datetime | None = None,
    clip_end: datetime | None = None,
    row_id: int | None = None,
    clip_id: int | None = None,
    knn_stage1: Sequence[float] | None = None,
    knn_stage2: Sequence[float] | None = None,
    approach: dict | None = None,
    trip_segment_id: int | None = None,
    trip_offset_seconds: float | None = None,
) -> Event:
    if session.get(DrivingSession, driving_session_id) is None:
        raise RuntimeError(f"driving_session {driving_session_id} not found")
    final_id = classification_type_id(session, type_value)
    if type_value == COMPLETE_STOP:
        stage1_id = final_id
        stage2_id = None
    else:
        stage1_id = classification_type_id(session, STAGE1_UNSAFE)
        stage2_id = final_id

    event = Event(id=row_id, driving_session_id=driving_session_id, time=time)
    session.add(event)
    session.flush()
    if event.id is None:
        raise RuntimeError("event insert did not assign an id")

    classification = Classification(
        event_id=event.id,
        classification_type_id=final_id,
        kind="auto",
    )
    session.add(classification)
    session.flush()
    if classification.id is None:
        raise RuntimeError("classification insert did not assign an id")

    session.add(
        AutoClassification(
            classification_id=classification.id,
            stage1_classification_type_id=stage1_id,
            stage2_classification_type_id=stage2_id,
        )
    )
    session.flush()
    auto = session.exec(
        select(AutoClassification).where(
            AutoClassification.classification_id == classification.id
        )
    ).first()
    if auto is None or auto.id is None:
        raise RuntimeError("auto_classification insert did not assign an id")

    feature_ids = knn_feature_ids(session, driving_session_id=driving_session_id)
    if knn_stage1 is not None:
        if len(knn_stage1) != len(KNN_STAGE1_NAMES):
            raise RuntimeError("knn_stage1 must have 4 values")
        for name, value in zip(KNN_STAGE1_NAMES, knn_stage1):
            key = (1, name)
            if key not in feature_ids:
                raise RuntimeError(f"knn_feature missing for {key!r}")
            session.add(
                KnnParameter(
                    auto_classification_id=auto.id,
                    knn_feature_id=feature_ids[key],
                    value=float(value),
                )
            )
    if knn_stage2 is not None:
        if len(knn_stage2) != len(KNN_STAGE2_NAMES):
            raise RuntimeError("knn_stage2 must have 2 values")
        for name, value in zip(KNN_STAGE2_NAMES, knn_stage2):
            key = (2, name)
            if key not in feature_ids:
                raise RuntimeError(f"knn_feature missing for {key!r}")
            session.add(
                KnnParameter(
                    auto_classification_id=auto.id,
                    knn_feature_id=feature_ids[key],
                    value=float(value),
                )
            )
    if approach is not None:
        session.add(
            ApproachParameters(
                auto_classification_id=auto.id,
                peak_area_pct=float(approach["peak_area_pct"]),
                approach_duration_s=float(approach["approach_duration_s"]),
                increasing_fraction=float(approach["increasing_fraction"]),
                log_linear_r2=float(approach["log_linear_r2"]),
                drop_duration_s=float(approach["drop_duration_s"]),
                post_drop_holds=bool(approach["post_drop_holds"]),
            )
        )
        session.flush()
        approach_row = session.exec(
            select(ApproachParameters).where(
                ApproachParameters.auto_classification_id == auto.id
            )
        ).first()
        if approach_row is None or approach_row.id is None:
            raise RuntimeError("approach_parameters insert did not assign an id")
        for reason in approach.get("fail_reasons") or ():
            session.add(
                ApproachFailReason(
                    approach_parameters_id=approach_row.id,
                    reason=str(reason),
                )
            )
    if trip_segment_id is not None and trip_offset_seconds is not None:
        if session.get(TripSegment, trip_segment_id) is None:
            raise RuntimeError(f"trip_segment {trip_segment_id} not found")
        session.add(
            EventTripLocation(
                event_id=event.id,
                trip_segment_id=trip_segment_id,
                trip_offset_seconds=float(trip_offset_seconds),
            )
        )

    if clip_path is not None:
        if (
            fps is None
            or order_number is None
            or num_frames is None
            or clip_start is None
            or clip_end is None
        ):
            raise RuntimeError(
                "fps, order_number, num_frames, clip_start, and clip_end are "
                "required when clip_path is set"
            )
        session.add(
            Clip(
                id=clip_id,
                event_id=event.id,
                local_path=str(clip_path),
                init_local_stored=True,
                file_size_bytes=local_file_size_bytes(clip_path),
                fps=fps,
                order_number=order_number,
                num_frames=num_frames,
                start_time=clip_start,
                end_time=clip_end,
            )
        )
        session.flush()
    return event


def attach_local_clip(
    session: Session,
    event_id: int,
    *,
    clip_path: Path | str,
    fps: int,
    order_number: int,
    num_frames: int,
    clip_start: datetime,
    clip_end: datetime,
    clip_id: int | None = None,
) -> Clip:
    """Attach or update the clip row for an event that was persisted without media."""
    if session.get(Event, event_id) is None:
        raise RuntimeError(f"event {event_id} not found")
    existing = session.exec(select(Clip).where(Clip.event_id == event_id)).first()
    path_str = str(clip_path)
    size = local_file_size_bytes(clip_path)
    if existing is None:
        clip = Clip(
            id=clip_id,
            event_id=event_id,
            local_path=path_str,
            init_local_stored=True,
            file_size_bytes=size,
            fps=fps,
            order_number=order_number,
            num_frames=num_frames,
            start_time=clip_start,
            end_time=clip_end,
        )
        session.add(clip)
        session.flush()
        return clip
    existing.local_path = path_str
    existing.init_local_stored = True
    existing.file_size_bytes = size
    existing.fps = fps
    existing.order_number = order_number
    existing.num_frames = num_frames
    existing.start_time = clip_start
    existing.end_time = clip_end
    if clip_id is not None:
        existing.id = clip_id
    session.add(existing)
    session.flush()
    return existing


def insert_trip_segment(
    session: Session,
    *,
    driving_session_id: int,
    local_path: Path | str,
    start_time: datetime,
    end_time: datetime,
    order_number: int,
    row_id: int | None = None,
    init_local_stored: bool | None = True,
) -> TripSegment:
    if session.get(DrivingSession, driving_session_id) is None:
        raise RuntimeError(f"driving_session {driving_session_id} not found")
    row = TripSegment(
        id=row_id,
        driving_session_id=driving_session_id,
        local_path=str(local_path),
        init_local_stored=init_local_stored,
        file_size_bytes=(
            local_file_size_bytes(local_path) if init_local_stored is True else None
        ),
        start_time=start_time,
        end_time=end_time,
        order_number=order_number,
    )
    session.add(row)
    session.flush()
    if row.id is None:
        raise RuntimeError("trip_segment insert did not assign an id")
    return row


def update_trip_segment(
    session: Session,
    segment_id: int,
    *,
    local_path: Path | str,
    end_time: datetime,
    init_local_stored: bool | None = True,
) -> TripSegment:
    row = session.get(TripSegment, segment_id)
    if row is None:
        raise RuntimeError(f"trip_segment {segment_id} not found")
    row.local_path = str(local_path)
    row.end_time = end_time
    row.init_local_stored = init_local_stored
    if init_local_stored is True:
        row.file_size_bytes = local_file_size_bytes(local_path)
    session.add(row)
    session.flush()
    return row


def insert_operational_exception(
    session: Session,
    *,
    driving_session_id: int,
    message: str,
    time: datetime,
    is_fatal: bool,
    row_id: int | None = None,
) -> OperationalException:
    if session.get(DrivingSession, driving_session_id) is None:
        raise RuntimeError(f"driving_session {driving_session_id} not found")
    row = OperationalException(
        id=row_id,
        driving_session_id=driving_session_id,
        message=message,
        time=time,
        is_fatal=is_fatal,
    )
    session.add(row)
    session.flush()
    if row.id is None:
        raise RuntimeError("operational_exception insert did not assign an id")
    return row
