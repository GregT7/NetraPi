"""hide synthetic clips from the public list

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-08 19:05:00.000000

Parking-lot / homemade-sign clips stay in the database but are not
public_visible, so Field Accuracy and Try-it-out omit them.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
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


def _synthetic_clip_ids():
    return (
        sa.select(_clip_flag.c.clip_id)
        .select_from(
            _clip_flag.join(
                _flag_def, _flag_def.c.id == _clip_flag.c.flag_def_id
            )
        )
        .where(_flag_def.c.value == "synthetic")
    )


def upgrade() -> None:
    op.execute(
        _clip.update()
        .where(_clip.c.id.in_(_synthetic_clip_ids()))
        .values(public_visible=False)
    )


def downgrade() -> None:
    op.execute(
        _clip.update()
        .where(_clip.c.id.in_(_synthetic_clip_ids()))
        .values(public_visible=True)
    )
