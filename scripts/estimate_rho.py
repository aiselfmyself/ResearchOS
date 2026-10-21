#!/usr/bin/env python3
"""Estimate the common-mode follow rate rho from two workers' correlated errors.

WHY THIS EXISTS
---------------
gitswarm/readout_sim.py models a jury of N homogeneous workers. Each worker,
with probability ``rho``, defers to a view A_t that is SHARED with every other
worker (A_t is correct with probability ``c``); with probability ``1-rho`` it
answers independently and is correct with probability ``p``. rho is the
common-mode term.

Until now rho has been a free parameter: contributions/2026-10-20_
common_mode_measurement.md and the integrated report §5.3 both conclude that
amplification is conditional on rho, but no measurement of rho exists. This
script makes rho estimable from data that scripts/measure_agreement.py already
produces.

THE ESTIMATOR
-------------
Let ``e`` be a worker's error rate. Under the model above (homogeneous
workers, one shared view):

    e             = rho*(1-c) + (1-rho)*(1-p)
    P(both wrong) = rho^2*(1-c)                both follow, shared view wrong
                  + 2*rho*(1-rho)*(1-c)*(1-p)  one follows, one independent
                  + (1-rho)^2*(1-p)^2          both independent

Expanding e^2 gives exactly the same terms except the first, where e^2 has
rho^2*(1-c)^2 instead of rho^2*(1-c). Subtracting:

    P(both wrong) - e^2 = rho^2 * c * (1-c)                            (*)

Two consequences, both reported by this script:

1. **A lower bound on rho that assumes nothing about c.** Since
   c*(1-c) <= 1/4 (maximised at c = 1/2), solving (*) for rho gives

       rho >= 2 * sqrt( P(both wrong) - e^2 )      when the excess is >= 0

   This is the headline number: it is the smallest rho compatible with the
   observed correlated-error rate, whatever the accuracy of the shared view.

2. **A point estimate under the assumption c = p** (the shared view is as
   accurate as an individual worker -- the "correlation only" regime of
   readout_sim.py, in which amplification vanishes and the benefit of
   aggregation is instead fully lost). With c = p, (*) becomes
   ``excess = rho^2 * p * (1-p)``, so

       rho = sqrt( excess / (p * (1-p)) )

   This assumption is strong and is reported separately, never as the default.

LIMITS
------
* ``excess`` is a difference of proportions, so it needs a LOT of items. With
  n jointly-decided items the sampling error alone is of order
  ``sqrt(P(1-P)/n)``. The ``--power`` mode reports how many items are needed
  before a given rho is detectable at all.
* When either worker makes zero errors, the independence null ``p1*p2`` is 0
  and lift is undefined; the same is true here. This script reports the
  detection limit instead of pretending to estimate rho.
* The model assumes a single shared view and homogeneous workers. Two
  sessions reading the same paper are an approximation of that, not an
  instance of it.

Usage:
    # from scripts/measure_agreement.py --json output
    python3 scripts/measure_agreement.py --a A.json --b B.json --truth T.json --json > m.json
    python3 scripts/estimate_rho.py --from-agreement m.json

    # or directly
    python3 scripts/estimate_rho.py --n 8 --p1 0.0 --p2 0.0 --both-wrong 0

    # how many items would we need?
    python3 scripts/estimate_rho.py --power --error-rate 0.20 --rho 0.30

Exit code: always 0 -- this is an instrument, never a gate (the same rule as
scripts/measure_agreement.py).
Standard library only.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Two-sided alpha = 0.05 and power = 0.80.
Z_ALPHA = 1.959964  # Phi^-1(0.975)
Z_BETA = 0.841621   # Phi^-1(0.80)


def estimate(n: int, p1: float, p2: float, both_wrong: float) -> Dict[str, Any]:
    """Return the rho estimate (or the detection limit when unidentifiable)."""
    e = (p1 + p2) / 2.0                      # mean per-worker error rate
    p_indep = 1.0 - e                        # per-worker accuracy under c = p
    expected_if_independent = p1 * p2        # independence null (exact marginals)
    excess = both_wrong - expected_if_independent

    out: Dict[str, Any] = {
        "n_joint_decided": n,
        "p1": p1,
        "p2": p2,
        "mean_error_rate_e": e,
        "p_both_wrong": both_wrong,
        "expected_p_both_wrong_if_independent": expected_if_independent,
        "excess": excess,
    }

    # Sampling error of P(both wrong) alone; p1 and p2 are treated as fixed.
    se = math.sqrt(both_wrong * (1.0 - both_wrong) / n) if n > 0 else float("nan")
    out["se_p_both_wrong"] = se
    out["excess_ci95"] = [excess - Z_ALPHA * se, excess + Z_ALPHA * se]

    if expected_if_independent <= 0.0:
        out["identifiable"] = False
        out["reason"] = (
            "at least one worker made no errors on the joint-decided subset, so the "
            "independence null p1*p2 is zero and the excess is undefined"
        )
        out["rho_lower_bound"] = None
        out["rho_point_estimate_c_eq_p"] = None
    elif excess < 0:
        out["identifiable"] = True
        out["rho_lower_bound"] = 0.0
        out["rho_point_estimate_c_eq_p"] = 0.0
        out["reason"] = (
            "joint errors are at or below the independence null: no evidence of a "
            "common-mode term at this sample size"
        )
    else:
        out["identifiable"] = True
        # c*(1-c) <= 1/4  =>  rho >= 2*sqrt(excess)
        out["rho_lower_bound"] = min(1.0, 2.0 * math.sqrt(excess))
        # c = p  =>  excess = rho^2 * p * (1-p)
        if p_indep > 0.0 and e > 0.0:
            out["rho_point_estimate_c_eq_p"] = min(
                1.0, math.sqrt(excess / (p_indep * e))
            )
        else:
            out["rho_point_estimate_c_eq_p"] = None
        out["reason"] = (
            "lower bound assumes nothing about the shared view's accuracy c; "
            "the point estimate additionally assumes c = p"
        )

    # Smallest excess this sample could have distinguished from zero.
    out["detection_limit_excess"] = Z_ALPHA * se if se == se else None
    if p_indep > 0.0 and e > 0.0 and out["detection_limit_excess"] is not None:
        out["detection_limit_rho_c_eq_p"] = min(
            1.0,
            math.sqrt(out["detection_limit_excess"] / (p_indep * e)),
        )
    else:
        out["detection_limit_rho_c_eq_p"] = None

    out["reading"] = _reading(out)
    return out


def _reading(r: Dict[str, Any]) -> str:
    if not r["identifiable"]:
        return (
            f"n={r['n_joint_decided']}: rho is NOT identifiable "
            f"({r['reason']}). Report the required sample size instead."
        )
    if r["excess"] < 0:
        return (
            f"n={r['n_joint_decided']}: no evidence of correlated error "
            f"(excess={r['excess']:+.4f}). rho is indistinguishable from 0 here; "
            f"the sample could only have detected rho >= "
            f"{r['detection_limit_rho_c_eq_p']} had it been present."
        )
    lo = r["rho_lower_bound"]
    pt = r["rho_point_estimate_c_eq_p"]
    return (
        f"n={r['n_joint_decided']}: rho >= {lo:.3f} (assumption-free lower bound); "
        f"rho ~ {pt:.3f} if the shared view is as accurate as a worker (c = p). "
        f"Detection limit of this sample: rho >= "
        f"{r['detection_limit_rho_c_eq_p']:.3f}."
    )


def required_n(error_rate: float, rho: float) -> Dict[str, Any]:
    """Items needed to detect `rho` at alpha=0.05, power=0.80 (c = p assumed).

    Two-proportion normal approximation:
        n = (z_a + z_b)^2 * P0(1-P0) / (P1 - P0)^2
    where P0 = e^2 is the joint-error rate under independence and
    P1 = P0 + rho^2 * p * (1-p) under the common-mode model with c = p.
    """
    e = error_rate
    p = 1.0 - e
    p0 = e * e
    delta = rho * rho * p * e
    if delta <= 0 or e <= 0 or p <= 0:
        return {"error_rate": e, "rho": rho, "required_n": None,
                "reading": "undefined: rho or the error rate is 0"}
    n = ((Z_ALPHA + Z_BETA) ** 2) * p0 * (1.0 - p0) / (delta ** 2)
    n_int = int(math.ceil(n))
    return {
        "error_rate": e,
        "rho": rho,
        "p_both_wrong_null": p0,
        "p_both_wrong_alt": p0 + delta,
        "required_n": n_int,
        "reading": (
            f"to detect rho={rho:.2f} at error rate {e:.2f} (alpha=0.05, power=0.80, "
            f"c=p) you need about {n_int:,} jointly-decided items with known truth"
        ),
    }


def load_agreement(path: Path) -> Dict[str, Any]:
    blob = json.loads(path.read_text(encoding="utf-8"))
    ta = blob.get("truth_analysis")
    if not isinstance(ta, dict):
        raise ValueError("no truth_analysis in the agreement JSON; run "
                         "measure_agreement.py with --truth and --json")
    return estimate(
        n=int(ta["n_joint_decided"]),
        p1=float(ta["p1"]),
        p2=float(ta["p2"]),
        both_wrong=float(ta["p_both_wrong"]),
    )


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--from-agreement", metavar="JSON",
                    help="output of measure_agreement.py --truth --json")
    ap.add_argument("--n", type=int, help="jointly-decided items with known truth")
    ap.add_argument("--p1", type=float, help="worker A error rate")
    ap.add_argument("--p2", type=float, help="worker B error rate")
    ap.add_argument("--both-wrong", type=float, help="P(both wrong)")
    ap.add_argument("--power", action="store_true",
                    help="report the sample size needed instead of estimating")
    ap.add_argument("--error-rate", type=float, help="assumed per-worker error rate e")
    ap.add_argument("--rho", type=float, help="rho to detect (or a grid if omitted)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.power:
        e = args.error_rate
        if e is None:
            print("error: --power needs --error-rate", file=sys.stderr)
            return 2
        rhos = [args.rho] if args.rho is not None else [0.1, 0.2, 0.3, 0.5]
        rows = [required_n(e, r) for r in rhos]
        if args.json:
            print(json.dumps(rows, indent=2))
        else:
            print(f"required jointly-decided items (error rate e={e:.2f}, "
                  f"alpha=0.05, power=0.80, c=p):")
            for row in rows:
                if row["required_n"] is None:
                    print(f"  rho={row['rho']:.2f}: {row['reading']}")
                else:
                    print(f"  rho={row['rho']:.2f}: {row['required_n']:,} items "
                          f"(P(both wrong) {row['p_both_wrong_null']:.4f} -> "
                          f"{row['p_both_wrong_alt']:.4f})")
        return 0

    if args.from_agreement:
        result = load_agreement(Path(args.from_agreement))
    elif args.n is not None and None not in (args.p1, args.p2, args.both_wrong):
        result = estimate(args.n, args.p1, args.p2, args.both_wrong)
    else:
        print("error: give --from-agreement FILE, or --n/--p1/--p2/--both-wrong",
              file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"n (joint-decided, truth known) = {result['n_joint_decided']}")
        print(f"  p1 = {result['p1']}   p2 = {result['p2']}   e = {result['mean_error_rate_e']}")
        print(f"  P(both wrong)                   = {result['p_both_wrong']}")
        print(f"  expected if independent (p1*p2) = {result['expected_p_both_wrong_if_independent']}")
        if result["identifiable"] and result["excess"] >= 0:
            print(f"  excess over independence        = {result['excess']:+.6f}"
                  f"   (95% CI {result['excess_ci95'][0]:+.4f} .. {result['excess_ci95'][1]:+.4f})")
            print(f"  rho lower bound (any c)         = {result['rho_lower_bound']:.4f}")
            if result["rho_point_estimate_c_eq_p"] is not None:
                print(f"  rho point estimate (c = p)      = {result['rho_point_estimate_c_eq_p']:.4f}")
        print(f"  detection limit of this sample  = rho >= {result['detection_limit_rho_c_eq_p']}")
        print(f"  {result['reading']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
