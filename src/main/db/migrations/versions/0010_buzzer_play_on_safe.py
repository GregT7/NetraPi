"""buzzer play_on_safe true

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-12 17:25:00.000000

Freeze play_on_safe=true onto the Alembic ``edge-json`` snapshot so it matches
live ``buzzer.json`` (coded complete-stop beep). Do not rewrite 0002; later
config freezes are new data revisions.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010"
down_revision: Union[str, Sequence[str], None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SEED_NAME = "edge-json"


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE buzzer_config
            SET play_on_safe = :flag
            WHERE master_config_id IN (
                SELECT id FROM master_config WHERE name = :name
            )
            """
        ).bindparams(flag=True, name=_SEED_NAME)
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE buzzer_config
            SET play_on_safe = :flag
            WHERE master_config_id IN (
                SELECT id FROM master_config WHERE name = :name
            )
            """
        ).bindparams(flag=False, name=_SEED_NAME)
    )
