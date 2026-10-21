#!/usr/bin/env python3
"""Create the name of a new ledger / snapshot shard, and optionally the file.

WHY THIS EXISTS
---------------
Since the 2026-10-21 sharding migration (contributions/2026-10-21_ledger_sharding_migration.md)
a new ledger record does not go into `state/<name>.jsonl` (that file is the
frozen base) but into a **new file** per session or work batch:

    state/<name>.d/<YYYY-MM-DD>-<12 hex>.jsonl
    tests/fixtures/arxiv_metadata_snapshot.d/<YYYY-MM-DD>-<12 hex>.json

The convention is what makes parallel branches mergeable, and the loader is
strict about it: a shard with a wrong name is reported instead of being read
silently. Getting the name right by hand is easy to get wrong -- during the
migration's own experiments a shard was written without its `.jsonl` suffix
and was therefore not read at all. This tool is the deterministic way to get
a valid name, and to create the directory (git does not track empty
directories, so the first shard in a ledger has nowhere to go otherwise).

USAGE
-----
    python3 scripts/new_ledger_shard.py evidence
        state/evidence.d/2026-10-21-3f9ac21b7d40.jsonl

    python3 scripts/new_ledger_shard.py evidence --create
        same, and create an empty file ready for one JSON record per line

    python3 scripts/new_ledger_shard.py arxiv_snapshot --create
        tests/fixtures/arxiv_metadata_snapshot.d/2026-10-21-<hex>.json,
        written with `entries: []` and provenance fields to fill in

    python3 scripts/new_ledger_shard.py --list
        show every target and whether its shard directory exists

`--date` pins the date part (default: today, local date). The 12 hex character
suffix is random (48 bits) from `secrets.token_hex(6)`: the date alone would
collide between sessions running on the same day.

WHAT IT DOES NOT DO
-------------------
It does not mint record IDs (`scripts/new_id.py` does), does not write records,
and does not touch the frozen base. A shard file is written once by one session
and never edited afterwards; a correction is a new shard.

Exit codes: 0 = path printed (and file created with --create),
2 = usage / I/O error, 3 = the target directory holds a file the loader would
not read (fix that first: the new shard would hide next to a broken one).
Standard library only.
"""
from __future__ import annotations

import argparse
import json
import secrets
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]

try:
    import ledger_store
    import validate_state as vs
except ImportError:  # running as scripts/new_ledger_shard.py
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import ledger_store
    import validate_state as vs

#: target name -> base file (relative to the repository root)
TARGETS: Dict[str, str] = {
    name: rel for name, (rel, _schema, _id_key) in vs.COLLECTIONS.items()
}
#: the citation snapshot follows the same base + parts rule with a JSON suffix
SNAPSHOT_TARGET = "arxiv_snapshot"
TARGETS[SNAPSHOT_TARGET] = "tests/fixtures/arxiv_metadata_snapshot.json"

SNAPSHOT_PART_SCHEMA = "researchos/arxiv-metadata-snapshot-part/v1"


def target_suffix(target: str) -> str:
    return ledger_store.SNAPSHOT_SUFFIX if target == SNAPSHOT_TARGET else ledger_store.SHARD_SUFFIX


def name_pattern(target: str):
    return (
        ledger_store.SNAPSHOT_SHARD_NAME_RE
        if target == SNAPSHOT_TARGET
        else ledger_store.SHARD_NAME_RE
    )


def shard_name(target: str, day: str) -> str:
    """Return a shard file name that matches the loader's convention."""
    if len(day) != 8 or not day.isdigit():
        raise ValueError(f"day must be YYYYMMDD, got {day!r}")
    stamp = f"{day[:4]}-{day[4:6]}-{day[6:]}"
    name = f"{stamp}-{secrets.token_hex(6)}{target_suffix(target)}"
    if not name_pattern(target).match(name):  # pragma: no cover - defensive
        raise RuntimeError(f"generated name does not match the convention: {name}")
    return name


def snapshot_template(day: str) -> str:
    """A valid part document; the provenance fields are for the author to fill."""
    document = {
        "schema": SNAPSHOT_PART_SCHEMA,
        "captured_at": f"{day[:4]}-{day[4:6]}-{day[6:]}",
        "capture_method": "TODO: how the metadata was obtained (e.g. arxiv abs page read via web fetch)",
        "capture_note": "TODO: which arXiv ID was added and why; the base snapshot stays frozen",
        "entries": [],
    }
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def plan(target: str, day: Optional[str], create: bool) -> Dict[str, object]:
    """Return {'path', 'created', 'warnings'} for one new shard."""
    base = ROOT / TARGETS[target]
    warnings: List[str] = []
    if not base.exists():
        raise FileNotFoundError(f"base file not found: {base}")
    directory = ledger_store.shard_dir(base)
    name = shard_name(target, day or date.today().strftime("%Y%m%d"))
    path = directory / name
    # Report a directory that already contains a file the loader will not read:
    # adding a correctly-named shard next to it would leave the problem hidden.
    for stray in ledger_store.unread_shard_like_files(base, target_suffix(target), name_pattern(target)):
        warnings.append(f"already present and NOT read by the loader: {stray.relative_to(ROOT)}")
    created = False
    if create:
        directory.mkdir(parents=True, exist_ok=True)
        if target == SNAPSHOT_TARGET:
            path.write_text(snapshot_template(day or date.today().strftime("%Y%m%d")), encoding="utf-8")
        else:
            path.write_text("", encoding="utf-8")
        created = True
    return {"path": path, "created": created, "warnings": warnings, "directory": directory}


def describe_targets() -> List[str]:
    lines = []
    for target in sorted(TARGETS):
        base = ROOT / TARGETS[target]
        directory = ledger_store.shard_dir(base)
        existing = len(ledger_store.shard_files(base, target_suffix(target)))
        state = "exists" if directory.is_dir() else "missing"
        lines.append(f"{target:16s} base={TARGETS[target]:48s} shard_dir={state} shards={existing}")
    return lines


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("target", nargs="?", help=f"one of: {', '.join(sorted(TARGETS))}")
    parser.add_argument("--date", default=None, help="YYYYMMDD (default: today)")
    parser.add_argument(
        "--create", action="store_true", help="also create the file (and its directory)"
    )
    parser.add_argument("--list", action="store_true", help="list targets and shard states")
    args = parser.parse_args(argv)

    if args.list:
        for line in describe_targets():
            print(line)
        return 0
    if not args.target:
        parser.error("a target is required (or use --list)")
    if args.target not in TARGETS:
        parser.error(f"unknown target {args.target!r}; expected one of {', '.join(sorted(TARGETS))}")
    if args.date and (len(args.date) != 8 or not args.date.isdigit()):
        parser.error(f"--date must be YYYYMMDD, got {args.date!r}")

    try:
        result = plan(args.target, args.date, args.create)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    path: Path = result["path"]  # type: ignore[assignment]
    for warning in result["warnings"]:  # type: ignore[union-attr]
        print(f"warning: {warning}", file=sys.stderr)
    print(path.relative_to(ROOT))
    if result["created"]:
        print(
            "created. Write one JSON record per line, then run "
            "'python3 scripts/validate_state.py' before opening the PR.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
