"""Regression tests for the 2026-10-19 independent audit.

These tests encode the *audit findings*, not just the happy path:
- the committed benchmark artifact must match a fresh execution;
- the readout must be path-scoped (otherwise metrics drift);
- the source metadata must keep the corrected first authors;
- the validator must reject bad types/enums and non-ancestor Informed-By refs.
"""
from __future__ import annotations

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

from gitswarm import readout  # noqa: E402
from gitswarm.benchmarks.benchmark import (  # noqa: E402
    ARTIFACT,
    run_benchmarks,
)
from scripts import validate_researchos as vr  # noqa: E402


class SchemaValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source_schema = json.loads(
            (ROOT / "schemas" / "source.json").read_text(encoding="utf-8")
        )
        self.evidence_schema = json.loads(
            (ROOT / "schemas" / "evidence.json").read_text(encoding="utf-8")
        )

    def test_repository_state_passes_all_checks(self) -> None:
        report = vr.run_all_checks(str(ROOT))
        self.assertEqual(report["errors"], [], msg="\n".join(report["errors"]))

    def test_invalid_enum_is_rejected(self) -> None:
        bad = {
            "evidence_id": "EVD-X",
            "source_id": "SRC-001",
            "excerpt": "x",
            "interpretation": "y",
            "confidence": "banana",
        }
        errors = vr.validate_record(bad, self.evidence_schema, "Evidence")
        self.assertTrue(any("confidence" in err for err in errors), errors)

    def test_invalid_type_is_rejected(self) -> None:
        bad = {
            "source_id": "SRC-X",
            "title": "t",
            "authors": "not-a-list",
            "year": "2026",
            "url": "u",
            "type": "preprint",
        }
        errors = vr.validate_record(bad, self.source_schema, "Source")
        self.assertTrue(any("authors" in err for err in errors), errors)
        self.assertTrue(any("year" in err for err in errors), errors)

    def test_duplicate_ids_are_rejected(self) -> None:
        records = [
            {"evidence_id": "EVD-DUP"},
            {"evidence_id": "EVD-DUP"},
        ]
        errors = vr.validate_unique_ids({"Evidence": (records, "evidence_id")})
        self.assertTrue(any("duplicate id" in err for err in errors), errors)


class BenchmarkReproducibilityTest(unittest.TestCase):
    def test_artifact_matches_fresh_execution(self) -> None:
        summary, per_seed = run_benchmarks()
        committed = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        for solver, values in summary.items():
            for key, value in values.items():
                recorded = committed[solver][key]
                if isinstance(value, float):
                    self.assertAlmostEqual(value, recorded, places=2)
                else:
                    self.assertEqual(value, recorded)
        for seed, values in per_seed.items():
            for solver, value in values.items():
                self.assertAlmostEqual(
                    value, committed["per_seed"][seed][solver], places=2
                )

    def test_benchmark_artifact_declares_reproducibility_metadata(self) -> None:
        committed = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        self.assertGreaterEqual(committed["_meta"]["schema_version"], 2)
        self.assertEqual(committed["_meta"]["problem"]["seeds"], [42, 100, 777, 999, 2026])
        self.assertEqual(committed["_meta"]["problem"]["random_iterations"], 500)
        self.assertEqual(
            set(committed["_meta"]["solver_sha256"]),
            {"greedy", "random", "two_opt", "simulated_annealing"},
        )

    def test_audit_finding_sa_is_only_marginally_better_than_two_opt(self) -> None:
        """The pre-audit artifact claimed an 8% gap; the real gap is ~0.16%."""
        summary, _ = run_benchmarks()
        sa = summary["simulated_annealing"]["mean_distance"]
        two_opt = summary["two_opt"]["mean_distance"]
        self.assertLess(sa, two_opt)
        self.assertLess((two_opt - sa) / two_opt, 0.01)


class ReadoutScopeTest(unittest.TestCase):
    def test_scoped_readout_is_stable(self) -> None:
        result = readout.analyze_gitswarm(paths=["gitswarm"])
        self.assertIsNotNone(result)
        self.assertEqual(result["total_worker_commits"], 7)
        self.assertEqual(result["candidate_commits"], 5)
        metrics = result["compounding_metrics"]
        self.assertEqual(metrics["contribution_reuse_rate_pct"], 100.0)
        self.assertEqual(metrics["negative_reuse_rate_pct"], 100.0)
        self.assertEqual(metrics["winner_ancestry_coverage_pct"], 80.0)

    def test_unscoped_readout_drifts(self) -> None:
        """Whole-repo scanning mixes in state/ [Worker-01]/[Worker-02] commits."""
        scoped = readout.analyze_gitswarm(paths=["gitswarm"])
        unscoped = readout.analyze_gitswarm(paths=[])
        self.assertIsNotNone(scoped)
        self.assertIsNotNone(unscoped)
        self.assertGreater(
            unscoped["total_worker_commits"], scoped["total_worker_commits"]
        )
        scoped_metrics = scoped["compounding_metrics"]
        unscoped_metrics = unscoped["compounding_metrics"]
        self.assertNotEqual(
            scoped_metrics["winner_ancestry_coverage_pct"],
            unscoped_metrics["winner_ancestry_coverage_pct"],
        )

    def test_snapshot_matches_scoped_readout(self) -> None:
        snapshot = json.loads(
            (ROOT / "gitswarm" / "artifacts" / "readout_snapshot.json").read_text(
                encoding="utf-8"
            )
        )
        result = readout.analyze_gitswarm(paths=["gitswarm"])
        self.assertIsNotNone(result)
        for key in (
            "total_worker_commits",
            "candidate_commits",
            "vote_tallies",
            "winning_candidate_sha",
            "compounding_metrics",
        ):
            self.assertEqual(result[key], snapshot[key], key)


