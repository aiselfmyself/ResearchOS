#!/usr/bin/env python3
"""Report hypothesis-coverage gaps in the relation ledger. An instrument.

WHAT THIS IS (AND IS NOT)
-------------------------
SHELDON (arXiv:2610.18025) separates the hypothesis space from the observation
space and stores, for every (hypothesis, observation) pair, a four-valued
verdict in ``E_t : H x O -> {support, refute, neutral, unresolved}``. The
reading memo ``contributions/2026-10-21_sheldon_reading.md`` derives four
predicates over that table (section 3.3) and a deterministic rule for the
``provisional`` attribute (section 3.4):

    unassessed(o)  := there is no REL record for o at all
    unexplained(o) := there is no REL record (h, o) with verdict "support"
    refutation(h)  := exists o with E(h, o) = "refute" and not provisional(o)
    provisional(o) := no other EVD with the same observation_key has a
                      different source_id

The verdicts themselves require judgement and are written into
``state/relations.jsonl`` by a separate adjudication step (never derived
mechanically from VER records -- memo section 5.4). *This script only counts
what is already recorded.* It is an instrument, not a gate:

  * it never writes to the ledger;
  * a hole in coverage is a *finding*, not a failure -- a run that reports
    100% unassessed still exits 0;
  * it is not wired into CI (the same standing as ``measure_agreement.py``,
    ``estimate_rho.py``, ``harness_regime.py``, ``holdout_eval.py`` and
    ``prune_candidates.py``).

Exit codes: 0 = measurement completed (whatever it found); 2 = usage or I/O
error (a missing or unparseable ledger, or bad arguments). 1 is never
returned by design, so any non-zero code means "could not measure", not
"found gaps".

FAIL-CLOSED RULE FOR ``provisional``
------------------------------------
A refutation is a strong claim, so the instrument refuses to count one without
independent corroboration (memo section 3.4, §7.2):

  * ``observation_key`` defaults to the record's own ``evidence_id``, which is
    unique -- so an EVD without an explicit key is always provisional;
  * an EVD with no usable ``source_id`` is provisional: a missing source
    cannot corroborate anything;
  * a REL whose ``observation_id`` does not resolve to an EVD is provisional
    (there is nothing to corroborate);
  * when the REL resolves to an EVD, an explicit boolean ``provisional`` on
    the REL record wins over the derived value, in both directions (the
    record states what the adjudication found; the derivation is only the
    default). A dangling ``observation_id`` cannot be un-gated this way: with
    no record there is nothing to corroborate, so it stays provisional even
    if the REL says ``false``;
  * a non-boolean ``provisional`` is ignored and the derived value is used.

The existing 2026-10-21 ledger has no ``observation_key`` on any EVD, so every
observation is provisional and no refutation can be counted. That is the
intended conservative default, not a bug: the baseline memo under
``contributions/`` records the measured result.

Two readings of "unassessed" are reported
-----------------------------------------
The prompt-level definition above (no REL record at all) is *not* the only
defensible one: SHELDON's ``unresolved`` verdict means "not yet assessed", so
an observation whose only RELs are ``unresolved`` is arguably unassessed too.
The primary count follows the literal definition; ``unresolved_only`` reports
the narrower set (at least one REL, every verdict ``unresolved``) so the gap
between the two readings is visible instead of silently chosen.

Observations without a REL still count as unassessed and unexplained even if
some REL mentions a hypothesis that does not exist: a record exists. Reference
integrity is ``validate_state.py``'s job, not this instrument's; dangling
references are listed under ``anomalies`` so they are not invisible.

REUSE
-----
Ledger reading is not reimplemented: paths come from
``validate_state.COLLECTIONS`` and parsing from ``validate_state.load_jsonl``.

Usage:
    python3 scripts/gap_scan.py
    python3 scripts/gap_scan.py --json
    python3 scripts/gap_scan.py --state-dir /path/to/state

Standard library only. The report is sorted, so two runs on the same ledgers
produce byte-identical output.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

try:
    import validate_state as vs
except ImportError:  # running as scripts/gap_scan.py
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import validate_state as vs

ROOT = vs.ROOT

VERDICTS = ("support", "refute", "neutral", "unresolved")
REFUTE = "refute"
SUPPORT = "support"
UNRESOLVED = "unresolved"

NO_SOURCE_LABEL = "(no source_id)"


class LedgerError(Exception):
    """A ledger could not be read or parsed (usage / I/O class error)."""


# ---------------------------------------------------------------------------
# Loading (thin wrapper over the validator's reader)
# ---------------------------------------------------------------------------
def ledger_path(name: str, state_dir: Path) -> Path:
    """Resolve a ledger file name from the validator's registry."""
    relative = vs.COLLECTIONS[name][0]
    return state_dir / Path(relative).name


