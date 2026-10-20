"""Regression tests for scripts/measure_agreement.py.

All expectations are fixed on SYNTHETIC data written to temporary
files (the 2026-10-19 audit lesson: tests must not depend on this
repository's own history or on other sessions' artefacts).

The four patterns the experiment doc requires are pinned here:

  * perfect agreement      -> agreement_rate 1.0, kappa 1.0
  * perfect disagreement   -> agreement_rate 0.0, kappa 0.0
  * independent errors     -> lift == 1.0 (P(both wrong) == p1*p2)
  * correlated errors      -> lift == 2.0 (co-errors above chance)

plus the abstention rule (unknown/null is neither right nor wrong
and must be excluded from the error-rate denominators, or lift is
distorted), the comparison rules (tolerance / normalization /
order-insensitivity), and the CLI contract (exit code always 0).
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

import measure_agreement as ma  # noqa: E402


# --------------------------------------------------------------------------
# Fixture helpers
# --------------------------------------------------------------------------
def item(item_id: str, value, label: str = "test item") -> dict:
    return {
        "id": item_id,
        "label": label,
        "value": value,
        "location": "fixture",
        "confidence": "high",
    }


def write(tmp: str, name: str, items: list) -> Path:
    path = Path(tmp) / name
    payload = {"session": "fixture", "items": items}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def run_measure(tmp: str, a_items, b_items, truth_items=None, tol=ma.DEFAULT_TOL):
    a_path = write(tmp, "a.json", a_items)
    b_path = write(tmp, "b.json", b_items)
    truth_path = (
        write(tmp, "truth.json", truth_items) if truth_items is not None else None
    )
    return ma.measure(a_path, b_path, truth_path, tol)


# --------------------------------------------------------------------------
# Comparison rules
# --------------------------------------------------------------------------
class ComparisonRuleTest(unittest.TestCase):
    def test_numeric_values_compare_within_tolerance(self) -> None:
        self.assertTrue(ma.values_equal(1.0, 1.0000001))
        self.assertFalse(ma.values_equal(1.0, 1.0001))
        self.assertTrue(ma.values_equal(1.0, 1.0001, tol=1e-3))
        self.assertTrue(ma.values_equal(7, 7))  # int vs int
        self.assertTrue(ma.values_equal(7, 7.0))  # int vs float

    def test_bool_never_equals_number(self) -> None:
        self.assertFalse(ma.values_equal(True, 1))
        self.assertTrue(ma.values_equal(True, True))
        self.assertFalse(ma.values_equal(True, "true"))

    def test_strings_normalize_whitespace_and_case(self) -> None:
        self.assertTrue(
            ma.values_equal("  Agora:  A Benchmark ", "agora: a benchmark")
        )
        self.assertFalse(ma.values_equal("Agora", "DuoDiscover"))

    def test_lists_compare_order_insensitively_as_multisets(self) -> None:
        self.assertTrue(ma.values_equal(["A", "B", "C"], ["c", "a", "b"]))
        self.assertFalse(ma.values_equal(["A", "B"], ["A", "B", "B"]))
        self.assertFalse(ma.values_equal(["A", "B"], ["A", "C"]))

    def test_abstentions_are_null_and_unknown_only(self) -> None:
        for abstention in (None, "unknown", "Unknown", " UNKNOWN "):
            self.assertTrue(ma.is_abstention(abstention), abstention)
        # "none" is a real answer (playbook A5: ライセンス無ければ "none")
        self.assertFalse(ma.is_abstention("none"))
        self.assertFalse(ma.is_abstention(""))
        self.assertFalse(ma.is_abstention(0))

    def test_type_mismatch_is_a_disagreement(self) -> None:
        # No silent coercion: "42" vs 42 is a real extraction difference.
        self.assertFalse(ma.values_equal("42", 42))


# --------------------------------------------------------------------------
# Verdict taxonomy
# --------------------------------------------------------------------------
class VerdictTest(unittest.TestCase):
    def test_agree_disagree_and_both_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = run_measure(
                tmp,
                [item("A1", "same"), item("A2", "x"), item("A3", None)],
                [item("A1", "SAME"), item("A2", "y"), item("A3", "unknown")],
            )
        verdicts = {i["id"]: i["verdict"] for i in report["items"]}
        self.assertEqual(verdicts["A1"], "agree")
        self.assertEqual(verdicts["A2"], "disagree")
        self.assertEqual(verdicts["A3"], "both-missing")

    def test_one_sided_abstention_is_disagree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = run_measure(
                tmp, [item("A1", "value")], [item("A1", "unknown")]
            )
        self.assertEqual(report["items"][0]["verdict"], "disagree")
        self.assertIn("abstained", report["items"][0]["note"])

    def test_coverage_gaps_get_their_own_verdicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = run_measure(tmp, [item("x1", 1)], [item("y1", 1)])
        verdicts = {i["id"]: i["verdict"] for i in report["items"]}
        self.assertEqual(verdicts["x1"], "a-only")
        self.assertEqual(verdicts["y1"], "b-only")
        # coverage gaps count against the agreement rate
        self.assertEqual(report["agreement_rate"], 0.0)

    def test_truth_only_item_is_both_missing_and_in_denominator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = run_measure(
                tmp,
                [item("i1", "v")],
                [item("i1", "v")],
                truth_items=[item("i1", "v"), item("i2", "v")],
            )
        verdicts = {i["id"]: i["verdict"] for i in report["items"]}
        self.assertEqual(verdicts["i1"], "agree")
        self.assertEqual(verdicts["i2"], "both-missing")
        self.assertEqual(report["agreement_rate"], 0.5)


# --------------------------------------------------------------------------
# The four pinned patterns (experiment doc completion condition)
# --------------------------------------------------------------------------
class PinnedPatternTest(unittest.TestCase):
    def test_perfect_agreement(self) -> None:
        items = [
            item("A1", "Agora: A Benchmark"),
            item("A2", 7),
            item("A3", "S. Researcher"),
            item("E1", True),
            item("B2", ["MMLU", "GSM8K", "ARC"]),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            report = run_measure(tmp, items, list(items))
        self.assertEqual(report["agreement_rate"], 1.0)
        self.assertEqual(
            report["verdict_counts"],
            {
                "agree": 5,
                "disagree": 0,
                "both-missing": 0,
                "a-only": 0,
                "b-only": 0,
            },
        )
        self.assertEqual(report["cohens_kappa"]["kappa"], 1.0)

    def test_perfect_disagreement(self) -> None:
        a_items = [
            item("A1", "alpha"),
            item("A2", 1),
            item("A3", "x"),
            item("E1", True),
            item("B2", ["p", "q"]),
        ]
        b_items = [
            item("A1", "beta"),
            item("A2", 2),
            item("A3", "y"),
            item("E1", False),
            item("B2", ["r", "s"]),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            report = run_measure(tmp, a_items, b_items)
        self.assertEqual(report["agreement_rate"], 0.0)
        self.assertEqual(report["verdict_counts"]["disagree"], 5)
        # disjoint value sets -> chance agreement is zero -> kappa 0
        self.assertEqual(report["cohens_kappa"]["kappa"], 0.0)

    def test_independent_errors_give_lift_one(self) -> None:
        # 8 items. A errs on {1,2,5,6}, B errs on {1,3,5,7}:
        # overlap {1,5} = 2 items = 1/4, exactly p1*p2 = 1/2*1/2.
        truth = [item(f"i{i}", f"T{i}") for i in range(1, 9)]
        a_items, b_items = [], []
        for i in range(1, 9):
            a_wrong, b_wrong = i in (1, 2, 5, 6), i in (1, 3, 5, 7)
            a_items.append(item(f"i{i}", f"AW{i}" if a_wrong else f"T{i}"))
            b_items.append(item(f"i{i}", f"BW{i}" if b_wrong else f"T{i}"))
        with tempfile.TemporaryDirectory() as tmp:
            report = run_measure(tmp, a_items, b_items, truth)
        analysis = report["truth_analysis"]
        self.assertEqual(analysis["n_joint_decided"], 8)
        self.assertEqual(analysis["p1"], 0.5)
        self.assertEqual(analysis["p2"], 0.5)
        self.assertEqual(analysis["p_both_wrong"], 0.25)
        self.assertEqual(analysis["expected_p_both_wrong_if_independent"], 0.25)
        self.assertEqual(analysis["lift"], 1.0)
        self.assertIn("independence", analysis["reading"])

    def test_correlated_errors_give_lift_two(self) -> None:
        # Both workers fail on the SAME four items: co-error rate
        # 1/2 vs independence null 1/4 -> lift 2.
        truth = [item(f"i{i}", f"T{i}") for i in range(1, 9)]
        a_items, b_items = [], []
        for i in range(1, 9):
            wrong = i in (1, 2, 3, 4)
            a_items.append(item(f"i{i}", f"AW{i}" if wrong else f"T{i}"))
            b_items.append(item(f"i{i}", f"BW{i}" if wrong else f"T{i}"))
        with tempfile.TemporaryDirectory() as tmp:
            report = run_measure(tmp, a_items, b_items, truth)
        analysis = report["truth_analysis"]
        self.assertEqual(analysis["n_both_wrong"], 4)
        self.assertEqual(analysis["p1"], 0.5)
        self.assertEqual(analysis["p2"], 0.5)
        self.assertEqual(analysis["p_both_wrong"], 0.5)
        self.assertEqual(analysis["expected_p_both_wrong_if_independent"], 0.25)
        self.assertEqual(analysis["lift"], 2.0)
        self.assertIn("positively correlated", analysis["reading"])


# --------------------------------------------------------------------------
# Abstentions and the error-rate denominators
# --------------------------------------------------------------------------
class AbstentionExclusionTest(unittest.TestCase):
    def test_unknown_is_excluded_from_error_denominators(self) -> None:
        # i1 both correct, i2 both wrong, i3 A right / B wrong,
        # i4 A abstains / B wrong, i5 both abstain.
        # Joint-decided subset = {i1,i2,i3}: p1 = 1/3, p2 = 2/3,
        # P(both wrong) = 1/3, null = 2/9, lift = 1.5.
        # Counting the abstentions as errors would give p1 = 1/4,
        # p2 = 3/4, P = 1/4, lift = 1.333... -- the distortion
        # this rule exists to prevent.
        truth = [item(f"i{i}", f"T{i}") for i in range(1, 6)]
        a_values = ["T1", "AW2", "T3", "unknown", "unknown"]
        b_values = ["T1", "BW2", "BW3", "BW4", "unknown"]
        a_items = [item(f"i{i}", v) for i, v in enumerate(a_values, 1)]
        b_items = [item(f"i{i}", v) for i, v in enumerate(b_values, 1)]
        with tempfile.TemporaryDirectory() as tmp:
            report = run_measure(tmp, a_items, b_items, truth)
        analysis = report["truth_analysis"]
        self.assertEqual(analysis["n_truth_known"], 5)
        self.assertEqual(analysis["n_joint_decided"], 3)
        self.assertEqual(analysis["p1"], round(1 / 3, 6))
        self.assertEqual(analysis["p2"], round(2 / 3, 6))
        self.assertEqual(analysis["p_both_wrong"], round(1 / 3, 6))
        self.assertEqual(analysis["lift"], 1.5)
        # context rates over each worker's own decided items:
        # A decided {i1,i2,i3} (wrong on i2), B decided {i1..i4}
        # (wrong on i2, i3, i4)
        self.assertEqual(analysis["worker_a"]["error_rate_all_decided"], round(1 / 3, 6))
        self.assertEqual(analysis["worker_b"]["error_rate_all_decided"], 0.75)
        self.assertEqual(analysis["worker_a"]["unknown"], 2)
        self.assertEqual(analysis["worker_b"]["unknown"], 1)
        # verdicts reflect the abstentions
        verdicts = {i["id"]: i["verdict"] for i in report["items"]}
        self.assertEqual(verdicts["i4"], "disagree")
        self.assertEqual(verdicts["i5"], "both-missing")

    def test_unknown_truth_excludes_the_item(self) -> None:
        # The paper does not state the answer: the item must leave
        # the truth analysis entirely, not count as an error.
        truth = [item("i1", "T1"), item("i2", None)]
        a_items = [item("i1", "T1"), item("i2", "whatever")]
        b_items = [item("i1", "T1"), item("i2", "whatever")]
        with tempfile.TemporaryDirectory() as tmp:
            report = run_measure(tmp, a_items, b_items, truth)
        analysis = report["truth_analysis"]
        self.assertEqual(analysis["n_truth_known"], 1)
        self.assertEqual(analysis["n_joint_decided"], 1)
        self.assertEqual(analysis["p1"], 0.0)
        self.assertIsNone(analysis["lift"])  # no errors -> undefined


# --------------------------------------------------------------------------
# Cohen's kappa
# --------------------------------------------------------------------------
class KappaTest(unittest.TestCase):
    def test_kappa_zero_when_one_worker_never_varies(self) -> None:
        # Classic kappa trap: 60% raw agreement, but A always says
        # "x", so chance agreement is also 0.6 -> kappa 0.
        a_items = [item(f"i{i}", "x") for i in range(1, 11)]
        b_items = [item(f"i{i}", "x" if i <= 6 else "y") for i in range(1, 11)]
        with tempfile.TemporaryDirectory() as tmp:
            report = run_measure(tmp, a_items, b_items)
        self.assertEqual(report["agreement_rate"], 0.6)
        self.assertEqual(report["cohens_kappa"]["po"], 0.6)
        self.assertEqual(report["cohens_kappa"]["pe"], 0.6)
        self.assertEqual(report["cohens_kappa"]["kappa"], 0.0)

    def test_kappa_hand_computed_example(self) -> None:
        # A = [x,x,x,y,y], B = [x,x,y,y,y]:
        # po = 4/5 = 0.8, pe = (3/5)(2/5)+(2/5)(3/5) = 0.48,
        # kappa = 0.32/0.52 = 8/13.
        a_items = [item(f"i{i}", v) for i, v in enumerate(["x", "x", "x", "y", "y"], 1)]
        b_items = [item(f"i{i}", v) for i, v in enumerate(["x", "x", "y", "y", "y"], 1)]
        with tempfile.TemporaryDirectory() as tmp:
            report = run_measure(tmp, a_items, b_items)
        self.assertEqual(report["cohens_kappa"]["po"], 0.8)
        self.assertEqual(report["cohens_kappa"]["pe"], 0.48)
        self.assertAlmostEqual(report["cohens_kappa"]["kappa"], 8 / 13, places=6)

    def test_perfect_negative_kappa(self) -> None:
        a_items = [item("i1", "x"), item("i2", "y")]
        b_items = [item("i1", "y"), item("i2", "x")]
        with tempfile.TemporaryDirectory() as tmp:
            report = run_measure(tmp, a_items, b_items)
        self.assertEqual(report["cohens_kappa"]["kappa"], -1.0)

    def test_kappa_null_when_nothing_is_jointly_rated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = run_measure(
                tmp, [item("i1", "unknown")], [item("i1", None)]
            )
        self.assertEqual(report["items"][0]["verdict"], "both-missing")
        self.assertIsNone(report["cohens_kappa"]["kappa"])

    def test_kappa_respects_numeric_tolerance(self) -> None:
        a_items = [item("i1", 1.0), item("i2", 2.0)]
        b_items = [item("i1", 1.0000001), item("i2", 2.0001)]
        with tempfile.TemporaryDirectory() as tmp:
            strict = run_measure(tmp, a_items, b_items)  # default 1e-6
            loose = run_measure(tmp, a_items, b_items, tol=1e-3)
        self.assertEqual(strict["agreement_rate"], 0.5)
        self.assertEqual(loose["agreement_rate"], 1.0)


# --------------------------------------------------------------------------
# CLI contract
# --------------------------------------------------------------------------
class CliTest(unittest.TestCase):
    def _run(self, argv, tmp):
        a_path = write(tmp, "a.json", [item("A1", "v"), item("A2", 1)])
        b_path = write(tmp, "b.json", [item("A1", "v"), item("A2", 2)])
        truth_path = write(tmp, "truth.json", [item("A1", "v"), item("A2", 1)])
        out, err = io.StringIO(), io.StringIO()
        argv_list = ["--a", str(a_path), "--b", str(b_path)]
        if argv.get("truth"):
            argv_list += ["--truth", str(truth_path)]
        if argv.get("json"):
            argv_list += ["--json"]
        if "tol" in argv:
            argv_list += ["--tol", str(argv["tol"])]
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ma.main(argv_list)
        return code, out.getvalue(), err.getvalue()

    def test_exit_code_is_always_zero_and_json_parses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, stdout, _ = self._run({"json": True, "truth": True}, tmp)
        self.assertEqual(code, 0)
        report = json.loads(stdout)
        self.assertEqual(report["schema"], "agreement-measurement/v1")
        self.assertEqual(report["agreement_rate"], 0.5)
        self.assertIn("lift", report["truth_analysis"])

    def test_human_output_reports_the_headline_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, stdout, _ = self._run({"truth": True}, tmp)
        self.assertEqual(code, 0)
        for token in ("Agreement rate", "Cohen's kappa", "lift", "P(both wrong)"):
            self.assertIn(token, stdout)

    def test_missing_input_still_exits_zero(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ma.main(
                [
                    "--a",
                    "/nonexistent/a.json",
                    "--b",
                    "/nonexistent/b.json",
                ]
            )
        self.assertEqual(code, 0)
        self.assertIn("error", err.getvalue().lower())

    def test_tol_flag_changes_the_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a_path = write(tmp, "a.json", [item("A1", 1.0)])
            b_path = write(tmp, "b.json", [item("A1", 1.0001)])
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    ma.main(["--a", str(a_path), "--b", str(b_path), "--json"]),
                    0,
                )
            self.assertEqual(json.loads(out.getvalue())["agreement_rate"], 0.0)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    ma.main(
                        [
                            "--a",
                            str(a_path),
                            "--b",
                            str(b_path),
                            "--tol",
                            "1e-3",
                            "--json",
                        ]
                    ),
                    0,
                )
            self.assertEqual(json.loads(out.getvalue())["agreement_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
