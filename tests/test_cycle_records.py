"""Regression tests for the 2026-10-21 hypothesis-cycle gates (Phase 1).

Phase 1 of docs/2026-10-21_hypothesis-cycle-automation.md adds the record
provenance that a loop needs when controlled experiments are out of scope:

  * `state/search_log.jsonl`  (QRY) -- which searches were actually run;
  * `state/runs.jsonl`        (RUN) -- what a round cost and how much of it
                                       needed a human;
  * `state/predictions.jsonl` (PRD) -- what was predicted before the
                                       observation existed.

and three gates on top of them. The gates are about *recorded provenance*, not
about quality:

  * a source in a new file must name its QRY, and the QRY must list it back;
  * a hypothesis in a new file must declare `round`,
    `derived_from_evidence_ids`, `refutation_condition` and the two
    next_* lists (split on 2026-10-21: one undifferentiated list held no
    searchable question);
  * a relation in a new file must declare `derived_from` and
    `searched_refutation`, and `derived_from=true` must agree with the
    hypothesis's own list.

Exemption is by *origin file* (state/cycle_exemptions.json), because a shard is
immutable: "not in a known file" is exactly "new record". The tests below pin
that the legacy files stay exempt and that a new shard is not.
"""
from __future__ import annotations

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

import check_doc_numbers as cdn  # noqa: E402
import new_id  # noqa: E402
import new_ledger_shard as nls  # noqa: E402
import validate_state as vs  # noqa: E402

NEW_SHARD = "state/evidence.d/2026-10-21-abcdef123456.jsonl"
QUERY = "QRY-20261021-bbbb"
SOURCE = "SRC-20261021-aaaa"
EVIDENCE = "EVD-20261021-dddd"
HYPOTHESIS = "HYP-20261021-cccc"
RELATION = "REL-20261021-eeee"


def _query(**overrides) -> dict:
    record = {
        "query_id": QUERY,
        "query": "long-horizon agent harness variance",
        "executed_at": "2026-10-21",
        "channel": "keyword",
        "hits": 4,
        "included_source_ids": [SOURCE],
    }
    record.update(overrides)
    return record


def _source(**overrides) -> dict:
    record = {
        "source_id": SOURCE,
        "title": "Synthetic source",
        "authors": ["A. Author"],
        "year": 2026,
        "url": "https://arxiv.org/abs/2601.00001",
        "type": "preprint",
        "query_id": QUERY,
    }
    record.update(overrides)
    return record


def _evidence(**overrides) -> dict:
    record = {
        "evidence_id": EVIDENCE,
        "source_id": SOURCE,
        "excerpt": "quoted text",
        "interpretation": "reading",
        "confidence": "high",
    }
    record.update(overrides)
    return record


def _hypothesis(**overrides) -> dict:
    record = {
        "hypothesis_id": HYPOTHESIS,
        "statement": "Synthetic hypothesis",
        "status": "proposed",
        "round": 1,
        "derived_from_evidence_ids": [EVIDENCE],
        "refutation_condition": {
            "observable": "an orthogonal model x harness run",
            "would_refute": "no ranking reversal at R < 1",
            "expected_if_true": "ranking reversal at R < 1",
        },
        "next_literature_questions": [
            "a third benchmark with a known model gap"
        ],
        "next_internal_measurements": [],
    }
    record.update(overrides)
    return record


def _relation(**overrides) -> dict:
    record = {
        "relation_id": RELATION,
        "hypothesis_id": HYPOTHESIS,
        "observation_id": EVIDENCE,
        "verdict": "support",
        "derived_from": False,
        "searched_refutation": True,
    }
    record.update(overrides)
    return record


def _data(**overrides) -> dict:
    """One of every record a compliant new-file entry needs."""
    data = {
        "sources": [_source()],
        "evidence": [_evidence()],
        "claims": [],
        "verifications": [],
        "hypotheses": [_hypothesis()],
        "relations": [_relation()],
        "search_log": [_query()],
        "runs": [],
        "predictions": [],
    }
    data.update(overrides)
    return data


def _check(data: dict, origins=None, exempt=frozenset(), root: Path = ROOT,
           pre_split=frozenset()):
    """Run only the cycle gates. No origins means 'every file is new'."""
    return vs.check_cycle_fields(
        data, origins or {}, set(exempt), root, set(pre_split)
    )


