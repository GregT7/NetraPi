"""trip segment file size bytes

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-22 18:52:00.000000

Same on-disk / S3 size column as clip.file_size_bytes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("trip_segment") as batch:
        batch.add_column(sa.Column("file_size_bytes", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("trip_segment") as batch:
        batch.drop_column("file_size_bytes")
