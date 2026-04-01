"""Database-level rules: frozen asset_snapshots rows (frozen_at IS NOT NULL) are immutable."""

from __future__ import annotations

from sqlalchemy import Engine, text
from sqlalchemy.engine import Connection


def _postgresql_upgrade_statements() -> list[str]:
    return [
        """
        CREATE OR REPLACE FUNCTION prevent_mutable_asset_snapshot()
        RETURNS TRIGGER AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            IF OLD.frozen_at IS NOT NULL THEN
              RAISE EXCEPTION 'cannot delete frozen asset_snapshot %', OLD.id;
            END IF;
            RETURN OLD;
          ELSIF TG_OP = 'UPDATE' THEN
            IF OLD.frozen_at IS NOT NULL THEN
              RAISE EXCEPTION 'cannot update frozen asset_snapshot %', OLD.id;
            END IF;
            RETURN NEW;
          END IF;
          RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """,
        """
        DROP TRIGGER IF EXISTS trg_asset_snapshots_immutable_when_frozen ON asset_snapshots;
        """,
        """
        CREATE TRIGGER trg_asset_snapshots_immutable_when_frozen
        BEFORE UPDATE OR DELETE ON asset_snapshots
        FOR EACH ROW
        EXECUTE FUNCTION prevent_mutable_asset_snapshot();
        """,
    ]


def _postgresql_downgrade_statements() -> list[str]:
    return [
        "DROP TRIGGER IF EXISTS trg_asset_snapshots_immutable_when_frozen ON asset_snapshots;",
        "DROP FUNCTION IF EXISTS prevent_mutable_asset_snapshot();",
    ]


def _sqlite_upgrade_statements() -> list[str]:
    return [
        "DROP TRIGGER IF EXISTS trg_asset_snapshots_no_update_when_frozen;",
        """
        CREATE TRIGGER trg_asset_snapshots_no_update_when_frozen
        BEFORE UPDATE ON asset_snapshots
        FOR EACH ROW
        WHEN OLD.frozen_at IS NOT NULL
        BEGIN
          SELECT RAISE(ABORT, 'cannot update frozen asset_snapshot');
        END;
        """,
        "DROP TRIGGER IF EXISTS trg_asset_snapshots_no_delete_when_frozen;",
        """
        CREATE TRIGGER trg_asset_snapshots_no_delete_when_frozen
        BEFORE DELETE ON asset_snapshots
        FOR EACH ROW
        WHEN OLD.frozen_at IS NOT NULL
        BEGIN
          SELECT RAISE(ABORT, 'cannot delete frozen asset_snapshot');
        END;
        """,
    ]


def install_asset_snapshot_immutability(engine: Engine) -> None:
    """Install dialect-appropriate triggers (PostgreSQL or SQLite). Idempotent."""
    dialect = engine.dialect.name
    if dialect == "postgresql":
        stmts = _postgresql_upgrade_statements()
    elif dialect == "sqlite":
        stmts = _sqlite_upgrade_statements()
    else:
        return
    with engine.begin() as conn:
        _run_statements(conn, stmts)


def _run_statements(conn: Connection, statements: list[str]) -> None:
    for raw in statements:
        conn.execute(text(raw.strip()))


def alembic_postgresql_upgrade() -> list[str]:
    return _postgresql_upgrade_statements()


def alembic_postgresql_downgrade() -> list[str]:
    return _postgresql_downgrade_statements()
