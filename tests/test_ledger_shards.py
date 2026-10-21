"""Regression tests for the 2026-10-21 ledger sharding migration (method B).

The migration (contributions/2026-10-21_ledger_sharding_migration.md, design in
contributions/2026-10-21_ledger_sharding_design.md) keeps every existing
`state/*.jsonl` and `tests/fixtures/arxiv_metadata_snapshot.json` as a **frozen
base** and puts new records in per-session shard files:

    state/<name>.d/YYYY-MM-DD-<12 hex>.jsonl
    tests/fixtures/arxiv_metadata_snapshot.d/YYYY-MM-DD-<12 hex>.json

`scripts/ledger_store.py` is the single reader for that layout. These tests pin
the properties the migration promised:

  * the union view preserves every base record, in order, unchanged;
  * a record that exists only in a shard is read, validated, counted, minted
    against, and resolved by the memo checker;
  * a duplicate ID is an error **even when the contents are identical**, and
    the message names both origins (never silently pick a winner);
  * a malformed shard or a shard with a non-conforming filename is reported,
    never skipped silently;
  * the snapshot's base header is not overwritten by a part;
  * a duplicate arXiv ID across parts is rejected.

The synthetic cases run on a temporary copy of the repository built from
symlinks, following tests/test_relations.py: the real `state/` is never written.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Dict, Optional
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import check_citations as cc  # noqa: E402
import check_doc_numbers as cdn  # noqa: E402
import check_memo_ledger_refs as cml  # noqa: E402
import ledger_store  # noqa: E402
import new_id  # noqa: E402
import validate_state as vs  # noqa: E402

LEDGERS = ("sources", "evidence", "claims", "verifications", "hypotheses", "relations")
SHARD_NAME = "2026-10-21-3f9ac21b7d40.jsonl"
SNAPSHOT_SHARD_NAME = "2026-10-21-3f9ac21b7d40.json"
FIXTURE = ROOT / "tests" / "fixtures" / "arxiv_metadata_snapshot.json"


def _evidence(evidence_id: str = "EVD-20261021-abc1", source_id: str = "SRC-001") -> dict:
    return {
        "evidence_id": evidence_id,
        "source_id": source_id,
        "excerpt": "quoted text",
        "interpretation": "reading",
        "confidence": "high",
    }


def _jsonl(*records: dict) -> str:
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)


def _temp_repo(tmp: Path, shards: Optional[Dict[str, str]] = None) -> Path:
    """Copy of the repo with a writable state/ and optional shard files.

    Everything except state/ and .git is symlinked, so path-existence checks
    see the real repository. All six ledgers are copied from the real repo so
    reference checks see real SRC / EVD / HYP records.
    """
    root = tmp / "repo"
    root.mkdir()
    for entry in ROOT.iterdir():
        if entry.name in {"state", ".git"}:
            continue
        os.symlink(entry, root / entry.name)
    state = root / "state"
    state.mkdir()
    for ledger in LEDGERS:
        shutil.copy(ROOT / "state" / f"{ledger}.jsonl", state / f"{ledger}.jsonl")
    for rel, content in (shards or {}).items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


class ShardLayoutTest(unittest.TestCase):
    def test_shard_directory_is_sibling_of_base_file(self):
        self.assertEqual(
            ledger_store.shard_dir(Path("state/evidence.jsonl")), Path("state/evidence.d")
        )
        self.assertEqual(
            ledger_store.shard_dir(Path("tests/fixtures/arxiv_metadata_snapshot.json")),
            Path("tests/fixtures/arxiv_metadata_snapshot.d"),
        )

    def test_documented_shard_names_are_accepted(self):
        self.assertTrue(ledger_store.SHARD_NAME_RE.match(SHARD_NAME))
        self.assertTrue(ledger_store.SNAPSHOT_SHARD_NAME_RE.match(SNAPSHOT_SHARD_NAME))

    def test_nonconforming_names_are_rejected(self):
        """A date-only name collides across same-day sessions; short entropy too."""
        bad = (
            "2026-10-21.jsonl",             # no entropy at all
            "2026-10-21-abc.jsonl",         # too few hex characters
            "2026-10-21-3F9AC21B7D40.jsonl",  # uppercase hex
            "20261021-3f9ac21b7d40.jsonl",  # wrong date format
            "2026-10-21-3f9ac21b7d40.json",  # snapshot part inside a ledger dir
        )
        for name in bad:
            with self.subTest(name=name):
                self.assertFalse(ledger_store.SHARD_NAME_RE.match(name))

    def test_hidden_and_unrelated_files_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "evidence.jsonl"
            base.write_text(_jsonl(_evidence()), encoding="utf-8")
            shard_dir = Path(tmp) / "evidence.d"
            shard_dir.mkdir()
            (shard_dir / ".editor.jsonl").write_text(_jsonl(_evidence("EVD-20261021-aaaa")), encoding="utf-8")
            (shard_dir / "notes.txt").write_text("not a ledger\n", encoding="utf-8")
            records, errors, _ = ledger_store.load_ledger(base)
            self.assertEqual([r["evidence_id"] for r in records], ["EVD-20261021-abc1"])
            self.assertEqual(errors, [])

    def test_missing_shard_directory_means_no_shards(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "evidence.jsonl"
            base.write_text(_jsonl(_evidence()), encoding="utf-8")
            self.assertEqual(ledger_store.shard_files(base, ".jsonl"), [])
            self.assertEqual(len(ledger_store.load_jsonl(base)[0]), 1)


class UnionViewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.base = self.dir / "evidence.jsonl"
        self.base.write_text(_jsonl(_evidence()), encoding="utf-8")

    def _shard(self, name: str, text: str) -> Path:
        directory = self.dir / "evidence.d"
        directory.mkdir(exist_ok=True)
        path = directory / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_base_only_view_matches_the_raw_file(self):
        raw, raw_errors, _ = ledger_store.read_jsonl_file(self.base)
        union, errors, origins = ledger_store.load_ledger(self.base)
        self.assertEqual(raw_errors, [])
        self.assertEqual(errors, [])
        self.assertEqual(union, raw)
        self.assertEqual(origins, [f"{self.base}:1"])

    def test_shard_records_follow_the_base_in_filename_order(self):
        later = "2026-10-21-ffffffffffff.jsonl"
        earlier = "2026-10-21-00000000000a.jsonl"
        self._shard(later, _jsonl(_evidence("EVD-20261021-cccc")))
        self._shard(earlier, _jsonl(_evidence("EVD-20261021-bbbb")))
        records, errors, _ = ledger_store.load_ledger(self.base)
        self.assertEqual(errors, [])
        self.assertEqual(
            [r["evidence_id"] for r in records],
            ["EVD-20261021-abc1", "EVD-20261021-bbbb", "EVD-20261021-cccc"],
        )

    def test_empty_shard_contributes_nothing(self):
        self._shard(SHARD_NAME, "")
        records, errors, _ = ledger_store.load_ledger(self.base)
        self.assertEqual(errors, [])
        self.assertEqual(len(records), 1)

    def test_invalid_shard_json_reports_path_and_line(self):
        shard = self._shard(SHARD_NAME, '{"evidence_id": "EVD-20261021-dddd"}\n{broken\n')
        records, errors, _ = ledger_store.load_ledger(self.base)
        self.assertEqual(len(records), 2)  # the valid line is not lost
        self.assertTrue(any(f"{shard}:2" in e and "invalid JSON" in e for e in errors), errors)

    def test_non_object_line_in_shard_is_reported(self):
        shard = self._shard(SHARD_NAME, "[1, 2, 3]\n")
        _records, errors, _ = ledger_store.load_ledger(self.base)
        self.assertTrue(any(f"{shard}:1" in e and "not a JSON object" in e for e in errors), errors)

    def test_bad_shard_name_is_reported_but_records_are_still_read(self):
        """Never lose a record because its filename is wrong."""
        shard = self._shard("2026-10-21.jsonl", _jsonl(_evidence("EVD-20261021-eeee")))
        records, errors, _ = ledger_store.load_ledger(self.base)
        self.assertIn("EVD-20261021-eeee", [r["evidence_id"] for r in records])
        self.assertTrue(any(str(shard) in e and "does not match" in e for e in errors), errors)

    def test_date_named_file_without_shard_suffix_is_reported(self):
        """A shard misspelt without `.jsonl` must not vanish silently."""
        shard = self._shard("2026-10-21-ffffffffffff", _jsonl(_evidence("EVD-20261021-ffff")))
        records, errors, _ = ledger_store.load_ledger(self.base)
        self.assertNotIn("EVD-20261021-ffff", [r["evidence_id"] for r in records])
        self.assertTrue(any(str(shard) in e and "NOT in the view" in e for e in errors), errors)

    def test_notes_in_a_shard_directory_are_not_reported(self):
        directory = self.dir / "evidence.d"
        directory.mkdir()
        (directory / "README.md").write_text("how to add a shard\n", encoding="utf-8")
        records, errors, _ = ledger_store.load_ledger(self.base)
        self.assertEqual(errors, [])
        self.assertEqual(len(records), 1)

    def test_missing_base_file_is_reported(self):
        missing = self.dir / "absent.jsonl"
        records, errors, _ = ledger_store.load_ledger(missing)
        self.assertEqual(records, [])
        self.assertTrue(any("file not found" in e for e in errors), errors)

    def test_duplicate_ids_report_both_origins(self):
        shard = self._shard(SHARD_NAME, _jsonl(_evidence()))
        records, _errors, origins = ledger_store.load_ledger(self.base)
        duplicates = ledger_store.duplicate_ids(records, origins, "evidence_id")
        self.assertEqual(len(duplicates), 1)
        self.assertIn(str(self.base), duplicates[0])
        self.assertIn(str(shard), duplicates[0])


class ValidatorIntegrationTest(unittest.TestCase):
    """validate_state must treat base + shards as one ledger."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_baseline_copy_is_valid(self):
        """Guards the other tests: a clean copy passes before any shard exists."""
        root = _temp_repo(Path(self.tmp.name))
        self.assertEqual(vs.run_all_checks(root)["errors"], [])

    def test_record_that_lives_only_in_a_shard_is_validated(self):
        root = _temp_repo(
            Path(self.tmp.name),
            {f"state/evidence.d/{SHARD_NAME}": _jsonl(_evidence())},
        )
        self.assertEqual(vs.run_all_checks(root)["errors"], [])
        records, errors, _ = ledger_store.load_ledger(root / "state" / "evidence.jsonl")
        self.assertEqual(errors, [])
        self.assertIn("EVD-20261021-abc1", [r["evidence_id"] for r in records])

    def test_duplicate_across_base_and_shard_names_both_origins(self):
        base_record = _evidence("EVD-001")
        root = _temp_repo(
            Path(self.tmp.name),
            {f"state/evidence.d/{SHARD_NAME}": _jsonl(base_record)},
        )
        errors = vs.run_all_checks(root)["errors"]
        duplicates = [e for e in errors if "duplicate evidence_id" in e]
        self.assertEqual(len(duplicates), 1, errors)
        self.assertIn("state/evidence.jsonl", duplicates[0])
        self.assertIn("state/evidence.d", duplicates[0])

    def test_identical_duplicate_across_two_shards_is_still_an_error(self):
        """Same content is not a reason to pick one silently (S1 section 1)."""
        payload = _jsonl(_evidence("EVD-20261021-abc1"))
        root = _temp_repo(
            Path(self.tmp.name),
            {
                f"state/evidence.d/{SHARD_NAME}": payload,
                "state/evidence.d/2026-10-21-0000000000ff.jsonl": payload,
            },
        )
        errors = vs.run_all_checks(root)["errors"]
        self.assertTrue(any("duplicate evidence_id" in e for e in errors), errors)

    def test_dangling_reference_inside_a_shard_is_caught(self):
        root = _temp_repo(
            Path(self.tmp.name),
            {f"state/evidence.d/{SHARD_NAME}": _jsonl(_evidence(source_id="SRC-999"))},
        )
        errors = vs.run_all_checks(root)["errors"]
        self.assertTrue(any("unknown source_id 'SRC-999'" in e for e in errors), errors)

    def test_id_format_is_enforced_inside_shards(self):
        root = _temp_repo(
            Path(self.tmp.name),
            {f"state/evidence.d/{SHARD_NAME}": _jsonl(_evidence("EVD-015"))},
        )
        errors = vs.run_all_checks(root)["errors"]
        self.assertTrue(any("frozen sequential range" in e for e in errors), errors)

    def test_counts_and_view_include_shards(self):
        root = _temp_repo(
            Path(self.tmp.name),
            {f"state/evidence.d/{SHARD_NAME}": _jsonl(_evidence())},
        )
        base_count = len(vs.load_jsonl(root / "state" / "evidence.jsonl")[0])
        self.assertEqual(base_count, 86 + 1)


