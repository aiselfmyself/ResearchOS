"""Tests for scripts/check_citations.py (README "next stage 2").

The check must be re-runnable WITHOUT network access: unit tests only ever
exercise the offline fixture path and a synthetic Atom XML document. The
--live network path is a manual tool and is deliberately never invoked here
(no test may depend on export.arxiv.org being reachable).

Covered:
  * offline check of the real ledger against the bundled snapshot passes;
  * arXiv-ID extraction (abs URL, versioned URL, DOI, non-arXiv source);
  * mismatch detection for tampered title / authors / year;
  * missing snapshot entry and malformed ledger -> non-zero exit;
  * Atom API response parsing (synthetic XML, no network).
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

import check_citations as cc  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "arxiv_metadata_snapshot.json"
SOURCES = ROOT / "state" / "sources.jsonl"

SAMPLE_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>arXiv Query: search_query=all:electron</title>
  <entry>
    <id>http://arxiv.org/abs/1707.08561v1</id>
    <published>2017-07-26T17:55:34Z</published>
    <title>Example Paper: A  Subtitle
      With Wrapping</title>
    <author><name>Alice Example</name></author>
    <author><name>Bob Example</name></author>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2610.07625v2</id>
    <published>2026-10-06T02:17:32Z</published>
    <title>Stateless Language Agents: Scaling Long-Horizon Automated Research</title>
    <author><name>Qizheng Zhang</name></author>
  </entry>
</feed>
"""


