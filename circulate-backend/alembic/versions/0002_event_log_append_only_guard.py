"""enforce append-only event_log

Revision ID: 0002_event_log_append_only
Revises: 0001_core
Create Date: 2026-03-24

"""

from alembic import op


revision = "0002_event_log_append_only"
down_revision = "0001_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_event_log_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'event_log is append-only: % is not allowed', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER event_log_no_update_delete
        BEFORE UPDATE OR DELETE ON event_log
        FOR EACH ROW
        EXECUTE FUNCTION prevent_event_log_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS event_log_no_update_delete ON event_log;")
    op.execute("DROP FUNCTION IF EXISTS prevent_event_log_mutation();")
