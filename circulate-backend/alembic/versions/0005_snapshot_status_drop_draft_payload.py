"""snapshot status column, nullable hash/frozen_at for DRAFT; drop assets.draft_payload

Revision ID: 0005_snapshot_status
Revises: 0004_add_draft_payload
Create Date: 2026-04-01

"""

from alembic import op
import sqlalchemy as sa


revision = "0005_snapshot_status"
down_revision = "0004_add_draft_payload"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NOT NULL + server_default backfills existing rows without UPDATE (PG 11+).
    # Do not run UPDATE ... SET status — the immutability trigger blocks updates to frozen rows.
    op.add_column(
        "asset_snapshots",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="FROZEN"),
    )
    op.alter_column(
        "asset_snapshots",
        "snapshot_hash_sha256",
        existing_type=sa.String(length=64),
        nullable=True,
    )
    op.alter_column(
        "asset_snapshots",
        "frozen_at",
        existing_type=sa.DateTime(),
        nullable=True,
    )
    op.alter_column(
        "asset_snapshots",
        "status",
        existing_type=sa.String(length=32),
        nullable=False,
        server_default=None,
    )
    op.drop_column("assets", "draft_payload")
    op.create_index("ix_asset_snapshots_status", "asset_snapshots", ["status"])


def downgrade() -> None:
    op.drop_index("ix_asset_snapshots_status", table_name="asset_snapshots")
    op.add_column("assets", sa.Column("draft_payload", sa.JSON(), nullable=True))
    op.alter_column(
        "asset_snapshots",
        "frozen_at",
        existing_type=sa.DateTime(),
        nullable=False,
    )
    op.alter_column(
        "asset_snapshots",
        "snapshot_hash_sha256",
        existing_type=sa.String(length=64),
        nullable=False,
    )
    op.drop_column("asset_snapshots", "status")
