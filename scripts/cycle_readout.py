#!/usr/bin/env python3
"""Read S8 stop signals from immutable RUN snapshots (NOT a CI gate).

A RUN stores *snapshot* counts taken immediately before and after a round.
This tool does not reconstruct historical ledgers from the current union view:
old ledgers have no per-round marker, and retroactively attributing their RELs
to a round would fabricate data. An absent metric means UNKNOWN, never zero.

A stop signal is an observation, not a failing test: exit 0 even for "stop".
Exit 2 means the RUN ledger could not be read or measurements are malformed.
No round is started or ledger modified by this program. Review the evidence
and secure another explicit authorization before starting a round after a stop.

Usage: python3 scripts/cycle_readout.py --json
       python3 scripts/cycle_readout.py --max-human-interventions 2 --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

try:
    import validate_state as vs
except ImportError:  # run from outside the scripts directory
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import validate_state as vs


def _count(row: Dict[str, Any], key: str, label: str) -> Optional[int]:
    value = row.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label}.{key}: expected nonnegative integer, got {value!r}")
    return value


def _pair_signal(
    metrics: Dict[str, Any], before: str, after: str, label: str
) -> Optional[tuple[int, int]]:
    left = _count(metrics, before, label)
    right = _count(metrics, after, label)
    return (left, right) if left is not None and right is not None else None


def analyse(
    runs: List[Dict[str, Any]],
    *,
    max_human_interventions: Optional[int] = None,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """Return per-RUN measurement and stop flags; never infer missing counts."""
    if any(value is not None and (type(value) is not int or value < 0)
           for value in (max_human_interventions, max_tokens)):
        raise ValueError("budget limits must be nonnegative integers")
    by_round: Dict[int, Dict[str, Any]] = {}
    by_id = set()
    for run in runs:
        if not isinstance(run, dict):
            raise ValueError("RUN is not an object")
        round_number = _count(run, "round", "RUN")
        run_id = run.get("run_id")
        if round_number is None or round_number < 1 or not isinstance(run_id, str) or not run_id:
            raise ValueError("RUN requires a positive round and a non-empty run_id")
        if round_number in by_round or run_id in by_id:
            raise ValueError(f"duplicate RUN round or run_id: {round_number}, {run_id}")
        metrics = run.get("metrics", {})
        if not isinstance(metrics, dict):
            raise ValueError(f"{run_id}.metrics: expected object")
        by_round[round_number] = run
        by_id.add(run_id)

    report: List[Dict[str, Any]] = []
    for number in sorted(by_round):
        run = by_round[number]
        rid = run["run_id"]
        metrics = run.get("metrics", {})
        unexplained = _pair_signal(metrics, "unexplained_before", "unexplained_after", rid)
        support = _pair_signal(metrics, "support_non_derived_before", "support_non_derived_after", rid)
        refute = _pair_signal(metrics, "refute_before", "refute_after", rid)
        human = _count(run, "human_interventions", rid)
        created = _count(run, "hypotheses_created", rid)
        decisions = _count(metrics, "decision_events_total", rid)
        tokens = _count(metrics, "tokens_total", rid)
        if decisions is not None and (decisions == 0 or human is None or human > decisions):
            raise ValueError(f"{rid}: decision_events_total must be positive and >= human_interventions")
        # A missing RUN (or missing hypotheses_created) interrupts the streak.
        last_three = [by_round.get(n) for n in range(number - 2, number + 1)]
        if number < 3:
            streak: Optional[bool] = False  # three rounds have not happened yet
        elif any(row is None for row in last_three):
            streak = None  # a missing RUN interrupts the history
        else:
            counts = [_count(row, "hypotheses_created", row["run_id"]) for row in last_three]
            streak = all(value == 0 for value in counts) if all(value is not None for value in counts) else None
        flags: Dict[str, Optional[bool]] = {
            "unexplained_not_decreased": unexplained[1] >= unexplained[0] if unexplained else None,
            # "Non-derived" means not flagged true, NOT distinct independent
            # sources (old REL flags are unknown and remain in this count).
            "refute_zero_with_support_growth": (
                refute == (0, 0) and support[1] > support[0]
                if refute and support else None
            ),
            "three_rounds_no_new_hypothesis": streak,
            "human_budget_exceeded": (
                human > max_human_interventions
                if max_human_interventions is not None and human is not None else None
            ),
            "token_budget_exceeded": (
                tokens > max_tokens if max_tokens is not None and tokens is not None else None
            ),
        }
        stop_reasons = [name for name, found in flags.items() if found is True]
        required = ("unexplained_not_decreased", "refute_zero_with_support_growth",
                    "three_rounds_no_new_hypothesis")
        missing = [name for name in required if flags[name] is None]
        if max_human_interventions is not None and flags["human_budget_exceeded"] is None:
            missing.append("human_budget_exceeded")
        if max_tokens is not None and flags["token_budget_exceeded"] is None:
            missing.append("token_budget_exceeded")
        status = "stop" if stop_reasons else ("review_required" if missing else "continue")
        report.append({
            "round": number,
            "run_id": rid,
            "status": status,
            "stop_reasons": stop_reasons,
            "unknown_signals": missing,
            "signals": flags,
            "snapshot": {
                "unexplained": list(unexplained) if unexplained else None,
                "support_non_derived": list(support) if support else None,
                "refute": list(refute) if refute else None,
                "hypotheses_created": created,
                "human_interventions": human,
                "decision_events_total": decisions,
                "intervention_count_rate": (
                    round(1 - human / decisions, 4) if decisions is not None else None
                ),
                "tokens_total": tokens,
            },
        })
    return {
        "rounds": report,
        "latest": report[-1] if report else None,
        "budgets": {"max_human_interventions": max_human_interventions, "max_tokens": max_tokens},
        "note": "Stop is advisory, not a CI gate. Missing history is unknown; non-derived support is REL count (not distinct independent sources); the intervention-count rate is not a time-based automation rate.",
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=vs.ROOT / "state")
    parser.add_argument("--max-human-interventions", type=int, default=None)
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        runs, errors = vs.load_jsonl(args.state_dir / "runs.jsonl")
        if errors:
            raise ValueError("; ".join(errors))
        result = analyse(runs, max_human_interventions=args.max_human_interventions,
                         max_tokens=args.max_tokens)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for row in result["rounds"]:
            print(f"round {row['round']}: {row['status']}; stop={row['stop_reasons']}; unknown={row['unknown_signals']}")
        if not result["rounds"]:
            print("No RUNs recorded; no stop decision is available.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
