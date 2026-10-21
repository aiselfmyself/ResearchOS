#!/usr/bin/env python3
"""Compare two independently RECORDED S4 relation adjudications (instrument).

Input JSON: {"session_id": "...", "items": [
  {"hypothesis_id": "HYP-...", "observation_id": "EVD-...",
   "verdict": "support|refute|neutral|unresolved|null", "rationale": "..."}
]}. The key is (hypothesis_id, observation_id), NOT the relation ID; order and
rationale are ignored for comparison. ``null`` / an absent item is an
abstention or missing judgment, whereas ``unresolved`` is a real verdict.
Compare values under ``measure_agreement.values_equal``; reject an invalid
verdict or duplicate pair rather than silently picking the first. Report
agreement over the union (missing counts against coverage), agreement on
jointly decided pairs and Cohen's kappa (null if undefined), plus retention of
A's support verdicts (for a pre-registered blind re-adjudication).

A comparator CANNOT establish independence, correctness, blinding, or a
self-preference effect. A matching result from the same session is still not
a second adjudicator. Session IDs and methods are reported verbatim; equal
session IDs produce an explicit warning, not a pass/fail. Empty inputs or
zero comparable items are valid measurements with null rates. Exit 0 for a
completed measurement irrespective of agreement; 2 for bad input/usage. Never
writes to the ledgers and is NOT a CI gate.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import measure_agreement as ma
except ImportError:  # running as scripts/relation_agreement.py
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import measure_agreement as ma

VERDICTS = ("support", "refute", "neutral", "unresolved")
Pair = Tuple[str, str]


def load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("session_id"), str) or not data["session_id"].strip():
        raise ValueError(f"{path}: expected object with non-empty session_id")
    if not isinstance(data.get("items"), list):
        raise ValueError(f"{path}: items must be an array")
    items: Dict[Pair, Optional[str]] = {}
    for index, item in enumerate(data["items"], 1):
        if not isinstance(item, dict):
            raise ValueError(f"{path}: items[{index}] must be an object")
        hid, oid = item.get("hypothesis_id"), item.get("observation_id")
        if not isinstance(hid, str) or not hid.strip() or not isinstance(oid, str) or not oid.strip():
            raise ValueError(f"{path}: items[{index}] needs hypothesis_id and observation_id")
        pair = (hid, oid)
        if pair in items:
            raise ValueError(f"{path}: duplicate pair {pair!r}")
        if "verdict" not in item:
            raise ValueError(f"{path}: items[{index}] has no verdict (use null to abstain)")
        value = item["verdict"]
        if value is not None and value not in VERDICTS:
            raise ValueError(f"{path}: items[{index}] invalid verdict {value!r}")
        items[pair] = value
    return {"session_id": data["session_id"].strip(), "method": data.get("method"), "items": items}


def _rate(n: int, d: int) -> Optional[float]:
    return round(n / d, 4) if d else None


def analyse(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Compare parsed bundles; no interpretation of verdicts as ground truth."""
    union = sorted(set(a["items"]) | set(b["items"]))
    rows: List[Dict[str, Any]] = []
    counts = Counter()
    left = Counter()
    right = Counter()
    support_total = retained = support_missing = 0
    for hid, oid in union:
        av, bv = a["items"].get((hid, oid)), b["items"].get((hid, oid))
        if av is None and bv is None:
            status = "both_abstained"
        elif av is None:
            status = "b_only"
        elif bv is None:
            status = "a_only"
        else:
            status = "agree" if ma.values_equal(av, bv) else "disagree"
            left[av] += 1
            right[bv] += 1
        counts[status] += 1
        if av == "support":
            support_total += 1
            retained += int(bv == "support")
            support_missing += int(bv is None)
        rows.append({"hypothesis_id": hid, "observation_id": oid, "a": av, "b": bv, "status": status})
    comparable = counts["agree"] + counts["disagree"]
    po = _rate(counts["agree"], comparable)
    pe = sum(left[v] * right[v] for v in VERDICTS) / comparable**2 if comparable else None
    # Agreement can be perfect on a one-category sample: kappa is undefined,
    # NOT 1.0. Report both raw counts and the chance-corrected statistic.
    kappa = (round((counts["agree"] / comparable - pe) / (1 - pe), 4)
             if pe is not None and pe < 1 else None)
    warnings: List[str] = []
    if a["session_id"] == b["session_id"]:
        warnings.append("same session_id: these records cannot establish independent adjudication")
    if support_missing:
        warnings.append(f"{support_missing} A-support item(s) lack a B verdict; retention is incomplete")
    return {
        "inputs": {"a": {"session_id": a["session_id"], "method": a.get("method")},
                   "b": {"session_id": b["session_id"], "method": b.get("method")}},
        "independence_verified": False,
        "universe": len(union),
        "counts": {key: counts[key] for key in ("agree", "disagree", "a_only", "b_only", "both_abstained")},
        "comparable": comparable,
        "agreement_over_union": _rate(counts["agree"], len(union)),
        "agreement_comparable": po,
        "cohens_kappa": {"kappa": kappa, "po": po, "pe": round(pe, 4) if pe is not None else None, "n": comparable},
        "a_support_retention": {"retained": retained, "total": support_total,
                                "missing_b": support_missing,
                                "rate": _rate(retained, support_total - support_missing)},
        "items": rows,
        "warnings": warnings,
    }


def measure(a_path: Path, b_path: Path) -> Dict[str, Any]:
    return analyse(load(a_path), load(b_path))


def format_human(report: Dict[str, Any]) -> str:
    c = report["counts"]
    r = report["a_support_retention"]
    lines = ["relation_agreement — S4 二重裁定（計測器。正しさ・独立性は保証しない）",
             f"A: {report['inputs']['a']} / B: {report['inputs']['b']}",
             f"union={report['universe']} comparable={report['comparable']} "
             f"agree={c['agree']} disagree={c['disagree']} a_only={c['a_only']} b_only={c['b_only']} "
             f"both_abstained={c['both_abstained']}",
             f"一致率: all={report['agreement_over_union']} decided={report['agreement_comparable']} "
             f"kappa={report['cohens_kappa']['kappa']}",
             f"A support 残存: {r['retained']}/{r['total']} (B 欠測={r['missing_b']}) "
             f"rate on decided={r['rate']}"]
    for row in report["items"]:
        lines.append(f"  {row['hypothesis_id']} x {row['observation_id']}: "
                     f"A={row['a']} B={row['b']} {row['status']}")
    for warning in report["warnings"]:
        lines.append(f"WARNING: {warning}")
    lines.append("独立性・盲検性・正確性は入力メタデータと実行手続きで別途検証すること")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--a", type=Path, required=True, help="first judgments JSON")
    parser.add_argument("--b", type=Path, required=True, help="second judgments JSON")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = measure(args.a, args.b)
    except (OSError, ValueError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else format_human(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
