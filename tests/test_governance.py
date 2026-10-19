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

import json
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


def approval(
    approval_id,
    proposal_id,
    session_id,
    review_ids,
    decision="approved",
    review_line_sha256=None,
):
    """An approval record.

    PRP-002 rev3 (C3/A2): ``review_line_sha256`` is mandatory for an 'approved'
    decision, so a fixture that expects a clean result must pass the binding via
    ``bind(*reviews)``.  Leaving it out is itself a test case — see
    ``ApprovalBindingTest``.
    """
    record = {
        "approval_id": approval_id,
        "proposal_id": proposal_id,
        "session_id": session_id,
        "review_ids": review_ids,
        "decision": decision,
        "created_at": "2026-10-19T00:00:00+00:00",
    }
    if review_line_sha256 is not None:
        record["review_line_sha256"] = review_line_sha256
    return record


def bind(*reviews):
    """The ``review_line_sha256`` map an approver must record for these reviews."""
    return {record["review_id"]: line_hash(record) for record in reviews}


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
        cited = review("REV-001", "PRP-001", "SES-b")
        errors, _warnings = govern(
            self.sessions,
            [proposal()],
            [cited],
            [approval("APR-001", "PRP-001", "SES-c", ["REV-001"], review_line_sha256=bind(cited))],
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


class GovernanceStageTest(unittest.TestCase):
    """A governance change may be proposed on a branch but needs approval to land."""

    def setUp(self) -> None:
        self.spec_proposer = {"may_write_governance_with_proposal": True}
        self.spec_verifier = {"may_write_governance_with_proposal": False}
        # PRP-002 G1: bootstrap has both flags in real policy; without-proposal only for propose
        self.spec_bootstrap = {"may_use_governance_paths_without_proposal": True, "may_write_governance_with_proposal": True}
        self.proposals = {
            "PRP-001": {"proposal_id": "PRP-001", "session_id": "SES-a",
                        "status": "pending_review"},
            "PRP-002": {"proposal_id": "PRP-002", "session_id": "SES-a",
                        "status": "approved"},
        }
        self.approved = {"PRP-002"}

    def decide(self, spec, role, proposal_id, session_id, stage):
        return guard.check_governance_path(
            role, spec, "scripts/x.py", proposal_id, self.proposals,
            self.approved, session_id, stage,
        )

    def test_proposer_may_change_with_pending_proposal(self) -> None:
        self.assertEqual(
            self.decide(self.spec_proposer, "proposer", "PRP-001", "SES-a", "propose"), []
        )

    def test_proposer_cannot_land_pending_proposal(self) -> None:
        errors = self.decide(self.spec_proposer, "proposer", "PRP-001", "SES-a", "land")
        self.assertTrue(any("not approved" in e for e in errors), errors)

    def test_proposer_cannot_land_own_approved_proposal(self) -> None:
        errors = self.decide(self.spec_proposer, "proposer", "PRP-002", "SES-a", "land")
        self.assertTrue(any("your own proposal" in e for e in errors), errors)

    def test_other_session_can_land_approved_proposal(self) -> None:
        self.assertEqual(
            self.decide(self.spec_proposer, "proposer", "PRP-002", "SES-b", "land"), []
        )

    def test_verifier_cannot_change_governance_paths(self) -> None:
        errors = self.decide(self.spec_verifier, "verifier", "PRP-002", "SES-b", "propose")
        self.assertTrue(any("may not modify" in e for e in errors), errors)

    def test_missing_trailer_is_rejected(self) -> None:
        errors = self.decide(self.spec_proposer, "proposer", None, "SES-a", "propose")
        self.assertTrue(any("Governance-Proposal" in e for e in errors), errors)

    def test_bootstrap_is_exempt(self) -> None:
        # PRP-002 G1: bootstrap may propose without proposal, but land requires approval
        self.assertEqual(
            self.decide(self.spec_bootstrap, "bootstrap", None, "SES-a", "propose"), []
        )

    def test_bootstrap_may_propose_without_proposal(self) -> None:
        # Propose stage: bootstrap exemption applies
        self.assertEqual(
            self.decide(self.spec_bootstrap, "bootstrap", None, "SES-a", "propose"), []
        )

    def test_bootstrap_land_requires_approval(self) -> None:
        # Land stage: bootstrap must present approved proposal, even with exemption
        errors = self.decide(self.spec_bootstrap, "bootstrap", None, "SES-a", "land")
        self.assertTrue(any("Governance-Proposal" in e or "not approved" in e for e in errors), errors)
        # With approved proposal from different session, land should pass
        self.assertEqual(
            self.decide(self.spec_bootstrap, "bootstrap", "PRP-002", "SES-b", "land"), []
        )


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
        """Assert the invariant, not the absence of approval.

        PRP-001 was proposed by SES-c4426c6b and approved by SES-955f8586 (a third session).
        The invariant is that the proposer must not self-approve, not that no approval exists.
        This test must keep passing after APR-001 is recorded.
        """
        proposals = {
            record["proposal_id"]: record
            for record in vr.load_jsonl(str(ROOT / "state" / "proposals.jsonl"))
        }
        self.assertIn("PRP-001", proposals)
        self.assertEqual(proposals["PRP-001"]["session_id"], "SES-c4426c6b")

        approvals = vr.load_jsonl(str(ROOT / "state" / "approvals.jsonl"))
        # No self-approval by proposer
        self.assertFalse(
            any(a.get("proposal_id") == "PRP-001" and a.get("session_id") == "SES-c4426c6b" for a in approvals),
            "PRP-001 must not be approved by the session that proposed it (SES-c4426c6b)",
        )
        # But a third session may approve (APR-001 by SES-955f8586)
        self.assertTrue(
            any(a.get("proposal_id") == "PRP-001" for a in approvals),
            "PRP-001 should have an approval by a third session (SES-955f8586)",
        )

        sessions = vr.load_jsonl(str(ROOT / "state" / "sessions.jsonl"))
        bootstrap = [s for s in sessions if "bootstrap" in s.get("roles", [])]
        bootstrap_ids = {s["session_id"] for s in bootstrap}
        self.assertEqual(bootstrap_ids, {"SES-c4426c6b"})

    def test_reviewer_cannot_approve(self) -> None:
        """A reviewer who reviewed PRP-001 cannot also approve it."""
        errors, _ = govern([session("SES-a", "arena/a", ["proposer"]), session("SES-b", "arena/b", ["verifier"])],
                           [proposal()], [review("REV-001", "PRP-001", "SES-b")],
                           [approval("APR-001", "PRP-001", "SES-b", ["REV-001"])])
        self.assertTrue(any("also reviewed" in e for e in errors), errors)

    def test_third_session_can_approve(self) -> None:
        """A third session (neither proposer nor reviewer) can approve."""
        sessions = [session("SES-a", "arena/a", ["proposer"]), session("SES-b", "arena/b", ["verifier"]), session("SES-c", "arena/c", ["approver"])]
        cited = review("REV-001", "PRP-001", "SES-b")
        errors, _ = govern(sessions,
            [proposal()], [cited],
            [approval("APR-001", "PRP-001", "SES-c", ["REV-001"], review_line_sha256=bind(cited))])
        self.assertEqual(errors, [])

    def test_append_only_hash_chain_is_enforced(self) -> None:
        """PRP-002 rev3 (C2/A1): a *real* tamper test.

        REV-003 §3.4 rejected the previous version of this test: it never
        modified anything, it only asserted that a clean ``state/reviews.jsonl``
        resolves without errors, so it also passed on a tampered tree.  This
        version rewrites a line and asserts the whole-file anchor rejects it.
        The end-to-end attacks (in-place rewrite, deletion, and a committed
        rewrite of a freshly appended line) live in
        ``tests/test_append_only_tamper.py``.
        """
        import shutil
        import tempfile

        from researchos_common import (
            anchored_ledgers,
            anchor_errors,
            append_jsonl,
            build_anchor_updates,
            now_utc,
        )

        tmp = Path(tempfile.mkdtemp(prefix="researchos-chain-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        (tmp / "state").mkdir(parents=True)
        for relative_path in anchored_ledgers():
            (tmp / relative_path).write_text("", encoding="utf-8")

        append_jsonl(
            tmp / "state" / "reviews.jsonl",
            {
                "review_id": "REV-001",
                "proposal_id": "PRP-001",
                "session_id": "SES-b",
                "result": "pass",
                "summary": "original",
                "created_at": now_utc(),
            },
            anchor=False,
        )
        for entry in build_anchor_updates(tmp, session_id="SES-test"):
            append_jsonl(tmp / "state" / "anchors.jsonl", entry, anchor=False)
        self.assertEqual(anchor_errors(tmp), [])

        # Tamper for real: rewrite the newest (and only) review line.
        target = tmp / "state" / "reviews.jsonl"
        record = json.loads(target.read_text(encoding="utf-8").strip())
        record["summary"] = "TAMPERED"
        target.write_text(
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n",
            encoding="utf-8",
        )
        errors = anchor_errors(tmp)
        self.assertTrue(
            any("was modified" in error for error in errors),
            f"a rewritten line must break the whole-file anchor: {errors}",
        )

        # Re-anchoring the tampered content must not clean it either.
        for entry in build_anchor_updates(tmp, session_id="SES-test"):
            append_jsonl(tmp / "state" / "anchors.jsonl", entry, anchor=False)
        errors = anchor_errors(tmp)
        self.assertTrue(
            any("was modified" in error for error in errors),
            f"re-anchoring must not hide the rewrite: {errors}",
        )

        # The repository's own committed ledgers stay consistent.
        self.assertEqual(guard.check_append_only(), [])

    def test_pass_review_with_failing_check_is_rejected(self) -> None:
        """PRP-002 G3: pass review containing fail check must be rejected."""
        sessions = [session("SES-a", "arena/a", ["proposer"]), session("SES-b", "arena/b", ["verifier"]), session("SES-c", "arena/c", ["approver"])]
        prop = proposal()
        rev = review("REV-001", "PRP-001", "SES-b", result="pass")
        # Inject failing check
        rev["checks"] = [{"name": "regression_tests", "result": "fail", "detail": "boom"}]
        approv = approval("APR-001", "PRP-001", "SES-c", ["REV-001"])
        errs, _ = govern(sessions, [prop], [rev], [approv])
        self.assertTrue(any("failing checks" in e or "missing required" in e or "pass" in e for e in errs), errs)

    def test_missing_required_check_is_rejected(self) -> None:
        """PRP-002 G3: missing required_checks must be rejected."""
        sessions = [session("SES-a", "arena/a", ["proposer"]), session("SES-b", "arena/b", ["verifier"]), session("SES-c", "arena/c", ["approver"])]
        prop = proposal()
        rev = review("REV-001", "PRP-001", "SES-b", result="pass")
        rev["checks"] = [{"name": "policy", "result": "pass"}]  # missing regression_tests
        approv = approval("APR-001", "PRP-001", "SES-c", ["REV-001"])
        # Need queue with required_checks
        queue = [{"queue_id": "RQ-001", "proposal_id": "PRP-001", "status": "completed", "created_by_session": "SES-a", "review_id": "REV-001", "required_checks": ["policy", "regression_tests"]}]
        errs, _ = govern(sessions, [prop], [rev], [approv], queue)
        # validate_governance checks required_checks, govern is wrapper for validate_governance?
        # Use direct validator
        import validate_researchos as vr2
        e2, w2 = [], []
        vr2.validate_governance(sessions, [prop], [rev], [approv], queue, sessions, e2, w2)
        self.assertTrue(any("missing required" in e for e in e2), e2)

    def test_multiple_reviews_from_one_session_remain_distinct(self) -> None:
        """PRP-002 G4: same verifier writing two reviews must not collide."""
        from researchos_common import resolve_effective
        rev1 = review("REV-001", "PRP-001", "SES-b")
        rev2 = review("REV-002", "PRP-001", "SES-b")
        # Untyped would group by session_id and error, typed must not
        _, typed_errs, _ = resolve_effective([rev1, rev2], "review_id")
        self.assertEqual(typed_errs, [])


class ApprovalBindingTest(unittest.TestCase):
    """PRP-002 rev3 (C3/A2): ``review_line_sha256`` is mandatory.

    REV-003 §4 reproduced the gap: a fixture approval ``APR-910`` with no
    binding passed ``validate_researchos.py --quiet`` with exit 0, because the
    check only ran "if present".  An approver could therefore be handed a
    different review after the fact.
    """

    def setUp(self) -> None:
        self.sessions = [
            session("SES-a", "arena/a", ["proposer"]),
            session("SES-b", "arena/b", ["verifier"]),
            session("SES-c", "arena/c", ["approver"]),
        ]
        self.proposal = proposal()
        self.review = review("REV-001", "PRP-001", "SES-b")
        self.second = review("REV-002", "PRP-001", "SES-b")

    def test_approval_without_binding_is_rejected(self) -> None:
        errors, _warnings = govern(
            self.sessions,
            [self.proposal],
            [self.review],
            [approval("APR-002", "PRP-001", "SES-c", ["REV-001"])],
        )
        self.assertTrue(
            any("has no review_line_sha256" in error for error in errors), errors
        )

    def test_incomplete_binding_is_rejected(self) -> None:
        errors, _warnings = govern(
            self.sessions,
            [self.proposal],
            [self.review, self.second],
            [
                approval(
                    "APR-002",
                    "PRP-001",
                    "SES-c",
                    ["REV-001", "REV-002"],
                    review_line_sha256=bind(self.review),
                )
            ],
        )
        self.assertTrue(
            any("no entry for the cited review 'REV-002'" in error for error in errors),
            errors,
        )

    def test_wrong_hash_is_rejected(self) -> None:
        errors, _warnings = govern(
            self.sessions,
            [self.proposal],
            [self.review],
            [
                approval(
                    "APR-002",
                    "PRP-001",
                    "SES-c",
                    ["REV-001"],
                    review_line_sha256={"REV-001": "0" * 64},
                )
            ],
        )
        self.assertTrue(
            any("review_line_sha256 mismatch" in error for error in errors), errors
        )

    def test_single_string_binding_for_two_reviews_is_rejected(self) -> None:
        errors, _warnings = govern(
            self.sessions,
            [self.proposal],
            [self.review, self.second],
            [
                approval(
                    "APR-002",
                    "PRP-001",
                    "SES-c",
                    ["REV-001", "REV-002"],
                )
                | {"review_sha256": line_hash(self.review)}
            ],
        )
        self.assertTrue(
            any("binds one review_sha256 string" in error for error in errors), errors
        )

    def test_correct_binding_passes(self) -> None:
        errors, _warnings = govern(
            self.sessions,
            [self.proposal],
            [self.review, self.second],
            [
                approval(
                    "APR-002",
                    "PRP-001",
                    "SES-c",
                    ["REV-001", "REV-002"],
                    review_line_sha256=bind(self.review, self.second),
                )
            ],
        )
        self.assertEqual(errors, [])

    def test_rejected_decision_does_not_need_a_binding(self) -> None:
        errors, _warnings = govern(
            self.sessions,
            [self.proposal],
            [self.review],
            [approval("APR-002", "PRP-001", "SES-c", ["REV-001"], decision="rejected")],
        )
        self.assertFalse(
            any("review_line_sha256" in error for error in errors), errors
        )

    def test_grandfathered_approval_only_warns(self) -> None:
        """APR-001 predates the rule; the exemption is data in policy/roles.json."""
        grandfathered = vr.grandfathered_approvals()
        self.assertIn("APR-001", grandfathered)
        errors, warnings = govern(
            self.sessions,
            [self.proposal],
            [self.review],
            [approval("APR-001", "PRP-001", "SES-c", ["REV-001"])],
        )
        self.assertFalse(
            any("review_line_sha256" in error for error in errors), errors
        )
        self.assertTrue(
            any("grandfathered" in warning for warning in warnings), warnings
        )

    def test_schema_requires_the_binding(self) -> None:
        schema = json.loads((ROOT / "schemas" / "approval.json").read_text(encoding="utf-8"))
        self.assertIn("review_line_sha256", schema["required"])
        self.assertEqual(
            schema["properties"]["review_line_sha256"]["additionalProperties"]["pattern"],
            "^[0-9a-f]{64}$",
        )

    def test_repository_approvals_are_bound_to_the_reviews_they_cite(self) -> None:
        approvals, approval_errors, _ = resolve_effective(
            vr.load_jsonl(str(ROOT / "state" / "approvals.jsonl")), "approval_id"
        )
        self.assertEqual(approval_errors, [])
        reviews, review_errors, _ = resolve_effective(
            vr.load_jsonl(str(ROOT / "state" / "reviews.jsonl")), "review_id"
        )
        self.assertEqual(review_errors, [])
        reviews_by_id = {record["review_id"]: record for record in reviews}
        bound = 0
        for record in approvals:
            if record.get("decision") != "approved":
                continue
            binding = record.get("review_line_sha256") or {}
            for review_id in record.get("review_ids", []):
                if review_id not in reviews_by_id:
                    continue
                self.assertIn(
                    review_id,
                    binding,
                    f"{record['approval_id']} cites {review_id} without binding it",
                )
                self.assertEqual(
                    binding[review_id],
                    line_hash(reviews_by_id[review_id]),
                    f"{record['approval_id']} binds a stale hash for {review_id}",
                )
                bound += 1
        self.assertGreater(bound, 0, "no approval in the repository is bound")


if __name__ == "__main__":
    unittest.main()