def _exempt_origins(*names: str) -> dict:
    return {name: [f"state/{name}.jsonl:1"] for name in names}


class RegistrationTest(unittest.TestCase):
    def test_cycle_ledgers_are_registered(self) -> None:
        for name, prefix, id_key in (
            ("search_log", "QRY", "query_id"),
            ("runs", "RUN", "run_id"),
            ("predictions", "PRD", "prediction_id"),
        ):
            with self.subTest(name=name):
                self.assertIn(name, vs.COLLECTIONS)
                self.assertEqual(vs.COLLECTIONS[name][2], id_key)
                self.assertEqual(vs.ID_PREFIXES[name], prefix)

    def test_cycle_ledgers_have_no_legacy_sequential_range(self) -> None:
        for prefix in ("QRY", "RUN", "PRD"):
            self.assertNotIn(prefix, vs.LEGACY_MAX)

    def test_id_tool_mints_cycle_ids(self) -> None:
        for prefix in ("QRY", "RUN", "PRD"):
            with self.subTest(prefix=prefix):
                self.assertRegex(
                    new_id.mint(prefix, day="20261021"),
                    rf"^{prefix}-20261021-[0-9a-f]{{4}}$",
                )

    def test_shard_tool_knows_the_cycle_ledgers(self) -> None:
        for name in ("search_log", "runs", "predictions"):
            self.assertIn(name, nls.TARGETS)

    def test_doc_number_checker_counts_them(self) -> None:
        for name in ("search_log", "runs", "predictions"):
            self.assertIn(name, cdn.LEDGERS)

    def test_cycle_ledgers_start_empty_or_valid(self) -> None:
        """An empty ledger is the correct initial state, not a failure."""
        for rel in ("state/search_log.jsonl", "state/runs.jsonl",
                    "state/predictions.jsonl"):
            records, errors = vs.load_jsonl(ROOT / rel)
            self.assertEqual(errors, [], msg="\n".join(errors))
            self.assertIsInstance(records, list)


class SearchChannelTest(unittest.TestCase):
    """Round 1 found that a known-item lookup had no honest channel."""

    def test_known_item_is_modelled(self) -> None:
        schema = json.loads((ROOT / "schemas" / "search_log.json").read_text(encoding="utf-8"))
        channels = schema["properties"]["channel"]["enum"]
        for channel in ("keyword", "citation", "review", "known_item", "manual"):
            with self.subTest(channel=channel):
                self.assertIn(channel, channels)

    def test_unknown_channel_is_rejected_by_the_schema(self) -> None:
        schema = json.loads((ROOT / "schemas" / "search_log.json").read_text(encoding="utf-8"))
        record = _query(channel="browsing")
        errors = vs.validate_record(record, schema, "ResearchOS Search Log Entry")
        self.assertTrue(any("not in" in e for e in errors), errors)

    def test_round_one_records_are_valid(self) -> None:
        """The first real round must stay loadable: two searches, one hypothesis."""
        records, errors = vs.load_jsonl(ROOT / "state" / "search_log.jsonl")
        self.assertEqual(errors, [], msg="\n".join(errors))
        channels = {r.get("channel") for r in records}
        self.assertIn("known_item", channels)


