#!/usr/bin/env python3
"""Reconcile "does the harness change rankings?" across papers, by regime.

THE APPARENT CONTRADICTION
--------------------------
Two papers in this repository's ledger appear to disagree:

* [8] "Stop Comparing LLM Agents Without Disclosing the Harness"
  (arXiv:2605.23950, SRC-20261020-07a3) runs a controlled 3x3 factorial --
  3 models x 3 harnesses on a 100-task SWE-bench Verified subset, 2 runs per
  cell -- and reports **HV/MV = 7.80** with **ranking reversals in 6 of 9**
  model-pair x harness-pair combinations. The harness dominates.

* [9] "Beyond Final Scores" (arXiv:2608.13417, SRC-20261020-4cff) reports in
  §5.1 that **harness choice primarily affects run-to-run stability rather
  than relative model ordering**: best@3 differs by at most 0.035 across
  harnesses, while avg@3 improves by 0.014-0.055. The harness does not
  reorder the models.

THE RECONCILIATION THIS SCRIPT ENCODES
--------------------------------------
The two papers sit on opposite sides of the same quantity:

    R = (spread across models) / (spread across harnesses)

* R < 1  -> the harness spread dominates  -> harness swaps change rankings
* R > 1  -> the model spread dominates    -> harness swaps change stability,
                                             not ordering

Both papers' own numbers put them far apart:

* [8] reports HV/MV = 7.80 as a **variance** ratio, so the spread (SD) ratio
  is sqrt(7.80) = 2.79 in the harness's favour, i.e. **R = 1/2.79 = 0.36**.
  Reversals were observed: 6/9. Consistent with R < 1.
* [9] reports a model spread of 0.237 (avg@3, strongest vs weakest) against a
  harness effect of 0.014-0.055, i.e. **R = 4.3 .. 16.9** (avg@3), or
  **R >= 3.5** on best@3 (0.122 / 0.035). No reordering was observed.
  Consistent with R > 1.

**The papers do not contradict each other; they sample different regimes.**
Neither claims a universal law, and the reconciliation is a hypothesis about
a threshold at R ~ 1 -- it is supported by exactly two data points and is
meant to be falsified by the third paper someone adds.

UNITS
-----
R must compare like with like. Pass either

* ``--model-spread`` / ``--harness-spread`` (both SD-like), or
* ``--model-variance`` / ``--harness-variance`` (the script takes the square
  root of each before dividing), or
* ``--hv-mv`` (a harness/model *variance* ratio, as [8] reports, in which
  case R = 1/sqrt(hv_mv)).

Usage:
    python3 scripts/harness_regime.py --reference
    python3 scripts/harness_regime.py --hv-mv 7.80 --label "[8]"
    python3 scripts/harness_regime.py --model-spread 0.237 --harness-spread 0.055
    python3 scripts/harness_regime.py --model-variance 0.004 --harness-variance 0.001

Exit code: always 0 -- an instrument, never a gate (the same rule as
scripts/measure_agreement.py and scripts/estimate_rho.py).
Standard library only.
"""
from __future__ import annotations

import argparse
import json
import math
from typing import Any, Dict, List, Optional

# The two reference cases, taken verbatim from the ledger:
#   EVD-20261021-3d5a  ([8] factorial: HV/MV 7.80, reversals 6/9)
#   EVD-20261021-1564 / EVD-20261021-7dd6  ([9] spreads and harness effects)
REFERENCE = [
    {
        "label": "[8] arXiv:2605.23950 -- 3 models x 3 harnesses (SWE-bench Verified subset)",
        "R_lo": 1.0 / math.sqrt(7.80),
        "R_hi": 1.0 / math.sqrt(7.80),
        "observed_reordering": True,
        "detail": "HV/MV = 7.80 (variance ratio) -> spread ratio sqrt(7.80) = 2.79 "
                  "in the harness's favour; reversals in 6 of 9 model-pair x "
                  "harness-pair combinations",
        "evidence": "EVD-20261021-3d5a",
    },
    {
        "label": "[9] arXiv:2608.13417 -- 7 models x 36 long-horizon tasks (avg@3)",
        "R_lo": 0.237 / 0.055,
        "R_hi": 0.237 / 0.014,
        "observed_reordering": False,
        "detail": "model spread 0.237 vs harness effect 0.014-0.055",
        "evidence": "EVD-20261021-1564",
    },
    {
        "label": "[9] arXiv:2608.13417 -- same, best@3",
        "R_lo": 0.122 / 0.035,
        "R_hi": None,  # only an upper bound on the harness effect is reported
        "observed_reordering": False,
        "detail": "model spread 0.122 vs harness effect at most 0.035 -> R >= 3.5",
        "evidence": "EVD-20261021-7dd6",
    },
]


