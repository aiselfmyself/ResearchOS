#!/usr/bin/env python3
"""Check the bibliography of state/sources.jsonl against arXiv metadata.

Implements README "next stage 2" (mechanical citation verification against
the arXiv API) in the smallest offline-first form:

  * Default mode is OFFLINE and deterministic: the ledger is compared
    against the bundled snapshot tests/fixtures/arxiv_metadata_snapshot.json
    (captured 2026-10-20). Any number of re-runs, including inside CI or
    unit tests, produce the same result and need no network.

  * --live queries export.arxiv.org's Atom API for the *current* metadata.
    It needs network access and is subject to arXiv's rate limits, so it is
    a MANUAL tool only: it is deliberately not wired into
    .github/workflows/core-check.yml and is never invoked by the tests.

What is compared per arXiv source: title (whitespace-normalized), the
ordered author list, and the publication year (derived from the submission
date). Sources without an arXiv ID (e.g. the GitHub repo SRC-004) are
skipped, not failures.

Usage:
    python3 scripts/check_citations.py            # offline self-check
    python3 scripts/check_citations.py --live     # manual, needs network
    python3 scripts/check_citations.py --fixture PATH --sources PATH

Exit codes: 0 = all checked sources match, 1 = mismatch or missing record,
2 = usage / I/O / network error.
Standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]

try:
    import ledger_store
except ImportError:  # running as scripts/check_citations.py
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import ledger_store

DEFAULT_SOURCES = ROOT / "state" / "sources.jsonl"
DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "arxiv_metadata_snapshot.json"
LIVE_API = "https://export.arxiv.org/api/query"
USER_AGENT = "ResearchOS-check_citations/1.0 (offline-first citation check)"

# arXiv IDs look like 2610.07625, optionally with a version suffix (v1).
ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5})(?:v\d+)?$")
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def normalize(text: str) -> str:
    """Collapse all whitespace runs so wrapping differences do not matter."""
    return " ".join(text.split())


def extract_arxiv_id(source: Dict[str, Any]) -> Optional[str]:
    """Return the bare arXiv ID from a ledger source's url or doi field.

    Returns None when the source does not point at arXiv (then it is
    skipped by the check, not failed).
    """
    for field in ("url", "doi"):
        value = source.get(field)
        if not value or not isinstance(value, str):
            continue
        match = ARXIV_ID_RE.search(value.strip())
        if match:
            return match.group(1)
    return None


def load_ledger(path: Path) -> List[Dict[str, Any]]:
    """Return the sources union view: frozen base file + session shards.

    A ledger whose shards double an ID is rejected here rather than silently
    collapsed, for the same reason the validator reports duplicates: the
    checker must not pick a winner (see scripts/ledger_store.py).
    """
    records, errors, origins = ledger_store.load_ledger(path)
    if errors:
        raise ValueError("\n".join(errors))
    duplicates = ledger_store.duplicate_ids(records, origins, "source_id")
    if duplicates:
        raise ValueError("\n".join(duplicates))
    return records


def load_fixture(path: Path) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    """Return ({arxiv_id: entry}, fixture header) for the snapshot union view.

    The base JSON is the frozen snapshot; entries added after 2026-10-21 live
    in `tests/fixtures/arxiv_metadata_snapshot.d/*.json`. The header returned
    is the base header verbatim, so a new part cannot silently rewrite the
    base's `captured_at` / `capture_note`.
    """
    return ledger_store.load_fixture(path)


def parse_atom_response(xml_text: str) -> Dict[str, Dict[str, Any]]:
    """Parse an arXiv Atom API response into {arxiv_id: entry}.

    Entry shape matches the bundled fixture: arxiv_id, title, authors,
    published (YYYY-MM-DD, taken from the API's published timestamp).
    """
    root = ET.fromstring(xml_text)
    entries: Dict[str, Dict[str, Any]] = {}
    for node in root.findall("atom:entry", ATOM_NS):
        raw_id = (node.findtext("atom:id", "", ATOM_NS) or "").strip()
        match = ARXIV_ID_RE.search(raw_id)
        if not match:
            continue  # error placeholder entries have no real arXiv ID
        arxiv_id = match.group(1)
        title = normalize(node.findtext("atom:title", "", ATOM_NS) or "")
        authors = [
            normalize(author.findtext("atom:name", "", ATOM_NS) or "")
            for author in node.findall("atom:author", ATOM_NS)
        ]
        published = (node.findtext("atom:published", "", ATOM_NS) or "")[:10]
        entries[arxiv_id] = {
            "arxiv_id": arxiv_id,
            "title": title,
            "authors": authors,
            "published": published,
        }
    return entries


def fetch_live(arxiv_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Query the arXiv Atom API. MANUAL use only (network + rate limits)."""
    query = ",".join(arxiv_ids)
    url = f"{LIVE_API}?id_list={query}&max_results={max(len(arxiv_ids), 1)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        xml_text = response.read().decode("utf-8")
    return parse_atom_response(xml_text)


def compare(source: Dict[str, Any], entry: Dict[str, Any]) -> List[str]:
    """Return human-readable mismatch descriptions (empty list = match)."""
    problems: List[str] = []
    ledger_title = normalize(str(source.get("title", "")))
    arxiv_title = normalize(str(entry.get("title", "")))
    if ledger_title != arxiv_title:
        problems.append(f"title: ledger={ledger_title!r} arxiv={arxiv_title!r}")

    ledger_authors = [normalize(str(a)) for a in source.get("authors", [])]
    arxiv_authors = [normalize(str(a)) for a in entry.get("authors", [])]
    if ledger_authors != arxiv_authors:
        problems.append(
            f"authors ({len(ledger_authors)} vs {len(arxiv_authors)}): "
            f"ledger={ledger_authors!r} arxiv={arxiv_authors!r}"
        )

    published = str(entry.get("published", ""))
    if not published[:4].isdigit():
        problems.append(f"published date missing in arXiv entry: {entry!r}")
    else:
        arxiv_year = int(published[:4])
        ledger_year = source.get("year")
        if ledger_year != arxiv_year:
            problems.append(f"year: ledger={ledger_year!r} arxiv={arxiv_year!r}")
    return problems


def run_check(
    sources: List[Dict[str, Any]], entries: Dict[str, Dict[str, Any]]
) -> Tuple[int, int, List[str]]:
    """Compare every arXiv source against the entries.

    Returns (checked, skipped, report_lines). The report's last semantics:
    any line starting with 'MISMATCH' or 'MISSING' is a failure.
    """
    checked = 0
    skipped = 0
    report: List[str] = []
    for source in sources:
        source_id = source.get("source_id", "<no id>")
        arxiv_id = extract_arxiv_id(source)
        if arxiv_id is None:
            skipped += 1
            report.append(f"SKIP    {source_id} (no arXiv ID in url/doi)")
            continue
        checked += 1
        entry = entries.get(arxiv_id)
        if entry is None:
            report.append(f"MISSING {source_id} {arxiv_id} (not in metadata snapshot)")
            continue
        problems = compare(source, entry)
        if problems:
            for problem in problems:
                report.append(f"MISMATCH {source_id} {arxiv_id} {problem}")
        else:
            report.append(f"OK      {source_id} {arxiv_id} (title/authors/year match)")
    return checked, skipped, report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check state/sources.jsonl bibliography against arXiv metadata."
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
        "--sources",
        type=Path,
        default=DEFAULT_SOURCES,
        help=f"ledger JSONL to check (default: {DEFAULT_SOURCES})",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="print only failures and the summary"
    )
    args = parser.parse_args(argv)

    try:
        sources = load_ledger(args.sources)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.live:
        print(
            "WARNING: --live queries export.arxiv.org "
            "(network + arXiv rate limits). Manual use only; "
            "not a CI gate.",
            file=sys.stderr,
        )
        arxiv_ids = sorted(
            {arxiv_id for source in sources if (arxiv_id := extract_arxiv_id(source))}
        )
        try:
            entries = fetch_live(arxiv_ids)
        except Exception as exc:  # URLError/HTTPError/timeout/parse
            print(f"error: live fetch failed: {exc}", file=sys.stderr)
            return 2
        if arxiv_ids and not entries:
            # e.g. arXiv answered "Rate exceeded" instead of Atom entries.
            # That is an infrastructure problem, NOT a citation mismatch.
            print(
                "error: live fetch returned no entries "
                "(rate limited or empty response); not treating as mismatch",
                file=sys.stderr,
            )
            return 2
        header_note = f"live API: {LIVE_API}?id_list={','.join(arxiv_ids)}"
    else:
        try:
            entries, header = load_fixture(args.fixture)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"error: failed to load fixture: {exc}", file=sys.stderr)
            return 2
        header_note = (
            f"offline snapshot: {args.fixture} "
            f"(captured {header.get('captured_at', 'unknown')})"
        )

    checked, skipped, report = run_check(sources, entries)
    failures = [line for line in report if line.startswith(("MISMATCH", "MISSING"))]
    if not args.quiet:
        print(header_note)
    for line in report:
        if args.quiet and line.startswith("OK"):
            continue
        print(line)
    print(
        f"summary: {checked} arXiv source(s) checked, {skipped} skipped, "
        f"{len(failures)} failure(s)"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
