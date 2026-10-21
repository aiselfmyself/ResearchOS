"""Phase 3 instruments: synthetic measurements, never a quality gate.

Historical flags are missing, not false; an independent rater's absence is
missing, not agreement. Neither rate (even 100%) proves correctness or
independence. CLI I/O tests use only temp ledgers; the real repo is not edited.
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
sys.path.insert(0, str(ROOT / "scripts"))
import gap_scan as gs  # noqa: E402
import next_queries as nq  # noqa: E402
import relation_agreement as ra  # noqa: E402
import self_support as ss  # noqa: E402


def hyp(hid="HYP-A", **extra):
    return {"hypothesis_id": hid, **extra}


def rel(rid, hid="HYP-A", oid="EVD-A", verdict="support", **extra):
    return {"relation_id": rid, "hypothesis_id": hid, "observation_id": oid,
            "verdict": verdict, **extra}


def bundle(session, items):
    return {"session_id": session, "method": "synthetic", "items": {
        (hid, eid): verdict for hid, eid, verdict in items
    }}


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def item(hid="HYP-A", eid="EVD-A", verdict="support"):
    return {"hypothesis_id": hid, "observation_id": eid, "verdict": verdict}


class SelfSupportTest(unittest.TestCase):
    def setUp(self):
        self.hypotheses = [hyp(derived_from_evidence_ids=["EVD-A"]),
                           hyp("HYP-LEGACY", evidence_ids=["EVD-B"])]
        self.relations = [
            rel("REL-1", derived_from=True),
            rel("REL-2", oid="EVD-C", derived_from=False),
            rel("REL-3", "HYP-LEGACY", "EVD-B"),
            rel("REL-4", "HYP-LEGACY", "EVD-D"),
            rel("REL-5", oid="EVD-E", verdict="neutral", derived_from=True),
        ]
        self.report = ss.analyse(self.hypotheses, self.relations)

    def test_unknown_is_not_false(self):
        self.assertEqual(self.report["totals"]["derived_false"], 1)
        self.assertEqual(self.report["totals"]["unknown_flag"], 2)
        self.assertEqual(self.report["totals"]["support_total"], 4)

    def test_rate_over_explicit_flags_and_bounds_over_all(self):
        t = self.report["totals"]
        self.assertEqual(t["known_flag_rate"], 0.5)
        self.assertEqual(t["flag_coverage"], 0.5)
        self.assertEqual(t["possible_rate_bounds"], [0.25, 0.75])

    def test_proxy_kept_separate_from_measured_numerator(self):
        self.assertEqual(self.report["totals"]["legacy_overlap_proxy"], 1)
        self.assertEqual(self.report["totals"]["derived_true"], 1)
        legacy = self.report["per_hypothesis"][1]
        self.assertEqual(legacy["known_flag_rate"], None)
        self.assertEqual(legacy["legacy_overlap_proxy_rate"], 0.5)

    def test_non_support_never_in_denominator(self):
        self.assertEqual(self.report["totals"]["non_support_relations"], 1)

    def test_boolean_false_is_not_a_true_flag(self):
        r = ss.analyse([hyp(derived_from_evidence_ids=[])],
                       [rel("R", derived_from=False)])["totals"]
        self.assertEqual((r["derived_true"], r["known_flag_rate"]), (0, 0.0))

    def test_empty_no_divide_by_zero(self):
        r = ss.analyse([hyp()], [])["totals"]
        self.assertIsNone(r["known_flag_rate"])
        self.assertEqual(r["possible_rate_bounds"], [None, None])
        self.assertIsNone(r["flag_coverage"])

    def test_only_legacy_unknown_rate_is_null_not_zero(self):
        r = ss.analyse([hyp()], [rel("R")])["totals"]
        self.assertEqual(r["known_flag_rate"], None)
        self.assertEqual(r["possible_rate_bounds"], [0.0, 1.0])

    def test_missing_flag_on_declared_origin_is_warned_not_assumed(self):
        r = ss.analyse([hyp(derived_from_evidence_ids=["EVD-A"])], [rel("R")])
        self.assertEqual(r["totals"]["unknown_flag"], 1)
        self.assertIn("missing derived_from", r["warnings"][0])

    def test_false_flag_on_declared_origin_is_warned_not_changed(self):
        r = ss.analyse([hyp(derived_from_evidence_ids=["EVD-A"])],
                       [rel("R", derived_from=False)])
        self.assertEqual(r["totals"]["derived_false"], 1)
        self.assertIn("derived_from=false", r["warnings"][0])

    def test_true_flag_not_in_declared_list_is_warned(self):
        r = ss.analyse([hyp(derived_from_evidence_ids=[])],
                       [rel("R", derived_from=True)])
        self.assertIn("derived_from=true", r["warnings"][0])

    def test_unknown_hypothesis_is_not_in_denominator(self):
        r = ss.analyse([], [rel("R")])
        self.assertEqual(r["totals"]["support_total"], 0)
        self.assertIn("unknown hypothesis", r["warnings"][0])

    def test_duplicate_support_pair_reported_not_silently_deduplicated(self):
        r = ss.analyse([hyp()], [rel("R1", derived_from=True), rel("R2", derived_from=False)])
        self.assertEqual(r["totals"]["support_total"], 2)
        self.assertIn("duplicate support pair", r["warnings"][0])

    def test_hypothesis_order_is_deterministic(self):
        r = ss.analyse(list(reversed(self.hypotheses)), list(reversed(self.relations)))
        self.assertEqual(r["per_hypothesis"], self.report["per_hypothesis"])

    def test_non_boolean_flag_is_unknown(self):
        r = ss.analyse([hyp()], [rel("R", derived_from="false")])["totals"]
        self.assertEqual((r["unknown_flag"], r["derived_false"]), (1, 0))

    def test_duplicate_hypothesis_cannot_silently_pick_one(self):
        with self.assertRaisesRegex(ss.gs.LedgerError, "duplicate hypothesis_id"):
            ss.analyse([hyp(), hyp()], [rel("R", derived_from=True)])


class SelfSupportCliTest(unittest.TestCase):
    def test_cli_reads_shards_and_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            write_jsonl(state / "hypotheses.jsonl", [hyp()])
            write_jsonl(state / "relations.jsonl", [])
            (state / "relations.d").mkdir()
            part = state / "relations.d" / "2026-10-21-0123456789ab.jsonl"
            write_jsonl(part, [rel("REL-1", derived_from=True)])
            before = {p: p.read_bytes() for p in state.rglob("*.jsonl")}
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(ss.main(["--state-dir", str(state), "--json"]), 0)
            self.assertEqual(json.loads(out.getvalue())["totals"]["derived_true"], 1)
            self.assertEqual(before, {p: p.read_bytes() for p in state.rglob("*.jsonl")})

    def test_cli_missing_dir_is_an_input_error_not_a_research_failure(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ss.main(["--state-dir", str(Path(tmp) / "absent")]), 2)

    def test_human_output_explains_unknown(self):
        self.assertIn("unknown=2", ss.format_human(ss.analyse([hyp()],
                            [rel("R"), rel("R2", oid="EVD-B")])) )


class ObservationKeySeedTest(unittest.TestCase):
    """An S3 key seeds a search but never manufactures independent evidence."""

    def setUp(self):
        self.evidence = [{"evidence_id": "EVD-A", "source_id": "SRC-A",
                          "excerpt": "no preference detected",
                          "observation_key": "self_preference_undetected_in_numeric_prediction"}]
        self.hypotheses = [{"hypothesis_id": "HYP-A",
                            "next_literature_questions": ["Can studies compare evaluator task types?"]}]

    def test_singleton_key_is_still_provisional_and_unexplained(self):
        gaps = gs.analyse(self.evidence, [rel("R", verdict="neutral")], self.hypotheses)
        self.assertEqual(gaps["totals"]["provisional"], 1)
        self.assertEqual(gaps["unexplained"]["evidence_ids"], ["EVD-A"])
        plan = nq.plan(self.hypotheses, self.evidence, [rel("R", verdict="neutral")], [], {})
        self.assertEqual(plan["coverage"]["with_seed"], 1)
        self.assertEqual(plan["coverage"]["queries"], 1)
        query = next(row["query"] for row in plan["queries"] if row["kind"] == "coverage")
        self.assertIn("undetected", query)  # not silently inverted by 'no' stopword

    def test_key_does_not_resolve_unexplained_without_support(self):
        plan = nq.plan(self.hypotheses, self.evidence, [], [], {})
        self.assertEqual(plan["coverage"]["with_seed"], 1)
        after = nq.plan(self.hypotheses, self.evidence,
                        [rel("R", verdict="support", derived_from=False)], [], {})
        self.assertEqual(after["coverage"]["queries"], 0)
        self.assertEqual(after["totals"]["unexplained"], 0)

    def test_only_different_source_can_corroborate(self):
        same = dict(self.evidence[0], evidence_id="EVD-B")
        self.assertEqual(gs.derive_provisional([*self.evidence, same]), [True, True])
        other = dict(same, source_id="SRC-B")
        self.assertEqual(gs.derive_provisional([*self.evidence, other]), [False, False])


class RelationAgreementTest(unittest.TestCase):
    def test_exact_agreement_and_disagreement(self):
        a = bundle("a", [("HYP-A", "EVD-A", "support"), ("HYP-A", "EVD-B", "unresolved")])
        b = bundle("b", [("HYP-A", "EVD-A", "support"), ("HYP-A", "EVD-B", "neutral")])
        r = ra.analyse(a, b)
        self.assertEqual(r["counts"]["agree"], 1)
        self.assertEqual(r["counts"]["disagree"], 1)
        self.assertEqual(r["agreement_comparable"], 0.5)
        self.assertEqual(r["a_support_retention"], {"retained": 1, "total": 1,
                          "missing_b": 0, "rate": 1.0})

    def test_unresolved_is_a_verdict_not_abstention(self):
        r = ra.analyse(bundle("a", [("H", "E", "unresolved")]),
                       bundle("b", [("H", "E", "unresolved")]))
        self.assertEqual(r["comparable"], 1)
        self.assertEqual(r["counts"]["agree"], 1)

    def test_missing_b_counts_against_union_not_as_disagreement(self):
        r = ra.analyse(bundle("a", [("H", "E1", "support"), ("H", "E2", "neutral")]),
                       bundle("b", [("H", "E1", "support")]))
        self.assertEqual(r["agreement_over_union"], 0.5)
        self.assertEqual(r["agreement_comparable"], 1.0)
        self.assertEqual(r["counts"]["a_only"], 1)

    def test_null_abstention_does_not_fake_agreement(self):
        r = ra.analyse(bundle("a", [("H", "E", None)]),
                       bundle("b", [("H", "E", None)]))
        self.assertEqual(r["counts"]["both_abstained"], 1)
        self.assertIsNone(r["agreement_comparable"])
        self.assertIsNone(r["cohens_kappa"]["kappa"])

    def test_one_abstention_is_not_decided(self):
        r = ra.analyse(bundle("a", [("H", "E", "support")]),
                       bundle("b", [("H", "E", None)]))
        self.assertEqual(r["counts"]["a_only"], 1)
        self.assertEqual(r["a_support_retention"]["missing_b"], 1)
        self.assertIsNone(r["a_support_retention"]["rate"])
        self.assertTrue(r["warnings"])

    def test_same_session_warned_even_if_all_agree(self):
        a = bundle("same", [("H", "E", "support")])
        r = ra.analyse(a, a)
        self.assertEqual(r["agreement_comparable"], 1.0)
        self.assertFalse(r["independence_verified"])
        self.assertIn("same session_id", r["warnings"][0])

    def test_distinct_session_ids_do_not_prove_independence(self):
        r = ra.analyse(bundle("a", []), bundle("b", []))
        self.assertFalse(r["independence_verified"])
        self.assertIsNone(r["agreement_over_union"])

    def test_kappa_and_single_category_undefined(self):
        a = bundle("a", [("H", "E1", "support"), ("H", "E2", "refute")])
        b = bundle("b", [("H", "E1", "support"), ("H", "E2", "refute")])
        self.assertEqual(ra.analyse(a, b)["cohens_kappa"]["kappa"], 1.0)
        one = bundle("a", [("H", "E1", "support")])
        self.assertIsNone(ra.analyse(one, dict(one, session_id="b"))["cohens_kappa"]["kappa"])

    def test_order_independent(self):
        a = bundle("a", [("H", "E2", "neutral"), ("H", "E1", "support")])
        b = bundle("b", [("H", "E1", "support"), ("H", "E2", "unresolved")])
        self.assertEqual([i["observation_id"] for i in ra.analyse(a, b)["items"]], ["E1", "E2"])

    def test_b_only_is_not_ignored(self):
        r = ra.analyse(bundle("a", []), bundle("b", [("H", "E", "support")]))
        self.assertEqual((r["universe"], r["counts"]["b_only"]), (1, 1))
        self.assertIsNone(r["a_support_retention"]["rate"])


class RelationAgreementCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.a = Path(self.tmp.name) / "a.json"
        self.b = Path(self.tmp.name) / "b.json"
        self.put(self.a, {"session_id": "a", "items": [item()]})
        self.put(self.b, {"session_id": "b", "items": [item()]})

    @staticmethod
    def put(path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    def test_cli_json_read_only_deterministic(self):
        before = (self.a.read_bytes(), self.b.read_bytes())
        results = []
        for _ in range(2):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(ra.main(["--a", str(self.a), "--b", str(self.b), "--json"]), 0)
            results.append(out.getvalue())
        self.assertEqual(results[0], results[1])
        self.assertEqual((self.a.read_bytes(), self.b.read_bytes()), before)
        self.assertEqual(json.loads(results[0])["counts"]["agree"], 1)

    def test_invalid_verdict_rejected(self):
        self.put(self.a, {"session_id": "a", "items": [item(verdict="SUPPORT")]})
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ra.main(["--a", str(self.a), "--b", str(self.b)]), 2)

    def test_duplicate_pair_is_error(self):
        self.put(self.a, {"session_id": "a", "items": [item(), item()]})
        with self.assertRaisesRegex(ValueError, "duplicate pair"):
            ra.load(self.a)

    def test_missing_verdict_is_error(self):
        self.put(self.a, {"session_id": "a", "items": [{"hypothesis_id": "H", "observation_id": "E"}]})
        with self.assertRaisesRegex(ValueError, "no verdict"):
            ra.load(self.a)

    def test_missing_or_invalid_session_id_is_error(self):
        for value in (None, "", 3):
            with self.subTest(value=value):
                self.put(self.a, {"session_id": value, "items": []})
                with self.assertRaisesRegex(ValueError, "session_id"):
                    ra.load(self.a)

    def test_malformed_items_rejected(self):
        for rows in (None, [3], [{"verdict": "support"}], [item(verdict="unknown")]):
            with self.subTest(rows=rows):
                self.put(self.a, {"session_id": "a", "items": rows})
                with self.assertRaises(ValueError):
                    ra.load(self.a)

    def test_missing_file_is_error(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ra.main(["--a", str(self.a), "--b", str(self.b) + "bad"]), 2)

    def test_empty_inputs_are_valid_not_a_gate(self):
        self.put(self.a, {"session_id": "a", "items": []})
        self.put(self.b, {"session_id": "b", "items": []})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ra.main(["--a", str(self.a), "--b", str(self.b)]), 0)


if __name__ == "__main__":
    unittest.main()
