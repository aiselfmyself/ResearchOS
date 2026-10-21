"""Tests for scripts/new_ledger_shard.py.

The tool exists because the shard *name* is load-bearing: `scripts/ledger_store.py`
reads only files matching `YYYY-MM-DD-<12 hex>.jsonl` (snapshot parts: `.json`)
and reports the rest instead of reading them. During the 2026-10-21 migration's
own experiments a shard was written without its `.jsonl` suffix and was
therefore invisible to every reader. These tests pin:

  * generated names satisfy the very pattern the loader uses;
  * the date can be pinned and a bad date is rejected;
  * `--create` makes the directory (git cannot track an empty one) and writes a
    file the loader accepts;
  * a snapshot part gets a valid document with `entries: []`;
  * a directory that already holds a file the loader would not read is
    reported, so a new shard is not added next to a broken one;
  * the CLI refuses unknown targets and bad arguments instead of guessing.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import ledger_store  # noqa: E402
import new_ledger_shard as nls  # noqa: E402
import validate_state as vs  # noqa: E402


class NameTest(unittest.TestCase):
    def test_every_target_is_a_validator_collection_or_the_snapshot(self):
        for name in vs.COLLECTIONS:
            self.assertIn(name, nls.TARGETS)
        self.assertIn(nls.SNAPSHOT_TARGET, nls.TARGETS)

    def test_generated_ledger_names_match_the_loader_pattern(self):
        for target in vs.COLLECTIONS:
            with self.subTest(target=target):
                for _ in range(20):
                    name = nls.shard_name(target, "20261021")
                    self.assertRegex(name, ledger_store.SHARD_NAME_RE)
                    self.assertTrue(name.startswith("2026-10-21-"))
                    self.assertTrue(name.endswith(".jsonl"))

    def test_generated_snapshot_names_match_the_loader_pattern(self):
        for _ in range(20):
            name = nls.shard_name(nls.SNAPSHOT_TARGET, "20261021")
            self.assertRegex(name, ledger_store.SNAPSHOT_SHARD_NAME_RE)
            self.assertTrue(name.endswith(".json"))

    def test_suffix_entropy_is_long_enough_to_avoid_same_day_collisions(self):
        names = {nls.shard_name("evidence", "20261021") for _ in range(200)}
        self.assertGreater(len(names), 190)
        for name in names:
            self.assertEqual(len(name.split("-", 3)[3].split(".")[0]), 12)

    def test_bad_day_is_rejected(self):
        for bad in ("2026-10-21", "2026102", "202610211", "abcdefgh"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                nls.shard_name("evidence", bad)


class CreateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "state").mkdir()
        (self.root / "tests" / "fixtures").mkdir(parents=True)
        (self.root / "state" / "evidence.jsonl").write_text("", encoding="utf-8")
        (self.root / "tests" / "fixtures" / "arxiv_metadata_snapshot.json").write_text(
            json.dumps({"captured_at": "2026-10-20", "entries": []}), encoding="utf-8"
        )
        patcher = mock.patch.object(nls, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_ledger_shard_creation_makes_dir_and_empty_file(self):
        result = nls.plan("evidence", "20261021", create=True)
        path: Path = result["path"]  # type: ignore[assignment]
        self.assertTrue(path.parent.is_dir())
        self.assertTrue(path.is_file())
        self.assertEqual(path.read_text(encoding="utf-8"), "")
        self.assertTrue(result["created"])
        records, errors = ledger_store.load_jsonl(self.root / "state" / "evidence.jsonl")
        self.assertEqual((records, errors), ([], []))

    def test_snapshot_part_is_a_loadable_document(self):
        result = nls.plan(nls.SNAPSHOT_TARGET, "20261021", create=True)
        path: Path = result["path"]  # type: ignore[assignment]
        document = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(document["schema"], nls.SNAPSHOT_PART_SCHEMA)
        self.assertEqual(document["entries"], [])
        self.assertEqual(document["captured_at"], "2026-10-21")
        entries, header = ledger_store.load_fixture(
            self.root / "tests" / "fixtures" / "arxiv_metadata_snapshot.json"
        )
        self.assertEqual(entries, {})
        self.assertEqual(header["captured_at"], "2026-10-20")

    def test_two_creations_do_not_collide(self):
        first = nls.plan("evidence", "20261021", create=True)["path"]
        second = nls.plan("evidence", "20261021", create=True)["path"]
        self.assertNotEqual(first, second)

    def test_stray_unread_file_is_reported_as_a_warning(self):
        directory = self.root / "state" / "evidence.d"
        directory.mkdir()
        stray = directory / "2026-10-21-ffffffffffff"
        stray.write_text('{"evidence_id": "EVD-20261021-aaaa"}\n', encoding="utf-8")
        result = nls.plan("evidence", "20261021", create=True)
        warnings = "\n".join(result["warnings"])  # type: ignore[arg-type]
        self.assertIn("NOT read by the loader", warnings)
        self.assertIn("2026-10-21-ffffffffffff", warnings)

    def test_notes_in_a_shard_directory_are_not_warnings(self):
        directory = self.root / "state" / "evidence.d"
        directory.mkdir()
        (directory / "README.md").write_text("how to add a shard\n", encoding="utf-8")
        self.assertEqual(nls.plan("evidence", "20261021", create=False)["warnings"], [])

    def test_missing_base_file_is_an_error(self):
        with self.assertRaises(FileNotFoundError):
            nls.plan("relations", "20261021", create=False)


class CliTest(unittest.TestCase):
    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = nls.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_list_prints_every_target(self):
        code, out, _ = self.run_main(["--list"])
        self.assertEqual(code, 0)
        for target in nls.TARGETS:
            self.assertIn(target, out)

    def test_print_mode_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "state").mkdir()
            (root / "state" / "evidence.jsonl").write_text("", encoding="utf-8")
            with mock.patch.object(nls, "ROOT", root):
                code, out, _ = self.run_main(["evidence", "--date", "20261021"])
                self.assertEqual(code, 0)
                self.assertTrue(out.strip().startswith("state/evidence.d/"))
                self.assertFalse((root / "state" / "evidence.d").exists())

    def test_unknown_target_exits_two(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                nls.main(["nope"])
        self.assertEqual(raised.exception.code, 2)

    def test_missing_target_exits_two(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                nls.main([])
        self.assertEqual(raised.exception.code, 2)

    def test_bad_date_exits_two(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                nls.main(["evidence", "--date", "2026-10-21"])
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
