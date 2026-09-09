"""hide clips that are not real_world from the public list

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-08 19:45:00.000000

Try-it-out and Field Accuracy only use public-road clips. Anything without
the real_world flag is public_visible false, including untagged rows.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008"
down_revision: Union[str, Sequence[str], None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_clip = sa.table(
    "clip",
    sa.column("id", sa.Integer),
    sa.column("public_visible", sa.Boolean),
)
_clip_flag = sa.table(
    "clip_flag",
    sa.column("clip_id", sa.Integer),
    sa.column("flag_def_id", sa.Integer),
)
_flag_def = sa.table(
    "flag_def",
    sa.column("id", sa.Integer),
    sa.column("value", sa.String),
)


def _clip_ids_with_flag(value: str):
    return (
        sa.select(_clip_flag.c.clip_id)
        .select_from(
            _clip_flag.join(
                _flag_def, _flag_def.c.id == _clip_flag.c.flag_def_id
            )
        )
        .where(_flag_def.c.value == value)
    )


def upgrade() -> None:
    op.execute(
        _clip.update()
        .where(~_clip.c.id.in_(_clip_ids_with_flag("real_world")))
        .values(public_visible=False)
    )


def downgrade() -> None:
    op.execute(
        _clip.update()
        .where(~_clip.c.id.in_(_clip_ids_with_flag("real_world")))
        .where(~_clip.c.id.in_(_clip_ids_with_flag("synthetic")))
        .values(public_visible=True)
    )
