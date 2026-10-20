"""Tests for scripts/check_memo_citations.py (memo citation verification).

The check must be re-runnable WITHOUT network access: unit tests only ever
exercise the offline fixture path. The --live network path is a manual tool
and is deliberately never invoked here (no test may depend on
export.arxiv.org being reachable).

Covered:
  * offline check of the real contributions/*.md against the bundled
    snapshot passes (exit 0, zero failures);
  * the fixture covers every arXiv ID cited anywhere in contributions/;
  * reference-line parsing (labels, leading parentheticals, ellipses,
    non-arXiv entries);
  * author-list comparison (exact / prefix+suffix / mismatch);
  * detection of tampered title, year, authors, and missing snapshot
    entries (exit 1);
  * inline arXiv mentions outside the 参考文献 section are checked too;
  * files without a reference section are noted, not failed.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import check_memo_citations as cm  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "arxiv_metadata_snapshot.json"
CONTRIBUTIONS = ROOT / "contributions"

SYNTHETIC_ENTRY = {
    "arxiv_id": "2610.00001",
    "source_url": "https://arxiv.org/abs/2610.00001",
    "title": "Synthetic Paper: A Title",
    "authors": ["Alice One", "Bob Two", "Carol Three", "Dan Four"],
    "published": "2026-10-01",
}


def run_main(argv):
    """Call cm.main with stdout+stderr captured; return (code, out, err)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cm.main(argv)
    return code, out.getvalue(), err.getvalue()


