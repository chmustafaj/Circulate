"""add draft_payload JSON column to assets

Revision ID: 0004_add_draft_payload
Revises: 0003_asset_snapshots_frozen
Create Date: 2026-04-01

"""

from alembic import op
import sqlalchemy as sa


revision = "0004_add_draft_payload"
down_revision = "0003_asset_snapshots_frozen"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("draft_payload", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("assets", "draft_payload")
