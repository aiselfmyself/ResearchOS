#!/usr/bin/env python3
"""Whole-file append-only anchors for ResearchOS (PRP-002 rev3, C2/A1).

Every ``state/*.jsonl`` ledger is *pinned*: ``state/anchors.jsonl`` records the
rolling hash of the file's first ``lines`` lines.  Because the rolling head
commits to the content **and order** of every line, one hash pins the whole
ledger — including its newest line, which the per-id revision chain
(``supersedes``) never covered.  That is the gap REV-003 §3.3 exploited.

``append_jsonl()`` refreshes the pin automatically, so the normal tools
(``researchos_session.py``, ``researchos_queue.py``, ``researchos_verify.py``)
never leave a ledger stale.  This CLI is the manual fallback for hand-written
appends and for the first (genesis) pin of a ledger.

Examples:
    python3 scripts/researchos_anchor.py update            # pin every stale tip
    python3 scripts/researchos_anchor.py update --file state/reviews.jsonl
    python3 scripts/researchos_anchor.py list
    python3 scripts/researchos_anchor.py verify            # exit 1 when unpinned
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from researchos_common import (  # noqa: E402
    ANCHORS_RELATIVE_PATH,
    ROOT,
    anchored_ledgers,
    anchor_errors,
    append_jsonl,
    build_anchor_updates,
    session_from_branch,
    ledger_lines,
    load_anchor_entries,
    rolling_head,
)


def derive_session_id(branch: Optional[str] = None) -> str:
    """``arena/86da9dab-researchos`` -> ``SES-86da9dab`` (the branch is the anchor).

    Lives in ``researchos_common.session_from_branch`` so that the automatic pin
    performed by ``append_jsonl`` attributes anchors the same way.
    """
    return session_from_branch(branch)


def _session_id(args) -> str:
    if getattr(args, "session", None):
        return args.session
    return derive_session_id()


def update(args) -> int:
    session_id = _session_id(args)
    updates = build_anchor_updates(ROOT, session_id=session_id)
    if args.file:
        updates = [entry for entry in updates if entry.get("file") == args.file]
        if not updates and args.file not in anchored_ledgers():
            raise SystemExit(
                f"'{args.file}' is not an anchored ledger "
                f"(anchored: {', '.join(anchored_ledgers())})"
            )
    if not updates:
        print(json.dumps({"pinned": [], "note": "every ledger tip is already anchored"},
                         indent=2, ensure_ascii=False))
        return 0
    anchor_path = ROOT / ANCHORS_RELATIVE_PATH
    for entry in updates:
        # anchor=False: the anchor ledger chains itself via prev_anchor_head_sha256.
        append_jsonl(anchor_path, entry, anchor=False)
    print(json.dumps({"pinned": updates}, indent=2, ensure_ascii=False))
    remaining = anchor_errors(ROOT)
    if remaining:
        print("warning: anchors are still inconsistent:", file=sys.stderr)
        for error in remaining:
            print(f"  - {error}", file=sys.stderr)
        return 1
    return 0


def list_anchors(args) -> int:
    _raw, entries = load_anchor_entries(ROOT)
    if args.file:
        entries = [entry for entry in entries if entry.get("file") == args.file]
    if args.format == "json":
        print(json.dumps(entries, indent=2, ensure_ascii=False))
        return 0
    if not entries:
        print("(no anchors recorded yet)")
        return 0
    print(f"{'anchor_id':20} {'file':28} {'lines':>6}  head")
    for entry in entries:
        print(
            f"{str(entry.get('anchor_id')):20} {str(entry.get('file')):28} "
            f"{str(entry.get('lines')):>6}  {str(entry.get('head_sha256'))[:16]}..."
        )
    return 0


def verify(args) -> int:
    errors = anchor_errors(ROOT)
    summary = {
        "ok": not errors,
        "anchored_ledgers": anchored_ledgers(),
        "heads": {
            relative_path: rolling_head(
                ledger_lines(
                    (ROOT / relative_path).read_text(encoding="utf-8")
                )
            )
            if (ROOT / relative_path).exists()
            else None
            for relative_path in anchored_ledgers()
        },
        "errors": errors,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 1 if errors else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Pin state/*.jsonl ledgers with whole-file rolling anchors"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    update_parser = sub.add_parser("update", help="append anchor entries for stale tips")
    update_parser.add_argument("--session", default=None, help="default: derived from branch")
    update_parser.add_argument("--file", default=None, help="only this ledger")

    list_parser = sub.add_parser("list", help="show recorded anchors")
    list_parser.add_argument("--file", default=None)
    list_parser.add_argument("--format", choices=["text", "json"], default="text")

    sub.add_parser("verify", help="exit 1 when a ledger is unpinned or an anchor broke")

    args = parser.parse_args(argv)
    if args.command == "update":
        return update(args)
    if args.command == "list":
        return list_anchors(args)
    return verify(args)


if __name__ == "__main__":
    sys.exit(main())
