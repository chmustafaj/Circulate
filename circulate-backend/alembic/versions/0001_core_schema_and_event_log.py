"""core schema and event_log

Revision ID: 0001_core
Revises:
Create Date: 2026-03-16

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_core"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_id", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_event_log_event_type", "event_log", ["event_type"])
    op.create_index("ix_event_log_aggregate_type", "event_log", ["aggregate_type"])
    op.create_index("ix_event_log_aggregate_id", "event_log", ["aggregate_id"])
    op.create_index("ix_event_log_created_at", "event_log", ["created_at"])

    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_assets_status", "assets", ["status"])

    op.create_table(
        "asset_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_version", sa.Integer(), nullable=False),
        sa.Column("snapshot_payload", sa.JSON(), nullable=False),
        sa.Column("snapshot_hash_sha256", sa.String(length=64), nullable=False),
        sa.Column("frozen_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_asset_snapshots_asset_id", "asset_snapshots", ["asset_id"])
    op.create_index("ix_asset_snapshots_snapshot_hash_sha256", "asset_snapshots", ["snapshot_hash_sha256"])
    op.create_index("ix_asset_snapshots_frozen_at", "asset_snapshots", ["frozen_at"])

    op.create_table(
        "holds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_holds_status", "holds", ["status"])

    op.create_table(
        "queues",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_queues_asset_id", "queues", ["asset_id"])
    op.create_index("ix_queues_position", "queues", ["position"])

    op.create_table(
        "pawn_loans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("principal_cents", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_pawn_loans_asset_id", "pawn_loans", ["asset_id"])
    op.create_index("ix_pawn_loans_status", "pawn_loans", ["status"])

    op.create_table(
        "attestations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_attestations_asset_id", "attestations", ["asset_id"])

    op.create_table(
        "custody_transitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_party", sa.String(length=128), nullable=False),
        sa.Column("to_party", sa.String(length=128), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_custody_transitions_asset_id", "custody_transitions", ["asset_id"])
    op.create_index("ix_custody_transitions_occurred_at", "custody_transitions", ["occurred_at"])

    op.create_table(
        "trm_state",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("state_payload", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "hash_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("subject_type", sa.String(length=64), nullable=False),
        sa.Column("subject_id", sa.String(length=64), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_hash_log_subject_type", "hash_log", ["subject_type"])
    op.create_index("ix_hash_log_subject_id", "hash_log", ["subject_id"])
    op.create_index("ix_hash_log_sha256", "hash_log", ["sha256"])
    op.create_index("ix_hash_log_created_at", "hash_log", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_hash_log_created_at", table_name="hash_log")
    op.drop_index("ix_hash_log_sha256", table_name="hash_log")
    op.drop_index("ix_hash_log_subject_id", table_name="hash_log")
    op.drop_index("ix_hash_log_subject_type", table_name="hash_log")
    op.drop_table("hash_log")

    op.drop_table("trm_state")

    op.drop_index("ix_custody_transitions_occurred_at", table_name="custody_transitions")
    op.drop_index("ix_custody_transitions_asset_id", table_name="custody_transitions")
    op.drop_table("custody_transitions")

    op.drop_index("ix_attestations_asset_id", table_name="attestations")
    op.drop_table("attestations")

    op.drop_index("ix_pawn_loans_status", table_name="pawn_loans")
    op.drop_index("ix_pawn_loans_asset_id", table_name="pawn_loans")
    op.drop_table("pawn_loans")

    op.drop_index("ix_queues_position", table_name="queues")
    op.drop_index("ix_queues_asset_id", table_name="queues")
    op.drop_table("queues")

    op.drop_index("ix_holds_status", table_name="holds")
    op.drop_table("holds")

    op.drop_index("ix_asset_snapshots_frozen_at", table_name="asset_snapshots")
    op.drop_index("ix_asset_snapshots_snapshot_hash_sha256", table_name="asset_snapshots")
    op.drop_index("ix_asset_snapshots_asset_id", table_name="asset_snapshots")
    op.drop_table("asset_snapshots")

    op.drop_index("ix_assets_status", table_name="assets")
    op.drop_table("assets")

    op.drop_index("ix_event_log_created_at", table_name="event_log")
    op.drop_index("ix_event_log_aggregate_id", table_name="event_log")
    op.drop_index("ix_event_log_aggregate_type", table_name="event_log")
    op.drop_index("ix_event_log_event_type", table_name="event_log")
    op.drop_table("event_log")

