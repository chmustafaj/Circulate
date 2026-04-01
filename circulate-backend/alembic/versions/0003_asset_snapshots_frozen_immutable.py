"""enforce immutability for frozen asset_snapshots

Revision ID: 0003_asset_snapshots_frozen
Revises: 0002_event_log_append_only
Create Date: 2026-03-31

"""

from alembic import op

from circulate_backend.infra.asset_snapshot_immutability import (
    alembic_postgresql_downgrade,
    alembic_postgresql_upgrade,
)


revision = "0003_asset_snapshots_frozen"
down_revision = "0002_event_log_append_only"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return
    for stmt in alembic_postgresql_upgrade():
        op.execute(stmt)


def downgrade() -> None:
    bind = op.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return
    for stmt in alembic_postgresql_downgrade():
        op.execute(stmt)
