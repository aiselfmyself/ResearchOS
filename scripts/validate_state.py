#!/usr/bin/env python3
"""Minimal deterministic validator for ResearchOS research ledgers.

Scope (deliberately small -- see docs/minimal-core-and-ci.md):
  * JSON well-formedness of the five *research* ledgers under state/:
    sources / evidence / claims / verifications / hypotheses.
  * Schema checks driven by schemas/*.json: required fields, types, enums,
    array item types. Extra fields are allowed (as in JSON Schema draft-07
    when additionalProperties is unset).
  * ID uniqueness within each ledger.
  * Record-ID format: new records use PREFIX-YYYYMMDD-xxxx so that two
    branches cannot mint the same ID; the pre-2026-10-20 sequential IDs are
    grandfathered up to a frozen maximum (docs/record-id-scheme.md).
  * Referential integrity between ledgers:
      evidence.source_id        -> sources
      claim.evidence_ids        -> evidence
      claim.counterclaim_ids    -> claims
      hypothesis.evidence_ids   -> evidence
      verification.target_id    -> sources | evidence | claims | hypotheses

Non-goals (frozen by design, not missing by accident):
  * No governance ledgers (sessions / proposals / reviews / approvals /
    review_queue), no role checks, no commit-trailer checks, no append-only
    hash chains. Those mechanisms live on the archived arena/* branches and
    are intentionally NOT part of the minimal core because their pursuit of
    formal completeness blocked all progress (see
    docs/stagnation-analysis-2026-10-20.md).
  * No network access. arXiv re-verification of citations is a separate,
    explicitly-run step, not a CI gate.

Usage:
    python3 scripts/validate_state.py [--quiet]

Exit code 0 = all checks pass, 1 = at least one error.
Standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]

# collection -> (ledger file, schema file, id key)
COLLECTIONS: Dict[str, Tuple[str, str, str]] = {
    "sources": ("state/sources.jsonl", "schemas/source.json", "source_id"),
    "evidence": ("state/evidence.jsonl", "schemas/evidence.json", "evidence_id"),
    "claims": ("state/claims.jsonl", "schemas/claim.json", "claim_id"),
    "verifications": (
        "state/verifications.jsonl",
        "schemas/verification.json",
        "verification_id",
    ),
    "hypotheses": (
        "state/hypotheses.jsonl",
        "schemas/hypothesis.json",
        "hypothesis_id",
    ),
}

# ---------------------------------------------------------------------------
# Record-ID scheme (see docs/record-id-scheme.md)
#
# Sequential IDs collide when two branches append to the same ledger: both
# read the same max(ID) and mint the same next number. New records therefore
# use ``PREFIX-YYYYMMDD-xxxx``, where ``xxxx`` is a random 4-hex suffix, so
# two independent sessions cannot mint the same ID. Once minted, an ID is
# never changed (references depend on it).
#
# The 49 records that predate this scheme keep their sequential IDs. They are
# grandfathered by *number*, not by listing them: a legacy ID is accepted only
# if it is at or below the frozen maximum below. Anything beyond that range is
# a new record and must use the new format.
# ---------------------------------------------------------------------------
ID_PREFIXES: Dict[str, str] = {
    "sources": "SRC",
    "evidence": "EVD",
    "claims": "CLM",
    "verifications": "VER",
    "hypotheses": "HYP",
}

# Frozen at 2026-10-20 when the non-sequential scheme was adopted.
# Do not raise these numbers; mint new records with a YYYYMMDD suffix instead.
LEGACY_MAX: Dict[str, int] = {
    "SRC": 4,
    "EVD": 14,
    "CLM": 7,
    "VER": 21,
    "HYP": 3,
}

ID_PATTERN = re.compile(r"^(?P<prefix>[A-Z]{3})-(?P<date>\d{8})-(?P<suffix>[0-9a-f]{4})$")
LEGACY_PATTERN = re.compile(r"^(?P<prefix>[A-Z]{3})-(?P<num>\d{3})$")


def load_jsonl(path: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Return (records, errors). Every line must be a JSON object."""
    records: List[Dict[str, Any]] = []
    errors: List[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return records, [f"{path}: file not found"]
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path}:{lineno}: invalid JSON: {exc}")
            continue
        if not isinstance(record, dict):
            errors.append(f"{path}:{lineno}: line is not a JSON object")
            continue
        records.append(record)
    return records, errors


