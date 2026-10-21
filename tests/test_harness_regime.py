"""Tests for scripts/harness_regime.py (the "does the harness reorder?" regime).

Two papers in the ledger appear to contradict each other: [8] finds ranking
reversals in 6 of 9 combinations, [9] finds the harness affects stability but
not ordering. This script encodes the reconciliation -- both are consistent
with a threshold at R = (model spread) / (harness spread) ~ 1 -- and, as
importantly, states that it rests on two data points and is confounded with
task domain.

Covered:
  * the three unit conversions (spread / variance / HV-MV) agree where they
    should;
  * R < 1 predicts reordering, R > 1 predicts stability only;
  * the built-in reference cases all agree with the threshold;
  * degenerate inputs return None instead of dividing by zero;
  * the two papers really do sit on opposite sides of 1.
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import harness_regime as hr  # noqa: E402


class UnitConversionTest(unittest.TestCase):
    def test_hv_mv_is_inverted_and_rooted(self):
        """[8] reports a variance ratio, so R = 1/sqrt(HV/MV)."""
        self.assertAlmostEqual(hr.from_hv_mv(7.80), 1.0 / math.sqrt(7.80), places=12)

    def test_variances_are_rooted_before_dividing(self):
        self.assertAlmostEqual(
            hr.from_variances(model_var=4.0, harness_var=1.0), 2.0, places=12
        )

    def test_spreads_divide_directly(self):
        self.assertAlmostEqual(hr.from_spreads(0.237, 0.055), 0.237 / 0.055, places=12)

    def test_variance_and_spread_forms_agree(self):
        # spread 2 vs 1  ==  variance 4 vs 1
        self.assertAlmostEqual(
            hr.from_spreads(2.0, 1.0),
            hr.from_variances(4.0, 1.0),
            places=12,
        )

    def test_hv_mv_matches_the_variance_form(self):
        # HV/MV = 7.80 means harness_var / model_var = 7.80.
        self.assertAlmostEqual(
            hr.from_hv_mv(7.80),
            hr.from_variances(model_var=1.0, harness_var=7.80),
            places=12,
        )


class RegimeTest(unittest.TestCase):
    def test_below_one_predicts_reordering(self):
        r = hr.regime(0.36)
        self.assertTrue(r["predicts_reordering"])
        self.assertEqual(r["dominant"], "harness")

    def test_above_one_predicts_stability_only(self):
        r = hr.regime(4.3)
        self.assertFalse(r["predicts_reordering"])
        self.assertEqual(r["dominant"], "model")

    def test_exactly_one_is_model_side(self):
        """The boundary itself: >= 1 means the model spread is not smaller."""
        self.assertFalse(hr.regime(1.0)["predicts_reordering"])


class ReferenceCaseTest(unittest.TestCase):
    def test_all_reference_cases_agree_with_the_threshold(self):
        rows = hr.check_reference(hr.REFERENCE)
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertTrue(row["consistent"], msg=row["label"])

    def test_the_two_papers_sit_on_opposite_sides(self):
        rows = hr.check_reference(hr.REFERENCE)
        paper8 = rows[0]
        paper9 = rows[1]
        self.assertLess(paper8["R"], 1.0)
        self.assertGreater(paper9["R"], 1.0)
        self.assertTrue(paper8["observed_reordering"])
        self.assertFalse(paper9["observed_reordering"])

    def test_reference_cites_its_evidence(self):
        for row in hr.check_reference(hr.REFERENCE):
            self.assertTrue(row["evidence"].startswith("EVD-"))


class DegenerateInputTest(unittest.TestCase):
    def test_zero_harness_variance(self):
        self.assertIsNone(hr.from_variances(1.0, 0.0))

    def test_zero_harness_spread(self):
        self.assertIsNone(hr.from_spreads(0.237, 0.0))

    def test_non_positive_hv_mv(self):
        self.assertIsNone(hr.from_hv_mv(0.0))
        self.assertIsNone(hr.from_hv_mv(-1.0))


if __name__ == "__main__":
    unittest.main()