def load_ledger(name: str, state_dir: Path) -> List[Dict[str, Any]]:
    """Read one ledger; raise LedgerError instead of guessing at broken input."""
    path = ledger_path(name, state_dir)
    records, errors = vs.load_jsonl(path)
    if errors:
        raise LedgerError("; ".join(errors))
    return records


# ---------------------------------------------------------------------------
# Identities
# ---------------------------------------------------------------------------
def _text(value: Any) -> str:
    """Return a stripped string, or "" for anything unusable."""
    return value.strip() if isinstance(value, str) else ""


def observation_id(record: Dict[str, Any], index: int) -> str:
    """The ID a REL must use to name this observation."""
    value = _text(record.get("evidence_id"))
    if value:
        return value
    return f"<record {index + 1}:no-evidence_id>"


def observation_key(record: Dict[str, Any], index: int) -> str:
    """SHELDON's grouping key; defaults to the record's own identity."""
    return _text(record.get("observation_key")) or observation_id(record, index)


def derive_provisional(evidences: List[Dict[str, Any]]) -> List[bool]:
    """Per record: True unless another EVD corroborates it from another source.

    ``provisional(o) := |{ o' : o'.observation_key = o.observation_key and
                           o'.source_id != o.source_id }| = 0``

    Fail-closed: a record with no usable ``source_id`` is provisional, and so
    is a record whose only same-key partners have no usable source either.
    """
    provisional = [True] * len(evidences)
    groups: Dict[str, List[int]] = {}
    sources: List[str] = [_text(record.get("source_id")) for record in evidences]
    for index, record in enumerate(evidences):
        groups.setdefault(observation_key(record, index), []).append(index)
    for members in groups.values():
        distinct = {sources[i] for i in members if sources[i]}
        for i in members:
            own = sources[i]
            if own and any(other != own for other in distinct):
                provisional[i] = False
    return provisional


