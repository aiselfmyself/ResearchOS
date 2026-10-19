#!/usr/bin/env python3
"""Append-only review queue.

The queue is how a verifier session finds work without being told by the
proposer.  A proposer enqueues a proposal; a verifier claims it (recording a
lease), runs ``scripts/researchos_verify.py``, and completes it with the review
id.  An approver then reads the review.

Examples:
    python3 scripts/researchos_queue.py add --proposal PRP-001 --session SES-c4426c6b
    python3 scripts/researchos_queue.py claim --queue RQ-001 --session SES-xxxx
    python3 scripts/researchos_queue.py complete --queue RQ-001 --review REV-001 --session SES-xxxx
    python3 scripts/researchos_queue.py list --status open
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from researchos_common import (  # noqa: E402
    ROOT,
    append_jsonl,
    line_hash,
    load_effective,
    next_id,
    now_utc,
    read_jsonl,
    resolve_effective,
)

QUEUE_PATH = ROOT / "state" / "review_queue.jsonl"
REVIEWS_PATH = ROOT / "state" / "reviews.jsonl"
PROPOSALS_PATH = ROOT / "state" / "proposals.jsonl"
SESSIONS_PATH = ROOT / "state" / "sessions.jsonl"


def _load(path: Path):
    effective, errors, _warnings = resolve_effective(read_jsonl(path))
    if errors:
        raise SystemExit(f"{path.name} is inconsistent:\n  " + "\n  ".join(errors))
    return effective


def _session(session_id: str) -> Optional[dict]:
    for record in _load(SESSIONS_PATH):
        if record.get("session_id") == session_id:
            return record
    return None


def add(args) -> int:
    if _session(args.session) is None:
        raise SystemExit(f"unknown session '{args.session}'; claim it first")
    proposals = {record["proposal_id"] for record in _load(PROPOSALS_PATH)}
    if args.proposal not in proposals:
        raise SystemExit(f"unknown proposal '{args.proposal}'")

    effective = _load(QUEUE_PATH)
    for record in effective:
        if (
            record.get("proposal_id") == args.proposal
            and record.get("status") in ("open", "claimed")
        ):
            print(f"{record['queue_id']} already tracks {args.proposal}")
            return 0

    checks = [item.strip() for item in args.checks.split(",") if item.strip()]
    record = {
        "queue_id": next_id(read_jsonl(QUEUE_PATH), "queue_id", "RQ"),
        "proposal_id": args.proposal,
        "required_checks": checks,
        "status": "open",
        "priority": args.priority,
        "created_at": now_utc(),
        "created_by_session": args.session,
        "notes": args.notes or "",
    }
    append_jsonl(QUEUE_PATH, record)
    print(f"enqueued {record['queue_id']} for {args.proposal}")
    return 0


def _latest(queue_id: str) -> dict:
    effective = _load(QUEUE_PATH)
    for record in effective:
        if record.get("queue_id") == queue_id:
            return record
    raise SystemExit(f"unknown queue item '{queue_id}'")


def _update(previous: dict, **changes) -> dict:
    updated = dict(previous)
    updated.update(changes)
    updated["revision"] = int(previous.get("revision", 1)) + 1
    updated["supersedes"] = line_hash(previous)
    append_jsonl(QUEUE_PATH, updated)
    return updated


def claim(args) -> int:
    session = _session(args.session)
    if session is None:
        raise SystemExit(f"unknown session '{args.session}'")
    if "verifier" not in session.get("roles", []):
        raise SystemExit(
            f"session '{args.session}' does not hold the verifier role; "
            "a proposer cannot claim its own review"
        )
    item = _latest(args.queue)
    if item.get("status") == "claimed" and item.get("claimed_by_session") == args.session:
        print(f"{args.queue} already claimed by {args.session}")
        return 0
    if item.get("status") != "open":
        raise SystemExit(f"{args.queue} is '{item.get('status')}', not 'open'")
    _update(item, status="claimed", claimed_by_session=args.session, claimed_at=now_utc())
    print(f"claimed {args.queue} as {args.session}")
    return 0


def complete(args) -> int:
    item = _latest(args.queue)
    if item.get("status") != "claimed":
        raise SystemExit(f"{args.queue} is '{item.get('status')}', not 'claimed'")
    if item.get("claimed_by_session") != args.session:
        raise SystemExit(
            f"{args.queue} is claimed by {item.get('claimed_by_session')}, not {args.session}"
        )
    reviews = {record["review_id"]: record for record in _load(REVIEWS_PATH)}
    review = reviews.get(args.review)
    if review is None:
        raise SystemExit(f"unknown review '{args.review}'")
    if review.get("proposal_id") != item.get("proposal_id"):
        raise SystemExit(
            f"review '{args.review}' targets {review.get('proposal_id')}, "
            f"not {item.get('proposal_id')}"
        )
    _update(item, status="completed", review_id=args.review, completed_at=now_utc())
    print(f"completed {args.queue} with {args.review}")
    return 0


def cancel(args) -> int:
    item = _latest(args.queue)
    if item.get("status") in ("completed", "cancelled"):
        print(f"{args.queue} already {item.get('status')}")
        return 0
    _update(item, status="cancelled", notes=args.notes or item.get("notes", ""))
    print(f"cancelled {args.queue}")
    return 0


def list_items(args) -> int:
    effective = _load(QUEUE_PATH)
    rows = []
    for record in effective:
        if args.status and record.get("status") != args.status:
            continue
        rows.append(record)
    if args.format == "json":
        print(json.dumps(rows, indent=2, ensure_ascii=False))
    else:
        if not rows:
            print("(queue empty)")
            return 0
        for record in rows:
            print(
                f"{record['queue_id']:8} {record.get('status'):9} "
                f"{record.get('proposal_id'):8} {record.get('priority', 'normal'):6} "
                f"{record.get('claimed_by_session', '-')}"
            )
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="ResearchOS review queue")
    sub = parser.add_subparsers(dest="command", required=True)

    add_parser = sub.add_parser("add")
    add_parser.add_argument("--proposal", required=True)
    add_parser.add_argument("--session", required=True)
    add_parser.add_argument(
        "--checks",
        default="schema,regression_tests,benchmark_reproducible,append_only,role_separation",
    )
    add_parser.add_argument("--priority", choices=["high", "normal", "low"], default="normal")
    add_parser.add_argument("--notes", default=None)
    add_parser.set_defaults(func=add)

    claim_parser = sub.add_parser("claim")
    claim_parser.add_argument("--queue", required=True)
    claim_parser.add_argument("--session", required=True)
    claim_parser.set_defaults(func=claim)

    complete_parser = sub.add_parser("complete")
    complete_parser.add_argument("--queue", required=True)
    complete_parser.add_argument("--review", required=True)
    complete_parser.add_argument("--session", required=True)
    complete_parser.set_defaults(func=complete)

    cancel_parser = sub.add_parser("cancel")
    cancel_parser.add_argument("--queue", required=True)
    cancel_parser.add_argument("--notes", default=None)
    cancel_parser.set_defaults(func=cancel)

    list_parser = sub.add_parser("list")
    list_parser.add_argument("--status", default=None)
    list_parser.add_argument("--format", choices=["text", "json"], default="text")
    list_parser.set_defaults(func=list_items)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
