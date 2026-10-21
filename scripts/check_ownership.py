#!/usr/bin/env python3
"""Classify changed paths against the parallel-work ownership map.

This implements docs/parallel-work-ownership.md, but ONLY as advice. It is
not a gate:

  * it is NOT wired into .github/workflows/core-check.yml;
  * it never fails a build on its own (default exit code is 0);
  * it does not read git authors, roles, trailers or history;
  * it does not rewrite, lock or protect anything.

The map itself is a short table (docs/parallel-work-ownership.md 2). One
integrator session owns ``README.md``, ``docs/minimal-core-and-ci.md`` and
``gitswarm/artifacts/``. Since 2026-10-21 ``state/`` is NOT integrator-owned:
any session may append ledger records and mint IDs without waiting for a human.
Deleting or rewriting an existing record still needs explicit human approval
(docs/autonomous-merge-policy-2026-10-21.md 1). Every session writes only its
own file under ``contributions/``. Everything else is UNSPECIFIED -- the
convention simply says nothing about it -- and the script reports it that way
instead of inventing a rule.

Because the tool can only see a path list, "my own file" has to be given
explicitly: pass ``--session-file contributions/<my-note>.md`` and any other
``contributions/`` path is reported as OTHER_SESSION_CONTRIBUTION.

Usage:
    python3 scripts/check_ownership.py README.md state/claims.jsonl
    git diff --name-only main | python3 scripts/check_ownership.py
    python3 scripts/check_ownership.py --git-diff origin/main
    python3 scripts/check_ownership.py --selftest          # offline fixture
    python3 scripts/check_ownership.py --selftest --strict # manual only

Exit codes: 0 = report produced (advisory), 1 = --strict found a conflict,
2 = usage / I/O error. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "ownership_cases.json"

# Classification values (kept as plain strings so the JSON output is readable).
INTEGRATOR_ONLY = "INTEGRATOR_ONLY"
ANY_SESSION_APPEND = "ANY_SESSION_APPEND"
SESSION_CONTRIBUTION = "SESSION_CONTRIBUTION"
OTHER_SESSION_CONTRIBUTION = "OTHER_SESSION_CONTRIBUTION"
UNSPECIFIED = "UNSPECIFIED"

FILE = "file"
DIR = "dir"

# The map. Order matters: the first matching rule wins, so a narrower file
# rule must come before a broader directory rule.
RULES: Sequence[tuple] = (
    ("README.md", FILE, INTEGRATOR_ONLY),
    ("docs/minimal-core-and-ci.md", FILE, INTEGRATOR_ONLY),
    # 2026-10-21: ledger appends and ID minting were opened up to every
    # session. Deletion and rewriting of existing records remain human-gated.
    ("state/", DIR, ANY_SESSION_APPEND),
    ("gitswarm/artifacts/", DIR, INTEGRATOR_ONLY),
    ("contributions/", DIR, SESSION_CONTRIBUTION),
)

# Classes that --strict reports as a conflict. --strict is a manual convenience
# for the integrator; nothing in CI or in the hooks calls it.
# ANY_SESSION_APPEND is deliberately absent: appending to state/ is allowed for
# every session, so it is not a conflict.
CONFLICTING = (INTEGRATOR_ONLY, OTHER_SESSION_CONTRIBUTION)


def normalize(path: str) -> str:
    """Return a repository-relative POSIX path.

    Raises ValueError for absolute paths and for paths that climb out of the
    repository, so a typo cannot silently be classified as something it is not.
    """
    raw = path.strip().replace("\\", "/")
    if not raw:
        raise ValueError("empty path")
    if raw.startswith("/"):
        raise ValueError(f"absolute path is not repository-relative: {path!r}")
    parts: List[str] = []
    for part in PurePosixPath(raw).parts:
        if part in ("", "."):
            continue
        if part == "..":
            raise ValueError(f"path escapes the repository root: {path!r}")
        parts.append(part)
    if not parts:
        raise ValueError(f"not a usable path: {path!r}")
    return "/".join(parts)


def classify(path: str, session_file: Optional[str] = None) -> str:
    """Return the ownership class of one repository-relative path."""
    norm = normalize(path)
    own = normalize(session_file) if session_file else None
    for pattern, kind, cls in RULES:
        if kind == FILE:
            matched = norm == pattern
        else:
            # "state/" matches state/claims.jsonl and also the directory
            # itself when it is written as "state" or "state/".
            matched = norm.startswith(pattern) or norm == pattern.rstrip("/")
        if not matched:
            continue
        if cls == SESSION_CONTRIBUTION and own is not None and norm != own:
            return OTHER_SESSION_CONTRIBUTION
        return cls
    return UNSPECIFIED


def classify_many(
    paths: Iterable[str], session_file: Optional[str] = None
) -> Dict[str, str]:
    """Classify several paths, de-duplicated, preserving first-seen order."""
    result: Dict[str, str] = {}
    for path in paths:
        norm = normalize(path)
        if norm in result:
            continue
        result[norm] = classify(norm, session_file=session_file)
    return result


def load_cases(fixture: Path = FIXTURE) -> dict:
    """Load the offline case fixture (tests/fixtures/ownership_cases.json)."""
    data = json.loads(fixture.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("cases"), list):
        raise ValueError(f"{fixture}: expected an object with a 'cases' list")
    return data


def run_selftest(fixture: Path = FIXTURE) -> int:
    """Re-run the bundled cases offline. 0 = all cases behave as recorded."""
    try:
        data = load_cases(fixture)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"selftest: cannot load {fixture}: {exc}", file=sys.stderr)
        return 2

    failures = 0
    cases = data["cases"]
    for index, case in enumerate(cases, start=1):
        name = case.get("name") or f"case {index}"
        session_file = case.get("session_file")
        expected = case.get("expect") or {}
        try:
            actual = classify_many(case.get("paths") or [], session_file=session_file)
        except ValueError as exc:
            print(f"FAIL {name}: unexpected error: {exc}")
            failures += 1
            continue
        if actual != expected:
            print(f"FAIL {name}: expected {expected}, got {actual}")
            failures += 1
        else:
            print(f"ok   {name}")

    print(f"\nselftest: {len(cases) - failures}/{len(cases)} cases passed")
    return 0 if failures == 0 else 1


def _read_stdin() -> List[str]:
    return [line for line in sys.stdin.read().splitlines() if line.strip()]


def _read_git_diff(rev: str) -> List[str]:
    proc = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=d", rev],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git diff failed for {rev!r}")
    return [line for line in proc.stdout.splitlines() if line.strip()]


def report(classes: Dict[str, str], as_json: bool, quiet: bool) -> None:
    if as_json:
        print(json.dumps({"schema": "ownership-report-v1", "paths": classes}, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if not quiet:
        for path, cls in classes.items():
            print(f"{cls:<28} {path}")
        counts: Dict[str, int] = {}
        for cls in classes.values():
            counts[cls] = counts.get(cls, 0) + 1
        summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "no paths"
        print(f"\n{len(classes)} path(s): {summary}")
        print(
            "advisory only: CI does not run this script and nothing is blocked "
            "(docs/parallel-work-ownership.md)"
        )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Classify paths against the (non-enforcing) ownership map"
    )
    parser.add_argument("paths", nargs="*", help="repository-relative paths")
    parser.add_argument(
        "--session-file",
        default=None,
        help="your own contributions/ file, e.g. contributions/2026-10-20_x.md",
    )
    parser.add_argument(
        "--git-diff",
        metavar="REV",
        default=None,
        help="take paths from 'git diff --name-only REV' (local git, no network)",
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="re-run tests/fixtures/ownership_cases.json offline and exit",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--quiet", action="store_true", help="no human-readable report")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="manual convenience: exit 1 when a conflicting class is present",
    )
    args = parser.parse_args(argv)

    if args.selftest:
        return run_selftest()

    paths = list(args.paths)
    try:
        if args.git_diff:
            paths.extend(_read_git_diff(args.git_diff))
        if not paths and not sys.stdin.isatty():
            paths.extend(_read_stdin())
        if not paths:
            parser.error("give paths, --git-diff REV, or pipe paths on stdin")
        classes = classify_many(paths, session_file=args.session_file)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (OSError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    report(classes, as_json=args.json, quiet=args.quiet)

    if args.strict:
        conflicts = [p for p, c in classes.items() if c in CONFLICTING]
        if conflicts:
            if not args.json:
                for path in conflicts:
                    print(f"conflict: {path} is not yours to write", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