def write_text(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


class OfflineCheckTest(unittest.TestCase):
    """The default mode: real memos vs bundled snapshot, no network."""

    def test_offline_check_passes_on_real_repo(self):
        code, out, err = run_main([])
        self.assertEqual(code, 0, msg=f"stdout={out!r} stderr={err!r}")
        self.assertIn("0 failure(s)", out)
        self.assertIn("offline snapshot", out)

    def test_fixture_covers_every_arxiv_id_cited_in_contributions(self):
        entries, _ = cm.cc.load_fixture(FIXTURE)
        cited = set()
        for memo in sorted(CONTRIBUTIONS.glob("*.md")):
            cited.update(cm.extract_arxiv_ids(memo.read_text(encoding="utf-8")))
        self.assertGreaterEqual(len(cited), 4)
        for arxiv_id in sorted(cited):
            self.assertIn(arxiv_id, entries, msg=f"{arxiv_id} not in fixture")

    def test_summary_counts_memos(self):
        code, out, _ = run_main(["--quiet"])
        self.assertEqual(code, 0)
        self.assertRegex(out, r"\d+ memo\(s\) scanned, \d+ arXiv citation\(s\) checked")


class ExtractIdsTest(unittest.TestCase):

    def test_colon_and_url_forms(self):
        text = "arXiv:2610.07625 and https://arxiv.org/abs/2610.04862v1 end"
        self.assertEqual(cm.extract_arxiv_ids(text), ["2610.07625", "2610.04862"])

    def test_doi_form_is_not_matched(self):
        # 10.48550/arXiv.2610.07625 uses a dot and must not be picked up as
        # a standalone mention (the same line's arXiv: form covers it).
        self.assertEqual(cm.extract_arxiv_ids("DOI: 10.48550/arXiv.2610.07625"), [])

    def test_plain_arxiv_word_not_matched(self):
        self.assertEqual(cm.extract_arxiv_ids("arXiv API and arXiv の abs ページ"), [])


class ParseReferenceTest(unittest.TestCase):

    def test_basic_entry_with_ellipsis(self):
        line = (
            '[1] Alice One, Bob Two, Carol Three, …, Dan Four. "Synthetic '
            'Paper: A Title." arXiv:2610.00001v1 [cs.AI], 2026（投稿 '
            "2026-10-01）. https://arxiv.org/abs/2610.00001 / DOI: "
            "10.48550/arXiv.2610.00001"
        )
        entry = cm.parse_reference_entry(line)
        self.assertEqual(entry["label"], "1")
        self.assertEqual(entry["arxiv_id"], "2610.00001")
        self.assertEqual(entry["title"], "Synthetic Paper: A Title.")
        self.assertEqual(entry["year"], 2026)
        self.assertEqual(
            entry["authors"], "Alice One, Bob Two, Carol Three, …, Dan Four"
        )

    def test_leading_parenthetical_is_stripped(self):
        line = '[3]（言及のみ）Alice One. "Synthetic Paper: A Title." arXiv:2610.00001, 2026.'
        entry = cm.parse_reference_entry(line)
        self.assertTrue(entry["authors"].startswith("Alice One"))
        self.assertEqual(entry["year"], 2026)

    def test_non_arxiv_entry_has_no_id(self):
        entry = cm.parse_reference_entry(
            "[4] Some repo. https://github.com/example/repo （2026-10-20 確認）"
        )
        self.assertEqual(entry["label"], "4")
        self.assertIsNone(entry["arxiv_id"])

    def test_non_reference_lines_return_none(self):
        self.assertIsNone(cm.parse_reference_entry("## 10. 参考文献"))
        self.assertIsNone(cm.parse_reference_entry("（内部記録への参照は文献引用ではない。）"))
        self.assertIsNone(cm.parse_reference_entry(""))


class AuthorCheckTest(unittest.TestCase):

    def test_exact_match_without_ellipsis(self):
        authors = "Alice One, Bob Two, Carol Three, Dan Four"
        self.assertEqual(cm.check_author_list(authors, SYNTHETIC_ENTRY["authors"]), [])

    def test_prefix_suffix_match_with_ellipsis(self):
        authors = "Alice One, Bob Two, …, Dan Four"
        self.assertEqual(cm.check_author_list(authors, SYNTHETIC_ENTRY["authors"]), [])

    def test_empty_segment_passes(self):
        self.assertEqual(cm.check_author_list("", SYNTHETIC_ENTRY["authors"]), [])

    def test_wrong_head_detected(self):
        authors = "Eve Wrong, Bob Two, …, Dan Four"
        problems = cm.check_author_list(authors, SYNTHETIC_ENTRY["authors"])
        self.assertTrue(any("head mismatch" in p for p in problems))

    def test_wrong_tail_detected(self):
        authors = "Alice One, Bob Two, …, Mallory Wrong"
        problems = cm.check_author_list(authors, SYNTHETIC_ENTRY["authors"])
        self.assertTrue(any("tail mismatch" in p for p in problems))

    def test_too_many_listed_detected(self):
        authors = "Alice One, Bob Two, Carol Three, Dan Four, Eve Wrong"
        problems = cm.check_author_list(authors, SYNTHETIC_ENTRY["authors"])
        self.assertTrue(problems)


class EntryCheckTest(unittest.TestCase):
    """check_entry against a synthetic fixture dict (no file IO)."""

    ENTRIES = {"2610.00001": SYNTHETIC_ENTRY}

    def _entry(self, **overrides):
        entry = {
            "label": "1",
            "arxiv_id": "2610.00001",
            "ids": ["2610.00001"],
            "title": "Synthetic Paper: A Title",
            "authors": "Alice One, Bob Two, Carol Three, Dan Four",
            "year": 2026,
        }
        entry.update(overrides)
        return entry

    def test_matching_entry_is_ok(self):
        checked, lines = cm.check_entry("memo.md", self._entry(), self.ENTRIES)
        self.assertEqual(checked, 1)
        self.assertTrue(lines[0].startswith("OK"))

    def test_title_case_difference_is_tolerated(self):
        checked, lines = cm.check_entry(
            "memo.md", self._entry(title="synthetic paper: a title"), self.ENTRIES
        )
        self.assertEqual(checked, 1)
        self.assertTrue(lines[0].startswith("OK"))

    def test_title_mismatch_detected(self):
        checked, lines = cm.check_entry(
            "memo.md", self._entry(title="Totally Different Title"), self.ENTRIES
        )
        self.assertEqual(checked, 1)
        self.assertTrue(any(l.startswith("MISMATCH") and "title" in l for l in lines))

    def test_year_mismatch_detected(self):
        checked, lines = cm.check_entry("memo.md", self._entry(year=2025), self.ENTRIES)
        self.assertEqual(checked, 1)
        self.assertTrue(any("year: memo=2025 arxiv=2026" in l for l in lines))

    def test_authors_mismatch_detected(self):
        checked, lines = cm.check_entry(
            "memo.md", self._entry(authors="Mallory Wrong"), self.ENTRIES
        )
        self.assertEqual(checked, 1)
        self.assertTrue(any("authors" in l for l in lines))

    def test_missing_fixture_entry_detected(self):
        checked, lines = cm.check_entry("memo.md", self._entry(), {})
        self.assertEqual(checked, 1)
        self.assertTrue(lines[0].startswith("MISSING"))

    def test_inconsistent_ids_in_one_reference_detected(self):
        checked, lines = cm.check_entry(
            "memo.md", self._entry(ids=["2610.00001", "2610.00002"]), self.ENTRIES
        )
        self.assertEqual(checked, 1)
        self.assertTrue(any("inconsistent arXiv IDs" in l for l in lines))

    def test_non_arxiv_entry_is_skipped(self):
        entry = {"label": "9", "ids": [], "arxiv_id": None}
        checked, lines = cm.check_entry("memo.md", entry, self.ENTRIES)
        self.assertEqual(checked, 0)
        self.assertTrue(lines[0].startswith("SKIP"))


class MemoFileTest(unittest.TestCase):
    """Whole-file behaviour on temporary memos (offline fixture path only)."""

    def _write_fixture(self, tmp: str) -> Path:
        payload = {
            "schema": "researchos/arxiv-metadata-snapshot/v1",
            "captured_at": "2026-10-20",
            "entries": [SYNTHETIC_ENTRY],
        }
        fixture = Path(tmp) / "fixture.json"
        fixture.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return fixture

    def test_wrong_year_in_memo_fails(self):
        memo = (
            "# Test memo\n\nbody\n\n## 参考文献\n\n"
            '[1] Alice One, Bob Two, Carol Three, …, Dan Four. "Synthetic '
            "Paper: A Title.\" arXiv:2610.00001v1 [cs.AI], 2025. "
            "https://arxiv.org/abs/2610.00001\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = write_text(Path(tmp) / "memo.md", memo)
            fixture = self._write_fixture(tmp)
            code, out, _ = run_main(
                ["--memos", str(path), "--fixture", str(fixture), "--quiet"]
            )
        self.assertEqual(code, 1)
        self.assertIn("MISMATCH", out)
        self.assertIn("year: memo=2025 arxiv=2026", out)

    def test_inline_mention_must_be_in_fixture(self):
        memo = "# Test\n\nWe build on arXiv:9999.11111 here.\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = write_text(Path(tmp) / "memo.md", memo)
            code, out, _ = run_main(
                ["--memos", str(path), "--fixture", str(FIXTURE), "--quiet"]
            )
        self.assertEqual(code, 1)
        self.assertIn("MISSING", out)
        self.assertIn("9999.11111", out)

    def test_file_without_reference_section_passes_with_note(self):
        memo = "# Test\n\nNo bibliography, only arXiv:2610.07625 inline.\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = write_text(Path(tmp) / "memo.md", memo)
            code, out, _ = run_main(
                ["--memos", str(path), "--fixture", str(FIXTURE)]
            )
        self.assertEqual(code, 0)
        self.assertIn("no 参考文献 section", out)
        self.assertIn("0 failure(s)", out)

    def test_missing_memo_file_is_usage_error(self):
        code, _, err = run_main(["--memos", "/nonexistent/memo.md"])
        self.assertEqual(code, 2)
        self.assertIn("not found", err)

    def test_malformed_fixture_is_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "fixture.json"
            fixture.write_text("{not json", encoding="utf-8")
            code, _, err = run_main(["--fixture", str(fixture)])
        self.assertEqual(code, 2)
        self.assertIn("failed to load fixture", err)


if __name__ == "__main__":
    unittest.main()