class ExemptionFileTest(unittest.TestCase):
    def test_real_exemptions_resolve(self) -> None:
        exempt, pre_split, errors = vs.load_cycle_exemptions(
            ROOT / vs.CYCLE_EXEMPTIONS
        )
        self.assertEqual(errors, [])
        self.assertIn("state/sources.jsonl", exempt)
        self.assertIn("state/hypotheses.d/2026-10-21-3990b64b4fdb.jsonl", exempt)
        self.assertIn(
            "state/hypotheses.d/2026-10-21-00a42038e2b6.jsonl", pre_split
        )

    def test_missing_file_is_an_error(self) -> None:
        """Fail closed: without it legacy and new records cannot be told apart."""
        with tempfile.TemporaryDirectory() as tmp:
            exempt, pre_split, errors = vs.load_cycle_exemptions(
                Path(tmp) / "absent.json"
            )
        self.assertEqual(exempt, set())
        self.assertEqual(pre_split, set())
        self.assertTrue(any("file not found" in e for e in errors), errors)

    def test_malformed_list_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text(json.dumps({"legacy_files": "state/sources.jsonl"}),
                            encoding="utf-8")
            exempt, pre_split, errors = vs.load_cycle_exemptions(path)
        self.assertEqual(exempt, set())
        self.assertTrue(any("list of strings" in e for e in errors), errors)

    def test_pre_split_and_legacy_must_not_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text(
                json.dumps({
                    "legacy_files": ["state/sources.jsonl"],
                    "pre_split_files": ["state/sources.jsonl"],
                }),
                encoding="utf-8",
            )
            _exempt, _pre, errors = vs.load_cycle_exemptions(path)
        self.assertTrue(any("appear in both" in e for e in errors), errors)

    def test_origin_line_suffix_is_stripped(self) -> None:
        origin = str(ROOT / "state" / "sources.jsonl") + ":12"
        self.assertEqual(vs.relative_origin(origin, ROOT), "state/sources.jsonl")


class SourceProvenanceTest(unittest.TestCase):
    def test_compliant_source_passes(self) -> None:
        self.assertEqual(_check(_data()), [])

    def test_missing_query_id_is_rejected(self) -> None:
        record = _source()
        del record["query_id"]
        errors = _check(_data(sources=[record]))
        self.assertTrue(any("missing query_id" in e for e in errors), errors)

    def test_unknown_query_id_is_rejected(self) -> None:
        errors = _check(_data(sources=[_source(query_id="QRY-20261021-9999")]))
        self.assertTrue(any("unknown query_id" in e for e in errors), errors)

    def test_query_must_list_the_source_back(self) -> None:
        errors = _check(_data(search_log=[_query(included_source_ids=[])]))
        self.assertTrue(any("does not list it" in e for e in errors), errors)

    def test_legacy_file_stays_exempt(self) -> None:
        record = {"source_id": "SRC-001", "title": "old"}
        errors = _check(
            _data(sources=[record], search_log=[]),
            origins=_exempt_origins("sources"),
            exempt={"state/sources.jsonl"},
        )
        self.assertEqual(errors, [])

    def test_new_shard_is_not_exempt(self) -> None:
        errors = _check(
            _data(sources=[{"source_id": SOURCE, "title": "new"}]),
            origins={"sources": [NEW_SHARD + ":1"]},
        )
        self.assertTrue(any("missing query_id" in e for e in errors), errors)


