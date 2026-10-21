#!/usr/bin/env python3
"""Inventory structural usage signals for human maintenance triage.

RELATION TO RRSI (arXiv:2609.24972)
----------------------------------
RRSI's pruning signal is measured utility: it tracks recent score changes for
evaluated edits by component, and sends components with no strictly positive
recent measured gain back to the proposer for removal. A separate acceptance
rule measures policy-token cost. This script implements neither rule.

Instead, it reports static repository signals (CI inclusion, tests, doc
references, and importers) that can help a human decide where to inspect. They
are not measures of performance contribution, token cost, component size, or
continued usefulness. The resulting candidate list is a prompt for review,
not an RRSI pruning verdict and not an authorization to delete anything.

The repository has been accumulating parts too. This tool asks which pieces
have observable structural links, while leaving utility and removal decisions
to measured evidence and human review.

WHAT THIS REPORTS
-----------------
For every script in `scripts/` and every gate in `core-check.yml`, it computes
mechanically-checkable structural signals:

    in_ci              is the script a CI gate step?
    has_tests          does tests/test_<name>.py exist?
    referenced_in_docs is it named in README.md or docs/*.md?
    imported_by        is it imported by another script or test?
    findings           (detectors only, --findings) findings on today's corpus

and classifies each component as `keep` / `active` / `weak-candidate` /
`candidate`.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
**It deletes nothing.** Pruning is a human judgement; this tool only stops the
question from going unasked. A report is the deliverable.

Two ambiguities are called out rather than resolved, because they cannot be
settled mechanically:

1. **A detector with zero findings is not automatically dead weight.** It may
   be a *deterrent* -- the reason the corpus is clean. Reporting "0 findings"
   as a prune signal would be to punish a check for working. So findings are
   reported as information and never fed into the verdict.
2. **A gate is load-bearing by definition.** Removing one changes what `main`
   guarantees, which is a policy decision, not a cleanup. Gates are therefore
   always classified `keep`, and only their *test coverage* is flagged.

Exit code: always 0 -- an instrument, never a gate (the same rule as
`measure_agreement.py`, `estimate_rho.py`, `harness_regime.py`,
`holdout_eval.py`).

USAGE
-----
    python3 scripts/prune_candidates.py
    python3 scripts/prune_candidates.py --findings   # also run each detector
    python3 scripts/prune_candidates.py --json

Standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
TESTS_DIR = ROOT / "tests"
WORKFLOW = ROOT / ".github" / "workflows" / "core-check.yml"
DOC_GLOBS = ("README.md", "docs/*.md")

# Scripts that are the repository's own plumbing rather than components.
# `new_id.py` is a one-shot ID minting tool; it has no gate and no tests by
# design, and reporting it as a prune candidate would be noise.
EXEMPT = {"new_id.py"}


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


# --------------------------------------------------------------------------
# signal collection
# --------------------------------------------------------------------------
def collect_scripts() -> List[Path]:
    return sorted(SCRIPTS_DIR.glob("*.py"))


def collect_ci_commands() -> Dict[str, str]:
    """Map 'scripts/foo.py' -> workflow step name, for steps that run a command."""
    out: Dict[str, str] = {}
    if not WORKFLOW.exists():
        return out
    name = None
    for raw in WORKFLOW.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        m = re.match(r"-\s*name:\s*(.+?)\s*$", stripped)
        if m:
            name = m.group(1).strip("\"'")
            continue
        m = re.match(r"run:\s*(.+?)\s*$", stripped)
        if m and name:
            for token in re.findall(r"scripts/([A-Za-z0-9_]+\.py)", m.group(1)):
                out[f"scripts/{token}"] = name
            name = None
    return out


def collect_doc_text() -> str:
    parts: List[str] = []
    for pattern in DOC_GLOBS:
        for p in sorted(ROOT.glob(pattern)):
            if p.is_file():
                parts.append(p.read_text(encoding="utf-8"))
    return "\n".join(parts)


def collect_test_coverage(stem: str) -> List[str]:
    """Test files that import or invoke this module, under any name.

    `validate_state` and `gitswarm.benchmarks.benchmark` have no
    test_validate_state.py / test_benchmark.py, but both are exercised inside
    tests/test_minimal_core.py. Flagging them as unpinned because the *file
    name* does not match would be a false alarm.
    """
    pattern = re.compile(rf"\b{re.escape(stem)}\b")
    covered: List[str] = []
    if not TESTS_DIR.is_dir():
        return covered
    for p in sorted(TESTS_DIR.glob("test_*.py")):
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        if pattern.search(text):
            covered.append(_rel(p))
    return covered


def collect_importers(stem: str) -> List[str]:
    """Files (scripts or tests) that import this module."""
    importers: List[str] = []
    pattern = re.compile(
        rf"^\s*(?:import|from)\s+{re.escape(stem)}\b", re.MULTILINE)
    for d in (SCRIPTS_DIR, TESTS_DIR):
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.py")):
            if p.name == f"{stem}.py":
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except OSError:
                continue
            if pattern.search(text):
                importers.append(_rel(p))
    return importers


def count_findings(script: str) -> Optional[int]:
    """Run a detector over its default corpus and count findings.

    Only meaningful for the check_* detectors; None for everything else.
    """
    if not script.startswith("check_"):
        return None
    cmd = [sys.executable, str(SCRIPTS_DIR / script), "--json"]
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True,
                              text=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode not in (0, 1):
        return None
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        if "findings" in data:
            return len(data["findings"])
        for key in ("summary", "report"):
            pass
    if isinstance(data, list):
        return len(data)
    return None


# --------------------------------------------------------------------------
# classification
# --------------------------------------------------------------------------
def classify(sig: Dict[str, Any]) -> str:
    if sig["in_ci"]:
        return "keep"
    hits = sum(1 for k in ("has_tests", "referenced_in_docs", "imported_by")
               if sig[k])
    if hits >= 2:
        return "active"
    if hits == 1:
        return "weak-candidate"
    return "candidate"


def evaluate_script(path: Path, docs: str, ci: Dict[str, str],
                    with_findings: bool) -> Dict[str, Any]:
    rel = _rel(path)
    stem = path.stem
    tests = TESTS_DIR / f"test_{stem}.py"
    importers = collect_importers(stem)
    sig: Dict[str, Any] = {
        "component": rel,
        "kind": "script",
        "in_ci": rel in ci,
        "ci_step": ci.get(rel),
        "has_tests": tests.is_file(),
        "test_file": _rel(tests) if tests.is_file() else None,
        "referenced_in_docs": stem in docs,
        "imported_by": importers,
        "exempt": path.name in EXEMPT,
    }
    if with_findings:
        sig["findings"] = count_findings(path.name)
    covered = collect_test_coverage(stem)
    sig["tested_by"] = covered
    sig["covered_by_tests"] = bool(sig["has_tests"] or covered)
    sig["verdict"] = "exempt" if sig["exempt"] else classify(sig)
    if sig["in_ci"] and not sig["covered_by_tests"]:
        sig.setdefault("warnings", []).append(
            "in CI but no test file imports or names it -- the gate is "
            "load-bearing, yet nothing pins its behaviour")
    return sig


def evaluate_gate(step: str, command: str, docs: str) -> Dict[str, Any]:
    """A gate's own contribution is policy; only its test coverage is checked."""
    m = re.search(r"(?:scripts|gitswarm)/[A-Za-z0-9_/]+\.py", command)
    target = m.group(0) if m else None
    tests: Optional[str] = None
    covered: List[str] = []
    warnings: List[str] = []
    if target:
        stem = Path(target).stem
        cand = TESTS_DIR / f"test_{stem}.py"
        tests = _rel(cand) if cand.is_file() else None
        covered = collect_test_coverage(stem)
    # A gate with no script target (e.g. `python3 -m unittest discover`) *is*
    # the test runner; there is nothing to pin and nothing to warn about.
    if target and not (tests or covered):
        warnings.append(
            "no test file imports or names the target -- the gate is "
            "load-bearing, yet nothing pins its behaviour")
    return {
        "component": step,
        "kind": "gate",
        "command": command,
        "target": target,
        "test_file": tests,
        "tested_by": covered,
        "in_ci": True,
        "verdict": "keep",
        "warnings": warnings,
    }


