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
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

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
