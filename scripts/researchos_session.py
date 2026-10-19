#!/usr/bin/env python3
"""Claim, inspect, and close ResearchOS sessions (append-only).

A *session* is one Arena.ai chat.  Arena binds each chat to one branch, which is
the only stable identity anchor available here: the sandbox git author is the
same for every session, so author names are recorded for audit but are **not**
used as proof of separation.  Branch uniqueness and append-only history are what
the harness can actually enforce.

Examples:
    python3 scripts/researchos_session.py claim --role verifier
    python3 scripts/researchos_session.py claim --role approver --kind human
    python3 scripts/researchos_session.py add-role --session SES-c4426c6b --role integrator
    python3 scripts/researchos_session.py close --session SES-c4426c6b --notes "..."
    python3 scripts/researchos_session.py list
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from researchos_common import (  # noqa: E402
    ROOT,
    append_jsonl,
    current_branch,
    git,
    load_effective,
    load_policy,
    now_utc,
    resolve_effective,
    sha256_file,
)
from researchos_common import read_jsonl  # noqa: E402

SESSIONS_PATH = ROOT / "state" / "sessions.jsonl"
BRANCH_SESSION_RE = re.compile(r"^arena/([a-z0-9]+)-")


def derive_session_id(branch: str) -> str:
    match = BRANCH_SESSION_RE.match(branch)
    if not match:
        raise SystemExit(
            f"cannot derive a session id from branch '{branch}'; pass --session"
        )
    return f"SES-{match.group(1)}"


def effective_sessions():
    records = read_jsonl(SESSIONS_PATH)
    effective, errors, _warnings = resolve_effective(records)
    if errors:
        raise SystemExit("state/sessions.jsonl is inconsistent:\n  " + "\n  ".join(errors))
    return records, effective


def find_session(effective, session_id: str):
    for record in effective:
        if record.get("session_id") == session_id:
            return record
    return None


def claim(args) -> int:
    policy = load_policy()
    roles = policy["roles"]
    branch = getattr(args, "branch", None) or current_branch()
    session_id = args.session or derive_session_id(branch)

    if args.role not in roles:
        raise SystemExit(f"unknown role '{args.role}'")
    if args.role == "bootstrap":
        existing_bootstrap = [
            record
            for record in effective_sessions()[1]
            if "bootstrap" in record.get("roles", [])
        ]
        if existing_bootstrap and args.session not in {
            record["session_id"] for record in existing_bootstrap
        }:
            raise SystemExit(
                "bootstrap is limited to one session; "
                f"already claimed by {existing_bootstrap[0]['session_id']}"
            )

    _records, effective = effective_sessions()
    existing = find_session(effective, session_id)

    if existing is None:
        conflict = [r for r in effective if r.get("branch") == branch]
        if conflict:
            raise SystemExit(
                f"branch '{branch}' is already owned by {conflict[0]['session_id']}; "
                "one branch may host only one session"
            )
        record = {
            "session_id": session_id,
            "branch": branch,
            "roles": [args.role],
            "kind": getattr(args, "kind", "agent"),
            "started_at": now_utc(),
            "status": "active",
            "policy_version": policy["policy_version"],
            "declared_model": args.model or "unknown",
            "declared_model_source": "self" if args.model else "unknown",
            "git_author": git("config", "user.name", check=False) or "unknown",
            "first_commit": getattr(args, "first_commit", None)
            or (git("rev-parse", "HEAD", check=False) or "0000000"),
            "notes": getattr(args, "notes", None) or "",
        }
        path_hash = append_jsonl(SESSIONS_PATH, record)
        print(json.dumps({"session_id": session_id, "roles": [args.role],
                          "branch": branch, "line_sha256": path_hash}, indent=2))
        return 0

    if existing.get("branch") != branch:
        raise SystemExit(
            f"session {session_id} belongs to branch '{existing.get('branch')}', "
            f"not '{branch}'"
        )
    if args.role in existing.get("roles", []):
        print(f"session {session_id} already has role '{args.role}'")
        return 0
    if existing.get("status") == "closed":
        raise SystemExit(f"session {session_id} is closed")

    updated = dict(existing)
    updated["roles"] = list(existing.get("roles", [])) + [args.role]
    updated["revision"] = int(existing.get("revision", 1)) + 1
    updated["supersedes"] = None  # filled below
    # Compute the hash of the line we are superseding (the effective record).
    from researchos_common import line_hash

    updated["supersedes"] = line_hash(existing)
    if args.model:
        updated["declared_model"] = args.model
        updated["declared_model_source"] = "self"
    append_jsonl(SESSIONS_PATH, updated)
    print(f"added role '{args.role}' to {session_id}")
    return 0


def close(args) -> int:
    _records, effective = effective_sessions()
    existing = find_session(effective, args.session)
    if existing is None:
        raise SystemExit(f"unknown session {args.session}")
    if existing.get("status") == "closed":
        print(f"session {args.session} already closed")
        return 0
    from researchos_common import line_hash

    updated = dict(existing)
    updated["status"] = "closed"
    updated["closed_at"] = now_utc()
    if args.notes:
        updated["notes"] = (existing.get("notes", "") + " " + args.notes).strip()
    updated["revision"] = int(existing.get("revision", 1)) + 1
    updated["supersedes"] = line_hash(existing)
    append_jsonl(SESSIONS_PATH, updated)
    print(f"closed {args.session}")
    return 0


def list_sessions(args) -> int:
    _records, effective = effective_sessions()
    payload = [
        {
            "session_id": record["session_id"],
            "branch": record["branch"],
            "roles": record.get("roles", []),
            "kind": record.get("kind"),
            "status": record.get("status", "active"),
            "started_at": record.get("started_at"),
        }
        for record in effective
    ]
    if args.format == "json":
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for item in payload:
            print(
                f"{item['session_id']:20} {item['status']:7} "
                f"{'+'.join(item['roles']):32} {item['branch']}"
            )
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="ResearchOS session ledger")
    sub = parser.add_subparsers(dest="command", required=True)

    claim_parser = sub.add_parser("claim", help="claim or extend a session role")
    claim_parser.add_argument("--role", required=True)
    claim_parser.add_argument("--session", default=None)
    claim_parser.add_argument("--branch", default=None)
    claim_parser.add_argument("--kind", choices=["agent", "human"], default="agent")
    claim_parser.add_argument("--model", default=None, help="self-declared, unverified")
    claim_parser.add_argument("--first-commit", default=None)
    claim_parser.add_argument("--notes", default=None)
    claim_parser.set_defaults(func=claim)

    close_parser = sub.add_parser("close")
    close_parser.add_argument("--session", required=True)
    close_parser.add_argument("--notes", default=None)
    close_parser.set_defaults(func=close)

    add_role = sub.add_parser("add-role")
    add_role.add_argument("--session", required=True)
    add_role.add_argument("--role", required=True)
    add_role.add_argument("--model", default=None)
    add_role.set_defaults(func=claim)

    list_parser = sub.add_parser("list")
    list_parser.add_argument("--format", choices=["text", "json"], default="text")
    list_parser.set_defaults(func=list_sessions)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
