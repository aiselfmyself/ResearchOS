"""S8 advisory readout: missing historical counts are unknown, not zero."""
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
import cycle_readout as cr  # noqa: E402


def run(number, **changes):
    record = {
        "run_id": f"RUN-{number}", "round": number, "human_interventions": 1,
        "hypotheses_created": 0,
        "metrics": {
            "unexplained_before": 4, "unexplained_after": 3,
            "support_non_derived_before": 10, "support_non_derived_after": 10,
            "refute_before": 0, "refute_after": 1,
            "decision_events_total": 5,
        },
    }
    record.update(changes)
    return record


class ReadoutTest(unittest.TestCase):
    def test_empty_ledger_is_not_a_green_signal(self):
        self.assertIsNone(cr.analyse([])["latest"])

    def test_unexplained_equal_or_growing_stops_not_exits_with_failure(self):
        for after in (4, 5):
            with self.subTest(after=after):
                row = run(1)
                row["metrics"]["unexplained_after"] = after
                result = cr.analyse([row])["latest"]
                self.assertEqual(result["status"], "stop")
                self.assertIn("unexplained_not_decreased", result["stop_reasons"])

    def test_unexplained_decreased_and_refute_present_allows_continue(self):
        row = cr.analyse([run(1)])["latest"]
        self.assertEqual(row["status"], "continue")
        self.assertEqual(row["signals"]["three_rounds_no_new_hypothesis"], False)
        self.assertIsNone(row["signals"]["human_budget_exceeded"])

    def test_zero_refute_and_growth_even_without_unexplained_warning(self):
        item = run(1)
        item["metrics"].update(refute_after=0, support_non_derived_after=11)
        row = cr.analyse([item])["latest"]
        self.assertEqual(row["stop_reasons"], ["refute_zero_with_support_growth"])

    def test_derived_support_growth_does_not_trigger_growth(self):
        item = run(1)
        item["metrics"].update(refute_after=0, support_derived_after=2)
        self.assertEqual(cr.analyse([item])["latest"]["status"], "continue")

    def test_existing_refute_does_not_count_as_refute_zero(self):
        item = run(1)
        item["metrics"].update(refute_before=1, refute_after=1, support_non_derived_after=11)
        self.assertEqual(cr.analyse([item])["latest"]["status"], "continue")

    def test_three_consecutive_zero_hypotheses_stops_with_shuffled_input(self):
        report = cr.analyse([run(3), run(1), run(2)])
        self.assertEqual([r["round"] for r in report["rounds"]], [1, 2, 3])
        self.assertIn("three_rounds_no_new_hypothesis", report["latest"]["stop_reasons"])

    def test_nonconsecutive_or_missing_created_cannot_imply_streak(self):
        item = run(2)
        del item["hypotheses_created"]
        result = cr.analyse([run(1), item, run(3)])["latest"]
        self.assertIsNone(result["signals"]["three_rounds_no_new_hypothesis"])
        self.assertEqual(result["status"], "review_required")
        self.assertEqual(cr.analyse([run(1), run(3)])["latest"]["status"], "review_required")

    def test_nonzero_hypothesis_breaks_streak(self):
        rows = [run(1, hypotheses_created=1), run(2), run(3)]
        self.assertEqual(cr.analyse(rows)["latest"]["status"], "continue")

    def test_missing_snapshot_not_inferred_from_present_state(self):
        row = run(1)
        del row["metrics"]["unexplained_before"]
        result = cr.analyse([row])["latest"]
        self.assertEqual(result["status"], "review_required")
        self.assertIn("unexplained_not_decreased", result["unknown_signals"])
        self.assertIsNone(result["signals"]["unexplained_not_decreased"])

    def test_one_stop_and_one_missing_still_stop(self):
        row = run(1)
        row["metrics"].update(unexplained_after=4)
        del row["metrics"]["refute_before"]
        result = cr.analyse([row])["latest"]
        self.assertEqual(result["status"], "stop")
        self.assertIn("refute_zero_with_support_growth", result["unknown_signals"])

    def test_budget_is_optional_and_unknown_if_requested_but_no_tokens(self):
        result = cr.analyse([run(1)], max_tokens=100)["latest"]
        self.assertEqual(result["status"], "review_required")
        self.assertIsNone(result["signals"]["token_budget_exceeded"])
        row = run(1)
        row["metrics"]["tokens_total"] = 101
        self.assertIn("token_budget_exceeded", cr.analyse([row], max_tokens=100)["latest"]["stop_reasons"])
        self.assertIn("human_budget_exceeded", cr.analyse([run(1)], max_human_interventions=0)["latest"]["stop_reasons"])

    def test_intervention_rate_is_event_rate_not_time_rate(self):
        row = cr.analyse([run(1)])["latest"]
        self.assertEqual(row["snapshot"]["intervention_count_rate"], 0.8)
        old = run(2)
        del old["metrics"]["decision_events_total"]
        self.assertIsNone(cr.analyse([old])["latest"]["snapshot"]["intervention_count_rate"])

    def test_invalid_or_duplicate_records_fail_closed(self):
        cases = [[run(1), run(1)], [run(1), run(1, run_id="NEW")]]
        for rows in cases:
            with self.assertRaisesRegex(ValueError, "duplicate"):
                cr.analyse(rows)
        for change in (True, -1, 1.5):
            with self.subTest(change=change):
                bad = run(1, human_interventions=change)
                with self.assertRaises(ValueError):
                    cr.analyse([bad])
        bad = run(1)
        bad["metrics"]["decision_events_total"] = 0
        with self.assertRaisesRegex(ValueError, "decision_events_total"):
            cr.analyse([bad])
        with self.assertRaises(ValueError):
            cr.analyse([run(1)], max_tokens=-1)

    def test_cli_is_read_only_and_stop_is_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            row = run(3)
            row["metrics"]["unexplained_after"] = 5
            base = state / "runs.jsonl"
            base.write_text(json.dumps(row) + "\n", encoding="utf-8")
            before = base.read_bytes()
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(cr.main(["--state-dir", str(state), "--json"]), 0)
            self.assertEqual(json.loads(output.getvalue())["latest"]["status"], "stop")
            self.assertEqual(before, base.read_bytes())

    def test_cli_io_error_is_not_research_stop(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cr.main(["--state-dir", tmp]), 2)

    def test_existing_round2_is_stop_and_round1_history_not_fabricated(self):
        rows, errors = cr.vs.load_jsonl(ROOT / "state" / "runs.jsonl")
        self.assertFalse(errors)
        report = cr.analyse(rows)
        self.assertEqual(report["rounds"][0]["status"], "review_required")
        self.assertIn("unexplained_not_decreased", report["rounds"][1]["stop_reasons"])
        self.assertIsNone(report["rounds"][0]["snapshot"]["intervention_count_rate"])
        self.assertIsNone(report["rounds"][1]["snapshot"]["intervention_count_rate"])

    def test_round3_snapshot_records_both_stop_signals_without_backfill(self):
        rows, errors = cr.vs.load_jsonl(ROOT / "state" / "runs.jsonl")
        self.assertFalse(errors)
        report = cr.analyse(rows)
        round3 = next(r for r in report["rounds"] if r["run_id"] == "RUN-20261021-0f00")
        self.assertEqual(round3["stop_reasons"], [
            "unexplained_not_decreased", "refute_zero_with_support_growth"])
        self.assertEqual(round3["snapshot"]["intervention_count_rate"], 0.9474)
        self.assertEqual(round3["snapshot"]["support_non_derived"], [88, 89])
