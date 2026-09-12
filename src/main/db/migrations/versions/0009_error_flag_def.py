"""seed error clip flag

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-12 16:40:00.000000

Review flag for unusable clips (glitch, truncated file, obstructed camera).
Do not assign an explicit id so SERIAL stays in sync. Tagged clips stay
public_visible; Try-it-out shows Label Error and accuracy ignores them.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009"
down_revision: Union[str, Sequence[str], None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_clip_flag = sa.table(
    "clip_flag",
    sa.column("clip_id", sa.Integer),
    sa.column("flag_def_id", sa.Integer),
)
_flag_def = sa.table(
    "flag_def",
    sa.column("id", sa.Integer),
    sa.column("value", sa.String),
    sa.column("note", sa.String),
)
_flag_def_insert = sa.table(
    "flag_def",
    sa.column("value", sa.String),
    sa.column("note", sa.String),
)

_ERROR_NOTE = (
    "Clip is unusable for evaluation (recording glitch, truncated file, "
    "obstructed camera, or similar). Stay listed when also real_world; "
    "Try-it-out shows Label Error. Do not combine with in_operating_envelope."
)


def upgrade() -> None:
    existing = op.get_bind().execute(
        sa.text("SELECT id FROM flag_def WHERE value = :value"),
        {"value": "error"},
    ).fetchone()
    if existing is None:
        op.bulk_insert(
            _flag_def_insert,
            [{"value": "error", "note": _ERROR_NOTE}],
        )
    else:
        op.execute(
            _flag_def.update()
            .where(_flag_def.c.value == "error")
            .values(note=_ERROR_NOTE)
        )


def downgrade() -> None:
    op.execute(
        _clip_flag.delete().where(
            _clip_flag.c.flag_def_id.in_(
                sa.select(_flag_def.c.id).where(_flag_def.c.value == "error")
            )
        )
    )
    op.execute(_flag_def.delete().where(_flag_def.c.value == "error"))
