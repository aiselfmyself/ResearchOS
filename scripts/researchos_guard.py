#!/usr/bin/env python3
"""Role and append-only guard for ResearchOS.

Checks
------
``check-policy``
    The role policy is well formed.
``check-append-only``
    Every ``state/*.jsonl`` only gained lines since the governance baseline
    (or, for files created later, since the commit that added them).
``check-commits``
    Every commit after the baseline carries ``Session-Id`` / ``Session-Role``
    trailers, the session exists and owns the current branch, and every changed
    path is allowed for that role.  Governance paths additionally require an
    approved ``Governance-Proposal``.
``check-all``
    All of the above, with a machine-readable summary.

The honest limit: this guard is itself repository code.  A session with write
access could weaken it.  That is why the merge to ``main`` stays a human gate
and why every governance change is recorded as a proposal that a different
session must review and a third session must approve.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from researchos_common import (  # noqa: E402
    ROOT,
    STATE_BASELINE,
    STATE_FILES,
    commit_paths,
    commit_trailers,
    commits_in_range,
    current_branch,
    git,
    git_show,
    is_merge,
    load_baseline,
    load_effective,
    load_policy,
    match_any,
    policy_errors,
    read_jsonl_text,
    resolve_effective,
)

SESSIONS_PATH = ROOT / "state" / "sessions.jsonl"


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


def check_policy() -> List[str]:
    try:
        policy = load_policy()
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot load policy/roles.json: {exc}"]
    return policy_errors(policy)


# ---------------------------------------------------------------------------
# Append-only
# ---------------------------------------------------------------------------


def _historical_text(relative_path: str, base_commit: str) -> Tuple[Optional[str], Optional[str]]:
    text = git_show(base_commit, relative_path)
    if text is not None:
        return text, base_commit
    try:
        added = git("log", "--diff-filter=A", "--format=%H", "--", relative_path)
    except RuntimeError:
        return None, None
    commits = [line.strip() for line in added.splitlines() if line.strip()]
    if not commits:
        return None, None
    first = commits[-1]  # git log is newest-first
    return git_show(first, relative_path), first


def prefix_violations(relative_path: str, historical: str, current: str) -> List[str]:
    """Return append-only violations between two versions of a JSONL file."""
    old_lines = [line for line in historical.splitlines() if line.strip()]
    new_lines = [line for line in current.splitlines() if line.strip()]
    if len(new_lines) < len(old_lines):
        return [
            f"{relative_path}: {len(old_lines)} lines at baseline but only "
            f"{len(new_lines)} now (append-only violation)"
        ]
    for index, old_line in enumerate(old_lines):
        if new_lines[index] != old_line:
            return [
                f"{relative_path}: line {index + 1} was modified or reordered "
                f"(append-only violation; append a new revision instead)"
            ]
    return []


def check_append_only(base_commit: Optional[str] = None, root: Path = ROOT) -> List[str]:
    baseline = load_baseline()
    base_commit = base_commit or baseline.get("base_commit")
    if not base_commit:
        return ["policy/state_baseline.json has no base_commit"]

    errors: List[str] = []
    candidates = sorted(set(list(STATE_FILES.values()) + list(baseline.get("files", {}))))
    for relative_path in candidates:
        path = root / relative_path
        historical, source = _historical_text(relative_path, base_commit)
        if historical is None:
            continue  # brand-new file, nothing to compare yet
        if not path.exists():
            errors.append(
                f"{relative_path}: file existed at {source[:7]} but is now missing"
            )
            continue
        errors.extend(
            prefix_violations(
                relative_path, historical, path.read_text(encoding="utf-8")
            )
        )
    return errors


# ---------------------------------------------------------------------------
# Commit / role checks
# ---------------------------------------------------------------------------


def _sessions_at(rev: str):
    text = git_show(rev, "state/sessions.jsonl")
    if text is None:
        if SESSIONS_PATH.exists():
            text = SESSIONS_PATH.read_text(encoding="utf-8")
        else:
            return [], []
    records = read_jsonl_text(text)
    effective, errors, _warnings = resolve_effective(records)
    return effective, errors


def _find_session(sessions: List[dict], session_id: str) -> Optional[dict]:
    for record in sessions:
        if record.get("session_id") == session_id:
            return record
    return None


def check_commits(
    base_commit: Optional[str] = None, branch: Optional[str] = None
) -> List[str]:
    baseline = load_baseline()
    base_commit = base_commit or baseline.get("base_commit")
    if not base_commit:
        return ["policy/state_baseline.json has no base_commit"]

    policy = load_policy()
    roles = policy["roles"]
    governance_paths = policy.get("governance_paths", [])
    branch = branch or current_branch()

    try:
        proposals, _errors, _warnings = load_effective("proposals")
    except (OSError, ValueError):
        proposals = []
    proposals_by_id = {record["proposal_id"]: record for record in proposals if "proposal_id" in record}
    try:
        approvals, _errors, _warnings = load_effective("approvals")
    except (OSError, ValueError):
        approvals = []
    approved_ids = {
        approval["proposal_id"]
        for approval in approvals
        if approval.get("decision") == "approved"
    }

    errors: List[str] = []
    commits = commits_in_range(base_commit, first_parent=True)
    head = commits[-1] if commits else None
    for sha in commits:
        short = sha[:7]
        if is_merge(sha):
            continue
        trailers = commit_trailers(sha)
        session_id = trailers.get("Session-Id")
        role = trailers.get("Session-Role")
        if not session_id or not role:
            errors.append(
                f"{short}: missing Session-Id / Session-Role trailers "
                "(required for every commit after the governance baseline)"
            )
            continue
        if role not in roles:
            errors.append(f"{short}: unknown role '{role}'")
            continue

        sessions, session_errors = _sessions_at(sha)
        if session_errors:
            errors.append(f"{short}: session ledger invalid: {session_errors[0]}")
            continue
        session = _find_session(sessions, session_id)
        if session is None:
            errors.append(f"{short}: session '{session_id}' is not in state/sessions.jsonl")
            continue
        # Inherited commits from a merged branch are audited through the session
        # ledger and record authorship instead of the current branch name.  The
        # live commit (HEAD) must belong to the session that owns this branch.
        if sha == head and session.get("branch") != branch:
            errors.append(
                f"{short}: session '{session_id}' belongs to branch "
                f"'{session.get('branch')}', not '{branch}'"
            )
        if role not in session.get("roles", []):
            errors.append(
                f"{short}: session '{session_id}' does not hold role '{role}'"
            )
        if session.get("status") == "closed":
            errors.append(f"{short}: session '{session_id}' is closed")

        spec = roles[role]
        for path in commit_paths(sha):
            if not match_any(spec.get("may_write", []), path):
                errors.append(
                    f"{short}: role '{role}' is not allowed to write '{path}'"
                )
            if match_any(governance_paths, path) and not spec.get(
                "may_use_governance_paths_without_proposal"
            ):
                proposal_id = trailers.get("Governance-Proposal")
                if not proposal_id:
                    errors.append(
                        f"{short}: governance path '{path}' changed without a "
                        "Governance-Proposal trailer"
                    )
                    continue
                proposal = proposals_by_id.get(proposal_id)
                if proposal is None:
                    errors.append(f"{short}: unknown proposal '{proposal_id}'")
                elif proposal_id not in approved_ids:
                    errors.append(
                        f"{short}: proposal '{proposal_id}' is not approved "
                        f"(status={proposal.get('status')})"
                    )
                elif proposal.get("session_id") == session_id:
                    errors.append(
                        f"{short}: cannot apply your own proposal '{proposal_id}'"
                    )
    return errors


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


# For each record file, the session fields a revision may legitimately claim.
# Order matters: a later queue revision is authored by the claimant, not by the
# session that originally opened the item.
RECORD_FILES = [
    ("state/sessions.jsonl", ["session_id"]),
    ("state/proposals.jsonl", ["session_id"]),
    ("state/reviews.jsonl", ["session_id"]),
    ("state/approvals.jsonl", ["session_id"]),
    ("state/review_queue.jsonl", ["claimed_by_session", "created_by_session"]),
    ("state/claims.jsonl", ["session_id"]),
    ("state/evidence.jsonl", ["session_id"]),
    ("state/verifications.jsonl", ["session_id"]),
]


def _blame_commit(relative_path: str, line_number: int) -> Optional[str]:
    try:
        output = git("blame", "--porcelain", "-L", f"{line_number},{line_number}", "--", relative_path)
    except RuntimeError:
        return None
    first = output.splitlines()[0] if output else ""
    sha = first.split(" ", 1)[0].lstrip("^")
    if not sha or set(sha) == {"0"}:
        return None  # uncommitted line
    return sha


def check_record_authorship() -> List[str]:
    """Every new record must be introduced by a commit whose Session-Id it claims.

    This binds a record to a session even when the commit is inherited from a
    merged branch (where the current branch name says nothing).
    """
    errors: List[str] = []
    for relative_path, session_fields in RECORD_FILES:
        path = ROOT / relative_path
        if not path.exists():
            continue
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        for index, line in enumerate(lines, 1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            candidates = [record.get(field) for field in session_fields]
            claimed = next((value for value in candidates if value), None)
            if not claimed:
                continue
            sha = _blame_commit(relative_path, index)
            if sha is None:
                continue  # not committed yet
            trailers = commit_trailers(sha)
            author_session = trailers.get("Session-Id")
            if author_session is None:
                errors.append(
                    f"{relative_path}:{index}: introduced by {sha[:7]} without a "
                    "Session-Id trailer"
                )
            elif author_session not in [value for value in candidates if value]:
                errors.append(
                    f"{relative_path}:{index}: record claims session '{claimed}' but "
                    f"was introduced by commit {sha[:7]} authored by "
                    f"'{author_session}' (accepted: {candidates})"
                )
    return errors


def status() -> Dict[str, object]:
    sessions, _e1, _w1 = load_effective("sessions")
    proposals, _e2, _w2 = load_effective("proposals")
    reviews, _e3, _w3 = load_effective("reviews")
    approvals, _e4, _w4 = load_effective("approvals")
    queue, _e5, _w5 = load_effective("review_queue")
    return {
        "branch": current_branch(),
        "sessions": [
            {
                "session_id": record["session_id"],
                "roles": record.get("roles"),
                "status": record.get("status", "active"),
            }
            for record in sessions
        ],
        "proposals": [
            {
                "proposal_id": record["proposal_id"],
                "kind": record.get("kind"),
                "status": record.get("status"),
            }
            for record in proposals
        ],
        "reviews": [
            {
                "review_id": record["review_id"],
                "proposal_id": record.get("proposal_id"),
                "result": record.get("result"),
            }
            for record in reviews
        ],
        "approvals": [
            {
                "approval_id": record["approval_id"],
                "proposal_id": record.get("proposal_id"),
                "decision": record.get("decision"),
            }
            for record in approvals
        ],
        "queue": [
            {
                "queue_id": record["queue_id"],
                "proposal_id": record.get("proposal_id"),
                "status": record.get("status"),
            }
            for record in queue
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="ResearchOS role / append-only guard")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check-policy")

    append_parser = sub.add_parser("check-append-only")
    append_parser.add_argument("--base", default=None)

    commits_parser = sub.add_parser("check-commits")
    commits_parser.add_argument("--base", default=None)
    commits_parser.add_argument("--branch", default=None)

    sub.add_parser("check-authorship")

    all_parser = sub.add_parser("check-all")
    all_parser.add_argument("--base", default=None)
    all_parser.add_argument("--branch", default=None)
    all_parser.add_argument("--json", action="store_true")

    sub.add_parser("status")

    args = parser.parse_args(argv)

    if args.command == "status":
        print(json.dumps(status(), indent=2, ensure_ascii=False))
        return 0

    results: Dict[str, List[str]] = {}
    if args.command in ("check-policy", "check-all"):
        results["policy"] = check_policy()
    if args.command in ("check-append-only", "check-all"):
        results["append_only"] = check_append_only(getattr(args, "base", None))
    if args.command in ("check-commits", "check-all"):
        results["commits"] = check_commits(
            getattr(args, "base", None), getattr(args, "branch", None)
        )
    if args.command in ("check-authorship", "check-all"):
        results["authorship"] = check_record_authorship()

    failed = {name: errors for name, errors in results.items() if errors}
    if getattr(args, "json", False):
        print(json.dumps({"ok": not failed, "results": results}, indent=2, ensure_ascii=False))
    else:
        for name, errors in results.items():
            if errors:
                print(f"FAIL: {name}")
                for error in errors:
                    print(f"  - {error}")
            else:
                print(f"PASS: {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
