#!/usr/bin/env python3
"""PRP-002 rev2 rework — executable acceptance probes (DoD runner).

REV-003 §5 walked the literal §14 acceptance commands and found that three of
them did not exist or did not behave as documented:

* ``verifications/prp002_design_probes.py`` was referenced but never written;
* ``researchos_guard.py check-commits --json`` exited **2** (no such argument),
  while §14 explicitly forbids exit 2;
* §14 claimed 52 regression tests where the suite had 57.

This file replaces the missing probe with something stronger: it *runs* the §14
commands and compares each exit code with the documented expectation, and it
adds a **mutation control** for the tamper tests — the append-only suite is run
once against the real guard and once against a deliberately neutered guard, and
the probe fails unless the neutered run turns red.  A test that cannot fail when
the guard is broken proves nothing, which is exactly what REV-003 §3.4 found.

Usage:
    python3 verifications/prp002_rev2_acceptance_probes.py           # human summary
    python3 verifications/prp002_rev2_acceptance_probes.py --json    # machine readable

Exit code: 0 when every probe is ok, 1 otherwise.  Nothing here writes to the
repository; every attack runs in a throwaway copy.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

TIMEOUT = 900


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def sh(*command: str, cwd: Path = ROOT, timeout: int = TIMEOUT) -> Tuple[int, str]:
    try:
        result = subprocess.run(
            list(command), cwd=str(cwd), text=True, capture_output=True, timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 124, f"{type(exc).__name__}: {exc}"
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode, output.strip()


def py(*args: str, cwd: Path = ROOT) -> Tuple[int, str]:
    return sh(sys.executable, *args, cwd=cwd)


def throwaway_copy() -> Tuple[Path, Path]:
    workspace = Path(tempfile.mkdtemp(prefix="prp002-rev3-probe-"))
    repo = workspace / "repo"
    shutil.copytree(
        ROOT, repo, symlinks=True, ignore=shutil.ignore_patterns("__pycache__")
    )
    return workspace, repo


def count_tests(output: str) -> Optional[int]:
    match = re.search(r"^Ran (\d+) tests?", output, re.MULTILINE)
    return int(match.group(1)) if match else None


def read_json(relative_path: str) -> Any:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# probes
# ---------------------------------------------------------------------------


def probe_r1_file_wide_anchor() -> List[Dict[str, Any]]:
    """R1 — the append-only anchor covers the *whole file*, tip included."""
    results: List[Dict[str, Any]] = []

    code, output = py("scripts/researchos_anchor.py", "verify")
    payload = {}
    try:
        payload = json.loads(output)
    except ValueError:
        pass
    results.append(
        {
            "id": "R1.1",
            "name": "every ledger is pinned at its tip",
            "command": "python3 scripts/researchos_anchor.py verify",
            "exit": code,
            "ok": code == 0 and payload.get("ok") is True,
            "detail": payload.get("errors") or output.splitlines()[-1:],
        }
    )

    # The anchor must pin the whole file, not just revisions of one id: the head
    # of a ledger changes when any line changes, including the newest one.
    from researchos_common import (  # noqa: PLC0415
        anchored_ledgers,
        ledger_lines,
        prefix_heads,
        rolling_head,
    )

    observations = []
    for relative_path in anchored_ledgers():
        path = ROOT / relative_path
        lines = ledger_lines(path.read_text(encoding="utf-8")) if path.exists() else []
        heads = prefix_heads(lines)
        observations.append(
            {
                "file": relative_path,
                "lines": len(lines),
                "head": rolling_head(lines),
                "every_prefix_pinned": all(
                    heads[index] != heads[index + 1] for index in range(len(heads) - 1)
                )
                if len(heads) > 1
                else True,
            }
        )
    results.append(
        {
            "id": "R1.2",
            "name": "rolling head is per-line (no two prefixes share a head)",
            "command": "researchos_common.rolling_head / prefix_heads",
            "exit": 0,
            "ok": all(obs["every_prefix_pinned"] for obs in observations),
            "detail": observations,
        }
    )

    # Adversarial: the three REV-003 §3 attacks must be rejected.
    import researchos_verify as rv  # noqa: PLC0415

    ok, detail = rv.check_append_only_adversarial()
    results.append(
        {
            "id": "R1.3",
            "name": "REV-003 §3.1-§3.3 attacks are rejected (rewrite / delete / "
            "rewrite of a freshly appended committed line)",
            "command": "researchos_verify.check_append_only_adversarial()",
            "exit": 0 if ok else 1,
            "ok": ok,
            "detail": json.loads(detail) if detail.startswith("[") else detail,
        }
    )
    return results


def probe_r2_real_tamper_tests() -> List[Dict[str, Any]]:
    """R2 — the tamper tests tamper, and they fail when the guard is weakened."""
    results: List[Dict[str, Any]] = []
    suite = "tests.test_append_only_tamper"

    code, output = py("-m", "unittest", suite)
    total = count_tests(output)
    results.append(
        {
            "id": "R2.1",
            "name": "adversarial append-only suite passes against the real guard",
            "command": f"python3 -m unittest {suite}",
            "exit": code,
            "ok": code == 0 and (total or 0) >= 12,
            "detail": {"tests": total, "tail": output.splitlines()[-3:]},
        }
    )

    source = (ROOT / "tests" / "test_append_only_tamper.py").read_text(encoding="utf-8")
    tampers = source.count("tamper_line(") + source.count("delete_line(")
    results.append(
        {
            "id": "R2.2",
            "name": "the suite really modifies ledger lines (REV-003 §3.4: the old "
            "test never tampered)",
            "command": "grep -c 'tamper_line(|delete_line(' tests/test_append_only_tamper.py",
            "exit": 0,
            "ok": tampers >= 8 and "TAMPERED" in source,
            "detail": {"tamper_call_sites": tampers},
        }
    )

    # Mutation control: neuter the three guard layers and require the suite to
    # go red.  If it still passes, the tests are vacuous.
    workspace, repo = throwaway_copy()
    try:
        common = repo / "scripts" / "researchos_common.py"
        text = common.read_text(encoding="utf-8")
        mutated = text.replace(
            'def anchor_errors(root: Path = ROOT) -> List[str]:',
            'def anchor_errors(root: Path = ROOT) -> List[str]:\n    return []',
            1,
        )
        assert mutated != text, "mutation anchor point moved"
        common.write_text(mutated, encoding="utf-8")

        guard_path = repo / "scripts" / "researchos_guard.py"
        guard_text = guard_path.read_text(encoding="utf-8")
        for signature in (
            "def check_working_tree_against_head(root: Path = ROOT) -> List[str]:",
            "def check_state_history(base_commit: str, root: Path = ROOT) -> List[str]:",
        ):
            replacement = f"{signature}\n    return []"
            assert signature in guard_text, f"mutation anchor point moved: {signature}"
            guard_text = guard_text.replace(signature, replacement, 1)
        guard_path.write_text(guard_text, encoding="utf-8")

        code, output = py("-m", "unittest", suite, cwd=repo)
        results.append(
            {
                "id": "R2.3",
                "name": "mutation control: with the anchor, HEAD and per-commit "
                "layers neutered the tamper suite must FAIL",
                "command": f"(neutered copy) python3 -m unittest {suite}",
                "exit": code,
                "ok": code != 0,
                "detail": {"tail": output.splitlines()[-4:]},
            }
        )
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    # The vacuous test flagged by REV-003 must have been replaced by one that
    # tampers for real.
    governance = (ROOT / "tests" / "test_governance.py").read_text(encoding="utf-8")
    replaced = (
        "def test_append_only_hash_chain_is_enforced" in governance
        and governance.count("TAMPERED") >= 1
        and "REV-003 §3.4" in governance
    )
    code, output = py(
        "-m",
        "unittest",
        "tests.test_governance.RepositoryStateTest."
        "test_append_only_hash_chain_is_enforced",
    )
    results.append(
        {
            "id": "R2.4",
            "name": "test_append_only_hash_chain_is_enforced was replaced by a real "
            "tamper test",
            "command": "python3 -m unittest tests.test_governance.RepositoryStateTest."
            "test_append_only_hash_chain_is_enforced",
            "exit": code,
            "ok": code == 0 and replaced,
            "detail": {"tampers_in_source": replaced},
        }
    )
    return results


def probe_r3_mandatory_review_binding() -> List[Dict[str, Any]]:
    """R3 — review_line_sha256 is mandatory for an approved decision."""
    results: List[Dict[str, Any]] = []

    schema = read_json("schemas/approval.json")
    results.append(
        {
            "id": "R3.1",
            "name": "schemas/approval.json requires review_line_sha256",
            "command": "jq .required schemas/approval.json",
            "exit": 0,
            "ok": "review_line_sha256" in schema.get("required", []),
            "detail": schema.get("required"),
        }
    )

    policy = read_json("policy/roles.json")
    binding = (policy.get("enforcement") or {}).get("approval_review_binding") or {}
    results.append(
        {
            "id": "R3.2",
            "name": "the grandfather clause is explicit data, not code",
            "command": "jq .enforcement.approval_review_binding policy/roles.json",
            "exit": 0,
            "ok": bool(binding.get("grandfathered_approvals"))
            and bool(binding.get("grandfather_reason"))
            and binding.get("required_for_decisions") == ["approved"],
            "detail": binding.get("grandfathered_approvals"),
        }
    )

    import researchos_verify as rv  # noqa: PLC0415

    ok, detail = rv.check_approval_binding()
    results.append(
        {
            "id": "R3.3",
            "name": "an unbound approval fails the validator while a bound one passes "
            "(REV-003 §4: fixture APR-910 used to exit 0)",
            "command": "researchos_verify.check_approval_binding()",
            "exit": 0 if ok else 1,
            "ok": ok,
            "detail": json.loads(detail) if detail.startswith("[") else detail,
        }
    )

    approvals = [
        json.loads(line)
        for line in (ROOT / "state" / "approvals.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    reviews = {
        json.loads(line)["review_id"]: line
        for line in (ROOT / "state" / "reviews.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    from researchos_common import line_hash, read_jsonl  # noqa: PLC0415

    review_records = {
        record["review_id"]: record
        for record in read_jsonl(ROOT / "state" / "reviews.jsonl")
    }
    bound = []
    for record in approvals:
        if record.get("decision") != "approved":
            continue
        binding_map = record.get("review_line_sha256") or {}
        for review_id in record.get("review_ids", []):
            if review_id not in review_records:
                continue
            bound.append(
                {
                    "approval_id": record.get("approval_id"),
                    "review_id": review_id,
                    "bound": binding_map.get(review_id) == line_hash(review_records[review_id]),
                }
            )
    results.append(
        {
            "id": "R3.4",
            "name": "every approval in this repository is bound to the reviews it cites",
            "command": "state/approvals.jsonl × state/reviews.jsonl",
            "exit": 0,
            "ok": bool(bound) and all(item["bound"] for item in bound),
            "detail": bound,
        }
    )
    del reviews
    return results


def probe_r4_dod_commands() -> List[Dict[str, Any]]:
    """R4 — the §14 commands exist and behave exactly as documented."""
    results: List[Dict[str, Any]] = []

    def expect(item: str, name: str, command: List[str], expected: Any) -> None:
        code, output = sh(*command)
        if isinstance(expected, (list, tuple, set)):
            ok = code in expected
        else:
            ok = code == expected
        results.append(
            {
                "id": item,
                "name": name,
                "command": " ".join(command),
                "exit": code,
                "expected_exit": sorted(expected) if isinstance(expected, (list, tuple, set)) else expected,
                "ok": ok and code != 2,
                "detail": output.splitlines()[-2:] if not ok else [],
            }
        )

    expect(
        "R4.1",
        "G1-G4 governance probes",
        [sys.executable, "verifications/prp001_governance_probes.py"],
        0,
    )
    expect(
        "R4.2",
        "check-commits --stage propose --json exists (REV-003 §5: exit 2)",
        [sys.executable, "scripts/researchos_guard.py", "check-commits", "--stage", "propose", "--json"],
        0,
    )
    expect(
        "R4.3",
        "check-commits --stage land --json exists and refuses an unapproved land",
        [sys.executable, "scripts/researchos_guard.py", "check-commits", "--stage", "land", "--json"],
        1,
    )
    expect(
        "R4.4",
        "check-all --stage land --json refuses an unapproved land",
        [sys.executable, "scripts/researchos_guard.py", "check-all", "--stage", "land", "--json"],
        1,
    )
    expect(
        "R4.5",
        "every guard sub-command accepts --json",
        [sys.executable, "scripts/researchos_guard.py", "check-append-only", "--json"],
        0,
    )
    expect(
        "R4.6",
        "check-authorship --json",
        [sys.executable, "scripts/researchos_guard.py", "check-authorship", "--json"],
        0,
    )
    expect(
        "R4.7",
        "check-policy --json",
        [sys.executable, "scripts/researchos_guard.py", "check-policy", "--json"],
        0,
    )
    expect(
        "R4.8",
        "deterministic validation",
        [sys.executable, "scripts/validate_researchos.py", "--quiet"],
        0,
    )
    suite_code, suite_output = py("-m", "unittest", "discover", "-s", "tests")
    results.append(
        {
            "id": "R4.9",
            "name": "regression suite",
            "command": f"{sys.executable} -m unittest discover -s tests",
            "exit": suite_code,
            "expected_exit": 0,
            "ok": suite_code == 0,
            "detail": suite_output.splitlines()[-3:] if suite_code else {"tests": count_tests(suite_output)},
        }
    )
    expect(
        "R4.10",
        "benchmark reproducibility",
        [sys.executable, "gitswarm/benchmarks/benchmark.py", "--check"],
        0,
    )
    expect(
        "R4.11",
        "readout snapshot",
        [sys.executable, "gitswarm/readout.py", "--quiet", "--format", "json"],
        0,
    )
    expect(
        "R4.12",
        "check-all --json is green on an untampered tree",
        [sys.executable, "scripts/researchos_guard.py", "check-all", "--json"],
        0,
    )

    # §14 must not hard-code a test count that drifts (REV-003 §5: 52 vs 57).
    total = count_tests(suite_output)
    doc = (ROOT / "reports" / "PRP-002-governance-fixes.md").read_text(encoding="utf-8")
    hard_coded = re.findall(r"全 tests PASS[^\n]*?(\d+)\s*件", doc)
    results.append(
        {
            "id": "R4.13",
            "name": "§14 no longer hard-codes a drifting test count",
            "command": "grep -n '件' reports/PRP-002-governance-fixes.md (§14)",
            "exit": 0,
            "ok": bool(total) and not hard_coded,
            "detail": {"measured_tests": total, "hard_coded_counts_found": hard_coded},
        }
    )

    # §14 must only reference probe files that exist.  Only §14 is scanned: the
    # rest of the document legitimately names artifacts that live on other
    # session tracks.
    section14 = doc.split("## 14.", 1)[-1].split("## 15.", 1)[0]
    referenced = sorted(set(re.findall(r"verifications/[A-Za-z0-9_.\-]+\.py", section14)))
    missing = [item for item in referenced if not (ROOT / item).exists()]
    results.append(
        {
            "id": "R4.14",
            "name": "every verifications/*.py referenced by the design doc exists "
            "(REV-003 §5: prp002_design_probes.py did not)",
            "command": "grep -o 'verifications/[A-Za-z0-9_.-]*\\.py' reports/PRP-002-governance-fixes.md",
            "exit": 0,
            "ok": not missing,
            "detail": {"referenced": referenced, "missing": missing},
        }
    )

    # Documents required by §14 item 7.
    governance_doc = (ROOT / "docs" / "GOVERNANCE.md").read_text(encoding="utf-8")
    required_phrases = [
        "state/anchors.jsonl",
        "rolling head",
        "review_line_sha256",
    ]
    results.append(
        {
            "id": "R4.15",
            "name": "GOVERNANCE.md documents the anchor ledger and the binding",
            "command": "grep -n 'state/anchors.jsonl' docs/GOVERNANCE.md",
            "exit": 0,
            "ok": all(phrase in governance_doc for phrase in required_phrases),
            "detail": {
                phrase: (phrase in governance_doc) for phrase in required_phrases
            },
        }
    )
    return results


PROBES = [
    ("R1", "file-wide append-only anchor (C2/A1)", probe_r1_file_wide_anchor),
    ("R2", "real tamper tests (REV-003 §3.4)", probe_r2_real_tamper_tests),
    ("R3", "mandatory review_line_sha256 (C3/A2)", probe_r3_mandatory_review_binding),
    ("R4", "§14 DoD command alignment", probe_r4_dod_commands),
]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    parser.add_argument(
        "--only", default=None, help="run a single group (R1, R2, R3 or R4)"
    )
    args = parser.parse_args(argv)

    report: List[Dict[str, Any]] = []
    for key, label, function in PROBES:
        if args.only and args.only != key:
            continue
        try:
            observations = function()
        except Exception as exc:  # a probe that crashes is a failed probe
            observations = [
                {
                    "id": f"{key}.crash",
                    "name": label,
                    "command": function.__name__,
                    "exit": 1,
                    "ok": False,
                    "detail": f"{type(exc).__name__}: {exc}",
                }
            ]
        report.append({"group": key, "label": label, "probes": observations})

    total = sum(len(group["probes"]) for group in report)
    passed = sum(
        1 for group in report for probe in group["probes"] if probe.get("ok")
    )
    ok = passed == total

    if args.json:
        print(json.dumps({"ok": ok, "passed": passed, "total": total, "groups": report},
                         indent=2, ensure_ascii=False))
    else:
        for group in report:
            print(f"\n{group['group']} — {group['label']}")
            for probe in group["probes"]:
                mark = "ok  " if probe.get("ok") else "FAIL"
                print(f"  [{mark}] {probe['id']:6} {probe['name']}")
                print(f"           $ {probe['command']}  -> exit {probe['exit']}")
                if not probe.get("ok") and probe.get("detail"):
                    print(f"           detail: {json.dumps(probe['detail'], ensure_ascii=False)[:400]}")
        print(f"\n{passed}/{total} probes ok -> {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
