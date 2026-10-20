"""Regression tests for the ResearchOS minimal core.

Design rule learned from the 2026-10-19 audit cycle: tests must NOT depend
on this repository's own git history (no hard-coded commit counts or SHAs)
and must NOT depend on frozen governance machinery. History-dependent
behaviour (readout scoping) is tested against *synthetic* temporary
repositories instead.

Covered:
  * benchmark artifact reproducibility (fresh execution == committed file),
    including solver-code hash binding that makes hand-written artifacts
    fail;
  * solver sanity properties on the fixed 30-city TSP seeds;
  * readout counting / nomination / scoping on a synthetic repo;
  * research-ledger validation, including the audit's citation corrections.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import validate_state  # noqa: E402
from gitswarm import readout  # noqa: E402
from gitswarm.benchmarks.benchmark import (  # noqa: E402
    ARTIFACT,
    SEEDS,
    SOLVERS,
    build_artifact,
    check_artifact,
    run_benchmarks,
)
from gitswarm.problem import (  # noqa: E402
    calculate_tour_distance,
    generate_cities,
    is_valid_tour,
)
from gitswarm.solvers import (  # noqa: E402
    greedy,
    random_search,
    simulated_annealing,
    two_opt,
)


class BenchmarkReproducibilityTest(unittest.TestCase):
    def test_artifact_matches_fresh_execution(self) -> None:
        """The committed matrix must equal a fresh run (anti-handwriting)."""
        summary, per_seed = run_benchmarks()
        artifact = build_artifact(summary, per_seed)
        self.assertEqual(check_artifact(artifact), [])

    def test_artifact_declares_reproducibility_metadata(self) -> None:
        committed = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        meta = committed["_meta"]
        self.assertGreaterEqual(meta["schema_version"], 2)
        self.assertEqual(meta["problem"]["seeds"], SEEDS)
        self.assertEqual(meta["problem"]["n_cities"], 30)
        self.assertEqual(meta["problem"]["random_iterations"], 500)
        self.assertEqual(set(meta["solver_sha256"]), set(SOLVERS))

    def test_artifact_solver_hashes_match_committed_code(self) -> None:
        """Solver hashes bind the numbers to the committed solver files."""
        committed = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        filenames = {
            "greedy": "greedy.py",
            "random": "random_search.py",
            "two_opt": "two_opt.py",
            "simulated_annealing": "simulated_annealing.py",
        }
        for solver, filename in filenames.items():
            code = (ROOT / "gitswarm" / "solvers" / filename).read_bytes()
            self.assertEqual(
                hashlib.sha256(code).hexdigest(),
                committed["_meta"]["solver_sha256"][solver],
                solver,
            )


class SolverSanityTest(unittest.TestCase):
    def test_all_solvers_return_valid_tours(self) -> None:
        for seed in SEEDS:
            cities = generate_cities(30, seed=seed)
            tours = {
                "greedy": greedy.solve(cities),
                "random": random_search.solve(cities, iterations=500, seed=seed),
                "two_opt": two_opt.solve(cities),
                "simulated_annealing": simulated_annealing.solve(
                    cities, seed=seed, temp=150.0, cooling=0.995, steps=5000
                ),
            }
            for name, tour in tours.items():
                self.assertTrue(
                    is_valid_tour(tour, 30), f"{name} seed {seed}"
                )

    def test_solver_quality_ordering_on_fixed_seeds(self) -> None:
        """Deterministic property: SA <= 2-opt < greedy < random (means)."""
        summary, _ = run_benchmarks()
        mean = {name: summary[name]["mean_distance"] for name in SOLVERS}
        self.assertLessEqual(mean["simulated_annealing"], mean["two_opt"])
        self.assertLess(mean["two_opt"], mean["greedy"])
        self.assertLess(mean["greedy"], mean["random"])

    def test_two_opt_never_worse_than_greedy_per_seed(self) -> None:
        for seed in SEEDS:
            cities = generate_cities(30, seed=seed)
            g = calculate_tour_distance(greedy.solve(cities), cities)
            t = calculate_tour_distance(two_opt.solve(cities), cities)
            self.assertLessEqual(t, g, f"seed {seed}")


def _git(cwd: str, *args: str) -> str:
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
    )
    return subprocess.check_output(
        ["git", *args], cwd=cwd, env=env, text=True
    ).strip()


def _commit(cwd: str, relpath: str, subject: str, body: str = "") -> str:
    target = Path(cwd, relpath)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(subject, encoding="utf-8")
    _git(cwd, "add", "-A")
    args = ["commit", "-q", "-m", subject]
    if body:
        args += ["-m", body]
    _git(cwd, *args)
    return _git(cwd, "rev-parse", "HEAD")


class ReadoutSyntheticTest(unittest.TestCase):
    """readout behaviour on a synthetic repo (no dependence on real history)."""

    def _build_swarm(self, tmp: str) -> dict:
        _git(tmp, "init", "-q", "-b", "main")
        _commit(tmp, "README.md", "chore: initial commit")
        w1 = _commit(
            tmp,
            "gitswarm/w1.txt",
            "[Worker-01] explore: greedy baseline",
            "Action-Type: explore\nOutcome: positive",
        )
        w2 = _commit(
            tmp,
            "gitswarm/w2.txt",
            "[Worker-02] experiment: random search",
            f"Action-Type: experiment\nOutcome: negative\nInformed-By: {w1[:7]}",
        )
        w3 = _commit(
            tmp,
            "gitswarm/w3.txt",
            "[Worker-03] refine: local search",
            f"Action-Type: refine\nOutcome: positive\nInformed-By: {w2[:7]}",
        )
        w4 = _commit(
            tmp,
            "gitswarm/w4.txt",
            "[Worker-04] nominate: pick winner",
            f"Action-Type: nominate\nNomination: {w3[:7]}",
        )
        # A worker commit outside the gitswarm/ scope (must be excludable).
        _commit(
            tmp,
            "state/note.md",
            "[Worker-05] explore: unrelated note",
            "Action-Type: explore\nOutcome: positive",
        )
        return {"w1": w1, "w2": w2, "w3": w3, "w4": w4}

    def test_counts_votes_and_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            shas = self._build_swarm(tmp)
            result = readout.analyze_gitswarm(cwd=Path(tmp))
            assert result is not None
            self.assertEqual(result["total_worker_commits"], 5)
            # nominate commits are not candidates
            self.assertEqual(result["candidate_commits"], 4)
            self.assertEqual(result["winning_candidate_sha"], shas["w3"][:7])
            self.assertEqual(
                result["vote_tallies"], {shas["w3"][:7]: 1}
            )
            metrics = result["compounding_metrics"]
            # W1 <- W2 <- W3 chain: every candidate is built upon except W5.
            self.assertEqual(metrics["negative_results_total"], 1)
            self.assertEqual(metrics["negative_results_reused"], 1)
            self.assertEqual(metrics["negative_reuse_rate_pct"], 100.0)

    def test_path_scope_excludes_unrelated_workers(self) -> None:
        """The 2026-10-19 audit lesson: unscoped readout drifts."""
        with tempfile.TemporaryDirectory() as tmp:
            self._build_swarm(tmp)
            scoped = readout.analyze_gitswarm(paths=["gitswarm"], cwd=Path(tmp))
            unscoped = readout.analyze_gitswarm(cwd=Path(tmp))
            assert scoped is not None and unscoped is not None
            self.assertEqual(scoped["total_worker_commits"], 4)
            self.assertEqual(unscoped["total_worker_commits"], 5)

    def test_empty_history_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _git(tmp, "init", "-q", "-b", "main")
            _commit(tmp, "README.md", "chore: initial commit")
            self.assertIsNone(readout.analyze_gitswarm(cwd=Path(tmp)))


class ResearchStateTest(unittest.TestCase):
    def test_bundled_state_passes_validation(self) -> None:
        report = validate_state.run_all_checks(ROOT)
        self.assertEqual(report["errors"], [], msg="\n".join(report["errors"]))

    def test_corrected_first_authors(self) -> None:
        """Audit correction 2026-10-19: first authors must stay fixed."""
        records, errors = validate_state.load_jsonl(ROOT / "state/sources.jsonl")
        self.assertEqual(errors, [])
        authors = {r["source_id"]: r["authors"] for r in records}
        self.assertEqual(authors["SRC-001"][0], "Qizheng Zhang")
        self.assertEqual(authors["SRC-003"][0], "Shubham Agarwal")
        self.assertEqual(len(authors["SRC-002"]), 14)

    def test_every_evidence_declares_quote_type(self) -> None:
        allowed = {
            "verbatim",
            "verbatim_excerpts",
            "measurement",
            "metadata_comparison",
            "fulltext_check",
            "code_inspection",
        }
        records, _ = validate_state.load_jsonl(ROOT / "state/evidence.jsonl")
        self.assertGreater(len(records), 0)
        for evidence in records:
            self.assertIn("quote_type", evidence, evidence["evidence_id"])
            self.assertIn(evidence["quote_type"], allowed)

    def test_audit_claim_statuses(self) -> None:
        records, _ = validate_state.load_jsonl(ROOT / "state/claims.jsonl")
        claims = {r["claim_id"]: r for r in records}
        for claim_id in ("CLM-004", "CLM-005", "CLM-006", "CLM-007"):
            self.assertIn(claim_id, claims)
        self.assertEqual(claims["CLM-003"]["status"], "candidate")


class ValidatorUnitTest(unittest.TestCase):
    def _evidence_schema(self) -> dict:
        return json.loads(
            (ROOT / "schemas" / "evidence.json").read_text(encoding="utf-8")
        )

    def test_invalid_enum_is_rejected(self) -> None:
        bad = {
            "evidence_id": "EVD-X",
            "source_id": "SRC-001",
            "excerpt": "x",
            "interpretation": "y",
            "confidence": "banana",
        }
        errors = validate_state.validate_record(bad, self._evidence_schema(), "E")
        self.assertTrue(any("confidence" in e for e in errors), errors)

    def test_missing_required_is_rejected(self) -> None:
        bad = {"evidence_id": "EVD-X", "source_id": "SRC-001"}
        errors = validate_state.validate_record(bad, self._evidence_schema(), "E")
        self.assertTrue(any("excerpt" in e for e in errors), errors)

    def test_invalid_type_is_rejected(self) -> None:
        schema = json.loads(
            (ROOT / "schemas" / "source.json").read_text(encoding="utf-8")
        )
        bad = {
            "source_id": "SRC-X",
            "title": "t",
            "authors": "not-a-list",
            "year": "2026",
            "url": "u",
            "type": "paper",
        }
        errors = validate_state.validate_record(bad, schema, "S")
        self.assertTrue(any("authors" in e for e in errors), errors)
        self.assertTrue(any("year" in e for e in errors), errors)

    def test_dangling_reference_is_rejected(self) -> None:
        data = {
            "sources": [],
            "evidence": [
                {
                    "evidence_id": "EVD-X",
                    "source_id": "SRC-NOPE",
                    "excerpt": "x",
                    "interpretation": "y",
                    "confidence": "high",
                }
            ],
            "claims": [],
            "verifications": [],
            "hypotheses": [],
        }
        errors = validate_state.check_references(data)
        self.assertTrue(any("SRC-NOPE" in e for e in errors), errors)

    def test_duplicate_ids_are_rejected(self) -> None:
        records = [{"source_id": "SRC-1"}, {"source_id": "SRC-1"}]
        errors = validate_state.check_uniqueness(records, "source_id", "test")
        self.assertTrue(any("duplicate" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