class CitationMetadataTest(unittest.TestCase):
    def setUp(self) -> None:
        self.sources = {
            source["source_id"]: source
            for source in vr.load_jsonl(str(ROOT / "state" / "sources.jsonl"))
        }

    def test_corrected_first_authors(self) -> None:
        self.assertEqual(self.sources["SRC-001"]["authors"][0], "Qizheng Zhang")
        self.assertEqual(self.sources["SRC-003"]["authors"][0], "Shubham Agarwal")
        self.assertEqual(len(self.sources["SRC-002"]["authors"]), 14)

    def test_every_evidence_declares_quote_type(self) -> None:
        allowed = {
            "verbatim",
            "verbatim_excerpts",
            "measurement",
            "metadata_comparison",
            "fulltext_check",
            "code_inspection",
        }
        for evidence in vr.load_jsonl(str(ROOT / "state" / "evidence.jsonl")):
            self.assertIn("quote_type", evidence, evidence["evidence_id"])
            self.assertIn(evidence["quote_type"], allowed)

    def test_audit_claims_are_recorded(self) -> None:
        claims = {
            claim["claim_id"]: claim
            for claim in vr.load_jsonl(str(ROOT / "state" / "claims.jsonl"))
        }
        for claim_id in ("CLM-004", "CLM-005", "CLM-006", "CLM-007"):
            self.assertIn(claim_id, claims)
        self.assertEqual(claims["CLM-003"]["status"], "candidate")


class ProvenanceAncestryTest(unittest.TestCase):
    @staticmethod
    def _git(cwd: str, *args: str, env: dict) -> None:
        subprocess.check_call(
            ["git", *args],
            cwd=cwd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    @staticmethod
    def _env() -> dict:
        env = os.environ.copy()
        env.update(
            {
                "GIT_AUTHOR_NAME": "audit",
                "GIT_AUTHOR_EMAIL": "audit@example.com",
                "GIT_COMMITTER_NAME": "audit",
                "GIT_COMMITTER_EMAIL": "audit@example.com",
            }
        )
        return env

    def test_non_ancestor_reference_is_rejected(self) -> None:
        """A merge can make a sibling commit visible in git log; it is not an ancestor."""
        with tempfile.TemporaryDirectory() as tmp:
            env = self._env()
            self._git(tmp, "init", "-q", "-b", "main", env=env)
            Path(tmp, "base.txt").write_text("base", encoding="utf-8")
            self._git(tmp, "add", "-A", env=env)
            self._git(tmp, "commit", "-qm", "base", env=env)

            self._git(tmp, "checkout", "-qb", "left", env=env)
            Path(tmp, "left.txt").write_text("left", encoding="utf-8")
            self._git(tmp, "add", "-A", env=env)
            self._git(tmp, "commit", "-qm", "left: explore", env=env)
            left = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=tmp, text=True
            ).strip()

            self._git(tmp, "checkout", "-q", "main", env=env)
            Path(tmp, "right.txt").write_text("right", encoding="utf-8")
            self._git(tmp, "add", "-A", env=env)
            self._git(
                tmp,
                "commit",
                "-qm",
                f"right: refine\n\nInformed-By: {left[:7]}\nAction-Type: refine",
                env=env,
            )
            self._git(tmp, "merge", "--no-ff", "left", "-m", "merge left", env=env)

            errors = vr.validate_git_provenance(tmp)
            self.assertTrue(
                any("non-ancestor" in err for err in errors),
                f"expected a non-ancestor error, got: {errors}",
            )

    def test_ancestor_reference_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = self._env()
            self._git(tmp, "init", "-q", "-b", "main", env=env)
            Path(tmp, "base.txt").write_text("base", encoding="utf-8")
            self._git(tmp, "add", "-A", env=env)
            self._git(tmp, "commit", "-qm", "base", env=env)
            base = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=tmp, text=True
            ).strip()

            Path(tmp, "child.txt").write_text("child", encoding="utf-8")
            self._git(tmp, "add", "-A", env=env)
            self._git(
                tmp,
                "commit",
                "-qm",
                f"child: refine\n\nInformed-By: {base[:7]}\nAction-Type: refine",
                env=env,
            )

            errors = vr.validate_git_provenance(tmp)
            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
