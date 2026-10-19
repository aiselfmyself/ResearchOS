"""Regression tests for the ResearchOS governance harness.

These tests encode the *rules*, not just the happy path:

* a proposer cannot review or approve its own proposal;
* a reviewer cannot approve the proposal it reviewed;
* an approval needs a passing review;
* bootstrap is a one-time role and a branch hosts one active session;
* state files only grow (append-only) and corrections form a hash chain;
* a new ``supported`` claim needs backing from a different session.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import researchos_guard as guard  # noqa: E402
from scripts import validate_researchos as vr  # noqa: E402
from scripts.researchos_common import (  # noqa: E402
    line_hash,
    path_matches,
    resolve_effective,
)


def session(session_id, branch, roles, status="active"):
    return {
        "session_id": session_id,
        "branch": branch,
        "roles": roles,
        "kind": "agent",
        "started_at": "2026-10-19T00:00:00+00:00",
        "policy_version": 1,
        "status": status,
    }


def proposal(proposal_id="PRP-001", session_id="SES-a", status="pending_review"):
    return {
        "proposal_id": proposal_id,
        "title": "t",
        "kind": "governance",
        "summary": "s",
        "changes": ["scripts/x.py"],
        "session_id": session_id,
        "status": status,
        "created_at": "2026-10-19T00:00:00+00:00",
    }


def review(review_id, proposal_id, session_id, result="pass"):
    return {
        "review_id": review_id,
        "proposal_id": proposal_id,
        "session_id": session_id,
        "checks": [{"name": "c", "result": "pass"}],
        "result": result,
        "created_at": "2026-10-19T00:00:00+00:00",
    }


def approval(approval_id, proposal_id, session_id, review_ids, decision="approved"):
    return {
        "approval_id": approval_id,
        "proposal_id": proposal_id,
        "session_id": session_id,
        "review_ids": review_ids,
        "decision": decision,
        "created_at": "2026-10-19T00:00:00+00:00",
    }


def govern(sessions, proposals, reviews, approvals, queue=None, raw_sessions=None):
    errors: list = []
    warnings: list = []
    vr.validate_governance(
        sessions,
        proposals,
        reviews,
        approvals,
        queue or [],
        raw_sessions if raw_sessions is not None else sessions,
        errors,
        warnings,
    )
    return errors, warnings


class PathPolicyTest(unittest.TestCase):
    def test_governance_globbing(self) -> None:
        self.assertTrue(path_matches("scripts/**", "scripts/researchos_guard.py"))
        self.assertTrue(path_matches("gitswarm/**", "gitswarm/solvers/greedy.py"))
        self.assertTrue(path_matches("state/*.jsonl", "state/claims.jsonl"))
        self.assertFalse(path_matches("state/*.jsonl", "state/nested/claims.jsonl"))
        self.assertFalse(path_matches("scripts/**", "docs/scripts.md"))

    def test_policy_is_valid(self) -> None:
        self.assertEqual(guard.check_policy(), [])

    def test_roles_are_separated_by_path(self) -> None:
        import json

        policy = json.loads((ROOT / "policy" / "roles.json").read_text(encoding="utf-8"))
        verifier_paths = policy["roles"]["verifier"]["may_write"]
        for forbidden in (
            "scripts/researchos_guard.py",
            "schemas/claim.json",
            "tests/test_governance.py",
            ".github/workflows/verify-github-actions.yml",
        ):
            self.assertFalse(
                any(path_matches(pattern, forbidden) for pattern in verifier_paths),
                f"verifier must not be able to write {forbidden}",
            )
        approver_paths = policy["roles"]["approver"]["may_write"]
        for forbidden in ("state/claims.jsonl", "state/reviews.jsonl", "scripts/x.py"):
            self.assertFalse(
                any(path_matches(pattern, forbidden) for pattern in approver_paths),
                f"approver must not be able to write {forbidden}",
            )


class RevisionChainTest(unittest.TestCase):
    def test_two_revisions_resolve_to_latest(self) -> None:
        first = {"session_id": "SES-a", "roles": ["proposer"]}
        second = {
            "session_id": "SES-a",
            "roles": ["proposer", "verifier"],
            "revision": 2,
            "supersedes": line_hash(first),
        }
        effective, errors, _warnings = resolve_effective([first, second], "session_id")
        self.assertEqual(errors, [])
        self.assertEqual(len(effective), 1)
        self.assertEqual(effective[0]["roles"], ["proposer", "verifier"])

    def test_tampered_supersedes_is_rejected(self) -> None:
        first = {"session_id": "SES-a", "roles": ["proposer"]}
        second = {
            "session_id": "SES-a",
            "roles": ["proposer", "verifier"],
            "revision": 2,
            "supersedes": "0" * 64,
        }
        _effective, errors, _warnings = resolve_effective([first, second], "session_id")
        self.assertTrue(any("supersedes" in error for error in errors), errors)

    def test_duplicate_revision_is_rejected(self) -> None:
        first = {"session_id": "SES-a", "roles": ["proposer"]}
        second = dict(first)
        _effective, errors, _warnings = resolve_effective([first, second], "session_id")
        self.assertTrue(any("duplicate revision" in error for error in errors), errors)

    def test_evidence_grouped_by_explicit_key(self) -> None:
        """Evidence carries both evidence_id and source_id; grouping must use evidence_id."""
        records = [
            {"evidence_id": "EVD-001", "source_id": "SRC-001"},
            {"evidence_id": "EVD-002", "source_id": "SRC-001"},
        ]
        effective, errors, _warnings = resolve_effective(records, "evidence_id")
        self.assertEqual(errors, [])
        self.assertEqual({r["evidence_id"] for r in effective}, {"EVD-001", "EVD-002"})


class AppendOnlyTest(unittest.TestCase):
    def test_appending_is_allowed(self) -> None:
        historical = '{"a":1}\n{"b":2}\n'
        current = historical + '{"c":3}\n'
        self.assertEqual(guard.prefix_violations("state/x.jsonl", historical, current), [])

    def test_editing_a_line_is_rejected(self) -> None:
        historical = '{"a":1}\n{"b":2}\n'
        current = '{"a":1}\n{"b":999}\n'
        errors = guard.prefix_violations("state/x.jsonl", historical, current)
        self.assertTrue(any("line 2" in error for error in errors), errors)

    def test_deleting_a_line_is_rejected(self) -> None:
        historical = '{"a":1}\n{"b":2}\n'
        current = '{"a":1}\n'
        errors = guard.prefix_violations("state/x.jsonl", historical, current)
        self.assertTrue(any("append-only" in error for error in errors), errors)

    def test_repository_state_is_append_only(self) -> None:
        self.assertEqual(guard.check_append_only(), [])


class SeparationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.sessions = [
            session("SES-a", "arena/a-review", ["proposer"]),
            session("SES-b", "arena/b-review", ["verifier"]),
            session("SES-c", "arena/c-review", ["approver"]),
        ]

    def test_clean_separation_passes(self) -> None:
        errors, _warnings = govern(
            self.sessions,
            [proposal()],
            [review("REV-001", "PRP-001", "SES-b")],
            [approval("APR-001", "PRP-001", "SES-c", ["REV-001"])],
        )
        self.assertEqual(errors, [])

    def test_self_review_is_rejected(self) -> None:
        errors, _warnings = govern(
            self.sessions,
            [proposal()],
            [review("REV-001", "PRP-001", "SES-a")],
            [],
        )
        self.assertTrue(any("self-review" in error for error in errors), errors)

    def test_self_approval_is_rejected(self) -> None:
        errors, _warnings = govern(
            self.sessions,
            [proposal()],
            [review("REV-001", "PRP-001", "SES-b")],
            [approval("APR-001", "PRP-001", "SES-a", ["REV-001"])],
        )
        self.assertTrue(any("self-approval" in error for error in errors), errors)

    def test_reviewer_cannot_also_approve(self) -> None:
        errors, _warnings = govern(
            self.sessions,
            [proposal()],
            [review("REV-001", "PRP-001", "SES-b")],
            [approval("APR-001", "PRP-001", "SES-b", ["REV-001"])],
        )
        self.assertTrue(
            any("also reviewed" in error for error in errors), errors
        )

    def test_approval_requires_passing_review(self) -> None:
        errors, _warnings = govern(
            self.sessions,
            [proposal()],
            [review("REV-001", "PRP-001", "SES-b", result="fail")],
            [approval("APR-001", "PRP-001", "SES-c", ["REV-001"])],
        )
        self.assertTrue(
            any("no passing review" in error for error in errors), errors
        )

    def test_approved_status_requires_approval_record(self) -> None:
        errors, _warnings = govern(
            self.sessions,
            [proposal(status="approved")],
            [review("REV-001", "PRP-001", "SES-b")],
            [],
        )
        self.assertTrue(
            any("no approved approval record" in error for error in errors), errors
        )

    def test_unknown_session_is_rejected(self) -> None:
        errors, _warnings = govern(
            self.sessions,
            [proposal()],
            [review("REV-001", "PRP-001", "SES-zzz")],
            [],
        )
        self.assertTrue(any("unknown session" in error for error in errors), errors)


class SessionLedgerTest(unittest.TestCase):
    def test_bootstrap_is_capped_at_one(self) -> None:
        sessions = [
            session("SES-a", "arena/a-x", ["bootstrap"]),
            session("SES-b", "arena/b-x", ["bootstrap"]),
        ]
        errors, _warnings = govern(sessions, [], [], [])
        self.assertTrue(any("bootstrap" in error for error in errors), errors)

    def test_branch_hosts_one_active_session(self) -> None:
        sessions = [
            session("SES-a", "arena/same-x", ["proposer"]),
            session("SES-b", "arena/same-x", ["verifier"]),
        ]
        errors, _warnings = govern(sessions, [], [], [])
        self.assertTrue(any("two active sessions" in error for error in errors), errors)

    def test_closed_sessions_do_not_conflict(self) -> None:
        sessions = [
            session("SES-a", "arena/same-x", ["proposer"], status="closed"),
            session("SES-b", "arena/same-x", ["verifier"]),
        ]
        errors, _warnings = govern(sessions, [], [], [])
        self.assertEqual(errors, [])

    def test_branch_must_not_change_across_revisions(self) -> None:
        first = session("SES-a", "arena/a-x", ["proposer"])
        second = dict(first)
        second["branch"] = "arena/b-x"
        second["revision"] = 2
        second["supersedes"] = line_hash(first)
        errors, _warnings = govern([second], [], [], [], raw_sessions=[first, second])
        self.assertTrue(any("branch changed" in error for error in errors), errors)


class ClaimPromotionTest(unittest.TestCase):
    def _run(self, claim, verifications, proposals, approvals, sessions):
        errors: list = []
        warnings: list = []
        baseline = {"legacy_line_sha256": {}}
        vr.validate_claim_promotion(
            [claim],
            verifications,
            proposals,
            approvals,
            sessions,
            baseline,
            errors,
            warnings,
        )
        return errors

    def test_new_supported_claim_needs_backing(self) -> None:
        claim = {
            "claim_id": "CLM-900",
            "statement": "s",
            "status": "supported",
            "session_id": "SES-a",
        }
        errors = self._run(claim, [], [], [], [session("SES-a", "arena/a-x", ["proposer"])])
        self.assertTrue(any("no approved proposal" in error for error in errors), errors)

    def test_independent_verification_allows_promotion(self) -> None:
        claim = {
            "claim_id": "CLM-900",
            "statement": "s",
            "status": "supported",
            "session_id": "SES-a",
        }
        verification = {
            "verification_id": "VER-900",
            "target_id": "CLM-900",
            "session_id": "SES-b",
            "result": "pass",
        }
        errors = self._run(
            claim,
            [verification],
            [],
            [],
            [
                session("SES-a", "arena/a-x", ["proposer"]),
                session("SES-b", "arena/b-x", ["verifier"]),
            ],
        )
        self.assertEqual(errors, [])

    def test_self_verification_does_not_count(self) -> None:
        claim = {
            "claim_id": "CLM-900",
            "statement": "s",
            "status": "supported",
            "session_id": "SES-a",
        }
        verification = {
            "verification_id": "VER-900",
            "target_id": "CLM-900",
            "session_id": "SES-a",
            "result": "pass",
        }
        errors = self._run(
            claim, [verification], [], [], [session("SES-a", "arena/a-x", ["proposer"])]
        )
        self.assertTrue(any("no approved proposal" in error for error in errors), errors)


class RepositoryStateTest(unittest.TestCase):
    def test_repository_passes_all_checks(self) -> None:
        report = vr.run_all_checks(str(ROOT))
        self.assertEqual(report["errors"], [], msg="\n".join(report["errors"]))

    def test_bootstrap_proposal_cannot_be_self_closed(self) -> None:
        """Assert the invariant, not the current number of sessions.

        A later verifier or approver session legitimately increases the session
        count; this test must keep passing while PRP-001 remains unapproved.
        """
        proposals = {
            record["proposal_id"]: record
            for record in vr.load_jsonl(str(ROOT / "state" / "proposals.jsonl"))
        }
        self.assertIn("PRP-001", proposals)
        self.assertEqual(proposals["PRP-001"]["session_id"], "SES-c4426c6b")

        approvals = vr.load_jsonl(str(ROOT / "state" / "approvals.jsonl"))
        self.assertFalse(
            any(a.get("proposal_id") == "PRP-001" for a in approvals),
            "PRP-001 must not be approved by the session that proposed it",
        )

        sessions = vr.load_jsonl(str(ROOT / "state" / "sessions.jsonl"))
        bootstrap = [s for s in sessions if "bootstrap" in s.get("roles", [])]
        bootstrap_ids = {s["session_id"] for s in bootstrap}
        self.assertEqual(bootstrap_ids, {"SES-c4426c6b"})


if __name__ == "__main__":
    unittest.main()