class HypothesisProvenanceTest(unittest.TestCase):
    def test_missing_round_is_rejected(self) -> None:
        record = _hypothesis()
        del record["round"]
        errors = _check(_data(hypotheses=[record]))
        self.assertTrue(any("'round'" in e for e in errors), errors)

    def test_round_zero_is_rejected(self) -> None:
        errors = _check(_data(hypotheses=[_hypothesis(round=0)]))
        self.assertTrue(any("'round'" in e for e in errors), errors)

    def test_missing_derived_ids_is_rejected(self) -> None:
        record = _hypothesis()
        del record["derived_from_evidence_ids"]
        errors = _check(_data(hypotheses=[record]))
        self.assertTrue(
            any("missing 'derived_from_evidence_ids'" in e for e in errors), errors
        )

    def test_unknown_derived_id_is_rejected(self) -> None:
        errors = _check(
            _data(hypotheses=[_hypothesis(derived_from_evidence_ids=["EVD-20261021-0000"])])
        )
        self.assertTrue(any("unknown derived_from evidence_id" in e for e in errors), errors)

    def test_empty_derived_list_is_allowed(self) -> None:
        """An imported hypothesis has no local generation inputs; that is a
        measurable state ('undeclared'), reported by the instrument in Phase 3,
        not a schema error here."""
        errors = _check(_data(hypotheses=[_hypothesis(derived_from_evidence_ids=[])]))
        self.assertEqual(errors, [])

    def test_missing_refutation_condition_is_rejected(self) -> None:
        record = _hypothesis()
        del record["refutation_condition"]
        errors = _check(_data(hypotheses=[record]))
        self.assertTrue(any("missing 'refutation_condition'" in e for e in errors), errors)

    def test_every_refutation_field_must_be_non_empty(self) -> None:
        for field in vs.REFUTATION_FIELDS:
            with self.subTest(field=field):
                condition = dict(_hypothesis()["refutation_condition"])
                condition[field] = "   "
                errors = _check(
                    _data(hypotheses=[_hypothesis(refutation_condition=condition)])
                )
                self.assertTrue(
                    any(f"refutation_condition.{field}" in e for e in errors), errors
                )

    def test_missing_literature_questions_is_rejected(self) -> None:
        record = _hypothesis()
        del record["next_literature_questions"]
        errors = _check(_data(hypotheses=[record]))
        self.assertTrue(
            any("'next_literature_questions'" in e for e in errors), errors
        )

    def test_empty_literature_questions_is_rejected(self) -> None:
        """Round 1: an empty searchable list means the planner has nothing to do."""
        errors = _check(
            _data(hypotheses=[_hypothesis(next_literature_questions=[])])
        )
        self.assertTrue(
            any("'next_literature_questions'" in e for e in errors), errors
        )

    def test_blank_literature_question_is_rejected(self) -> None:
        errors = _check(
            _data(hypotheses=[_hypothesis(next_literature_questions=["  "])])
        )
        self.assertTrue(
            any("next_literature_questions item" in e for e in errors), errors
        )

    def test_missing_internal_measurements_is_rejected(self) -> None:
        record = _hypothesis()
        del record["next_internal_measurements"]
        errors = _check(_data(hypotheses=[record]))
        self.assertTrue(
            any("'next_internal_measurements'" in e for e in errors), errors
        )

    def test_empty_internal_measurements_is_allowed(self) -> None:
        """'Nothing to measure internally' is a decision, not a schema error."""
        errors = _check(
            _data(hypotheses=[_hypothesis(next_internal_measurements=[])])
        )
        self.assertEqual(errors, [])

    def test_legacy_next_observations_does_not_satisfy_the_split(self) -> None:
        record = _hypothesis()
        del record["next_literature_questions"]
        del record["next_internal_measurements"]
        record["next_observations"] = ["the old single list"]
        errors = _check(_data(hypotheses=[record]))
        self.assertTrue(any("next_literature_questions" in e for e in errors), errors)

    def test_pre_split_file_keeps_the_legacy_list_requirement(self) -> None:
        record = {"hypothesis_id": "HYP-20261021-00b4", "statement": "s",
                  "status": "proposed", "round": 1,
                  "derived_from_evidence_ids": [],
                  "refutation_condition": dict(_hypothesis()["refutation_condition"]),
                  "next_observations": ["a third benchmark"]}
        origin = {"hypotheses": ["state/hypotheses.d/2026-10-21-00a42038e2b6.jsonl:1"]}
        errors = _check(_data(hypotheses=[record]), origins=origin,
                        pre_split={"state/hypotheses.d/2026-10-21-00a42038e2b6.jsonl"})
        self.assertEqual(errors, [])
        record["next_observations"] = []
        errors = _check(_data(hypotheses=[record]), origins=origin,
                        pre_split={"state/hypotheses.d/2026-10-21-00a42038e2b6.jsonl"})
        self.assertTrue(any("pre-split record" in e for e in errors), errors)

    def test_legacy_hypothesis_stays_exempt(self) -> None:
        record = {"hypothesis_id": "HYP-001", "statement": "old", "status": "supported"}
        errors = _check(
            _data(hypotheses=[record]),
            origins=_exempt_origins("hypotheses"),
            exempt={"state/hypotheses.jsonl"},
        )
        self.assertEqual(errors, [])


