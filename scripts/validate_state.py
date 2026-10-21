#!/usr/bin/env python3
"""Minimal deterministic validator for ResearchOS research ledgers.

Scope (deliberately small -- see docs/minimal-core-and-ci.md):
  * JSON well-formedness of the five *research* ledgers under state/:
    sources / evidence / claims / verifications / hypotheses.
  * Schema checks driven by schemas/*.json: required fields, types, enums,
    array item types. Extra fields are allowed (as in JSON Schema draft-07
    when additionalProperties is unset).
  * ID uniqueness within each ledger. Since 2026-10-21 a ledger is the union
    of a frozen base file (`state/<name>.jsonl`) and its session shards
    (`state/<name>.d/*.jsonl`, see scripts/ledger_store.py and
    contributions/2026-10-21_ledger_sharding_migration.md). Uniqueness is
    checked across the union, and a duplicate reports both origins. Every
    other check below also runs over the union.
  * Record-ID format: new records use PREFIX-YYYYMMDD-xxxx so that two
    branches cannot mint the same ID; the pre-2026-10-20 sequential IDs are
    grandfathered up to a frozen maximum (docs/record-id-scheme.md).
  * Referential integrity between ledgers:
      evidence.source_id        -> sources
      claim.evidence_ids        -> evidence
      claim.counterclaim_ids    -> claims
      hypothesis.evidence_ids   -> evidence
      verification.target_id    -> sources | evidence | claims | hypotheses
      claim.hypothesis_ids      -> hypotheses            (optional field)
      relation.hypothesis_id    -> hypotheses
      relation.observation_id   -> evidence
      relation.source_id        -> sources               (optional field)

  * The observation_key overlay state/evidence_keys.jsonl (frozen base, empty
    until 2026-10-21) plus its shards state/evidence_keys.d/*.jsonl. It adds
    an optional ``observation_key`` to an existing EVD without rewriting the
    frozen evidence ledger: SHELDON's ``provisional`` rule groups observations
    by that key, and a record cannot be edited in place once written.
    Each overlay record is {evidence_id, observation_key, ...}; the key is
    only ever added, never replaced (the validator refuses a second key for
    the same evidence_id, and never overrides a key the EVD already has).

  * The relation ledger state/relations.jsonl (E_t: hypothesis x observation
    -> support/refute/neutral/unresolved; SHELDON reading section 5.1) is
    schema-checked and reference-checked like the other ledgers. It has no
    legacy sequential IDs: REL-NNN is never accepted.

  * The hypothesis-cycle ledgers (2026-10-21): search_log (QRY), runs (RUN),
    predictions (PRD). They make the loop's inputs auditable -- which searches
    were run, what a round cost, and what was predicted before the observation
    existed. See docs/2026-10-21_hypothesis-cycle-automation.md.

  * The cycle gates (2026-10-21). Records that predate this work are listed by
    *origin file* in state/cycle_exemptions.json and are exempt; every record
    in any other file must carry the cycle fields:

        source.query_id                  -> a QRY record, which must list the
                                            source in included_source_ids
        hypothesis.round                 -> integer >= 1
        hypothesis.derived_from_evidence_ids
                                         -> the observations that GENERATED
                                            the hypothesis (they can never also
                                            be counted as its support)
        hypothesis.refutation_condition  -> observable / would_refute /
                                            expected_if_true, all non-empty;
                                            optional threshold is checked when
                                            present (metric / operator / value)
        hypothesis.next_literature_questions
                                         -> non-empty list of strings; the
                                            questions the search planner turns
                                            into queries (2026-10-21 round 1:
                                            the old single next_observations
                                            list held no searchable question)
        hypothesis.next_internal_measurements
                                         -> a list of strings (may be empty)
        relation.derived_from            -> boolean
        relation.searched_refutation     -> boolean

    Exemption is by file, not by ID, because a shard is immutable and written
    by one session: "not in a known file" is exactly "new record". A relation
    that sets derived_from=true must name an observation listed in its
    hypothesis's derived_from_evidence_ids (only checked when the hypothesis
    itself carries the field, since legacy hypotheses never recorded theirs).

    Two exemption lists exist in state/cycle_exemptions.json:

        legacy_files     -- everything predating the cycle system
        pre_split_files  -- predating the 2026-10-21 round-1 lesson that a
                            single next_observations list is not searchable.
                            These keep every other cycle check; only the
                            next_* split is waived.

    The split was first enforced after round 1, whose own hypothesis shard
    therefore still carries the old single list. Exempting that file from all
    checks would have removed the round / derived_from / refutation gates from
    the one record that demonstrates them, so the narrower list is used.

Non-goals (frozen by design, not missing by accident):
  * No governance ledgers (sessions / proposals / reviews / approvals /
    review_queue), no role checks, no commit-trailer checks, no append-only
    hash chains. Those mechanisms live on the archived arena/* branches and
    are intentionally NOT part of the minimal core because their pursuit of
    formal completeness blocked all progress (see
    docs/stagnation-analysis-2026-10-20.md).
  * No network access. arXiv re-verification of citations is a separate,
    explicitly-run step, not a CI gate.

Usage:
    python3 scripts/validate_state.py [--quiet]

Exit code 0 = all checks pass, 1 = at least one error.
Standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]

try:
    import ledger_store
except ImportError:  # running as scripts/validate_state.py
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import ledger_store

# collection -> (ledger file, schema file, id key)
COLLECTIONS: Dict[str, Tuple[str, str, str]] = {
    "sources": ("state/sources.jsonl", "schemas/source.json", "source_id"),
    "evidence": ("state/evidence.jsonl", "schemas/evidence.json", "evidence_id"),
    "claims": ("state/claims.jsonl", "schemas/claim.json", "claim_id"),
    "verifications": (
        "state/verifications.jsonl",
        "schemas/verification.json",
        "verification_id",
    ),
    "hypotheses": (
        "state/hypotheses.jsonl",
        "schemas/hypothesis.json",
        "hypothesis_id",
    ),
    "relations": (
        "state/relations.jsonl",
        "schemas/relation.json",
        "relation_id",
    ),
    # Hypothesis-cycle ledgers (2026-10-21). Empty until the loop runs; the
    # gates below are prospective, so an empty ledger is the correct initial
    # state and is not treated as a failure.
    "search_log": (
        "state/search_log.jsonl",
        "schemas/search_log.json",
        "query_id",
    ),
    "runs": ("state/runs.jsonl", "schemas/run.json", "run_id"),
    "predictions": (
        "state/predictions.jsonl",
        "schemas/prediction.json",
        "prediction_id",
    ),
}

# ---------------------------------------------------------------------------
# Record-ID scheme (see docs/record-id-scheme.md)
#
# Sequential IDs collide when two branches append to the same ledger: both
# read the same max(ID) and mint the same next number. New records therefore
# use ``PREFIX-YYYYMMDD-xxxx``, where ``xxxx`` is a random 4-hex suffix, so
# two independent sessions cannot mint the same ID. Once minted, an ID is
# never changed (references depend on it).
#
# The 49 records that predate this scheme keep their sequential IDs. They are
# grandfathered by *number*, not by listing them: a legacy ID is accepted only
# if it is at or below the frozen maximum below. Anything beyond that range is
# a new record and must use the new format. The relation ledger (REL) was
# created after the scheme, so it has no legacy range at all: LEGACY_MAX has
# no REL key and REL-NNN is rejected (check_id_format treats a missing key as
# a maximum of 0).
# ---------------------------------------------------------------------------
ID_PREFIXES: Dict[str, str] = {
    "sources": "SRC",
    "evidence": "EVD",
    "claims": "CLM",
    "verifications": "VER",
    "hypotheses": "HYP",
    "relations": "REL",
    "search_log": "QRY",
    "runs": "RUN",
    "predictions": "PRD",
}

# Frozen at 2026-10-20 when the non-sequential scheme was adopted.
# Do not raise these numbers; mint new records with a YYYYMMDD suffix instead.
LEGACY_MAX: Dict[str, int] = {
    "SRC": 4,
    "EVD": 14,
    "CLM": 7,
    "VER": 21,
    "HYP": 3,
}

ID_PATTERN = re.compile(r"^(?P<prefix>[A-Z]{3})-(?P<date>\d{8})-(?P<suffix>[0-9a-f]{4})$")
LEGACY_PATTERN = re.compile(r"^(?P<prefix>[A-Z]{3})-(?P<num>\d{3})$")

#: The observation_key overlay (see the module docstring). It is *not* one of
#: COLLECTIONS: it has no IDs of its own, it only annotates existing EVDs.
EVIDENCE_KEYS_LEDGER = "state/evidence_keys.jsonl"

#: Files whose records predate the 2026-10-21 cycle gates (see the module
#: docstring). Exemption is by *origin file*, so no per-record list is needed.
CYCLE_EXEMPTIONS = "state/cycle_exemptions.json"


def load_ledger_records(
    path: Path,
) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    """Return (records, errors, origins) of one ledger's union view.

    ``origins[i]`` is the ``"<file>:<line>"`` of ``records[i]``: the frozen
    base file first, then each shard file in filename order.
    """
    return ledger_store.load_ledger(path)


def load_jsonl(path: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Return (records, errors) of one ledger: base + shards.

    Kept as the historical two-tuple API; it is shard-aware, so every caller
    that used it before the 2026-10-21 migration reads the union view without
    changing its own code.
    """
    records, errors, _origins = ledger_store.load_ledger(path)
    return records, errors


