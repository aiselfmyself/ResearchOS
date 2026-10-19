#!/usr/bin/env python3
"""
GitSwarm Readout & Contribution Graph Analyzer.

Implements deterministic plurality readout and compounding-inference metrics as
described in GitSwarm (Shah et al., arXiv:2610.04862).

Important: the original version scanned the *entire* repository history.  Once
the ResearchOS role-play commits ``[Worker-01]`` / ``[Worker-02]`` were added to
``state/``, they were silently counted as GitSwarm workers and the reported
metrics changed (100% -> 85.7%, 80% -> 57.1%).  The readout is now path-scoped
by default (``gitswarm/``), and the scope is recorded in the output.

Usage:
    python3 gitswarm/readout.py                     # scoped to gitswarm/
    python3 gitswarm/readout.py --all-paths         # legacy whole-repo scope
    python3 gitswarm/readout.py --format json --output gitswarm/artifacts/readout_snapshot.json
    python3 gitswarm/readout.py --since 2026-10-01
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = "gitswarm"
ACTIONS = ["explore", "experiment", "verify", "refine", "synthesize", "nominate"]


def get_git_commits(
    paths: Optional[Iterable[str]] = None,
    since: Optional[str] = None,
    cwd: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Return commits, optionally limited to the given paths and date."""
    fmt = "%H%x1f%P%x1f%an%x1f%s%x1f%b%x1e"
    cmd = ["git", "log", f"--format={fmt}"]
    if since:
        cmd.append(f"--since={since}")
    if paths:
        cmd.append("--")
        cmd.extend(paths)

    raw = subprocess.check_output(cmd, cwd=cwd or ROOT, text=True)
    commits: List[Dict[str, Any]] = []
    for entry in raw.strip().split("\x1e"):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split("\x1f", 4)
        if len(parts) < 4:
            continue
        commits.append(
            {
                "sha": parts[0],
                "parents": parts[1].split() if parts[1] else [],
                "author": parts[2],
                "subject": parts[3],
                "body": parts[4] if len(parts) > 4 else "",
            }
        )
    return commits


def parse_gitswarm_metadata(commit: Dict[str, Any]) -> Dict[str, Any]:
    body = commit["body"]
    subject = commit["subject"]

    worker_match = re.match(r"^\[(Worker-[^\]]+)\]", subject)
    worker_id = worker_match.group(1) if worker_match else None

    action_match = re.search(
        r"Action-Type:\s*([a-zA-Z0-9_\-]+)", body, re.IGNORECASE
    )
    action_type = action_match.group(1).lower() if action_match else None
    if not action_type and worker_id:
        lowered = subject.lower()
        for action in ACTIONS:
            if action in lowered:
                action_type = action
                break

    informed_match = re.search(r"Informed-By:\s*([^\n]+)", body, re.IGNORECASE)
    informed_by: List[str] = []
    if informed_match:
        for ref in informed_match.group(1).split(","):
            ref = ref.strip().strip("`")
            if ref and ref.lower() not in ("none", "root"):
                informed_by.append(ref)

    outcome_match = re.search(r"Outcome:\s*([a-zA-Z0-9_\-]+)", body, re.IGNORECASE)
    outcome = outcome_match.group(1).lower() if outcome_match else None

    metric_match = re.search(r"Metric:\s*([^\n]+)", body, re.IGNORECASE)
    metric = metric_match.group(1).strip() if metric_match else None

    nomination_match = re.search(
        r"Nomination:\s*([a-zA-Z0-9]+)", body, re.IGNORECASE
    )
    nomination = nomination_match.group(1).strip() if nomination_match else None

    return {
        "worker_id": worker_id,
        "action_type": action_type,
        "informed_by": informed_by,
        "outcome": outcome,
        "metric": metric,
        "nomination": nomination,
    }


