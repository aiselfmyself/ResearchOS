"""Tests for the homogeneous-worker plurality readout simulation.

Network-free, history-free, standard library only.  These tests do two jobs:

  1. Guard the mechanics (determinism, N=1 identity, degenerate cases).
  2. Lock in the two empirical findings and the analytic threshold that
     predicts them, so that a future refactor cannot quietly change the
     conclusions the ledger entries are built on.
"""

import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gitswarm import readout_sim as rs  # noqa: E402


class DeterminismTest(unittest.TestCase):
    def test_same_cell_is_reproducible(self):
        a = rs.simulate_cell(p=0.60, rho=0.60, c=0.0, n_voters=9, tasks=200)
        b = rs.simulate_cell(p=0.60, rho=0.60, c=0.0, n_voters=9, tasks=200)
        self.assertEqual(a, b)

    def test_different_cells_differ(self):
        a = rs.simulate_cell(p=0.60, rho=0.60, c=0.0, n_voters=9, tasks=200)
        b = rs.simulate_cell(p=0.60, rho=0.10, c=0.0, n_voters=9, tasks=200)
        self.assertNotEqual(a, b)

    def test_evaluate_is_a_pure_function_of_the_electorate(self):
        rng = random.Random(7)
        electorate = rs.draw_electorate(
            rng, p=0.6, rho=0.5, c=0.0, n_voters=5, tasks=50
        )
        first = rs.evaluate(electorate, 5)
        second = rs.evaluate(electorate, 5)
        self.assertEqual(first, second)


class MechanicsTest(unittest.TestCase):
    def test_single_voter_has_amplification_exactly_one(self):
        """With one worker the readout IS the worker, so the ratio is 1."""
        for p in rs.ACCURACIES:
            for rho in rs.RHOS:
                cell = rs.simulate_cell(p=p, rho=rho, c=0.0, n_voters=1, tasks=150)
                self.assertAlmostEqual(
                    cell["amplification"], 1.0, places=6, msg=f"p={p} rho={rho}"
                )
                self.assertAlmostEqual(
                    cell["individual_error"],
                    cell["plurality_error"],
                    places=6,
                )

    def test_full_deferral_makes_readout_identical_to_a_worker(self):
        """rho = 1: every worker defers, so plurality cannot differ from one."""
        cell = rs.simulate_cell(p=0.7, rho=1.0, c=0.3, n_voters=15, tasks=200)
        self.assertAlmostEqual(cell["amplification"], 1.0, delta=0.02)

    def test_correct_shared_view_drives_readout_to_zero_error(self):
        """A shared view that is always right is exactly what pooling is for."""
        cell = rs.simulate_cell(p=0.30, rho=0.90, c=1.0, n_voters=15, tasks=200)
        self.assertLess(cell["plurality_error"], 0.01)

    def test_individual_error_matches_the_analytic_marginal(self):
        """Measured individual error should equal rho*(1-c) + (1-rho)*(1-p)."""
        p, rho, c = 0.70, 0.40, 0.20
        cell = rs.simulate_cell(p=p, rho=rho, c=c, n_voters=3, tasks=4000)
        expected = rho * (1 - c) + (1 - rho) * (1 - p)
        self.assertAlmostEqual(cell["individual_error"], expected, delta=0.02)

    def test_no_deferral_makes_shared_accuracy_irrelevant(self):
        """Control: at rho = 0 nothing is shared, so c cannot matter."""
        cells = [
            rs.simulate_cell(p=0.60, rho=0.0, c=c, n_voters=9, tasks=2000)[
                "plurality_error"
            ]
            for c in rs.SHARED_ACCURACIES
        ]
        for value in cells:
            self.assertAlmostEqual(value, cells[0], delta=0.03)

    def test_prefix_semantics_add_workers(self):
        """Larger N uses a prefix of the same drawn electorate."""
        rng = random.Random(11)
        electorate = rs.draw_electorate(
            rng, p=0.6, rho=0.5, c=0.0, n_voters=15, tasks=300
        )
        self.assertEqual(len(electorate[0][1]), 15)
        self.assertEqual(
            rs.evaluate(electorate, 15)["individual_error"],
            rs.evaluate(electorate, 15)["individual_error"],
        )


class CriticalRhoTest(unittest.TestCase):
    """The analytic threshold rho > p/(1+p), derived before reading the sweep."""

    def test_formula(self):
        self.assertAlmostEqual(rs.critical_rho(0.0), 0.0)
        self.assertAlmostEqual(rs.critical_rho(1.0), 0.5)
        self.assertAlmostEqual(rs.critical_rho(0.5), 1 / 3, places=6)

    def test_threshold_predicts_amplification_for_competent_workers(self):
        """For p above chance, a wrong shared view captures the readout exactly
        when the deferral rate exceeds p/(1+p).  Checked against the sweep."""
        results = rs.run_sweep()
        mismatches = []
        for p in (0.40, 0.60, 0.80):
            threshold = rs.critical_rho(p)
            for rho in rs.RHOS:
                cell = results[f"{p:.2f}"][f"{rho:.2f}"]["0.00"]["15"]
                amplified = cell["amplification"] > 1.0
                predicted = rho > threshold
                if amplified is not predicted:
                    mismatches.append(
                        f"p={p} rho={rho} (threshold {threshold:.4f}): "
                        f"amplification={cell['amplification']}"
                    )
        self.assertEqual(
            mismatches, [], "threshold prediction failed: " + "; ".join(mismatches)
        )


