#!/usr/bin/env python3
"""Shared helpers for the ResearchOS governance harness.

Design notes
------------
* **Append-only state.**  A correction is a *new line* with the same id,
  a higher ``revision`` and a ``supersedes`` field holding the canonical hash
  of the previous line.  Existing lines are never edited or deleted.
* **Legacy grandfathering.**  Records that existed at the governance baseline
  (`policy/state_baseline.json`) are identified by their line hash and are
  exempt from the new requirements.  Everything appended after the baseline
  must comply.
* **No external dependencies.**  The harness must run on a bare runner.
* **COLLECTION_ID_KEYS:** Every call to ``resolve_effective`` for a state
  collection MUST pass the collection-specific id_key (e.g. ``review_id`` for
  reviews, ``queue_id`` for review_queue).  Using the default ``ID_KEYS``
  order silently groups reviews by ``session_id`` and breaks
  ``researchos_queue.py complete`` for verifiers with multiple REV-*.
  Use ``load_effective(name)`` which does this automatically.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "state"
POLICY_DIR = ROOT / "policy"
SCHEMA_DIR = ROOT / "schemas"

ROLES_POLICY = POLICY_DIR / "roles.json"
STATE_BASELINE = POLICY_DIR / "state_baseline.json"

STATE_FILES: Dict[str, str] = {
    "sources": "state/sources.jsonl",
    "evidence": "state/evidence.jsonl",
    "claims": "state/claims.jsonl",
    "verifications": "state/verifications.jsonl",
    "hypotheses": "state/hypotheses.jsonl",
    "sessions": "state/sessions.jsonl",
    "proposals": "state/proposals.jsonl",
    "reviews": "state/reviews.jsonl",
    "approvals": "state/approvals.jsonl",
    "review_queue": "state/review_queue.jsonl",
}

LEGACY_STATE_FILES: List[str] = [
    "state/sources.jsonl",
    "state/evidence.jsonl",
    "state/claims.jsonl",
    "state/verifications.jsonl",
    "state/hypotheses.jsonl",
]

ID_KEYS = (
    "source_id",
    "evidence_id",
    "claim_id",
    "verification_id",
    "hypothesis_id",
    "session_id",
    "proposal_id",
    "review_id",
    "approval_id",
    "queue_id",
)

COLLECTION_ID_KEYS: Dict[str, str] = {
    "sources": "source_id",
    "evidence": "evidence_id",
    "claims": "claim_id",
    "verifications": "verification_id",
    "hypotheses": "hypothesis_id",
    "sessions": "session_id",
    "proposals": "proposal_id",
    "reviews": "review_id",
    "approvals": "approval_id",
    "review_queue": "queue_id",
}

# ---------------------------------------------------------------------------
# JSON / hashing
# ---------------------------------------------------------------------------


def canonical_json(record: Dict[str, Any]) -> str:
    return json.dumps(
        record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def line_hash(record: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(record).encode("utf-8")).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# JSONL I/O
# ---------------------------------------------------------------------------


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{index}: {exc}") from exc
    return records


def read_jsonl_text(text: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def append_jsonl(path: Path, record: Dict[str, Any]) -> str:
    """Append one record. Returns the canonical line hash."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json(record)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(payload + "\n")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def record_id(record: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    for key in ID_KEYS:
        if key in record:
            return key, str(record[key])
    return None, None


# ---------------------------------------------------------------------------
# Revisions
# ---------------------------------------------------------------------------


