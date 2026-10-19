#!/usr/bin/env python3
"""Read-only independent negative probes for PRP-001 governance defects (G1-G4).

Run from the repository root. Fixtures and mocks are in memory only; no
protected files, Git history, or state records are modified. Exit 1 means
that at least one expected governance rejection was not enforced.

These probes are the executable acceptance criteria for PRP-002:
- G1: bootstrap land requires independent approval
- G2: merge commits are audited
- G3: approval rejects failed/missing required checks
- G4: multiple reviews from one session remain distinct

PRP-002 must make all four enforced=true.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import researchos_guard as guard
import validate_researchos as validator
from researchos_common import load_policy, resolve_effective


def run_probes():
    policy = load_policy()
    observations = []

    errors = guard.check_governance_path(
        "bootstrap", policy["roles"]["bootstrap"],
        "scripts/researchos_guard.py", None, {}, set(),
        "SES-c4426c6b", "land",
    )
    observations.append({
        "name": "bootstrap_land_requires_independent_approval",
        "expected": "reject an unapproved governance change at land",
        "errors": errors,
        "enforced": bool(errors),
        "scope": "direct policy function, not a real main merge",
    })

    # A merge with no trailers and protected-path changes must not disappear
    # from the audit. The current implementation must inspect both.
    with patch.object(guard, "commits_in_range", return_value=["synthetic-merge"]), \
         patch.object(guard, "is_merge", return_value=True), \
         patch.object(guard, "commit_trailers", return_value={}) as trailers, \
         patch.object(guard, "commit_paths", return_value=["scripts/x.py"]) as paths:
        errors = guard.check_commits(branch="arena/e7ac466a-researchos", stage="land")
        observations.append({
            "name": "merge_commits_are_audited",
            "expected": "reject merge with no session trailers or approval",
            "errors": errors,
            "enforced": bool(errors),
            "trailers_inspected": trailers.called,
            "paths_inspected": paths.called,
            "scope": "mocked Git boundary; no real merge performed",
        })

    # Three distinct roles/sessions: rejection should arise from the failed
    # check, not from self-review or self-approval. IDs below are test fixtures.
    sessions = [
        {"session_id": "SES-fixture-p", "branch": "arena/fixture-p", "roles": ["proposer"]},
        {"session_id": "SES-fixture-v", "branch": "arena/fixture-v", "roles": ["verifier"]},
        {"session_id": "SES-fixture-a", "branch": "arena/fixture-a", "roles": ["approver"]},
    ]
    proposal = {"proposal_id": "PRP-999", "session_id": "SES-fixture-p", "status": "pending_review"}
    review = {
        "review_id": "REV-999", "proposal_id": "PRP-999",
        "session_id": "SES-fixture-v", "result": "pass",
        "checks": [{"name": "regression_tests", "result": "fail"}],
    }
    approval = {
        "approval_id": "APR-999", "proposal_id": "PRP-999",
        "session_id": "SES-fixture-a", "decision": "approved", "review_ids": ["REV-999"],
    }
    queue = {
        "queue_id": "RQ-999", "proposal_id": "PRP-999", "status": "completed",
        "created_by_session": "SES-fixture-p", "claimed_by_session": "SES-fixture-v",
        "review_id": "REV-999", "required_checks": ["governance_review", "regression_tests"],
    }
    errors, warnings = [], []
    validator.validate_governance(
        sessions, [proposal], [review], [approval], [queue], sessions, errors, warnings,
    )
    observations.append({
        "name": "approval_rejects_failed_or_missing_required_checks",
        "expected": "reject pass summary containing a failed check and missing governance_review",
        "errors": errors, "warnings": warnings, "enforced": bool(errors),
        "scope": "governance validator with in-memory fixtures; not end-to-end CI",
    })
    # queue._load and verify.main omit id_key when resolving reviews.
    # A verifier legitimately writing two reviews is grouped by session_id.
    second_review = dict(review, review_id="REV-998")
    _, untyped_errors, _ = resolve_effective([review, second_review])
    _, typed_errors, _ = resolve_effective([review, second_review], "review_id")
    # After PRP-002 G4 fix, queue._load and verify use typed resolution (review_id),
    # so the correct check is typed_errors == []
    observations.append({
        "name": "multiple_reviews_from_one_session_remain_distinct",
        "expected": "two distinct review IDs resolve without revision errors when using review_id",
        "untyped_errors": untyped_errors, "typed_errors": typed_errors,
        "enforced": not typed_errors,
        "scope": "same helper invocation as queue._load (now load_effective with review_id), with in-memory review fixtures",
    })
    return observations


if __name__ == "__main__":
    results = run_probes()
    print(json.dumps(results, indent=2, ensure_ascii=False))
    sys.exit(0 if all(item["enforced"] for item in results) else 1)
