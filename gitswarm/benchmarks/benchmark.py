#!/usr/bin/env python3
"""
GitSwarm multi-seed benchmark (reproducible).

Historically this module was *written by* ``gitswarm/run_simulation.py`` and the
Worker-05 summary was hard-coded in that script.  The committed artifact did not
match a fresh execution.  This version is the single source of truth:

    python3 gitswarm/benchmarks/benchmark.py            # print summary
    python3 gitswarm/benchmarks/benchmark.py --write    # regenerate artifact
    python3 gitswarm/benchmarks/benchmark.py --check    # CI drift check

The artifact keeps the historical top-level keys (``greedy``, ``random``,
``two_opt``, ``simulated_annealing``) for backwards compatibility and adds
``_meta`` (environment, seeds, code hashes) and ``per_seed`` (raw values).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:  # allow `python3 gitswarm/benchmarks/benchmark.py`
    sys.path.insert(0, str(ROOT))

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

SEEDS: List[int] = [42, 100, 777, 999, 2026]
N_CITIES: int = 30
RANDOM_ITERATIONS: int = 500
SA_PARAMS: Dict[str, float] = {"temp": 150.0, "cooling": 0.995, "steps": 5000}
SOLVERS: List[str] = ["greedy", "random", "two_opt", "simulated_annealing"]
SOLVER_FILES: Dict[str, str] = {
    "greedy": "greedy.py",
    "random": "random_search.py",
    "two_opt": "two_opt.py",
    "simulated_annealing": "simulated_annealing.py",
}
ARTIFACT: Path = ROOT / "gitswarm" / "artifacts" / "benchmark_matrix.json"
TOLERANCE: float = 0.01


def run_benchmarks(
    seeds: Optional[Iterable[int]] = None,
    random_iterations: int = RANDOM_ITERATIONS,
) -> Tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, float]]]:
    """Run every solver on every seed and return (summary, per_seed)."""
    seeds = list(seeds if seeds is not None else SEEDS)
    per_seed: Dict[str, Dict[str, float]] = {}

    for seed in seeds:
        cities = generate_cities(N_CITIES, seed=seed)
        tours = {
            "greedy": greedy.solve(cities),
            "random": random_search.solve(
                cities, iterations=random_iterations, seed=seed
            ),
            "two_opt": two_opt.solve(cities),
            "simulated_annealing": simulated_annealing.solve(
                cities, seed=seed, **SA_PARAMS
            ),
        }
        per_seed[str(seed)] = {}
        for name, tour in tours.items():
            if not is_valid_tour(tour, N_CITIES):
                raise AssertionError(f"{name} returned an invalid tour for seed {seed}")
            per_seed[str(seed)][name] = calculate_tour_distance(tour, cities)

    summary: Dict[str, Dict[str, float]] = {}
    for name in SOLVERS:
        distances = [per_seed[str(seed)][name] for seed in seeds]
        summary[name] = {
            "mean_distance": round(sum(distances) / len(distances), 2),
            "min_distance": min(distances),
            "max_distance": max(distances),
            "runs": len(distances),
        }
    return summary, per_seed


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


def build_artifact(
    summary: Dict[str, Dict[str, float]],
    per_seed: Dict[str, Dict[str, float]],
    seeds: Optional[Iterable[int]] = None,
    random_iterations: int = RANDOM_ITERATIONS,
) -> Dict[str, object]:
    seeds = list(seeds if seeds is not None else SEEDS)
    artifact: Dict[str, object] = {
        "_meta": {
            "schema_version": 2,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            ),
            "generated_by": "gitswarm/benchmarks/benchmark.py",
            "git_head": _git_head(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "problem": {
                "name": "30-city Euclidean TSP",
                "n_cities": N_CITIES,
                "seeds": seeds,
                "random_iterations": random_iterations,
                "sa_params": SA_PARAMS,
            },
            "solver_sha256": {
                name: _sha256(ROOT / "gitswarm" / "solvers" / filename)
                for name, filename in SOLVER_FILES.items()
            },
        }
    }
    artifact.update(summary)
    artifact["per_seed"] = per_seed
    return artifact


def write_artifact(
    artifact: Dict[str, object], path: Path = ARTIFACT
) -> None:
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
    if not isinstance(meta, dict) or meta.get("schema_version", 0) < 2:
        errors.append(
            "artifact has no schema_version >= 2 metadata; regenerate with --write"
        )

    for name in SOLVERS:
        if name not in committed:
            errors.append(f"artifact missing solver '{name}'")
            continue
        for key in ("mean_distance", "min_distance", "max_distance", "runs"):
            actual = artifact[name][key]  # type: ignore[index]
            recorded = committed[name].get(key)
            if recorded is None:
                errors.append(f"artifact missing {name}.{key}")
            elif isinstance(actual, float):
                if abs(actual - recorded) > tolerance:
                    errors.append(
                        f"{name}.{key}: committed={recorded} actual={actual} "
                        f"(delta={actual - recorded:+.3f})"
                    )
            elif actual != recorded:
                errors.append(
                    f"{name}.{key}: committed={recorded} actual={actual}"
                )

    committed_per_seed = committed.get("per_seed", {})
    for seed, values in artifact["per_seed"].items():  # type: ignore[union-attr]
        recorded_values = committed_per_seed.get(seed, {})
        for name, actual in values.items():
            recorded = recorded_values.get(name)
            if recorded is None:
                errors.append(f"artifact missing per_seed[{seed}].{name}")
            elif abs(actual - recorded) > tolerance:
                errors.append(
                    f"per_seed[{seed}].{name}: committed={recorded} actual={actual} "
                    f"(delta={actual - recorded:+.3f})"
                )

    return errors


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="GitSwarm multi-seed benchmark")
    parser.add_argument(
        "--write", action="store_true", help="regenerate the committed artifact"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare a fresh run with the committed artifact (CI mode)",
    )
    parser.add_argument(
        "--json", action="store_true", help="print the full summary as JSON"
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    summary, per_seed = run_benchmarks()
    artifact = build_artifact(summary, per_seed)

    if args.write:
        write_artifact(artifact)
        print(f"wrote {ARTIFACT.relative_to(ROOT)}")

    if args.check:
        errors = check_artifact(artifact)
        if errors:
            print("FAIL: benchmark artifact is not reproducible:")
            for err in errors:
                print(f"  - {err}")
            return 1
        print("PASS: benchmark artifact matches a fresh execution")

    if args.json:
        print(json.dumps({"summary": summary, "per_seed": per_seed}, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