class ReaderIntegrationTest(unittest.TestCase):
    """Every reader named in the S1 migration steps must see shards."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_doc_number_counts_include_shards(self):
        root = _temp_repo(
            Path(self.tmp.name),
            {f"state/evidence.d/{SHARD_NAME}": _jsonl(_evidence())},
        )
        with mock.patch.object(cdn, "STATE_DIR", root / "state"):
            counts = cdn.actual_ledger_counts()
        self.assertEqual(counts["evidence"], 87)

    def test_new_id_sees_ids_that_exist_only_in_shards(self):
        root = _temp_repo(
            Path(self.tmp.name),
            {f"state/evidence.d/{SHARD_NAME}": _jsonl(_evidence("EVD-20261021-cafe"))},
        )
        existing = new_id._existing_ids(root / "state" / "evidence.jsonl", "evidence_id")
        self.assertIn("EVD-20261021-cafe", existing)
        self.assertNotIn(new_id.mint("EVD", day="20261021", taken=existing), existing)

    def test_memo_ledger_refs_resolves_shard_ids(self):
        root = _temp_repo(
            Path(self.tmp.name),
            {f"state/hypotheses.d/{SHARD_NAME}": _jsonl({"hypothesis_id": "HYP-001"})},
        )
        with mock.patch.object(cml, "ROOT", root):
            ids = cml.load_ledger_ids()
        self.assertIn("HYP-001", ids["HYP"])

    def test_citation_check_reads_sources_shards(self):
        source = {
            "source_id": "SRC-20261021-abc1",
            "title": "Synthetic title",
            "authors": ["A. Author"],
            "year": 2026,
            "url": "https://arxiv.org/abs/2601.00001",
        }
        root = _temp_repo(
            Path(self.tmp.name),
            {f"state/sources.d/{SHARD_NAME}": _jsonl(source)},
        )
        records = cc.load_ledger(root / "state" / "sources.jsonl")
        self.assertIn("SRC-20261021-abc1", [r["source_id"] for r in records])

    def test_citation_check_rejects_duplicate_source_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "sources.jsonl"
            record = {"source_id": "SRC-001", "url": "https://arxiv.org/abs/2601.00001"}
            base.write_text(_jsonl(record), encoding="utf-8")
            shard_dir = Path(tmp) / "sources.d"
            shard_dir.mkdir()
            (shard_dir / SHARD_NAME).write_text(_jsonl(record), encoding="utf-8")
            with self.assertRaises(ValueError) as raised:
                cc.load_ledger(base)
            self.assertIn("duplicate source_id", str(raised.exception))


class SnapshotShardTest(unittest.TestCase):
    """The citation snapshot follows the same base + parts rule."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.base = self.dir / "snapshot.json"
        self.base.write_text(
            json.dumps(
                {
                    "schema": "researchos/arxiv-metadata-snapshot/v1",
                    "captured_at": "2026-10-20",
                    "capture_note": "base note",
                    "entries": [
                        {
                            "arxiv_id": "2601.00001",
                            "title": "Base",
                            "authors": ["A"],
                            "published": "2026-01-01",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def _part(self, name: str, entries, **header) -> Path:
        directory = self.dir / "snapshot.d"
        directory.mkdir(exist_ok=True)
        document = dict(header)
        document["entries"] = entries
        path = directory / name
        path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        return path

    def test_parts_are_merged_by_arxiv_id(self):
        self._part(
            SNAPSHOT_SHARD_NAME,
            [{"arxiv_id": "2601.00002", "title": "Part", "authors": ["B"], "published": "2026-02-02"}],
            capture_note="part note",
        )
        entries, header, _origins, part_headers = ledger_store.load_snapshot(self.base)
        self.assertEqual(sorted(entries), ["2601.00001", "2601.00002"])
        self.assertEqual(header["captured_at"], "2026-10-20")
        self.assertEqual(len(part_headers), 1)
        self.assertIn("part note", json.dumps(part_headers, ensure_ascii=False))

    def test_base_header_is_not_overwritten_by_a_part(self):
        self._part(
            SNAPSHOT_SHARD_NAME,
            [{"arxiv_id": "2601.00002", "title": "Part", "authors": ["B"], "published": "2026-02-02"}],
            captured_at="2026-12-31",
            capture_note="newer",
        )
        entries, header = ledger_store.load_fixture(self.base)
        self.assertEqual(header["captured_at"], "2026-10-20")
        self.assertEqual(header["capture_note"], "base note")
        self.assertIn("2601.00002", entries)

    def test_duplicate_arxiv_id_across_base_and_part_is_rejected(self):
        self._part(
            SNAPSHOT_SHARD_NAME,
            [{"arxiv_id": "2601.00001", "title": "Same ID", "authors": ["A"], "published": "2026-01-01"}],
        )
        with self.assertRaises(ValueError) as raised:
            ledger_store.load_fixture(self.base)
        message = str(raised.exception)
        self.assertIn("duplicate arxiv_id '2601.00001'", message)
        self.assertIn(str(self.base), message)
        self.assertIn("snapshot.d", message)

    def test_duplicate_arxiv_id_inside_two_parts_is_rejected(self):
        entry = {"arxiv_id": "2601.00002", "title": "Part", "authors": ["B"], "published": "2026-02-02"}
        self._part(SNAPSHOT_SHARD_NAME, [entry])
        self._part("2026-10-21-0123456789ab.json", [entry])
        with self.assertRaises(ValueError) as raised:
            ledger_store.load_fixture(self.base)
        self.assertIn("duplicate arxiv_id", str(raised.exception))

    def test_part_with_bad_name_is_rejected(self):
        self._part(
            "2026-10-21.json",
            [{"arxiv_id": "2601.00002", "title": "Part", "authors": ["B"], "published": "2026-02-02"}],
        )
        with self.assertRaises(ValueError) as raised:
            ledger_store.load_fixture(self.base)
        self.assertIn("does not match", str(raised.exception))

    def test_part_with_bad_suffix_is_rejected(self):
        directory = self.dir / "snapshot.d"
        directory.mkdir()
        (directory / "2026-10-21-3f9ac21b7d40.jsonl").write_text(
            json.dumps({"entries": []}), encoding="utf-8"
        )
        with self.assertRaises(ValueError) as raised:
            ledger_store.load_fixture(self.base)
        self.assertIn("NOT in the view", str(raised.exception))

    def test_part_without_entries_list_is_rejected(self):
        directory = self.dir / "snapshot.d"
        directory.mkdir()
        (directory / SNAPSHOT_SHARD_NAME).write_text('{"entries": {}}', encoding="utf-8")
        with self.assertRaises(ValueError) as raised:
            ledger_store.load_fixture(self.base)
        self.assertIn("'entries' must be a list", str(raised.exception))

    def test_citation_checker_loader_sees_part_entries(self):
        self._part(
            SNAPSHOT_SHARD_NAME,
            [{"arxiv_id": "2601.00002", "title": "Part", "authors": ["B"], "published": "2026-02-02"}],
        )
        entries, _header = cc.load_fixture(self.base)
        self.assertIn("2601.00002", entries)

    def test_real_snapshot_has_unique_arxiv_ids(self):
        """The bundled base must stay duplicate-free after the migration."""
        entries, header = cc.load_fixture(FIXTURE)
        self.assertGreater(len(entries), 0)
        self.assertIn("captured_at", header)
        documents = [json.loads(FIXTURE.read_text(encoding="utf-8"))]
        for part in ledger_store.shard_files(FIXTURE, ".json"):
            documents.append(json.loads(part.read_text(encoding="utf-8")))
        seen = []
        for document in documents:
            seen.extend(entry["arxiv_id"] for entry in document["entries"])
        self.assertEqual(len(seen), len(set(seen)))


class BundledLedgerTest(unittest.TestCase):
    """The real repository after the migration: no record lost, none reordered."""

    def test_base_records_are_unchanged_and_come_first(self):
        for name, (ledger_rel, _schema, _id_key) in vs.COLLECTIONS.items():
            with self.subTest(ledger=name):
                base = ROOT / ledger_rel
                raw, raw_errors, _ = ledger_store.read_jsonl_file(base)
                union, errors, _ = ledger_store.load_ledger(base)
                self.assertEqual(raw_errors, [], f"{ledger_rel}: base unreadable")
                self.assertEqual(errors, [], f"{ledger_rel}: shard problems")
                self.assertEqual(union[: len(raw)], raw)
                if name != "relations":
                    # relations.jsonl is legitimately empty until the R3/R4
                    # backfill writes the first verdicts.
                    self.assertGreater(len(raw), 0, ledger_rel)

    def test_every_ledger_view_is_valid(self):
        self.assertEqual(vs.run_all_checks(ROOT)["errors"], [])

    def test_no_shard_is_present_that_the_loader_would_ignore(self):
        for ledger_rel in (rel for rel, _s, _k in vs.COLLECTIONS.values()):
            base = ROOT / ledger_rel
            directory = ledger_store.shard_dir(base)
            if not directory.is_dir():
                continue
            for path in directory.iterdir():
                if path.is_file() and not path.name.startswith("."):
                    with self.subTest(path=str(path)):
                        self.assertTrue(
                            ledger_store.SHARD_NAME_RE.match(path.name),
                            f"{path} would be read but does not follow the convention",
                        )


if __name__ == "__main__":
    unittest.main()
