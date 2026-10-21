"""Regression tests for scripts/gap_scan.py.

gap_scan counts hypothesis-coverage gaps from the relation ledger
(contributions/2026-10-21_sheldon_reading.md sections 3.3-3.4 and 5.6). It is
an instrument, not a gate. This file pins the properties the specification
requires, all on SYNTHETIC ledgers written to temporary directories (the
2026-10-19 audit lesson: a test must not depend on this repository's own
history or on another session's artefacts):

  * with an empty relation ledger every observation is unassessed AND
    unexplained (100%);
  * a support REL removes the observation from unexplained (but not from
    unassessed, which asks for a REL of any kind);
  * a refute is counted only when the observation is corroborated -- a second
    EVD with the same observation_key from a DIFFERENT source_id. No key, no
    second record, same source, or a missing source all stay provisional, and
    a provisional refute is reported as suppressed instead of counted;
  * an explicit `provisional` on the REL decides, in both directions, but a
    dangling observation_id can never be un-gated that way (fail-closed);
  * per-source (region) counts are ordered by unassessed count, descending,
    with source_id as the deterministic tie-break;
  * the --json document has the documented shape and types;
  * the exit code is 0 for any completed measurement (including 100%
    unassessed) and 2 only for usage / I/O problems;
  * the ledgers are never written to, and two runs agree.
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

import gap_scan as gs  # noqa: E402


# --------------------------------------------------------------------------
# Fixture helpers
# --------------------------------------------------------------------------
def evd(evidence_id: str, source_id: str = "SRC-A", key=None) -> dict:
    record = {
        "evidence_id": evidence_id,
        "source_id": source_id,
        "excerpt": "synthetic excerpt",
        "interpretation": "synthetic interpretation",
        "confidence": "high",
    }
    if key is not None:
        record["observation_key"] = key
    if source_id is None:
        record.pop("source_id")
    return record


def rel(relation_id: str, hypothesis_id: str, observation_id: str,
        verdict: str, **extra) -> dict:
    record = {
        "relation_id": relation_id,
        "hypothesis_id": hypothesis_id,
        "observation_id": observation_id,
        "verdict": verdict,
    }
    record.update(extra)
    return record


def hyp(hypothesis_id: str) -> dict:
    return {
        "hypothesis_id": hypothesis_id,
        "statement": "synthetic hypothesis",
        "status": "testing",
    }


def write_jsonl(path: Path, records) -> None:
    lines = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
    path.write_text(lines, encoding="utf-8")


def make_state(tmp: str, evidence, relations, hypotheses=None) -> Path:
    state = Path(tmp) / "state"
    state.mkdir(exist_ok=True)
    write_jsonl(state / "evidence.jsonl", evidence)
    write_jsonl(state / "relations.jsonl", relations)
    write_jsonl(
        state / "hypotheses.jsonl",
        [hyp("HYP-001"), hyp("HYP-002")] if hypotheses is None else hypotheses,
    )
    return state


def report_for(evidence, relations, hypotheses=None) -> dict:
    return gs.analyse(
        evidence,
        relations,
        [hyp("HYP-001"), hyp("HYP-002")] if hypotheses is None else hypotheses,
    )


def hypothesis_row(report: dict, hypothesis_id: str) -> dict:
    for row in report["per_hypothesis"]:
        if row["hypothesis_id"] == hypothesis_id:
            return row
    raise AssertionError(f"{hypothesis_id} not in report")


def run_cli(argv):
    """Run main() and return (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = gs.main(argv)
    return code, out.getvalue(), err.getvalue()


# --------------------------------------------------------------------------
# 1. Empty ledger: every observation is unassessed and unexplained
# --------------------------------------------------------------------------
class EmptyLedgerTest(unittest.TestCase):
    def setUp(self):
        self.evidence = [
            evd("EVD-001", "SRC-A"),
            evd("EVD-002", "SRC-B"),
            evd("EVD-003", "SRC-A"),
        ]
        self.report = report_for(self.evidence, [])

    def test_every_observation_is_unassessed(self):
        block = self.report["unassessed"]
        self.assertEqual(block["count"], 3)
        self.assertEqual(block["total"], 3)
        self.assertEqual(block["rate"], 1.0)
        self.assertEqual(
            block["evidence_ids"], ["EVD-001", "EVD-002", "EVD-003"]
        )

    def test_every_observation_is_unexplained(self):
        block = self.report["unexplained"]
        self.assertEqual(block["count"], 3)
        self.assertEqual(block["total"], 3)
        self.assertEqual(block["rate"], 1.0)

    def test_all_observations_are_provisional_without_a_key(self):
        self.assertEqual(self.report["totals"]["provisional"], 3)
        self.assertEqual(self.report["totals"]["non_provisional"], 0)

    def test_hypothesis_rows_are_zero_but_present(self):
        for hid in ("HYP-001", "HYP-002"):
            row = hypothesis_row(self.report, hid)
            for verdict in ("support", "refute", "neutral", "unresolved"):
                self.assertEqual(row[verdict], 0, f"{hid}.{verdict}")

    def test_narrow_reading_excludes_observations_with_no_relation(self):
        # Nothing has a REL, so nothing is "assessed but unresolved" either.
        self.assertEqual(self.report["unresolved_only"]["count"], 0)

    def test_empty_evidence_ledger_does_not_divide_by_zero(self):
        report = report_for([], [])
        self.assertEqual(report["unassessed"]["count"], 0)
        self.assertEqual(report["unassessed"]["rate"], 0.0)
        self.assertEqual(report["unexplained"]["rate"], 0.0)
        self.assertEqual(report["per_source"], [])


# --------------------------------------------------------------------------
# 2. support / neutral / unresolved move an observation out of the lists
# --------------------------------------------------------------------------
class SupportTest(unittest.TestCase):
    def setUp(self):
        self.evidence = [evd("EVD-001", "SRC-A"), evd("EVD-002", "SRC-B")]
        self.report = report_for(
            self.evidence, [rel("REL-1", "HYP-001", "EVD-001", "support")]
        )

    def test_support_removes_the_observation_from_unexplained(self):
        self.assertEqual(
            self.report["unexplained"]["evidence_ids"], ["EVD-002"]
        )
        self.assertEqual(self.report["unexplained"]["count"], 1)
        self.assertEqual(self.report["unexplained"]["rate"], 0.5)

    def test_support_also_removes_it_from_unassessed(self):
        self.assertEqual(
            self.report["unassessed"]["evidence_ids"], ["EVD-002"]
        )

    def test_support_is_counted_on_the_named_hypothesis_only(self):
        self.assertEqual(hypothesis_row(self.report, "HYP-001")["support"], 1)
        self.assertEqual(hypothesis_row(self.report, "HYP-002")["support"], 0)

    def test_provisional_support_still_counts_as_support(self):
        # SHELDON gates only "refute"; a provisional observation may guide
        # exploration, so its support is usable.
        self.assertNotIn("EVD-001", self.report["unexplained"]["evidence_ids"])

    def test_neutral_and_unresolved_are_counted_but_do_not_explain(self):
        report = report_for(
            self.evidence,
            [
                rel("REL-1", "HYP-001", "EVD-001", "neutral"),
                rel("REL-2", "HYP-002", "EVD-002", "unresolved"),
            ],
        )
        self.assertEqual(report["unexplained"]["count"], 2)
        self.assertEqual(hypothesis_row(report, "HYP-001")["neutral"], 1)
        self.assertEqual(hypothesis_row(report, "HYP-002")["unresolved"], 1)

    def test_unresolved_only_lists_assessed_but_unresolved_observations(self):
        report = report_for(
            self.evidence,
            [rel("REL-1", "HYP-001", "EVD-001", "unresolved")],
        )
        self.assertEqual(report["unresolved_only"]["evidence_ids"], ["EVD-001"])
        self.assertEqual(report["unresolved_only"]["count"], 1)

    def test_unresolved_only_drops_observations_with_a_decided_verdict(self):
        report = report_for(
            self.evidence,
            [
                rel("REL-1", "HYP-001", "EVD-001", "unresolved"),
                rel("REL-2", "HYP-002", "EVD-001", "support"),
            ],
        )
        self.assertEqual(report["unresolved_only"]["count"], 0)


# --------------------------------------------------------------------------
# 3. Refutations are counted only and exactly when corroborated
# --------------------------------------------------------------------------
class ProvisionalRefuteTest(unittest.TestCase):
    def test_corroborated_observation_yields_a_counted_refutation(self):
        evidence = [
            evd("EVD-001", "SRC-A", key="K1"),
            evd("EVD-002", "SRC-B", key="K1"),
        ]
        report = report_for(
            evidence, [rel("REL-1", "HYP-001", "EVD-001", "refute")]
        )
        row = hypothesis_row(report, "HYP-001")
        self.assertEqual(row["refute"], 1)
        self.assertEqual(row["refute_suppressed_provisional"], 0)
        self.assertEqual(report["totals"]["non_provisional"], 2)

    def test_observation_without_a_key_cannot_refute(self):
        report = report_for(
            [evd("EVD-001", "SRC-A")],
            [rel("REL-1", "HYP-001", "EVD-001", "refute")],
        )
        row = hypothesis_row(report, "HYP-001")
        self.assertEqual(row["refute"], 0)
        self.assertEqual(row["refute_suppressed_provisional"], 1)

    def test_same_key_from_the_same_source_cannot_refute(self):
        evidence = [
            evd("EVD-001", "SRC-A", key="K1"),
            evd("EVD-002", "SRC-A", key="K1"),
        ]
        report = report_for(
            evidence, [rel("REL-1", "HYP-001", "EVD-001", "refute")]
        )
        row = hypothesis_row(report, "HYP-001")
        self.assertEqual(row["refute"], 0)
        self.assertEqual(row["refute_suppressed_provisional"], 1)

    def test_a_key_shared_without_a_second_source_is_still_provisional(self):
        evidence = [
            evd("EVD-001", "SRC-A", key="K1"),
            evd("EVD-002", "SRC-B", key="K2"),
        ]
        report = report_for(
            evidence,
            [
                rel("REL-1", "HYP-001", "EVD-001", "refute"),
                rel("REL-2", "HYP-002", "EVD-002", "refute"),
            ],
        )
        self.assertEqual(hypothesis_row(report, "HYP-001")["refute"], 0)
        self.assertEqual(hypothesis_row(report, "HYP-002")["refute"], 0)

    def test_observation_without_a_source_id_is_provisional(self):
        evidence = [
            evd("EVD-001", None, key="K1"),
            evd("EVD-002", "SRC-B", key="K1"),
        ]
        report = report_for(
            evidence, [rel("REL-1", "HYP-001", "EVD-001", "refute")]
        )
        self.assertEqual(hypothesis_row(report, "HYP-001")["refute"], 0)
        # Fail-closed in both directions: the record without a source cannot be
        # corroborated, and it cannot corroborate the one that has a source.
        self.assertEqual(report["totals"]["provisional"], 2)
        self.assertEqual(report["totals"]["non_provisional"], 0)

    def test_explicit_provisional_true_suppresses_a_corroborated_refute(self):
        evidence = [
            evd("EVD-001", "SRC-A", key="K1"),
            evd("EVD-002", "SRC-B", key="K1"),
        ]
        report = report_for(
            evidence,
            [rel("REL-1", "HYP-001", "EVD-001", "refute", provisional=True)],
        )
        row = hypothesis_row(report, "HYP-001")
        self.assertEqual(row["refute"], 0)
        self.assertEqual(row["refute_suppressed_provisional"], 1)

    def test_explicit_provisional_false_is_honoured_for_a_known_observation(self):
        report = report_for(
            [evd("EVD-001", "SRC-A")],
            [rel("REL-1", "HYP-001", "EVD-001", "refute", provisional=False)],
        )
        self.assertEqual(hypothesis_row(report, "HYP-001")["refute"], 1)

    def test_non_boolean_provisional_falls_back_to_the_derivation(self):
        report = report_for(
            [evd("EVD-001", "SRC-A")],
            [rel("REL-1", "HYP-001", "EVD-001", "refute", provisional="no")],
        )
        row = hypothesis_row(report, "HYP-001")
        self.assertEqual(row["refute"], 0)
        self.assertEqual(row["refute_suppressed_provisional"], 1)

    def test_dangling_observation_stays_provisional_even_if_flagged_false(self):
        report = report_for(
            [evd("EVD-001", "SRC-A")],
            [rel("REL-1", "HYP-001", "EVD-404", "refute", provisional=False)],
        )
        row = hypothesis_row(report, "HYP-001")
        self.assertEqual(row["refute"], 0)
        self.assertEqual(row["refute_suppressed_provisional"], 1)
        self.assertEqual(
            report["anomalies"]["dangling_observation"],
            ["REL-1: observation_id=EVD-404"],
        )

    def test_dangling_hypothesis_is_reported_and_not_attributed(self):
        report = report_for(
            [evd("EVD-001", "SRC-A")],
            [rel("REL-1", "HYP-999", "EVD-001", "support")],
        )
        self.assertEqual(
            report["anomalies"]["dangling_hypothesis"],
            ["REL-1: hypothesis_id=HYP-999"],
        )
        self.assertEqual([r["hypothesis_id"] for r in report["per_hypothesis"]],
                         ["HYP-001", "HYP-002"])

    def test_unknown_verdict_is_not_counted_as_support_or_refute(self):
        report = report_for(
            [evd("EVD-001", "SRC-A")],
            [rel("REL-1", "HYP-001", "EVD-001", "banana")],
        )
        row = hypothesis_row(report, "HYP-001")
        self.assertEqual(row["support"], 0)
        self.assertEqual(row["refute"], 0)
        self.assertEqual(row["other"], 1)
        self.assertEqual(
            report["anomalies"]["unknown_verdict"], ["REL-1: verdict=banana"]
        )
        # A record exists, so the observation is not unassessed.
        self.assertEqual(report["unassessed"]["count"], 0)

    def test_duplicate_pairs_are_reported(self):
        report = report_for(
            [evd("EVD-001", "SRC-A")],
            [
                rel("REL-1", "HYP-001", "EVD-001", "support"),
                rel("REL-2", "HYP-001", "EVD-001", "support"),
            ],
        )
        self.assertEqual(
            report["anomalies"]["duplicate_pairs"],
            ["HYP-001 x EVD-001 (2 records)"],
        )
        self.assertEqual(hypothesis_row(report, "HYP-001")["support"], 2)


# --------------------------------------------------------------------------
# 4. Per-region (source_id) aggregation and ordering
# --------------------------------------------------------------------------
class RegionOrderingTest(unittest.TestCase):
    def setUp(self):
        self.evidence = [
            evd("EVD-001", "SRC-B"),
            evd("EVD-002", "SRC-A"),
            evd("EVD-003", "SRC-C"),
            evd("EVD-004", "SRC-C"),
            evd("EVD-005", "SRC-C"),
            evd("EVD-006", "SRC-B"),
        ]
        self.report = report_for(
            self.evidence,
            [rel("REL-1", "HYP-001", "EVD-002", "support")],
        )

    def test_sources_are_ordered_by_unassessed_count_descending(self):
        order = [row["source_id"] for row in self.report["per_source"]]
        self.assertEqual(order, ["SRC-C", "SRC-B", "SRC-A"])

    def test_ties_are_broken_by_source_id(self):
        report = report_for(
            [evd("EVD-001", "SRC-Z"), evd("EVD-002", "SRC-M")], []
        )
        order = [row["source_id"] for row in report["per_source"]]
        self.assertEqual(order, ["SRC-M", "SRC-Z"])

    def test_counts_per_source_are_reported(self):
        rows = {row["source_id"]: row for row in self.report["per_source"]}
        self.assertEqual(rows["SRC-C"]["evidence"], 3)
        self.assertEqual(rows["SRC-C"]["unassessed"], 3)
        self.assertEqual(rows["SRC-A"]["unassessed"], 0)
        self.assertEqual(rows["SRC-A"]["unexplained"], 0)
        self.assertEqual(rows["SRC-B"]["unexplained"], 2)

    def test_missing_source_id_is_grouped_under_an_explicit_label(self):
        report = report_for([evd("EVD-001", None)], [])
        self.assertEqual(
            [row["source_id"] for row in report["per_source"]],
            [gs.NO_SOURCE_LABEL],
        )


# --------------------------------------------------------------------------
# 5. --json shape
# --------------------------------------------------------------------------
class JsonShapeTest(unittest.TestCase):
    def setUp(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(
                tmp,
                [evd("EVD-001", "SRC-A"), evd("EVD-002", "SRC-B")],
                [rel("REL-1", "HYP-001", "EVD-001", "support")],
            )
            code, out, err = run_cli(["--state-dir", str(state), "--json"])
        self.code, self.payload, self.stderr = code, json.loads(out), err

    def test_exit_code_and_streams(self):
        self.assertEqual(self.code, 0)
        self.assertEqual(self.stderr, "")

    def test_top_level_keys(self):
        self.assertEqual(
            sorted(self.payload),
            sorted([
                "generated_from", "totals", "unassessed", "unexplained",
                "unresolved_only", "per_hypothesis", "per_source", "anomalies",
            ]),
        )

    def test_provenance_names_the_ledgers(self):
        self.assertEqual(
            self.payload["generated_from"],
            {
                "evidence": "state/evidence.jsonl",
                "relations": "state/relations.jsonl",
                "hypotheses": "state/hypotheses.jsonl",
            },
        )

    def test_counts_are_integers_and_rates_are_fractions(self):
        self.assertEqual(self.payload["totals"]["evidence"], 2)
        self.assertEqual(self.payload["totals"]["relations"], 1)
        self.assertEqual(self.payload["totals"]["hypotheses"], 2)
        for key in ("unassessed", "unexplained"):
            block = self.payload[key]
            self.assertIsInstance(block["count"], int)
            self.assertIsInstance(block["total"], int)
            self.assertIsInstance(block["rate"], float)
            self.assertIsInstance(block["evidence_ids"], list)
            self.assertEqual(block["total"], 2)
            self.assertEqual(block["count"], len(block["evidence_ids"]))
        self.assertEqual(self.payload["unassessed"], {
            "count": 1, "total": 2, "rate": 0.5, "evidence_ids": ["EVD-002"],
        })

    def test_per_hypothesis_rows_have_every_verdict_key(self):
        row = self.payload["per_hypothesis"][0]
        self.assertEqual(row["hypothesis_id"], "HYP-001")
        for key in ("support", "refute", "neutral", "unresolved",
                    "refute_suppressed_provisional", "other"):
            self.assertIsInstance(row[key], int)
        self.assertEqual(row["support"], 1)

    def test_per_source_rows_have_the_documented_keys(self):
        row = self.payload["per_source"][0]
        self.assertEqual(
            sorted(row), ["evidence", "source_id", "unassessed", "unexplained"]
        )

    def test_anomalies_is_a_dict_of_lists(self):
        self.assertEqual(
            sorted(self.payload["anomalies"]),
            ["dangling_hypothesis", "dangling_observation", "duplicate_pairs",
             "unknown_verdict"],
        )
        for value in self.payload["anomalies"].values():
            self.assertEqual(value, [])


# --------------------------------------------------------------------------
# 6. CLI contract: exit 0 on findings, 2 on usage / I/O
# --------------------------------------------------------------------------
class CliContractTest(unittest.TestCase):
    def test_exit_zero_when_everything_is_unassessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp, [evd("EVD-001"), evd("EVD-002")], [])
            code, out, _ = run_cli(["--state-dir", str(state)])
        self.assertEqual(code, 0)
        self.assertIn("unassessed: 2 / 2 (100.0%)", out)
        self.assertIn("unexplained: 2 / 2 (100.0%)", out)

    def test_human_output_lists_every_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(
                tmp, [evd("EVD-001")], [rel("REL-1", "HYP-001", "EVD-001", "refute")]
            )
            code, out, _ = run_cli(["--state-dir", str(state)])
        self.assertEqual(code, 0)
        for heading in (
            "unassessed:", "unexplained:", "unresolved のみ:",
            "仮説ごとの verdict", "観測領域（source_id）別", "計測器でありゲート",
        ):
            self.assertIn(heading, out)
        self.assertIn("provisional により抑止=1", out)

    def test_exit_two_when_the_relations_ledger_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state"
            state.mkdir()
            write_jsonl(state / "evidence.jsonl", [evd("EVD-001")])
            write_jsonl(state / "hypotheses.jsonl", [hyp("HYP-001")])
            code, out, err = run_cli(["--state-dir", str(state)])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("file not found", err)

    def test_exit_two_when_a_ledger_line_is_not_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp, [evd("EVD-001")], [])
            (state / "relations.jsonl").write_text("{not json\n", encoding="utf-8")
            code, _, err = run_cli(["--state-dir", str(state)])
        self.assertEqual(code, 2)
        self.assertIn("invalid JSON", err)

    def test_exit_two_when_the_state_directory_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run_cli(["--state-dir", str(Path(tmp) / "nope")])
        self.assertEqual(code, 2)
        self.assertIn("state directory not found", err)

    def test_unknown_argument_is_a_usage_error(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                gs.main(["--bogus"])
        self.assertEqual(raised.exception.code, 2)


# --------------------------------------------------------------------------
# 7. Instrument properties: read-only, deterministic, real-ledger baseline
# --------------------------------------------------------------------------
class InstrumentPropertiesTest(unittest.TestCase):
    def test_the_ledgers_are_not_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(
                tmp,
                [evd("EVD-001", "SRC-A", key="K1"), evd("EVD-002", "SRC-B", key="K1")],
                [rel("REL-1", "HYP-001", "EVD-001", "refute")],
            )
            before = {p.name: p.read_bytes() for p in state.iterdir()}
            run_cli(["--state-dir", str(state)])
            after = {p.name: p.read_bytes() for p in state.iterdir()}
        self.assertEqual(before, after)

    def test_two_runs_produce_identical_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp, [evd("EVD-001"), evd("EVD-002", "SRC-B")], [])
            first = run_cli(["--state-dir", str(state), "--json"])[1]
            second = run_cli(["--state-dir", str(state), "--json"])[1]
        self.assertEqual(first, second)

    def test_real_ledgers_are_readable_and_consistent(self):
        # A smoke test on the repository's own ledgers: the instrument must run
        # and must not mutate anything. No counts are asserted here -- the
        # measured baseline lives in contributions/ and changes with backfill.
        before = {
            name: (ROOT / rel).read_bytes()
            for name, (rel, _schema, _key) in gs.vs.COLLECTIONS.items()
        }
        code, out, _ = run_cli(["--json"])
        after = {
            name: (ROOT / rel).read_bytes()
            for name, (rel, _schema, _key) in gs.vs.COLLECTIONS.items()
        }
        self.assertEqual(code, 0)
        self.assertEqual(before, after)
        payload = json.loads(out)
        self.assertEqual(
            payload["totals"]["evidence"],
            payload["unassessed"]["total"],
        )
        self.assertEqual(
            payload["unassessed"]["count"],
            len(payload["unassessed"]["evidence_ids"]),
        )
        self.assertEqual(
            payload["unexplained"]["count"],
            len(payload["unexplained"]["evidence_ids"]),
        )


if __name__ == "__main__":
    unittest.main()
