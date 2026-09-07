"""clip.public_visible for Try-it-out list

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-06 21:21:00.000000

Portfolio list and mint only include clips where public_visible is true.
Existing rows stay visible (default 1). Hide room/iPad clips with UPDATE.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "clip",
        sa.Column(
            "public_visible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("clip", "public_visible")
