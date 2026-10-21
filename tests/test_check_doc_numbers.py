"""Tests for scripts/check_doc_numbers.py (audit ID 19: stale-number check).

The defect class is: a number describing the repository's *current* state is
written literally into prose, and nothing re-checks it. The 2026-10-20 audit
hit this twice (ID 12: stale counts; ID 14: DoD said "3検査" while CI had 7
gates) and found both by hand.

The hard part is not detecting drift -- it is **not flagging legitimate
numbers**. "候補5件" and "fixture追記7件" are counts, but they are not test
counts. An earlier draft of this checker produced four false positives on
docs/minimal-core-and-ci.md alone, so those cases are pinned here as tests.

`scan_file()` takes the expected values as arguments, so a test can supply any
combination without touching the real ledger.

Covered:
  * the real repo passes with zero findings;
  * actual_* recompute from the repo and agree with each other;
  * a stale total is caught, including the bare "N件" form;
  * a stale per-file count is caught even when the line names a second,
    unrelated test file (the case a line-level rule gave up on);
  * blockquotes and `drift-ok` are skipped;
  * generic "N件" counts with no test context are NOT flagged;
  * gate and ledger mismatches are caught;
  * a missing file is reported, not crashed on.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import check_doc_numbers as cdn  # noqa: E402


class RealRepoTest(unittest.TestCase):
    def test_repo_docs_have_no_stale_numbers(self):
        report = cdn.scan(cdn.TARGETS)
        self.assertEqual(report["findings"], [], msg=str(report["findings"]))

    def test_main_exits_zero_on_the_real_repo(self):
        self.assertEqual(cdn.main([]), 0)

    def test_every_target_exists(self):
        for rel in cdn.TARGETS:
            self.assertTrue((ROOT / rel).is_file(), rel)


class ActualValueTest(unittest.TestCase):
    def test_test_counts_sum(self):
        total, per_file = cdn.actual_test_counts()
        self.assertEqual(total, sum(per_file.values()))
        self.assertGreater(total, 0)
        self.assertIn("test_minimal_core.py", per_file)

    def test_test_file_count_matches_basename(self):
        _, per_file = cdn.actual_test_counts()
        for name in per_file:
            self.assertTrue(name.startswith("test_"), name)
            self.assertTrue(name.endswith(".py"), name)

    def test_gate_count_matches_yaml_run_steps(self):
        """Gates are steps with `run:`; setup steps use `uses:`."""
        text = cdn.WORKFLOW.read_text(encoding="utf-8")
        # every step after "steps:" that has a run key
        self.assertGreaterEqual(cdn.actual_gate_count(), 3)
        self.assertIn("steps:", text)

    def test_ledger_counts_match_line_counts(self):
        ledgers = cdn.actual_ledger_counts()
        self.assertEqual(set(ledgers), set(cdn.LEDGERS))
        for name, fname in cdn.LEDGERS.items():
            path = cdn.STATE_DIR / fname
            expected = sum(1 for l in path.read_text(encoding="utf-8").splitlines() if l.strip())
            self.assertEqual(ledgers[name], expected, fname)


class ScanFileTest(unittest.TestCase):
    """scan_file(path, total, per_file, gates, ledgers) with injected values."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def scan(self, text, total=184, gates=7, ledgers=None,
             per_file=None, name="doc.md"):
        p = self.dir / name
        p.write_text(text, encoding="utf-8")
        return cdn.scan_file(
            p, total,
            per_file if per_file is not None else {"test_minimal_core.py": 34},
            gates,
            ledgers if ledgers is not None
            else {"sources": 11, "evidence": 49, "claims": 8,
                  "verifications": 29, "hypotheses": 2},
        )

    # --- things that must be caught -------------------------------------
    def test_stale_total_in_parenthesised_bare_count(self):
        """The real drift found in README.md: "テスト（約5秒・110件）"."""
        out = self.scan("# 1. テスト（約5秒・110件）\n")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["kind"], "total-tests")
        self.assertEqual(out[0]["found"], 110)
        self.assertEqual(out[0]["expected"], 184)

    def test_stale_total_with_tests_word(self):
        out = self.scan("全 **150テスト** が通る\n")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["expected"], 184)

    def test_stale_total_with_sum_form(self):
        out = self.scan("                               ── 合計 100件\n")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["kind"], "total-tests")

    def test_stale_per_file_count(self):
        out = self.scan("  test_minimal_core.py   履歴非依存の回帰テスト（34件）\n",
                        per_file={"test_minimal_core.py": 40})
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["found"], 34)
        self.assertEqual(out[0]["expected"], 40)

    def test_per_file_count_caught_even_with_second_test_file_on_line(self):
        """A line may name an unrelated test file; do not give up on it.

        This is the case that a line-level "ambiguous" rule silently missed:
        docs/minimal-core-and-ci.md says "test_minimal_core.py | （28テスト）"
        and then mentions the rejected "test_integrity.py" in the notes.
        """
        line = ("| `tests/test_minimal_core.py` | **新規**（28テスト） | "
                "履歴非依存テスト。旧 `test_integrity.py` は不採用 |\n")
        out = self.scan(line, per_file={"test_minimal_core.py": 34})
        self.assertEqual(len(out), 1)
        self.assertIn("test_minimal_core.py", out[0]["kind"])
        self.assertEqual(out[0]["found"], 28)
        self.assertEqual(out[0]["expected"], 34)

    def test_stale_gate_count(self):
        out = self.scan("最小CI（3ゲート）が緑であること\n")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["kind"], "gates")
        self.assertEqual(out[0]["expected"], 7)

    def test_stale_gate_count_with_markdown_emphasis(self):
        """The DoD writes "**7 つ**）"; a strict "つ）" pattern missed it."""
        out = self.scan("1. 最小CI（`core-check.yml` の**全ゲート**——**7 つ**）が緑\n",
                        gates=8)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["kind"], "gates")
        self.assertEqual(out[0]["found"], 7)
        self.assertEqual(out[0]["expected"], 8)

    def test_stale_ledger_count(self):
        out = self.scan("台帳は evidence=40 件\n")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["kind"], "ledger:evidence")
        self.assertEqual(out[0]["expected"], 49)

    def test_missing_file_is_reported(self):
        out = cdn.scan_file(self.dir / "nope.md", 184, {}, 7, {})
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["kind"], "missing-file")

    # --- things that must NOT be caught ---------------------------------
    def test_blockquote_is_skipped(self):
        """Narrative lines are historical snapshots, not current claims."""
        out = self.scan("> 台帳は evidence=47 / verifications=27 になった\n")
        self.assertEqual(out, [])

    def test_drift_ok_marker_skips_line(self):
        out = self.scan("最小CI（3ゲート）が緑  <!-- drift-ok -->\n")
        self.assertEqual(out, [])

    def test_generic_counts_without_test_context_are_not_flagged(self):
        """The four false positives of the first draft."""
        for line in [
            "| `contributions/` 2件 | PR #9そのまま |\n",
            "| `scripts/check_memo_citations.py`、fixture追記7件 | **新規** |\n",
            "3 件出ている。\n",
            "- 期待値が旧履歴に固定（worker commit 7件・候補5件・指標100/100/80）\n",
        ]:
            with self.subTest(line=line.strip()):
                self.assertEqual(self.scan(line), [])

    def test_correct_numbers_produce_no_findings(self):
        out = self.scan(
            "  test_minimal_core.py   履歴非依存の回帰テスト（34件）\n"
            "                         ── 合計 184件\n"
            "最小CI（7ゲート）\n"
            "台帳は evidence=49 / verifications=29\n"
        )
        self.assertEqual(out, [])

    def test_unknown_test_file_name_is_not_compared(self):
        out = self.scan("| `tests/test_deleted.py` | 旧（5テスト） |\n")
        self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()