# ---------------------------------------------------------------------------
# observation_key overlay (2026-10-21)
#
# An EVD record is append-only: once it is in state/evidence.jsonl or a shard
# it is never edited, and writing a second record with the same evidence_id
# would be reported as a duplicate. But SHELDON's ``provisional`` rule needs
# ``observation_key`` on the EVD, so the key has to be added *somewhere else*.
# The overlay is that place: ``state/evidence_keys.jsonl`` (frozen base) plus
# ``state/evidence_keys.d/<YYYY-MM-DD>-<12 hex>.jsonl`` shards, one record per
# annotated EVD. It follows the same base + parts rule as the ledgers
# (scripts/ledger_store.py) without being one of them: it has no ID of its own
# and it cannot change anything except adding a key that is not yet present.
# ---------------------------------------------------------------------------
def load_evidence_keys(
    path: Path,
) -> Tuple[Dict[str, str], List[str]]:
    """Return (evidence_id -> observation_key, errors) of the overlay.

    A missing base file with no shards means "no overlay yet" and is not an
    error. Malformed records, a shard without its base, and two keys for the
    same evidence are errors: silently keeping one of them is exactly the
    failure mode the sharded ledgers are designed to report.
    """
    path = Path(path)
    errors: List[str] = []
    records: List[Dict[str, Any]] = []
    origins: List[str] = []
    if path.exists():
        records, load_errors, origins = ledger_store.load_ledger(path)
        errors.extend(load_errors)
    else:
        shards = ledger_store.shard_files(path, ledger_store.SHARD_SUFFIX)
        if shards:
            errors.append(
                f"{path}: base file not found but {len(shards)} shard(s) "
                f"exist; the overlay shards would be read against nothing"
            )
    mapping: Dict[str, str] = {}
    first_origin: Dict[str, str] = {}
    for index, record in enumerate(records):
        origin = origins[index] if index < len(origins) else str(path)
        evidence_id = record.get("evidence_id")
        key = record.get("observation_key")
        if not isinstance(evidence_id, str) or not evidence_id.strip():
            errors.append(
                f"{origin}: overlay record has no usable evidence_id"
            )
            continue
        if not isinstance(key, str) or not key.strip():
            errors.append(
                f"{origin}: overlay record for {evidence_id} has no usable "
                f"observation_key"
            )
            continue
        if evidence_id in first_origin:
            errors.append(
                f"duplicate overlay key for {evidence_id}: "
                f"{first_origin[evidence_id]} and {origin}"
            )
            continue
        first_origin[evidence_id] = origin
        mapping[evidence_id] = key.strip()
    return mapping, errors