class RelationProvenanceTest(unittest.TestCase):
    def test_missing_flags_are_rejected(self) -> None:
        record = _relation()
        del record["derived_from"]
        del record["searched_refutation"]
        errors = _check(_data(relations=[record]))
        self.assertTrue(any("'derived_from'" in e for e in errors), errors)
        self.assertTrue(any("'searched_refutation'" in e for e in errors), errors)

    def test_derived_true_must_agree_with_the_hypothesis(self) -> None:
        errors = _check(
            _data(
                hypotheses=[_hypothesis(derived_from_evidence_ids=[])],
                relations=[_relation(derived_from=True)],
            )
        )
        self.assertTrue(
            any("derived_from=true" in e for e in errors), errors
        )

    def test_derived_true_is_consistent_when_declared(self) -> None:
        errors = _check(_data(relations=[_relation(derived_from=True)]))
        self.assertEqual(errors, [])

    def test_legacy_hypothesis_skips_the_cross_check(self) -> None:
        """Legacy hypotheses never recorded their inputs; do not invent one."""
        hypothesis = {"hypothesis_id": HYPOTHESIS, "statement": "old", "status": "proposed"}
        errors = _check(
            _data(
                hypotheses=[hypothesis],
                relations=[_relation(derived_from=True)],
            ),
            origins={"hypotheses": ["state/hypotheses.jsonl:1"]},
            exempt={"state/hypotheses.jsonl"},
        )
        self.assertEqual(errors, [])


class ThresholdTest(unittest.TestCase):
    """The optional machine-readable half of a refutation condition."""

    def _with_threshold(self, **threshold):
        condition = dict(_hypothesis()["refutation_condition"])
        condition["threshold"] = threshold
        return _check(_data(hypotheses=[_hypothesis(refutation_condition=condition)]))

    def test_absent_threshold_is_fine(self) -> None:
        self.assertEqual(_check(_data()), [])

    def test_well_formed_threshold_passes(self) -> None:
        errors = self._with_threshold(
            metric="residual_support_rate", operator="<=", value=0.7
        )
        self.assertEqual(errors, [])

    def test_unknown_operator_is_rejected(self) -> None:
        errors = self._with_threshold(
            metric="residual_support_rate", operator="~=", value=0.7
        )
        self.assertTrue(any("operator" in e for e in errors), errors)

    def test_missing_threshold_field_is_rejected(self) -> None:
        errors = self._with_threshold(metric="m", operator="<")  # no value
        self.assertTrue(any("threshold.value is missing" in e for e in errors), errors)

    def test_non_numeric_value_is_rejected(self) -> None:
        errors = self._with_threshold(metric="m", operator="<", value="0.7")
        self.assertTrue(any("must be a number" in e for e in errors), errors)

    def test_boolean_value_is_rejected(self) -> None:
        """bool is an int subclass in Python; a threshold of True is nonsense."""
        errors = self._with_threshold(metric="m", operator="<", value=True)
        self.assertTrue(any("must be a number" in e for e in errors), errors)

    def test_empty_metric_is_rejected(self) -> None:
        errors = self._with_threshold(metric="  ", operator="<", value=0.7)
        self.assertTrue(any("metric" in e for e in errors), errors)

    def test_threshold_applies_to_predictions_too(self) -> None:
        record = {
            "prediction_id": "PRD-20261021-2222",
            "hypothesis_id": HYPOTHESIS,
            "registered_at": "2026-10-21",
            "probability": 0.6,
            "statement": "s",
            "refutation_condition": {
                "observable": "o", "would_refute": "w", "expected_if_true": "e",
                "threshold": {"metric": "m", "operator": "??", "value": 1},
            },
        }
        errors = _check(_data(predictions=[record]))
        self.assertTrue(any("operator" in e for e in errors), errors)


