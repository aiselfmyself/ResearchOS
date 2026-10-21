"""Tests for the relation ledger (state/relations.jsonl, schemas/relation.json).

The relation ledger is the SHELDON-style evidence relation
E_t : hypothesis x observation -> {support, refute, neutral, unresolved}
(contributions/2026-10-21_sheldon_reading.md section 5.1, backfill step 1-3,
section 5.7). This file pins the behaviour that the validator and the ID
tooling must have before any verdict is written into the ledger:

  * the empty ledger is valid;
  * a well-formed REL record is accepted;
  * broken references (hypothesis / observation / source) are rejected;
  * invalid verdicts and missing required fields are rejected;
  * REL IDs must use PREFIX-YYYYMMDD-xxxx; the sequential form REL-NNN is
    rejected because REL has no grandfathered range;
  * the optional fields added to evidence / hypothesis / claim (sections
    5.2, 5.3, 5.5) do not disturb existing records and are type-checked;
  * claim.hypothesis_ids, when present, must resolve to hypotheses;
  * new_id.py mints REL IDs, and REL references in memos are resolved by
    check_memo_ledger_refs.py (gate 7).

Like tests/test_minimal_core.py, the reference checks run on synthetic
in-memory data, and the end-to-end checks run on a temporary copy of the
repository whose state/ directory is replaced by a synthetic ledger. The
real state/ files are never written.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
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
import new_id  # noqa: E402
import validate_state as vs  # noqa: E402

GOOD_REL_ID = "REL-20261021-abcd"


def _schema(name: str) -> dict:
    return json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))


def _relation(**overrides) -> dict:
    record = {
        "relation_id": GOOD_REL_ID,
        "hypothesis_id": "HYP-001",
        "observation_id": "EVD-001",
        "verdict": "support",
        "provisional": False,
        "source_id": "SRC-001",
        "rationale": "合成テスト用の1行理由",
        "recorded_at": "2026-10-21",
    }
    record.update(overrides)
    return record


def _synthetic_data(**extra) -> dict:
    """Minimal in-memory ledger set with one of each referenced record."""
    data = {
        "sources": [{"source_id": "SRC-001"}],
        "evidence": [{"evidence_id": "EVD-001", "source_id": "SRC-001"}],
        "claims": [],
        "verifications": [],
        "hypotheses": [{"hypothesis_id": "HYP-001"}],
        "relations": [],
    }
    data.update(extra)
    return data


def _synthetic_root(tmp: str, relation_lines: list) -> Path:
    """Copy of the repo whose state/relations.jsonl holds ``relation_lines``.

    Everything except state/ is symlinked, so the path-existence checks see
    the real repository. The five real research ledgers are copied, so the
    reference checks see real SRC / EVD / HYP records.
    """
    root = Path(tmp) / "repo"
    root.mkdir()
    for entry in ROOT.iterdir():
        if entry.name in {"state", ".git"}:
            continue
        os.symlink(entry, root / entry.name)
    state = root / "state"
    state.mkdir()
    for _name, (ledger_rel, _schema, _id_key) in vs.COLLECTIONS.items():
        target = root / ledger_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / ledger_rel, target)
    shutil.copy(ROOT / vs.CYCLE_EXEMPTIONS, root / vs.CYCLE_EXEMPTIONS)
    (state / "relations.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in relation_lines),
        encoding="utf-8",
    )
    return root


class RelationLedgerFilesTest(unittest.TestCase):
    def test_relation_ledger_is_registered(self) -> None:
        self.assertIn("relations", vs.COLLECTIONS)
        ledger, schema, id_key = vs.COLLECTIONS["relations"]
        self.assertEqual(ledger, "state/relations.jsonl")
        self.assertEqual(schema, "schemas/relation.json")
        self.assertEqual(id_key, "relation_id")
        self.assertEqual(vs.ID_PREFIXES["relations"], "REL")

    def test_frozen_base_is_empty_and_the_union_is_valid(self) -> None:
        """The base stays empty; R4 wrote the verdicts into a shard.

        When this test was written the union was empty too ("until R4 writes
        verdicts"). R4 ran on 2026-10-21, so asserting an empty union would
        now pin a transient state instead of the rule: the frozen base is
        never appended to, and the union view is what must be valid.
        """
        path = ROOT / "state" / "relations.jsonl"
        self.assertTrue(path.exists(), "state/relations.jsonl must exist")
        self.assertEqual(path.read_bytes(), b"", "the frozen base must stay empty")
        records, errors = vs.load_jsonl(path)
        self.assertEqual(errors, [])
        self.assertGreater(len(records), 0, "R4 wrote the verdicts into a shard")
        for record in records:
            self.assertIn(record["verdict"], ("support", "refute", "neutral", "unresolved"))

    def test_real_repository_passes_with_the_relation_ledger(self) -> None:
        report = vs.run_all_checks(ROOT)
        self.assertEqual(report["errors"], [], msg="\n".join(report["errors"]))

    def test_relation_schema_declares_required_fields_and_verdict_enum(self) -> None:
        schema = _schema("relation.json")
        self.assertEqual(
            sorted(schema["required"]),
            sorted(["relation_id", "hypothesis_id", "observation_id", "verdict"]),
        )
        self.assertEqual(
            schema["properties"]["verdict"]["enum"],
            ["support", "refute", "neutral", "unresolved"],
        )
        self.assertEqual(schema["properties"]["provisional"]["type"], "boolean")


class RelationRecordTest(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = _schema("relation.json")

    def test_valid_relation_is_accepted(self) -> None:
        record = _relation()
        self.assertEqual(vs.validate_record(record, self.schema, "R"), [])
        self.assertEqual(
            vs.check_id_format([record], "relation_id", "relations.jsonl", "REL"),
            [],
        )
        self.assertEqual(vs.check_references(_synthetic_data(relations=[record])), [])

    def test_optional_fields_may_be_omitted(self) -> None:
        minimal = {
            "relation_id": GOOD_REL_ID,
            "hypothesis_id": "HYP-001",
            "observation_id": "EVD-001",
            "verdict": "unresolved",
        }
        self.assertEqual(vs.validate_record(minimal, self.schema, "R"), [])
        # source_id is optional, so its absence must not trigger a reference error.
        self.assertEqual(
            vs.check_references(_synthetic_data(relations=[minimal])), []
        )

    def test_missing_required_field_is_rejected(self) -> None:
        for field in ("relation_id", "hypothesis_id", "observation_id", "verdict"):
            record = _relation()
            del record[field]
            errors = vs.validate_record(record, self.schema, "R")
            self.assertTrue(any(field in e for e in errors), (field, errors))

    def test_invalid_verdict_is_rejected(self) -> None:
        # Verdicts of other ledgers ("falsified", "pass") and wrong case are not verdicts.
        for bad in ("banana", "Support", "falsified", "pass", ""):
            errors = vs.validate_record(_relation(verdict=bad), self.schema, "R")
            self.assertTrue(any("verdict" in e for e in errors), (bad, errors))

    def test_provisional_must_be_boolean(self) -> None:
        errors = vs.validate_record(_relation(provisional="yes"), self.schema, "R")
        self.assertTrue(any("provisional" in e for e in errors), errors)

    def test_dangling_hypothesis_reference_is_rejected(self) -> None:
        errors = vs.check_references(
            _synthetic_data(relations=[_relation(hypothesis_id="HYP-999")])
        )
        self.assertTrue(any("HYP-999" in e for e in errors), errors)

    def test_dangling_observation_reference_is_rejected(self) -> None:
        errors = vs.check_references(
            _synthetic_data(relations=[_relation(observation_id="EVD-999")])
        )
        self.assertTrue(any("EVD-999" in e for e in errors), errors)

    def test_dangling_source_reference_is_rejected(self) -> None:
        errors = vs.check_references(
            _synthetic_data(relations=[_relation(source_id="SRC-999")])
        )
        self.assertTrue(any("SRC-999" in e for e in errors), errors)

    def test_observation_id_resolves_to_evidence_not_claims(self) -> None:
        """observation_id points at the evidence ledger only (section 5.1)."""
        data = _synthetic_data(
            claims=[{"claim_id": "CLM-001"}],
            relations=[_relation(observation_id="CLM-001")],
        )
        errors = vs.check_references(data)
        self.assertTrue(any("CLM-001" in e for e in errors), errors)

    def test_relation_ids_are_checked_for_uniqueness(self) -> None:
        errors = vs.check_uniqueness(
            [_relation(), _relation()], "relation_id", "state/relations.jsonl"
        )
        self.assertTrue(any("duplicate" in e for e in errors), errors)


class RelationIdFormatTest(unittest.TestCase):
    def test_sequential_rel_id_is_rejected(self) -> None:
        """REL has no grandfathered range, so REL-001 is not accepted."""
        errors = vs.check_id_format(
            [{"relation_id": "REL-001"}], "relation_id", "relations.jsonl", "REL"
        )
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("REL-001", errors[0])
        self.assertIn("no grandfathered sequential range", errors[0])

    def test_rel_legacy_max_is_not_defined(self) -> None:
        self.assertNotIn("REL", vs.LEGACY_MAX)

    def test_sequential_rel_id_fails_the_whole_ledger_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _synthetic_root(tmp, [_relation(relation_id="REL-001")])
            report = vs.run_all_checks(root)
        self.assertTrue(
            any("REL-001" in e for e in report["errors"]), report["errors"]
        )

    def test_new_format_rel_id_passes_the_whole_ledger_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _synthetic_root(tmp, [_relation()])
            report = vs.run_all_checks(root)
        self.assertEqual(report["errors"], [], msg="\n".join(report["errors"]))

    def test_end_to_end_dangling_reference_fails_the_whole_ledger_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _synthetic_root(tmp, [_relation(hypothesis_id="HYP-999")])
            report = vs.run_all_checks(root)
        self.assertTrue(
            any("HYP-999" in e for e in report["errors"]), report["errors"]
        )

    def test_rel_token_in_prose_must_resolve(self) -> None:
        """ID_TOKEN_RE includes REL, so prose mentions are checked too."""
        data = _synthetic_data()
        data["evidence"][0]["interpretation"] = "REL-20261021-ffff に言及"
        errors = vs.check_cross_references(data, ROOT)
        self.assertTrue(any("REL-20261021-ffff" in e for e in errors), errors)


class OptionalFieldsTest(unittest.TestCase):
    """Sections 5.2, 5.3 and 5.5: optional fields must not break existing records."""

    def test_existing_records_remain_valid(self) -> None:
        for ledger, schema_name in (
            ("evidence", "evidence.json"),
            ("hypotheses", "hypothesis.json"),
            ("claims", "claim.json"),
        ):
            schema = _schema(schema_name)
            records, errors = vs.load_jsonl(ROOT / "state" / f"{ledger}.jsonl")
            self.assertEqual(errors, [])
            self.assertGreater(len(records), 0, ledger)
            for record in records:
                self.assertEqual(
                    vs.validate_record(record, schema, ledger), [], ledger
                )

    def test_new_optional_evidence_fields_are_accepted(self) -> None:
        schema = _schema("evidence.json")
        record = {
            "evidence_id": "EVD-001",
            "source_id": "SRC-001",
            "excerpt": "x",
            "interpretation": "y",
            "confidence": "high",
            "observation_key": "obs-0001",
            "observation_axis": "data sources",
            "observation_region": "SRC-001",
        }
        self.assertEqual(vs.validate_record(record, schema, "E"), [])
        bad = dict(record, observation_region=5)
        errors = vs.validate_record(bad, schema, "E")
        self.assertTrue(any("observation_region" in e for e in errors), errors)

    def test_new_optional_hypothesis_fields_are_accepted_and_separate_from_status(
        self,
    ) -> None:
        schema = _schema("hypothesis.json")
        record = {
            "hypothesis_id": "HYP-001",
            "statement": "s",
            "status": "supported",
            "hypothesis_region": "TASK.md §2-2",
            "search_status": "setaside",
            "cooldown_rounds": 3,
        }
        # status keeps its own enum; search_status is a second, independent field.
        self.assertEqual(vs.validate_record(record, schema, "H"), [])
        bad_search = dict(record, search_status="banana")
        self.assertTrue(
            any("search_status" in e for e in vs.validate_record(bad_search, schema, "H"))
        )
        bad_cooldown = dict(record, cooldown_rounds="3")
        self.assertTrue(
            any("cooldown_rounds" in e for e in vs.validate_record(bad_cooldown, schema, "H"))
        )
        # The old status enum is unchanged: search_status values are not statuses.
        bad_status = dict(record, status="retained")
        self.assertTrue(
            any("status" in e for e in vs.validate_record(bad_status, schema, "H"))
        )

    def test_existing_hypothesis_records_stay_valid_when_fields_are_added(self) -> None:
        schema = _schema("hypothesis.json")
        records, _ = vs.load_jsonl(ROOT / "state" / "hypotheses.jsonl")
        for record in records:
            extended = dict(
                record, hypothesis_region="x", search_status="retained", cooldown_rounds=3
            )
            self.assertEqual(vs.validate_record(extended, schema, "H"), [])

    def test_claim_hypothesis_ids_must_resolve_to_hypotheses(self) -> None:
        data = _synthetic_data(
            claims=[
                {
                    "claim_id": "CLM-001",
                    "evidence_ids": ["EVD-001"],
                    "hypothesis_ids": ["HYP-001"],
                }
            ]
        )
        self.assertEqual(vs.check_references(data), [])

        data["claims"][0]["hypothesis_ids"] = ["HYP-999"]
        errors = vs.check_references(data)
        self.assertTrue(any("HYP-999" in e for e in errors), errors)

    def test_claim_hypothesis_ids_do_not_accept_evidence_ids(self) -> None:
        data = _synthetic_data(
            claims=[{"claim_id": "CLM-001", "hypothesis_ids": ["EVD-001"]}]
        )
        errors = vs.check_references(data)
        self.assertTrue(any("EVD-001" in e for e in errors), errors)

    def test_claim_without_hypothesis_ids_is_unaffected(self) -> None:
        data = _synthetic_data(claims=[{"claim_id": "CLM-001", "evidence_ids": []}])
        self.assertEqual(vs.check_references(data), [])

    def test_claim_hypothesis_ids_type_is_checked(self) -> None:
        schema = _schema("claim.json")
        record = {
            "claim_id": "CLM-001",
            "statement": "s",
            "evidence_ids": [],
            "status": "candidate",
            "scope": "s",
            "hypothesis_ids": [1],
        }
        errors = vs.validate_record(record, schema, "C")
        self.assertTrue(any("hypothesis_ids" in e for e in errors), errors)


class RelationIdToolTest(unittest.TestCase):
    def test_mint_produces_rel_ids(self) -> None:
        rid = new_id.mint("REL", day="20261021")
        self.assertRegex(rid, r"^REL-20261021-[0-9a-f]{4}$")
        self.assertEqual(vs.ID_PATTERN.match(rid).group("prefix"), "REL")

    def test_cli_mints_unique_rel_ids_into_a_scratch_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "relations.jsonl"
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = new_id.main(
                    ["REL", "--count", "3", "--date", "20261021", "--ledger", str(ledger)]
                )
        self.assertEqual(code, 0)
        lines = buffer.getvalue().split()
        self.assertEqual(len(set(lines)), 3)
        for line in lines:
            self.assertRegex(line, r"^REL-20261021-[0-9a-f]{4}$")

    def test_new_id_reads_relation_key_from_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "relations.jsonl"
            ledger.write_text(json.dumps(_relation()) + "\n", encoding="utf-8")
            taken = new_id._existing_ids(ledger, new_id.ID_KEYS["REL"])
        self.assertEqual(taken, {GOOD_REL_ID})

    def test_rel_is_a_registered_prefix(self) -> None:
        self.assertEqual(new_id.PREFIXES["REL"], "state/relations.jsonl")
        self.assertEqual(new_id.ID_KEYS["REL"], "relation_id")


class MemoRelReferenceTest(unittest.TestCase):
    """Gate 7 (check_memo_ledger_refs.py) resolves REL references in memos."""

    def test_ledger_id_map_has_a_rel_bucket(self) -> None:
        ids = cm.load_ledger_ids()
        self.assertIn("REL", ids)
        # R4 wrote the verdicts on 2026-10-21; the bucket must hold exactly the
        # union view's relation IDs (not just the frozen base's, which is empty).
        records, errors = vs.load_jsonl(ROOT / "state" / "relations.jsonl")
        self.assertEqual(errors, [])
        self.assertEqual(ids["REL"], {r["relation_id"] for r in records})
        self.assertGreater(len(ids["REL"]), 0)

    def test_existing_rel_reference_resolves(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            memo = Path(tmp) / "memo.md"
            memo.write_text(f"関係 {GOOD_REL_ID} を参照する。", encoding="utf-8")
            dangling, archived, referenced = cm.scan(
                [memo], {"REL": {GOOD_REL_ID}}, set()
            )
        self.assertEqual(dangling, [])
        self.assertEqual(archived, [])
        self.assertEqual(referenced["REL"], {GOOD_REL_ID})

    def test_unresolved_rel_reference_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            memo = Path(tmp) / "memo.md"
            memo.write_text(f"関係 {GOOD_REL_ID} を参照。", encoding="utf-8")
            dangling, archived, _ = cm.scan([memo], {"REL": set()}, set())
        self.assertEqual(archived, [])
        self.assertEqual(dangling, [("memo.md", "id", GOOD_REL_ID)])

    def test_sequential_rel_reference_is_reported_as_dangling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            memo = Path(tmp) / "memo.md"
            memo.write_text("REL-001 を参照。", encoding="utf-8")
            dangling, _, _ = cm.scan([memo], {"REL": set()}, set())
        self.assertEqual(dangling, [("memo.md", "id", "REL-001")])

    def test_memo_gate_fails_on_unresolved_rel_with_empty_ledger(self) -> None:
        """With the empty ledger, any REL reference in a memo is dangling (exit 1)."""
        with tempfile.TemporaryDirectory() as tmp:
            memo = Path(tmp) / "memo.md"
            memo.write_text(f"{GOOD_REL_ID}\n", encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = cm.main(["--memos", str(memo)])
        self.assertEqual(code, 1, buf.getvalue())
        self.assertIn(GOOD_REL_ID, buf.getvalue())


if __name__ == "__main__":
    unittest.main()
