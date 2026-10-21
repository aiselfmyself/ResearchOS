#!/usr/bin/env python3
"""Plan the next literature searches (S0/S7). An instrument.

WHAT THIS IS (AND IS NOT)
-------------------------
``docs/2026-10-21_hypothesis-cycle-automation.md`` section 3 (S7) says the
queries of a round are generated *mechanically* from the hypothesis's next
observations and its refutation condition, because a human writing them puts a
human back in the bottleneck. This script is that generator.

  * It never calls a model and never touches the network: the rule is
    deterministic, so two runs on the same ledgers agree byte for byte.
  * It never writes to the ledger. A planned query becomes a ``QRY`` record
    only when the search step (S1) actually runs it; the plan is a proposal.
  * It is an instrument, not a gate: planning zero queries (every hypothesis
    pre-split, or every question unsearchable) exits 0 and is reported.

Exit codes: 0 = plan completed (whatever it contains); 2 = usage or I/O error
(a broken ledger, a broken overlay, an unknown ``--hypothesis``, bad
arguments). 1 is never returned by design.

INPUTS
------
1. ``next_literature_questions`` on the hypothesis record (new records), or
   from the overlay ``state/hypothesis_questions.jsonl`` (records written
   before the 2026-10-21 split; see ``scripts/hypothesis_questions.py``).
   A hypothesis with neither is **reported and skipped** -- never silently
   treated as having no questions, and never planned from its legacy
   ``next_observations`` (that field mixed literature questions with self
   experiments, which is why the split exists).

2. Weights from ``scripts/gap_scan.py`` (the same measurement, not a second
   definition of it):
     * ``unresolved`` relations per hypothesis -> priority of that
       hypothesis's queries (a hypothesis with many open verdicts is where
       another search is most likely to settle something);
     * ``unexplained`` observations -> coverage queries, built from an
       explicit ``observation_key`` when one exists. An unexplained
       observation with no key has no query seed; the count is reported
       (annotating keys is an S3 job, not something this script invents).

3. ``state/search_log.jsonl``: a planned query that has already been run is
   moved to ``already_searched`` instead of being proposed again. A query
   whose terms are a *subset* of an executed query counts as covered
   (``match: "subset"``); this is reported, never silent.

QUERY GENERATION RULE (deterministic)
-------------------------------------
    lower-case the question -> split on anything but letters/digits/hyphen
    -> drop stopwords and duplicates, keep order -> keep the first
    --max-terms tokens (default 10) -> join with spaces

Hyphenated compounds (``self-preference``, ``long-horizon``) stay one token
because arXiv treats them as meaningful. A question with no surviving token
(e.g. written only in Japanese) is reported as ``no_terms`` instead of
producing an empty query.

``--with-review`` adds one ``review``-channel variant per hypothesis (first
question, four terms + ``survey``): section 3 (S7) lists the paper type as one
of the factors, but a review query is only useful once per hypothesis, not
once per question.

Standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import gap_scan as gs  # noqa: E402
import hypothesis_questions as hq  # noqa: E402

DEFAULT_MAX_TERMS = 10

#: Dropped before a question becomes a query. Kept deliberately small: a word
#: that changes what a paper is about ("effect", "model", "test") never goes
#: in, and neither does a negated form that arXiv cannot use anyway.
STOPWORDS = frozenset(
    """
    a an the and or but if then than that this these those of in on at to for
    from by with without within into over under between across per as is are
    was were be been being am do does did done can could should would may
    might must will shall not no nor so such it its their there here we our
    you your they them he she his her how what which who whom whose when where
    why whether about more most less least very much many few both each other
    same own also just only compared among such
    """.split()
)

#: Letters/digits, with an internal hyphen kept (see the module docstring).
TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")

KIND_HYPOTHESIS = "hypothesis"
KIND_COVERAGE = "coverage"


class PlanError(Exception):
    """The plan could not be produced (usage / I/O class error)."""


# ---------------------------------------------------------------------------
# Text -> query
# ---------------------------------------------------------------------------
def tokenize(text: str) -> List[str]:
    """Lower-case and split ``text`` into query tokens (hyphens preserved)."""
    if not isinstance(text, str):
        return []
    return TOKEN_RE.findall(text.lower())


def query_terms(
    question: str, max_terms: int = DEFAULT_MAX_TERMS, stopwords: Iterable[str] = STOPWORDS
) -> List[str]:
    """Content terms of a question, in order, deduplicated, capped."""
    drop = set(stopwords)
    seen: set = set()
    terms: List[str] = []
    for token in tokenize(question):
        if token in drop or token in seen:
            continue
        seen.add(token)
        terms.append(token)
        if len(terms) >= max_terms:
            break
    return terms


def build_query(question: str, max_terms: int = DEFAULT_MAX_TERMS) -> Optional[str]:
    """Return the keyword string for a question, or None if nothing survives."""
    terms = query_terms(question, max_terms)
    return " ".join(terms) if terms else None


def normalise_query(text: str) -> List[str]:
    """Tokens of an executed query, for de-duplication against the log."""
    return tokenize(text)


# ---------------------------------------------------------------------------
# Planning (pure: records in, report out)
# ---------------------------------------------------------------------------
def _unresolved_by_hypothesis(
    relations: List[Dict[str, Any]]
) -> Dict[str, List[str]]:
    """REL ids whose verdict is ``unresolved``, per hypothesis (sorted)."""
    found: Dict[str, List[str]] = {}
    for relation in relations:
        if relation.get("verdict") != "unresolved":
            continue
        hypothesis_id = relation.get("hypothesis_id")
        relation_id = relation.get("relation_id")
        if not isinstance(hypothesis_id, str) or not isinstance(relation_id, str):
            continue
        found.setdefault(hypothesis_id, []).append(relation_id)
    return {key: sorted(value) for key, value in found.items()}


def _searched_index(
    search_log: List[Dict[str, Any]]
) -> List[Tuple[set, str]]:
    """(terms, query_id) for every executed keyword query, in log order."""
    index: List[Tuple[set, str]] = []
    for record in search_log:
        text = record.get("query")
        query_id = record.get("query_id")
        if not isinstance(text, str) or not isinstance(query_id, str):
            continue
        terms = normalise_query(text)
        if terms:
            index.append((set(terms), query_id))
    return index


def _match_searched(
    terms: List[str], index: List[Tuple[set, str]]
) -> Tuple[List[str], Optional[str]]:
    """Return (matching query ids, "exact" | "subset" | None)."""
    wanted = set(terms)
    exact = [query_id for known, query_id in index if known == wanted]
    if exact:
        return exact, "exact"
    if len(wanted) < 2:
        # A one-word query is too generic to call "covered": "question" is a
        # subset of any executed query containing the word.
        return [], None
    subsets = [query_id for known, query_id in index if wanted <= known]
    if subsets:
        return subsets, "subset"
    return [], None


def _overlay_questions(
    hypotheses: List[Dict[str, Any]], overlay: Dict[str, List[str]]
) -> Tuple[Dict[str, List[str]], Dict[str, str], List[Dict[str, Any]]]:
    """Resolve questions per hypothesis; return (questions, source, skipped)."""
    resolved: Dict[str, List[str]] = {}
    sources: Dict[str, str] = {}
    skipped: List[Dict[str, Any]] = []
    for hypothesis in hypotheses:
        hypothesis_id = hypothesis.get("hypothesis_id")
        if not isinstance(hypothesis_id, str):
            continue
        questions, source = hq.questions_for(hypothesis, overlay)
        if questions:
            resolved[hypothesis_id] = questions
            sources[hypothesis_id] = source
        else:
            skipped.append(
                {
                    "hypothesis_id": hypothesis_id,
                    "reason": "no_questions",
                    "detail": (
                        "record にも overlay にも next_literature_questions が"
                        "無い（分割前の記録）。問いを足すまで検索計画を作れない"
                    ),
                }
            )
    return resolved, sources, skipped


def _coverage_queries(
    evidences: List[Dict[str, Any]],
    unexplained_ids: List[str],
    max_terms: int,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Coverage queries from explicit observation keys; (queries, no-seed ids)."""
    by_id = {
        record.get("evidence_id"): (index, record)
        for index, record in enumerate(evidences)
        if isinstance(record.get("evidence_id"), str)
    }
    keys: Dict[str, List[str]] = {}
    without_seed: List[str] = []
    for evidence_id in unexplained_ids:
        found = by_id.get(evidence_id)
        if found is None:
            without_seed.append(evidence_id)
            continue
        index, record = found
        key = gs.observation_key(record, index)
        if key == evidence_id:
            # The default key IS the evidence id: nothing to search for.
            without_seed.append(evidence_id)
            continue
        keys.setdefault(key, []).append(evidence_id)

    queries: List[Dict[str, Any]] = []
    for key in sorted(keys):
        query = build_query(key.replace("_", " "), max_terms)
        if query is None:  # pragma: no cover - a key with no usable token
            without_seed.extend(sorted(keys[key]))
            continue
        evidence_ids = sorted(keys[key])
        queries.append(
            {
                "query": query,
                "channel": "keyword",
                "kind": KIND_COVERAGE,
                "priority": len(evidence_ids),
                "weight_reasons": {"unexplained_observations": len(evidence_ids)},
                "hypothesis_ids": [],
                "source_questions": [],
                "derived_from": evidence_ids,
                "variant_of": None,
                "observation_key": key,
            }
        )
    return queries, sorted(without_seed)


