#!/usr/bin/env python3
"""Unified read view over the frozen base ledgers and their session shards.

WHY THIS EXISTS (S1 design, method B)
-------------------------------------
`state/*.jsonl` were single files that every session appended to. Two branches
appending at the end of the same file collide as *text*, even when they add
different records with different IDs (measured in
contributions/2026-10-21_ledger_sharding_design.md section 4.1). The adopted
design (method B, adopted by the human on 2026-10-21) keeps those files as a
**frozen base shard** and puts new records in *new* files, one per session or
work batch:

    state/evidence.jsonl                 frozen base (never edited again)
    state/evidence.d/2026-10-21-<12 hex>.jsonl
                                         one session's appended records

The same rule applies to the citation snapshot:

    tests/fixtures/arxiv_metadata_snapshot.json          frozen base
    tests/fixtures/arxiv_metadata_snapshot.d/*.json      added entries

This module is the single place that knows that layout. Readers ask it for
records / snapshot entries and get the **union view**, ordered deterministically
(base first, then shard files in filename order, records in file order). The
union is *not* written back to a tracked file: a committed aggregate would be a
shared append point again, which is the problem being removed.

DELIBERATE PROPERTIES
---------------------
* **Nothing is silently dropped.** A shard whose filename does not match the
  convention is still read; the naming problem is reported as an error so the
  records are never lost sight of.
* **Identical duplicates are errors too.** The same record ID in two places is
  reported with both origins, even when the contents are equal. Choosing one
  silently is exactly the failure mode `merge=union` produced in the S1
  experiment. Snapshot entries are keyed by `arxiv_id` and follow the same
  rule.
* **The base is never rewritten and its header is never overwritten.** For the
  snapshot the view header is the base header verbatim; per-part headers are
  returned separately so provenance is not mixed into the base's
  `captured_at` / `capture_note`.
* **A missing shard directory is normal.** It means "nothing has been appended
  since the base was frozen yet"; it is not an error.
* **Hidden files (leading ".") are ignored** in shard directories, so editor
  scratch files do not become records. Everything else with the right suffix
  is read (see the first bullet).

SHARD FILENAME CONVENTION
-------------------------
`YYYY-MM-DD-<12 lowercase hex>.jsonl` (snapshot parts: `.json`), for example
`2026-10-21-3f9ac21b7d40.jsonl`. The date is the session's start date; the
12 hex characters (48 random bits) are what makes same-day parallel sessions
collide-free. A shard file is written once by one session and is never edited
afterwards: a correction is a new shard plus a recorded decision, because
editing a shard re-creates the shared-text hazard.

Non-goals: writing records, deciding which shard a new record belongs to,
schema validation, ID minting, or a Git merge driver.

Standard library only.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

SHARD_DIR_SUFFIX = ".d"
SHARD_SUFFIX = ".jsonl"
SNAPSHOT_SUFFIX = ".json"

#: `2026-10-21-3f9ac21b7d40.jsonl` / `2026-10-21-3f9ac21b7d40.json`
SHARD_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[0-9a-f]{12}\.jsonl$")
SNAPSHOT_SHARD_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[0-9a-f]{12}\.json$")

#: ``"path:line"`` origin of one record in the union view.
Origin = str

#: A file whose name starts like a shard but is not read (wrong suffix or
#: wrong entropy) must be reported: silently skipping it would drop records.
DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def shard_dir(base: Path) -> Path:
    """Return the shard directory that belongs to a base file.

    ``state/evidence.jsonl`` -> ``state/evidence.d``;
    ``tests/fixtures/arxiv_metadata_snapshot.json`` ->
    ``tests/fixtures/arxiv_metadata_snapshot.d``.
    """
    base = Path(base)
    stem = base.name[: -len(base.suffix)] if base.suffix else base.name
    return base.with_name(stem + SHARD_DIR_SUFFIX)


def shard_files(base: Path, suffix: str) -> List[Path]:
    """Shard files of ``base``, in deterministic (filename) order.

    A missing directory yields an empty list. Hidden files are skipped; the
    caller is expected to check every returned name against the convention.
    """
    directory = shard_dir(base)
    if not directory.is_dir():
        return []
    return sorted(
        path
        for path in directory.glob("*" + suffix)
        if path.is_file() and not path.name.startswith(".")
    )


def unread_shard_like_files(base: Path, suffix: str, pattern: re.Pattern) -> List[Path]:
    """Date-named files in the shard directory that the loader will NOT read.

    They are almost certainly a shard misspelt (``2026-10-21-<hex>`` without
    ``.jsonl``, uppercase hex, too few characters). Reading nothing and saying
    nothing would lose records, so callers report these.
    """
    directory = shard_dir(base)
    if not directory.is_dir():
        return []
    unread: List[Path] = []
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue
        if not DATE_PREFIX_RE.match(path.name):
            continue  # README.md and other notes are not shard attempts
        if path.name.endswith(suffix) and pattern.match(path.name):
            continue  # read normally
        unread.append(path)
    return unread


def read_jsonl_file(path: Path) -> Tuple[List[Dict[str, Any]], List[str], List[Origin]]:
    """Read one JSONL file. Return (records, errors, origins) without overlap.

    ``origins[i]`` is ``"<path>:<line>"`` for ``records[i]``. Error messages
    keep the shape the pre-sharding validator produced, so existing callers
    and their tests see the same text for a broken base file.
    """
    records: List[Dict[str, Any]] = []
    errors: List[str] = []
    origins: List[Origin] = []
    try:
        with path.open(encoding="utf-8") as stream:
            for lineno, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    errors.append(f"{path}:{lineno}: invalid JSON: {exc}")
                    continue
                if not isinstance(record, dict):
                    errors.append(f"{path}:{lineno}: line is not a JSON object")
                    continue
                records.append(record)
                origins.append(f"{path}:{lineno}")
    except FileNotFoundError:
        errors.append(f"{path}: file not found")
    except OSError as exc:  # permission denied and similar
        errors.append(f"{path}: {exc}")
    return records, errors, origins


def load_ledger(
    base: Path,
) -> Tuple[List[Dict[str, Any]], List[str], List[Origin]]:
    """Return the union view (records, errors, origins) for one ledger.

    Base records come first (in file order), then shard records in shard
    filename order. Duplicate IDs are *reported*, not resolved: the caller
    (validate_state.check_uniqueness) compares the origins.
    """
    base = Path(base)
    records, errors, origins = read_jsonl_file(base)
    for path in shard_files(base, SHARD_SUFFIX):
        if not SHARD_NAME_RE.match(path.name):
            errors.append(
                f"{path}: shard filename does not match "
                f"YYYY-MM-DD-<12 hex>.jsonl (records were still read)"
            )
        part_records, part_errors, part_origins = read_jsonl_file(path)
        records.extend(part_records)
        errors.extend(part_errors)
        origins.extend(part_origins)
    for path in unread_shard_like_files(base, SHARD_SUFFIX, SHARD_NAME_RE):
        errors.append(
            f"{path}: ignored: a shard must be named "
            f"YYYY-MM-DD-<12 hex>{SHARD_SUFFIX}; its records are NOT in the view"
        )
    return records, errors, origins


def load_jsonl(base: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Two-tuple form of :func:`load_ledger`, for existing callers."""
    records, errors, _origins = load_ledger(base)
    return records, errors


