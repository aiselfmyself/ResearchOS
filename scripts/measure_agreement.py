#!/usr/bin/env python3
"""Measure agreement and correlated errors between two extraction outputs.

Session B of the 2026-10-20 parallel experiment
(docs/parallel-experiment-2026-10-20.md).  Two independent sessions
(A and A') read the SAME paper and emit the same extraction items in
the playbook §4 JSON format.  This tool compares the two outputs item
by item and computes:

  * per-item verdicts: agree / disagree / both-missing, plus a-only /
    b-only when one side never covered the item (coverage gaps count
    against agreement, so they are visible in the rate's denominator);
  * the agreement rate (agree / all items in the universe);
  * Cohen's kappa at the value level (chance-corrected agreement);
  * when ground truth is supplied (--truth), each worker's error rate
    p1 / p2, the observed co-error rate P(both wrong), the independence
    null p1 * p2, and lift = P(both wrong) / (p1 * p2) -- the same idea
    as the amplification factor in gitswarm/readout_sim.py.
    lift > 1 means the two workers erred together more often than
    independence predicts: their errors are positively correlated.

WHAT THIS TOOL IS AND IS NOT
------------------------------
It is an instrument, not a gate: the exit code is ALWAYS 0 for any
completed run, including runs whose inputs are unreadable (the problem
is reported on stderr instead), so it can never fail a CI run.  Only
CLI misuse (argparse) exits non-zero.  It measures agreement between
two outputs; it does not measure correctness unless --truth is given.
Even with truth, it cannot separate worker homogeneity (rho) from
deference to a shared view (c), because both sessions read the same
input -- that confound is documented in the experiment doc §1 and in
the companion memo contributions/2026-10-20_agreement_measurement.md.

Comparison rules (deliberately strict; the memo documents why):
  * numbers (int/float, not bool) compare within --tol (default 1e-6);
  * strings compare after whitespace collapsing and case-folding;
  * lists compare as multisets (order-insensitive);
  * JSON null and the string "unknown" are ABSTENTIONS: neither right
    nor wrong.  They are excluded from the error-rate denominators,
    because counting them as errors would inflate p1/p2 and distort
    lift;
  * values must have the same JSON type to agree -- no "42" == 42
    coercion, because a type mismatch is a real disagreement about the
    extraction, not a rounding difference.

Cohen's kappa uses the emitted values as nominal categories over the
jointly rated items (both workers emitted a usable value).  Numeric
categories are quantized to the tolerance grid so the chance estimate
pe respects --tol; the observed agreement po is taken from the
authoritative verdicts.  Kappa is null when nothing was jointly rated.

The truth analysis (p1, p2, lift) is computed on the joint-decided
subset: items whose truth is known and where BOTH workers emitted a
usable value.  p1, p2 and P(both wrong) are all defined on that same
subset, so the independence null p1 * p2 is exactly the product of the
two marginals.  Per-worker error rates over ALL items that worker
decided are reported alongside, for context.

Usage:
    python3 scripts/measure_agreement.py --a a.json --b b.json \
        [--truth truth.json] [--tol 1e-6] [--json]

Standard library only.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]

# Verdict taxonomy.  The first three are required by the task spec;
# a-only / b-only are coverage gaps (present in exactly one output).
AGREE = "agree"
DISAGREE = "disagree"
BOTH_MISSING = "both-missing"
A_ONLY = "a-only"
B_ONLY = "b-only"
VERDICTS = (AGREE, DISAGREE, BOTH_MISSING, A_ONLY, B_ONLY)

DEFAULT_TOL = 1e-6
# Below this many jointly decided items, lift carries no statistical
# weight.  The real E2 run has n = 1 pair of sessions, so this warning
# is expected to fire; it is a property of the experiment, not a bug.
MIN_JOINT_N = 30


# --------------------------------------------------------------------------
# Value comparison
# --------------------------------------------------------------------------
def is_abstention(value: Any) -> bool:
    """True for JSON null and the string "unknown" (an abstention).

    An abstention is neither right nor wrong.  Treating it as either
    would distort p1/p2 and therefore lift -- see the memo §3.
    """
    if value is None:
        return True
    return isinstance(value, str) and value.strip().casefold() == "unknown"


def normalize_string(value: str) -> str:
    """Case-fold and collapse all whitespace runs to single spaces."""
    return " ".join(value.casefold().split())


def values_equal(a: Any, b: Any, tol: float = DEFAULT_TOL) -> bool:
    """Compare two extracted values under the documented rules."""
    if isinstance(a, bool) or isinstance(b, bool):
        # bool before numbers: True must not equal 1.
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= tol
    if isinstance(a, str) and isinstance(b, str):
        return normalize_string(a) == normalize_string(b)
    if isinstance(a, list) and isinstance(b, list):
        return _multiset_equal(a, b, tol)
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(
            values_equal(a[key], b[key], tol) for key in a
        )
    return False  # different JSON types never agree


def _multiset_equal(a: Sequence[Any], b: Sequence[Any], tol: float) -> bool:
    """Order-insensitive list comparison (multiset matching).

    Each element of a must consume exactly one element of b.  With the
    tolerance comparator the greedy match is not a perfect equivalence
    relation at boundary cases; that is documented in the memo and the
    raw counts are always reported alongside.
    """
    if len(a) != len(b):
        return False
    remaining = list(b)
    for x in a:
        for index, y in enumerate(remaining):
            if values_equal(x, y, tol):
                del remaining[index]
                break
        else:
            return False
    return True


def category_key(value: Any, tol: float = DEFAULT_TOL) -> Tuple:
    """Hashable nominal category for Cohen's kappa.

    Numbers are quantized to the tolerance grid so that values which
    compare equal under --tol land in the same bucket; everything else
    is keyed by its normalized form.
    """
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, (int, float)):
        return ("num", round(float(value) / tol))
    if isinstance(value, str):
        return ("str", normalize_string(value))
    if isinstance(value, list):
        return ("list", tuple(sorted(category_key(v, tol) for v in value)))
    if isinstance(value, dict):
        return (
            "dict",
            tuple(sorted((k, category_key(v, tol)) for k, v in value.items())),
        )
    return ("other", repr(value))


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------
def load_extraction(path: Path) -> Dict[str, Any]:
    """Load one playbook §4 extraction JSON into an id -> item map."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise ValueError(
            f"{path}: expected an object with an 'items' list "
            "(playbook §4 format)"
        )
    by_id: Dict[str, Dict[str, Any]] = {}
    duplicates: List[str] = []
    for item in data["items"]:
        if not isinstance(item, dict) or "id" not in item:
            raise ValueError(
                f"{path}: every entry in 'items' must be an object "
                "with an 'id'"
            )
        item_id = str(item["id"])
        if item_id in by_id:
            duplicates.append(item_id)
            continue  # first occurrence wins; the duplicate is reported
        by_id[item_id] = item
    return {
        "meta": {key: value for key, value in data.items() if key != "items"},
        "by_id": by_id,
        "duplicates": duplicates,
    }


