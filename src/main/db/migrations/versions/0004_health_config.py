"""health config snapshot table

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-23 12:40:00.000000

Frozen health.json settings as a 1:1 child of master_config.
Backfills defaults for every existing snapshot (including the Alembic `edge-json` seed).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULTS = {
    "render_wait_s": 90.0,
    "render_poll_s": 2.0,
    "render_request_timeout_s": 15.0,
    "internet_probe_host": "8.8.8.8",
    "internet_probe_port": 53,
    "internet_probe_timeout_s": 3.0,
    "public_https_host": "www.google.com",
    "public_https_port": 443,
    "wlan_interface": "wlan0",
    "keepalive_interval_s": 300.0,
    "keepalive_request_timeout_s": 15.0,
    "keepalive_fail_limit": 3,
    "log_path": "logs/health.log",
}


def upgrade() -> None:
    op.create_table(
        "health_config",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("master_config_id", sa.Integer(), nullable=False),
        sa.Column("render_wait_s", sa.Float(), nullable=False),
        sa.Column("render_poll_s", sa.Float(), nullable=False),
        sa.Column("render_request_timeout_s", sa.Float(), nullable=False),
        sa.Column("internet_probe_host", sa.String(), nullable=False),
        sa.Column("internet_probe_port", sa.Integer(), nullable=False),
        sa.Column("internet_probe_timeout_s", sa.Float(), nullable=False),
        sa.Column("public_https_host", sa.String(), nullable=False),
        sa.Column("public_https_port", sa.Integer(), nullable=False),
        sa.Column("wlan_interface", sa.String(), nullable=False),
        sa.Column("keepalive_interval_s", sa.Float(), nullable=False),
        sa.Column("keepalive_request_timeout_s", sa.Float(), nullable=False),
        sa.Column("keepalive_fail_limit", sa.Integer(), nullable=False),
        sa.Column("log_path", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["master_config_id"], ["master_config.id"]),
        sa.UniqueConstraint("master_config_id"),
    )
    bind = op.get_bind()
    ids = bind.execute(sa.text("SELECT id FROM master_config")).fetchall()
    if ids:
        table = sa.table(
            "health_config",
            sa.column("master_config_id", sa.Integer),
            sa.column("render_wait_s", sa.Float),
            sa.column("render_poll_s", sa.Float),
            sa.column("render_request_timeout_s", sa.Float),
            sa.column("internet_probe_host", sa.String),
            sa.column("internet_probe_port", sa.Integer),
            sa.column("internet_probe_timeout_s", sa.Float),
            sa.column("public_https_host", sa.String),
            sa.column("public_https_port", sa.Integer),
            sa.column("wlan_interface", sa.String),
            sa.column("keepalive_interval_s", sa.Float),
            sa.column("keepalive_request_timeout_s", sa.Float),
            sa.column("keepalive_fail_limit", sa.Integer),
            sa.column("log_path", sa.String),
        )
        op.bulk_insert(
            table,
            [{"master_config_id": row[0], **_DEFAULTS} for row in ids],
        )


def downgrade() -> None:
    op.drop_table("health_config")
