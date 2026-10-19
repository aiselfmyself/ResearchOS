#!/usr/bin/env python3
"""
ResearchOS Deterministic Core Validator (hardened, governance-aware)

Checks
------
1. Schema validation (JSON Schema draft-07 subset, stdlib only).
2. Revision chains: a correction is a new line with a higher ``revision`` and a
   ``supersedes`` hash matching the previous line.
3. ID uniqueness across every state file (after revisions are collapsed).
4. Referential integrity between sources, evidence, claims, verifications,
   hypotheses, sessions, proposals, reviews, approvals, and the review queue.
5. Governor separation: a proposal, its review, and its approval must come from
   three different sessions; an approval requires a passing review; bootstrap is
   limited to one session; a branch hosts at most one active session.
6. Claim promotion: a *new* ``supported`` claim needs an approved proposal or a
   passing verification from a different session.  Legacy records (hashes listed
   in ``policy/state_baseline.json``) are grandfathered.
7. Git provenance: every ``Informed-By`` trailer must resolve to an ancestor of
   the citing commit.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from researchos_common import (  # noqa: E402
    COLLECTION_ID_KEYS,
    LEGACY_STATE_FILES,
    STATE_FILES,
    is_legacy,
    line_hash,
    load_baseline,
    read_jsonl,
    resolve_effective,
)

LEGACY_RELATIVES = set(LEGACY_STATE_FILES)


# --------------------------------------------------------------------------
# Loading helpers
# --------------------------------------------------------------------------


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    return read_jsonl(Path(path))


# --------------------------------------------------------------------------
# 1. Minimal JSON-Schema validator
# --------------------------------------------------------------------------


def _is_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def validate_node(value: Any, schema: Dict[str, Any], path: str) -> List[str]:
    errors: List[str] = []

    expected = schema.get("type")
    if expected is not None:
        expected_types = expected if isinstance(expected, list) else [expected]
        if not any(_is_type(value, t) for t in expected_types):
            errors.append(
                f"{path}: expected type {expected_types}, got {type(value).__name__}"
            )
            return errors

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value {value!r} is not one of {schema['enum']}")

    if isinstance(value, dict):
        for req in schema.get("required", []):
            if req not in value:
                errors.append(f"{path}: missing required field '{req}'")

        props = schema.get("properties", {})
        for key, child in value.items():
            if key in props:
                errors.extend(validate_node(child, props[key], f"{path}.{key}"))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: unexpected additional property '{key}'")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: expected at least {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: expected at most {schema['maxItems']} items")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for idx, item in enumerate(value):
                errors.extend(validate_node(item, item_schema, f"{path}[{idx}]"))

    if isinstance(value, str) and "pattern" in schema:
        if re.search(schema["pattern"], value) is None:
            errors.append(
                f"{path}: string {value!r} does not match pattern {schema['pattern']!r}"
            )

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} is below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value} is above maximum {schema['maximum']}")

    return errors


def validate_record(
    record: Dict[str, Any], schema: Dict[str, Any], schema_name: str
) -> List[str]:
    return [
        f"{schema_name}: {err}" for err in validate_node(record, schema, schema_name)
    ]


# --------------------------------------------------------------------------
# 2. ID uniqueness
# --------------------------------------------------------------------------


def validate_unique_ids(
    collections: Dict[str, Tuple[List[Dict[str, Any]], str]]
) -> List[str]:
    errors: List[str] = []
    seen: Dict[str, str] = {}
    for label, (records, key) in collections.items():
        for idx, record in enumerate(records, 1):
            rid = record.get(key)
            if not isinstance(rid, str) or not rid:
                errors.append(f"{label} record #{idx}: missing or invalid '{key}'")
                continue
            if rid in seen:
                errors.append(
                    f"duplicate id '{rid}' in {label} (already defined in {seen[rid]})"
                )
            else:
                seen[rid] = label
    return errors


# --------------------------------------------------------------------------
# 3. Referential integrity
# --------------------------------------------------------------------------


def validate_referential_integrity(
    sources: List[Dict[str, Any]],
    evidence: List[Dict[str, Any]],
    claims: List[Dict[str, Any]],
    verifications: List[Dict[str, Any]],
    hypotheses: Optional[List[Dict[str, Any]]] = None,
) -> List[str]:
    hypotheses = hypotheses or []
    source_ids = {s["source_id"] for s in sources}
    evidence_ids = {e["evidence_id"] for e in evidence}
    claim_ids = {c["claim_id"] for c in claims}
    hypothesis_ids = {h["hypothesis_id"] for h in hypotheses}
    all_targets = source_ids | evidence_ids | claim_ids | hypothesis_ids

    errors: List[str] = []

    for e in evidence:
        if e.get("source_id") not in source_ids:
            errors.append(
                f"Evidence '{e.get('evidence_id')}' references non-existent source "
                f"'{e.get('source_id')}'"
            )

    for c in claims:
        for eid in c.get("evidence_ids", []):
            if eid not in evidence_ids:
                errors.append(
                    f"Claim '{c.get('claim_id')}' references non-existent evidence '{eid}'"
                )
        for cid in c.get("counterclaim_ids", []):
            if cid not in claim_ids:
                errors.append(
                    f"Claim '{c.get('claim_id')}' references non-existent counterclaim '{cid}'"
                )
            if cid == c.get("claim_id"):
                errors.append(
                    f"Claim '{c.get('claim_id')}' lists itself as a counterclaim"
                )

    for h in hypotheses:
        for eid in h.get("evidence_ids", []):
            if eid not in evidence_ids:
                errors.append(
                    f"Hypothesis '{h.get('hypothesis_id')}' references non-existent "
                    f"evidence '{eid}'"
                )

    for v in verifications:
        if v.get("target_id") not in all_targets:
            errors.append(
                f"Verification '{v.get('verification_id')}' references non-existent "
                f"target '{v.get('target_id')}'"
            )

    return errors


# --------------------------------------------------------------------------
# 4. Governance separation
# --------------------------------------------------------------------------


def validate_governance(
    sessions: List[Dict[str, Any]],
    proposals: List[Dict[str, Any]],
    reviews: List[Dict[str, Any]],
    approvals: List[Dict[str, Any]],
    queue: List[Dict[str, Any]],
    raw_sessions: List[Dict[str, Any]],
    errors: List[str],
    warnings: List[str],
) -> None:
    sessions_by = {s["session_id"]: s for s in sessions if "session_id" in s}
    proposals_by = {p["proposal_id"]: p for p in proposals if "proposal_id" in p}
    reviews_by = {r["review_id"]: r for r in reviews if "review_id" in r}

    # Bootstrap is a one-time installation role.
    boot = [s for s in sessions if "bootstrap" in s.get("roles", [])]
    if len(boot) > 1:
        errors.append(
            "more than one bootstrap session: "
            + ", ".join(s["session_id"] for s in boot)
        )
    if boot:
        warnings.append(
            f"bootstrap session {boot[0]['session_id']} installed the harness; "
            "its governance changes still need a post-hoc independent review"
        )

    # One active session per branch (the branch is the identity anchor).
    branches: Dict[str, str] = {}
    for session in sessions:
        if session.get("status", "active") == "closed":
            continue
        branch = session.get("branch")
        if branch in branches and branches[branch] != session["session_id"]:
            errors.append(
                f"branch '{branch}' hosts two active sessions: "
                f"{branches[branch]} and {session['session_id']}"
            )
        branches[branch] = session["session_id"]

    # A session's branch must never change across revisions.
    for record in raw_sessions:
        for later in raw_sessions:
            if (
                record.get("session_id") == later.get("session_id")
                and record is not later
                and record.get("branch") != later.get("branch")
            ):
                errors.append(
                    f"session {record.get('session_id')}: branch changed across revisions"
                )

    # Role coverage
    for proposal in proposals:
        if proposal.get("session_id") not in sessions_by:
            errors.append(
                f"Proposal '{proposal.get('proposal_id')}' references unknown session "
                f"'{proposal.get('session_id')}'"
            )
        elif "proposer" not in sessions_by[proposal["session_id"]].get("roles", []):
            warnings.append(
                f"Proposal '{proposal.get('proposal_id')}' was created by a session "
                "without the proposer role"
            )

    reviews_by_proposal: Dict[str, List[Dict[str, Any]]] = {}
    for review in reviews:
        proposal = proposals_by.get(review.get("proposal_id"))
        if proposal is None:
            errors.append(
                f"Review '{review.get('review_id')}' references unknown proposal "
                f"'{review.get('proposal_id')}'"
            )
            continue
        reviews_by_proposal.setdefault(proposal["proposal_id"], []).append(review)
        if review.get("session_id") not in sessions_by:
            errors.append(
                f"Review '{review.get('review_id')}' references unknown session "
                f"'{review.get('session_id')}'"
            )
        if review.get("session_id") == proposal.get("session_id"):
            errors.append(
                f"Review '{review.get('review_id')}' is a self-review: session "
                f"{review.get('session_id')} both proposed and reviewed "
                f"{proposal.get('proposal_id')}"
            )
        if (
            review.get("session_id") in sessions_by
            and "verifier" not in sessions_by[review["session_id"]].get("roles", [])
        ):
            warnings.append(
                f"Review '{review.get('review_id')}' was written by a session "
                "without the verifier role"
            )

    approved_ids = set()
    for approval in approvals:
        proposal = proposals_by.get(approval.get("proposal_id"))
        if proposal is None:
            errors.append(
                f"Approval '{approval.get('approval_id')}' references unknown proposal "
                f"'{approval.get('proposal_id')}'"
            )
            continue
        if approval.get("session_id") not in sessions_by:
            errors.append(
                f"Approval '{approval.get('approval_id')}' references unknown session "
                f"'{approval.get('session_id')}'"
            )
        review_ids = approval.get("review_ids", [])
        referenced = []
        for review_id in review_ids:
            review = reviews_by.get(review_id)
            if review is None:
                errors.append(
                    f"Approval '{approval.get('approval_id')}' references unknown "
                    f"review '{review_id}'"
                )
                continue
            if review.get("proposal_id") != proposal["proposal_id"]:
                errors.append(
                    f"Approval '{approval.get('approval_id')}' cites review '{review_id}' "
                    f"which targets {review.get('proposal_id')}"
                )
            referenced.append(review)

        if approval.get("decision") == "approved":
            approved_ids.add(proposal["proposal_id"])
            if proposal.get("session_id") == approval.get("session_id"):
                errors.append(
                    f"Approval '{approval.get('approval_id')}' is a self-approval: "
                    f"session {approval.get('session_id')} proposed "
                    f"{proposal['proposal_id']}"
                )
            for review in referenced:
                if review.get("session_id") == approval.get("session_id"):
                    errors.append(
                        f"Approval '{approval.get('approval_id')}' was written by a "
                        f"session that also reviewed {proposal['proposal_id']}"
                    )
            if not any(review.get("result") == "pass" for review in referenced):
                errors.append(
                    f"Approval '{approval.get('approval_id')}' is 'approved' but cites "
                    "no passing review"
                )
        elif approval.get("decision") == "rejected":
            if not referenced:
                errors.append(
                    f"Approval '{approval.get('approval_id')}' rejected a proposal "
                    "without citing a review"
                )

    for proposal in proposals:
        if proposal.get("status") == "approved" and proposal["proposal_id"] not in approved_ids:
            errors.append(
                f"Proposal '{proposal['proposal_id']}' is 'approved' but has no "
                "approved approval record"
            )
        if (
            proposal.get("status") == "pending_review"
            and proposal["proposal_id"] in approved_ids
        ):
            warnings.append(
                f"Proposal '{proposal['proposal_id']}' has an approved approval record "
                "but its status is still pending_review"
            )

    for item in queue:
        proposal_id = item.get("proposal_id")
        if proposal_id not in proposals_by:
            errors.append(
                f"Queue '{item.get('queue_id')}' references unknown proposal "
                f"'{proposal_id}'"
            )
        if item.get("created_by_session") not in sessions_by:
            errors.append(
                f"Queue '{item.get('queue_id')}' references unknown session "
                f"'{item.get('created_by_session')}'"
            )
        if item.get("status") == "claimed" and not item.get("claimed_by_session"):
            errors.append(
                f"Queue '{item.get('queue_id')}' is claimed without claimed_by_session"
            )
        if item.get("claimed_by_session") and item["claimed_by_session"] not in sessions_by:
            errors.append(
                f"Queue '{item.get('queue_id')}' references unknown claimant "
                f"'{item.get('claimed_by_session')}'"
            )
        if item.get("status") == "completed":
            if not item.get("review_id"):
                errors.append(
                    f"Queue '{item.get('queue_id')}' is completed without a review_id"
                )
            elif item["review_id"] not in reviews_by:
                errors.append(
                    f"Queue '{item.get('queue_id')}' references unknown review "
                    f"'{item.get('review_id')}'"
                )

    for item in queue:
        if item.get("status") == "open":
            warnings.append(
                f"Review queue '{item.get('queue_id')}' is open for "
                f"{item.get('proposal_id')}"
            )


# --------------------------------------------------------------------------
# 5. New-record requirements and claim promotion
# --------------------------------------------------------------------------


def validate_new_records(
    collections: Dict[str, List[Dict[str, Any]]],
    baseline: Dict[str, Any],
    errors: List[str],
    warnings: List[str],
) -> None:
    session_field = {
        "review_queue": "created_by_session",
        "sessions": "session_id",
    }
    for name, relative in STATE_FILES.items():
        records = collections.get(name, [])
        if not records:
            continue
        field = session_field.get(name, "session_id")
        for record in records:
            if is_legacy(relative, record, baseline):
                continue
            identifier = record.get("session_id") or record.get("claim_id") or record.get(
                "evidence_id"
            ) or record.get("proposal_id") or record.get("queue_id") or "?"
            if field not in record:
                errors.append(
                    f"{relative}: new record '{identifier}' has no {field}"
                )
            if not any(
                key in record for key in ("recorded_at", "created_at", "started_at")
            ):
                errors.append(
                    f"{relative}: new record '{identifier}' has no timestamp "
                    "(recorded_at / created_at / started_at)"
                )


def validate_claim_promotion(
    claims: List[Dict[str, Any]],
    verifications: List[Dict[str, Any]],
    proposals: List[Dict[str, Any]],
    approvals: List[Dict[str, Any]],
    sessions: List[Dict[str, Any]],
    baseline: Dict[str, Any],
    errors: List[str],
    warnings: List[str],
) -> None:
    approved_proposals = {
        approval.get("proposal_id")
        for approval in approvals
        if approval.get("decision") == "approved"
    }
    proposal_sessions = {
        proposal.get("proposal_id"): proposal.get("session_id") for proposal in proposals
    }
    session_ids = {session["session_id"] for session in sessions}

    for claim in claims:
        if claim.get("status") != "supported":
            continue
        if is_legacy("state/claims.jsonl", claim, baseline):
            continue
        claim_session = claim.get("session_id")
        if claim_session and claim_session not in session_ids:
            errors.append(
                f"Claim '{claim.get('claim_id')}' references unknown session "
                f"'{claim_session}'"
            )

        proposal_id = claim.get("proposal_id")
        backed_by_proposal = bool(
            proposal_id
            and proposal_id in approved_proposals
            and proposal_sessions.get(proposal_id) != claim_session
        )
        backed_by_verification = any(
            verification.get("target_id") == claim.get("claim_id")
            and verification.get("result") == "pass"
            and verification.get("session_id")
            and verification.get("session_id") != claim_session
            for verification in verifications
        )
        if not (backed_by_proposal or backed_by_verification):
            errors.append(
                f"Claim '{claim.get('claim_id')}' is 'supported' but has no approved "
                "proposal and no passing verification from a different session"
            )


# --------------------------------------------------------------------------
# 6. Git provenance
# --------------------------------------------------------------------------


def _git(args: List[str], cwd: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=cwd, text=True, stderr=subprocess.DEVNULL
    ).strip()


def _resolve_commit(ref: str, cwd: str) -> Optional[str]:
    try:
        return _git(["rev-parse", "--verify", f"{ref}^{{commit}}"], cwd)
    except subprocess.CalledProcessError:
        return None


def _is_ancestor(ancestor: str, descendant: str, cwd: str) -> bool:
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.returncode == 0


def validate_git_provenance(root: str = ".") -> List[str]:
    try:
        raw_log = _git(["log", "--format=%H%x1f%P%x1f%s%x1f%b%x1e"], root)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        return [f"Unable to read git history: {exc}"]

    entries = [e for e in raw_log.split("\x1e") if e.strip()]
    if not entries:
        return ["Git history is empty; cannot verify provenance"]

    commits: Dict[str, Dict[str, Any]] = {}
    for entry in entries:
        parts = entry.strip().split("\x1f", 3)
        sha = parts[0]
        commits[sha] = {
            "parents": parts[1].split() if len(parts) > 1 and parts[1] else [],
            "subject": parts[2] if len(parts) > 2 else "",
            "body": parts[3] if len(parts) > 3 else "",
        }

    errors: List[str] = []
    for sha, commit in commits.items():
        for line in commit["body"].splitlines():
            match = re.match(r"(?i)^informed-by:\s*(.+)$", line.strip())
            if not match:
                continue
            for ref in match.group(1).split(","):
                ref = ref.strip().strip("`")
                if not ref or ref.lower() in ("none", "root"):
                    continue
                if not re.fullmatch(r"[0-9a-fA-F]{4,40}", ref):
                    errors.append(
                        f"Commit {sha[:7]} has malformed Informed-By reference '{ref}'"
                    )
                    continue
                resolved = _resolve_commit(ref, root)
                if resolved is None:
                    errors.append(
                        f"Commit {sha[:7]} cites non-existent Informed-By SHA: '{ref}'"
                    )
                    continue
                if resolved == sha:
                    errors.append(
                        f"Commit {sha[:7]} cites itself in Informed-By: '{ref}'"
                    )
                    continue
                if not _is_ancestor(resolved, sha, root):
                    errors.append(
                        f"Commit {sha[:7]} cites non-ancestor Informed-By SHA: "
                        f"'{ref}' resolves to {resolved[:7]} which is not an ancestor"
                    )

    return errors


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------


def _safe(records: List[Dict[str, Any]], key: str) -> Tuple[List[Dict[str, Any]], str]:
    return records, key


def run_all_checks(root: str = ".") -> Dict[str, Any]:
    """Run every check and return a structured report (no printing, no exit)."""
    root_path = Path(root).resolve()
    schema_dir = root_path / "schemas"
    state_dir = root_path / "state"
    previous_cwd = Path.cwd()
    os.chdir(root_path)  # git helpers and baseline paths are repository-relative

    try:
        schema_files = [
            "source",
            "evidence",
            "claim",
            "verification",
            "hypothesis",
            "session",
            "proposal",
            "review",
            "approval",
            "review_queue",
        ]
        schemas = {
            name: load_json(str(schema_dir / f"{name}.json")) for name in schema_files
        }

        raw: Dict[str, List[Dict[str, Any]]] = {}
        collections: Dict[str, List[Dict[str, Any]]] = {}
        errors: List[str] = []
        warnings: List[str] = []

        for name in STATE_FILES:
            raw[name] = load_jsonl(str(state_dir / f"{Path(STATE_FILES[name]).name}"))
            effective, revision_errors, revision_warnings = resolve_effective(
                raw[name], COLLECTION_ID_KEYS[name]
            )
            errors.extend(f"{STATE_FILES[name]}: {err}" for err in revision_errors)
            warnings.extend(f"{STATE_FILES[name]}: {warn}" for warn in revision_warnings)
            collections[name] = effective

        schema_map = {
            "sources": "source",
            "evidence": "evidence",
            "claims": "claim",
            "verifications": "verification",
            "hypotheses": "hypothesis",
            "sessions": "session",
            "proposals": "proposal",
            "reviews": "review",
            "approvals": "approval",
            "review_queue": "review_queue",
        }
        schema_label = {
            "sources": "Source",
            "evidence": "Evidence",
            "claims": "Claim",
            "verifications": "Verification",
            "hypotheses": "Hypothesis",
            "sessions": "Session",
            "proposals": "Proposal",
            "reviews": "Review",
            "approvals": "Approval",
            "review_queue": "QueueItem",
        }
        for name, schema_name in schema_map.items():
            for record in collections[name]:
                errors.extend(
                    validate_record(record, schemas[schema_name], schema_label[name])
                )

        id_keys = {
            "Source": (collections["sources"], "source_id"),
            "Evidence": (collections["evidence"], "evidence_id"),
            "Claim": (collections["claims"], "claim_id"),
            "Verification": (collections["verifications"], "verification_id"),
            "Hypothesis": (collections["hypotheses"], "hypothesis_id"),
            "Session": (collections["sessions"], "session_id"),
            "Proposal": (collections["proposals"], "proposal_id"),
            "Review": (collections["reviews"], "review_id"),
            "Approval": (collections["approvals"], "approval_id"),
            "Queue": (collections["review_queue"], "queue_id"),
        }
        errors.extend(validate_unique_ids(id_keys))

        errors.extend(
            validate_referential_integrity(
                collections["sources"],
                collections["evidence"],
                collections["claims"],
                collections["verifications"],
                collections["hypotheses"],
            )
        )

        validate_governance(
            collections["sessions"],
            collections["proposals"],
            collections["reviews"],
            collections["approvals"],
            collections["review_queue"],
            raw["sessions"],
            errors,
            warnings,
        )

        baseline = load_baseline()
        if not baseline:
            warnings.append(
                "policy/state_baseline.json is missing; legacy grandfathering is disabled"
            )
        else:
            validate_new_records(collections, baseline, errors, warnings)
            validate_claim_promotion(
                collections["claims"],
                collections["verifications"],
                collections["proposals"],
                collections["approvals"],
                collections["sessions"],
                baseline,
                errors,
                warnings,
            )

        errors.extend(validate_git_provenance(str(root_path)))

        for claim in collections["claims"]:
            if claim.get("status") == "supported":
                passed = any(
                    v.get("target_id") == claim["claim_id"]
                    and v.get("result") == "pass"
                    for v in collections["verifications"]
                )
                if not passed:
                    warnings.append(
                        f"Claim '{claim['claim_id']}' is 'supported' but has no "
                        "passing verification"
                    )
        for source in collections["sources"]:
            if not any(
                e.get("source_id") == source["source_id"]
                for e in collections["evidence"]
            ):
                warnings.append(
                    f"Source '{source['source_id']}' has no linked evidence"
                )
        for ev in collections["evidence"]:
            if "quote_type" not in ev:
                warnings.append(
                    f"Evidence '{ev['evidence_id']}' does not declare quote_type "
                    "(verbatim vs paraphrase)"
                )

        return {
            "root": str(root_path),
            "counts": {
                "sources": len(collections["sources"]),
                "evidence": len(collections["evidence"]),
                "claims": len(collections["claims"]),
                "verifications": len(collections["verifications"]),
                "hypotheses": len(collections["hypotheses"]),
                "sessions": len(collections["sessions"]),
                "proposals": len(collections["proposals"]),
                "reviews": len(collections["reviews"]),
                "approvals": len(collections["approvals"]),
                "queue": len(collections["review_queue"]),
            },
            "errors": errors,
            "warnings": warnings,
            "source_ids": sorted(s["source_id"] for s in collections["sources"]),
        }
    finally:
        os.chdir(previous_cwd)


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="ResearchOS deterministic core validation"
    )
    parser.add_argument(
        "--root", default=".", help="repository root (default: current directory)"
    )
    parser.add_argument("--quiet", action="store_true", help="only print failures")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not args.quiet:
        print("=" * 60)
        print(" ResearchOS Core Deterministic Validation (governance) ")
        print("=" * 60)

    try:
        report = run_all_checks(args.root)
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not load research state: {exc}")
        return 1

    counts = report["counts"]
    if not args.quiet:
        print(
            "Loaded: {sources} Sources, {evidence} Evidence, {claims} Claims, "
            "{verifications} Verifications, {hypotheses} Hypotheses".format(**counts)
        )
        print(
            "        {sessions} Sessions, {proposals} Proposals, {reviews} Reviews, "
            "{approvals} Approvals, {queue} Queue".format(**counts)
        )

    if report["errors"]:
        print(f"FAIL: {len(report['errors'])} deterministic check error(s):")
        for err in report["errors"]:
            print(f"  - {err}")
        for warning in report["warnings"]:
            print(f"  warning: {warning}")
        return 1

    if not args.quiet:
        print("✓ Schema validation PASS (types, enums, required fields, items)")
        print("✓ Revision chains PASS (append-only corrections)")
        print("✓ ID uniqueness PASS")
        print("✓ Referential integrity PASS")
        print("✓ Governance separation PASS (proposer ≠ reviewer ≠ approver)")
        print("✓ Git provenance Informed-By PASS (existence + ancestry)")

    if report["warnings"] and not args.quiet:
        print(f"\nWarnings ({len(report['warnings'])}):")
        for warning in report["warnings"]:
            print(f"  - {warning}")

    if not args.quiet:
        print("=" * 60)
        print(" ALL DETERMINISTIC CHECKS PASSED ")
        print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
