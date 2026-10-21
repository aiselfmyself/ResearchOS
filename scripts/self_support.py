#!/usr/bin/env python3
"""Measure self-support in the hypothesis/relation ledgers (Phase 3 instrument).

A support REL with ``derived_from: true`` uses the hypothesis's own generation
input and must not be counted as independent support. Only explicit booleans
enter the measured rate; the 2026-10-21 pre-cycle RELs have NO such flag and
are UNKNOWN, not ``false``. The bound [flagged true / all support,
(flagged true + unknown) / all support] makes that missingness visible.

A separate *historical overlap proxy* counts unflagged support whose EVD is in
a legacy hypothesis's ``evidence_ids``. That list may be a support list, NOT a
record of generation inputs; it is not added to the measured numerator. The
2026-10-21 round-0 estimate used that proxy. An explicit
``derived_from_evidence_ids`` list enables a consistency warning for unflagged
or false support from declared generation inputs. This instrument does not
repair/guess flags and does not edit the ledgers.

Rates describe the current SNAPSHOT, not a particular round: historical RELs
have no round field. Run each round and record the snapshot in RUN.metrics to
compare deltas. Exit 0 means a measurement completed (including zero support
or a high self-support rate); exit 2 means invalid input/I/O. NOT a CI gate.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

try:
    import gap_scan as gs
except ImportError:  # running as scripts/self_support.py
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import gap_scan as gs

ROOT = gs.ROOT


def _rate(numerator: int, denominator: int) -> Optional[float]:
    return round(numerator / denominator, 4) if denominator else None


def _bucket(hypothesis_id: str) -> Dict[str, Any]:
    return {
        "hypothesis_id": hypothesis_id,
        "support_total": 0,
        "derived_true": 0,
        "derived_false": 0,
        "unknown_flag": 0,
        "legacy_overlap_proxy": 0,
    }


def analyse(
    hypotheses: List[Dict[str, Any]], relations: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Pure snapshot measurement. A missing flag is UNKNOWN even on legacy RELs."""
    by_id: Dict[str, Dict[str, Any]] = {}
    for row in hypotheses:
        hid = row.get("hypothesis_id")
        if not isinstance(hid, str):
            continue  # validator checks malformed identities; no rate exists
        if hid in by_id:
            raise gs.LedgerError(f"duplicate hypothesis_id {hid!r}; cannot measure by picking one")
        by_id[hid] = row
    rows = {hid: _bucket(hid) for hid in sorted(by_id)}
    warnings: List[str] = []
    seen_support_pairs: Dict[tuple, str] = {}
    non_support = 0
    for rel in relations:
        if rel.get("verdict") != "support":
            non_support += 1
            continue
        hid = rel.get("hypothesis_id")
        rid = str(rel.get("relation_id", "<unknown>"))
        oid = rel.get("observation_id")
        if hid not in rows:
            warnings.append(f"{rid}: unknown hypothesis {hid!r}; support omitted")
            continue
        pair = (hid, str(oid))
        if pair in seen_support_pairs:
            warnings.append(f"{rid}: duplicate support pair {pair!r} also in {seen_support_pairs[pair]}; counting REL records, not distinct observations")
        else:
            seen_support_pairs[pair] = rid
        row = rows[hid]
        hyp = by_id[hid]
        row["support_total"] += 1
        flag = rel.get("derived_from")
        declared = hyp.get("derived_from_evidence_ids")
        if flag is True:
            row["derived_true"] += 1
            if isinstance(declared, list) and oid not in declared:
                warnings.append(f"{rid}: derived_from=true but {oid!r} not in {hid}.derived_from_evidence_ids")
        elif flag is False:
            row["derived_false"] += 1
            if isinstance(declared, list) and oid in declared:
                warnings.append(f"{rid}: derived_from=false despite {oid!r} in {hid}.derived_from_evidence_ids")
        else:
            row["unknown_flag"] += 1
            if isinstance(declared, list) and oid in declared:
                warnings.append(f"{rid}: missing derived_from for declared generation input {oid!r} of {hid}")
            elif not isinstance(declared, list) and oid in (hyp.get("evidence_ids") or []):
                row["legacy_overlap_proxy"] += 1

    for row in rows.values():
        known = row["derived_true"] + row["derived_false"]
        row["known_flag_rate"] = _rate(row["derived_true"], known)
        row["flag_coverage"] = _rate(known, row["support_total"])
        row["possible_rate_bounds"] = [
            _rate(row["derived_true"], row["support_total"]),
            _rate(row["derived_true"] + row["unknown_flag"], row["support_total"]),
        ]
        row["legacy_overlap_proxy_rate"] = _rate(row["legacy_overlap_proxy"], row["unknown_flag"])
    totals = {
        key: sum(row[key] for row in rows.values())
        for key in ("support_total", "derived_true", "derived_false", "unknown_flag", "legacy_overlap_proxy")
    }
    totals["non_support_relations"] = non_support
    known = totals["derived_true"] + totals["derived_false"]
    totals["known_flag_rate"] = _rate(totals["derived_true"], known)
    totals["flag_coverage"] = _rate(known, totals["support_total"])
    totals["possible_rate_bounds"] = [
        _rate(totals["derived_true"], totals["support_total"]),
        _rate(totals["derived_true"] + totals["unknown_flag"], totals["support_total"]),
    ]
    return {
        "definition": "Explicit boolean derived_from on support RELs only; missing/non-boolean = unknown. Historical evidence_ids overlap is a proxy, NOT proof of generation.",
        "snapshot_not_round": True,
        "totals": totals,
        "per_hypothesis": [rows[hid] for hid in sorted(rows)],
        "warnings": sorted(warnings),
    }


def measure(state_dir: Optional[Path] = None) -> Dict[str, Any]:
    state = Path(state_dir) if state_dir is not None else ROOT / "state"
    if not state.is_dir():
        raise gs.LedgerError(f"state directory not found: {state}")
    return analyse(gs.load_ledger("hypotheses", state), gs.load_ledger("relations", state))


def format_human(report: Dict[str, Any]) -> str:
    totals = report["totals"]
    lines = ["self_support — 生成元による支持（計測器。ゲートではない）",
             f"snapshot: support={totals['support_total']} / explicit true={totals['derived_true']} "
             f"false={totals['derived_false']} unknown={totals['unknown_flag']}",
             f"既知フラグ内の自己支持率={totals['known_flag_rate']} "
             f"(flag coverage={totals['flag_coverage']}; 全体の可能範囲={totals['possible_rate_bounds']})",
             f"legacy evidence_ids 重なり（独立した証拠ではない推定）={totals['legacy_overlap_proxy']}",
             "仮説ごと（既知フラグ内の割合; unknown は分母に入れない）:"]
    for row in report["per_hypothesis"]:
        lines.append(f"  {row['hypothesis_id']}: {row['derived_true']}/{row['derived_true'] + row['derived_false']} "
                     f"= {row['known_flag_rate']}  unknown={row['unknown_flag']} "
                     f"legacy overlap proxy={row['legacy_overlap_proxy']}")
    for warning in report["warnings"]:
        lines.append(f"WARNING: {warning}")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--state-dir", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = measure(args.state_dir)
    except (gs.LedgerError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else format_human(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
