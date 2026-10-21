"""Tests for scripts/check_ownership.py and the offline ownership fixture.

The ownership map (docs/parallel-work-ownership.md) is advisory: these tests
pin the *classification* rules and the offline self-check, and assert that the
tool stays non-enforcing (default exit code 0, not wired into CI). No test
reads git history, a commit author, or the network.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import check_ownership as co  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "ownership_cases.json"
WORKFLOW = ROOT / ".github" / "workflows" / "core-check.yml"


def run(*argv):
    """Call main() and return (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = co.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class TestClassify(unittest.TestCase):
    def test_integrator_only_paths(self):
        for path in (
            "README.md",
            "docs/minimal-core-and-ci.md",
            "gitswarm/artifacts/benchmark_matrix.json",
        ):
            self.assertEqual(co.classify(path), co.INTEGRATOR_ONLY, path)

    def test_state_is_appendable_by_any_session(self):
        # 2026-10-21: ledger appends and ID minting no longer need a human or
        # the integrator. Deletion/rewriting is still human-gated, but this tool
        # only sees paths, so it cannot tell the two apart -- see the map.
        for path in ("state/claims.jsonl", "state", "state/evidence.jsonl"):
            self.assertEqual(co.classify(path), co.ANY_SESSION_APPEND, path)
        self.assertNotIn(co.ANY_SESSION_APPEND, co.CONFLICTING)

    def test_contributions_are_session_writable(self):
        self.assertEqual(
            co.classify("contributions/2026-10-20_note.md"), co.SESSION_CONTRIBUTION
        )

    def test_other_sessions_note_needs_session_file(self):
        mine = "contributions/2026-10-20_mine.md"
        self.assertEqual(co.classify(mine, session_file=mine), co.SESSION_CONTRIBUTION)
        self.assertEqual(
            co.classify("contributions/2026-10-20_theirs.md", session_file=mine),
            co.OTHER_SESSION_CONTRIBUTION,
        )

    def test_paths_outside_the_map_are_unspecified_not_forbidden(self):
        for path in (
            "scripts/check_ownership.py",
            "tests/test_ownership.py",
            "docs/record-id-scheme.md",
            "task/TASK.md",
            "schemas/claim.json",
        ):
            self.assertEqual(co.classify(path), co.UNSPECIFIED, path)

    def test_prefix_lookalikes_do_not_match(self):
        for path in (
            "README.md.bak",
            "docs/minimal-core-and-ci.md.orig",
            "stateful/ledger.jsonl",
            "gitswarm/solvers/greedy.py",
        ):
            self.assertEqual(co.classify(path), co.UNSPECIFIED, path)

    def test_normalization_and_deduplication(self):
        classes = co.classify_many(["./README.md", "README.md", "state/./evidence.jsonl"])
        self.assertEqual(
            classes,
            {"README.md": co.INTEGRATOR_ONLY, "state/evidence.jsonl": co.ANY_SESSION_APPEND},
        )

    def test_rejects_paths_that_escape_the_repository(self):
        for bad in ("/etc/passwd", "../outside.md", "state/../../x"):
            with self.assertRaises(ValueError, msg=bad):
                co.classify(bad)


class TestSelfTest(unittest.TestCase):
    def test_bundled_fixture_is_valid_and_passes(self):
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(data["schema"], "ownership-cases-v1")
        self.assertGreaterEqual(len(data["cases"]), 4)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(co.run_selftest(FIXTURE), 0)
        self.assertIn("cases passed", out.getvalue())

    def test_selftest_detects_a_wrong_expectation(self):
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        case = json.loads(json.dumps(data["cases"][0]))
        first = next(iter(case["expect"]))
        case["expect"][first] = co.SESSION_CONTRIBUTION
        broken = {"schema": data["schema"], "cases": [case]}

        tmp = ROOT / "tests" / "fixtures" / "_tmp_ownership_broken.json"
        try:
            tmp.write_text(json.dumps(broken), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(co.run_selftest(tmp), 1)
            self.assertIn("FAIL", out.getvalue())
        finally:
            tmp.unlink(missing_ok=True)

    def test_selftest_missing_fixture_is_an_io_error(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
            io.StringIO()
        ):
            self.assertEqual(co.run_selftest(ROOT / "tests" / "fixtures" / "nope.json"), 2)


class TestCli(unittest.TestCase):
    def test_selftest_cli_is_green(self):
        code, out, _ = run("--selftest")
        self.assertEqual(code, 0)
        self.assertIn("cases passed", out)

    def test_default_mode_is_advisory(self):
        # INTEGRATOR_ONLY and OTHER_SESSION_CONTRIBUTION are present, but without
        # --strict nothing is blocked: this is the whole point of the map.
        code, out, err = run(
            "README.md",
            "state/claims.jsonl",
            "contributions/theirs.md",
            "--session-file",
            "contributions/mine.md",
        )
        self.assertEqual(code, 0)
        self.assertIn("advisory only", out)
        self.assertIn(co.OTHER_SESSION_CONTRIBUTION, out)
        self.assertEqual(err, "")

    def test_strict_mode_is_opt_in(self):
        code, _, err = run("README.md", "--strict")
        self.assertEqual(code, 1)
        self.assertIn("conflict", err)
        code, _, _ = run("docs/record-id-scheme.md", "--strict")
        self.assertEqual(code, 0)

    def test_json_output(self):
        code, out, _ = run("README.md", "--json")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["schema"], "ownership-report-v1")
        self.assertEqual(payload["paths"]["README.md"], co.INTEGRATOR_ONLY)

    def test_bad_path_is_a_usage_error(self):
        code, _, err = run("/etc/passwd")
        self.assertEqual(code, 2)
        self.assertIn("absolute path", err)

    def test_not_wired_into_ci(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("check_ownership", workflow)
        self.assertNotIn("ownership", workflow)


if __name__ == "__main__":
    unittest.main()
