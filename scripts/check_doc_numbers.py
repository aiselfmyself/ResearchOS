#!/usr/bin/env python3
"""Detect stale numbers in docs that describe the repository's CURRENT state.

WHY THIS EXISTS (audit ID 19)
-----------------------------
The 2026-10-20 audit found the same class of defect twice, as two separate
IDs:

* **ID 12** — recorded counts ("74テスト" etc.) went stale.
* **ID 14** — `docs/minimal-core-and-ci.md` §4 pinned the DoD to "3検査"
  while CI had grown to 4, then 6, then 7 gates.

Both were caused by the same thing: **a number describing current state was
written literally into prose, and nothing re-checked it.** Both were found by
hand, after the fact.

This script closes that class of defect. It recomputes the numbers from the
repository and compares them against the numbers written in the docs.

SCOPE IS DELIBERATELY NARROW
----------------------------
It only checks **current-state declarations**, and it only scans the files
listed in TARGETS (by default `README.md` and `docs/minimal-core-and-ci.md`).
It is NOT run over the audit or the integrated report: those are historical
narratives full of legitimately stale numbers ("evidence 47 → 48"), and a
checker that flags a normal state is worse than no checker (this is the
lesson recorded in the audit as A7).

TWO SKIP RULES
--------------
1. **Blockquotes (`>`) are skipped.** In these docs a blockquote is narrative
   — "on 2026-10-20 we did X, leaving the ledger at evidence=47" — which is a
   historical snapshot, not a claim about the present.
2. **`drift-ok` anywhere on a line skips it.** The explicit escape hatch, for
   the rare case where a non-blockquote line legitimately cites an old value.

WHAT IS CHECKED
---------------
   合計 N件 / Nテスト / N tests   -> total test count
   test_NAME.py ... （N件）       -> that file's test count
   Nゲート / N gates / N つのゲート -> CI gate count
   evidence=N, sources=N, ...     -> ledger record counts

Ambiguity rule: if a line names exactly one `test_*.py`, any number on it is
read as *that file's* count. If it names several, the line is skipped as
ambiguous. If it names none, the number is read as the total.

Actual values are recomputed, never hard-coded:
* test counts — static count of `def test_` methods (verified equal to the
  number `unittest` collects, so no imports or 5-second run is needed);
* gate count — steps in `core-check.yml` that carry a `run:` key (setup steps
  use `uses:`, so this needs no allowlist of setup step names);
* ledger counts — records in the ledger union view, i.e. the frozen
  `state/*.jsonl` base plus any `state/<name>.d/*.jsonl` session shards
  (see `scripts/ledger_store.py`).

Usage:
    python3 scripts/check_doc_numbers.py
    python3 scripts/check_doc_numbers.py --file docs/other.md
    python3 scripts/check_doc_numbers.py --json

Exit code: 0 if every checked number matches, 1 if any is stale (this IS a
gate — unlike `measure_agreement.py`, `estimate_rho.py` and
`harness_regime.py`, which are instruments). Standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]

try:
    import ledger_store
except ImportError:  # running as scripts/check_doc_numbers.py
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import ledger_store

TESTS_DIR = ROOT / "tests"
STATE_DIR = ROOT / "state"
WORKFLOW = ROOT / ".github" / "workflows" / "core-check.yml"

TARGETS = ["README.md", "docs/minimal-core-and-ci.md"]

LEDGERS = {
    "sources": "sources.jsonl",
    "evidence": "evidence.jsonl",
    "claims": "claims.jsonl",
    "verifications": "verifications.jsonl",
    "hypotheses": "hypotheses.jsonl",
}

SKIP_MARKER = "drift-ok"

# --- patterns -------------------------------------------------------------
TEST_FILE_RE = re.compile(r"test_([A-Za-z0-9_]+)\.py")
# "件" is a generic counter in Japanese ("候補5件", "fixture追記7件"), so a bare
# "N件" is only read as a test count when the line also talks about tests, or
# when it is explicitly a total ("合計 N件"). Requiring that context is what
# keeps this check free of false positives.
TOTAL_SUM_RE = re.compile(r"合計\s*(\d[\d,]*)\s*件")
TESTS_WORD_RE = re.compile(r"(\d[\d,]*)\s*(?:テスト|tests?)", re.IGNORECASE)
PAREN_COUNT_RE = re.compile(r"[（(]\s*(\d[\d,]*)\s*件\s*[）)]")
BARE_COUNT_RE = re.compile(r"(\d[\d,]*)\s*件")
HAS_TEST_WORD_RE = re.compile(r"テスト|tests?", re.IGNORECASE)
# Tolerate markdown emphasis between the counter and the paren: the DoD
# writes "**7 つ**）", which a strict "つ）" pattern misses.
GATE_RE = re.compile(r"(\d+)\s*(?:ゲート|gates?|つのゲート|つ\s*\**\s*[）)])")
LEDGER_RE = re.compile(
    r"\b(" + "|".join(LEDGERS) + r")\s*=\s*(\d[\d,]*)", re.IGNORECASE
)


def _rel(path: Path) -> str:
    """Relative to the repo root when possible, else the path as given.

    Tests scan temporary files outside the repo, so this cannot assume the
    file lives under ROOT.
    """
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _to_int(s: str) -> Optional[int]:
    try:
        return int(s.replace(",", ""))
    except (ValueError, AttributeError):
        return None


# --- actual values, recomputed from the repo ------------------------------
def actual_test_counts() -> Tuple[int, Dict[str, int]]:
    """Total test count and per-file counts, from `def test_` definitions."""
    per_file: Dict[str, int] = {}
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        n = sum(
            1 for line in path.read_text(encoding="utf-8").splitlines()
            if re.match(r"\s*def test_", line)
        )
        per_file[path.name] = n
    return sum(per_file.values()), per_file


def actual_gate_count() -> int:
    """Steps in core-check.yml that run a command. Setup steps use `uses:`."""
    if not WORKFLOW.exists():
        return 0
    # A step starts with "      - name:"; it is a gate iff it has a sibling
    # "        run:" key. Counting `- name:` blocks that are followed by `run:`
    # before the next `- name:` is enough, and needs no setup allowlist.
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    count = 0
    in_step = False
    has_run = False
    for raw in lines:
        stripped = raw.strip()
        if re.match(r"-\s*(name|uses|run)\s*:", stripped):
            if in_step and has_run:
                count += 1
            in_step = True
            has_run = stripped.startswith("run:")
        elif in_step and stripped.startswith("run:"):
            has_run = True
    if in_step and has_run:
        count += 1
    return count


def actual_ledger_counts() -> Dict[str, int]:
    """Record counts of the ledger union view (frozen base + session shards).

    Before the 2026-10-21 sharding migration this counted non-empty *lines* of
    `state/<name>.jsonl`. That is no longer the ledger: new records go to
    `state/<name>.d/*.jsonl` and the base file is frozen. Counting the union
    keeps the documented numbers meaningful; unparseable lines are not records
    and are reported by `validate_state.py` instead of being counted here.
    """
    out: Dict[str, int] = {}
    for name, fname in LEDGERS.items():
        records, _errors = ledger_store.load_jsonl(STATE_DIR / fname)
        out[name] = len(records)
    return out


# --- scanning -------------------------------------------------------------
def scan_file(path: Path, total: int, per_file: Dict[str, int],
              gates: int, ledgers: Dict[str, int]) -> List[Dict[str, Any]]:
    """Return one finding per stale number found in `path`."""
    findings: List[Dict[str, Any]] = []
    if not path.exists():
        return [{"file": _rel(path), "line": 0, "kind": "missing-file",
                 "found": None, "expected": None, "text": str(path)}]

    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if SKIP_MARKER in line:
            continue
        if line.lstrip().startswith(">"):
            continue  # narrative / historical snapshot

        # Test counts. Rather than deciding per line whether the number refers
        # to the whole suite or to one file, anchor on each `test_NAME.py`
        # mention and read the count from a window around it. A line may name
        # several test files (e.g. "test_minimal_core.py ... 旧 test_integrity.py"),
        # and a line-level rule would have to give up as ambiguous -- which is
        # exactly how a real drift (28 vs 34) slipped through.
        named = list(TEST_FILE_RE.finditer(line))
        for nm in named:
            fname = f"test_{nm.group(1)}.py"
            expected = per_file.get(fname)
            if expected is None:
                continue  # not a real test file (e.g. a deleted one)
            window = line[max(0, nm.start() - 40): min(len(line), nm.end() + 120)]
            cands = [m.group(1) for m in PAREN_COUNT_RE.finditer(window)]
            cands += [m.group(1) for m in TESTS_WORD_RE.finditer(window)]
            seen: set = set()
            for raw in cands:
                found = _to_int(raw)
                if found is None or found in seen or found == expected:
                    continue
                seen.add(found)
                findings.append({
                    "file": _rel(path), "line": lineno,
                    "kind": f"per-file-tests:{fname}", "found": found,
                    "expected": expected, "text": line.strip()[:160],
                })

        # Total test count: only on lines that name no test file at all.
        if not named:
            expected_tests = total
            cands = [m.group(1) for m in TOTAL_SUM_RE.finditer(line)]
            cands += [m.group(1) for m in TESTS_WORD_RE.finditer(line)]
            if HAS_TEST_WORD_RE.search(line):
                # e.g. "# 1. テスト（約5秒・110件）" -- a bare "N件" counts as
                # the suite size only when the line is actually about tests.
                cands += [m.group(1) for m in BARE_COUNT_RE.finditer(line)]
            seen = set()
            for raw in cands:
                found = _to_int(raw)
                if found is None or found in seen or found == expected_tests:
                    continue
                seen.add(found)
                findings.append({
                    "file": _rel(path), "line": lineno,
                    "kind": "total-tests", "found": found,
                    "expected": expected_tests, "text": line.strip()[:160],
                })

        # gate count
        for m in GATE_RE.finditer(line):
            found = _to_int(m.group(1))
            if found is None or found == gates:
                continue
            findings.append({
                "file": _rel(path), "line": lineno,
                "kind": "gates", "found": found, "expected": gates,
                "text": line.strip()[:160],
            })

        # ledger counts
        for m in LEDGER_RE.finditer(line):
            key = m.group(1).lower()
            found = _to_int(m.group(2))
            expected = ledgers.get(key)
            if found is None or expected is None or found == expected:
                continue
            findings.append({
                "file": _rel(path), "line": lineno,
                "kind": f"ledger:{key}", "found": found, "expected": expected,
                "text": line.strip()[:160],
            })

    return findings


def scan(paths: List[str]) -> Dict[str, Any]:
    total, per_file = actual_test_counts()
    gates = actual_gate_count()
    ledgers = actual_ledger_counts()
    findings: List[Dict[str, Any]] = []
    scanned: List[str] = []
    for p in paths:
        path = ROOT / p
        scanned.append(p)
        findings.extend(scan_file(path, total, per_file, gates, ledgers))
    return {
        "actual": {"total_tests": total, "gates": gates, **ledgers},
        "per_file_tests": per_file,
        "scanned": scanned,
        "findings": findings,
    }


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--file", action="append", default=None,
                    help=f"doc to check (repeatable; default: {', '.join(TARGETS)})")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    paths = args.file if args.file else list(TARGETS)
    report = scan(paths)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1 if report["findings"] else 0

    a = report["actual"]
    print(f"actual: tests={a['total_tests']} gates={a['gates']} "
          f"sources={a['sources']} evidence={a['evidence']} claims={a['claims']} "
          f"verifications={a['verifications']} hypotheses={a['hypotheses']}")
    for f in report["findings"]:
        print(f"  STALE {f['file']}:{f['line']} [{f['kind']}] "
              f"found {f['found']}, expected {f['expected']}")
        print(f"        {f['text']}")
    n = len(report["findings"])
    print(f"summary: {len(paths)} doc(s) scanned, {n} stale number(s)")
    return 1 if n else 0


if __name__ == "__main__":
    raise SystemExit(main())
