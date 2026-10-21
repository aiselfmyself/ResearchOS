#!/usr/bin/env python3
"""Check ledger-ID and repo-path references inside research memos.

This is the third member of the memo-checking family:

  * scripts/check_citations.py       -- state/sources.jsonl vs arXiv snapshot
  * scripts/check_memo_citations.py  -- arXiv IDs inside contributions/*.md
  * scripts/check_memo_ledger_refs.py-- ledger IDs and repo paths inside
                                        contributions/*.md  (this script)

WHY THIS EXISTS
---------------
contributions/2026-10-20_integrated_survey_report.md §3.4 records a finding
from [Mei et al., 2025]: current models are markedly better at *understanding*
complex context than at *generating* equally sophisticated long-form output.
This repository delegates long-form writing to agents (survey memos, audit
documents, the integrated report itself, PR bodies), so the asymmetry applies
directly to it.

Two consequences, both observed here rather than assumed:

  * Two factual errors in an agent-written memo survived human reading and
    were caught only by verbatim collation against the original papers
    ("arXiv:2605.23950 has no experiments"; "context engineering is a
    hierarchy"). See docs/incomplete-work-audit-2026-10-20.md §13.7(1).
  * A transcription error crept into an evidence record's excerpt field and
    was caught only by diffing the excerpt against the collation session's
    source text. See §13.6.

**This script cannot catch either class.** Semantic errors need the original
source; this script only sees the memo. What it *can* catch mechanically is
the failure mode that long-form generation is most prone to and that costs
nothing to verify: **references that do not resolve.**

WHAT IS CHECKED
---------------
1. Every ID-shaped token (``SRC-``/``EVD-``/``CLM-``/``VER-``/``HYP-``)
   mentioned in a scanned memo must exist in one of the five research
   ledgers under state/. A citation of a record that does not exist is a
   hallucinated or mistyped reference.
2. IDs that were removed from the ledgers on 2026-10-20 and preserved in
   docs/archived-ledger-records-2026-10-20.md are reported as ARCHIVED, not
   as failures. The integrated report legitimately discusses CLM-004/005/007
   in that capacity; treating them as dangling would be wrong.
3. Every repo-relative path token (gitswarm/, scripts/, tests/, state/,
   contributions/, docs/ + a file extension) mentioned in a scanned memo
   must exist. This is the same rule scripts/validate_state.py applies to
   ledger records, extended here to memos.

Optional (``--coverage``, not a failure):
4. Ledger records that no scanned memo references. Newly created evidence is
   legitimately unreferenced until the report is updated, so this is
   informational only and is deliberately not wired into CI.

The token patterns are imported from scripts/validate_state.py so that the
ledger checker and the memo checker cannot drift apart.

Usage:
    python3 scripts/check_memo_ledger_refs.py                  # all contributions/*.md
    python3 scripts/check_memo_ledger_refs.py --memos A.md B.md
    python3 scripts/check_memo_ledger_refs.py --coverage       # also report unreferenced records
    python3 scripts/check_memo_ledger_refs.py --quiet          # only the summary line

Exit codes: 0 = every reference resolves, 1 = at least one dangling
reference, 2 = usage / I/O error.
Standard library only. No network.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

try:
    import validate_state as vs
except ImportError:  # running as scripts/check_memo_ledger_refs.py
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import validate_state as vs

ROOT = vs.ROOT
DEFAULT_MEMO_DIR = ROOT / "contributions"
DEFAULT_ARCHIVE_DOC = ROOT / "docs" / "archived-ledger-records-2026-10-20.md"

Finding = Tuple[str, str, str]  # (memo name, kind, token)


def load_ledger_ids() -> Dict[str, Set[str]]:
    """Map every ID prefix to the set of IDs present in the research ledgers."""
    ids: Dict[str, Set[str]] = {}
    for name, (ledger, _schema, id_key) in vs.COLLECTIONS.items():
        prefix = vs.ID_PREFIXES[name]
        ids.setdefault(prefix, set())
        path = ROOT / ledger
        if not path.exists():
            raise FileNotFoundError(f"ledger not found: {path}")
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            value = json.loads(line).get(id_key)
            if isinstance(value, str):
                ids[prefix].add(value)
    return ids


def load_archived_ids(archive_doc: Path) -> Set[str]:
    """IDs preserved in the archive document after the 2026-10-20 removal.

    The document is prose, so this collects every ID-shaped token it
    mentions. That is intentionally broad: an ID mentioned there is *known*
    to the repository even if it is not in a ledger.
    """
    if not archive_doc.exists():
        return set()
    return {m.group(0) for m in vs.ID_TOKEN_RE.finditer(archive_doc.read_text(encoding="utf-8"))}


def scan(memo_paths: List[Path], ids: Dict[str, Set[str]], archived: Set[str]
         ) -> Tuple[List[Finding], List[Finding], Dict[str, Set[str]]]:
    """Return (dangling, archived_hits, referenced_ids)."""
    dangling: List[Finding] = []
    archived_hits: List[Finding] = []
    referenced: Dict[str, Set[str]] = {p: set() for p in ids}
    seen_dangling: Set[Tuple[str, str]] = set()
    seen_archived: Set[Tuple[str, str]] = set()

    for memo in memo_paths:
        text = memo.read_text(encoding="utf-8")
        for match in vs.ID_TOKEN_RE.finditer(text):
            token = match.group(0)
            prefix = match.group("prefix")
            if prefix in referenced:
                referenced[prefix].add(token)
            if token in ids.get(prefix, set()):
                continue
            key = (memo.name, token)
            if token in archived:
                if key not in seen_archived:
                    seen_archived.add(key)
                    archived_hits.append((memo.name, "archived", token))
                continue
            if key not in seen_dangling:
                seen_dangling.add(key)
                dangling.append((memo.name, "id", token))

        seen_paths: Set[str] = set()
        for match in vs.PATH_TOKEN_RE.finditer(text):
            path = match.group("path")
            if (ROOT / path).exists() or path in seen_paths:
                continue
            seen_paths.add(path)
            dangling.append((memo.name, "path", path))

    return dangling, archived_hits, referenced


def coverage_report(ids: Dict[str, Set[str]], referenced: Dict[str, Set[str]]) -> List[str]:
    """Ledger records that no scanned memo mentions."""
    lines: List[str] = []
    for prefix, known in sorted(ids.items()):
        missing = sorted(known - referenced.get(prefix, set()))
        if missing:
            lines.append(f"  {prefix}: {len(missing)} record(s) not referenced by any memo")
            for token in missing[:20]:
                lines.append(f"      {token}")
            if len(missing) > 20:
                lines.append(f"      ... and {len(missing) - 20} more")
    return lines


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--memos", nargs="*", default=None,
                        help="memo files to scan (default: contributions/*.md)")
    parser.add_argument("--archive-doc", default=str(DEFAULT_ARCHIVE_DOC),
                        help="document listing IDs removed from the ledgers")
    parser.add_argument("--coverage", action="store_true",
                        help="also report ledger records no memo references (informational)")
    parser.add_argument("--quiet", action="store_true", help="print only the summary")
    args = parser.parse_args(argv)

    if args.memos:
        memo_paths = [Path(p) for p in args.memos]
    else:
        if not DEFAULT_MEMO_DIR.is_dir():
            print(f"error: memo directory not found: {DEFAULT_MEMO_DIR}", file=sys.stderr)
            return 2
        memo_paths = sorted(DEFAULT_MEMO_DIR.glob("*.md"))

    missing_files = [str(p) for p in memo_paths if not p.exists()]
    if missing_files:
        print("error: memo file(s) not found: " + ", ".join(missing_files), file=sys.stderr)
        return 2

    try:
        ids = load_ledger_ids()
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: could not load ledgers: {exc}", file=sys.stderr)
        return 2

    archived = load_archived_ids(Path(args.archive_doc))
    dangling, archived_hits, referenced = scan(memo_paths, ids, archived)

    if not args.quiet:
        for name, kind, token in dangling:
            label = "dangling path" if kind == "path" else "dangling ledger ID"
            print(f"  {name}: {label} {token}")
        for name, _kind, token in archived_hits:
            print(f"  {name}: archived ledger ID {token} (known, not in any ledger) -- OK")
        if args.coverage:
            for line in coverage_report(ids, referenced):
                print(line)

    n_dangling = len(dangling)
    summary = (
        f"summary: {len(memo_paths)} memo(s) scanned, "
        f"{n_dangling} dangling reference(s), "
        f"{len(archived_hits)} archived ID reference(s)"
    )
    print(summary)
    return 1 if n_dangling else 0


if __name__ == "__main__":
    raise SystemExit(main())
