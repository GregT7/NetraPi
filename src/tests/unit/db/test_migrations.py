from __future__ import annotations

from pathlib import Path

from datetime import datetime, timezone

from sqlmodel import select

import db.database as database
from db.database import get_session, init_engine
from db.models import (
    BuzzerConfig,
    ClassificationType,
    Clip,
    ClipFlag,
    DrivingSession,
    Event,
    FlagDef,
    HealthConfig,
    MasterConfig,
)

ALEMBIC_INI = Path(__file__).resolve().parents[3] / "main" / "db" / "alembic.ini"


def _upgrade(url: str) -> None:
    from alembic import command
    from alembic.config import Config

    database.set_database_url_override(url)
    if not ALEMBIC_INI.is_file():
        raise RuntimeError(f"Alembic config not found: {ALEMBIC_INI}")
    command.upgrade(Config(str(ALEMBIC_INI)), "head")


def test_alembic_ini_exists() -> None:
    assert ALEMBIC_INI.is_file()


def test_upgrade_head_seeds_master_config_and_types(sqlite_url: str) -> None:
    _upgrade(sqlite_url)
    init_engine(sqlite_url)
    with get_session() as session:
        master = session.exec(
            select(MasterConfig).where(MasterConfig.name == "edge-json")
        ).one()
        assert master.id is not None
        values = {row.value for row in session.exec(select(ClassificationType)).all()}
        flags = {row.value for row in session.exec(select(FlagDef)).all()}
        health = session.exec(
            select(HealthConfig).where(HealthConfig.master_config_id == master.id)
        ).one()
        buzzer = session.exec(
            select(BuzzerConfig).where(BuzzerConfig.master_config_id == master.id)
        ).one()
    assert "complete-stop" in values
    assert "rolling-stop" in values
    assert "run-through" in values
    assert flags == {
        "error",
        "in_operating_envelope",
        "real_world",
        "synthetic",
    }
    assert health.render_wait_s == 90
    assert health.wlan_interface == "wlan0"
    assert buzzer.play_on_safe is True


def test_upgrade_hides_non_real_world_clips(sqlite_url: str) -> None:
    from alembic import command
    from alembic.config import Config

    database.set_database_url_override(sqlite_url)
    config = Config(str(ALEMBIC_INI))
    command.upgrade(config, "0006")
    init_engine(sqlite_url)
    now = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
    with get_session() as session:
        driving = DrivingSession(master_config_id=1, start_time=now)
        session.add(driving)
        session.commit()
        session.refresh(driving)
        assert driving.id is not None
        session.add(Event(driving_session_id=driving.id, time=now))
        session.add(Event(driving_session_id=driving.id, time=now))
        session.add(Event(driving_session_id=driving.id, time=now))
        session.commit()
        events = session.exec(select(Event).order_by(Event.id)).all()
        assert (
            len(events) == 3
            and events[0].id is not None
            and events[1].id is not None
            and events[2].id is not None
        )
        session.add(
            Clip(
                event_id=events[0].id,
                fps=30,
                num_frames=10,
                order_number=1,
                public_visible=True,
                start_time=now,
                end_time=now,
            )
        )
        session.add(
            Clip(
                event_id=events[1].id,
                fps=30,
                num_frames=10,
                order_number=2,
                public_visible=True,
                start_time=now,
                end_time=now,
            )
        )
        session.add(
            Clip(
                event_id=events[2].id,
                fps=30,
                num_frames=10,
                order_number=3,
                public_visible=True,
                start_time=now,
                end_time=now,
            )
        )
        session.commit()
        synthetic = session.exec(
            select(FlagDef).where(FlagDef.value == "synthetic")
        ).one()
        real_world = session.exec(
            select(FlagDef).where(FlagDef.value == "real_world")
        ).one()
        clips = session.exec(select(Clip).order_by(Clip.order_number)).all()
        session.add(ClipFlag(clip_id=clips[0].id, flag_def_id=synthetic.id))
        session.add(ClipFlag(clip_id=clips[1].id, flag_def_id=real_world.id))
        session.commit()
        synthetic_clip_id = clips[0].id
        real_clip_id = clips[1].id
        untagged_clip_id = clips[2].id

    if database._engine is not None:
        database._engine.dispose()
        database._engine = None
    command.upgrade(config, "0008")
    init_engine(sqlite_url)
    with get_session() as session:
        synthetic_clip = session.get(Clip, synthetic_clip_id)
        real_clip = session.get(Clip, real_clip_id)
        untagged_clip = session.get(Clip, untagged_clip_id)
        assert synthetic_clip is not None
        assert real_clip is not None
        assert untagged_clip is not None
        assert synthetic_clip.public_visible is False
        assert real_clip.public_visible is True
        assert untagged_clip.public_visible is False


def test_upgrade_keeps_error_clips_visible(sqlite_url: str) -> None:
    from alembic import command
    from alembic.config import Config

    database.set_database_url_override(sqlite_url)
    config = Config(str(ALEMBIC_INI))
    command.upgrade(config, "0008")
    init_engine(sqlite_url)
    now = datetime(2026, 9, 12, 16, 0, tzinfo=timezone.utc)
    with get_session() as session:
        driving = DrivingSession(master_config_id=1, start_time=now)
        session.add(driving)
        session.commit()
        session.refresh(driving)
        assert driving.id is not None
        session.add(Event(driving_session_id=driving.id, time=now))
        session.commit()
        event = session.exec(select(Event)).one()
        assert event.id is not None
        session.add(
            Clip(
                event_id=event.id,
                fps=30,
                num_frames=10,
                order_number=1,
                public_visible=True,
                start_time=now,
                end_time=now,
            )
        )
        session.commit()
        clip = session.exec(select(Clip)).one()
        real_world = session.exec(
            select(FlagDef).where(FlagDef.value == "real_world")
        ).one()
        session.add(FlagDef(value="error", note="pre-seed"))
        session.commit()
        error = session.exec(select(FlagDef).where(FlagDef.value == "error")).one()
        session.add(ClipFlag(clip_id=clip.id, flag_def_id=real_world.id))
        session.add(ClipFlag(clip_id=clip.id, flag_def_id=error.id))
        session.commit()
        clip_id = clip.id

    if database._engine is not None:
        database._engine.dispose()
        database._engine = None
    command.upgrade(config, "0009")
    init_engine(sqlite_url)
    with get_session() as session:
        clip = session.get(Clip, clip_id)
        errors = session.exec(select(FlagDef).where(FlagDef.value == "error")).all()
        assert clip is not None
        assert clip.public_visible is True
        assert len(errors) == 1
        assert errors[0].note.startswith("Clip is unusable")