def run_main(argv):
    """Call cc.main with stdout+stderr captured; return (code, out, err)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cc.main(argv)
    return code, out.getvalue(), err.getvalue()


def write_json(path: Path, payload) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class OfflineCheckTest(unittest.TestCase):
    """The default mode: ledger vs bundled snapshot, no network."""

    def test_offline_check_passes_on_real_ledger(self):
        code, out, err = run_main([])
        self.assertEqual(code, 0, msg=f"stdout={out!r} stderr={err!r}")
        self.assertIn("0 failure(s)", out)
        self.assertIn("offline snapshot", out)

    def test_fixture_covers_every_arxiv_ledger_source(self):
        entries, _ = cc.load_fixture(FIXTURE)
        sources = cc.load_ledger(SOURCES)
        arxiv_sources = [s for s in sources if cc.extract_arxiv_id(s)]
        self.assertGreaterEqual(len(arxiv_sources), 3)
        for source in arxiv_sources:
            arxiv_id = cc.extract_arxiv_id(source)
            self.assertIn(arxiv_id, entries, msg=f"{source['source_id']} not in fixture")

    def test_non_arxiv_only_ledger_is_all_skips(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "sources.jsonl"
            row = {"source_id": "SRC-004", "title": "t", "authors": ["A"],
                   "year": 2026, "url": "https://github.com/x/y", "doi": None}
            ledger.write_text(json.dumps(row) + "\n", encoding="utf-8")
            code, out, _ = run_main(["--sources", str(ledger), "--quiet"])
        self.assertEqual(code, 0)
        self.assertIn("0 arXiv source(s) checked, 1 skipped, 0 failure(s)", out)


class ExtractArxivIdTest(unittest.TestCase):

    def test_abs_url(self):
        self.assertEqual(
            cc.extract_arxiv_id({"url": "https://arxiv.org/abs/2610.07625"}),
            "2610.07625",
        )

    def test_versioned_abs_url_strips_suffix(self):
        self.assertEqual(
            cc.extract_arxiv_id({"url": "https://arxiv.org/abs/1707.08561v3"}),
            "1707.08561",
        )

    def test_doi_form(self):
        self.assertEqual(
            cc.extract_arxiv_id({"url": None, "doi": "10.48550/arXiv.2610.04862"}),
            "2610.04862",
        )

    def test_non_arxiv_source_returns_none(self):
        self.assertIsNone(
            cc.extract_arxiv_id(
                {"url": "https://github.com/aiselfmyself/ResearchOS", "doi": None}
            )
        )

    def test_missing_fields_return_none(self):
        self.assertIsNone(cc.extract_arxiv_id({}))
        self.assertIsNone(cc.extract_arxiv_id({"url": None, "doi": None}))


class NormalizationTest(unittest.TestCase):

    def test_whitespace_collapse(self):
        self.assertEqual(cc.normalize("  Foo \n\t Bar  "), "Foo Bar")

    def test_compare_ignores_wrapping_only(self):
        source = {"title": "A B", "authors": ["X Y"], "year": 2026}
        entry = {"title": "A\n  B", "authors": ["X  Y"], "published": "2026-01-01"}
        self.assertEqual(cc.compare(source, entry), [])


class MismatchDetectionTest(unittest.TestCase):
    """Tampering with a snapshot entry must be detected (exit 1)."""

    def _run_with_tampered_entry(self, tamper):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        entry = next(e for e in fixture["entries"] if e["arxiv_id"] == "2610.07625")
        tamper(entry)
        with tempfile.TemporaryDirectory() as tmp:
            fixture_path = write_json(Path(tmp) / "fixture.json", fixture)
            return run_main(["--fixture", str(fixture_path), "--quiet"])

    def test_tampered_title_detected(self):
        code, out, _ = self._run_with_tampered_entry(
            lambda e: e.update(title="Totally Different Title")
        )
        self.assertEqual(code, 1)
        self.assertIn("MISMATCH", out)
        self.assertIn("title", out)

    def test_tampered_authors_detected(self):
        code, out, _ = self._run_with_tampered_entry(
            lambda e: e["authors"].__setitem__(0, "Someone Else")
        )
        self.assertEqual(code, 1)
        self.assertIn("authors", out)

    def test_tampered_year_detected(self):
        code, out, _ = self._run_with_tampered_entry(
            lambda e: e.update(published="2019-10-06")
        )
        self.assertEqual(code, 1)
        self.assertIn("year: ledger=2026 arxiv=2019", out)

    def test_missing_fixture_entry_detected(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["entries"] = [
            e for e in fixture["entries"] if e["arxiv_id"] != "2610.07625"
        ]
        with tempfile.TemporaryDirectory() as tmp:
            fixture_path = write_json(Path(tmp) / "fixture.json", fixture)
            code, out, _ = run_main(["--fixture", str(fixture_path), "--quiet"])
        self.assertEqual(code, 1)
        self.assertIn("MISSING", out)

    def test_malformed_ledger_line_is_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "sources.jsonl"
            ledger.write_text("{not json\n", encoding="utf-8")
            code, _, err = run_main(["--sources", str(ledger)])
        self.assertEqual(code, 2)
        self.assertIn("invalid JSON", err)


class AtomParsingTest(unittest.TestCase):
    """--live response parsing, exercised on synthetic XML only (no network)."""

    def test_parse_atom_response(self):
        entries = cc.parse_atom_response(SAMPLE_ATOM)
        self.assertEqual(set(entries), {"1707.08561", "2610.07625"})
        first = entries["1707.08561"]
        self.assertEqual(first["title"], "Example Paper: A Subtitle With Wrapping")
        self.assertEqual(first["authors"], ["Alice Example", "Bob Example"])
        self.assertEqual(first["published"], "2017-07-26")
        self.assertEqual(entries["2610.07625"]["published"], "2026-10-06")

    def test_parse_atom_response_ignores_error_placeholders(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <id>http://arxiv.org/abs/9999.99999</id>
            <title>Error</title>
          </entry>
        </feed>"""
        # No version suffix on a 5-digit id is still a valid arXiv id shape;
        # an entry without a parsable id at all is dropped:
        xml_no_id = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry><title>Rate exceeded.</title></entry>
        </feed>"""
        self.assertEqual(set(cc.parse_atom_response(xml_no_id)), set())
        self.assertEqual(set(cc.parse_atom_response(xml)), {"9999.99999"})


if __name__ == "__main__":
    unittest.main()