def resolve_effective(
    records: List[Dict[str, Any]],
    id_key: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    """Collapse revisions.

    ``id_key`` must be supplied for collections whose records also carry other
    id-like fields (for example an evidence record carries both ``evidence_id``
    and ``source_id``).  Without it the first matching key in ``ID_KEYS`` wins,
    which silently groups evidence by source.

    Returns ``(effective_records, errors, warnings)``.  ``effective_records``
    keeps the latest revision of every id in first-seen order.
    """
    errors: List[str] = []
    warnings: List[str] = []
    order: List[str] = []
    versions: Dict[str, List[Dict[str, Any]]] = {}

    for record in records:
        if id_key is not None:
            key = id_key
            value = record.get(id_key)
        else:
            key, value = record_id(record)
        if key is None or value is None:
            errors.append(f"record has no known id field: {record}")
            continue
        if value not in versions:
            versions[value] = []
            order.append(value)
        versions[value].append(record)

    effective: List[Dict[str, Any]] = []
    for value in order:
        chain = versions[value]
        annotated: List[Tuple[int, int, Dict[str, Any]]] = []
        for position, record in enumerate(chain):
            revision = record.get("revision", 1)
            if not isinstance(revision, int) or isinstance(revision, bool):
                errors.append(f"{value}: revision must be an integer")
                revision = 1
            annotated.append((revision, position, record))

        annotated.sort(key=lambda item: (item[0], item[1]))
        previous_hash: Optional[str] = None
        seen_revisions: set = set()
        for index, (revision, _position, record) in enumerate(annotated):
            if revision in seen_revisions:
                errors.append(f"{value}: duplicate revision {revision}")
            seen_revisions.add(revision)

            if index == 0:
                if revision != 1:
                    errors.append(
                        f"{value}: first stored revision is {revision}, expected 1"
                    )
            else:
                expected = record.get("supersedes")
                if not expected:
                    errors.append(
                        f"{value}: revision {revision} is missing 'supersedes'"
                    )
                elif previous_hash and expected != previous_hash:
                    errors.append(
                        f"{value}: revision {revision} 'supersedes' does not match "
                        f"the previous line hash"
                    )
            previous_hash = line_hash(record)

        latest = annotated[-1][2]
        if latest.get("deleted") is True:
            warnings.append(f"{value}: latest revision is marked deleted")
            continue
        effective.append(latest)

    return effective, errors, warnings


# ---------------------------------------------------------------------------
# Baseline / legacy detection
# ---------------------------------------------------------------------------


def load_baseline() -> Dict[str, Any]:
    if not STATE_BASELINE.exists():
        return {}
    with STATE_BASELINE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def legacy_hashes(baseline: Optional[Dict[str, Any]] = None) -> Dict[str, set]:
    baseline = baseline if baseline is not None else load_baseline()
    return {
        path: set(hashes)
        for path, hashes in (baseline.get("legacy_line_sha256") or {}).items()
    }


def is_legacy(
    relative_path: str,
    record: Dict[str, Any],
    baseline: Optional[Dict[str, Any]] = None,
) -> bool:
    hashes = legacy_hashes(baseline).get(relative_path, set())
    return line_hash(record) in hashes


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def git(*args: str, cwd: Optional[Path] = None, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd or ROOT),
        text=True,
        capture_output=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout.strip()


def git_show(rev: str, path: str) -> Optional[str]:
    result = subprocess.run(
        ["git", "show", f"{rev}:{path}"],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def current_branch() -> str:
    env = os.environ.get("GITHUB_REF_NAME")
    if env:
        return env
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    name = result.stdout.strip()
    return name if name and name != "HEAD" else os.environ.get("GITHUB_HEAD_REF", "HEAD")


def commit_trailers(rev: str) -> Dict[str, str]:
    body = git("log", "-1", "--format=%B", rev)
    trailers: Dict[str, str] = {}
    for line in body.splitlines():
        match = re.match(r"^([A-Za-z0-9-]+):\s*(.+?)\s*$", line.strip())
        if match:
            trailers.setdefault(match.group(1), match.group(2))
    return trailers


def commit_paths(rev: str) -> List[str]:
    output = git("show", "--name-only", "--format=", rev)
    return [line.strip() for line in output.splitlines() if line.strip()]


def commits_in_range(base: str, first_parent: bool = False) -> List[str]:
    args = ["rev-list", "--reverse"]
    if first_parent:
        args.append("--first-parent")
    args.append(f"{base}..HEAD")
    output = git(*args)
    return [line.strip() for line in output.splitlines() if line.strip()]


def is_merge(rev: str) -> bool:
    try:
        parents = git("rev-list", "--parents", "-n", "1", rev).split()
    except RuntimeError:
        # Synthetic or invalid SHA (e.g. probe mock) — treat conservatively
        return False
    return len(parents) > 2


def commit_parents(rev: str) -> Optional[List[str]]:
    """Return parent SHAs of rev, or None if rev is synthetic/invalid."""
    try:
        parts = git("rev-list", "--parents", "-n", "1", rev).split()
    except RuntimeError:
        return None
    # parts[0] is rev itself, rest are parents
    if not parts:
        return None
    return parts[1:] if len(parts) > 1 else []


def is_ancestor(ancestor: str, descendant: str) -> Optional[bool]:
    """Check if ancestor is ancestor of descendant. None on error/synthetic."""
    if not ancestor or not descendant:
        return None
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=str(ROOT),
        capture_output=True,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    # Error (e.g. synthetic sha, unknown rev)
    return None


def commits_in_merge_second_parent(merge_sha: str, base_commit: str, first_parent_sha: str) -> List[str]:
    """List commits from second-parent side of a merge, excluding first-parent history.
    
    Used to audit governance paths introduced via a side branch that --first-parent hides.
    Returns [] on error or if merge has no second parent.
    """
    parents = commit_parents(merge_sha)
    if parents is None or len(parents) < 2:
        return []
    # parents[0] is first_parent, parents[1:] are other parents
    result: List[str] = []
    for other in parents[1:]:
        try:
            # commits reachable from other but not from first_parent nor base
            out = git("rev-list", "--reverse", f"{base_commit}..{other}", f"^{first_parent_sha}")
            result.extend(line.strip() for line in out.splitlines() if line.strip())
        except RuntimeError:
            # If enumeration fails (synthetic), report as error elsewhere; don't crash
            continue
    return result


# ---------------------------------------------------------------------------
# Path matching (supports ** across separators, * within a segment)
# ---------------------------------------------------------------------------


def path_matches(pattern: str, path: str) -> bool:
    regex: List[str] = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "*":
            if pattern[index : index + 2] == "**":
                regex.append(".*")
                index += 2
                if index < len(pattern) and pattern[index] == "/":
                    index += 1
                continue
            regex.append("[^/]*")
            index += 1
        elif char == "?":
            regex.append("[^/]")
            index += 1
        else:
            regex.append(re.escape(char))
            index += 1
    return re.fullmatch("".join(regex), path) is not None


def match_any(patterns: Sequence[str], path: str) -> bool:
    return any(path_matches(pattern, path) for pattern in patterns)


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


def load_policy() -> Dict[str, Any]:
    with ROLES_POLICY.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def policy_errors(policy: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    roles = policy.get("roles") or {}
    if not roles:
        errors.append("policy: no roles defined")
    for name, spec in roles.items():
        if not isinstance(spec.get("may_write"), list):
            errors.append(f"policy: role '{name}' has no may_write list")
        if not spec.get("description"):
            errors.append(f"policy: role '{name}' has no description")
    for path in policy.get("governance_paths", []):
        if not isinstance(path, str) or not path:
            errors.append("policy: invalid governance path")
    return errors


# ---------------------------------------------------------------------------
# Record lookups
# ---------------------------------------------------------------------------


def by_id(records: Iterable[Dict[str, Any]], key: str) -> Dict[str, Dict[str, Any]]:
    return {
        str(record[key]): record
        for record in records
        if isinstance(record, dict) and key in record
    }


def load_collection(name: str) -> List[Dict[str, Any]]:
    return read_jsonl(ROOT / STATE_FILES[name])


def load_effective(name: str) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    return resolve_effective(load_collection(name), COLLECTION_ID_KEYS.get(name))


def now_utc() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def next_id(records: List[Dict[str, Any]], key: str, prefix: str) -> str:
    """Generate next sequential ID. WARNING: parallel session lines collide.

    Two independent proposers forking the same parent will mint the same next
    ID (e.g. PRP-002) and cause duplicate revision errors on union.  For
    governance IDs (PRP-*, REV-*, APR-*, RQ-*) use a manual unique suffix or
    await PRP-003's UUID scheme.  The function is kept for research claims
    where collision is low-impact.
    """
    highest = 0
    for record in records:
        value = str(record.get(key, ""))
        if value.startswith(prefix):
            suffix = value[len(prefix) :].lstrip("-")
            if suffix.isdigit():
                highest = max(highest, int(suffix))
    return f"{prefix}-{highest + 1:03d}"


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":  # pragma: no cover - debugging helper
    print(json.dumps(load_policy(), indent=2, ensure_ascii=False))
    sys.exit(0)