def apply_evidence_keys(
    evidences: List[Dict[str, Any]], mapping: Dict[str, str]
) -> List[Dict[str, Any]]:
    """Return copies of ``evidences`` with the overlay key added where absent.

    An ``observation_key`` already on the EVD is never replaced: the overlay is
    an annotation, not a correction, and silently overriding a recorded value
    would make the ledger disagree with itself.
    """
    result: List[Dict[str, Any]] = []
    for record in evidences:
        evidence_id = record.get("evidence_id")
        key = mapping.get(evidence_id) if isinstance(evidence_id, str) else None
        existing = record.get("observation_key")
        has_key = isinstance(existing, str) and existing.strip()
        if key and not has_key:
            record = dict(record)
            record["observation_key"] = key
        result.append(record)
    return result


def check_evidence_keys(
    evidences: List[Dict[str, Any]], mapping: Dict[str, str]
) -> List[str]:
    """Every overlay key must name an EVD that exists (fail closed)."""
    ids = {
        record.get("evidence_id")
        for record in evidences
        if isinstance(record.get("evidence_id"), str)
    }
    return [
        f"{EVIDENCE_KEYS_LEDGER}: observation_key for unknown evidence_id {eid!r}"
        for eid in sorted(mapping)
        if eid not in ids
    ]