def _check_type(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return True  # unknown type name: do not fail, schema bug is separate


def validate_record(
    record: Dict[str, Any], schema: Dict[str, Any], label: str
) -> List[str]:
    """Validate one record against a JSON-Schema-subset schema."""
    errors: List[str] = []
    properties = schema.get("properties", {})
    for field in schema.get("required", []):
        if field not in record:
            errors.append(f"{label}: missing required field '{field}'")
    for field, subschema in properties.items():
        if field not in record:
            continue
        value = record[field]
        expected = subschema.get("type")
        if expected and not _check_type(value, expected):
            errors.append(
                f"{label}: field '{field}' must be {expected}, "
                f"got {type(value).__name__}"
            )
            continue
        if "enum" in subschema and value not in subschema["enum"]:
            errors.append(
                f"{label}: field '{field}' value {value!r} "
                f"not in {subschema['enum']}"
            )
        items = subschema.get("items")
        if isinstance(items, dict) and isinstance(value, list):
            item_type = items.get("type")
            if item_type:
                for index, item in enumerate(value):
                    if not _check_type(item, item_type):
                        errors.append(
                            f"{label}: field '{field}[{index}]' must be "
                            f"{item_type}, got {type(item).__name__}"
                        )
    return errors


def check_uniqueness(
    records: List[Dict[str, Any]], id_key: str, ledger: str
) -> List[str]:
    errors: List[str] = []
    seen: Dict[str, int] = {}
    for lineno, record in enumerate(records, start=1):
        rid = record.get(id_key)
        if not isinstance(rid, str):
            errors.append(f"{ledger}:{lineno}: missing or non-string {id_key!r}")
            continue
        if rid in seen:
            errors.append(
                f"{ledger}:{lineno}: duplicate {id_key} {rid!r} "
                f"(first seen at line {seen[rid]})"
            )
        else:
            seen[rid] = lineno
    return errors


def check_id_format(
    records: List[Dict[str, Any]], id_key: str, ledger: str, prefix: str
) -> List[str]:
    """Enforce the non-sequential ID scheme (docs/record-id-scheme.md).

    Accepted:
      * ``PREFIX-YYYYMMDD-xxxx`` (the current scheme); and
      * ``PREFIX-NNN`` only up to ``LEGACY_MAX[prefix]`` (grandfathered).
    """
    errors: List[str] = []
    legacy_max = LEGACY_MAX.get(prefix, 0)
    for lineno, record in enumerate(records, start=1):
        rid = record.get(id_key)
        if not isinstance(rid, str):
            continue  # reported by check_uniqueness
        match = ID_PATTERN.match(rid)
        if match:
            if match.group("prefix") != prefix:
                errors.append(
                    f"{ledger}:{lineno}: ID {rid!r} must start with {prefix!r}"
                )
            continue
        match = LEGACY_PATTERN.match(rid)
        if match:
            if match.group("prefix") != prefix:
                errors.append(
                    f"{ledger}:{lineno}: ID {rid!r} must start with {prefix!r}"
                )
            elif int(match.group("num")) > legacy_max:
                errors.append(
                    f"{ledger}:{lineno}: ID {rid!r} extends the frozen sequential "
                    f"range (max {prefix}-{legacy_max:03d}); mint one with "
                    f"'python3 scripts/new_id.py {prefix}' instead"
                )
            continue
        errors.append(
            f"{ledger}:{lineno}: ID {rid!r} must look like "
            f"{prefix}-YYYYMMDD-xxxx (mint one with scripts/new_id.py)"
        )
    return errors


def check_references(data: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    errors: List[str] = []
    ids = {
        name: {
            r.get(COLLECTIONS[name][2])
            for r in records
            if isinstance(r.get(COLLECTIONS[name][2]), str)
        }
        for name, records in data.items()
    }

    def _exists(target: str) -> bool:
        return any(target in known for known in ids.values())

    for record in data["evidence"]:
        src = record.get("source_id")
        if isinstance(src, str) and src not in ids["sources"]:
            errors.append(
                f"evidence {record.get('evidence_id')}: unknown source_id {src!r}"
            )
    for record in data["claims"]:
        cid = record.get("claim_id")
        for eid in record.get("evidence_ids", []) or []:
            if eid not in ids["evidence"]:
                errors.append(f"claim {cid}: unknown evidence_id {eid!r}")
        for cc in record.get("counterclaim_ids", []) or []:
            if cc not in ids["claims"]:
                errors.append(f"claim {cid}: unknown counterclaim_id {cc!r}")
    for record in data["hypotheses"]:
        hid = record.get("hypothesis_id")
        for eid in record.get("evidence_ids", []) or []:
            if eid not in ids["evidence"]:
                errors.append(f"hypothesis {hid}: unknown evidence_id {eid!r}")
    for record in data["verifications"]:
        vid = record.get("verification_id")
        target = record.get("target_id")
        if isinstance(target, str) and not _exists(target):
            errors.append(f"verification {vid}: unknown target_id {target!r}")
    return errors


def run_all_checks(root: Path = ROOT) -> Dict[str, List[str]]:
    errors: List[str] = []
    data: Dict[str, List[Dict[str, Any]]] = {}
    for name, (ledger_rel, schema_rel, id_key) in COLLECTIONS.items():
        records, load_errors = load_jsonl(root / ledger_rel)
        errors.extend(load_errors)
        try:
            schema = json.loads((root / schema_rel).read_text(encoding="utf-8"))
        except FileNotFoundError:
            errors.append(f"{schema_rel}: schema file not found")
            data[name] = records
            continue
        label = schema.get("title", name)
        for record in records:
            errors.extend(validate_record(record, schema, label))
        errors.extend(check_uniqueness(records, id_key, ledger_rel))
        errors.extend(
            check_id_format(records, id_key, ledger_rel, ID_PREFIXES[name])
        )
        data[name] = records
    errors.extend(check_references(data))
    return {"errors": errors}


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate research ledgers")
    parser.add_argument("--quiet", action="store_true", help="only print errors")
    args = parser.parse_args(argv)
    report = run_all_checks(ROOT)
    if report["errors"]:
        print("FAIL: research ledger validation errors:")
        for err in report["errors"]:
            print(f"  - {err}")
        return 1
    if not args.quiet:
        counts = ", ".join(
            f"{name}={len(load_jsonl(ROOT / rel)[0])}"
            for name, (rel, _, _) in COLLECTIONS.items()
        )
        print(f"PASS: research ledgers valid ({counts})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