def collect_gates() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not WORKFLOW.exists():
        return out
    name = None
    for raw in WORKFLOW.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        m = re.match(r"-\s*name:\s*(.+?)\s*$", stripped)
        if m:
            name = m.group(1).strip("\"'")
            continue
        m = re.match(r"run:\s*(.+?)\s*$", stripped)
        if m and name:
            out.append({"step": name, "command": m.group(1).strip()})
            name = None
    return out


def scan(with_findings: bool = False) -> Dict[str, Any]:
    docs = collect_doc_text()
    ci = collect_ci_commands()
    components: List[Dict[str, Any]] = []
    for p in collect_scripts():
        components.append(evaluate_script(p, docs, ci, with_findings))
    for g in collect_gates():
        components.append(evaluate_gate(g["step"], g["command"], docs))

    counts: Dict[str, int] = {}
    for c in components:
        counts[c["verdict"]] = counts.get(c["verdict"], 0) + 1
    return {
        "components": components,
        "counts": counts,
        "prune_candidates": [c["component"] for c in components
                             if c["verdict"] in ("candidate", "weak-candidate")],
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--findings", action="store_true",
                    help="also run each detector and report its finding count "
                         "(slower; informational only, never feeds the verdict)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    report = scan(with_findings=args.findings)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    for c in report["components"]:
        if c["kind"] == "gate":
            flag = "  " if not c["warnings"] else "! "
            print(f"{flag}[gate]   {c['component']}")
            print(f"         -> {c['command']}")
            cover = c["test_file"] or (", ".join(c["tested_by"]) or "NONE")
            print(f"         test: {cover}")
            continue
        marks = []
        if c["in_ci"]:
            marks.append("ci")
        if c["has_tests"]:
            marks.append("tests")
        elif c.get("tested_by"):
            marks.append(f"tests-via:{len(c['tested_by'])}")
        if c["referenced_in_docs"]:
            marks.append("docs")
        if c["imported_by"]:
            marks.append(f"imported-by:{len(c['imported_by'])}")
        if c.get("findings") is not None:
            marks.append(f"findings:{c['findings']}")
        print(f"   [script] {c['component']}  ({', '.join(marks) or 'no signals'})"
              f"  -> {c['verdict']}")
        for w in c.get("warnings", []):
            print(f"         ! {w}")

    counts = report["counts"]
    summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    print(f"\nsummary: {len(report['components'])} component(s) [{summary}]")
    if report["prune_candidates"]:
        print("prune candidates (HUMAN DECISION -- nothing is deleted):")
        for name in report["prune_candidates"]:
            print(f"  - {name}")
    else:
        print("prune candidates: none")
    print("\nNote: a detector reporting 0 findings is NOT a prune signal -- it "
          "may be a deterrent.\n      Gates are always 'keep': removing one "
          "changes what main guarantees.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