def relation_provisional(
    relation: Dict[str, Any],
    provisional_by_id: Dict[str, bool],
) -> bool:
    """Fail-closed precedence for one REL record.

    1. an unresolvable observation is provisional: there is nothing to
       corroborate, so no explicit flag can make it a confirmed refutation;
    2. an explicit boolean ``provisional`` wins over the derived value;
    3. otherwise use the observation's derived value.
    """
    oid = _text(relation.get("observation_id"))
    if oid not in provisional_by_id:
        return True
    explicit = relation.get("provisional")
    if isinstance(explicit, bool):
        return explicit
    return provisional_by_id[oid]


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------
def _rate(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0.0


def _bucket() -> Dict[str, int]:
    counts = {verdict: 0 for verdict in VERDICTS}
    counts["other"] = 0
    counts["refute_suppressed_provisional"] = 0
    return counts


def analyse(
    evidences: List[Dict[str, Any]],
    relations: List[Dict[str, Any]],
    hypotheses: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute the report for already-parsed ledgers (pure, no I/O)."""
    ids = [observation_id(record, i) for i, record in enumerate(evidences)]
    provisional_flags = derive_provisional(evidences)
    provisional_by_id = dict(zip(ids, provisional_flags))

    hypothesis_ids = [
        _text(record.get("hypothesis_id")) for record in hypotheses
    ]
    per_hypothesis: Dict[str, Dict[str, int]] = {
        hid: _bucket() for hid in hypothesis_ids if hid
    }

    anomalies: Dict[str, List[str]] = {
        "dangling_hypothesis": [],
        "dangling_observation": [],
        "unknown_verdict": [],
        "duplicate_pairs": [],
    }
    seen_pairs: Dict[tuple, int] = {}
    relations_by_observation: Dict[str, List[Dict[str, Any]]] = {}
    support_by_observation: set = set()
    unresolved_only_candidates: set = set(ids)

    for relation in relations:
        rid = _text(relation.get("relation_id")) or "<no relation_id>"
        oid = _text(relation.get("observation_id"))
        hid = _text(relation.get("hypothesis_id"))
        verdict = _text(relation.get("verdict"))

        resolved_observation = oid in provisional_by_id
        if resolved_observation:
            relations_by_observation.setdefault(oid, []).append(relation)
            if verdict in VERDICTS and verdict != UNRESOLVED:
                unresolved_only_candidates.discard(oid)
            if verdict == SUPPORT:
                support_by_observation.add(oid)
        else:
            anomalies["dangling_observation"].append(
                f"{rid}: observation_id={oid or '<missing>'}"
            )

        counts = per_hypothesis.get(hid)
        if counts is None:
            anomalies["dangling_hypothesis"].append(
                f"{rid}: hypothesis_id={hid or '<missing>'}"
            )
        elif verdict == REFUTE:
            # The only gated count: a refutation must survive the provisional
            # rule, otherwise it is reported as suppressed, never as refute.
            if relation_provisional(relation, provisional_by_id):
                counts["refute_suppressed_provisional"] += 1
            else:
                counts["refute"] += 1
        elif verdict in VERDICTS:
            counts[verdict] += 1
        else:
            # Includes an empty verdict and any out-of-enum string, even one
            # that happens to name an internal counter ("other").
            counts["other"] += 1
            anomalies["unknown_verdict"].append(
                f"{rid}: verdict={verdict or '<missing>'}"
            )

        pair = (hid, oid)
        seen_pairs[pair] = seen_pairs.get(pair, 0) + 1

    anomalies["duplicate_pairs"] = [
        f"{hid or '<missing>'} x {oid or '<missing>'} ({n} records)"
        for (hid, oid), n in sorted(seen_pairs.items())
        if n > 1
    ]

    unassessed = [oid for oid in ids if oid not in relations_by_observation]
    unexplained = [oid for oid in ids if oid not in support_by_observation]
    # Narrow reading of "unassessed": a REL exists but every verdict for the
    # observation is "unresolved". Requires at least one REL by construction.
    unresolved_only = sorted(
        oid
        for oid in unresolved_only_candidates
        if oid in relations_by_observation
    )

    # Region = source_id (memo section 5.2 defines observation_region as an
    # override of source_id; no record uses it yet, so group by source_id as
    # the specification says and show the override when one appears).
    regions: Dict[str, Dict[str, int]] = {}
    for index, oid in enumerate(ids):
        source = _text(evidences[index].get("source_id")) or NO_SOURCE_LABEL
        row = regions.setdefault(
            source, {"evidence": 0, "unassessed": 0, "unexplained": 0}
        )
        row["evidence"] += 1
        if oid not in relations_by_observation:
            row["unassessed"] += 1
        if oid not in support_by_observation:
            row["unexplained"] += 1

    per_source = [
        {
            "source_id": source,
            "evidence": row["evidence"],
            "unassessed": row["unassessed"],
            "unexplained": row["unexplained"],
        }
        for source, row in sorted(
            regions.items(),
            key=lambda item: (
                -item[1]["unassessed"],
                -item[1]["unexplained"],
                item[0],
            ),
        )
    ]

    total = len(ids)
    provisional_count = sum(1 for flag in provisional_flags if flag)
    return {
        "generated_from": {
            "evidence": vs.COLLECTIONS["evidence"][0],
            "relations": vs.COLLECTIONS["relations"][0],
            "hypotheses": vs.COLLECTIONS["hypotheses"][0],
        },
        "totals": {
            "evidence": total,
            "relations": len(relations),
            "hypotheses": len(per_hypothesis),
            "provisional": provisional_count,
            "non_provisional": total - provisional_count,
        },
        "unassessed": {
            "count": len(unassessed),
            "total": total,
            "rate": _rate(len(unassessed), total),
            "evidence_ids": unassessed,
        },
        "unexplained": {
            "count": len(unexplained),
            "total": total,
            "rate": _rate(len(unexplained), total),
            "evidence_ids": unexplained,
        },
        "unresolved_only": {
            "count": len(unresolved_only),
            "evidence_ids": unresolved_only,
        },
        "per_hypothesis": [
            {"hypothesis_id": hid, **counts}
            for hid, counts in per_hypothesis.items()
        ],
        "per_source": per_source,
        "anomalies": anomalies,
    }


def measure(state_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Read the ledgers under ``state_dir`` and return the report."""
    state_dir = Path(state_dir) if state_dir is not None else ROOT / "state"
    if not state_dir.is_dir():
        raise LedgerError(f"state directory not found: {state_dir}")
    evidences = load_ledger("evidence", state_dir)
    relations = load_ledger("relations", state_dir)
    hypotheses = load_ledger("hypotheses", state_dir)
    return analyse(evidences, relations, hypotheses)


# ---------------------------------------------------------------------------
# Human-readable rendering
# ---------------------------------------------------------------------------
def _percent(rate: float) -> str:
    return f"{rate * 100:.1f}%"


def _listing(title: str, block: Dict[str, Any], explanation: str) -> List[str]:
    lines = [
        f"{title}: {block['count']} / {block['total']} "
        f"({_percent(block['rate'])})  — {explanation}"
    ]
    if block["evidence_ids"]:
        lines.append("  " + ", ".join(block["evidence_ids"]))
    return lines


def format_human(report: Dict[str, Any]) -> str:
    totals = report["totals"]
    lines = [
        "gap_scan — 仮説カバレッジの穴（計測器。ゲートではない）",
        f"台帳: evidence={totals['evidence']} relations={totals['relations']} "
        f"hypotheses={totals['hypotheses']}  "
        f"(provisional={totals['provisional']} / "
        f"non-provisional={totals['non_provisional']})",
        "",
    ]
    lines.extend(
        _listing(
            "unassessed",
            report["unassessed"],
            "REL が 1 件も無い観測",
        )
    )
    lines.append("")
    lines.extend(
        _listing(
            "unexplained",
            report["unexplained"],
            "support の REL が無い観測",
        )
    )
    lines.append("")
    unresolved_only = report["unresolved_only"]
    lines.append(
        f"unresolved のみ: {unresolved_only['count']} 件 "
        f"（REL はあるが全 verdict が unresolved。狭い読みの unassessed）"
    )
    if unresolved_only["evidence_ids"]:
        lines.append("  " + ", ".join(unresolved_only["evidence_ids"]))
    lines.append("")
    lines.append("仮説ごとの verdict（refute は非 provisional のみを数える）")
    if report["per_hypothesis"]:
        for row in report["per_hypothesis"]:
            suppressed = row["refute_suppressed_provisional"]
            extra = f" / provisional により抑止={suppressed}" if suppressed else ""
            other = f" / other={row['other']}" if row["other"] else ""
            lines.append(
                f"  {row['hypothesis_id']}  support={row['support']} "
                f"refute={row['refute']} neutral={row['neutral']} "
                f"unresolved={row['unresolved']}{extra}{other}"
            )
    else:
        lines.append("  (仮説が 0 件)")
    lines.append("")
    lines.append("観測領域（source_id）別の未評価件数（多い順）")
    for row in report["per_source"]:
        lines.append(
            f"  {row['source_id']:<28} unassessed={row['unassessed']:>3} / "
            f"{row['evidence']:<3} unexplained={row['unexplained']:>3}"
        )
    lines.append("")
    anomalies = report["anomalies"]
    if any(anomalies.values()):
        lines.append("台帳の参照異常（validate_state.py が本来の検査器）")
        for kind in sorted(anomalies):
            for item in anomalies[kind]:
                lines.append(f"  [{kind}] {item}")
        lines.append("")
    lines.append(
        "注記: これは計測器でありゲートではない。穴があっても終了コードは 0。"
        "台帳は読み取りのみで、変更していない。"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report hypothesis-coverage gaps in the relation ledger "
        "(an instrument, never a gate)"
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=None,
        help="directory holding evidence.jsonl / relations.jsonl / "
        "hypotheses.jsonl (default: <repo>/state)",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        report = measure(args.state_dir)
    except LedgerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print(
            "gap_scan: exit 2 (usage / I/O error; coverage gaps alone never "
            "change the exit code)",
            file=sys.stderr,
        )
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_human(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