# --------------------------------------------------------------------------
# Measurement
# --------------------------------------------------------------------------
def _value_of(extraction: Optional[Dict[str, Any]], item_id: str) -> Any:
    item = extraction["by_id"].get(item_id) if extraction else None
    return item.get("value") if item is not None else None


def _status_against_truth(
    value: Any, present: bool, truth_value: Any, tol: float
) -> str:
    """correct / wrong / unknown for one worker on one item."""
    if not present or is_abstention(value):
        return "unknown"
    return "correct" if values_equal(value, truth_value, tol) else "wrong"


def measure(
    a_path: Path,
    b_path: Path,
    truth_path: Optional[Path],
    tol: float,
) -> Dict[str, Any]:
    """Run the whole measurement and return the report as a dict."""
    a = load_extraction(a_path)
    b = load_extraction(b_path)
    truth = load_extraction(truth_path) if truth_path else None

    warnings: List[str] = []
    for name, extraction in (("a", a), ("b", b), ("truth", truth)):
        if extraction and extraction["duplicates"]:
            warnings.append(
                f"{name}: duplicate item ids (first occurrence wins): "
                f"{extraction['duplicates']}"
            )

    universe = sorted(
        set(a["by_id"]) | set(b["by_id"]) | set(truth["by_id"] if truth else {})
    )
    if not universe:
        warnings.append("universe is empty: no items in any input")

    items: List[Dict[str, Any]] = []
    verdict_counts = {verdict: 0 for verdict in VERDICTS}
    rated: List[Tuple[Any, Any]] = []  # both workers emitted a value

    for item_id in universe:
        a_item = a["by_id"].get(item_id)
        b_item = b["by_id"].get(item_id)
        truth_item = truth["by_id"].get(item_id) if truth else None
        a_present = a_item is not None
        b_present = b_item is not None
        a_value = a_item.get("value") if a_present else None
        b_value = b_item.get("value") if b_present else None
        truth_value = truth_item.get("value") if truth_item is not None else None
        truth_known = truth_item is not None and not is_abstention(truth_value)

        a_missing = not a_present or is_abstention(a_value)
        b_missing = not b_present or is_abstention(b_value)

        if not a_present and not b_present:
            verdict, note = BOTH_MISSING, "item absent from both outputs"
        elif not a_present:
            verdict, note = B_ONLY, "present only in B (coverage gap)"
        elif not b_present:
            verdict, note = A_ONLY, "present only in A (coverage gap)"
        elif a_missing and b_missing:
            verdict, note = BOTH_MISSING, "both workers abstained (unknown/null)"
        elif a_missing or b_missing:
            verdict = DISAGREE
            who = "A" if a_missing else "B"
            note = f"{who} abstained (unknown/null) while the other asserted a value"
        elif values_equal(a_value, b_value, tol):
            verdict, note = AGREE, "values match under the comparison rules"
        else:
            verdict, note = DISAGREE, "values differ under the comparison rules"

        verdict_counts[verdict] += 1
        if verdict in (AGREE, DISAGREE) and not a_missing and not b_missing:
            rated.append((a_value, b_value))

        a_status = (
            _status_against_truth(a_value, a_present, truth_value, tol)
            if truth_known
            else None
        )
        b_status = (
            _status_against_truth(b_value, b_present, truth_value, tol)
            if truth_known
            else None
        )

        items.append(
            {
                "id": item_id,
                "verdict": verdict,
                "note": note,
                "a_present": a_present,
                "b_present": b_present,
                "a_value": a_value if a_present else None,
                "b_value": b_value if b_present else None,
                "truth_value": truth_value if truth_item is not None else None,
                "truth_known": truth_known,
                "a_status": a_status,
                "b_status": b_status,
            }
        )

    n_items = len(universe)
    n_agree = verdict_counts[AGREE]
    n_comparable = verdict_counts[AGREE] + verdict_counts[DISAGREE]
    report: Dict[str, Any] = {
        "schema": "agreement-measurement/v1",
        "generated_by": "scripts/measure_agreement.py",
        "inputs": {
            "a": str(a_path),
            "b": str(b_path),
            "truth": str(truth_path) if truth_path else None,
            "tol": tol,
        },
        "universe": {"n_items": n_items, "ids": universe},
        "items": items,
        "verdict_counts": verdict_counts,
        "agreement_rate": round(n_agree / n_items, 6) if n_items else None,
        "agreement_rate_comparable": (
            round(n_agree / n_comparable, 6) if n_comparable else None
        ),
        "warnings": warnings,
    }

    # -- Cohen's kappa over the jointly rated items --------------------
    n_rated = len(rated)
    if n_rated == 0:
        kappa_result: Dict[str, Any] = {
            "kappa": None,
            "po": None,
            "pe": None,
            "n_rated": 0,
            "note": "no item was jointly rated (both workers emitted a "
            "usable value); kappa is undefined",
        }
    else:
        counts_a = Counter(category_key(x, tol) for x, _ in rated)
        counts_b = Counter(category_key(y, tol) for _, y in rated)
        po = sum(1 for x, y in rated if values_equal(x, y, tol)) / n_rated
        pe = sum(
            (counts_a[key] / n_rated) * (counts_b[key] / n_rated)
            for key in set(counts_a) | set(counts_b)
        )
        if pe >= 1.0 - 1e-12:
            # Both raters constant on one category: chance agreement is
            # total, and so is observed agreement.
            kappa = 1.0
        else:
            kappa = (po - pe) / (1.0 - pe)
        kappa_result = {
            "kappa": round(kappa, 6),
            "po": round(po, 6),
            "pe": round(pe, 6),
            "n_rated": n_rated,
            "note": "value-level Cohen's kappa: categories are the "
            "normalized emitted values, jointly rated items only "
            "(both workers gave a usable value); numeric categories "
            "are quantized to the --tol grid for pe",
        }
    report["cohens_kappa"] = kappa_result

    # -- Truth analysis: error rates and lift ---------------------------
    if truth is None:
        report["truth_analysis"] = None
    else:
        joint = [
            item
            for item in items
            if item["truth_known"]
            and item["a_status"] in ("correct", "wrong")
            and item["b_status"] in ("correct", "wrong")
        ]
        n_joint = len(joint)
        wrong_a = sum(1 for item in joint if item["a_status"] == "wrong")
        wrong_b = sum(1 for item in joint if item["b_status"] == "wrong")
        both_wrong = sum(
            1
            for item in joint
            if item["a_status"] == "wrong" and item["b_status"] == "wrong"
        )
        p1 = wrong_a / n_joint if n_joint else None
        p2 = wrong_b / n_joint if n_joint else None
        p_both_wrong = both_wrong / n_joint if n_joint else None
        expected = p1 * p2 if (p1 is not None and p2 is not None) else None
        lift = (
            p_both_wrong / expected
            if expected is not None and expected > 0.0
            else None
        )

        if lift is None:
            reading = (
                "undefined: at least one worker made no errors on the "
                "joint-decided subset, so the independence null "
                "p1*p2 is zero"
            )
        elif lift > 1.0:
            reading = (
                "lift > 1: the two workers erred TOGETHER more often "
                "than independence predicts -- errors are positively "
                "correlated"
            )
        elif lift < 1.0:
            reading = (
                "lift < 1: co-errors are RARER than independence "
                "predicts (disjoint or anti-correlated errors)"
            )
        else:
            reading = "lift = 1: co-errors match the independence null"

        if n_joint and n_joint < MIN_JOINT_N:
            warnings.append(
                f"n_joint={n_joint} < {MIN_JOINT_N}: statistical power "
                "is very low; lift is an observation, not an estimate "
                "(experiment doc §1)"
            )

        decided_a = [
            item for item in items if item["truth_known"] and item["a_status"] in ("correct", "wrong")
        ]
        decided_b = [
            item for item in items if item["truth_known"] and item["b_status"] in ("correct", "wrong")
        ]
        report["truth_analysis"] = {
            "n_truth_known": sum(1 for item in items if item["truth_known"]),
            "n_joint_decided": n_joint,
            "worker_a": {
                "decided": len(decided_a),
                "correct": sum(1 for i in decided_a if i["a_status"] == "correct"),
                "wrong": sum(1 for i in decided_a if i["a_status"] == "wrong"),
                "unknown": sum(
                    1 for item in items if item["truth_known"] and item["a_status"] == "unknown"
                ),
                "error_rate_all_decided": (
                    round(
                        sum(1 for i in decided_a if i["a_status"] == "wrong")
                        / len(decided_a),
                        6,
                    )
                    if decided_a
                    else None
                ),
            },
            "worker_b": {
                "decided": len(decided_b),
                "correct": sum(1 for i in decided_b if i["b_status"] == "correct"),
                "wrong": sum(1 for i in decided_b if i["b_status"] == "wrong"),
                "unknown": sum(
                    1 for item in items if item["truth_known"] and item["b_status"] == "unknown"
                ),
                "error_rate_all_decided": (
                    round(
                        sum(1 for i in decided_b if i["b_status"] == "wrong")
                        / len(decided_b),
                        6,
                    )
                    if decided_b
                    else None
                ),
            },
            "p1": round(p1, 6) if p1 is not None else None,
            "p2": round(p2, 6) if p2 is not None else None,
            "n_both_wrong": both_wrong,
            "p_both_wrong": round(p_both_wrong, 6) if p_both_wrong is not None else None,
            "expected_p_both_wrong_if_independent": (
                round(expected, 6) if expected is not None else None
            ),
            "lift": round(lift, 6) if lift is not None else None,
            "reading": reading,
            "definition": (
                "p1, p2 and P(both wrong) are computed on the "
                "joint-decided subset (truth known AND both workers "
                "emitted a usable value), so the independence null "
                "p1*p2 is the product of the same marginals; "
                "error_rate_all_decided is the per-worker rate over "
                "every item that worker decided, given for context"
            ),
        }

    return report


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------
def _short(value: Any, present: bool, limit: int = 48) -> str:
    if not present:
        return "(not in file)"
    if is_abstention(value):
        return "(abstained)"
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def format_human(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("Agreement measurement (ResearchOS session B instrument)")
    for key in ("a", "b", "truth"):
        path = report["inputs"][key]
        label = key if key != "truth" else "truth"
        lines.append(f"  {label:<6}: {path}")
    lines.append(f"  tol   : {report['inputs']['tol']}")
    lines.append("")
    lines.append(
        f"Universe: {report['universe']['n_items']} item ids "
        "(union of A, B[, truth])"
    )
    lines.append("")
    lines.append("Per-item verdicts:")
    for item in report["items"]:
        left = _short(item["a_value"], item["a_present"])
        right = _short(item["b_value"], item["b_present"])
        lines.append(
            f"  {item['id']:<6} {item['verdict']:<12} "
            f"A={left}  B={right}"
        )
        if item["truth_known"]:
            lines.append(
                f"        truth={_short(item['truth_value'], True)}  "
                f"A:{item['a_status']} B:{item['b_status']}"
            )
        elif report["truth_analysis"] is not None:
            lines.append(
                "        truth: unknown -> item excluded "
                "from the error analysis"
            )
        lines.append(f"        note: {item['note']}")

    counts = report["verdict_counts"]
    lines.append("")
    lines.append(
        "Verdict counts: "
        + " ".join(f"{name}={counts[name]}" for name in VERDICTS)
    )
    lines.append(
        f"Agreement rate (agree / all items): "
        f"{counts[AGREE]}/{report['universe']['n_items']} "
        f"= {report['agreement_rate']}"
    )
    comparable = counts[AGREE] + counts[DISAGREE]
    lines.append(
        f"Agreement rate (comparable items only): "
        f"{counts[AGREE]}/{comparable} "
        f"= {report['agreement_rate_comparable']}"
    )
    kappa = report["cohens_kappa"]
    lines.append(
        "Cohen's kappa (value-level, jointly rated): "
        f"{kappa['kappa']}  (po={kappa['po']}, pe={kappa['pe']}, "
        f"n_rated={kappa['n_rated']})"
    )

    truth = report["truth_analysis"]
    if truth is not None:
        lines.append("")
        lines.append("--- truth analysis (correlated errors) ---")
        lines.append(f"Items with known truth: {truth['n_truth_known']}")
        lines.append(
            f"Joint-decided subset (both workers answered): "
            f"{truth['n_joint_decided']}"
        )
        for worker in ("worker_a", "worker_b"):
            info = truth[worker]
            lines.append(
                f"  {worker}: decided {info['decided']} "
                f"(correct {info['correct']}, wrong {info['wrong']}), "
                f"abstained {info['unknown']} -> error rate over all "
                f"decided = {info['error_rate_all_decided']}"
            )
        lines.append(f"  p1 (A error rate, joint subset) = {truth['p1']}")
        lines.append(f"  p2 (B error rate, joint subset) = {truth['p2']}")
        lines.append(
            f"  P(both wrong)                     = "
            f"{truth['p_both_wrong']} ({truth['n_both_wrong']} item(s))"
        )
        lines.append(
            f"  expected if independent (p1*p2)   = "
            f"{truth['expected_p_both_wrong_if_independent']}"
        )
        lines.append(f"  lift = P(both wrong) / (p1*p2)      = {truth['lift']}")
        lines.append(f"  reading: {truth['reading']}")

    if report["warnings"]:
        lines.append("")
        for warning in report["warnings"]:
            lines.append(f"WARNING: {warning}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure agreement and correlated errors between "
        "two extraction outputs (an instrument, never a gate)"
    )
    parser.add_argument("--a", required=True, type=Path, help="first extraction JSON")
    parser.add_argument("--b", required=True, type=Path, help="second extraction JSON")
    parser.add_argument(
        "--truth", type=Path, default=None, help="ground-truth JSON (optional)"
    )
    parser.add_argument(
        "--tol",
        type=float,
        default=DEFAULT_TOL,
        help=f"numeric comparison tolerance (default: {DEFAULT_TOL})",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(list(argv) if argv is not None else None)

    # An instrument never gates: any measurement-level problem is
    # reported and the exit code stays 0.
    try:
        report = measure(args.a, args.b, args.truth, args.tol)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        print(
            "measurement tool: exit code stays 0 (this is an instrument, "
            "not a gate; see scripts/measure_agreement.py docstring)",
            file=sys.stderr,
        )
        return 0

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_human(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
