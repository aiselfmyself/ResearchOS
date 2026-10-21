"""Tests for scripts/sync_doc_counts.py (the mechanical half of gate 8).

Gate 8 (`check_doc_numbers.py`) refuses a document whose current-state numbers
are stale. Syncing those numbers is mechanical -- recompute, replace -- but it
was a hand edit until 2026-10-21, and during the sharding migration that hand
edit collided with `origin/main` three times on the same one-line number
(contributions/2026-10-21_ledger_sharding_migration.md sections 4.3 and 4.4).

These tests pin the properties that make the tool safe to run unattended:

  * it changes only numbers the checker flagged, and only on those lines;
  * prose, ordering, blockquotes and `drift-ok` lines are preserved verbatim;
  * a per-file count next to another number is fixed without touching the
    neighbour;
  * `relations=` is synced like the other five ledger counts;
  * `--dry-run` writes nothing;
  * after a run the checker is clean, and a clean file yields no changes.
"""
from __future__ import annotations

import contextlib
import io
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
import sync_doc_counts as sdc  # noqa: E402

LEDGERS = {
    "sources": 23,
    "evidence": 86,
    "claims": 9,
    "verifications": 34,
    "hypotheses": 2,
    "relations": 0,
}
PER_FILE = {"test_minimal_core.py": 34, "test_ledger_shards.py": 39}


class FixFileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "doc.md"

    def fix(self, text, total=342, per_file=None, gates=8, ledgers=None):
        self.path.write_text(text, encoding="utf-8")
        changes = sdc.fix_file(
            self.path, total, per_file if per_file is not None else PER_FILE,
            gates, ledgers if ledgers is not None else LEDGERS,
        )
        return changes, self.path.read_text(encoding="utf-8")

    def test_total_in_sum_form(self):
        changes, text = self.fix("- テスト: 合計 280件（`tests/` の 13 ファイル）\n")
        self.assertEqual(len(changes), 1)
        self.assertEqual(text, "- テスト: 合計 342件（`tests/` の 13 ファイル）\n")

    def test_total_in_bare_paren_form(self):
        _, text = self.fix("# 1. テスト（約5秒・280件）\n")
        self.assertEqual(text, "# 1. テスト（約5秒・342件）\n")

    def test_total_with_tests_word(self):
        _, text = self.fix("全 **280テスト** が通る\n")
        self.assertEqual(text, "全 **342テスト** が通る\n")

    def test_gate_count(self):
        _, text = self.fix("- CI ゲート: 7ゲート\n")
        self.assertEqual(text, "- CI ゲート: 8ゲート\n")

    def test_every_ledger_count_including_relations(self):
        _, text = self.fix(
            "- 台帳: sources=11 / evidence=49 / claims=8 / verifications=29 / "
            "hypotheses=2 / relations=3\n"
        )
        self.assertEqual(
            text,
            "- 台帳: sources=23 / evidence=86 / claims=9 / verifications=34 / "
            "hypotheses=2 / relations=0\n",
        )

    def test_ledger_replacement_swallows_the_whole_number(self):
        """`evidence=860` is one number: the checker reads 860, so the tool
        replaces all of it. A partial replace would leave `evidence=860`
        behind as `evidence=860` -> `evidence=86` + a stray `0`."""
        _, text = self.fix("- 台帳: evidence=860\n")
        self.assertEqual(text, "- 台帳: evidence=86\n")

    def test_per_file_count_leaves_the_neighbouring_number_alone(self):
        _, text = self.fix(
            "  test_minimal_core.py         履歴非依存の回帰テスト（30件）\n"
        )
        self.assertEqual(
            text, "  test_minimal_core.py         履歴非依存の回帰テスト（34件）\n"
        )

    def test_blockquotes_are_never_rewritten(self):
        original = "> 当時のスナップショット：evidence=11 / 合計 184件\n"
        changes, text = self.fix(original)
        self.assertEqual(changes, [])
        self.assertEqual(text, original)

    def test_drift_ok_lines_are_never_rewritten(self):
        original = "「テストが 205 件ある」こと。 <!-- drift-ok -->\n"
        changes, text = self.fix(original)
        self.assertEqual(changes, [])
        self.assertEqual(text, original)

    def test_clean_document_yields_no_changes(self):
        original = "- テスト: 合計 342件\n- CI ゲート: 8ゲート\n"
        changes, text = self.fix(original)
        self.assertEqual(changes, [])
        self.assertEqual(text, original)

    def test_untouched_lines_are_byte_identical(self):
        original = (
            "# 見出し\n"
            "\n"
            "- テスト: 合計 280件\n"
            "説明文はそのまま。  余白も保つ。\n"
            "\n"
            "```text\n"
            "候補5件、fixture追記7件（無関係な数）\n"
            "```\n"
        )
        _, text = self.fix(original)
        self.assertEqual(text, original.replace("合計 280件", "合計 342件"))

    def test_dry_run_writes_nothing(self):
        original = "- テスト: 合計 280件\n"
        self.path.write_text(original, encoding="utf-8")
        changes = sdc.fix_file(self.path, 342, PER_FILE, 8, LEDGERS, dry_run=True)
        self.assertEqual(len(changes), 1)
        self.assertEqual(self.path.read_text(encoding="utf-8"), original)

    def test_result_is_accepted_by_the_checker(self):
        text = (
            "- 台帳: sources=1 / evidence=2 / claims=3 / verifications=4 / "
            "hypotheses=5 / relations=6\n"
            "- テスト: 合計 10件（`tests/` の 2 ファイル）\n"
            "  test_minimal_core.py 回帰（1件）\n"
            "- CI ゲート: 1ゲート\n"
        )
        _, fixed = self.fix(text)
        self.assertEqual(cdn.scan_file(self.path, 342, PER_FILE, 8, LEDGERS), [])
        self.assertIn("合計 342件", fixed)


class RealRepoTest(unittest.TestCase):
    def test_dry_run_on_the_real_repo_reports_and_changes_nothing(self):
        before = {rel: (ROOT / rel).read_bytes() for rel in cdn.TARGETS}
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = sdc.main(["--dry-run"])
        self.assertEqual(code, 0)
        for rel in cdn.TARGETS:
            self.assertEqual((ROOT / rel).read_bytes(), before[rel], rel)

    def test_main_syncs_an_explicit_file_and_leaves_the_checker_green(self):
        """End-to-end on a temporary doc: `--file` accepts absolute paths.

        The tracked documents are read-only from a test's point of view: a test
        that ran `main([])` here rewrote README.md in the working tree, which is
        why this case uses its own file.
        """
        total, _per_file = cdn.actual_test_counts()
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "doc.md"
            doc.write_text(f"- テスト: 合計 {total + 1}件\n- CI ゲート: 1ゲート\n", encoding="utf-8")
            before = {rel: (ROOT / rel).read_bytes() for rel in cdn.TARGETS}
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = sdc.main(["--file", str(doc)])
            self.assertEqual(code, 0, out.getvalue())
            self.assertIn("0 stale number(s) remaining", out.getvalue())
            self.assertEqual(
                doc.read_text(encoding="utf-8"), f"- テスト: 合計 {total}件\n- CI ゲート: 8ゲート\n"
            )
            for rel in cdn.TARGETS:
                self.assertEqual((ROOT / rel).read_bytes(), before[rel], rel)

    def test_missing_doc_is_an_error(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(sdc.main(["--file", "nope.md"]), 2)


if __name__ == "__main__":
    unittest.main()
