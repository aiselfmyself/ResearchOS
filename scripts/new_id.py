#!/usr/bin/env python3
"""Mint a record ID for the research ledgers.

Sequential IDs (``EVD-015``) collide when two branches append to the same
``state/*.jsonl`` ledger: both read the same maximum and mint the same number,
which shows up as a git add/add conflict or as a duplicate-ID validation error
after a union merge. This tool mints ``PREFIX-YYYYMMDD-xxxx`` instead, where
``xxxx`` is a random 4-hex suffix, so independent sessions cannot collide.

The ID is checked against the existing ledger before it is printed. Once an ID
is written into a record it must never change, because other records reference
it.

Usage:
    python3 scripts/new_id.py SRC
    python3 scripts/new_id.py EVD --count 3
    python3 scripts/new_id.py CLM --date 20261020 --ledger state/claims.jsonl

Standard library only. See docs/record-id-scheme.md.
"""
from __future__ import annotations

import argparse
import json
import secrets
import sys
from datetime import date
from pathlib import Path
from typing import Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]

PREFIXES = {
    "SRC": "state/sources.jsonl",
    "EVD": "state/evidence.jsonl",
    "CLM": "state/claims.jsonl",
    "VER": "state/verifications.jsonl",
    "HYP": "state/hypotheses.jsonl",
}

ID_KEYS = {
    "SRC": "source_id",
    "EVD": "evidence_id",
    "CLM": "claim_id",
    "VER": "verification_id",
    "HYP": "hypothesis_id",
}


def _existing_ids(path: Path, id_key: str) -> set:
    if not path.exists():
        return set()
    ids = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        rid = record.get(id_key) if isinstance(record, dict) else None
        if isinstance(rid, str):
            ids.add(rid)
    return ids


def mint(
    prefix: str,
    day: Optional[str] = None,
    taken: Optional[Iterable[str]] = None,
) -> str:
    """Return one unused ``PREFIX-YYYYMMDD-xxxx`` ID."""
    if prefix not in PREFIXES:
        raise ValueError(f"unknown prefix {prefix!r}; expected one of {sorted(PREFIXES)}")
    stamp = day or date.today().strftime("%Y%m%d")
    if len(stamp) != 8 or not stamp.isdigit():
        raise ValueError(f"--date must be YYYYMMDD, got {stamp!r}")
    seen = set(taken or ())
    for _ in range(1000):
        candidate = f"{prefix}-{stamp}-{secrets.token_hex(2)}"
        if candidate not in seen:
            return candidate
    raise RuntimeError("could not mint a unique ID; check the ledger for corruption")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Mint a research-ledger record ID")
    parser.add_argument("prefix", choices=sorted(PREFIXES), help="record prefix")
    parser.add_argument(
        "--count", type=int, default=1, help="how many IDs to mint (default 1)"
    )
    parser.add_argument(
        "--date", default=None, help="YYYYMMDD stamp (default: today, UTC-free local date)"
    )
    parser.add_argument(
        "--ledger",
        default=None,
        help="ledger file to check for collisions (default: derived from prefix)",
    )
    args = parser.parse_args(argv)

    if args.count < 1:
        parser.error("--count must be at least 1")

    ledger = Path(args.ledger) if args.ledger else ROOT / PREFIXES[args.prefix]
    if not ledger.is_absolute():
        # Resolve against the repository root, so the collision check cannot be
        # silently skipped by running this from another directory.
        ledger = ROOT / ledger
    taken = _existing_ids(ledger, ID_KEYS[args.prefix])

    for _ in range(args.count):
        new_id = mint(args.prefix, day=args.date, taken=taken)
        taken.add(new_id)
        print(new_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
