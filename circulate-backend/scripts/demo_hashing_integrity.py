#!/usr/bin/env python3
"""Interactive demo: snapshot SHA256, manual /verify/snapshot in Postman or curl, pgAdmin.

  PYTHONPATH=src python scripts/demo_hashing_integrity.py

Requires DATABASE_URL. Each step prints PostgreSQL for pgAdmin Query Tool (Postgres).
Step 2 also prints Postman/curl for /verify/snapshot. Nothing runs SQL from Python.
"""

from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
import os

os.environ["LOG_LEVEL"] = "ERROR"

from circulate_backend.infra.logging import configure_logging

configure_logging()

from circulate_backend.domain.asset_service import create_asset, freeze_snapshot
from circulate_backend.infra.asset_snapshot_immutability import install_asset_snapshot_immutability
from circulate_backend.infra.db import Base, get_engine

import circulate_backend.infra.db_models  # noqa: F401 — register models


def pause(msg: str) -> None:
    try:
        input(msg)
    except EOFError:
        pass


def banner(n: int, title: str) -> None:
    print("\n" + "=" * 60 + f"\n STEP {n}: {title}\n" + "=" * 60)


def pg_header(what: str) -> None:
    print(f"\n--- PostgreSQL (pgAdmin → Query Tool) — {what} ---\n")


def main() -> None:
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    install_asset_snapshot_immutability(engine)

    freeze_request = {
        "valuation_method": "metal",
        "category": "jewelry",
        "condition": "good",
        "serial_number": "SN-DEMO-001",
        "materials_description": "gold",
        "metal": {
            "metal_profile": "gold_14k",
            "weight_mg": 24300,
        },
        "photo_urls": ["https://example.com/demo-watch.jpg"],
    }

    print("\nSnapshot hash demo — press Enter after each pgAdmin check.\n")
    pause("Enter to create asset + freeze snapshot… ")

    banner(1, "Frozen snapshot")
    asset, _draft_snap = create_asset()
    snapshot = freeze_snapshot(asset.id, freeze_request)
    sid, aid = str(snapshot.id), str(asset.id)
    print(f"asset_id={aid}\nsnapshot_id={sid}\nhash={snapshot.snapshot_hash_sha256}")
    pg_header("inspect rows after freeze (paste each query; expect one row each)")
    print(
        f"SELECT id, status, is_archived, created_at, updated_at\n"
        f"FROM assets\n"
        f"WHERE id = '{aid}'::uuid;\n"
    )
    print(
        f"SELECT id, asset_id, snapshot_version, status, snapshot_hash_sha256, snapshot_payload, frozen_at\n"
        f"FROM asset_snapshots\n"
        f"WHERE id = '{sid}'::uuid;\n"
    )
    print(
        "SELECT id, subject_type, subject_id, sha256, created_at\n"
        "FROM hash_log\n"
        "WHERE subject_type = 'asset_snapshot'\n"
        f"  AND subject_id = '{sid}';\n"
    )
    print(
        "Expect: assets.status = FROZEN; snapshot_hash_sha256 matches printed hash;\n"
        "hash_log.sha256 matches asset_snapshots.snapshot_hash_sha256.\n"
    )
    pause("Enter for Step 2… ")

    banner(2, "Verify via Postman or curl (you run the request)")
    verify_body = {"snapshot_id": sid, "payload": dict(snapshot.snapshot_payload)}
    verify_json = json.dumps(verify_body)
    verify_json_pretty = json.dumps(verify_body, indent=2)

    print(
        "\n1) Start the API in another terminal (same DATABASE_URL as this script), from circulate-backend:\n"
        "     PYTHONPATH=src uvicorn circulate_backend.api.main:app --reload\n"
    )
    print("2) Postman:\n"
          "     Method:  POST\n"
          "     URL:     http://127.0.0.1:8000/verify/snapshot\n"
          "     Headers: Content-Type  application/json\n"
          "     Body:    raw  JSON  — paste the block below.\n")
    print("--- paste as Body (raw JSON) ---")
    print(verify_json_pretty)
    print("--- end ---\n")
    print("     Expected response: 200 and  {\"valid\": true}\n")
    print(
        "3) curl (same request):\n   "
        + "curl -s -X POST http://127.0.0.1:8000/verify/snapshot "
        + '-H "Content-Type: application/json" '
        + f"-d {shlex.quote(verify_json)}\n"
    )

    pause(
        "When you have run POST /verify/snapshot and seen the response, press Enter for Step 3… "
    )

    banner(3, "Tamper in pgAdmin (SQL only — not run from this script)")
    print(
        "Same database as this demo. With migration 0003 applied, each statement should ERROR.\n"
        "(SQLite uses different syntax; run these against PostgreSQL in pgAdmin.)\n"
    )
    pg_header("tamper attempts (expect errors from trigger)")
    print("UPDATE (try to change a column):")
    print(
        f"UPDATE asset_snapshots\n"
        f"SET snapshot_version = snapshot_version + 1\n"
        f"WHERE id = '{sid}'::uuid;\n"
    )
    print("--- DELETE ---")
    print(f"DELETE FROM asset_snapshots\nWHERE id = '{sid}'::uuid;\n")
    print(
        "Expected (PostgreSQL): error mentions cannot update frozen asset_snapshot or\n"
        "cannot delete frozen asset_snapshot (trigger prevent_mutable_asset_snapshot).\n"
    )
    pause(
        "After you have run the SQL in pgAdmin and seen the database reject it, press Enter for Step 4… "
    )

    banner(4, "Verify unchanged (pgAdmin SQL — you run the queries)")
    print(
        "After the failed UPDATE/DELETE, the row should be unchanged. Run in Query Tool:\n"
    )
    print("--- Inspect the frozen snapshot row ---")
    print(
        f"SELECT id, snapshot_version, status, snapshot_hash_sha256, snapshot_payload, frozen_at\n"
        f"FROM asset_snapshots\n"
        f"WHERE id = '{sid}'::uuid;\n"
    )
    print("Done.\n")


if __name__ == "__main__":
    main()
