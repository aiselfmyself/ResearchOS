#!/usr/bin/env python3
"""Does a plurality readout over homogeneous workers amplify error?

This is the measurement that ``task/TASK.md`` objective 3 has been missing
since 2026-10-19.  Every memo in ``contributions/`` records the same caveat --
"共通モード障害の直接測定は存在しない / nobody has measured this" -- so CLM-003
and HYP-002 rest on plausibility, not evidence.  This module measures it.

THE SETTING
-----------
A jury problem, which is what the open proposal actually asks for:

    「正解が既知でモデルが苦手な課題を使い、同質ワーカーの多数決が誤りを
      増幅するかを直接測る」
    (use tasks whose correct answer is known and that the worker is bad at,
     and measure directly whether a homogeneous plurality amplifies error)

* ``TASKS`` independent tasks.  Each has one correct answer among ``N_OPTIONS``
  candidates.  The correct answer is fixed in advance: ground truth is known by
  construction, so accuracy is exactly measurable.

* ``N`` homogeneous workers each nominate one candidate.  Plurality selects the
  most-nominated candidate, with deterministic tie-breaking, exactly as
  GitSwarm's decentralized readout does (arXiv:2610.04862, §2.5).

* A worker is homogeneous in the sense that matters here: every worker draws
  from the SAME distribution, and with probability ``rho`` it defers to a view
  that is SHARED with all the other workers -- the common-mode term.

    with prob rho    : output the shared view A_t
                       (A_t is correct with probability ``c``; when it is
                        wrong, every follower is wrong in the SAME way)
    with prob 1-rho  : answer independently, correct with probability ``p``,
                       otherwise pick uniformly among the wrong candidates

WHAT "AMPLIFICATION" MEANS HERE
-------------------------------
    amplification = plurality_error / individual_error

``individual_error`` is MEASURED, not assumed: it is the fraction of all
worker-answers in that cell that were wrong.  (It is not simply 1-p, because
deferring to the shared view changes it.)  Amplification above 1.0 means
pooling the workers produced a WORSE answer than asking one of them.

THE TWO QUESTIONS THIS SEPARATES
--------------------------------
The literature -- and CLM-003 -- run two distinct mechanisms together under the
single heading "common-mode failure".  This sweep separates them:

  1. ``p`` below chance (1/N_OPTIONS).
     Workers who are individually worse than random.  Plurality then converges
     on a wrong answer more reliably than any single worker is wrong.

  2. ``rho`` with a shared view that is worse than the workers (``c`` < ``p``).
     Workers who are competent individually, but who defer to a shared
     misconception.  The correlated bloc outvotes the scattered independent
     minority, so agreement manufactures a majority that a single worker
     would not have produced.

The sweep varies ``p``, ``rho`` and ``c`` independently so the two can be told
apart, and so that the region where each dominates is visible.

WHAT THIS IS NOT  (read before citing any number from it)
--------------------------------------------------------
The workers are Bernoulli draws from the model stated above.  They are NOT
language-model agents, and nothing here measures the correlation structure of
any real LLM swarm -- that remains unmeasured, and is now the only thing
standing between this result and an empirical claim about GitSwarm-style
systems.  What this module measures is the behaviour of the plurality rule
itself under stated assumptions, which is a prerequisite for knowing what an
empirical measurement would have to look for.

Usage:
    python3 gitswarm/readout_sim.py                # print the summary table
    python3 gitswarm/readout_sim.py --write        # regenerate the artifact
    python3 gitswarm/readout_sim.py --check        # CI drift check
    python3 gitswarm/readout_sim.py --json         # machine-readable results

Standard library only.  Deterministic given the committed parameters.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]

# --------------------------------------------------------------------------
# Parameters.  Changing any of these changes the artifact; re-run --write.
# --------------------------------------------------------------------------
TASKS: int = 1000           # independent tasks per cell
N_OPTIONS: int = 4          # candidate answers per task; exactly one is right
N_VOTERS: List[int] = [1, 3, 5, 9, 15]
ACCURACIES: List[float] = [0.15, 0.25, 0.40, 0.60, 0.80]
RHOS: List[float] = [0.0, 0.3, 0.6, 0.9]
SHARED_ACCURACIES: List[float] = [0.0, 0.5, 1.0]
MAX_VOTERS: int = max(N_VOTERS)

ARTIFACT: Path = ROOT / "gitswarm" / "artifacts" / "readout_sim_matrix.json"
TOLERANCE: float = 0.01
CODE_FILES: Dict[str, str] = {"readout_sim": "gitswarm/readout_sim.py"}


# --------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------
def _cell_seed(p: float, rho: float, c: float) -> int:
    """Stable integer seed for one cell, derived from its parameters only."""
    payload = (
        f"readout-sim|v1|p={p}|rho={rho}|c={c}|"
        f"tasks={TASKS}|options={N_OPTIONS}|maxvoters={MAX_VOTERS}"
    ).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def critical_rho(p: float) -> float:
    """Deferral rate above which a WRONG shared view captures the readout.

    A deferring bloc of ``rho * N`` workers all vote for the shared answer.
    The independent voters are correct with probability ``p``, so the truth
    collects about ``(1 - rho) * N * p`` votes.  The bloc wins when

        rho * N > (1 - rho) * N * p   <=>   rho > p / (1 + p)

    Below this threshold the scattered independent majority outvotes the
    correlated bloc and the readout still helps.  Above it, agreement
    manufactures a majority that no single worker would have produced.

    This is a prediction made BEFORE looking at the sweep output; the sweep is
    then checked against it (see ``tests/test_readout_sim.py``).
    """
    return p / (1.0 + p)


def draw_electorate(
    rng: random.Random,
    p: float,
    rho: float,
    c: float,
    n_voters: int = MAX_VOTERS,
    tasks: int = TASKS,
) -> List[Tuple[int, List[int]]]:
    """Draw ``tasks`` electorates of ``n_voters`` workers.

    Returns one ``(truth, answers)`` pair per task.  This is the only place the
    model is implemented; ``evaluate`` and ``run_sweep`` both consume it.
    """
    electorate: List[Tuple[int, List[int]]] = []
    for _ in range(tasks):
        truth = rng.randrange(N_OPTIONS)
        # The shared view: correct with probability c, otherwise one specific
        # wrong option that every deferring worker copies verbatim.
        if rng.random() < c:
            shared = truth
        else:
            shared = (truth + rng.randrange(1, N_OPTIONS)) % N_OPTIONS
        answers: List[int] = []
        for _ in range(n_voters):
            if rng.random() < rho:
                answers.append(shared)
            elif rng.random() < p:
                answers.append(truth)
            else:
                answers.append((truth + rng.randrange(1, N_OPTIONS)) % N_OPTIONS)
        electorate.append((truth, answers))
    return electorate


def evaluate(
    electorate: Sequence[Tuple[int, Sequence[int]]], n_voters: int
) -> Dict[str, float]:
    """Score a drawn electorate using the first ``n_voters`` of each task.

    Taking a prefix means increasing N ADDS workers instead of re-drawing a
    fresh jury, so the N-sweep isolates the effect of group size.
    """
    wrong = 0
    answers_cast = 0
    plurality_wrong = 0
    for truth, answers in electorate:
        tally = [0] * N_OPTIONS
        for answer in answers[:n_voters]:
            tally[answer] += 1
            answers_cast += 1
            if answer != truth:
                wrong += 1
        # Plurality readout: most nominations wins, ties broken deterministically
        # by lowest candidate index.
        best_index = 0
        for idx in range(1, N_OPTIONS):
            if tally[idx] > tally[best_index]:
                best_index = idx
        if best_index != truth:
            plurality_wrong += 1

    individual_error = wrong / answers_cast
    plurality_error = plurality_wrong / len(electorate)
    return {
        "individual_error": round(individual_error, 4),
        "plurality_error": round(plurality_error, 4),
        "amplification": (
            round(plurality_error / individual_error, 4) if individual_error else 0.0
        ),
    }


def simulate_cell(
    p: float,
    rho: float,
    c: float,
    n_voters: int,
    tasks: int = TASKS,
) -> Dict[str, float]:
    """Run ``tasks`` elections with ``n_voters`` homogeneous workers."""
    rng = random.Random(_cell_seed(p, rho, c))
    electorate = draw_electorate(rng, p, rho, c, n_voters=n_voters, tasks=tasks)
    return evaluate(electorate, n_voters)


def run_matched_sweep() -> Dict[str, Dict[str, Dict[str, float]]]:
    """Correlation with a shared view NO BETTER AND NO WORSE than a worker.

    Sets ``c == p``, so a worker's marginal accuracy is ``p`` whatever the
    deferral rate::

        rho * c + (1 - rho) * p = rho * p + (1 - rho) * p = p

    Holding individual accuracy fixed is what makes this a controlled
    comparison.  Any change in the readout is therefore attributable to
    CORRELATION ALONE -- not to the workers having become individually worse,
    which is the confound that makes the plain ``c`` sweep hard to interpret.

    This is the experiment that isolates the claim CLM-003 actually makes about
    homogeneous workers, as distinct from the claim about a wrong shared view.
    """
    out: Dict[str, Dict[str, Dict[str, float]]] = {}
    for p in ACCURACIES:
        p_key = f"{p:.2f}"
        out[p_key] = {}
        for rho in RHOS:
            rng = random.Random(_cell_seed(p, rho, p))
            electorate = draw_electorate(rng, p, rho, p)
            out[p_key][f"{rho:.2f}"] = {
                str(n): evaluate(electorate, n) for n in N_VOTERS
            }
    return out


def run_sweep() -> Dict[str, Dict[str, Dict[str, Dict[str, float]]]]:
    """Return results[p][rho][c][N] -> metrics, averaged over ``TASKS`` tasks."""
    results: Dict[str, Dict[str, Dict[str, Dict[str, float]]]] = {}
    for p in ACCURACIES:
        p_key = f"{p:.2f}"
        results[p_key] = {}
        for rho in RHOS:
            rho_key = f"{rho:.2f}"
            results[p_key][rho_key] = {}
            for c in SHARED_ACCURACIES:
                rng = random.Random(_cell_seed(p, rho, c))
                electorate = draw_electorate(rng, p, rho, c)
                results[p_key][rho_key][f"{c:.2f}"] = {
                    str(n): evaluate(electorate, n) for n in N_VOTERS
                }
    return results


# --------------------------------------------------------------------------
# Artifact plumbing (mirrors gitswarm/benchmarks/benchmark.py)
# --------------------------------------------------------------------------
def _sha256(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head() -> Optional[str]:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def build_artifact(results, matched=None) -> Dict[str, object]:
    if matched is None:
        matched = run_matched_sweep()
    return {
        "_meta": {
            "schema_version": 1,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            ),
            "generated_by": "gitswarm/readout_sim.py",
            "git_head": _git_head(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "parameters": {
                "tasks": TASKS,
                "n_options": N_OPTIONS,
                "n_voters": N_VOTERS,
                "accuracies": ACCURACIES,
                "rhos": RHOS,
                "shared_accuracies": SHARED_ACCURACIES,
                "chance_level": round(1.0 / N_OPTIONS, 4),
                "critical_rho": {
                    f"{a:.2f}": round(critical_rho(a), 4) for a in ACCURACIES
                },
            },
            "code_sha256": {
                name: _sha256(ROOT / rel) for name, rel in CODE_FILES.items()
            },
        },
        "results": results,
        "matched_results": matched,
    }


def write_artifact(artifact: Dict[str, object], path: Path = ARTIFACT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, ensure_ascii=False)
        f.write("\n")


def check_artifact(
    artifact: Dict[str, object],
    path: Path = ARTIFACT,
    tolerance: float = TOLERANCE,
) -> List[str]:
    """Compare a fresh run with the committed artifact; return error strings."""
    if not path.exists():
        return [f"artifact not found: {path}"]

    with path.open("r", encoding="utf-8") as f:
        committed = json.load(f)

    errors: List[str] = []
    meta = committed.get("_meta")
    if not isinstance(meta, dict) or meta.get("schema_version", 0) < 1:
        errors.append(
            "artifact has no schema_version >= 1 metadata; regenerate with --write"
        )

    def _cmp(committed_obj: object, fresh_obj: object, trail: str) -> None:
        if isinstance(fresh_obj, dict):
            if not isinstance(committed_obj, dict):
                errors.append(f"{trail}: expected an object in the artifact")
                return
            for key, value in fresh_obj.items():
                if key not in committed_obj:
                    errors.append(f"{trail}.{key}: missing from artifact")
                else:
                    _cmp(committed_obj[key], value, f"{trail}.{key}")
        elif isinstance(fresh_obj, (int, float)) and not isinstance(fresh_obj, bool):
            if not isinstance(committed_obj, (int, float)) or isinstance(
                committed_obj, bool
            ):
                errors.append(f"{trail}: expected a number in the artifact")
            elif abs(float(fresh_obj) - float(committed_obj)) > tolerance:
                errors.append(
                    f"{trail}: committed={committed_obj} actual={fresh_obj} "
                    f"(delta={float(fresh_obj) - float(committed_obj):+.4f})"
                )

    _cmp(committed.get("results"), artifact["results"], "results")
    _cmp(committed.get("matched_results"), artifact["matched_results"], "matched_results")
    return errors


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------
def format_table(results) -> str:
    lines: List[str] = []
    header = (
        f"{'p':>5} {'rho':>5} {'c':>5} {'N':>3} "
        f"{'indiv_err':>10} {'plural_err':>11} {'amplif':>8}"
    )
    lines.append(header)
    lines.append("-" * (len(header) + 14))
    for p in ACCURACIES:
        for rho in RHOS:
            for c in SHARED_ACCURACIES:
                for n in N_VOTERS:
                    cell = results[f"{p:.2f}"][f"{rho:.2f}"][f"{c:.2f}"][str(n)]
                    flag = "  <-- amplified" if cell["amplification"] > 1.0 else ""
                    lines.append(
                        f"{p:>5} {rho:>5} {c:>5} {n:>3} "
                        f"{cell['individual_error']:>10.4f} "
                        f"{cell['plurality_error']:>11.4f} "
                        f"{cell['amplification']:>8.4f}{flag}"
                    )
    return "\n".join(lines)


def format_matched_table(matched) -> str:
    """Correlation alone: does the benefit of pooling survive?"""
    lines: List[str] = []
    header = f"{'p':>5} {'rho':>5} {'N':>3} {'indiv_err':>10} {'plural_err':>11} {'amplif':>8}"
    lines.append(header)
    lines.append("-" * len(header))
    for p in ACCURACIES:
        for rho in RHOS:
            cell = matched[f"{p:.2f}"][f"{rho:.2f}"]["15"]
            lines.append(
                f"{p:>5} {rho:>5} {15:>3} "
                f"{cell['individual_error']:>10.4f} "
                f"{cell['plurality_error']:>11.4f} "
                f"{cell['amplification']:>8.4f}"
            )
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Homogeneous-worker plurality readout: error-amplification sweep"
    )
    parser.add_argument("--write", action="store_true", help="regenerate the artifact")
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare a fresh run with the committed artifact (CI mode)",
    )
    parser.add_argument("--json", action="store_true", help="print results as JSON")
    args = parser.parse_args(list(argv) if argv is not None else None)

    results = run_sweep()
    artifact = build_artifact(results, run_matched_sweep())

    if args.write:
        write_artifact(artifact)
        print(f"wrote {ARTIFACT.relative_to(ROOT)}")

    if args.check:
        errors = check_artifact(artifact)
        if errors:
            print("FAIL: readout-sim artifact is not reproducible:")
            for err in errors:
                print(f"  - {err}")
            return 1
        print("PASS: readout-sim artifact matches a fresh execution")

    if args.json:
        print(json.dumps(
            {"results": results, "matched_results": artifact["matched_results"]},
            indent=2,
        ))
    elif not args.check and not args.write:
        print(f"tasks={TASKS} per cell, options={N_OPTIONS} "
              f"(chance = {1.0 / N_OPTIONS:.2f})")
        print("amplification = plurality_error / measured individual_error")
        print()
        print(format_table(results))
        print()
        print("MATCHED sweep (c == p): correlation alone, individual accuracy held")
        print("fixed at p.  Shown at N=15.  Amplification rising towards 1.0 means")
        print("the benefit of pooling is being destroyed, not that errors grow.")
        print()
        print(format_matched_table(artifact["matched_results"]))

    return 0


if __name__ == "__main__":
    sys.exit(main())
