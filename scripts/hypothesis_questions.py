#!/usr/bin/env python3
"""Load the next_literature_questions overlay for legacy hypotheses.

WHY THIS EXISTS
---------------
The 2026-10-21 round-1 lesson split a single ``next_observations`` list into
``next_literature_questions`` (what a search can answer) and
``next_internal_measurements`` (what this repository measures itself). New
hypothesis records must carry both.

But a ledger record is append-only: six of the seven hypotheses in
``state/hypotheses.jsonl`` predate the split and are exempt from it, and
writing a second record with the same ``hypothesis_id`` would be a duplicate
ID. Their questions therefore cannot be added to the record. Without a place to
put them, ``scripts/next_queries.py`` would plan zero queries forever -- which
is the failure mode round 1 was meant to catch.

The overlay is that place, and it follows the rule already used for
``observation_key`` (``state/evidence_keys.jsonl``):

    state/hypothesis_questions.jsonl            frozen base (empty at first)
    state/hypothesis_questions.d/<date>-<hex>.jsonl   one record per hypothesis

    {"hypothesis_id": "HYP-001",
     "questions": ["...", "..."],
     "recorded_at": "2026-10-21",
     "basis": "statement + refutation_condition",
     "note": "..."}

WHAT IT MAY AND MAY NOT DO
--------------------------
* It may supply questions for a hypothesis whose record has none.
* It may NOT shadow one that has some: two sources of truth for the same
  field is exactly the drift this repository keeps auditing. That case is an
  error (see ``check``), not a preference order.
* It carries no IDs of its own and changes no record.

Entry points:
    load(path)                        -> ({hypothesis_id: [question]}, errors)
    check(overlay, hypotheses)        -> errors (unknown ID, shadowing)
    questions_for(hypothesis, overlay)-> ([question] | None, source)

Standard library only.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]

try:
    import ledger_store
except ImportError:  # running as scripts/hypothesis_questions.py
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import ledger_store

#: Frozen base of the overlay. The name follows ``state/evidence_keys.jsonl``.
LEDGER = "state/hypothesis_questions.jsonl"


def load(path: Path) -> Tuple[Dict[str, List[str]], List[str]]:
    """Return ({hypothesis_id: questions}, errors) for the overlay.

    A missing base with no shards means "no overlay yet" and is not an error.
    A base that is missing while shards exist is an error: the shards would be
    read against nothing. Malformed records and two records for the same
    hypothesis are errors too -- silently keeping one of them loses a decision.
    """
    path = Path(path)
    errors: List[str] = []
    if not path.exists():
        shards = ledger_store.shard_files(path, ledger_store.SHARD_SUFFIX)
        if shards:
            return {}, [
                f"{path}: base file not found but {len(shards)} shard(s) exist; "
                f"the overlay shards would be read against nothing"
            ]
        return {}, []

    records, load_errors, origins = ledger_store.load_ledger(path)
    errors.extend(load_errors)

    overlay: Dict[str, List[str]] = {}
    first_origin: Dict[str, str] = {}
    for index, record in enumerate(records):
        origin = origins[index] if index < len(origins) else str(path)
        hypothesis_id = record.get("hypothesis_id")
        if not isinstance(hypothesis_id, str) or not hypothesis_id.strip():
            errors.append(f"{origin}: overlay record has no usable hypothesis_id")
            continue
        hypothesis_id = hypothesis_id.strip()
        questions = record.get("questions")
        if not isinstance(questions, list) or not questions:
            errors.append(
                f"{origin}: overlay record for {hypothesis_id} has no "
                f"non-empty 'questions' list"
            )
            continue
        if not all(isinstance(item, str) and item.strip() for item in questions):
            errors.append(
                f"{origin}: every question for {hypothesis_id} must be a "
                f"non-empty string"
            )
            continue
        if hypothesis_id in overlay:
            errors.append(
                f"{origin}: duplicate overlay record for {hypothesis_id} "
                f"(first seen at {first_origin[hypothesis_id]}); refusing to "
                f"choose between them"
            )
            continue
        overlay[hypothesis_id] = [item.strip() for item in questions]
        first_origin[hypothesis_id] = origin
    return overlay, errors


def check(
    overlay: Dict[str, List[str]], hypotheses: List[Dict[str, Any]]
) -> List[str]:
    """Validate the overlay against the hypotheses it annotates."""
    errors: List[str] = []
    by_id = {
        record.get("hypothesis_id"): record
        for record in hypotheses
        if isinstance(record.get("hypothesis_id"), str)
    }
    for hypothesis_id in sorted(overlay):
        record = by_id.get(hypothesis_id)
        if record is None:
            errors.append(
                f"{LEDGER}: questions for unknown hypothesis_id "
                f"{hypothesis_id!r}"
            )
            continue
        if isinstance(record.get("next_literature_questions"), list) and record[
            "next_literature_questions"
        ]:
            errors.append(
                f"{LEDGER}: {hypothesis_id} already carries "
                f"next_literature_questions in its own record; the overlay "
                f"must not shadow it (two sources of truth drift apart)"
            )
    return errors


def questions_for(
    hypothesis: Dict[str, Any], overlay: Dict[str, List[str]]
) -> Tuple[Optional[List[str]], str]:
    """Return (questions, source) for one hypothesis.

    ``source`` is ``"record"`` (the hypothesis carries its own list),
    ``"overlay"`` (a pre-split record annotated in the overlay) or ``"none"``
    (nothing to plan from -- the caller must report it, not skip silently).
    """
    own = hypothesis.get("next_literature_questions")
    if isinstance(own, list) and own:
        return [item.strip() for item in own if isinstance(item, str)], "record"
    hypothesis_id = hypothesis.get("hypothesis_id")
    if isinstance(hypothesis_id, str) and hypothesis_id in overlay:
        return list(overlay[hypothesis_id]), "overlay"
    return None, "none"
