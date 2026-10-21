"""Tests for scripts/check_memo_ledger_refs.py (memo reference verification).

The check exists because agent-written long-form output is weaker than
agent reading (contributions/2026-10-20_integrated_survey_report.md §3.4),
and this repository delegates long-form writing to agents. It cannot detect
semantic errors -- those need the original source -- but it can detect
references that do not resolve, which is the failure mode long-form
generation is most prone to and which costs nothing to verify.

Covered:
  * the real contributions/*.md scan passes (exit 0);
  * a memo citing a ledger record that exists passes;
  * a memo citing a ledger ID that does not exist fails (exit 1);
  * a memo citing a repo path that does not exist fails;
  * IDs preserved in the archive document are reported but do not fail;
  * --coverage reports ledger records no memo references, without failing;
  * a missing memo file is a usage error (exit 2), not a check failure.
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

import check_memo_ledger_refs as cm  # noqa: E402

CONTRIBUTIONS = ROOT / "contributions"
ARCHIVE_DOC = ROOT / "docs" / "archived-ledger-records-2026-10-20.md"


def _first_id(prefix: str) -> str:
    """Return one real ledger ID for `prefix` (e.g. "EVD")."""
    for name, (ledger, _schema, id_key) in __import__("validate_state").COLLECTIONS.items():
        if __import__("validate_state").ID_PREFIXES[name] != prefix:
            continue
        for line in (ROOT / ledger).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                return json.loads(line)[id_key]
    raise AssertionError(f"no ledger record for prefix {prefix}")


def _run(memo_text: str, *extra: str) -> tuple[int, str]:
    """Write `memo_text` to a temp memo and run the checker against it."""
    with tempfile.TemporaryDirectory() as tmp:
        memo = Path(tmp) / "memo.md"
        memo.write_text(memo_text, encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cm.main(["--memos", str(memo), *extra])
        return code, buf.getvalue()


class RealRepoScanTest(unittest.TestCase):
    def test_offline_scan_passes_on_real_repo(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cm.main([])
        self.assertEqual(code, 0, msg=buf.getvalue())
        self.assertIn("0 dangling reference(s)", buf.getvalue())

    def test_summary_counts_every_memo(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cm.main(["--quiet"])
        expected = len(sorted(CONTRIBUTIONS.glob("*.md")))
        self.assertIn(f"{expected} memo(s) scanned", buf.getvalue())

    def test_archived_ids_are_known_and_do_not_fail(self):
        # The integrated report legitimately discusses the records that were
        # removed from the ledgers on 2026-10-20.
        self.assertTrue(ARCHIVE_DOC.exists(), "archive document must exist")
        archived = cm.load_archived_ids(ARCHIVE_DOC)
        self.assertIn("CLM-004", archived)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cm.main([])
        self.assertEqual(code, 0, msg=buf.getvalue())
        self.assertIn("archived ID reference(s)", buf.getvalue())


class SyntheticMemoTest(unittest.TestCase):
    def test_existing_ledger_id_passes(self):
        token = _first_id("EVD")
        code, out = _run(f"根拠は {token} を参照。\n")
        self.assertEqual(code, 0, msg=out)
        self.assertIn("0 dangling reference(s)", out)

    def test_unknown_ledger_id_fails(self):
        code, out = _run("根拠は EVD-20260101-0000 を参照。\n")
        self.assertEqual(code, 1, msg=out)
        self.assertIn("dangling ledger ID EVD-20260101-0000", out)

    def test_unknown_repo_path_fails(self):
        code, out = _run("実装は gitswarm/does_not_exist.py にある。\n")
        self.assertEqual(code, 1, msg=out)
        self.assertIn("dangling path gitswarm/does_not_exist.py", out)

    def test_existing_repo_path_passes(self):
        code, out = _run("実装は gitswarm/readout_sim.py にある。\n")
        self.assertEqual(code, 0, msg=out)

    def test_bare_filename_is_not_checked(self):
        # The pattern is deliberately conservative: only repo-relative paths
        # under a known top-level directory are checked.
        code, out = _run("実装は run_simulation.py にあった（現在は存在しない）。\n")
        self.assertEqual(code, 0, msg=out)

    def test_archived_id_does_not_fail(self):
        code, out = _run("CLM-004 は退避済みである。\n")
        self.assertEqual(code, 0, msg=out)
        self.assertIn("archived ledger ID CLM-004", out)

    def test_same_dangling_token_reported_once_per_memo(self):
        code, out = _run("EVD-20260101-0000 と EVD-20260101-0000 を参照。\n")
        self.assertEqual(code, 1, msg=out)
        self.assertEqual(out.count("EVD-20260101-0000"), 1)

    def test_coverage_reports_unreferenced_records_without_failing(self):
        code, out = _run("本文。\n", "--coverage")
        self.assertEqual(code, 0, msg=out)
        self.assertIn("not referenced by any memo", out)


class UsageTest(unittest.TestCase):
    def test_missing_memo_file_is_usage_error(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cm.main(["--memos", str(ROOT / "contributions" / "nope.md")])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
