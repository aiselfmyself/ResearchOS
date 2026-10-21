#!/usr/bin/env python3
"""Check arXiv citations inside survey memos (contributions/*.md) offline-first.

This is the companion of scripts/check_citations.py for memo-internal
citations: the ledger checker verifies state/sources.jsonl, while this
script verifies the reference sections (参考文献) and inline arXiv mentions
of the research memos in contributions/.

Modes:

  * Default mode is OFFLINE and deterministic: every arXiv ID cited in the
    scanned memos is looked up in the bundled snapshot
    tests/fixtures/arxiv_metadata_snapshot.json (captured 2026-10-20), and
    each numbered reference entry's title, authors and publication year are
    compared against it. Any number of re-runs, including inside unit
    tests, produce the same result and need no network.

  * --live queries export.arxiv.org's Atom API for the *current* metadata
    and runs the same comparison against it. It needs network access and
    is subject to arXiv's rate limits, so it is a MANUAL tool only: it is
    deliberately not wired into .github/workflows/core-check.yml and is
    never invoked by the tests.

Comparison rules per reference entry (lines starting with "[label]" inside
the 参考文献 / References section):

  * entries without an arXiv ID are skipped -- but only when the entry
    carries some other URL (e.g. a link to a GitHub repository). An entry
    with no arXiv ID and no URL at all is reported as MALFORMED and fails:
    in practice it means the entry was wrapped onto a second physical line,
    which the line-oriented parser cannot see;
  * the arXiv ID (from "arXiv:ID" or an arxiv.org/abs/ URL) must exist in
    the snapshot;
  * the quoted title must match the snapshot title (whitespace- and
    case-normalized: memos may fix capitalization when transcribing);
  * the year following the arXiv ID must match the snapshot's submission
    year;
  * the author list must match the snapshot: exactly (no ellipsis), or as
    "first N ... last M" when the memo uses an ellipsis (… or ...).

Additionally, every arXiv ID mentioned anywhere in a scanned memo (inline
citations included) must exist in the snapshot.

Usage:
    python3 scripts/check_memo_citations.py                 # all contributions/*.md
    python3 scripts/check_memo_citations.py --memos A.md B.md
    python3 scripts/check_memo_citations.py --live          # manual, needs network

Exit codes: 0 = all checked citations match, 1 = mismatch or missing record,
2 = usage / I/O / network error.
Standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import check_citations as cc
except ImportError:  # running as scripts/check_memo_citations.py
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import check_citations as cc

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MEMO_DIR = ROOT / "contributions"
DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "arxiv_metadata_snapshot.json"

# "arXiv:2610.07625" / "arXiv:2610.07625v1" (case-sensitive, as on arXiv)
ARXIV_COLON_RE = re.compile(r"arXiv:(\d{4}\.\d{4,5})(?:v\d+)?")
# "https://arxiv.org/abs/2610.07625" / "arxiv.org/abs/1707.08561v3"
ARXIV_URL_RE = re.compile(r"arxiv\.org/abs/(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)

REFS_HEADING_RE = re.compile(r"^#{1,3}\s+.*(?:参考文献|References)", re.MULTILINE)
NEXT_HEADING_RE = re.compile(r"^#{1,2}\s+\S", re.MULTILINE)
REF_START_RE = re.compile(r"^\[([A-Za-z0-9]+)\]\s*")
# e.g. 'arXiv:2610.07625v1 [cs.LG], 2026' or 'arXiv:2609.18094, 2026'
YEAR_RE_TEMPLATE = r"arXiv:{id}(?:v\d+)?(?:\s*\[[^\]]*\])?,\s*(\d{{4}})"
QUOTED_RE = re.compile(r'"([^"]+)"')
ELLIPSIS_RE = re.compile(r"\s*(?:…|\.\.\.)\s*")
# Any URL marks a reference as legitimately non-arXiv (a code repository, a
# project page, ...). Without one, an entry that carries no arXiv ID is far
# more likely to be broken than intentional -- see check_entry().
URL_RE = re.compile(r"https?://", re.IGNORECASE)


def extract_arxiv_ids(text: str) -> List[str]:
    """All arXiv IDs mentioned in text, in first-seen order, deduplicated."""
    seen: List[str] = []
    for match in list(ARXIV_COLON_RE.finditer(text)) + list(ARXIV_URL_RE.finditer(text)):
        arxiv_id = match.group(1)
        if arxiv_id not in seen:
            seen.append(arxiv_id)
    return seen


def find_reference_section(text: str) -> Optional[str]:
    """Return the raw text of the 参考文献/References section, or None."""
    heading = REFS_HEADING_RE.search(text)
    if heading is None:
        return None
    start = heading.end()
    nxt = NEXT_HEADING_RE.search(text, start)
    return text[start : nxt.start() if nxt else len(text)]


def strip_leading_parentheticals(text: str) -> str:
    """Drop leading full-width parenthetical notes like （言及のみ）."""
    while text.startswith("（"):
        close = text.find("）")
        if close == -1:
            break
        text = text[close + 1 :].lstrip()
    return text


def parse_reference_entry(line: str) -> Optional[Dict[str, Any]]:
    """Parse one '[label] ...' reference line into a dict.

    Returns None when the line is not a reference entry. The dict always
    carries label; arxiv_id may be None (non-arXiv entry -> skipped later).
    """
    match = REF_START_RE.match(line)
    if match is None:
        return None
    rest = strip_leading_parentheticals(line[match.end() :].strip())
    ids = extract_arxiv_ids(rest)
    entry: Dict[str, Any] = {
        "label": match.group(1),
        "raw": rest,
        "ids": ids,
        "arxiv_id": ids[0] if ids else None,
    }
    if not ids:
        return entry

    quoted = QUOTED_RE.search(rest)
    if quoted:
        entry["title"] = quoted.group(1)
        author_segment = rest[: quoted.start()]
    else:
        colon = rest.find("arXiv:")
        author_segment = rest[:colon] if colon != -1 else ""
    entry["authors"] = author_segment.strip().rstrip(". ").strip()

    year_match = re.search(YEAR_RE_TEMPLATE.format(id=re.escape(entry["arxiv_id"])), rest)
    if year_match:
        entry["year"] = int(year_match.group(1))
    return entry


def check_author_list(author_segment: str, fixture_authors: List[str]) -> List[str]:
    """Compare a memo's author segment against the snapshot's author list."""
    problems: List[str] = []
    if not author_segment:
        return problems  # nothing claimed -> nothing to check
    segments = ELLIPSIS_RE.split(author_segment)
    head = [a.strip().rstrip(".") for a in segments[0].split(",") if a.strip()]
    if len(segments) == 1:
        if head != fixture_authors:
            problems.append(
                f"authors ({len(head)} vs {len(fixture_authors)}): "
                f"memo={head!r} arxiv={fixture_authors!r}"
            )
        return problems
    tail = [a.strip().rstrip(".") for a in segments[-1].split(",") if a.strip()]
    if fixture_authors[: len(head)] != head:
        problems.append(
            f"authors head mismatch: memo={head!r} "
            f"arxiv_head={fixture_authors[: len(head)]!r}"
        )
    expected_tail = fixture_authors[len(fixture_authors) - len(tail) :]
    if expected_tail != tail:
        problems.append(
            f"authors tail mismatch: memo={tail!r} arxiv_tail={expected_tail!r}"
        )
    if len(head) + len(tail) > len(fixture_authors):
        problems.append(
            f"authors list too long: {len(head)}+{len(tail)} > {len(fixture_authors)}"
        )
    return problems


def check_entry(
    memo_name: str, entry: Dict[str, Any], entries: Dict[str, Dict[str, Any]]
) -> Tuple[int, List[str]]:
    """Check one reference entry. Returns (checked, report_lines)."""
    label = entry["label"]
    arxiv_id = entry.get("arxiv_id")
    if arxiv_id is None:
        # A reference to something other than a paper (a code repository, a
        # project page) is fine -- but only if it actually links to it. An
        # entry with no arXiv ID *and* no URL is almost always an entry that
        # an editor wrapped onto a second physical line: the parser only ever
        # sees the first line, so the arXiv ID sitting on the second line
        # silently disappears. That used to be reported as a harmless SKIP,
        # which meant a real citation went entirely unverified.
        if URL_RE.search(entry.get("raw", "")):
            return 0, [f"SKIP    {memo_name} [{label}] (no arXiv ID)"]
        return 0, [
            f"MALFORMED {memo_name} [{label}] reference has neither an arXiv "
            f"ID nor any URL -- it is most likely wrapped across lines. "
            f"Put every reference on a single physical line."
        ]
    if len(entry["ids"]) > 1:
        return 1, [
            f"MISMATCH {memo_name} [{label}] inconsistent arXiv IDs in one "
            f"reference: {entry['ids']}"
        ]
    fixture_entry = entries.get(arxiv_id)
    if fixture_entry is None:
        return 1, [
            f"MISSING {memo_name} [{label}] {arxiv_id} (not in metadata snapshot)"
        ]

    problems: List[str] = []
    if "title" in entry:
        # Memos write the title as "...Title." inside the quotes, so a
        # trailing period is punctuation, not part of the title.
        memo_title = cc.normalize(entry["title"]).rstrip(".")
        snapshot_title = cc.normalize(str(fixture_entry.get("title", ""))).rstrip(".")
        if memo_title.lower() != snapshot_title.lower():
            problems.append(
                f"title: memo={memo_title!r} arxiv={snapshot_title!r}"
            )
    if "year" in entry:
        published = str(fixture_entry.get("published", ""))
        if not published[:4].isdigit():
            problems.append(f"published date missing in snapshot: {fixture_entry!r}")
        elif entry["year"] != int(published[:4]):
            problems.append(f"year: memo={entry['year']} arxiv={int(published[:4])}")
    problems.extend(
        check_author_list(entry.get("authors", ""), fixture_entry.get("authors", []))
    )
    if problems:
        return 1, [
            f"MISMATCH {memo_name} [{label}] {arxiv_id} {problem}"
            for problem in problems
        ]
    return 1, [f"OK      {memo_name} [{label}] {arxiv_id} (title/authors/year match)"]


def check_memo(
    memo_path: Path, entries: Dict[str, Dict[str, Any]]
) -> Tuple[int, int, List[str]]:
    """Check one memo. Returns (checked, skipped, report_lines)."""
    name = memo_path.name
    text = memo_path.read_text(encoding="utf-8")
    checked = 0
    skipped = 0
    report: List[str] = []
    ref_ids: List[str] = []

    section = find_reference_section(text)
    if section is None:
        report.append(f"NOTE    {name} (no 参考文献 section)")
    else:
        for line in section.splitlines():
            entry = parse_reference_entry(line)
            if entry is None:
                continue
            n, lines = check_entry(name, entry, entries)
            checked += n
            if entry.get("arxiv_id"):
                ref_ids.extend(entry["ids"])
            elif not any(line.startswith("MALFORMED") for line in lines):
                skipped += 1
            report.extend(lines)

    # Inline mentions anywhere in the memo must be covered by the snapshot
    # (deduplicated against the per-reference MISSING lines above).
    for arxiv_id in extract_arxiv_ids(text):
        if arxiv_id in ref_ids:
            continue
        if arxiv_id not in entries:
            report.append(
                f"MISSING {name} {arxiv_id} (inline mention, not in metadata snapshot)"
            )
        else:
            checked += 1
            report.append(
                f"OK      {name} {arxiv_id} (inline mention found in snapshot)"
            )
    return checked, skipped, report


def load_memos(memo_args: Optional[List[Path]]) -> List[Path]:
    if memo_args:
        memos = [Path(p) for p in memo_args]
        missing = [str(p) for p in memos if not p.is_file()]
        if missing:
            raise FileNotFoundError(f"memo file(s) not found: {', '.join(missing)}")
        return memos
    return sorted(DEFAULT_MEMO_DIR.glob("*.md"))


def load_fixture(path: Path) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    """Snapshot union view: frozen base JSON + `*.d/*.json` parts.

    Delegates to `check_citations.load_fixture` (and thus to
    `ledger_store.load_fixture`) so the two citation checkers cannot disagree
    about which entries exist.
    """
    return cc.load_fixture(path)


def fetch_live_ids(arxiv_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Query the arXiv Atom API. MANUAL use only (network + rate limits)."""
    return cc.fetch_live(arxiv_ids)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check contributions/*.md citations against arXiv metadata."
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="query export.arxiv.org instead of the bundled snapshot "
        "(manual use only; needs network; not a CI gate)",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=DEFAULT_FIXTURE,
        help=f"metadata snapshot JSON (default: {DEFAULT_FIXTURE})",
    )
    parser.add_argument(
        "--memos",
        nargs="+",
        type=Path,
        default=None,
        help="memo files to check (default: all contributions/*.md)",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="print only failures and the summary"
    )
    args = parser.parse_args(argv)

    try:
        memos = load_memos(args.memos)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.live:
        print(
            "WARNING: --live queries export.arxiv.org "
            "(network + arXiv rate limits). Manual use only; "
            "not a CI gate.",
            file=sys.stderr,
        )
        all_ids = sorted(
            {
                arxiv_id
                for memo in memos
                for arxiv_id in extract_arxiv_ids(
                    memo.read_text(encoding="utf-8")
                )
            }
        )
        try:
            entries = fetch_live_ids(all_ids)
        except Exception as exc:  # URLError/HTTPError/timeout/parse
            print(f"error: live fetch failed: {exc}", file=sys.stderr)
            return 2
        if all_ids and not entries:
            print(
                "error: live fetch returned no entries "
                "(rate limited or empty response); not treating as mismatch",
                file=sys.stderr,
            )
            return 2
        header_note = f"live API: {cc.LIVE_API}?id_list={','.join(all_ids)}"
    else:
        try:
            entries, header = cc.load_fixture(args.fixture)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"error: failed to load fixture: {exc}", file=sys.stderr)
            return 2
        header_note = (
            f"offline snapshot: {args.fixture} "
            f"(captured {header.get('captured_at', 'unknown')})"
        )

    checked = 0
    skipped = 0
    report: List[str] = []
    for memo in memos:
        n, s, lines = check_memo(memo, entries)
        checked += n
        skipped += s
        report.extend(lines)

    failures = [
        line
        for line in report
        if line.startswith(("MISMATCH", "MISSING", "MALFORMED"))
    ]
    if not args.quiet:
        print(header_note)
        print(f"memos: {', '.join(m.name for m in memos)}")
    for line in report:
        if args.quiet and (line.startswith("OK") or line.startswith("NOTE")):
            continue
        print(line)
    print(
        f"summary: {len(memos)} memo(s) scanned, {checked} arXiv citation(s) "
        f"checked, {skipped} skipped, {len(failures)} failure(s)"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
