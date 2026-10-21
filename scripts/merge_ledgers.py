#!/usr/bin/env python3
"""Merge append-only JSONL ledgers without hiding ID collisions or deletions.

WHY: independent branches append at the same text location. Compare records by
ID, not line position, and retain original spelling to avoid noisy diffs.
Non-goals: schema/citation validation, shard discovery, a CI gate, a Git merge
driver, or automatic resolution of edits. This is an explicit repair tool, not
S1's future shard validator (which must reject even identical duplicate IDs).

Usage: python3 scripts/merge_ledgers.py --base BASE --ours OURS --theirs THEIRS
           --id-key KEY [--out OUT] [--allow-delete]

IDs are nonempty strings sorted lexically (legacy and new formats both work).
Content equality ignores object key order and whitespace, but not array order
or JSON number spelling/type. Blank lines are ignored. Base spelling wins,
then ours, then theirs. Missing final newlines are added only when needed to
separate records. --allow-delete applies delete-wins to base IDs missing on
EITHER side; it never permits conflicting contents. Exit: 0 success, 1 semantic
conflict, 2 invalid input/IO/arguments. No output is opened before validation.
Standard library only; no tracked ledger is modified unless explicitly --out.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def reject_constant(value):
    raise ValueError(f"non-JSON constant: {value}")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate object key: {key}")
        result[key] = value
    return result


def load(path, label, id_key, errors):
    records = {}
    try:
        with Path(path).open(encoding="utf-8", newline="") as stream:
            for number, raw in enumerate(stream, 1):
                if not raw.strip():
                    continue
                location = f"{label}:{path}:{number}"
                try:
                    value = json.loads(raw, parse_constant=reject_constant,
                                       object_pairs_hook=unique_object,
                                       parse_int=str_number_int,
                                       parse_float=str_number_float)
                    if not isinstance(value, dict):
                        raise ValueError("record must be a JSON object")
                    identity = value.get(id_key)
                    if not isinstance(identity, str) or isinstance(identity, JSONNumber) or not identity:
                        raise ValueError(f"missing or invalid string ID: {id_key}")
                except ValueError as exc:
                    errors.append(f"{location}: {exc}")
                    continue
                records.setdefault(identity, []).append((value, raw, location))
    except (OSError, UnicodeError) as exc:
        errors.append(f"{label}:{path}: {exc}")
    return records


class JSONNumber(str):
    """Keep JSON numbers distinct from strings and preserve numeric spelling."""


def str_number_int(value):
    return JSONNumber(value)


def str_number_float(value):
    return JSONNumber(value)


def equal(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(equal(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(equal(a, b) for a, b in zip(left, right))
    return left == right


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("base", "ours", "theirs", "id-key"):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--out")
    parser.add_argument("--allow-delete", action="store_true")
    args = parser.parse_args(argv)
    errors = []
    base, ours, theirs = [load(getattr(args, name), name, args.id_key, errors)
                          for name in ("base", "ours", "theirs")]
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2
    identities = set(base) | set(ours) | set(theirs)
    deleted = set(base) - (set(ours) & set(theirs))
    conflicts = []
    for identity in sorted(identities):
        entries = [entry for ledger in (base, ours, theirs)
                   for entry in ledger.get(identity, [])]
        if any(not equal(entries[0][0], entry[0]) for entry in entries[1:]):
            conflicts.append(f"conflict ID {identity!r}:\n" + "\n".join(
                f"  {location}: {raw.rstrip()}" for _, raw, location in entries))
    for identity in sorted(deleted):
        missing = ", ".join(name for name, ledger in (("ours", ours), ("theirs", theirs))
                            if identity not in ledger)
        print(f"deletion ID {identity!r}: missing from {missing}"
              + (" (allowed)" if args.allow_delete else ""), file=sys.stderr)
    if conflicts:
        print("\n".join(conflicts), file=sys.stderr)
    if conflicts or (deleted and not args.allow_delete):
        return 1
    order = list(base) + sorted(identities - set(base))
    lines = []
    for identity in order:
        if identity in deleted:
            continue
        ledger = next(ledger for ledger in (base, ours, theirs) if identity in ledger)
        lines.append(ledger[identity][0][1])
    output = "".join(raw if raw.endswith(("\n", "\r")) or i == len(lines) - 1
                     else raw + "\n" for i, raw in enumerate(lines))
    try:
        if args.out:
            with Path(args.out).open("w", encoding="utf-8", newline="") as stream:
                stream.write(output)
        else:
            sys.stdout.write(output)
    except (OSError, UnicodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
