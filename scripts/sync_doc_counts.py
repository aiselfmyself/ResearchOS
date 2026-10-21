#!/usr/bin/env python3
"""Recompute the CURRENT-STATE numbers in the two documents that state them.

WHY THIS EXISTS
---------------
`scripts/check_doc_numbers.py` (gate 8) recomputes the numbers that describe
the repository's present state -- test count, CI gate count, per-file test
counts, ledger record counts -- and fails when a document disagrees.

That check is the reason the numbers cannot be dropped: a documented count is
a claim about `main` right now, and gate 8 is what keeps the claim true. The
cost is that any session that adds a test or appends a ledger record also has
to edit `README.md` and `docs/minimal-core-and-ci.md`. Those two files are
shared text: `docs/parallel-work-ownership.md` §2.2 already allows every
session to sync numbers there, but it is a manual edit.

During the 2026-10-21 sharding migration that manual edit collided with
`origin/main` **three times**, and every time the conflict was exactly the same
one-line number (`contributions/2026-10-21_ledger_sharding_migration.md` §4.3,
§4.4). Resolving it is mechanical -- recompute, replace -- so it should be a
command, not a judgement call. That is what this script is.

WHAT IT DOES
------------
It asks `check_doc_numbers` what is stale, rewrites **only the numbers on the
lines that checker flagged**, and then re-runs the checker. If anything is
still stale it says so and exits 1 rather than pretending to have fixed it.
Lines that were not flagged are not touched, so prose, ordering and whitespace
of the documents are preserved.

    python3 scripts/sync_doc_counts.py            # rewrite README + docs
    python3 scripts/sync_doc_counts.py --dry-run  # show the planned edits
    python3 scripts/sync_doc_counts.py --file README.md

WHAT IT DOES NOT DO
-------------------
It does not decide what the document should *say*, and does not bypass gate 8:
it uses the same detection code as the gate, so a number it writes is by
construction one the gate accepts. It also does not edit blockquotes or
`drift-ok` lines (the checker skips them, so they are never "stale" here).

Exit codes: 0 = documents agree with the repository after the run (or nothing
was stale), 1 = something is still stale afterwards, 2 = usage / I/O error.
Standard library only.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]

try:
    import check_doc_numbers as cdn
except ImportError:  # running as scripts/sync_doc_counts.py
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import check_doc_numbers as cdn

Change = Tuple[int, str, str]  # (line number, before, after)


def _sub_count(pattern: "re.Pattern[str]", text: str, found: int, expected: int) -> str:
    """Replace group 1 with `expected` wherever that number equals `found`.

    Matches are computed on the incoming text and applied in reverse order, so
    changing the width of a number cannot invalidate a later span.
    """
    spans = [
        match.span(1)
        for match in pattern.finditer(text)
        if cdn._to_int(match.group(1)) == found
    ]
    for start, end in reversed(spans):
        text = text[:start] + str(expected) + text[end:]
    return text


def _rewrite_total(line: str, found: int, expected: int) -> str:
    for pattern in (
        cdn.TOTAL_SUM_RE,
        cdn.PAREN_COUNT_RE,
        cdn.TESTS_WORD_RE,
        cdn.BARE_COUNT_RE,
    ):
        line = _sub_count(pattern, line, found, expected)
    return line


def _rewrite_per_file(line: str, fname: str, found: int, expected: int) -> str:
    mentions = [
        mention
        for mention in cdn.TEST_FILE_RE.finditer(line)
        if f"test_{mention.group(1)}.py" == fname
    ]
    for mention in reversed(mentions):
        lo = max(0, mention.start() - 40)
        hi = min(len(line), mention.end() + 120)
        window = line[lo:hi]
        for pattern in (cdn.PAREN_COUNT_RE, cdn.TESTS_WORD_RE):
            window = _sub_count(pattern, window, found, expected)
        line = line[:lo] + window + line[hi:]
    return line


def _rewrite_line(line: str, kinds: List[Dict[str, object]]) -> str:
    for finding in kinds:
        kind = str(finding["kind"])
        found = int(finding["found"])  # type: ignore[arg-type]
        expected = int(finding["expected"])  # type: ignore[arg-type]
        if kind == "total-tests":
            line = _rewrite_total(line, found, expected)
        elif kind.startswith("per-file-tests:"):
            line = _rewrite_per_file(line, kind.split(":", 1)[1], found, expected)
        elif kind == "gates":
            line = _sub_count(cdn.GATE_RE, line, found, expected)
        elif kind.startswith("ledger:"):
            name = kind.split(":", 1)[1]
            line = re.sub(
                rf"\b{re.escape(name)}\s*=\s*{found}(?!\d)",
                f"{name}={expected}",
                line,
            )
        else:  # unknown kind: leave it for the re-check to report
            continue
    return line


def fix_file(
    path: Path,
    total: int,
    per_file: Dict[str, int],
    gates: int,
    ledgers: Dict[str, int],
    dry_run: bool = False,
) -> List[Change]:
    """Rewrite the stale numbers in one file. Return the applied changes."""
    findings = cdn.scan_file(path, total, per_file, gates, ledgers)
    if not findings:
        return []
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    by_line: Dict[int, List[Dict[str, object]]] = {}
    for finding in findings:
        by_line.setdefault(int(finding["line"]), []).append(finding)

    changes: List[Change] = []
    for lineno, kinds in sorted(by_line.items()):
        index = lineno - 1
        before = lines[index]
        after = _rewrite_line(before, kinds)
        if after != before:
            lines[index] = after
            changes.append((lineno, before.rstrip("\n"), after.rstrip("\n")))
    if changes and not dry_run:
        path.write_text("".join(lines), encoding="utf-8")
    return changes


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--file", action="append", default=None,
        help=f"doc to fix (repeatable; default: {', '.join(cdn.TARGETS)})",
    )
    parser.add_argument("--dry-run", action="store_true", help="show the edits, write nothing")
    args = parser.parse_args(argv)

    paths = args.file if args.file else list(cdn.TARGETS)
    total, per_file = cdn.actual_test_counts()
    gates = cdn.actual_gate_count()
    ledgers = cdn.actual_ledger_counts()

    applied = 0
    for rel in paths:
        path = ROOT / rel
        if not path.exists():
            print(f"error: no such doc: {rel}", file=sys.stderr)
            return 2
        try:
            changes = fix_file(path, total, per_file, gates, ledgers, dry_run=args.dry_run)
        except OSError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        for lineno, before, after in changes:
            print(f"{'would fix' if args.dry_run else 'fixed'} {rel}:{lineno}")
            print(f"  - {before.strip()[:160]}")
            print(f"  + {after.strip()[:160]}")
        applied += len(changes)

    if args.dry_run:
        print(f"dry run: {applied} number(s) would change")
        return 0

    report = cdn.scan(paths)
    if report["findings"]:
        print("still stale after the rewrite (not fixed automatically):")
        for finding in report["findings"]:
            print(
                f"  {finding['file']}:{finding['line']} [{finding['kind']}] "
                f"found {finding['found']}, expected {finding['expected']}"
            )
        return 1

    print(f"synced: {applied} number(s) changed, 0 stale number(s) remaining")
    return 0


if __name__ == "__main__":
    sys.exit(main())
