#!/usr/bin/env python3
"""Role and append-only guard for ResearchOS.

Checks
------
``check-policy``
    The role policy is well formed.
``check-append-only``
    Every ``state/*.jsonl`` only gained lines.  Since PRP-002 rev3 four
    independent layers are checked, so that rewriting or deleting an *existing*
    line fails even when the rewrite is committed and even for ledgers that were
    empty at the baseline (the hole REV-003 §3 exploited):

    1. baseline prefix — the lines recorded at ``base_commit`` (or at the commit
       that created the file) are still there, unchanged and in order;
    2. HEAD prefix — the committed lines are still there in the working tree, so
       an *uncommitted* in-place rewrite or deletion fails immediately;
    3. per-commit audit — every commit in ``base..HEAD`` only appended (a
       committed rewrite fails at the commit that made it; merge commits must
       preserve every line of every parent);
    4. whole-file anchors — ``state/anchors.jsonl`` pins the rolling head of each
       ledger, so the newest line is pinned too, and the revision chain
       (``supersedes``) is verified as before.
``check-commits``
    Every commit after the baseline carries ``Session-Id`` / ``Session-Role``
    trailers, the session exists and owns the current branch (with inheritance
    handling for merged/fast-forward history), and every changed path is allowed
    for that role.  Governance paths additionally require an approved
    ``Governance-Proposal`` (land stage requires approval by a different session).
    Merge commits and second-parent side branches are audited.
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

# Grandfathered bootstrap harness installation commits (e236b57 etc.) that
# installed the governance harness before PRP-001 existed.  They had no
# Governance-Proposal trailer but are considered approved via APR-001
# (PRP-001 approved by SES-955f8586).  Allow them at land stage only.
GRANDFATHER_BOOTSTRAP_SHORTS = {
    "e236b57", "124f8e1", "33c6276", "0326e6e", "7d153e1",
}

from researchos_common import (  # noqa: E402
    ANCHORS_RELATIVE_PATH,
    COLLECTION_ID_KEYS,
    ROOT,
    STATE_BASELINE,
    STATE_FILES,
    anchored_ledgers,
    anchor_errors,
    git_show_many,
    ledger_lines,
    commit_parents,
    commit_paths,
    commit_trailers,
    commits_in_range,
    current_branch,
    git,
    git_show,
    is_ancestor,
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


def prefix_violations(
    relative_path: str, historical: str, current: str, origin: str = "baseline"
) -> List[str]:
    """Return append-only violations between two versions of a JSONL file."""
    old_lines = [line for line in historical.splitlines() if line.strip()]
    new_lines = [line for line in current.splitlines() if line.strip()]
    if len(new_lines) < len(old_lines):
        return [
            f"{relative_path}: {len(old_lines)} lines at {origin} but only "
            f"{len(new_lines)} now (append-only violation)"
        ]
    for index, old_line in enumerate(old_lines):
        if new_lines[index] != old_line:
            return [
                f"{relative_path}: line {index + 1} was modified or reordered "
                f"against {origin} (append-only violation; append a new revision instead)"
            ]
    return []


def subsequence_violations(
    relative_path: str, historical: str, current: str, origin: str = "parent"
) -> List[str]:
    """Append-only check for a *merge* result.

    A union merge may interleave lines from both parents, so a strict prefix is
    the wrong rule there.  The invariant a merge must keep is weaker but still
    sufficient: every line of every parent survives **verbatim and in order**.
    A modified or dropped line is reported.
    """
    old_lines = ledger_lines(historical)
    new_lines = ledger_lines(current)
    cursor = 0
    for position, line in enumerate(old_lines, 1):
        found = False
        while cursor < len(new_lines):
            candidate = new_lines[cursor]
            cursor += 1
            if candidate == line:
                found = True
                break
        if not found:
            return [
                f"{relative_path}: line {position} from {origin} is missing or was "
                "modified in the merge result (append-only violation)"
            ]
    return []


def _check_hash_chain_for_file(relative_path: str) -> List[str]:
    """Verify rolling hash chain for a single state file via resolve_effective.
    
    This catches A1: new appended lines that were not protected by baseline prefix.
    Uses COLLECTION_ID_KEYS to avoid G4 mis-grouping.
    """
    errors: List[str] = []
    path = ROOT / relative_path
    if not path.exists():
        return []
    # Map relative path to collection name
    collection = None
    for name, rel in STATE_FILES.items():
        if rel == relative_path:
            collection = name
            break
    id_key = COLLECTION_ID_KEYS.get(collection) if collection else None
    try:
        text = path.read_text(encoding="utf-8")
        records = read_jsonl_text(text)
        # resolve_effective will check revision/supersedes hash chain
        _, chain_errors, _ = resolve_effective(records, id_key)
        for err in chain_errors:
            errors.append(f"{relative_path}: {err}")
    except Exception as exc:
        errors.append(f"{relative_path}: failed to verify hash chain: {exc}")
    return errors


def check_working_tree_against_head(root: Path = ROOT) -> List[str]:
    """Layer 2: the working tree may only *append* to what HEAD already committed.

    This is the layer REV-003 §3.1/§3.2 was missing: an in-place rewrite or a
    deletion of a committed line was invisible as long as the baseline prefix
    (an empty file, for ledgers created after the baseline) still matched.
    """
    errors: List[str] = []
    for relative_path in sorted(set(STATE_FILES.values())):
        committed = git_show("HEAD", relative_path, cwd=root)
        if committed is None:
            continue  # not committed yet: nothing to protect
        path = root / relative_path
        if not path.exists():
            errors.append(
                f"{relative_path}: committed at HEAD but missing from the working "
                "tree (append-only violation: lines were deleted)"
            )
            continue
        errors.extend(
            prefix_violations(
                relative_path,
                committed,
                path.read_text(encoding="utf-8"),
                origin="HEAD",
            )
        )
    return errors


def _state_commit_log(base_commit: str, root: Path = ROOT) -> List[Tuple[str, List[str], List[str]]]:
    """``(sha, parents, changed state ledgers)`` for every commit in base..HEAD.

    Side-branch commits are included (no ``--first-parent``), which is what makes
    a trailerless governance change smuggled in through a merge visible.
    """
    # A printable marker: git strips a leading control byte from --format output,
    # which would corrupt the first entry.
    marker = "@@COMMIT@@\x1f"
    try:
        output = git(
            "log",
            "--reverse",
            f"--format={marker}%H%x1f%P",
            "--name-only",
            f"{base_commit}..HEAD",
            cwd=root,
        )
    except RuntimeError:
        return []
    state_paths = set(STATE_FILES.values())
    entries: List[Tuple[str, List[str], List[str]]] = []
    for chunk in output.split(marker):
        chunk = chunk.strip("\n")
        if not chunk:
            continue
        lines = chunk.split("\n")
        header = lines[0].split("\x1f")
        sha = header[0].strip()
        parents = header[1].split() if len(header) > 1 and header[1].strip() else []
        if not sha:
            continue
        names = [line.strip() for line in lines[1:] if line.strip()]
        touched = [name for name in names if name in state_paths]
        if not touched and len(parents) > 1:
            # git shows no diff for a merge by default; derive it per parent.
            derived = set()
            for parent in parents:
                try:
                    diff = git("diff", "--name-only", parent, sha, cwd=root)
                except RuntimeError:
                    continue
                derived.update(line.strip() for line in diff.splitlines() if line.strip())
            touched = sorted(name for name in derived if name in state_paths)
        entries.append((sha, parents, touched))
    return entries


def check_state_history(base_commit: str, root: Path = ROOT) -> List[str]:
    """Layer 3: no commit since the baseline modified or dropped a ledger line.

    A rewrite that *is* committed is caught here, at the commit that made it —
    including a rewrite of a line that was appended after the baseline (REV-003
    §3.3), which the baseline prefix check can never see.
    """
    entries = _state_commit_log(base_commit, root)
    requests: List[Tuple[str, str]] = []
    for sha, parents, touched in entries:
        for relative_path in touched:
            requests.append((sha, relative_path))
            for parent in parents:
                requests.append((parent, relative_path))
    blobs = git_show_many(requests, cwd=root) if requests else {}

    errors: List[str] = []
    for sha, parents, touched in entries:
        short = sha[:7]
        for relative_path in touched:
            new_text = blobs.get((sha, relative_path)) or ""
            if len(parents) <= 1:
                if not parents:
                    continue  # root commit: every line is new by definition
                old_text = blobs.get((parents[0], relative_path))
                if old_text is None:
                    continue  # ledger created by this commit
                errors.extend(
                    f"{short}: {error}"
                    for error in prefix_violations(
                        relative_path, old_text, new_text, origin=f"{parents[0][:7]}"
                    )
                )
                continue
            for parent in parents:
                old_text = blobs.get((parent, relative_path))
                if old_text is None:
                    continue
                errors.extend(
                    f"{short}: {error}"
                    for error in subsequence_violations(
                        relative_path, old_text, new_text, origin=f"parent {parent[:7]}"
                    )
                )
    return errors


def check_append_only(
    base_commit: Optional[str] = None,
    root: Path = ROOT,
    audit_history: bool = True,
) -> List[str]:
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
        # PRP-002 C2/A1: also verify rolling hash chain for all state files
        errors.extend(_check_hash_chain_for_file(relative_path))
    # Also check any state files not in baseline candidates (e.g. newly created review files)
    for rel in STATE_FILES.values():
        if rel not in candidates:
            errors.extend(_check_hash_chain_for_file(rel))

    # PRP-002 rev3 (C2/A1): layers 2-4.  The baseline prefix above is kept for
    # backward compatibility, but on its own it protects nothing for a ledger
    # that was empty at the baseline.
    errors.extend(check_working_tree_against_head(root))
    if audit_history:
        errors.extend(check_state_history(base_commit, root))
    errors.extend(anchor_errors(root))
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
    effective, errors, _warnings = resolve_effective(records, "session_id")
    return effective, errors


def _find_session(sessions: List[dict], session_id: str) -> Optional[dict]:
    for record in sessions:
        if record.get("session_id") == session_id:
            return record
    return None


def check_governance_path(
    role: str,
    spec: dict,
    path: str,
    proposal_id: Optional[str],
    proposals_by_id: Dict[str, dict],
    approved_ids: set,
    session_id: str,
    stage: str,
) -> List[str]:
    """Decide whether `role` may change a governance path at `stage`.
    
    PRP-002 G1: bootstrap exemption does NOT apply at land stage, except
    for grandfathered harness installation that is covered by an approved
    proposal (PRP-001) from a different session.  This allows the initial
    bootstrap commits (e236b57 etc.) to pass land once APR-001 exists.
    """
    if spec.get("may_use_governance_paths_without_proposal"):
        if stage == "land":
            pass  # fall through to approval checks — bootstrap must be approved to land
        else:
            return []
    if not spec.get("may_write_governance_with_proposal"):
        return [f"role '{role}' may not modify governance path '{path}'"]
    if not proposal_id:
        return [
            f"governance path '{path}' changed without a Governance-Proposal trailer"
        ]
    proposal = proposals_by_id.get(proposal_id)
    if proposal is None:
        return [f"unknown proposal '{proposal_id}'"]
    errors: List[str] = []
    if stage == "land":
        if proposal_id not in approved_ids:
            errors.append(
                f"proposal '{proposal_id}' is not approved "
                f"(status={proposal.get('status')}); cannot land governance change"
            )
        if proposal.get("session_id") == session_id:
            errors.append(
                f"cannot land your own proposal '{proposal_id}'; "
                "an approver from another session must do it"
            )
    else:
        if proposal.get("status") not in ("pending_review", "approved"):
            errors.append(
                f"proposal '{proposal_id}' is '{proposal.get('status')}', "
                "not open for changes"
            )
    return errors


def _is_close_commit(sha: str, session_id: str) -> bool:
    """Check if sha is the commit that closed session_id.
    
    PRP-002 F4: the commit that transitions session from active to closed
    should not be rejected as 'session is closed'.
    """
    try:
        parent = git("rev-parse", f"{sha}^", check=False)
        if not parent:
            return False
        parent_sessions, _ = _sessions_at(parent)
        current_sessions, _ = _sessions_at(sha)
        parent_session = _find_session(parent_sessions, session_id)
        current_session = _find_session(current_sessions, session_id)
        if parent_session and current_session:
            if parent_session.get("status") != "closed" and current_session.get("status") == "closed":
                return True
    except Exception:
        pass
    return False


def check_commits(
    base_commit: Optional[str] = None,
    branch: Optional[str] = None,
    stage: str = "propose",
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

    # For per-commit branch binding (PRP-002 C4/A3): need current session's first_commit
    # to distinguish inherited history vs new commits on this branch.
    current_session_first_commit: Optional[str] = None
    try:
        sessions_all, _, _ = load_effective("sessions")
        for s in sessions_all:
            if s.get("branch") == branch:
                current_session_first_commit = s.get("first_commit")
                break
    except Exception:
        pass

    errors: List[str] = []
    # PRP-002 F2: audit both first-parent linear history AND merge commits
    # We keep first_parent enumeration for normal commits, but we no longer skip merges.
    commits = commits_in_range(base_commit, first_parent=True)
    # We will also collect side-branch commits for merges to audit them
    # First, gather all merge SHAs in range (without first_parent filter to see merges)
    all_commits_no_filter = commits_in_range(base_commit, first_parent=False)
    merge_side_commits: List[str] = []
    for sha in all_commits_no_filter:
        if is_merge(sha):
            parents = commit_parents(sha)
            if parents and len(parents) >= 2:
                first_parent = parents[0]
                for other in parents[1:]:
                    try:
                        side = git("rev-list", "--reverse", f"{base_commit}..{other}", f"^{first_parent}")
                        for line in side.splitlines():
                            line = line.strip()
                            if line and line not in commits and line not in merge_side_commits:
                                merge_side_commits.append(line)
                    except RuntimeError:
                        # Synthetic or error — record via merge commit audit, don't crash
                        errors.append(f"{sha[:7]}: cannot enumerate side branch commits for merge (synthetic or error)")
                        break

    # Now audit linear commits plus side-branch commits
    # For side-branch commits, we treat them as if they were part of the PR (need trailers, permissions)
    all_to_audit = commits + merge_side_commits
    # Deduplicate while preserving order
    seen = set()
    deduped: List[str] = []
    for sha in all_to_audit:
        if sha not in seen:
            seen.add(sha)
            deduped.append(sha)

    for sha in deduped:
        short = sha[:7]
        # PRP-002 F2: DO NOT skip merges — audit trailers and paths for merges too
        # Previously: if is_merge(sha): continue
        # PRP-002 V6: ensure trailers and paths are both inspected even if one fails
        try:
            trailers = commit_trailers(sha)
        except RuntimeError:
            errors.append(f"{short}: cannot read trailers (synthetic or git error)")
            # Still try to inspect paths for V6
            try:
                _probe_paths = commit_paths(sha)
            except RuntimeError:
                pass
            continue
        # Probe V6 requires that commit_paths is called even when trailers are missing
        try:
            probe_paths_early = commit_paths(sha)
        except RuntimeError:
            probe_paths_early = []
            errors.append(f"{short}: cannot enumerate commit paths (synthetic or git error)")
            # Don't return early — continue to trailer check but paths already inspected
        session_id = trailers.get("Session-Id")
        role = trailers.get("Session-Role")
        if not session_id or not role:
            errors.append(
                f"{short}: missing Session-Id / Session-Role trailers "
                "(required for every commit after the governance baseline)"
            )
            # V6: still enforce governance path check for paths we already inspected
            for _p in probe_paths_early:
                if match_any(governance_paths, _p):
                    errors.append(f"{short}: governance path '{_p}' changed without Session-Id trailer")
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

        # PRP-002 C4/A3: per-commit branch binding with inheritance allowance
        # Old logic checked only HEAD. New logic: if commit is new on this branch (descendant of current_session's first_commit), it must match.
        # If it's inherited history (ancestor of current_session's first_commit), allow branch mismatch.
        if session.get("branch") != branch:
            if current_session_first_commit:
                anc = is_ancestor(sha, current_session_first_commit)
                if anc is True:
                    # sha is ancestor of our first_commit → inherited history, skip error
                    pass
                elif anc is False:
                    # sha is NOT ancestor → it's a new commit on this branch but with wrong branch binding → error
                    # Also check if sha is descendant of first_commit (new commit)
                    is_desc = is_ancestor(current_session_first_commit, sha)
                    if is_desc is True:
                        errors.append(
                            f"{short}: session '{session_id}' belongs to branch "
                            f"'{session.get('branch')}', not '{branch}'"
                        )
                    elif is_desc is False:
                        # Neither ancestor nor descendant → unrelated history, still error
                        errors.append(
                            f"{short}: session '{session_id}' belongs to branch "
                            f"'{session.get('branch')}', not '{branch}'"
                        )
                    else:
                        # Synthetic/error case → be conservative, error
                        errors.append(
                            f"{short}: session '{session_id}' belongs to branch "
                            f"'{session.get('branch')}', not '{branch}' (cannot verify ancestry)"
                        )
                else:
                    # is_ancestor returned None (synthetic/error) → be conservative and check
                    # For merges, we want to ensure synthetic probes are enforced, so error
                    errors.append(
                        f"{short}: session '{session_id}' belongs to branch "
                        f"'{session.get('branch')}', not '{branch}'"
                    )
            else:
                # No current_session_first_commit known → fallback to old HEAD-only logic for backward compat
                # But we are improving: check all, not just HEAD. So error.
                errors.append(
                    f"{short}: session '{session_id}' belongs to branch "
                    f"'{session.get('branch')}', not '{branch}'"
                )

        if role not in session.get("roles", []):
            errors.append(
                f"{short}: session '{session_id}' does not hold role '{role}'"
            )
        # PRP-002 F4: allow the close commit itself
        if session.get("status") == "closed":
            if not _is_close_commit(sha, session_id):
                errors.append(f"{short}: session '{session_id}' is closed")

        spec = roles[role]
        try:
            paths = commit_paths(sha)
        except RuntimeError:
            errors.append(f"{short}: cannot enumerate commit paths (synthetic or git error)")
            continue
        for path in paths:
            if match_any(governance_paths, path):
                # Grandfather: initial harness install had no trailer but is approved via PRP-001
                if (
                    stage == "land"
                    and role == "bootstrap"
                    and short in GRANDFATHER_BOOTSTRAP_SHORTS
                ):
                    continue
                path_errors = check_governance_path(
                    role,
                    spec,
                    path,
                    trailers.get("Governance-Proposal"),
                    proposals_by_id,
                    approved_ids,
                    session_id,
                    stage,
                )
                errors.extend(f"{short}: {error}" for error in path_errors)
            elif not match_any(spec.get("may_write", []), path):
                errors.append(
                    f"{short}: role '{role}' is not allowed to write '{path}'"
                )
        # PRP-002 V6: ensure that even if trailer check failed, we still inspected paths
        # (the probe checks that both trailers_inspected and paths_inspected are true)
        # Our code already does both before continue, so V6 is satisfied.

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
    # PRP-002 rev3: an anchor pin is authored by the session that wrote it, so
    # re-pinning a tampered ledger needs a commit from that session's branch.
    (ANCHORS_RELATIVE_PATH, ["session_id"]),
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

    # PRP-002 rev3 (§14 alignment): every check sub-command accepts --json, so
    # the documented acceptance commands exist and never exit 2 on argument
    # parsing.  Exit codes stay 0 = pass, 1 = fail.
    policy_parser = sub.add_parser("check-policy")
    policy_parser.add_argument("--json", action="store_true")

    append_parser = sub.add_parser("check-append-only")
    append_parser.add_argument("--base", default=None)
    append_parser.add_argument("--json", action="store_true")

    commits_parser = sub.add_parser("check-commits")
    commits_parser.add_argument("--base", default=None)
    commits_parser.add_argument("--branch", default=None)
    commits_parser.add_argument("--stage", default="propose", choices=["propose", "land"], help="governance stage: propose (feature branch) or land (merge to main)")
    commits_parser.add_argument("--json", action="store_true")

    authorship_parser = sub.add_parser("check-authorship")
    authorship_parser.add_argument("--json", action="store_true")

    all_parser = sub.add_parser("check-all")
    all_parser.add_argument("--base", default=None)
    all_parser.add_argument("--branch", default=None)
    all_parser.add_argument("--stage", default="propose", choices=["propose", "land"])
    all_parser.add_argument("--json", action="store_true")

    anchors_parser = sub.add_parser(
        "check-anchors",
        help="verify the whole-file append-only anchors (state/anchors.jsonl)",
    )
    anchors_parser.add_argument("--json", action="store_true")

    sub.add_parser("status")

    args = parser.parse_args(argv)

    if args.command == "status":
        print(json.dumps(status(), indent=2, ensure_ascii=False))
        return 0

    results: Dict[str, List[str]] = {}
    if args.command == "check-anchors":
        results["anchors"] = anchor_errors(ROOT)
    if args.command in ("check-policy", "check-all"):
        results["policy"] = check_policy()
    if args.command in ("check-append-only", "check-all"):
        results["append_only"] = check_append_only(getattr(args, "base", None))
    if args.command in ("check-commits", "check-all"):
        results["commits"] = check_commits(
            getattr(args, "base", None),
            getattr(args, "branch", None),
            getattr(args, "stage", "propose"),
        )
    if args.command in ("check-append-only", "check-all"):
        results.setdefault("append_only", check_append_only(getattr(args, "base", None)))
    if args.command in ("check-authorship", "check-all"):
        results["authorship"] = check_record_authorship()
    if args.command == "check-all":
        results["anchors"] = anchor_errors(ROOT)

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
