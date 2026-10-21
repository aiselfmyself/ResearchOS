"""Tests for scripts/estimate_rho.py (common-mode term rho from paired errors).

rho -- the probability that a worker defers to a shared view -- has been a
free parameter in gitswarm/readout_sim.py. This script makes it estimable
from the correlated-error output that measure_agreement.py already produces.

Covered:
  * the core identity P(both wrong) - e^2 = rho^2 * c * (1-c) is inverted
    correctly for a case with a known closed-form answer;
  * the assumption-free lower bound never exceeds the c = p point estimate;
  * zero-error workers make rho unidentifiable rather than silently 0;
  * joint errors below the independence null report rho = 0, not a
    negative square root;
  * --power is monotonically decreasing in rho and reports sane sizes;
  * measure_agreement.py --json output is loaded correctly.
"""
from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import estimate_rho as er  # noqa: E402


class ClosedFormTest(unittest.TestCase):
    """A case whose answer is computable by hand.

    e = 0.20, c = p = 0.80.  excess = rho^2 * c * (1-c) = rho^2 * 0.16.
    With rho = 0.30: excess = 0.09 * 0.16 = 0.0144, and
    P(both wrong) = e^2 + excess = 0.04 + 0.0144 = 0.0544.
    """

    def test_round_trip(self):
        r = er.estimate(n=1000, p1=0.20, p2=0.20, both_wrong=0.0544)
        self.assertTrue(r["identifiable"])
        self.assertAlmostEqual(r["excess"], 0.0144, places=10)
        # 2*sqrt(0.0144) = 0.24 -- the bound that assumes nothing about c.
        self.assertAlmostEqual(r["rho_lower_bound"], 0.24, places=10)
        # sqrt(0.0144 / (0.8 * 0.2)) = sqrt(0.09) = 0.30 -- the c = p estimate.
        self.assertAlmostEqual(r["rho_point_estimate_c_eq_p"], 0.30, places=10)

    def test_lower_bound_is_weakest(self):
        """The assumption-free bound must never exceed the c = p estimate."""
        for excess_rho in (0.1, 0.25, 0.4, 0.7):
            e = 0.2
            excess = excess_rho ** 2 * 0.8 * 0.2
            r = er.estimate(n=10000, p1=e, p2=e, both_wrong=e * e + excess)
            self.assertLessEqual(
                r["rho_lower_bound"], r["rho_point_estimate_c_eq_p"] + 1e-12,
                msg=f"rho={excess_rho}: bound exceeded the point estimate",
            )


class DegenerateCaseTest(unittest.TestCase):
    def test_zero_errors_makes_rho_unidentifiable(self):
        r = er.estimate(n=8, p1=0.0, p2=0.0, both_wrong=0.0)
        self.assertFalse(r["identifiable"])
        self.assertIsNone(r["rho_lower_bound"])
        self.assertIsNone(r["rho_point_estimate_c_eq_p"])
        self.assertIn("no errors", r["reason"])

    def test_negative_excess_reports_zero_not_nan(self):
        r = er.estimate(n=100, p1=0.2, p2=0.2, both_wrong=0.01)
        self.assertTrue(r["identifiable"])
        self.assertLess(r["excess"], 0)
        self.assertEqual(r["rho_lower_bound"], 0.0)
        self.assertEqual(r["rho_point_estimate_c_eq_p"], 0.0)
        self.assertTrue(math.isfinite(r["rho_lower_bound"]))

    def test_detection_limit_is_positive(self):
        r = er.estimate(n=100, p1=0.2, p2=0.2, both_wrong=0.05)
        self.assertGreater(r["detection_limit_rho_c_eq_p"], 0)

    def test_independence_gives_zero(self):
        """Exactly the independent rate must not be read as correlation."""
        r = er.estimate(n=100000, p1=0.2, p2=0.2, both_wrong=0.04)
        self.assertAlmostEqual(r["excess"], 0.0, places=12)
        self.assertEqual(r["rho_lower_bound"], 0.0)


class PowerTest(unittest.TestCase):
    def test_required_n_decreases_with_rho(self):
        sizes = [er.required_n(0.20, rho)["required_n"] for rho in (0.1, 0.2, 0.3, 0.5)]
        self.assertEqual(sizes, sorted(sizes, reverse=True))

    def test_required_n_is_positive(self):
        self.assertGreater(er.required_n(0.20, 0.3)["required_n"], 0)

    def test_zero_rho_is_undefined(self):
        self.assertIsNone(er.required_n(0.20, 0.0)["required_n"])

    def test_zero_error_rate_is_undefined(self):
        self.assertIsNone(er.required_n(0.0, 0.3)["required_n"])

    def test_magnitude_is_plausible(self):
        """Detecting a moderate rho needs thousands of items, not dozens.

        This is the point of the instrument: it stops anyone from reading
        rho off a handful of paired judgements.
        """
        self.assertGreater(er.required_n(0.20, 0.3)["required_n"], 500)


class LoadAgreementTest(unittest.TestCase):
    def test_loads_measure_agreement_json(self):
        blob = {
            "schema": "agreement-measurement/v1",
            "truth_analysis": {
                "n_joint_decided": 500,
                "p1": 0.2, "p2": 0.2,
                "p_both_wrong": 0.0544,
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.json"
            path.write_text(json.dumps(blob), encoding="utf-8")
            r = er.load_agreement(path)
        self.assertEqual(r["n_joint_decided"], 500)
        self.assertAlmostEqual(r["rho_point_estimate_c_eq_p"], 0.30, places=10)

    def test_missing_truth_analysis_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.json"
            path.write_text(json.dumps({"schema": "agreement-measurement/v1"}),
                            encoding="utf-8")
            with self.assertRaises(ValueError):
                er.load_agreement(path)


if __name__ == "__main__":
    unittest.main()
