#!/usr/bin/env python3
"""Shared helpers for the ResearchOS governance harness.

Design notes
------------
* **Append-only state.**  A correction is a *new line* with the same id,
  a higher ``revision`` and a ``supersedes`` field holding the canonical hash
  of the previous line.  Existing lines are never edited or deleted.
* **Legacy grandfathering.**  Records that existed at the governance baseline
  (`policy/state_baseline.json`) are identified by their line hash and are
  exempt from the new requirements.  Everything appended after the baseline
  must comply.
* **No external dependencies.**  The harness must run on a bare runner.
* **COLLECTION_ID_KEYS:** Every call to ``resolve_effective`` for a state
  collection MUST pass the collection-specific id_key (e.g. ``review_id`` for
  reviews, ``queue_id`` for review_queue).  Using the default ``ID_KEYS``
  order silently groups reviews by ``session_id`` and breaks
  ``researchos_queue.py complete`` for verifiers with multiple REV-*.
  Use ``load_effective(name)`` which does this automatically.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "state"
POLICY_DIR = ROOT / "policy"
SCHEMA_DIR = ROOT / "schemas"

ROLES_POLICY = POLICY_DIR / "roles.json"
STATE_BASELINE = POLICY_DIR / "state_baseline.json"

STATE_FILES: Dict[str, str] = {
    "sources": "state/sources.jsonl",
    "evidence": "state/evidence.jsonl",
    "claims": "state/claims.jsonl",
    "verifications": "state/verifications.jsonl",
    "hypotheses": "state/hypotheses.jsonl",
    "sessions": "state/sessions.jsonl",
    "proposals": "state/proposals.jsonl",
    "reviews": "state/reviews.jsonl",
    "approvals": "state/approvals.jsonl",
    "review_queue": "state/review_queue.jsonl",
    "anchors": "state/anchors.jsonl",
}

# PRP-002 rev3 (C2/A1): the whole-file append-only anchor ledger.  Every other
# ``state/*.jsonl`` is pinned by an entry in this file; the anchor ledger pins
# itself through ``prev_anchor_head_sha256`` on each entry.
ANCHORS_RELATIVE_PATH = "state/anchors.jsonl"

#: Collections whose lines are content-addressed and therefore idempotent:
#: appending the *identical* line twice (what a union merge of two parallel
#: tracks does) is a no-op, not a "duplicate revision" conflict.
IDEMPOTENT_COLLECTIONS = frozenset({"anchors"})

LEGACY_STATE_FILES: List[str] = [
    "state/sources.jsonl",
    "state/evidence.jsonl",
    "state/claims.jsonl",
    "state/verifications.jsonl",
    "state/hypotheses.jsonl",
]

ID_KEYS = (
    "source_id",
    "evidence_id",
    "claim_id",
    "verification_id",
    "hypothesis_id",
    "session_id",
    "proposal_id",
    "review_id",
    "approval_id",
    "queue_id",
)

COLLECTION_ID_KEYS: Dict[str, str] = {
    "sources": "source_id",
    "evidence": "evidence_id",
    "claims": "claim_id",
    "verifications": "verification_id",
    "hypotheses": "hypothesis_id",
    "sessions": "session_id",
    "proposals": "proposal_id",
    "reviews": "review_id",
    "approvals": "approval_id",
    "review_queue": "queue_id",
    "anchors": "anchor_id",
}

# ---------------------------------------------------------------------------
# JSON / hashing
# ---------------------------------------------------------------------------


def canonical_json(record: Dict[str, Any]) -> str:
    return json.dumps(
        record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def line_hash(record: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(record).encode("utf-8")).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Whole-file rolling head (PRP-002 rev3, C2/A1)
# ---------------------------------------------------------------------------
#
# ``resolve_effective`` only chains *revisions of the same id*: the newest line
# of a ledger is pinned by nothing, so rewriting it in place went undetected
# (REV-003 §3.3).  The rolling head below commits to the content **and order**
# of every line of a file, so a single hash pins the whole ledger including its
# tip.  Anchors (``state/anchors.jsonl``) store those heads; ``check-append-only``
# re-derives them from the working tree and compares.

GENESIS_HASH = "0" * 64


def ledger_lines(text: str) -> List[str]:
    """Non-empty lines of a JSONL document, verbatim (no re-serialisation)."""
    return [line for line in text.splitlines() if line.strip()]


def line_digest(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def rolling_head(lines: Iterable[str]) -> str:
    """Order-committing hash chain over raw lines. Empty input -> GENESIS_HASH."""
    head = GENESIS_HASH
    for line in lines:
        head = hashlib.sha256(f"{head}{line_digest(line)}".encode("utf-8")).hexdigest()
    return head


def prefix_heads(lines: Sequence[str]) -> List[str]:
    """``prefix_heads[i]`` is the rolling head of ``lines[: i + 1]``."""
    heads: List[str] = []
    head = GENESIS_HASH
    for line in lines:
        head = hashlib.sha256(f"{head}{line_digest(line)}".encode("utf-8")).hexdigest()
        heads.append(head)
    return heads


def head_at(heads: Sequence[str], count: int) -> str:
    """Rolling head of the first ``count`` lines given ``prefix_heads`` output."""
    if count <= 0:
        return GENESIS_HASH
    if count > len(heads):
        raise IndexError(f"file has {len(heads)} lines, cannot pin {count}")
    return heads[count - 1]


def file_head(path: Path) -> str:
    if not path.exists():
        return GENESIS_HASH
    return rolling_head(ledger_lines(path.read_text(encoding="utf-8")))


def anchor_id_for(
    relative_path: str,
    head_sha256: str,
    session_id: Optional[str] = None,
    created_at: Optional[str] = None,
) -> str:
    """Deterministic anchor id derived from the pin and its authorship.

    Two parallel tracks that pin the same tip in different sessions get
    different ids, so a union merge does not produce a spurious
    "duplicate revision" conflict (A5).  Re-running the same update in the same
    second yields the same id, which keeps the operation idempotent.
    """
    material = "\n".join(
        [relative_path, head_sha256, str(session_id or ""), str(created_at or "")]
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"ANC-{digest[:16]}"


# ---------------------------------------------------------------------------
# JSONL I/O
# ---------------------------------------------------------------------------


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{index}: {exc}") from exc
    return records


def read_jsonl_text(text: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


RECORD_SESSION_FIELDS = ("session_id", "created_by_session", "claimed_by_session")


def record_session_hint(record: Dict[str, Any]) -> Optional[str]:
    """The session a record attributes itself to, across the ledger variants.

    ``state/review_queue.jsonl`` rows carry ``created_by_session`` /
    ``claimed_by_session`` and no ``session_id``, so an auto-pin that only looked
    at ``session_id`` wrote ``"unknown"`` -- and ``check-authorship`` then
    rejected the anchor line, because its introducing commit names a real
    session (PRP-002 rev3).
    """
    for field in RECORD_SESSION_FIELDS:
        value = record.get(field)
        if isinstance(value, str) and value:
            return value
    return None


def append_jsonl(
    path: Path, record: Dict[str, Any], anchor: bool = True
) -> str:
    """Append one record. Returns the canonical line hash.

    PRP-002 rev3 (C2/A1): when the target is one of the anchored
    ``state/*.jsonl`` ledgers inside this repository, the append also pins the
    new file tip in ``state/anchors.jsonl`` so the line just written cannot be
    rewritten later without breaking an anchor.  Pass ``anchor=False`` for
    scratch/temporary files outside the repository ledgers.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json(record)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(payload + "\n")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    if anchor and is_anchored_ledger(path):
        try:
            record_anchor(path, session_id=record_session_hint(record))
        except Exception:  # never let pinning break the append itself
            pass
    return digest


def record_id(record: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    for key in ID_KEYS:
        if key in record:
            return key, str(record[key])
    return None, None


# ---------------------------------------------------------------------------
# Revisions
# ---------------------------------------------------------------------------


def resolve_effective(
    records: List[Dict[str, Any]],
    id_key: Optional[str] = None,
    allow_identical_duplicates: bool = False,
) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    """Collapse revisions.

    ``id_key`` must be supplied for collections whose records also carry other
    id-like fields (for example an evidence record carries both ``evidence_id``
    and ``source_id``).  Without it the first matching key in ``ID_KEYS`` wins,
    which silently groups evidence by source.

    Returns ``(effective_records, errors, warnings)``.  ``effective_records``
    keeps the latest revision of every id in first-seen order.
    """
    errors: List[str] = []
    warnings: List[str] = []
    order: List[str] = []
    versions: Dict[str, List[Dict[str, Any]]] = {}

    for record in records:
        if id_key is not None:
            key = id_key
            value = record.get(id_key)
        else:
            key, value = record_id(record)
        if key is None or value is None:
            errors.append(f"record has no known id field: {record}")
            continue
        if value not in versions:
            versions[value] = []
            order.append(value)
        versions[value].append(record)

    effective: List[Dict[str, Any]] = []
    for value in order:
        chain = versions[value]
        annotated: List[Tuple[int, int, Dict[str, Any]]] = []
        for position, record in enumerate(chain):
            revision = record.get("revision", 1)
            if not isinstance(revision, int) or isinstance(revision, bool):
                errors.append(f"{value}: revision must be an integer")
                revision = 1
            annotated.append((revision, position, record))

        annotated.sort(key=lambda item: (item[0], item[1]))
        previous_hash: Optional[str] = None
        seen_revisions: set = set()
        seen_line_hashes: set = set()
        for index, (revision, _position, record) in enumerate(annotated):
            record_hash = line_hash(record)
            if revision in seen_revisions:
                if allow_identical_duplicates and record_hash in seen_line_hashes:
                    # Content-addressed ledger (anchors): the identical line was
                    # appended twice, e.g. by a union merge of parallel tracks.
                    warnings.append(
                        f"{value}: identical duplicate line for revision {revision} "
                        "(idempotent, ignored)"
                    )
                else:
                    errors.append(f"{value}: duplicate revision {revision}")
            seen_revisions.add(revision)
            seen_line_hashes.add(record_hash)

            if index == 0:
                if revision != 1:
                    errors.append(
                        f"{value}: first stored revision is {revision}, expected 1"
                    )
            else:
                expected = record.get("supersedes")
                if not expected:
                    errors.append(
                        f"{value}: revision {revision} is missing 'supersedes'"
                    )
                elif previous_hash and expected != previous_hash:
                    errors.append(
                        f"{value}: revision {revision} 'supersedes' does not match "
                        f"the previous line hash"
                    )
            previous_hash = line_hash(record)

        latest = annotated[-1][2]
        if latest.get("deleted") is True:
            warnings.append(f"{value}: latest revision is marked deleted")
            continue
        effective.append(latest)

    return effective, errors, warnings


# ---------------------------------------------------------------------------
# Whole-file append-only anchors (PRP-002 rev3, C2/A1)
# ---------------------------------------------------------------------------


def anchored_ledgers() -> List[str]:
    """``state/*.jsonl`` ledgers whose tip must be pinned by an anchor entry."""
    return [
        relative_path
        for name, relative_path in STATE_FILES.items()
        if relative_path != ANCHORS_RELATIVE_PATH
    ]


def is_anchored_ledger(path: Path) -> bool:
    """True when ``path`` is one of this repository's anchored ledgers."""
    try:
        resolved = Path(path).resolve()
        resolved.relative_to(ROOT)
    except (OSError, ValueError):
        return False
    return relative(resolved) in set(anchored_ledgers())


def load_anchor_entries(root: Path = ROOT) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Raw lines and parsed entries of the anchor ledger, in file order."""
    path = Path(root) / ANCHORS_RELATIVE_PATH
    if not path.exists():
        return [], []
    raw = ledger_lines(path.read_text(encoding="utf-8"))
    entries: List[Dict[str, Any]] = []
    for line in raw:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            entries.append({})
    return raw, entries


def build_anchor_updates(
    root: Path = ROOT, session_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Anchor entries needed to pin every ledger at its current tip.

    Each entry commits to (a) the rolling head of the first ``lines`` lines of
    its ledger, (b) the previous anchor for the same ledger, and (c) the whole
    anchor ledger as it was before this entry (``prev_anchor_head_sha256``).
    Returns ``[]`` when everything is already pinned.
    """
    root = Path(root)
    raw_anchors, entries = load_anchor_entries(root)
    latest: Dict[str, Dict[str, Any]] = {}
    for entry in entries:
        target = entry.get("file")
        if isinstance(target, str):
            latest[target] = entry

    updates: List[Dict[str, Any]] = []
    # PRP-002 rev3: resolve the author once, so an auto-pin from a ledger whose
    # records have no `session_id` (e.g. review_queue) is still attributed.
    resolved_session = session_id or session_from_branch(root=root)
    simulated = list(raw_anchors)
    for relative_path in anchored_ledgers():
        path = root / relative_path
        lines = (
            ledger_lines(path.read_text(encoding="utf-8")) if path.exists() else []
        )
        head = rolling_head(lines)
        previous = latest.get(relative_path)
        if (
            previous
            and previous.get("head_sha256") == head
            and previous.get("lines") == len(lines)
        ):
            continue  # already pinned at this tip
        created_at = now_utc()
        updates.append(
            {
                "anchor_id": anchor_id_for(
                    relative_path,
                    head,
                    session_id=resolved_session,
                    created_at=created_at,
                ),
                "file": relative_path,
                "lines": len(lines),
                "head_sha256": head,
                "prev_head_sha256": (previous or {}).get("head_sha256", GENESIS_HASH),
                "prev_lines": (previous or {}).get("lines", 0),
                "prev_anchor_head_sha256": rolling_head(simulated),
                "prev_anchor_lines": len(simulated),
                "session_id": resolved_session or "unknown",
                "created_at": created_at,
            }
        )
        simulated.append(canonical_json(updates[-1]))
    return updates


def record_anchor(
    path: Path, root: Path = ROOT, session_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Append the anchor entry that pins ``path``'s current tip. Idempotent."""
    root = Path(root)
    relative_path = relative(Path(path))
    updates = [
        entry
        for entry in build_anchor_updates(root, session_id=session_id)
        if entry.get("file") == relative_path
    ]
    anchor_path = root / ANCHORS_RELATIVE_PATH
    anchor_path.parent.mkdir(parents=True, exist_ok=True)
    for entry in updates:
        append_jsonl(anchor_path, entry, anchor=False)
    return updates


def anchor_errors(root: Path = ROOT) -> List[str]:
    """Verify every anchor against the working tree.

    Three properties are checked, in increasing strength:

    1. **self-chain** — entry *i* pins the anchor ledger as of entry *i-1*, so
       rewriting an earlier anchor line breaks a later one;
    2. **prefix pin** — for every entry, the first ``lines`` lines of its ledger
       must still roll up to ``head_sha256``; rewriting or deleting *any*
       anchored line (including the newest one) breaks this;
    3. **tip pin** — the newest entry per ledger must match the ledger's current
       length and head, so a fresh append is unprotected only until the next
       anchor refresh (``researchos_anchor.py update``).
    """
    root = Path(root)
    errors: List[str] = []
    anchors_rel = ANCHORS_RELATIVE_PATH
    raw_anchors, entries = load_anchor_entries(root)

    for index, entry in enumerate(entries, 1):
        if not entry:
            errors.append(f"{anchors_rel}: line {index} is not valid JSON")

    # 1. self-chain of the anchor ledger
    anchor_heads = prefix_heads(raw_anchors)
    for index, entry in enumerate(entries):
        expected = GENESIS_HASH if index == 0 else anchor_heads[index - 1]
        recorded = entry.get("prev_anchor_head_sha256")
        if recorded is None:
            errors.append(
                f"{anchors_rel}: line {index + 1} has no prev_anchor_head_sha256"
            )
        elif recorded != expected:
            errors.append(
                f"{anchors_rel}: line {index + 1} prev_anchor_head_sha256 does not "
                "match the anchor ledger before it — an earlier anchor line was "
                "modified or removed"
            )
        expected_lines = index
        if entry.get("prev_anchor_lines") not in (None, expected_lines):
            errors.append(
                f"{anchors_rel}: line {index + 1} prev_anchor_lines is "
                f"{entry.get('prev_anchor_lines')}, expected {expected_lines}"
            )

    # 2. prefix pin of every entry against the current ledger content
    line_cache: Dict[str, Optional[List[str]]] = {}
    head_cache: Dict[str, List[str]] = {}

    def _lines_for(relative_path: str) -> Optional[List[str]]:
        if relative_path not in line_cache:
            candidate = root / relative_path
            line_cache[relative_path] = (
                ledger_lines(candidate.read_text(encoding="utf-8"))
                if candidate.exists()
                else None
            )
            line_cache_head = line_cache[relative_path]
            head_cache[relative_path] = (
                prefix_heads(line_cache_head) if line_cache_head is not None else []
            )
        return line_cache[relative_path]

    latest: Dict[str, Dict[str, Any]] = {}
    for entry in entries:
        relative_path = entry.get("file")
        if not isinstance(relative_path, str) or not relative_path:
            errors.append(f"{anchors_rel}: entry {entry.get('anchor_id')} has no file")
            continue
        current = _lines_for(relative_path)
        if current is None:
            errors.append(
                f"{relative_path}: anchored by {entry.get('anchor_id')} but the file "
                "is missing"
            )
            continue
        count = entry.get("lines")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            errors.append(
                f"{relative_path}: anchor {entry.get('anchor_id')} has a non-integer "
                "line count"
            )
            continue
        if count > len(current):
            errors.append(
                f"{relative_path}: anchor {entry.get('anchor_id')} pins {count} lines "
                f"but only {len(current)} remain (append-only violation: lines were "
                "deleted)"
            )
            continue
        expected_head = head_at(head_cache[relative_path], count)
        if entry.get("head_sha256") != expected_head:
            errors.append(
                f"{relative_path}: anchor {entry.get('anchor_id')} pins the first "
                f"{count} lines to {str(entry.get('head_sha256'))[:12]}... but they now "
                f"roll up to {expected_head[:12]}... (an anchored line was modified)"
            )
        previous = latest.get(relative_path)
        if previous is None:
            if entry.get("prev_lines") not in (None, 0):
                errors.append(
                    f"{relative_path}: first anchor {entry.get('anchor_id')} must start "
                    "from prev_lines 0"
                )
            if entry.get("prev_head_sha256") not in (None, GENESIS_HASH):
                errors.append(
                    f"{relative_path}: first anchor {entry.get('anchor_id')} must start "
                    "from the genesis head"
                )
        else:
            if entry.get("prev_head_sha256") != previous.get("head_sha256"):
                errors.append(
                    f"{relative_path}: anchor chain broken at {entry.get('anchor_id')} "
                    "(prev_head_sha256 does not match the previous anchor)"
                )
            if entry.get("prev_lines") != previous.get("lines"):
                errors.append(
                    f"{relative_path}: anchor chain broken at {entry.get('anchor_id')} "
                    "(prev_lines does not match the previous anchor)"
                )
            if isinstance(entry.get("lines"), int) and isinstance(
                previous.get("lines"), int
            ):
                if entry["lines"] < previous["lines"]:
                    errors.append(
                        f"{relative_path}: anchor {entry.get('anchor_id')} pins fewer "
                        "lines than its predecessor (append-only violation)"
                    )
        latest[relative_path] = entry

    # 3. tip pin / coverage
    for relative_path in anchored_ledgers():
        path = root / relative_path
        current = (
            ledger_lines(path.read_text(encoding="utf-8")) if path.exists() else []
        )
        entry = latest.get(relative_path)
        if entry is None:
            errors.append(
                f"{relative_path}: not anchored — run "
                "'python3 scripts/researchos_anchor.py update' and commit the result"
            )
            continue
        pinned_lines = entry.get("lines")
        pinned_head = entry.get("head_sha256")
        actual_head = rolling_head(current)
        if pinned_lines == len(current) and pinned_head != actual_head:
            # Same length, different content: this is a rewrite, not an append,
            # and re-anchoring cannot hide it (the older entry still pins the
            # original prefix — see property 2 above).
            errors.append(
                f"{relative_path}: anchor pins {pinned_lines} lines to "
                f"{str(pinned_head)[:12]}... but the same {len(current)} lines now "
                f"roll up to {actual_head[:12]}... — the tip was rewritten, not "
                "appended (append-only violation)"
            )
        elif pinned_lines != len(current) or pinned_head != actual_head:
            errors.append(
                f"{relative_path}: anchor is stale ({pinned_lines} lines pinned, "
                f"{len(current)} now) — if lines were appended, run 'python3 "
                "scripts/researchos_anchor.py update' and commit the result"
            )
    return errors


# ---------------------------------------------------------------------------
# Baseline / legacy detection
# ---------------------------------------------------------------------------


def load_baseline() -> Dict[str, Any]:
    if not STATE_BASELINE.exists():
        return {}
    with STATE_BASELINE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def legacy_hashes(baseline: Optional[Dict[str, Any]] = None) -> Dict[str, set]:
    baseline = baseline if baseline is not None else load_baseline()
    return {
        path: set(hashes)
        for path, hashes in (baseline.get("legacy_line_sha256") or {}).items()
    }


def is_legacy(
    relative_path: str,
    record: Dict[str, Any],
    baseline: Optional[Dict[str, Any]] = None,
) -> bool:
    hashes = legacy_hashes(baseline).get(relative_path, set())
    return line_hash(record) in hashes


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def git(*args: str, cwd: Optional[Path] = None, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd or ROOT),
        text=True,
        capture_output=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout.strip()


def git_show(rev: str, path: str, cwd: Optional[Path] = None) -> Optional[str]:
    result = subprocess.run(
        ["git", "show", f"{rev}:{path}"],
        cwd=str(cwd or ROOT),
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def git_show_many(
    requests: Iterable[Tuple[str, str]], cwd: Optional[Path] = None
) -> Dict[Tuple[str, str], Optional[str]]:
    """Batch ``git show <rev>:<path>`` through a single ``git cat-file --batch``.

    Returns ``{(rev, path): text_or_None}``; ``None`` means the object does not
    exist at that revision (file not yet created, or a synthetic rev).  Reading
    in binary and decoding per blob keeps multi-byte (Japanese) ledgers correct,
    because ``cat-file`` reports byte sizes, not character counts.
    """
    unique: List[Tuple[str, str]] = list(dict.fromkeys(requests))
    result: Dict[Tuple[str, str], Optional[str]] = {key: None for key in unique}
    if not unique:
        return result
    names = "\n".join(f"{rev}:{path}" for rev, path in unique) + "\n"
    try:
        proc = subprocess.run(
            ["git", "cat-file", "--batch"],
            cwd=str(cwd or ROOT),
            input=names.encode("utf-8"),
            capture_output=True,
        )
    except OSError:
        return result
    if proc.returncode != 0:
        return result
    stream = proc.stdout
    offset = 0
    for key in unique:
        newline = stream.find(b"\n", offset)
        if newline == -1:
            break
        header = stream[offset:newline].decode("utf-8", "replace").strip()
        offset = newline + 1
        if header.endswith("missing"):
            continue
        parts = header.split()
        if len(parts) < 3:
            continue
        try:
            size = int(parts[2])
        except ValueError:
            continue
        blob = stream[offset : offset + size]
        offset += size + 1  # trailing newline after the blob
        result[key] = blob.decode("utf-8", "replace")
    return result


def session_from_branch(branch: Optional[str] = None, root: Path = ROOT) -> str:
    """``arena/86da9dab-researchos`` -> ``SES-86da9dab`` (the branch is the anchor).

    PRP-002 rev3: every anchor entry is attributed to the session that wrote it
    (``RECORD_FILES`` checks authorship), so an auto-pin triggered by a record
    that carries no ``session_id`` key -- ``state/review_queue.jsonl`` uses
    ``created_by_session`` / ``claimed_by_session`` -- must still resolve to a
    real session instead of ``unknown``.
    """
    name = branch or current_branch(root)
    if name.startswith("arena/") and name.endswith("-researchos"):
        return "SES-" + name[len("arena/") : -len("-researchos")]
    if name and name != "HEAD":
        return "SES-" + name.replace("/", "-")
    return ""


def current_branch(root: Path = ROOT) -> str:
    env = os.environ.get("GITHUB_REF_NAME")
    if env:
        return env
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=str(root),
        text=True,
        capture_output=True,
    )
    name = result.stdout.strip()
    if name and name != "HEAD":
        return name
    # An unborn branch (a fresh `git init -b <name>` with no commit yet) reports
    # "HEAD" from rev-parse, but symbolic-ref still knows the branch name.  A
    # genuinely detached HEAD fails symbolic-ref and keeps the old fallback.
    symbolic = subprocess.run(
        ["git", "symbolic-ref", "--short", "HEAD"],
        cwd=str(root),
        text=True,
        capture_output=True,
    )
    name = symbolic.stdout.strip()
    if name:
        return name
    return os.environ.get("GITHUB_HEAD_REF", "HEAD")


def commit_trailers(rev: str) -> Dict[str, str]:
    body = git("log", "-1", "--format=%B", rev)
    trailers: Dict[str, str] = {}
    for line in body.splitlines():
        match = re.match(r"^([A-Za-z0-9-]+):\s*(.+?)\s*$", line.strip())
        if match:
            trailers.setdefault(match.group(1), match.group(2))
    return trailers


def commit_paths(rev: str) -> List[str]:
    output = git("show", "--name-only", "--format=", rev)
    return [line.strip() for line in output.splitlines() if line.strip()]


def commits_in_range(base: str, first_parent: bool = False) -> List[str]:
    args = ["rev-list", "--reverse"]
    if first_parent:
        args.append("--first-parent")
    args.append(f"{base}..HEAD")
    output = git(*args)
    return [line.strip() for line in output.splitlines() if line.strip()]


def is_merge(rev: str) -> bool:
    try:
        parents = git("rev-list", "--parents", "-n", "1", rev).split()
    except RuntimeError:
        # Synthetic or invalid SHA (e.g. probe mock) — treat conservatively
        return False
    return len(parents) > 2


def commit_parents(rev: str) -> Optional[List[str]]:
    """Return parent SHAs of rev, or None if rev is synthetic/invalid."""
    try:
        parts = git("rev-list", "--parents", "-n", "1", rev).split()
    except RuntimeError:
        return None
    # parts[0] is rev itself, rest are parents
    if not parts:
        return None
    return parts[1:] if len(parts) > 1 else []


def is_ancestor(ancestor: str, descendant: str) -> Optional[bool]:
    """Check if ancestor is ancestor of descendant. None on error/synthetic."""
    if not ancestor or not descendant:
        return None
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=str(ROOT),
        capture_output=True,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    # Error (e.g. synthetic sha, unknown rev)
    return None


def commits_in_merge_second_parent(merge_sha: str, base_commit: str, first_parent_sha: str) -> List[str]:
    """List commits from second-parent side of a merge, excluding first-parent history.
    
    Used to audit governance paths introduced via a side branch that --first-parent hides.
    Returns [] on error or if merge has no second parent.
    """
    parents = commit_parents(merge_sha)
    if parents is None or len(parents) < 2:
        return []
    # parents[0] is first_parent, parents[1:] are other parents
    result: List[str] = []
    for other in parents[1:]:
        try:
            # commits reachable from other but not from first_parent nor base
            out = git("rev-list", "--reverse", f"{base_commit}..{other}", f"^{first_parent_sha}")
            result.extend(line.strip() for line in out.splitlines() if line.strip())
        except RuntimeError:
            # If enumeration fails (synthetic), report as error elsewhere; don't crash
            continue
    return result


# ---------------------------------------------------------------------------
# Path matching (supports ** across separators, * within a segment)
# ---------------------------------------------------------------------------


def path_matches(pattern: str, path: str) -> bool:
    regex: List[str] = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "*":
            if pattern[index : index + 2] == "**":
                regex.append(".*")
                index += 2
                if index < len(pattern) and pattern[index] == "/":
                    index += 1
                continue
            regex.append("[^/]*")
            index += 1
        elif char == "?":
            regex.append("[^/]")
            index += 1
        else:
            regex.append(re.escape(char))
            index += 1
    return re.fullmatch("".join(regex), path) is not None


def match_any(patterns: Sequence[str], path: str) -> bool:
    return any(path_matches(pattern, path) for pattern in patterns)


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


def load_policy() -> Dict[str, Any]:
    with ROLES_POLICY.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def policy_errors(policy: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    roles = policy.get("roles") or {}
    if not roles:
        errors.append("policy: no roles defined")
    for name, spec in roles.items():
        if not isinstance(spec.get("may_write"), list):
            errors.append(f"policy: role '{name}' has no may_write list")
        if not spec.get("description"):
            errors.append(f"policy: role '{name}' has no description")
    for path in policy.get("governance_paths", []):
        if not isinstance(path, str) or not path:
            errors.append("policy: invalid governance path")
    return errors


# ---------------------------------------------------------------------------
# Record lookups
# ---------------------------------------------------------------------------


def by_id(records: Iterable[Dict[str, Any]], key: str) -> Dict[str, Dict[str, Any]]:
    return {
        str(record[key]): record
        for record in records
        if isinstance(record, dict) and key in record
    }


def load_collection(name: str) -> List[Dict[str, Any]]:
    return read_jsonl(ROOT / STATE_FILES[name])


def load_effective(name: str) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    return resolve_effective(
        load_collection(name),
        COLLECTION_ID_KEYS.get(name),
        allow_identical_duplicates=name in IDEMPOTENT_COLLECTIONS,
    )


def now_utc() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def next_id(records: List[Dict[str, Any]], key: str, prefix: str) -> str:
    """Generate next sequential ID. WARNING: parallel session lines collide.

    Two independent proposers forking the same parent will mint the same next
    ID (e.g. PRP-002) and cause duplicate revision errors on union.  For
    governance IDs (PRP-*, REV-*, APR-*, RQ-*) use a manual unique suffix or
    await PRP-003's UUID scheme.  The function is kept for research claims
    where collision is low-impact.
    """
    highest = 0
    for record in records:
        value = str(record.get(key, ""))
        if value.startswith(prefix):
            suffix = value[len(prefix) :].lstrip("-")
            if suffix.isdigit():
                highest = max(highest, int(suffix))
    return f"{prefix}-{highest + 1:03d}"


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":  # pragma: no cover - debugging helper
    print(json.dumps(load_policy(), indent=2, ensure_ascii=False))
    sys.exit(0)
