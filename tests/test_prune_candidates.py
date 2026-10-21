"""Tests for scripts/prune_candidates.py (RRSI: low-contribution pruning).

RRSI prunes harness components of little value. This repository has been
accumulating parts -- 4 CI gates to 8, 1 check script to 10 -- and nothing had
asked which of them earn their place.

The dangerous version of this tool is one that deletes things. Pruning is a
human judgement (a gate removal changes what `main` guarantees), so the
property that matters most is pinned here directly:
`test_never_deletes_anything` asserts the source contains no deletion calls,
and `test_no_gate_is_ever_a_prune_candidate` asserts a gate can never come
back as something to prune.

Also pinned, because both were false alarms in the first draft:

* `validate_state` and `gitswarm.benchmarks.benchmark` have no
  `test_<name>.py`, but both are exercised from `tests/test_minimal_core.py`.
  Flagging them as unpinned because the *filename* does not match would be
  wrong -- coverage is therefore detected by content, not by name.
* A gate whose command is `python3 -m unittest discover` has no script target
  at all; it *is* the test runner, and warning about it is noise.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import prune_candidates as pc  # noqa: E402


class SafetyTest(unittest.TestCase):
    def test_never_deletes_anything(self):
        """The tool reports; a human decides. No removal primitives allowed."""
        source = (ROOT / "scripts" / "prune_candidates.py").read_text(
            encoding="utf-8")
        offenders = [
            name for name in ("unlink", "rmtree", "os.remove", "os.rmdir",
                              "shutil.rmtree", "Path.unlink")
            if name in source
        ]
        self.assertEqual(offenders, [],
                         f"prune tool must not delete; found {offenders}")

    def test_no_gate_is_ever_a_prune_candidate(self):
        """Removing a gate changes what main guarantees -- never suggest it."""
        report = pc.scan()
        gates = {c["component"] for c in report["components"]
                 if c["kind"] == "gate"}
        self.assertTrue(gates)
        for name in report["prune_candidates"]:
            self.assertNotIn(name, gates)
        for c in report["components"]:
            if c["kind"] == "gate":
                self.assertEqual(c["verdict"], "keep", c["component"])

    def test_main_exits_zero(self):
        self.assertEqual(pc.main([]), 0)


class CollectTest(unittest.TestCase):
    def test_scripts_are_found(self):
        names = {p.name for p in pc.collect_scripts()}
        self.assertIn("validate_state.py", names)
        self.assertIn("check_doc_numbers.py", names)

    def test_ci_commands_are_mapped(self):
        ci = pc.collect_ci_commands()
        self.assertIn("scripts/validate_state.py", ci)
        self.assertIn("scripts/check_doc_numbers.py", ci)
        # every mapped entry maps to a human-readable step name
        for script, step in ci.items():
            self.assertTrue(step.strip())
            self.assertTrue(script.startswith("scripts/"))

    def test_gates_include_all_eight(self):
        gates = pc.collect_gates()
        self.assertGreaterEqual(len(gates), 8)
        commands = " ".join(g["command"] for g in gates)
        self.assertIn("unittest discover", commands)
        self.assertIn("check_doc_numbers.py", commands)


class ClassifyTest(unittest.TestCase):
    def base(self, **kw):
        sig = {"in_ci": False, "has_tests": False,
               "referenced_in_docs": False, "imported_by": []}
        sig.update(kw)
        return sig

    def test_in_ci_is_always_keep(self):
        self.assertEqual(pc.classify(self.base(in_ci=True)), "keep")

    def test_two_or_more_signals_is_active(self):
        self.assertEqual(
            pc.classify(self.base(has_tests=True, referenced_in_docs=True)),
            "active")

    def test_one_signal_is_weak_candidate(self):
        self.assertEqual(pc.classify(self.base(has_tests=True)),
                         "weak-candidate")

    def test_no_signals_is_candidate(self):
        self.assertEqual(pc.classify(self.base()), "candidate")

    def test_imported_by_counts_as_a_signal(self):
        self.assertEqual(
            pc.classify(self.base(imported_by=["tests/test_x.py"],
                                  referenced_in_docs=True)),
            "active")


class TestCoverageTest(unittest.TestCase):
    def test_coverage_is_detected_by_content_not_filename(self):
        """validate_state has no test_validate_state.py, but is exercised
        from tests/test_minimal_core.py. Name matching would miss it."""
        self.assertFalse((pc.TESTS_DIR / "test_validate_state.py").exists())
        covered = pc.collect_test_coverage("validate_state")
        self.assertTrue(covered, "validate_state is tested under another name")
        self.assertIn("tests/test_minimal_core.py", covered)

    def test_benchmark_is_covered(self):
        self.assertTrue(pc.collect_test_coverage("benchmark"))

    def test_unknown_module_has_no_coverage(self):
        # Built at runtime: a literal here would be found by the content scan,
        # since this file is itself part of the corpus being searched.
        sentinel = "no_such_module_" + "zzz9"
        self.assertEqual(pc.collect_test_coverage(sentinel), [])

    def test_no_gate_warns_without_reason(self):
        report = pc.scan()
        for c in report["components"]:
            if c["kind"] == "gate" and c["target"] is None:
                # e.g. `python3 -m unittest discover` -- it IS the test runner
                self.assertEqual(c["warnings"], [], c["component"])


class RealRepoTest(unittest.TestCase):
    def test_every_component_has_a_verdict(self):
        for c in pc.scan()["components"]:
            self.assertIn(c["verdict"],
                          {"keep", "active", "weak-candidate", "candidate",
                           "exempt"}, c["component"])

    def test_new_id_is_exempt(self):
        """A one-shot ID minting tool with no gate or tests by design."""
        by_name = {c["component"]: c
                   for c in pc.scan()["components"] if c["kind"] == "script"}
        self.assertEqual(by_name["scripts/new_id.py"]["verdict"], "exempt")

    def test_json_output_is_serialisable(self):
        import json
        report = pc.scan()
        json.dumps(report, ensure_ascii=False)  # must not raise

    def test_findings_option_runs(self):
        report = pc.scan(with_findings=True)
        detectors = [c for c in report["components"]
                     if c.get("findings") is not None]
        self.assertTrue(detectors, "check_* detectors should report findings")


if __name__ == "__main__":
    unittest.main()