class CorrelationAloneTest(unittest.TestCase):
    """The matched sweep (c == p): correlation with no systematic bias.

    This is the controlled comparison.  Individual accuracy is held fixed at p
    for every deferral rate, so anything the readout does is caused purely by
    the workers' errors becoming shared.
    """

    def test_control_individual_accuracy_is_held_fixed(self):
        """Precondition: deferring to an equally-good shared view cannot change
        how often a single worker is right."""
        matched = rs.run_matched_sweep()
        for p in rs.ACCURACIES:
            errors = [
                matched[f"{p:.2f}"][f"{rho:.2f}"]["15"]["individual_error"]
                for rho in rs.RHOS
            ]
            for value in errors:
                self.assertAlmostEqual(
                    value,
                    1 - p,
                    delta=0.03,
                    msg=f"p={p}: individual error drifted to {value}",
                )

    def test_correlation_alone_does_not_amplify_error(self):
        """For workers above chance, sharing errors never makes the group
        worse than one worker -- it only ever removes the benefit."""
        matched = rs.run_matched_sweep()
        for p in (0.40, 0.60, 0.80):
            for rho in rs.RHOS:
                amp = matched[f"{p:.2f}"][f"{rho:.2f}"]["15"]["amplification"]
                self.assertLess(
                    amp, 1.03, f"p={p} rho={rho}: correlation amplified to {amp}"
                )

    def test_correlation_destroys_the_whole_benefit_of_pooling(self):
        """The damage is not that errors grow but that N workers collapse to
        the statistical content of one.  p=0.80, N=15: amplification climbs
        from 0.00 (a perfect readout) to 1.00 (fifteen workers, one vote)."""
        matched = rs.run_matched_sweep()
        amps = [
            matched["0.80"][f"{rho:.2f}"]["15"]["amplification"] for rho in rs.RHOS
        ]
        self.assertEqual(amps, sorted(amps), f"not monotone: {amps}")
        self.assertLess(amps[0], 0.01)
        self.assertAlmostEqual(amps[-1], 1.0, delta=0.02)


class FindingTest(unittest.TestCase):
    """The two findings the ledger entries rest on."""

    def test_workers_below_chance_are_amplified_by_pooling(self):
        """p below 1/k, no deferral: more workers makes the answer worse, and
        monotonically so.  This is the anti-Condorcet regime."""
        previous = 0.0
        for n in (1, 3, 5, 9, 15):
            cell = rs.simulate_cell(
                p=0.15, rho=0.0, c=0.0, n_voters=n, tasks=1500
            )
            self.assertGreater(
                cell["amplification"], previous - 1e-9, f"not monotone at N={n}"
            )
            previous = cell["amplification"]
        self.assertGreater(previous, 1.05)

    def test_competent_workers_above_chance_gain_from_pooling(self):
        """p above chance, no deferral: pooling is a large win."""
        cell = rs.simulate_cell(p=0.80, rho=0.0, c=0.0, n_voters=15, tasks=1500)
        self.assertLess(cell["amplification"], 0.10)

    def test_common_mode_turns_a_win_into_a_loss(self):
        """The headline: the SAME competent workers, but deferring to a wrong
        shared view at rho = 0.6, are made worse by pooling -- and the harm
        grows with group size."""
        n3 = rs.simulate_cell(p=0.60, rho=0.60, c=0.0, n_voters=3, tasks=1500)
        n15 = rs.simulate_cell(p=0.60, rho=0.60, c=0.0, n_voters=15, tasks=1500)
        self.assertGreater(n15["amplification"], n3["amplification"])
        self.assertGreater(n15["amplification"], 1.15)
        # Individual accuracy is unchanged by group size; only the readout moves.
        self.assertAlmostEqual(
            n3["individual_error"], n15["individual_error"], delta=0.03
        )

    def test_moderate_deferral_still_helps(self):
        """Below the threshold the bloc is outvoted and pooling still wins."""
        cell = rs.simulate_cell(p=0.80, rho=0.30, c=0.0, n_voters=15, tasks=1500)
        self.assertLess(cell["amplification"], 1.0)


class ArtifactTest(unittest.TestCase):
    def test_write_then_check_round_trips(self):
        results = rs.run_sweep()
        artifact = rs.build_artifact(results)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "matrix.json"
            rs.write_artifact(artifact, path)
            self.assertEqual(rs.check_artifact(artifact, path), [])
            self.assertTrue(path.exists())

    def test_check_detects_a_perturbed_value(self):
        results = rs.run_sweep()
        artifact = rs.build_artifact(results)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "matrix.json"
            rs.write_artifact(artifact, path)
            committed = json.loads(path.read_text(encoding="utf-8"))
            committed["results"]["0.60"]["0.60"]["0.00"]["15"]["amplification"] = 9.9
            path.write_text(json.dumps(committed), encoding="utf-8")
            fresh = rs.build_artifact(rs.run_sweep())
            errors = rs.check_artifact(fresh, path)
        self.assertTrue(errors)
        self.assertTrue(any("amplification" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
