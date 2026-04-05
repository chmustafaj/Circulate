#!/usr/bin/env python3
"""Interactive demo: you type the same inputs a user would at freeze, see Fair-Max math, then DB + pgAdmin.

  cd circulate-backend && PYTHONPATH=src python scripts/demo_fair_max_valuation.py

Needs DATABASE_URL (e.g. in .env) pointing at the Postgres you use in pgAdmin.
Paste the printed SQL into Query Tool; nothing runs SQL from Python.
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
from circulate_backend.domain.valuation.calculator import compute_fair_max
from circulate_backend.domain.valuation.enums import (
    Category,
    Condition,
    MetalProfile,
    Subcategory,
    ValuationMethod,
)
from circulate_backend.domain.valuation.ruleset_loader import CURRENT_RULESET_VERSION, load_ruleset
from circulate_backend.infra.asset_snapshot_immutability import install_asset_snapshot_immutability
from circulate_backend.infra.db import Base, get_engine

import circulate_backend.infra.db_models  # noqa: F401


def _prompt_line(label: str, default: str | None = None) -> str:
    if default is not None:
        hint = f" [{default}]"
    else:
        hint = ""
    raw = input(f"{label}{hint}: ").strip()
    if not raw and default is not None:
        return default
    return raw


def _prompt_int(label: str, default: int | None = None) -> int:
    while True:
        raw = _prompt_line(label, str(default) if default is not None else None)
        if not raw and default is not None:
            return default
        try:
            return int(raw)
        except ValueError:
            print("  Enter a whole number.")


def _pick_enum(label: str, enum_cls: type, default: str | None = None) -> str:
    names = [e.value for e in enum_cls]
    print(f"  ({', '.join(names)})")
    while True:
        raw = _prompt_line(label, default)
        if not raw and default is not None:
            raw = default
        if raw in names:
            return raw
        print(f"  Use one of: {names}")


def _prompt_photo_urls() -> list[str]:
    print("\nPhotos (off-chain URLs — same idea as the real app after upload).")
    raw = _prompt_line(
        "Photo URL(s), comma-separated",
        "https://example.com/asset-photo.jpg",
    )
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return parts if parts else ["https://example.com/asset-photo.jpg"]


def _print_metal_math(
    ruleset: dict,
    profile: str,
    weight_mg: int,
    stone_mg: int,
    cond: str,
    cat: Category,
) -> None:
    net = weight_mg - stone_mg
    cpm = ruleset["metal_cents_per_mg"][profile]
    raw = net * cpm
    cb = ruleset["condition_bps"][cond]
    baseline = raw * cb // 10000
    lo = raw * ruleset["policy"]["metal_floor_bps"] // 10000
    hi = raw * ruleset["policy"]["metal_cap_bps"] // 10000
    r = compute_fair_max(
        valuation_method=ValuationMethod.metal,
        category=cat,
        condition=Condition(cond),
        metal_profile=MetalProfile(profile),
        weight_mg=weight_mg,
        stone_deduction_mg=stone_mg,
        ruleset=ruleset,
    )
    print("\nHow the metal path works (all integer cents):")
    print(f"  Net weight (gross − stone) = {weight_mg} − {stone_mg} = {net} mg")
    print(f"  Raw metal value = {net} × {cpm} (cents/mg for {profile}) = {raw}")
    print(f"  Condition '{cond}' → {cb} bps (10000 = 100%)")
    print(f"  Baseline candidate = {raw} × {cb} // 10000 = {baseline}")
    print(f"  Allowed band on raw value: min {lo}, max {hi}")
    print(f"  Final Fair-Max (matches engine) = {r.fair_max_cents} cents\n")


def _print_product_math(
    ruleset: dict,
    cat_s: str,
    sub_s: str,
    fab_m: int,
    sk_m: int,
    cond: str,
    cat: Category,
) -> None:
    key = f"{cat_s}.{sub_s}"
    anchor = ruleset["category_anchors_cents"][key]
    rf = ruleset["time_rates"]["fabrication_cents_per_minute"]
    rs = ruleset["time_rates"]["skill_cents_per_minute"]
    fab_c = fab_m * rf
    sk_c = sk_m * rs
    pre = anchor + fab_c + sk_c
    r = compute_fair_max(
        valuation_method=ValuationMethod.merchandise,
        category=cat,
        condition=Condition(cond),
        subcategory=Subcategory(sub_s),
        fabrication_minutes=fab_m,
        skill_minutes=sk_m,
        ruleset=ruleset,
    )
    print("\nHow the product path works (materials anchor + time × rates, then condition, then clamp):")
    print(f"  Materials baseline for {key} = {anchor}")
    print(f"  Fabrication: {fab_m} min × {rf} c/min = {fab_c}")
    print(f"  Skill: {sk_m} min × {rs} c/min = {sk_c}")
    print(f"  Pre-condition total = {pre}")
    print(f"  After condition (see engine) → baseline {r.baseline_cents}, band min {r.min_cents} max {r.max_cents}")
    print(f"  Final Fair-Max = {r.fair_max_cents} cents\n")


def _run_once(ruleset: dict) -> None:
    print("\n--- Same choices as freeze /assets/{id}/freeze ---\n")
    path = _pick_enum("Valuation path", ValuationMethod, "metal")

    cat_s = _pick_enum("Category", Category, "jewelry")
    cond_s = _pick_enum("Condition", Condition, "good")
    cat = Category(cat_s)

    serial = _prompt_line("Serial number (optional, Enter to skip)", "")
    desc = _prompt_line("Materials / description (optional, Enter to skip)", "")
    photo_urls = _prompt_photo_urls()

    freeze_data: dict = {
        "valuation_method": path,
        "category": cat_s,
        "condition": cond_s,
        "photo_urls": photo_urls,
    }
    if serial:
        freeze_data["serial_number"] = serial
    if desc:
        freeze_data["materials_description"] = desc

    if path == "metal":
        print("\nMetal inputs (scale + assay):")
        prof = _pick_enum("Metal profile", MetalProfile, "gold_14k")
        wmg = _prompt_int("Gross weight in milligrams", 24300)
        stone = _prompt_int("Stone / non-metal deduction (mg)", 0)
        freeze_data["metal"] = {
            "metal_profile": prof,
            "weight_mg": wmg,
            "stone_deduction_mg": stone,
        }
        _print_metal_math(ruleset, prof, wmg, stone, cond_s, cat)
    else:
        anchor_keys = list(ruleset["category_anchors_cents"].keys())
        print("\nProduct inputs: category + subcategory must match a row in the ruleset.")
        print(f"  Valid combos: {', '.join(anchor_keys)}")
        sub_s = _pick_enum("Subcategory", Subcategory, "wristwatch")
        key = f"{cat_s}.{sub_s}"
        if key not in ruleset["category_anchors_cents"]:
            print(f"\n  No anchor for '{key}'. Pick category+subcategory from the list above. Restart the script.\n")
            return
        fab_m = _prompt_int("Fabrication minutes (integer)", 100)
        sk_m = _prompt_int("Skill / expertise minutes (integer)", 200)
        freeze_data["merchandise"] = {
            "subcategory": sub_s,
            "fabrication_minutes": fab_m,
            "skill_minutes": sk_m,
        }
        _print_product_math(ruleset, cat_s, sub_s, fab_m, sk_m, cond_s, cat)

    input("Press Enter to create the asset and freeze with these values… ")

    asset, _ = create_asset()
    snapshot = freeze_snapshot(asset.id, freeze_data)
    aid, sid = str(asset.id), str(snapshot.id)
    fm = snapshot.snapshot_payload["fair_max_cents"]

    print(f"\nasset_id={aid}\nsnapshot_id={sid}\nfair_max_cents={fm}\n")

    print("--- PostgreSQL (pgAdmin → Query Tool) ---\n")
    print(f"SELECT id, status FROM assets WHERE id = '{aid}'::uuid;\n")
    print(
        f"SELECT jsonb_pretty(snapshot_payload::jsonb)\n"
        f"FROM asset_snapshots WHERE id = '{sid}'::uuid;\n"
    )

    print("\n--- Verify hash via API (same DB as this script) ---")
    print("Start API:  PYTHONPATH=src uvicorn circulate_backend.api.main:app --reload\n")
    verify = {"snapshot_id": sid, "payload": dict(snapshot.snapshot_payload)}
    vj = json.dumps(verify)
    print("curl:")
    print(
        "  curl -s -X POST http://127.0.0.1:8000/verify/snapshot "
        '-H "Content-Type: application/json" '
        f"-d {shlex.quote(vj)}\n"
    )
    print('Expect: {"valid":true,...} or similar.\n')


def main() -> None:
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    install_asset_snapshot_immutability(engine)

    ruleset = load_ruleset()
    print(f"\nRuleset loaded: {ruleset['version']} (file {CURRENT_RULESET_VERSION})\n")

    while True:
        _run_once(ruleset)
        again = input("Run again with different inputs? (y/N): ").strip().lower()
        if again not in ("y", "yes"):
            break
    print("Done.\n")


if __name__ == "__main__":
    main()