class CycleLedgerFieldTest(unittest.TestCase):
    def test_search_log_included_source_must_exist(self) -> None:
        errors = _check(
            _data(search_log=[_query(included_source_ids=["SRC-20261021-9999"])])
        )
        self.assertTrue(any("unknown included source_id" in e for e in errors), errors)

    def test_search_log_derived_from_must_resolve(self) -> None:
        errors = _check(_data(search_log=[_query(derived_from=["EVD-20261021-0000"])]))
        self.assertTrue(any("unknown derived_from" in e for e in errors), errors)

    def test_prediction_probability_range(self) -> None:
        for bad in (-0.01, 1.01):
            with self.subTest(probability=bad):
                record = {
                    "prediction_id": "PRD-20261021-2222",
                    "hypothesis_id": HYPOTHESIS,
                    "registered_at": "2026-10-21",
                    "probability": bad,
                    "statement": "s",
                }
                errors = _check(_data(predictions=[record]))
                self.assertTrue(any("[0, 1]" in e for e in errors), errors)

    def test_prediction_must_name_a_hypothesis(self) -> None:
        record = {
            "prediction_id": "PRD-20261021-2222",
            "hypothesis_id": "HYP-20261021-0000",
            "registered_at": "2026-10-21",
            "probability": 0.6,
            "statement": "s",
        }
        errors = vs.check_references(_data(predictions=[record]))
        self.assertTrue(any("unknown hypothesis_id" in e for e in errors), errors)

    def test_run_round_and_interventions_are_validated(self) -> None:
        record = {
            "run_id": "RUN-20261021-3333",
            "round": 0,
            "started_at": "2026-10-21T08:00:00Z",
            "human_interventions": -1,
        }
        errors = _check(_data(runs=[record]))
        self.assertTrue(any("'round' must be an integer >= 1" in e for e in errors), errors)
        self.assertTrue(
            any("'human_interventions' must be an integer >= 0" in e for e in errors),
            errors,
        )

    def test_compliant_round_records_pass(self) -> None:
        records = [{
            "run_id": "RUN-20261021-3333",
            "round": 2,
            "started_at": "2026-10-21T08:00:00Z",
            "ended_at": "2026-10-21T09:00:00Z",
            "human_interventions": 2,
            "hypotheses_created": 1,
        }, {
            "prediction_id": "PRD-20261021-2222",
            "hypothesis_id": HYPOTHESIS,
            "registered_at": "2026-10-21",
            "probability": 0.6,
            "statement": "a third benchmark will show a reversal",
        }]
        errors = _check(_data(runs=records[:1], predictions=records[1:]))
        errors += vs.check_references(_data(runs=records[:1], predictions=records[1:]))
        self.assertEqual(errors, [])


class EndToEndTest(unittest.TestCase):
    """The gates must fire in a real shard, and only there."""

    def _temp_repo(self, tmp: Path, shards: dict) -> Path:
        root = tmp / "repo"
        root.mkdir()
        for entry in ROOT.iterdir():
            if entry.name in {"state", ".git"}:
                continue
            os.symlink(entry, root / entry.name)
        for name, (ledger_rel, _schema, _id_key) in vs.COLLECTIONS.items():
            target = root / ledger_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / ledger_rel, target)
        shutil.copy(ROOT / vs.CYCLE_EXEMPTIONS, root / vs.CYCLE_EXEMPTIONS)
        for rel, records in shards.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
                encoding="utf-8",
            )
        return root

    def test_baseline_copy_still_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._temp_repo(Path(tmp), {})
            self.assertEqual(vs.run_all_checks(root)["errors"], [])

    def test_new_source_without_a_search_record_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._temp_repo(
                Path(tmp),
                {"state/sources.d/2026-10-21-abcdef123456.jsonl": [_source(query_id=None)]},
            )
            errors = vs.run_all_checks(root)["errors"]
        self.assertTrue(any("missing query_id" in e for e in errors), errors)

    def test_new_source_with_a_matching_search_record_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._temp_repo(
                Path(tmp),
                {
                    "state/search_log.d/2026-10-21-abcdef123456.jsonl": [_query()],
                    "state/sources.d/2026-10-21-abcdef123456.jsonl": [_source()],
                },
            )
            errors = vs.run_all_checks(root)["errors"]
        self.assertEqual(errors, [], msg="\n".join(errors))

    def test_new_hypothesis_without_the_cycle_fields_is_rejected(self) -> None:
        record = {"hypothesis_id": HYPOTHESIS, "statement": "s", "status": "proposed",
                  "evidence_ids": [EVIDENCE]}
        with tempfile.TemporaryDirectory() as tmp:
            root = self._temp_repo(
                Path(tmp),
                {
                    "state/search_log.d/2026-10-21-abcdef123456.jsonl": [_query()],
                    "state/sources.d/2026-10-21-abcdef123456.jsonl": [_source()],
                    "state/evidence.d/2026-10-21-abcdef123456.jsonl": [_evidence()],
                    "state/hypotheses.d/2026-10-21-abcdef123456.jsonl": [record],
                },
            )
            errors = vs.run_all_checks(root)["errors"]
        self.assertTrue(any("missing 'refutation_condition'" in e for e in errors), errors)
        self.assertTrue(any("'round'" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