def duplicate_ids(
    records: List[Dict[str, Any]], origins: List[Origin], id_key: str
) -> List[str]:
    """Report every repeated string ID with the two origins involved."""
    errors: List[str] = []
    first: Dict[str, Origin] = {}
    for record, origin in zip(records, origins):
        identity = record.get(id_key)
        if not isinstance(identity, str):
            continue
        if identity in first:
            errors.append(
                f"duplicate {id_key} {identity!r}: {first[identity]} and {origin}"
            )
        else:
            first[identity] = origin
    return errors


def _read_snapshot_file(
    path: Path, errors: List[str]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Return (entries, header) of one snapshot file; report problems."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{path}: file not found")
        return [], {}
    except OSError as exc:
        errors.append(f"{path}: {exc}")
        return [], {}
    except json.JSONDecodeError as exc:
        errors.append(f"{path}: invalid JSON: {exc}")
        return [], {}
    if not isinstance(document, dict):
        errors.append(f"{path}: snapshot must be a JSON object")
        return [], {}
    entries = document.get("entries", [])
    if not isinstance(entries, list):
        errors.append(f"{path}: 'entries' must be a list")
        return [], {}
    header = {key: value for key, value in document.items() if key != "entries"}
    return entries, header


def load_snapshot(
    base: Path,
) -> Tuple[
    Dict[str, Dict[str, Any]],
    Dict[str, Any],
    Dict[str, str],
    Dict[str, Dict[str, Any]],
]:
    """Return (entries, header, origins, part_headers) for the snapshot view.

    ``entries`` is keyed by ``arxiv_id``; ``header`` is the base header
    unchanged; ``origins`` maps each arXiv ID to its file; ``part_headers``
    keeps each shard's header so provenance is preserved without overwriting
    the base's ``captured_at`` / ``capture_note``.

    Raises ``ValueError`` listing every problem when a shard name, a shard
    document, an entry, or a duplicate arXiv ID is invalid.
    """
    base = Path(base)
    errors: List[str] = []
    base_entries, header = _read_snapshot_file(base, errors)
    documents: List[Tuple[Path, List[Dict[str, Any]]]] = [(base, base_entries)]
    part_headers: Dict[str, Dict[str, Any]] = {}
    for path in shard_files(base, SNAPSHOT_SUFFIX):
        if not SNAPSHOT_SHARD_NAME_RE.match(path.name):
            errors.append(
                f"{path}: shard filename does not match "
                f"YYYY-MM-DD-<12 hex>.json"
            )
        entries, part_header = _read_snapshot_file(path, errors)
        documents.append((path, entries))
        part_headers[str(path)] = part_header
    for path in unread_shard_like_files(base, SNAPSHOT_SUFFIX, SNAPSHOT_SHARD_NAME_RE):
        errors.append(
            f"{path}: ignored: a snapshot part must be named "
            f"YYYY-MM-DD-<12 hex>{SNAPSHOT_SUFFIX}; its entries are NOT in the view"
        )

    entries_by_id: Dict[str, Dict[str, Any]] = {}
    origins: Dict[str, str] = {}
    for path, entries in documents:
        for position, entry in enumerate(entries):
            label = f"{path}:entries[{position}]"
            if not isinstance(entry, dict):
                errors.append(f"{label}: entry is not a JSON object")
                continue
            arxiv_id = entry.get("arxiv_id")
            if not isinstance(arxiv_id, str) or not arxiv_id:
                errors.append(f"{label}: missing or non-string 'arxiv_id'")
                continue
            if arxiv_id in entries_by_id:
                errors.append(
                    f"duplicate arxiv_id {arxiv_id!r}: "
                    f"{origins[arxiv_id]} and {path}"
                )
                continue
            entries_by_id[arxiv_id] = entry
            origins[arxiv_id] = str(path)

    if errors:
        raise ValueError("\n".join(errors))
    return entries_by_id, header, origins, part_headers


def load_fixture(base: Path) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    """Two-tuple form of :func:`load_snapshot` used by the citation checkers."""
    entries, header, _origins, _part_headers = load_snapshot(base)
    return entries, header