def analyze_gitswarm(
    paths: Optional[Iterable[str]] = None,
    since: Optional[str] = None,
    cwd: Optional[Path] = None,
    verbose: bool = False,
) -> Optional[Dict[str, Any]]:
    """Analyze the GitSwarm contribution graph. Returns None if no workers."""
    paths = list(paths) if paths else []
    all_commits = get_git_commits(paths=paths, since=since, cwd=cwd)

    swarm_commits: List[Dict[str, Any]] = []
    for commit in all_commits:
        meta = parse_gitswarm_metadata(commit)
        if meta["worker_id"]:
            commit = dict(commit)
            commit["meta"] = meta
            swarm_commits.append(commit)

    swarm_commits.reverse()  # chronological

    if not swarm_commits:
        if verbose:
            print("No GitSwarm worker commits found in the selected scope.")
        return None

    if verbose:
        print(f"Loaded {len(swarm_commits)} GitSwarm worker commits.")

    full_sha_map: Dict[str, str] = {}
    for commit in swarm_commits:
        full_sha_map[commit["sha"]] = commit["sha"]
        full_sha_map[commit["sha"][:7]] = commit["sha"]

    # Physical parents + semantic Informed-By edges
    dependencies: Dict[str, set] = {}
    dependents: Dict[str, set] = {commit["sha"]: set() for commit in swarm_commits}
    for commit in swarm_commits:
        sha = commit["sha"]
        deps = set()
        for parent in commit["parents"]:
            if parent in dependents:
                deps.add(parent)
        for ref in commit["meta"]["informed_by"]:
            resolved = full_sha_map.get(ref[:7], full_sha_map.get(ref))
            if resolved and resolved in dependents:
                deps.add(resolved)
        dependencies[sha] = deps
        for dep in deps:
            dependents[dep].add(sha)

    candidate_shas = {
        commit["sha"]
        for commit in swarm_commits
        if commit["meta"]["action_type"] != "nominate"
    }

    # Nominations and plurality readout
    votes: Dict[str, int] = {}
    nominations: List[Dict[str, Any]] = []
    invalid_nominations: List[Dict[str, Any]] = []
    for commit in swarm_commits:
        nomination = commit["meta"]["nomination"]
        if not nomination:
            continue
        target_sha = full_sha_map.get(nomination[:7], full_sha_map.get(nomination))
        if target_sha and target_sha in candidate_shas:
            votes[target_sha] = votes.get(target_sha, 0) + 1
            nominations.append(
                {
                    "nominator": commit["meta"]["worker_id"],
                    "nominator_sha": commit["sha"][:7],
                    "target_sha": target_sha[:7],
                    "vote_commit": commit["subject"],
                }
            )
        else:
            invalid_nominations.append(
                {
                    "nominator": commit["meta"]["worker_id"],
                    "nominator_sha": commit["sha"][:7],
                    "target": nomination,
                    "reason": "target is not a candidate commit",
                }
            )

    winning_sha: Optional[str] = None
    if votes:
        winning_sha = sorted(votes, key=lambda sha: (-votes[sha], sha))[0]

    # Compounding metrics
    non_nomination = [
        commit
        for commit in swarm_commits
        if commit["meta"]["action_type"] != "nominate"
    ]
    reused = [
        commit for commit in non_nomination if len(dependents[commit["sha"]]) > 0
    ]
    reuse_rate = len(reused) / len(non_nomination) * 100 if non_nomination else 0.0

    negative = [
        commit
        for commit in non_nomination
        if commit["meta"]["outcome"] == "negative"
    ]
    reused_negative = [
        commit for commit in negative if len(dependents[commit["sha"]]) > 0
    ]
    negative_reuse_rate = (
        len(reused_negative) / len(negative) * 100 if negative else 0.0
    )

    transitive_ancestors: set = set()
    if winning_sha:
        queue = [winning_sha]
        visited: set = set()
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            if current in candidate_shas:
                transitive_ancestors.add(current)
            for dep in dependencies.get(current, set()):
                if dep not in visited:
                    queue.append(dep)

    ancestry_coverage = (
        len(transitive_ancestors) / len(candidate_shas) * 100 if candidate_shas else 0.0
    )

    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": {
            "paths": paths if paths else "ALL",
            "since": since,
            "commits_scanned": len(all_commits),
        },
        "total_worker_commits": len(swarm_commits),
        "candidate_commits": len(candidate_shas),
        "nomination_votes": nominations,
        "invalid_nominations": invalid_nominations,
        "vote_tallies": {sha[:7]: count for sha, count in votes.items()},
        "winning_candidate_sha": winning_sha[:7] if winning_sha else None,
        "winning_candidate_full_sha": winning_sha,
        "compounding_metrics": {
            "contribution_reuse_rate_pct": round(reuse_rate, 1),
            "negative_results_total": len(negative),
            "negative_results_reused": len(reused_negative),
            "negative_reuse_rate_pct": round(negative_reuse_rate, 1),
            "winner_ancestry_coverage_pct": round(ancestry_coverage, 1),
        },
        "reused_commits": sorted(commit["sha"][:7] for commit in reused),
        "unreused_commits": sorted(
            commit["sha"][:7] for commit in non_nomination if commit not in reused
        ),
    }
    return result


def _print_text(result: Dict[str, Any]) -> None:
    print("\n" + "=" * 50)
    print(" GITSWARM READOUT RESULTS ")
    print("=" * 50)
    scope = result["scope"]
    print(f"Scope: paths={scope['paths']} since={scope['since']}")
    print(f"Commits scanned: {scope['commits_scanned']}")
    print(f"Total Swarm Contributions: {result['total_worker_commits']}")
    print(f"Candidate Solutions: {result['candidate_commits']}")
    print(f"Vote Tallies: {result['vote_tallies']}")
    print(f"Deterministic Winner: {result['winning_candidate_sha']}")
    if result["invalid_nominations"]:
        print(f"Invalid nominations: {len(result['invalid_nominations'])}")
    metrics = result["compounding_metrics"]
    print("\n[Compounding Inference Metrics]")
    print(
        f"- Contribution Reuse Rate: {metrics['contribution_reuse_rate_pct']}% "
        f"({len(result['reused_commits'])}/{result['candidate_commits']})"
    )
    print(
        f"- Negative Result Citation Rate: {metrics['negative_reuse_rate_pct']}% "
        f"({metrics['negative_results_reused']}/{metrics['negative_results_total']})"
    )
    print(
        f"- Winner Ancestry Coverage: {metrics['winner_ancestry_coverage_pct']}%"
    )
    print("=" * 50 + "\n")


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="GitSwarm readout analyzer")
    parser.add_argument(
        "--path",
        action="append",
        default=None,
        help="limit history to a path (repeatable; default: gitswarm)",
    )
    parser.add_argument(
        "--all-paths",
        action="store_true",
        help="scan the whole repository (legacy behaviour; can mix in unrelated workers)",
    )
    parser.add_argument("--since", default=None, help="git --since date filter")
    parser.add_argument(
        "--format", choices=["text", "json"], default="text", help="stdout format"
    )
    parser.add_argument("--output", default=None, help="write JSON to this path")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    paths = [] if args.all_paths else (args.path or [DEFAULT_PATH])
    result = analyze_gitswarm(
        paths=paths, since=args.since, verbose=not args.quiet
    )
    if result is None:
        return 1

    if args.format == "json" or args.output:
        payload = json.dumps(result, indent=2, ensure_ascii=False)
        if args.format == "json":
            print(payload)
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(payload + "\n", encoding="utf-8")
            if not args.quiet:
                print(f"wrote {output}")
    else:
        _print_text(result)

    return 0


if __name__ == "__main__":
    sys.exit(main())