def _check_type(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return True  # unknown type name: do not fail, schema bug is separate


def validate_record(
    record: Dict[str, Any], schema: Dict[str, Any], label: str
) -> List[str]:
    """Validate one record against a JSON-Schema-subset schema."""
    errors: List[str] = []
    properties = schema.get("properties", {})
    for field in schema.get("required", []):
        if field not in record:
            errors.append(f"{label}: missing required field '{field}'")
    for field, subschema in properties.items():
        if field not in record:
            continue
        value = record[field]
        expected = subschema.get("type")
        if expected and not _check_type(value, expected):
            errors.append(
                f"{label}: field '{field}' must be {expected}, "
                f"got {type(value).__name__}"
            )
            continue
        if "enum" in subschema and value not in subschema["enum"]:
            errors.append(
                f"{label}: field '{field}' value {value!r} "
                f"not in {subschema['enum']}"
            )
        items = subschema.get("items")
        if isinstance(items, dict) and isinstance(value, list):
            item_type = items.get("type")
            if item_type:
                for index, item in enumerate(value):
                    if not _check_type(item, item_type):
                        errors.append(
                            f"{label}: field '{field}[{index}]' must be "
                            f"{item_type}, got {type(item).__name__}"
                        )
    return errors


def check_uniqueness(
    records: List[Dict[str, Any]],
    id_key: str,
    ledger: str,
    origins: Optional[List[str]] = None,
) -> List[str]:
    """Report duplicate IDs. With ``origins``, name both files explicitly.

    ``origins`` is the parallel list from :func:`load_ledger_records`; without
    it the historical line-number message is produced (used by tests that
    validate an in-memory list).
    """
    errors: List[str] = []
    seen: Dict[str, str] = {}
    for index, record in enumerate(records):
        origin = (
            origins[index]
            if origins is not None and index < len(origins)
            else f"{ledger}:line {index + 1}"
        )
        rid = record.get(id_key)
        if not isinstance(rid, str):
            errors.append(f"{ledger}:{index + 1}: missing or non-string {id_key!r}")
            continue
        if rid in seen:
            errors.append(
                f"{ledger}:{index + 1}: duplicate {id_key} {rid!r} "
                f"(first seen at {seen[rid]}; also at {origin})"
            )
        else:
            seen[rid] = origin
    return errors


def check_id_format(
    records: List[Dict[str, Any]], id_key: str, ledger: str, prefix: str
) -> List[str]:
    """Enforce the non-sequential ID scheme (docs/record-id-scheme.md).

    Accepted:
      * ``PREFIX-YYYYMMDD-xxxx`` (the current scheme); and
      * ``PREFIX-NNN`` only up to ``LEGACY_MAX[prefix]`` (grandfathered).
    """
    errors: List[str] = []
    legacy_max = LEGACY_MAX.get(prefix, 0)
    for lineno, record in enumerate(records, start=1):
        rid = record.get(id_key)
        if not isinstance(rid, str):
            continue  # reported by check_uniqueness
        match = ID_PATTERN.match(rid)
        if match:
            if match.group("prefix") != prefix:
                errors.append(
                    f"{ledger}:{lineno}: ID {rid!r} must start with {prefix!r}"
                )
            continue
        match = LEGACY_PATTERN.match(rid)
        if match:
            if match.group("prefix") != prefix:
                errors.append(
                    f"{ledger}:{lineno}: ID {rid!r} must start with {prefix!r}"
                )
            elif legacy_max == 0:
                errors.append(
                    f"{ledger}:{lineno}: ID {rid!r} is a sequential ID, but "
                    f"{prefix} has no grandfathered sequential range; mint one "
                    f"with 'python3 scripts/new_id.py {prefix}' instead"
                )
            elif int(match.group("num")) > legacy_max:
                errors.append(
                    f"{ledger}:{lineno}: ID {rid!r} extends the frozen sequential "
                    f"range (max {prefix}-{legacy_max:03d}); mint one with "
                    f"'python3 scripts/new_id.py {prefix}' instead"
                )
            continue
        errors.append(
            f"{ledger}:{lineno}: ID {rid!r} must look like "
            f"{prefix}-YYYYMMDD-xxxx (mint one with scripts/new_id.py)"
        )
    return errors


# ---------------------------------------------------------------------------
# Hypothesis-cycle gates (2026-10-21)
#
# WHY THESE EXIST
# ---------------
# The 2026-10-21 measurement of the ledger found that the four hypotheses added
# on that day were "supported" by the very observations used to generate them
# (94-100% of their support), and that the relation ledger contained zero
# refutations out of 241. That is not a data error -- it is what happens when
# generation and adjudication share a material and nothing records the
# difference. A loop that generates hypotheses automatically would amplify it.
#
# The gates are therefore about *recorded provenance*, not about quality:
#   * which search produced a source;
#   * which observations produced a hypothesis;
#   * what would refute it, written before it is looked for;
#   * what to look for next.
# Whether a hypothesis is good, or whether support is contaminated, is a human
# judgement and stays an instrument's report (scripts/self_support.py is the
# planned Phase 3 instrument), never a gate.
#
# Exemption is by origin file, listed in state/cycle_exemptions.json. Using the
# file rather than the ID needs no maintenance as records accumulate, and a
# shard is immutable, so a new file is exactly the set of new records.
# ---------------------------------------------------------------------------
REFUTATION_FIELDS = ("observable", "would_refute", "expected_if_true")
THRESHOLD_FIELDS = ("metric", "operator", "value")
THRESHOLD_OPERATORS = ("<", "<=", ">", ">=", "==", "!=")


def load_cycle_exemptions(path: Path) -> Tuple[set, set, List[str]]:
    """Return (legacy files, pre-split files, errors) from the exemptions file.

    A missing file is an error rather than "nothing is exempt": without it the
    validator cannot tell a grandfathered record from a new one, and silently
    choosing either interpretation would either redden the whole repository or
    switch the gates off. Both are worse than saying so.
    """
    errors: List[str] = []
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return set(), set(), [
            f"{path}: file not found; the cycle gates cannot distinguish "
            f"legacy records from new ones without it"
        ]
    except (OSError, json.JSONDecodeError) as exc:
        return set(), set(), [f"{path}: {exc}"]

    def files(key: str) -> Optional[set]:
        value = document.get(key)
        if value is None:
            return set()
        if not isinstance(value, list) or not all(isinstance(f, str) for f in value):
            errors.append(f"{path}: '{key}' must be a list of strings")
            return None
        return {f.replace("\\", "/") for f in value}

    legacy = files("legacy_files")
    if legacy is None:
        return set(), set(), errors
    pre_split = files("pre_split_files")
    if pre_split is None:
        return set(), set(), errors
    overlap = legacy & pre_split
    if overlap:
        errors.append(
            f"{path}: {sorted(overlap)} appear in both legacy_files and "
            f"pre_split_files; legacy_files already waives every check"
        )
    return legacy, pre_split, errors


def relative_origin(origin: str, root: Path) -> str:
    """Return ``origin`` relative to ``root`` in POSIX form when possible.

    Origins carry a ``:<line>`` suffix (``".../state/sources.jsonl:12"``), and
    tests build temporary copies of the repository, so the path is absolute
    there. Both are normalised away: an exemption names a *file*.
    """
    raw = origin
    head, _, tail = raw.rpartition(":")
    if head and tail.isdigit():
        raw = head  # drop the ":<line>" suffix, keep the path
    try:
        path = Path(raw)
        if not path.is_absolute():
            return path.as_posix()
        return path.resolve().relative_to(Path(root).resolve()).as_posix()
    except (ValueError, OSError):
        return Path(raw).as_posix()


def _is_exempt(rel_origin: str, exempt_files: set) -> bool:
    return rel_origin in exempt_files


def check_threshold(condition: Any, label: str) -> List[str]:
    """Validate the optional machine-readable half of a refutation condition.

    Absent is fine: a condition that cannot be written with a numeric
    threshold is still a valid refutation condition, just not one a script can
    score. Present-but-malformed is an error, because a threshold that does not
    parse is worse than no threshold -- it looks checkable and is not.
    """
    errors: List[str] = []
    if not isinstance(condition, dict) or "threshold" not in condition:
        return errors
    threshold = condition.get("threshold")
    if not isinstance(threshold, dict):
        return [f"{label}: refutation_condition.threshold must be an object"]
    for field in THRESHOLD_FIELDS:
        if field not in threshold:
            errors.append(f"{label}: refutation_condition.threshold.{field} is missing")
    metric = threshold.get("metric")
    if "metric" in threshold and not _nonempty_string(metric):
        errors.append(f"{label}: refutation_condition.threshold.metric must be a non-empty string")
    operator = threshold.get("operator")
    if "operator" in threshold and operator not in THRESHOLD_OPERATORS:
        errors.append(
            f"{label}: refutation_condition.threshold.operator {operator!r} is not one of "
            f"{list(THRESHOLD_OPERATORS)}"
        )
    value = threshold.get("value")
    if "value" in threshold and (
        not isinstance(value, (int, float)) or isinstance(value, bool)
    ):
        errors.append(f"{label}: refutation_condition.threshold.value must be a number")
    return errors


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def check_cycle_fields(
    data: Dict[str, List[Dict[str, Any]]],
    origins: Dict[str, List[str]],
    exempt_files: set,
    root: Path,
    pre_split_files: Optional[set] = None,
) -> List[str]:
    """Enforce the 2026-10-21 provenance fields on non-exempt records.

    ``pre_split_files`` waives only the next_literature_questions /
    next_internal_measurements split (see the module docstring).
    """
    errors: List[str] = []
    pre_split_files = pre_split_files or set()

    def rel(name: str, index: int) -> str:
        found = origins.get(name, [])
        return relative_origin(found[index], root) if index < len(found) else ""

    evidence_ids = {
        r.get("evidence_id") for r in data.get("evidence", [])
        if isinstance(r.get("evidence_id"), str)
    }
    source_ids = {
        r.get("source_id") for r in data.get("sources", [])
        if isinstance(r.get("source_id"), str)
    }
    query_by_id = {
        r.get("query_id"): r for r in data.get("search_log", [])
        if isinstance(r.get("query_id"), str)
    }
    hypothesis_by_id = {
        r.get("hypothesis_id"): r for r in data.get("hypotheses", [])
        if isinstance(r.get("hypothesis_id"), str)
    }
    known_ids = set(evidence_ids) | source_ids | set(query_by_id)
    known_ids |= set(hypothesis_by_id)
    known_ids |= {
        r.get("relation_id") for r in data.get("relations", [])
        if isinstance(r.get("relation_id"), str)
    }
    known_ids |= {
        r.get("claim_id") for r in data.get("claims", [])
        if isinstance(r.get("claim_id"), str)
    }
    known_ids |= {
        r.get("verification_id") for r in data.get("verifications", [])
        if isinstance(r.get("verification_id"), str)
    }

    # --- sources: every new source names the search that found it ---------
    for index, record in enumerate(data.get("sources", [])):
        if _is_exempt(rel("sources", index), exempt_files):
            continue
        sid = record.get("source_id")
        query_id = record.get("query_id")
        if not _nonempty_string(query_id):
            errors.append(
                f"source {sid}: missing query_id; a source added after "
                f"2026-10-21 must point at the search log entry (QRY) that "
                f"found it (docs/2026-10-21_hypothesis-cycle-automation.md "
                f"section 5)"
            )
            continue
        query = query_by_id.get(query_id)
        if query is None:
            errors.append(f"source {sid}: unknown query_id {query_id!r}")
        else:
            included = query.get("included_source_ids") or []
            if sid not in included:
                errors.append(
                    f"source {sid}: query {query_id} does not list it in "
                    f"included_source_ids"
                )

    # --- hypotheses: generation provenance, refutation, next observations -
    for index, record in enumerate(data.get("hypotheses", [])):
        if _is_exempt(rel("hypotheses", index), exempt_files):
            continue
        hid = record.get("hypothesis_id")
        round_number = record.get("round")
        if not isinstance(round_number, int) or isinstance(round_number, bool) \
                or round_number < 1:
            errors.append(
                f"hypothesis {hid}: missing or invalid 'round' "
                f"(integer >= 1); every hypothesis added after 2026-10-21 "
                f"must say which loop round produced it"
            )
        derived = record.get("derived_from_evidence_ids")
        if not isinstance(derived, list):
            errors.append(
                f"hypothesis {hid}: missing 'derived_from_evidence_ids'; "
                f"record which observations produced the hypothesis so they "
                f"can be excluded from its support"
            )
        else:
            for eid in derived:
                if eid not in evidence_ids:
                    errors.append(
                        f"hypothesis {hid}: unknown derived_from evidence_id "
                        f"{eid!r}"
                    )
        condition = record.get("refutation_condition")
        if not isinstance(condition, dict):
            errors.append(
                f"hypothesis {hid}: missing 'refutation_condition'; a "
                f"hypothesis without a stated refutation is a summary, not a "
                f"hypothesis"
            )
        else:
            for field in REFUTATION_FIELDS:
                if not _nonempty_string(condition.get(field)):
                    errors.append(
                        f"hypothesis {hid}: refutation_condition.{field} must "
                        f"be a non-empty string"
                    )
        errors.extend(check_threshold(condition, f"hypothesis {hid}"))
        # Split on 2026-10-21 (round 1): the single next_observations list held
        # only self-experiments and internal measurements, so the search
        # planner had nothing to search. A literature question and an internal
        # measurement are different jobs and are now recorded separately.
        if _is_exempt(rel("hypotheses", index), pre_split_files):
            # Still check the legacy field it does have: a record that predates
            # the split must not lose its shape either.
            legacy = record.get("next_observations")
            if not isinstance(legacy, list) or not legacy:
                errors.append(
                    f"hypothesis {hid}: pre-split record must keep a non-empty "
                    f"'next_observations' list"
                )
            elif not all(_nonempty_string(item) for item in legacy):
                errors.append(
                    f"hypothesis {hid}: every next_observations item must be a "
                    f"non-empty string"
                )
        else:
            questions = record.get("next_literature_questions")
            if not isinstance(questions, list) or not questions:
                errors.append(
                    f"hypothesis {hid}: 'next_literature_questions' must be a "
                    f"non-empty list of questions a literature search could "
                    f"answer; the search planner turns them into queries"
                )
            elif not all(_nonempty_string(item) for item in questions):
                errors.append(
                    f"hypothesis {hid}: every next_literature_questions item "
                    f"must be a non-empty string"
                )
            measurements = record.get("next_internal_measurements")
            if not isinstance(measurements, list):
                errors.append(
                    f"hypothesis {hid}: 'next_internal_measurements' must be a "
                    f"list (use an empty list when there is nothing to measure "
                    f"internally -- state the decision, do not omit the field)"
                )
            elif not all(_nonempty_string(item) for item in measurements):
                errors.append(
                    f"hypothesis {hid}: every next_internal_measurements item "
                    f"must be a non-empty string"
                )

    # --- relations: derived flag, and the refutation actually searched ----
    for index, record in enumerate(data.get("relations", [])):
        if _is_exempt(rel("relations", index), exempt_files):
            continue
        rid = record.get("relation_id")
        if not isinstance(record.get("derived_from"), bool):
            errors.append(
                f"relation {rid}: missing boolean 'derived_from' "
                f"(was this observation used to generate the hypothesis?)"
            )
        if not isinstance(record.get("searched_refutation"), bool):
            errors.append(
                f"relation {rid}: missing boolean 'searched_refutation' "
                f"('no refutation found' and 'no refutation searched for' are "
                f"different states)"
            )
        if record.get("derived_from") is True:
            hypothesis = hypothesis_by_id.get(record.get("hypothesis_id"))
            declared = (
                hypothesis.get("derived_from_evidence_ids")
                if isinstance(hypothesis, dict) else None
            )
            # Only checkable when the hypothesis recorded its own inputs;
            # legacy hypotheses never did, so the flag is left as declared.
            if isinstance(declared, list) \
                    and record.get("observation_id") not in declared:
                errors.append(
                    f"relation {rid}: derived_from=true but observation "
                    f"{record.get('observation_id')!r} is not in hypothesis "
                    f"{record.get('hypothesis_id')}.derived_from_evidence_ids"
                )

    # --- search log: what the query claims to have found ------------------
    for record in data.get("search_log", []):
        qid = record.get("query_id")
        included = record.get("included_source_ids") or []
        if not isinstance(included, list):
            errors.append(f"search_log {qid}: included_source_ids must be a list")
            continue
        for sid in included:
            if sid not in source_ids:
                errors.append(
                    f"search_log {qid}: unknown included source_id {sid!r}"
                )
        derived = record.get("derived_from") or []
        if not isinstance(derived, list):
            errors.append(f"search_log {qid}: derived_from must be a list")
            continue
        for token in derived:
            if token not in known_ids:
                errors.append(f"search_log {qid}: unknown derived_from {token!r}")

    # --- runs: a round number, a non-negative intervention count ----------
    for record in data.get("runs", []):
        rid = record.get("run_id")
        round_number = record.get("round")
        if not isinstance(round_number, int) or isinstance(round_number, bool) \
                or round_number < 1:
            errors.append(f"run {rid}: 'round' must be an integer >= 1")
        interventions = record.get("human_interventions")
        if not isinstance(interventions, int) \
                or isinstance(interventions, bool) or interventions < 0:
            errors.append(
                f"run {rid}: 'human_interventions' must be an integer >= 0"
            )

    # --- predictions: a probability in [0, 1] -----------------------------
    for record in data.get("predictions", []):
        pid = record.get("prediction_id")
        errors.extend(
            check_threshold(record.get("refutation_condition"), f"prediction {pid}")
        )
        probability = record.get("probability")
        if not isinstance(probability, (int, float)) \
                or isinstance(probability, bool) or not 0.0 <= probability <= 1.0:
            errors.append(
                f"prediction {pid}: 'probability' must be a number in [0, 1]"
            )

    return errors


def check_references(data: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    errors: List[str] = []
    ids = {
        name: {
            r.get(COLLECTIONS[name][2])
            for r in records
            if isinstance(r.get(COLLECTIONS[name][2]), str)
        }
        for name, records in data.items()
    }

    def _exists(target: str) -> bool:
        return any(target in known for known in ids.values())

    for record in data["evidence"]:
        src = record.get("source_id")
        if isinstance(src, str) and src not in ids["sources"]:
            errors.append(
                f"evidence {record.get('evidence_id')}: unknown source_id {src!r}"
            )
    for record in data["claims"]:
        cid = record.get("claim_id")
        for eid in record.get("evidence_ids", []) or []:
            if eid not in ids["evidence"]:
                errors.append(f"claim {cid}: unknown evidence_id {eid!r}")
        for cc in record.get("counterclaim_ids", []) or []:
            if cc not in ids["claims"]:
                errors.append(f"claim {cid}: unknown counterclaim_id {cc!r}")
    for record in data["hypotheses"]:
        hid = record.get("hypothesis_id")
        for eid in record.get("evidence_ids", []) or []:
            if eid not in ids["evidence"]:
                errors.append(f"hypothesis {hid}: unknown evidence_id {eid!r}")
    for record in data["claims"]:
        # Optional field (added with the relation ledger): absent is fine,
        # present must resolve to hypotheses.
        cid = record.get("claim_id")
        for hid in record.get("hypothesis_ids", []) or []:
            if hid not in ids.get("hypotheses", set()):
                errors.append(f"claim {cid}: unknown hypothesis_id {hid!r}")
    for record in data.get("relations", []):
        rid = record.get("relation_id")
        hid = record.get("hypothesis_id")
        if isinstance(hid, str) and hid not in ids.get("hypotheses", set()):
            errors.append(f"relation {rid}: unknown hypothesis_id {hid!r}")
        oid = record.get("observation_id")
        if isinstance(oid, str) and oid not in ids.get("evidence", set()):
            errors.append(f"relation {rid}: unknown observation_id {oid!r}")
        src = record.get("source_id")
        if isinstance(src, str) and src not in ids.get("sources", set()):
            errors.append(f"relation {rid}: unknown source_id {src!r}")
    for record in data["verifications"]:
        vid = record.get("verification_id")
        target = record.get("target_id")
        if isinstance(target, str) and not _exists(target):
            errors.append(f"verification {vid}: unknown target_id {target!r}")
    for record in data.get("predictions", []):
        pid = record.get("prediction_id")
        hid = record.get("hypothesis_id")
        if isinstance(hid, str) and hid not in ids.get("hypotheses", set()):
            errors.append(f"prediction {pid}: unknown hypothesis_id {hid!r}")
    return errors


# ---------------------------------------------------------------------------
# Cross-reference check inside prose fields (added 2026-10-20)
#
# check_references() only walks the structured *id fields*, so it cannot see
# an ID or a file path that a record merely *mentions* in prose. That blind
# spot is exactly what the 2026-10-20 audit found: CLM-004/005/007 and
# EVD-012/013/014 described artefacts that the minimal-core extraction had
# deleted, and nothing in CI noticed. See
# docs/incomplete-work-audit-2026-10-20.md §3.2 and §3.3, and
# docs/archived-ledger-records-2026-10-20.md for the records removed.
#
# The patterns are deliberately conservative: only ID-shaped tokens and
# repo-relative paths under a known top-level directory are checked, so bare
# filenames ("run_simulation.py") and ordinary prose stay untouched.
# ---------------------------------------------------------------------------
ID_TOKEN_RE = re.compile(
    r"(?<![-\w])(?P<prefix>SRC|EVD|CLM|VER|HYP|REL|QRY|RUN|PRD)"
    r"-(?:\d{3}|\d{8}-[0-9a-f]{4})(?![-\w])"
)
PATH_TOKEN_RE = re.compile(
    r"(?<![-\w])(?P<path>(?:gitswarm|scripts|tests|state|contributions|docs)"
    r"/[\w][\w./-]*\.(?:py|md|json|jsonl|yml|txt))(?![-\w])"
)


def _collect_strings(node: Any, out: List[str]) -> None:
    """Collect every string reachable from a decoded JSON record."""
    if isinstance(node, str):
        out.append(node)
    elif isinstance(node, list):
        for item in node:
            _collect_strings(item, out)
    elif isinstance(node, dict):
        for item in node.values():
            _collect_strings(item, out)


def check_cross_references(
    data: Dict[str, List[Dict[str, Any]]], root: Path
) -> List[str]:
    """Flag ledger IDs and repo paths mentioned in prose that do not exist."""
    errors: List[str] = []
    ids = {
        ID_PREFIXES[name]: {
            record.get(COLLECTIONS[name][2])
            for record in records
            if isinstance(record.get(COLLECTIONS[name][2]), str)
        }
        for name, records in data.items()
    }

    for name, records in data.items():
        id_key = COLLECTIONS[name][2]
        for record in records:
            label = f"{name} {record.get(id_key)}"
            strings: List[str] = []
            _collect_strings(record, strings)
            seen: set = set()
            for text in strings:
                for match in ID_TOKEN_RE.finditer(text):
                    token = match.group(0)
                    if token in ids.get(match.group("prefix"), set()):
                        continue
                    if token in seen:
                        continue
                    seen.add(token)
                    errors.append(
                        f"{label}: mentions {token}, which is not in any "
                        f"ledger (records archived on 2026-10-20 are "
                        f"listed in "
                        f"docs/archived-ledger-records-2026-10-20.md)"
                    )
                for match in PATH_TOKEN_RE.finditer(text):
                    path = match.group("path")
                    if (root / path).exists() or path in seen:
                        continue
                    seen.add(path)
                    errors.append(
                        f"{label}: mentions {path}, which does not exist"
                    )
    return errors


def run_all_checks(root: Path = ROOT) -> Dict[str, List[str]]:
    errors: List[str] = []
    data: Dict[str, List[Dict[str, Any]]] = {}
    origins_by_name: Dict[str, List[str]] = {}
    key_mapping, key_errors = load_evidence_keys(root / EVIDENCE_KEYS_LEDGER)
    errors.extend(key_errors)
    for name, (ledger_rel, schema_rel, id_key) in COLLECTIONS.items():
        records, load_errors, origins = load_ledger_records(root / ledger_rel)
        origins_by_name[name] = origins
        if name == "evidence":
            # The overlay adds observation_key to existing records; every other
            # check (schema, IDs, references, prose) then sees the same view
            # that scripts/gap_scan.py measures.
            records = apply_evidence_keys(records, key_mapping)
        errors.extend(load_errors)
        try:
            schema = json.loads((root / schema_rel).read_text(encoding="utf-8"))
        except FileNotFoundError:
            errors.append(f"{schema_rel}: schema file not found")
            data[name] = records
            continue
        label = schema.get("title", name)
        for record in records:
            errors.extend(validate_record(record, schema, label))
        errors.extend(check_uniqueness(records, id_key, ledger_rel, origins))
        errors.extend(
            check_id_format(records, id_key, ledger_rel, ID_PREFIXES[name])
        )
        data[name] = records
    errors.extend(check_evidence_keys(data.get("evidence", []), key_mapping))
    errors.extend(check_references(data))
    exempt_files, pre_split, exempt_errors = load_cycle_exemptions(
        root / CYCLE_EXEMPTIONS
    )
    errors.extend(exempt_errors)
    errors.extend(
        check_cycle_fields(data, origins_by_name, exempt_files, root, pre_split)
    )
    errors.extend(check_cross_references(data, root))
    return {"errors": errors}


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate research ledgers")
    parser.add_argument("--quiet", action="store_true", help="only print errors")
    args = parser.parse_args(argv)
    report = run_all_checks(ROOT)
    if report["errors"]:
        print("FAIL: research ledger validation errors:")
        for err in report["errors"]:
            print(f"  - {err}")
        return 1
    if not args.quiet:
        counts = ", ".join(
            f"{name}={len(load_jsonl(ROOT / rel)[0])}"
            for name, (rel, _, _) in COLLECTIONS.items()
        )
        print(f"PASS: research ledgers valid ({counts})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
