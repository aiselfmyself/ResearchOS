#!/usr/bin/env python3
"""Fingerprint ledger records so a migration or revert can be proven identical.

WHY THIS EXISTS
---------------
The 2026-10-21 sharding migration (contributions/2026-10-21_ledger_sharding_migration.md)
changed *how* ledger records are read, not where the existing ones live. The
definition of done for that migration is "the set of records, by ID and by
content, is unchanged". This tool produces the evidence: it prints, per ledger,
the record count and one SHA-256 per record, computed from a canonical form of
the decoded JSON (sorted keys, no insignificant whitespace). The hash is
therefore independent of line order, file layout, and formatting -- exactly
what "same ID, same content" means.

MODES
-----
``--raw-only``
    Read only the base files (`state/<name>.jsonl`), ignoring shard
    directories. This reproduces the pre-migration view, so the output can be
    compared byte-for-byte with a run of the default mode.

default
    Read the union view through `scripts/ledger_store.py`: frozen base first,
    then `state/<name>.d/*.jsonl` in filename order.

``--records``
    Include one `ID<TAB>hash` line per record (sorted by ID). A `diff` of two
    such listings is the set-equality proof: an added, removed, or edited
    record shows up as a diff line, an unchanged set yields no output.

``--files``
    Also print the SHA-256 of every file read (base and shards), which is the
    byte-level statement "the frozen base was not touched".

``--ledger NAME``
    Restrict to one collection (repeatable). Names are the validator's
    collection names: sources, evidence, claims, verifications, hypotheses,
    relations.

Exit codes: 0 = fingerprints produced, 2 = a ledger could not be parsed (the
exit code is informational; `scripts/validate_state.py` is the gate).
Standard library only. Nothing is written anywhere.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]

try:
    import ledger_store
    import validate_state as vs
except ImportError:  # running as scripts/ledger_digest.py
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import ledger_store
    import validate_state as vs


def record_hash(record: Dict) -> str:
    """SHA-256 of the canonical JSON form (key order and spacing ignored)."""
    canonical = json.dumps(
        record, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprints(
    name: str,
    ledger_rel: str,
    id_key: str,
    raw_only: bool,
) -> Tuple[List[Tuple[str, str]], List[str], List[Path]]:
    """Return ([(id, hash)], errors, files_read) for one ledger."""
    base = ROOT / ledger_rel
    files: List[Path] = [base]
    if raw_only:
        records, errors, _origins = ledger_store.read_jsonl_file(base)
    else:
        records, errors, _origins = ledger_store.load_ledger(base)
        files.extend(ledger_store.shard_files(base, ledger_store.SHARD_SUFFIX))
    rows: List[Tuple[str, str]] = []
    for position, record in enumerate(records):
        identity = record.get(id_key)
        if not isinstance(identity, str) or not identity:
            # Keep the record visible: an unidentifiable record is a real
            # problem, so it gets a positional label instead of being hidden.
            identity = f"<{name}[{position}] has no {id_key}>"
        rows.append((identity, record_hash(record)))
    rows.sort(key=lambda row: row[0])
    return rows, errors, files


def combined_hash(rows: List[Tuple[str, str]]) -> str:
    digest = hashlib.sha256()
    for identity, value in rows:
        digest.update(f"{identity}\t{value}\n".encode("utf-8"))
    return digest.hexdigest()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--raw-only",
        action="store_true",
        help="read only the frozen base files (pre-migration view)",
    )
    parser.add_argument(
        "--records", action="store_true", help="print one ID<TAB>hash line per record"
    )
    parser.add_argument(
        "--files", action="store_true", help="also print the SHA-256 of each file read"
    )
    parser.add_argument(
        "--ledger", action="append", default=None, help="collection name (repeatable)"
    )
    args = parser.parse_args(argv)

    names = sorted(vs.COLLECTIONS)
    if args.ledger:
        unknown = [n for n in args.ledger if n not in vs.COLLECTIONS]
        if unknown:
            parser.error(f"unknown ledger(s): {', '.join(unknown)}")
        names = [n for n in names if n in set(args.ledger)]

    # The mode goes to stderr so stdout is diffable between the pre-migration
    # (--raw-only) and post-migration (union) runs: identical record sets must
    # produce byte-identical stdout.
    mode = "raw-only(base files)" if args.raw_only else "union(base+shards)"
    print(f"# ledger_digest {mode}", file=sys.stderr)
    print("# ledger\trecords\tcombined_sha256")
    had_errors = False
    for name in names:
        ledger_rel, _schema, id_key = vs.COLLECTIONS[name]
        rows, errors, files = fingerprints(name, ledger_rel, id_key, args.raw_only)
        print(f"{name}\t{len(rows)}\t{combined_hash(rows)}")
        if args.records:
            for identity, value in rows:
                print(f"  {identity}\t{value}")
        if args.files:
            for path in files:
                if path.exists():
                    print(f"  file\t{path.relative_to(ROOT)}\t{file_hash(path)}")
                else:
                    print(f"  file\t{path.relative_to(ROOT)}\t<missing>")
        for error in errors:
            had_errors = True
            print(f"  error\t{error}", file=sys.stderr)
    return 2 if had_errors else 0


if __name__ == "__main__":
    sys.exit(main())
