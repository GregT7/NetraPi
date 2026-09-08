"""flag_def lookup and clip_flag instances

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-08 13:40:00.000000

Optional review flags on clips (ideal operating envelope, real-world, parking-lot).
Seed lookup rows; do not assign explicit ids so SERIAL stays in sync.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_flag_def = sa.table(
    "flag_def",
    sa.column("value", sa.String),
    sa.column("note", sa.String),
)

_FLAG_DEFS = (
    {
        "value": "in_operating_envelope",
        "note": (
            "Right-most lane closest to the stop sign, sign on the right side of "
            "the road, and the white halt line close to the sign. Apply only on "
            "real-world clips. Mutually exclusive with synthetic."
        ),
    },
    {
        "value": "real_world",
        "note": (
            "Clip recorded on a public road with a real stop sign. Mutually "
            "exclusive with synthetic."
        ),
    },
    {
        "value": "synthetic",
        "note": (
            "Parking-lot / training clip using a homemade stop sign. Mutually "
            "exclusive with real_world and in_operating_envelope."
        ),
    },
)


def upgrade() -> None:
    op.create_table(
        "flag_def",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("note", sa.String(), nullable=False),
        sa.UniqueConstraint("value", name="uq_flag_def_value"),
    )
    op.create_table(
        "clip_flag",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clip_id", sa.Integer(), nullable=False),
        sa.Column("flag_def_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["clip_id"], ["clip.id"]),
        sa.ForeignKeyConstraint(["flag_def_id"], ["flag_def.id"]),
        sa.UniqueConstraint("clip_id", "flag_def_id", name="uq_clip_flag_clip_def"),
    )
    op.bulk_insert(_flag_def, list(_FLAG_DEFS))


def downgrade() -> None:
    op.drop_table("clip_flag")
    op.drop_table("flag_def")
