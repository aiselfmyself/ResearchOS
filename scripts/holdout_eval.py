#!/usr/bin/env python3
"""Hold-out / OOD separation for the repository's deterministic checks.

WHY THIS EXISTS
---------------
RRSI (arXiv:2609.24972, triaged in `docs/literature-triage-2026-10-21.md`)
improves a *harness* by evaluating candidate changes against a fixed task set,
and guards against the obvious failure: **the harness overfits to the tasks it
was tuned on.** Its remedy is to separate the indicator tasks used to guide
search from a held-out / OOD evaluation used to decide adoption.

This repository has the same shape, with different nouns:

    RRSI                                this repository
    ---------------------------------   ----------------------------------
    harness (prompts, control flow)     CI + scripts + docs conventions
    fixed task set                      the current corpus (memos, docs)
    candidate edit                      a new check, a skip rule, a threshold
    overfitting                         "tuned until the gate is green"

The last row is not hypothetical. `scripts/check_doc_numbers.py` had to grow
two skip rules (blockquotes, `drift-ok`) and a narrowing of the "N件" pattern
before it stopped reporting false positives. **Every one of those rules was
fitted to the corpus in front of me.** Nothing in the repository checked
whether the rules generalise to files that were not part of that fitting.

This module supplies that missing check.

WHAT IT DOES
------------
1. Splits a corpus into **dev** and **hold-out** partitions deterministically
   (SHA-256 of the path under a recorded seed), so the split is stable across
   runs and machines.
2. Runs a detector over each partition separately.
3. Reports the generalisation gap, and flags the RRSI failure mode:
   **zero findings on dev, findings on hold-out** -- i.e. a detector that
   looks clean only on the partition it was tuned against.
4. Gives an **adoption verdict judged on the hold-out partition**, not on dev.
   This is RRSI's central rule: *adoption is decided out of sample.*

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
* It is **an instrument, not a gate.** Exit code is always 0 (the same rule as
  `measure_agreement.py`, `estimate_rho.py`, `harness_regime.py`). A verdict of
  "reject" means "look at this", not "CI is red" -- a corpus with genuine
  findings on both partitions is a *normal* state for some detectors, and
  flagging normal states is a mistake this repository has already made once
  (recorded as lesson A7).
* It does **not** judge whether a detector is *correct*. Only whether its
  behaviour transfers across a partition it was not tuned on.
* It does **not** limit edits per round (RRSI's other regulariser). In this
  repository that is the PR review process, not a script.

USAGE
-----
    python3 scripts/holdout_eval.py                 # all detectors
    python3 scripts/holdout_eval.py --detector memo_ledger_refs
    python3 scripts/holdout_eval.py --holdout-frac 0.3 --seed 20261021
    python3 scripts/holdout_eval.py --json

Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

DEFAULT_SEED = "researchos-holdout-v1"
DEFAULT_HOLDOUT_FRAC = 0.20
# Below this many items a hold-out partition cannot support any inference.
MIN_HOLDOUT_ITEMS = 3


# --------------------------------------------------------------------------
# corpora
# --------------------------------------------------------------------------
def corpus_memos() -> List[Path]:
    return sorted((ROOT / "contributions").glob("*.md"))


def corpus_docs() -> List[Path]:
    return [ROOT / "README.md", ROOT / "docs" / "minimal-core-and-ci.md"]


CORPORA: Dict[str, Callable[[], List[Path]]] = {
    "memos": corpus_memos,
    "docs": corpus_docs,
}


# --------------------------------------------------------------------------
# partition
# --------------------------------------------------------------------------
def partition_key(path: Path, seed: str) -> int:
    """Stable pseudo-random integer derived from the path and the seed.

    Using the path (not an index) means the split does not move when files are
    added or removed -- a file's assignment is a property of its name.
    """
    rel = str(path.relative_to(ROOT)) if _under_root(path) else str(path)
    digest = hashlib.sha256(f"{seed}\x00{rel}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _under_root(path: Path) -> bool:
    try:
        path.relative_to(ROOT)
        return True
    except ValueError:
        return False


def partition(paths: Sequence[Path], seed: str = DEFAULT_SEED,
              holdout_frac: float = DEFAULT_HOLDOUT_FRAC
              ) -> Tuple[List[Path], List[Path]]:
    """Split into (dev, hold-out). Deterministic for a given seed and corpus."""
    ordered = sorted(paths, key=lambda p: partition_key(p, seed))
    n_holdout = int(round(len(ordered) * holdout_frac))
    n_holdout = max(0, min(n_holdout, len(ordered)))
    if not ordered:
        return [], []
    return ordered[n_holdout:], ordered[:n_holdout]


# --------------------------------------------------------------------------
# "explained away" density -- how much of a partition a detector cannot see
# --------------------------------------------------------------------------
def exclusion_density(paths: Sequence[Path]) -> Dict[str, Any]:
    """Fraction of lines a detector is prevented from judging.

    Skip rules are legitimate, but they are also the easiest way to make a
    detector look clean on the corpus it was tuned against. If dev is far more
    heavily excluded than hold-out, that is a smell.
    """
    total = 0
    excluded = 0
    for p in paths:
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            total += 1
            stripped = line.lstrip()
            if stripped.startswith(">") or "drift-ok" in line:
                excluded += 1
    return {
        "lines": total,
        "excluded": excluded,
        "density": (excluded / total) if total else 0.0,
    }


# --------------------------------------------------------------------------
# detectors -- each returns (items_examined, findings)
# --------------------------------------------------------------------------
def run_memo_citations(paths: Sequence[Path]) -> Tuple[int, int]:
    import check_memo_citations as cmc

    entries = cmc.load_fixture(cmc.DEFAULT_FIXTURE) if hasattr(cmc, "load_fixture") \
        else json.loads(cmc.DEFAULT_FIXTURE.read_text(encoding="utf-8"))
    if isinstance(entries, dict) and "entries" in entries:
        entries = {e["arxiv_id"]: e for e in entries["entries"]}
    checked = 0
    findings = 0
    for p in paths:
        n, _skipped, report = cmc.check_memo(p, entries)
        checked += n
        findings += sum(1 for line in report
                        if line.startswith(("MISMATCH", "MISSING")))
    return checked, findings


def run_memo_ledger_refs(paths: Sequence[Path]) -> Tuple[int, int]:
    import check_memo_ledger_refs as cml
    import validate_state as vs

    ids = cml.load_ledger_ids()
    archived = cml.load_archived_ids(Path(cml.DEFAULT_ARCHIVE_DOC))
    dangling, _archived_hits, _referenced = cml.scan(list(paths), ids, archived)
    # "items" = ledger-ID / path tokens actually considered by the detector
    items = 0
    for p in paths:
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8")
        items += len(vs.ID_TOKEN_RE.findall(text)) + len(vs.PATH_TOKEN_RE.findall(text))
    return items, len(dangling)


def run_doc_numbers(paths: Sequence[Path]) -> Tuple[int, int]:
    import check_doc_numbers as cdn

    report = cdn.scan([str(p.relative_to(ROOT)) if _under_root(p) else str(p)
                       for p in paths])
    lines = sum(len(p.read_text(encoding="utf-8").splitlines()) for p in paths
                if p.is_file())
    return lines, len(report["findings"])


DETECTORS: Dict[str, Dict[str, Any]] = {
    "memo_citations": {"corpus": "memos", "fn": run_memo_citations,
                       "unit": "reference entries checked"},
    "memo_ledger_refs": {"corpus": "memos", "fn": run_memo_ledger_refs,
                         "unit": "ID/path tokens considered"},
    "doc_numbers": {"corpus": "docs", "fn": run_doc_numbers,
                    "unit": "candidate lines scanned"},
}


# --------------------------------------------------------------------------
# line-level partition -- for corpora too small to split by file
# --------------------------------------------------------------------------
def split_lines(paths: Sequence[Path], seed: str, holdout_frac: float,
                tmpdir: Path) -> Tuple[List[Path], List[Path]]:
    """Split the *lines* of a corpus, not the files.

    The detector most at risk of overfitting here -- `check_doc_numbers` --
    works line by line, and its corpus is only two files, so a file-level
    split cannot produce a hold-out at all. Splitting lines gives each
    detector a hold-out of the same granularity at which it actually judges.

    Trade-off: a detector that needs multi-line context would be distorted.
    All three detectors wired in here are line-based, so this is safe for
    them -- but it is a per-detector property, not a universal rule.
    """
    cutoff = int(round(holdout_frac * 100))
    dev_paths: List[Path] = []
    hold_paths: List[Path] = []
    (tmpdir / "dev").mkdir(parents=True, exist_ok=True)
    (tmpdir / "holdout").mkdir(parents=True, exist_ok=True)
    for p in paths:
        if not p.is_file():
            continue
        dev_lines: List[str] = []
        hold_lines: List[str] = []
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
            key = partition_key(Path(f"{p}#{i}"), seed)
            (hold_lines if (key % 100) < cutoff else dev_lines).append(line)
        # Keep each original file separate. Concatenating them would let a
        # line from one file supply context for a line from another, which
        # manufactures findings that exist in neither real document.
        d = tmpdir / "dev" / p.name
        h = tmpdir / "holdout" / p.name
        d.write_text("\n".join(dev_lines), encoding="utf-8")
        h.write_text("\n".join(hold_lines), encoding="utf-8")
        dev_paths.append(d)
        hold_paths.append(h)
    return dev_paths, hold_paths


# --------------------------------------------------------------------------
# evaluation
# --------------------------------------------------------------------------
def _rate(findings: int, items: int) -> Optional[float]:
    return (findings / items) if items else None


def evaluate(name: str, seed: str = DEFAULT_SEED,
             holdout_frac: float = DEFAULT_HOLDOUT_FRAC) -> Dict[str, Any]:
    spec = DETECTORS[name]
    paths = CORPORA[spec["corpus"]]()
    dev, hold = partition(paths, seed=seed, holdout_frac=holdout_frac)

    out: Dict[str, Any] = {
        "detector": name,
        "corpus": spec["corpus"],
        "unit": spec["unit"],
        "seed": seed,
        "holdout_frac": holdout_frac,
        "dev_files": [_rel(p) for p in dev],
        "holdout_files": [_rel(p) for p in hold],
    }

    if len(hold) < MIN_HOLDOUT_ITEMS:
        # File-level split is unusable (the corpus is too small). Fall back to
        # splitting lines, which is the granularity these detectors judge at.
        out["granularity"] = "line"
        out["file_level_note"] = (
            f"file-level split unusable: hold-out would have {len(hold)} of "
            f"{len(paths)} item(s), need >= {MIN_HOLDOUT_ITEMS}. Fell back to "
            f"line-level partition."
        )
        with tempfile.TemporaryDirectory() as td:
            dev, hold = split_lines(paths, seed, holdout_frac, Path(td))
            out["dev_lines"] = sum(
                1 for p in dev for _ in p.read_text(encoding="utf-8").splitlines())
            out["holdout_lines"] = sum(
                1 for p in hold for _ in p.read_text(encoding="utf-8").splitlines())
            if out["holdout_lines"] < MIN_HOLDOUT_ITEMS:
                # Even at line granularity there is not enough to judge.
                # Say so rather than emitting a verdict built on nothing.
                items, findings = spec["fn"](paths)
                out["status"] = "insufficient-holdout"
                out["reason"] = (
                    f"even at line granularity the hold-out has "
                    f"{out['holdout_lines']} line(s); need at least "
                    f"{MIN_HOLDOUT_ITEMS}. The {spec['corpus']!r} corpus is too "
                    f"small to support an out-of-sample judgement."
                )
                out["whole_corpus"] = {"items": items, "findings": findings}
                out["verdict"] = "insufficient"
                return out
            dev_items, dev_find = spec["fn"](dev)
            hold_items, hold_find = spec["fn"](hold)
    else:
        out["granularity"] = "file"
        dev_items, dev_find = spec["fn"](dev)
        hold_items, hold_find = spec["fn"](hold)
    out["dev"] = {"items": dev_items, "findings": dev_find,
                  "rate": _rate(dev_find, dev_items)}
    out["holdout"] = {"items": hold_items, "findings": hold_find,
                      "rate": _rate(hold_find, hold_items)}
    out["dev_exclusion"] = exclusion_density(dev)
    out["holdout_exclusion"] = exclusion_density(hold)

    gap = None
    if out["dev"]["rate"] is not None and out["holdout"]["rate"] is not None:
        gap = out["holdout"]["rate"] - out["dev"]["rate"]
    out["generalisation_gap"] = gap

    # --- RRSI adoption rule: decide out of sample -------------------------
    if dev_find == 0 and hold_find > 0:
        out["status"] = "OVERFIT-SUSPECTED"
        out["verdict"] = "reject"
        out["reason"] = (
            "Zero findings on dev but findings on hold-out: the detector looks "
            "clean only on the partition it was most likely tuned against."
        )
    elif hold_find > 0:
        out["status"] = "findings-on-holdout"
        out["verdict"] = "reject"
        out["reason"] = (
            "Findings on hold-out. Adoption is judged out of sample, so this "
            "detector would not be adopted as-is."
        )
    elif dev_find > 0:
        out["status"] = "dev-only-findings"
        out["verdict"] = "adopt-with-caveat"
        out["reason"] = (
            "Hold-out is clean but dev has findings. Adoption is permitted, but "
            "the dev findings are unexplained -- check whether a skip rule is "
            "hiding them."
        )
    else:
        out["status"] = "clean"
        out["verdict"] = "adopt"
        out["reason"] = "No findings on either partition."

    # --- exclusion asymmetry ----------------------------------------------
    dd = out["dev_exclusion"]["density"]
    hd = out["holdout_exclusion"]["density"]
    out["exclusion_asymmetry"] = dd - hd
    if dd - hd > 0.10:
        out.setdefault("warnings", []).append(
            f"dev excludes {dd:.1%} of lines vs {hd:.1%} on hold-out "
            f"(asymmetry {dd - hd:.1%}): skip rules may have been fitted to dev."
        )
    return out


def _rel(p: Path) -> str:
    return str(p.relative_to(ROOT)) if _under_root(p) else str(p)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--detector", action="append", default=None,
                    help=f"detector to evaluate (default: all of "
                         f"{', '.join(DETECTORS)})")
    ap.add_argument("--seed", default=DEFAULT_SEED)
    ap.add_argument("--holdout-frac", type=float, default=DEFAULT_HOLDOUT_FRAC)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    names = args.detector or list(DETECTORS)
    unknown = [n for n in names if n not in DETECTORS]
    if unknown:
        print(f"error: unknown detector(s): {', '.join(unknown)}", file=sys.stderr)
        return 2

    results = [evaluate(n, seed=args.seed, holdout_frac=args.holdout_frac)
               for n in names]

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0

    for r in results:
        print(f"=== {r['detector']}  (corpus: {r['corpus']}, seed: {r['seed']})")
        if r["status"] == "insufficient-holdout":
            print(f"    {r['reason']}")
            wc = r.get("whole_corpus", {})
            print(f"    whole corpus: {wc.get('findings', 0)} finding(s) / "
                  f"{wc.get('items', 0)} {r['unit']}")
            print(f"    verdict: {r['verdict']}")
            continue
        d, h = r["dev"], r["holdout"]
        print(f"    dev     : {d['findings']:3d} finding(s) / {d['items']:5d} "
              f"{r['unit']}  (rate {d['rate'] or 0:.4f})")
        print(f"    hold-out: {h['findings']:3d} finding(s) / {h['items']:5d} "
              f"{r['unit']}  (rate {h['rate'] or 0:.4f})")
        gap = r["generalisation_gap"]
        print(f"    generalisation gap (holdout - dev): "
              f"{'n/a' if gap is None else f'{gap:+.4f}'}")
        print(f"    exclusion density: dev {r['dev_exclusion']['density']:.1%} "
              f"vs hold-out {r['holdout_exclusion']['density']:.1%}")
        for w in r.get("warnings", []):
            print(f"    WARNING {w}")
        print(f"    verdict : {r['verdict']}  [{r['status']}] -- {r['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