def regime(r: float) -> Dict[str, Any]:
    """Classify a spread ratio R and predict whether rankings flip."""
    return {
        "R": r,
        "dominant": "harness" if r < 1.0 else "model",
        "predicts_reordering": r < 1.0,
        "reading": (
            f"R = {r:.3f}: harness spread dominates -> harness swaps are expected "
            f"to REORDER the models"
            if r < 1.0 else
            f"R = {r:.3f}: model spread dominates -> harness swaps are expected to "
            f"change stability, not ordering"
        ),
    }


def from_spreads(model_spread: float, harness_spread: float) -> Optional[float]:
    if harness_spread <= 0:
        return None
    return model_spread / harness_spread


def from_variances(model_var: float, harness_var: float) -> Optional[float]:
    if model_var < 0 or harness_var <= 0:
        return None
    return math.sqrt(model_var) / math.sqrt(harness_var)


def from_hv_mv(hv_mv: float) -> Optional[float]:
    """[8] reports harness-variance / model-variance; invert it."""
    if hv_mv <= 0:
        return None
    return 1.0 / math.sqrt(hv_mv)


def check_reference(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Does the R < 1 threshold predict each reference case correctly?"""
    out = []
    for row in rows:
        r = row["R_lo"] if row["R_hi"] is None else (row["R_lo"] + row["R_hi"]) / 2
        pred = r < 1.0
        out.append({
            "label": row["label"],
            "R": r,
            "predicted_reordering": pred,
            "observed_reordering": row["observed_reordering"],
            "consistent": pred == row["observed_reordering"],
            "detail": row["detail"],
            "evidence": row["evidence"],
        })
    return out


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--reference", action="store_true",
                    help="print the two built-in reference cases and check the threshold")
    ap.add_argument("--model-spread", type=float)
    ap.add_argument("--harness-spread", type=float)
    ap.add_argument("--model-variance", type=float)
    ap.add_argument("--harness-variance", type=float)
    ap.add_argument("--hv-mv", type=float,
                    help="harness-variance / model-variance ratio, as [8] reports")
    ap.add_argument("--label", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.reference:
        rows = check_reference(REFERENCE)
        if args.json:
            print(json.dumps(rows, indent=2))
            return 0
        print("R = (spread across models) / (spread across harnesses)\n")
        for row in rows:
            flag = "consistent" if row["consistent"] else "INCONSISTENT"
            print(f"  {row['label']}")
            print(f"      R = {row['R']:.3f}   predicted reordering = "
                  f"{row['predicted_reordering']}   observed = "
                  f"{row['observed_reordering']}   -> {flag}")
            print(f"      {row['detail']}   [{row['evidence']}]")
        all_ok = all(r["consistent"] for r in rows)
        print(f"\n  threshold R ~ 1 agrees with "
              f"{sum(1 for r in rows if r['consistent'])}/{len(rows)} reference cases.")
        print("  Caveat: this is two data points, not a fitted law. Add a third paper "
              "before trusting it.")
        return 0

    r: Optional[float] = None
    if args.hv_mv is not None:
        r = from_hv_mv(args.hv_mv)
    elif args.model_variance is not None and args.harness_variance is not None:
        r = from_variances(args.model_variance, args.harness_variance)
    elif args.model_spread is not None and args.harness_spread is not None:
        r = from_spreads(args.model_spread, args.harness_spread)

    if r is None:
        print("error: give --hv-mv, or --model-variance/--harness-variance, or "
              "--model-spread/--harness-spread (or use --reference)", file=sys.stderr)
        return 2

    result = regime(r)
    if args.label:
        result["label"] = args.label
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if args.label:
            print(args.label)
        print(f"  {result['reading']}")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main())
