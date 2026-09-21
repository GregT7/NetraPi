"""seed testing clip flag

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-20 19:25:00.000000

Review flag for pipeline-only clips (not real-world, not synthetic).
Do not assign an explicit id so SERIAL stays in sync. Tagged clips are
not for evaluation; without real_world they stay off the public list.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011"
down_revision: Union[str, Sequence[str], None] = "0010"
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

_TESTING_NOTE = (
    "Clip recorded only to exercise the pipeline. Not real-world and not "
    "synthetic. Do not use for evaluation. Mutually exclusive with "
    "real_world, in_operating_envelope, and synthetic."
)


def upgrade() -> None:
    existing = op.get_bind().execute(
        sa.text("SELECT id FROM flag_def WHERE value = :value"),
        {"value": "testing"},
    ).fetchone()
    if existing is None:
        op.bulk_insert(
            _flag_def_insert,
            [{"value": "testing", "note": _TESTING_NOTE}],
        )
    else:
        op.execute(
            _flag_def.update()
            .where(_flag_def.c.value == "testing")
            .values(note=_TESTING_NOTE)
        )


def downgrade() -> None:
    op.execute(
        _clip_flag.delete().where(
            _clip_flag.c.flag_def_id.in_(
                sa.select(_flag_def.c.id).where(_flag_def.c.value == "testing")
            )
        )
    )
    op.execute(_flag_def.delete().where(_flag_def.c.value == "testing"))
