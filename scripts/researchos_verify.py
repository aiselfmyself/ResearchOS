#!/usr/bin/env python3
"""Standard independent verification suite for ResearchOS.

Run this in a **verifier session** (a different Arena chat from the proposer).
It re-executes everything that can be re-executed, compares artifacts against
their committed snapshots, checks role separation and append-only history, and
emits a ``REV-*`` record.  It never approves anything.

Examples:
    python3 scripts/researchos_verify.py --proposal PRP-001 --session SES-xxxx
    python3 scripts/researchos_verify.py --proposal PRP-001 --session SES-xxxx --write
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from researchos_common import (  # noqa: E402
    ROOT,
    STATE_FILES,
    append_jsonl,
    load_effective,
    next_id,
    now_utc,
    read_jsonl,
    resolve_effective,
)

REVIEWS_PATH = ROOT / "state" / "reviews.jsonl"


def _run(command: List[str], timeout: int = 300) -> tuple:
    try:
        result = subprocess.run(
            command,
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        detail = (result.stdout.strip() or result.stderr.strip() or "").replace("\n", " ")
        return result.returncode == 0, detail[:400]
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s"
    except OSError as exc:
        return False, str(exc)


def _sessions() -> Dict[str, dict]:
    # PRP-002 G4: use COLLECTION_ID_KEYS via load_effective
    effective, errors, _warnings = load_effective("sessions")
    if errors:
        raise SystemExit("state/sessions.jsonl is inconsistent:\n  " + "\n  ".join(errors))
    return {record["session_id"]: record for record in effective}


def _proposal(proposal_id: str) -> dict:
    proposals, errors, _warnings = load_effective("proposals")
    if errors:
        raise SystemExit("state/proposals.jsonl is inconsistent:\n  " + "\n  ".join(errors))
    for record in proposals:
        if record.get("proposal_id") == proposal_id:
            return record
    raise SystemExit(f"unknown proposal '{proposal_id}'")


def check_readout_snapshot() -> tuple:
    snapshot_path = ROOT / "gitswarm" / "artifacts" / "readout_snapshot.json"
    if not snapshot_path.exists():
        return False, "readout snapshot missing"
    with snapshot_path.open("r", encoding="utf-8") as handle:
        snapshot = json.load(handle)
    command = [
        sys.executable,
        "gitswarm/readout.py",
        "--quiet",
        "--format",
        "json",
    ]
    result = subprocess.run(
        command, cwd=str(ROOT), text=True, capture_output=True, timeout=120
    )
    if result.returncode != 0:
        return False, f"readout.py failed: {result.stderr.strip()[:300]}"
    current = json.loads(result.stdout)
    keys = (
        "total_worker_commits",
        "candidate_commits",
        "vote_tallies",
        "winning_candidate_sha",
        "compounding_metrics",
    )
    mismatches = [key for key in keys if current.get(key) != snapshot.get(key)]
    if mismatches:
        return False, "readout drifted: " + ", ".join(mismatches)
    return True, "readout matches the committed snapshot"



# ---------------------------------------------------------------------------
# Adversarial probes (PRP-002 rev3)
# ---------------------------------------------------------------------------
#
# REV-003 §2 made the point that cannot be repeated often enough: "13/13 pass"
# was measured on a *clean* tree, so the append-only check proved nothing.  A
# suite that only runs on untampered state cannot falsify its own DoD.  The two
# probes below therefore attack a throwaway copy of this repository and require
# the harness to reject the attack — and they also run the positive control, so
# "everything is red" cannot pass as a green probe.


def _throwaway_copy() -> Tuple[Path, Path]:
    """Copy this repository (working tree + ``.git``) into a temp directory."""
    workspace = Path(tempfile.mkdtemp(prefix="researchos-probe-"))
    repo = workspace / "repo"
    shutil.copytree(
        ROOT, repo, symlinks=True, ignore=shutil.ignore_patterns("__pycache__")
    )
    return workspace, repo


def _probe_run(repo: Path, *command: str, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(command),
        cwd=str(repo),
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def _tamper_line(repo: Path, relative_path: str, index: int, field: str, value) -> None:
    path = repo / relative_path
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    record = json.loads(lines[index])
    record[field] = value
    lines[index] = json.dumps(
        record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _delete_line(repo: Path, relative_path: str, index: int) -> None:
    path = repo / relative_path
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    del lines[index]
    path.write_text(
        ("\n".join(lines) + "\n") if lines else "", encoding="utf-8"
    )


def check_append_only_adversarial() -> tuple:
    """Attack the append-only guard in a throwaway copy; it must reject all three.

    These are the attacks REV-003 §3.1-§3.3 ran by hand and which the harness
    accepted at the time.
    """
    workspace, repo = _throwaway_copy()
    observations: List[dict] = []
    try:
        reviews = "state/reviews.jsonl"

        # Positive control: an untampered copy must be green, otherwise the
        # attack assertions below would be satisfied by a guard that always fails.
        control = _probe_run(repo, sys.executable, "scripts/researchos_guard.py", "check-append-only")
        observations.append(
            {"attack": "control_pristine_tree", "rejected": control.returncode == 0,
             "expected": "exit 0", "exit": control.returncode}
        )

        # Attack 1: rewrite a committed line in place.
        attack1 = _throwaway_copy()
        _tamper_line(attack1[1], reviews, 0, "summary", "TAMPERED by probe")
        result1 = _probe_run(attack1[1], sys.executable, "scripts/researchos_guard.py", "check-append-only")
        observations.append(
            {"attack": "rewrite_committed_line_in_place", "rejected": result1.returncode == 1,
             "expected": "exit 1", "exit": result1.returncode,
             "detail": (result1.stdout or result1.stderr).strip().splitlines()[0:1]}
        )
        shutil.rmtree(attack1[0], ignore_errors=True)

        # Attack 2: delete a committed line.
        attack2 = _throwaway_copy()
        _delete_line(attack2[1], reviews, 0)
        result2 = _probe_run(attack2[1], sys.executable, "scripts/researchos_guard.py", "check-all", "--json")
        rejected2 = result2.returncode == 1
        if result2.returncode == 0:
            try:
                rejected2 = json.loads(result2.stdout).get("ok") is False
            except (ValueError, AttributeError):
                rejected2 = False
        observations.append(
            {"attack": "delete_committed_line", "rejected": rejected2,
             "expected": "check-all ok=false", "exit": result2.returncode}
        )
        shutil.rmtree(attack2[0], ignore_errors=True)

        # Attack 3: append a line, commit it, then rewrite the committed line —
        # the A1 hole the baseline prefix can never see.
        attack3 = _throwaway_copy()
        repo3 = attack3[1]
        appended = _probe_run(
            repo3, sys.executable, "-c",
            "import sys; sys.path.insert(0, 'scripts');"
            "from pathlib import Path;"
            "from researchos_common import append_jsonl, now_utc;"
            "append_jsonl(Path('state/reviews.jsonl'), {"
            "'review_id': 'REV-9001', 'proposal_id': 'PRP-002',"
            "'session_id': 'SES-f99f5b7f',"
            "'checks': [{'name': 'policy', 'result': 'pass'}],"
            "'result': 'pass', 'summary': 'original',"
            "'environment': 'probe', 'created_at': now_utc()})",
        )
        _probe_run(repo3, "git", "add", "-A")
        _probe_run(
            repo3, "git", "-c", "user.name=probe", "-c", "user.email=probe@example.invalid",
            "commit", "-q", "-m",
            "[Verifier] review: append REV-9001\n\nSession-Id: SES-f99f5b7f\n"
            "Session-Role: verifier\nPolicy-Version: 1",
        )
        clean3 = _probe_run(repo3, sys.executable, "scripts/researchos_guard.py", "check-append-only")
        lines = [line for line in (repo3 / reviews).read_text(encoding="utf-8").splitlines() if line.strip()]
        _tamper_line(repo3, reviews, len(lines) - 1, "summary", "TAMPERED after commit")
        result3a = _probe_run(repo3, sys.executable, "scripts/researchos_guard.py", "check-append-only")
        _probe_run(repo3, sys.executable, "scripts/researchos_anchor.py", "update")
        _probe_run(repo3, "git", "add", "-A")
        _probe_run(
            repo3, "git", "-c", "user.name=probe", "-c", "user.email=probe@example.invalid",
            "commit", "-q", "-m",
            "[Verifier] review: rewrite REV-9001\n\nSession-Id: SES-f99f5b7f\n"
            "Session-Role: verifier\nPolicy-Version: 1",
        )
        result3b = _probe_run(repo3, sys.executable, "scripts/researchos_guard.py", "check-append-only")
        observations.append(
            {"attack": "rewrite_freshly_appended_committed_line",
             "rejected": appended.returncode == 0 and clean3.returncode == 0
             and result3a.returncode == 1 and result3b.returncode == 1,
             "expected": "append+commit exit 0, then rewrite exit 1 (uncommitted and committed)",
             "exit": {"append": appended.returncode, "clean_after_append": clean3.returncode,
                      "rewrite_uncommitted": result3a.returncode,
                      "rewrite_committed": result3b.returncode}}
        )
        shutil.rmtree(attack3[0], ignore_errors=True)
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    ok = all(bool(obs.get("rejected")) for obs in observations) and len(observations) == 4
    return ok, json.dumps(observations, ensure_ascii=False)[:1200]


def check_approval_binding() -> tuple:
    """An 'approved' decision without review_line_sha256 must fail the validator.

    REV-003 §4 appended a fixture ``APR-910`` with no binding and got exit 0.
    The probe repeats that, plus the positive control (the same approval *with*
    a correct binding must be accepted), so a validator that always fails cannot
    pass the probe.
    """
    workspace, repo = _throwaway_copy()
    observations: List[dict] = []
    try:
        fixture = (
            "import sys; sys.path.insert(0, 'scripts');"
            "from pathlib import Path;"
            "from researchos_common import append_jsonl, line_hash, now_utc;"
            "bound = sys.argv[1] == 'bound';"
            "append_jsonl(Path('state/sessions.jsonl'), {'session_id': 'SES-probe-p',"
            " 'branch': 'arena/probe-p-researchos', 'roles': ['proposer'], 'kind': 'agent',"
            " 'started_at': now_utc(), 'status': 'active', 'policy_version': 1});"
            "append_jsonl(Path('state/sessions.jsonl'), {'session_id': 'SES-probe-v',"
            " 'branch': 'arena/probe-v-researchos', 'roles': ['verifier'], 'kind': 'agent',"
            " 'started_at': now_utc(), 'status': 'active', 'policy_version': 1});"
            "append_jsonl(Path('state/sessions.jsonl'), {'session_id': 'SES-probe-a',"
            " 'branch': 'arena/probe-a-researchos', 'roles': ['approver'], 'kind': 'agent',"
            " 'started_at': now_utc(), 'status': 'active', 'policy_version': 1});"
            "append_jsonl(Path('state/proposals.jsonl'), {'proposal_id': 'PRP-901',"
            " 'title': 'probe', 'kind': 'research', 'summary': 'probe', 'changes': [],"
            " 'session_id': 'SES-probe-p', 'status': 'pending_review', 'created_at': now_utc()});"
            "rev = {'review_id': 'REV-901', 'proposal_id': 'PRP-901', 'session_id': 'SES-probe-v',"
            " 'checks': [{'name': 'policy', 'result': 'pass'}], 'result': 'pass',"
            " 'created_at': now_utc()};"
            "append_jsonl(Path('state/reviews.jsonl'), rev);"
            "apr = {'approval_id': 'APR-901', 'proposal_id': 'PRP-901',"
            " 'session_id': 'SES-probe-a', 'review_ids': ['REV-901'], 'decision': 'approved',"
            " 'created_at': now_utc()};"
            "apr['review_line_sha256'] = {'REV-901': line_hash(rev)} if bound else None;"
            "apr = {k: v for k, v in apr.items() if v is not None};"
            "append_jsonl(Path('state/approvals.jsonl'), apr)"
        )
        for variant, expected_exit in (("unbound", 1), ("bound", 0)):
            case = _throwaway_copy()
            appended = _probe_run(case[1], sys.executable, "-c", fixture, variant)
            # Refresh the anchors so the probe measures the binding rule only.
            _probe_run(case[1], sys.executable, "scripts/researchos_anchor.py", "update")
            result = _probe_run(case[1], sys.executable, "scripts/validate_researchos.py", "--quiet")
            output = (result.stdout or "") + (result.stderr or "")
            # The unbound case must fail *because of the binding*, not for some
            # unrelated reason, so the error text is asserted too.
            matched = appended.returncode == 0 and result.returncode == expected_exit
            if variant == "unbound":
                matched = matched and "review_line_sha256" in output
            observations.append(
                {"case": f"approval_{variant}", "exit": result.returncode,
                 "expected_exit": expected_exit, "matched": matched,
                 "detail": [line for line in output.splitlines() if line.strip()][0:2]}
            )
            shutil.rmtree(case[0], ignore_errors=True)
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    ok = bool(observations) and all(obs["matched"] for obs in observations)
    return ok, json.dumps(observations, ensure_ascii=False)[:900]


def build_checks(proposal_id: str, session_id: str, base: Optional[str]) -> List[dict]:
    checks: List[dict] = []

    ok, detail = _run([sys.executable, "scripts/researchos_guard.py", "check-policy"])
    checks.append({"name": "policy", "result": "pass" if ok else "fail", "detail": detail})

    ok, detail = _run([sys.executable, "scripts/validate_researchos.py", "--quiet"])
    checks.append(
        {"name": "schema_and_integrity", "result": "pass" if ok else "fail", "detail": detail}
    )

    ok, detail = _run([sys.executable, "-m", "unittest", "discover", "-s", "tests"])
    checks.append(
        {"name": "regression_tests", "result": "pass" if ok else "fail", "detail": detail}
    )

    ok, detail = _run([sys.executable, "gitswarm/benchmarks/benchmark.py", "--check"])
    checks.append(
        {
            "name": "benchmark_reproducible",
            "result": "pass" if ok else "fail",
            "detail": detail,
        }
    )

    ok, detail = check_readout_snapshot()
    checks.append(
        {"name": "readout_snapshot", "result": "pass" if ok else "fail", "detail": detail}
    )

    append_command = [sys.executable, "scripts/researchos_guard.py", "check-append-only"]
    if base:
        append_command += ["--base", base]
    ok, detail = _run(append_command)
    checks.append(
        {"name": "append_only", "result": "pass" if ok else "fail", "detail": detail}
    )

    # PRP-002 rev3: append-only is only a real invariant if a tamper is rejected.
    ok, detail = check_append_only_adversarial()
    checks.append(
        {
            "name": "append_only_adversarial",
            "result": "pass" if ok else "fail",
            "detail": detail,
        }
    )

    # PRP-002 rev3 (C3/A2): the approval/review binding is mandatory.
    ok, detail = check_approval_binding()
    checks.append(
        {
            "name": "approval_binding",
            "result": "pass" if ok else "fail",
            "detail": detail,
        }
    )

    commit_command = [sys.executable, "scripts/researchos_guard.py", "check-commits"]
    if base:
        commit_command += ["--base", base]
    ok, detail = _run(commit_command)
    checks.append(
        {"name": "role_guard", "result": "pass" if ok else "fail", "detail": detail}
    )

    # PRP-002 V10: governance probes as first-class checks (4 probes -> 4 required checks)
    # These are the executable acceptance criteria for G1-G4
    probe_path = ROOT / "verifications" / "prp001_governance_probes.py"
    governance_observations = []
    if probe_path.exists():
        ok, detail = _run([sys.executable, str(probe_path)])
        # Parse JSON output if available, else fallback to raw detail
        try:
            import json as _j
            # Re-run to capture full JSON
            result = subprocess.run(
                [sys.executable, str(probe_path)],
                cwd=str(ROOT), text=True, capture_output=True, timeout=120
            )
            observations = _j.loads(result.stdout)
            governance_observations = observations
            # Map probe names to required_checks names (V9 unified)
            name_map = {
                "bootstrap_land_requires_independent_approval": "bootstrap_land_requires_approval",
                "merge_commits_are_audited": "merge_commits_are_audited",
                "approval_rejects_failed_or_missing_required_checks": "approval_consistency",
                "multiple_reviews_from_one_session_remain_distinct": "distinct_reviews",
            }
            for obs in observations:
                req_name = name_map.get(obs["name"], obs["name"])
                checks.append({
                    "name": req_name,
                    "result": "pass" if obs.get("enforced") else "fail",
                    "detail": _j.dumps(obs, ensure_ascii=False)[:400]
                })
            # Also emit governance_review as aggregated (for backward compat with RQ-001 which requires it)
            gov_ok = all(o.get("enforced") for o in observations) if observations else ok
            checks.append({"name": "governance_review", "result": "pass" if gov_ok else "fail", "detail": "aggregated from 4 governance probes; see individual checks"})
        except Exception as exc:
            # Fallback: single governance_review check
            checks.append({"name": "governance_review", "result": "pass" if ok else "fail", "detail": f"probe runner: {detail} ({exc})"})
    else:
        # If probe file missing, governance_review is a placeholder
        checks.append({"name": "governance_review", "result": "skip", "detail": "probe file missing"})

    sessions = _sessions()
    proposal = _proposal(proposal_id)
    session = sessions.get(session_id)
    if session is None:
        checks.append(
            {
                "name": "role_separation",
                "result": "fail",
                "detail": f"unknown session '{session_id}'",
            }
        )
    else:
        problems = []
        if "verifier" not in session.get("roles", []):
            problems.append("session does not hold the verifier role")
        if session_id == proposal.get("session_id"):
            problems.append("reviewer is the proposer")
        if proposal.get("status") not in ("pending_review", "approved"):
            problems.append(f"proposal status is '{proposal.get('status')}'")
        checks.append(
            {
                "name": "role_separation",
                "result": "fail" if problems else "pass",
                "detail": "; ".join(problems) or "reviewer differs from proposer",
            }
        )

    return checks


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="ResearchOS independent verification")
    parser.add_argument("--proposal", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--base", default=None)
    parser.add_argument("--summary", default=None)
    parser.add_argument(
        "--write", action="store_true", help="append the review to state/reviews.jsonl"
    )
    args = parser.parse_args(argv)

    checks = build_checks(args.proposal, args.session, args.base)
    failures = [check for check in checks if check["result"] == "fail"]
    if failures:
        result = "fail"
    elif any(check["result"] == "skip" for check in checks):
        result = "partial"
    else:
        result = "pass"

    # PRP-002 G4: use collection-specific id_key for reviews
    existing, _errors, _warnings = resolve_effective(read_jsonl(REVIEWS_PATH), "review_id")
    review_id = next_id(existing, "review_id", "REV")
    review = {
        "review_id": review_id,
        "proposal_id": args.proposal,
        "session_id": args.session,
        "checks": checks,
        "result": result,
        "summary": args.summary
        or (
            "all checks passed"
            if result == "pass"
            else "; ".join(f"{c['name']}: {c['detail']}" for c in failures)
        ),
        "environment": f"{sys.version.split()[0]} on {sys.platform}",
        "created_at": now_utc(),
    }

    print(json.dumps({"review_id": review_id, "result": result, "checks": checks}, indent=2, ensure_ascii=False))
    if args.write:
        append_jsonl(REVIEWS_PATH, review)
        print(f"\nwrote {review_id} to state/reviews.jsonl")

    return 0 if result == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
