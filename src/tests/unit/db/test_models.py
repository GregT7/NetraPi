from __future__ import annotations

from sqlmodel import SQLModel

import db.models as models


def _table_models() -> list[type[SQLModel]]:
    found: list[type[SQLModel]] = []
    for obj in vars(models).values():
        if obj is SQLModel:
            continue
        if (
            isinstance(obj, type)
            and issubclass(obj, SQLModel)
            and getattr(obj, "__tablename__", None)
        ):
            found.append(obj)
    return found


def test_every_table_model_is_in_metadata() -> None:
    names = {cls.__tablename__ for cls in _table_models()}
    assert names == set(SQLModel.metadata.tables)


def test_operational_table_names() -> None:
    tables = set(SQLModel.metadata.tables)
    assert {
        "classification_type",
        "object_label",
        "master_config",
        "driving_session",
        "trip_segment",
        "operational_exception",
        "event",
        "event_trip_location",
        "clip",
        "classification",
        "manual_classification",
        "auto_classification",
        "knn_parameter",
        "approach_parameters",
        "approach_fail_reason",
    }.issubset(tables)


def test_clip_one_to_one_with_event() -> None:
    event_fk = models.Clip.__table__.c.event_id
    assert event_fk.unique is True
    assert list(event_fk.foreign_keys)[0].target_fullname == "event.id"


def test_classification_kind_check_and_unique_event_kind() -> None:
    args = models.Classification.__table_args__
    names = {arg.name for arg in args}
    assert "ck_classification_kind" in names
    assert "uq_classification_event_kind" in names


def test_driving_session_fk_to_master_config() -> None:
    fk = list(models.DrivingSession.__table__.c.master_config_id.foreign_keys)[0]
    assert fk.target_fullname == "master_config.id"