def _merge_entries(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collapse identical query strings, keeping every provenance link."""
    merged: Dict[str, Dict[str, Any]] = {}
    for entry in entries:
        key = entry["query"]
        if key not in merged:
            merged[key] = {
                **entry,
                "hypothesis_ids": list(entry["hypothesis_ids"]),
                "source_questions": list(entry["source_questions"]),
                "derived_from": list(entry["derived_from"]),
                "weight_reasons": dict(entry["weight_reasons"]),
            }
            continue
        target = merged[key]
        for name, value in entry["weight_reasons"].items():
            target["weight_reasons"][name] = (
                target["weight_reasons"].get(name, 0) + value
            )
        for hypothesis_id in entry["hypothesis_ids"]:
            if hypothesis_id not in target["hypothesis_ids"]:
                target["hypothesis_ids"].append(hypothesis_id)
        for question in entry["source_questions"]:
            if question not in target["source_questions"]:
                target["source_questions"].append(question)
        target["derived_from"] = sorted(
            set(target["derived_from"]) | set(entry["derived_from"])
        )
        if entry["kind"] == KIND_HYPOTHESIS:
            target["kind"] = KIND_HYPOTHESIS
    for target in merged.values():
        # 1 + the number of open gaps the query answers, after merging. Kept in
        # one place so a duplicate question cannot inflate its own priority.
        target["priority"] = 1 + sum(target["weight_reasons"].values())
    return list(merged.values())


def _sort_key(entry: Dict[str, Any]) -> Tuple:
    # Higher priority first; hypothesis queries before coverage at equal
    # priority; query text as the deterministic tie-break.
    return (
        -entry["priority"],
        0 if entry["kind"] == KIND_HYPOTHESIS else 1,
        0 if entry["channel"] == "keyword" else 1,
        entry["query"],
    )


def plan(
    hypotheses: List[Dict[str, Any]],
    evidences: List[Dict[str, Any]],
    relations: List[Dict[str, Any]],
    search_log: List[Dict[str, Any]],
    overlay: Dict[str, List[str]],
    *,
    max_terms: int = DEFAULT_MAX_TERMS,
    include_coverage: bool = True,
    limit: Optional[int] = None,
    with_review: bool = False,
) -> Dict[str, Any]:
    """Compute the plan for already-parsed ledgers (pure, no I/O)."""
    gaps = gs.analyse(evidences, relations, hypotheses)
    unresolved = _unresolved_by_hypothesis(relations)
    questions_by_hypothesis, sources, skipped = _overlay_questions(
        hypotheses, overlay
    )

    entries: List[Dict[str, Any]] = []
    question_count = 0
    for hypothesis_id in sorted(questions_by_hypothesis):
        questions = questions_by_hypothesis[hypothesis_id]
        open_relations = unresolved.get(hypothesis_id, [])
        weight = 1 + len(open_relations)
        for position, question in enumerate(questions):
            question_count += 1
            query = build_query(question, max_terms)
            if query is None:
                skipped.append(
                    {
                        "hypothesis_id": hypothesis_id,
                        "reason": "no_terms",
                        "question": question,
                        "detail": (
                            "英数字の内容語が残らない（日本語のみ等）。"
                            "検索可能な英語の問いとして書き直す必要がある"
                        ),
                    }
                )
                continue
            entries.append(
                {
                    "query": query,
                    "channel": "keyword",
                    "kind": KIND_HYPOTHESIS,
                    "priority": weight,
                    "weight_reasons": {"unresolved_relations": len(open_relations)},
                    "hypothesis_ids": [hypothesis_id],
                    "source_questions": [question],
                    "derived_from": [hypothesis_id] + open_relations,
                    "variant_of": None,
                    "observation_key": None,
                }
            )
            if with_review and position == 0:
                review = " ".join(query_terms(question, max_terms)[:4] + ["survey"])
                entries.append(
                    {
                        "query": review,
                        "channel": "review",
                        "kind": KIND_HYPOTHESIS,
                        "priority": weight,
                        "weight_reasons": {
                            "unresolved_relations": len(open_relations)
                        },
                        "hypothesis_ids": [hypothesis_id],
                        "source_questions": [question],
                        "derived_from": [hypothesis_id] + open_relations,
                        "variant_of": query,
                        "observation_key": None,
                    }
                )

    unexplained_ids = list(gaps["unexplained"]["evidence_ids"])
    coverage_queries: List[Dict[str, Any]] = []
    without_seed: List[str] = []
    if include_coverage:
        coverage_queries, without_seed = _coverage_queries(
            evidences, unexplained_ids, max_terms
        )
        entries.extend(coverage_queries)

    search_index = _searched_index(search_log)
    planned: List[Dict[str, Any]] = []
    already: List[Dict[str, Any]] = []
    for entry in sorted(_merge_entries(entries), key=_sort_key):
        query_ids, match = _match_searched(tokenize(entry["query"]), search_index)
        if query_ids:
            already.append({**entry, "query_ids": query_ids, "match": match})
        else:
            planned.append(entry)

    truncated = 0
    if limit is not None and len(planned) > limit:
        truncated = len(planned) - limit
        planned = planned[:limit]

    return {
        "totals": {
            "hypotheses": len(hypotheses),
            "hypotheses_with_questions": len(questions_by_hypothesis),
            "hypotheses_without_questions": len(
                [h for h in hypotheses if isinstance(h.get("hypothesis_id"), str)]
            )
            - len(questions_by_hypothesis),
            "question_sources": {
                source: list(sources.values()).count(source)
                for source in ("record", "overlay")
            },
            "questions": question_count,
            "planned": len(planned),
            "planned_keyword": len(
                [entry for entry in planned if entry["channel"] == "keyword"]
            ),
            "planned_review": len(
                [entry for entry in planned if entry["channel"] == "review"]
            ),
            "already_searched": len(already),
            "skipped_no_terms": len(
                [item for item in skipped if item["reason"] == "no_terms"]
            ),
            "truncated": truncated,
            "unexplained": len(unexplained_ids),
            "unexplained_with_seed": len(unexplained_ids) - len(without_seed),
            "unresolved_relations": sum(len(value) for value in unresolved.values()),
        },
        "queries": planned,
        "already_searched": already,
        "skipped": skipped,
        "coverage": {
            "enabled": include_coverage,
            "unexplained": len(unexplained_ids),
            "with_seed": len(unexplained_ids) - len(without_seed),
            "without_seed": without_seed,
            "queries": len(coverage_queries),
        },
    }


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def _state_path(state_dir: Path, relative: str) -> Path:
    return state_dir / Path(relative).name


def measure(
    state_dir: Optional[Path] = None,
    *,
    max_terms: int = DEFAULT_MAX_TERMS,
    include_coverage: bool = True,
    limit: Optional[int] = None,
    hypothesis_ids: Optional[Sequence[str]] = None,
    with_review: bool = False,
) -> Dict[str, Any]:
    """Read the ledgers under ``state_dir`` and return the plan."""
    state_dir = Path(state_dir) if state_dir is not None else ROOT / "state"
    if not state_dir.is_dir():
        raise PlanError(f"state directory not found: {state_dir}")

    hypotheses = gs.load_ledger("hypotheses", state_dir)
    evidences = gs.load_ledger("evidence", state_dir)
    relations = gs.load_ledger("relations", state_dir)
    search_log = gs.load_ledger("search_log", state_dir)

    overlay, overlay_errors = hq.load(_state_path(state_dir, hq.LEDGER))
    errors = overlay_errors + hq.check(overlay, hypotheses)
    if errors:
        raise PlanError("; ".join(errors))

    if hypothesis_ids:
        known = {
            record.get("hypothesis_id")
            for record in hypotheses
            if isinstance(record.get("hypothesis_id"), str)
        }
        unknown = sorted(set(hypothesis_ids) - known)
        if unknown:
            raise PlanError(
                f"--hypothesis names unknown hypothesis_id(s): {unknown}"
            )
        wanted = set(hypothesis_ids)
        hypotheses = [
            record
            for record in hypotheses
            if record.get("hypothesis_id") in wanted
        ]

    return plan(
        hypotheses,
        evidences,
        relations,
        search_log,
        overlay,
        max_terms=max_terms,
        include_coverage=include_coverage,
        limit=limit,
        with_review=with_review,
    )


# ---------------------------------------------------------------------------
# Human-readable rendering
# ---------------------------------------------------------------------------
def _label(entry: Dict[str, Any]) -> str:
    channel = entry["channel"]
    return "keyword" if channel == "keyword" else channel


def format_human(report: Dict[str, Any]) -> str:
    totals = report["totals"]
    sources = totals["question_sources"]
    lines = [
        "next_queries — 次の検索計画（S0/S7。計測器でありゲートではない）",
        f"仮説 {totals['hypotheses']} 件 / 問いあり {totals['hypotheses_with_questions']} 件"
        f"（record {sources['record']} / overlay {sources['overlay']}）"
        f" / 計画 {totals['planned']} 件"
        f"（keyword {totals['planned_keyword']}・review {totals['planned_review']}）",
        f"既出 {totals['already_searched']} 件 / 語なし {totals['skipped_no_terms']} 件"
        f" / 上限で除外 {totals['truncated']} 件",
        "",
    ]

    if report["queries"]:
        lines.append("計画（優先度の高い順）")
        for entry in report["queries"]:
            hypothesis_ids = ", ".join(entry["hypothesis_ids"]) or "-"
            reasons = ", ".join(
                f"{name}={value}" for name, value in sorted(entry["weight_reasons"].items())
            )
            lines.append(
                f"  [{entry['priority']}] ({_label(entry)}) {entry['query']}"
            )
            lines.append(f"      由来: {hypothesis_ids}（{reasons}）")
            for question in entry["source_questions"]:
                lines.append(f"      問い: {question}")
            if entry["kind"] == KIND_COVERAGE:
                lines.append(
                    f"      未説明観測: {', '.join(entry['derived_from'])}"
                )
            if entry["variant_of"]:
                lines.append(f"      派生: {entry['variant_of']} の review 版")
        lines.append("")
    else:
        lines.append("計画: 0 件（検索可能な問いが無い。下のスキップを参照）")
        lines.append("")

    if report["already_searched"]:
        lines.append("既に検索済み（提案しない）")
        for entry in report["already_searched"]:
            lines.append(
                f"  [{'/'.join(entry['query_ids'])}] ({entry['match']}) "
                f"{entry['query']}"
            )
        lines.append("")

    skipped = report["skipped"]
    if skipped:
        lines.append("スキップ（問いが無い・検索語が残らない）")
        for item in skipped:
            hypothesis_id = item.get("hypothesis_id", "-")
            reason = item["reason"]
            question = item.get("question")
            suffix = f" / 問い: {question}" if question else ""
            lines.append(f"  {hypothesis_id} [{reason}] {item['detail']}{suffix}")
        lines.append("")

    coverage = report["coverage"]
    if coverage["enabled"]:
        lines.append(
            f"coverage（未説明観測からのクエリ）: 未説明 {coverage['unexplained']} 件"
            f" / 種あり {coverage['with_seed']} 件 / 種なし"
            f" {len(coverage['without_seed'])} 件"
        )
        if coverage["without_seed"]:
            lines.append(
                "  種なし = observation_key の注釈が無い観測。"
                "クエリを作れないので、注釈（S3）まで待つ（--json で全件）"
            )
    else:
        lines.append("coverage: 無効（--no-coverage）")

    lines.append("")
    lines.append(
        "注記: これは計測器でありゲートではない。台帳は読み取りのみで、変更していない。"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Plan the next literature searches from next_literature_questions, "
            "weighted by the gap_scan measurement. Instrument, not a gate."
        )
    )
    parser.add_argument(
        "--state-dir",
        default=None,
        help="directory holding hypotheses.jsonl / evidence.jsonl / "
        "relations.jsonl / search_log.jsonl (default: <repo>/state)",
    )
    parser.add_argument(
        "--json", action="store_true", help="machine-readable output"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="propose at most N queries (the rest is counted as truncated)",
    )
    parser.add_argument(
        "--max-terms",
        type=int,
        default=DEFAULT_MAX_TERMS,
        help=f"content terms per query (default {DEFAULT_MAX_TERMS})",
    )
    parser.add_argument(
        "--no-coverage",
        action="store_true",
        help="do not derive queries from unexplained observations",
    )
    parser.add_argument(
        "--with-review",
        action="store_true",
        help="add one review-channel variant per hypothesis (S7 paper type)",
    )
    parser.add_argument(
        "--hypothesis",
        action="append",
        default=None,
        metavar="HYP_ID",
        help="plan for this hypothesis only (repeatable)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.limit is not None and args.limit < 0:
        parser.error("--limit must be >= 0")
    if args.max_terms < 1:
        parser.error("--max-terms must be >= 1")

    try:
        report = measure(
            args.state_dir,
            max_terms=args.max_terms,
            include_coverage=not args.no_coverage,
            limit=args.limit,
            hypothesis_ids=args.hypothesis,
            with_review=args.with_review,
        )
    except (gs.LedgerError, PlanError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        print(
            "next_queries は台帳を読めないときだけ失敗する（終了コード 2）。"
            "計画が 0 件でも 0。",
            file=sys.stderr,
        )
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(format_human(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
