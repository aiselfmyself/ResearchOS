#!/usr/bin/env python3
"""
GitSwarm Readout & Contribution Graph Analyzer
Instantiates deterministic plurality readout and compounding inference metrics
as described in GitSwarm (Shah et al., arXiv:2610.04862).
"""
import re
import subprocess
import json
import sys

def get_git_commits():
    # Extract commit SHA, parent, author, subject, body
    fmt = "%H%x1f%P%x1f%an%x1f%s%x1f%b%x1e"
    raw = subprocess.check_output(["git", "log", f"--format={fmt}"], text=True)
    entries = raw.strip().split("\x1e")
    commits = []
    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split("\x1f")
        if len(parts) >= 4:
            sha = parts[0]
            parents = parts[1].split() if parts[1] else []
            author = parts[2]
            subject = parts[3]
            body = parts[4] if len(parts) > 4 else ""
            commits.append({
                "sha": sha,
                "parents": parents,
                "author": author,
                "subject": subject,
                "body": body
            })
    return commits

def parse_gitswarm_metadata(commit):
    body = commit["body"]
    subject = commit["subject"]
    
    # Parse Worker ID
    worker_match = re.search(r"\[(Worker-[^\]]+)\]", subject)
    worker_id = worker_match.group(1) if worker_match else None
    
    # Parse Action Type
    action_match = re.search(r"Action-Type:\s*([a-zA-Z0-9_\-]+)", body, re.IGNORECASE)
    action_type = action_match.group(1).lower() if action_match else None
    if not action_type and worker_id:
        # fallback to subject keyword
        for act in ["explore", "experiment", "verify", "refine", "synthesize", "nominate"]:
            if act in subject.lower():
                action_type = act
                break
                
    # Parse Informed-By
    informed_match = re.search(r"Informed-By:\s*([^\n]+)", body, re.IGNORECASE)
    informed_by = []
    if informed_match:
        for ref in informed_match.group(1).split(","):
            ref = ref.strip()
            if ref and ref.lower() != "none" and ref.lower() != "root":
                informed_by.append(ref)
                
    # Parse Outcome
    outcome_match = re.search(r"Outcome:\s*([a-zA-Z0-9_\-]+)", body, re.IGNORECASE)
    outcome = outcome_match.group(1).lower() if outcome_match else None
    
    # Parse Metric
    metric_match = re.search(r"Metric:\s*([^\n]+)", body, re.IGNORECASE)
    metric = metric_match.group(1).strip() if metric_match else None

    # Parse Nomination
    nomination_match = re.search(r"Nomination:\s*([a-zA-Z0-9]+)", body, re.IGNORECASE)
    nomination = nomination_match.group(1).strip() if nomination_match else None

    return {
        "worker_id": worker_id,
        "action_type": action_type,
        "informed_by": informed_by,
        "outcome": outcome,
        "metric": metric,
        "nomination": nomination
    }

def analyze_gitswarm():
    all_commits = get_git_commits()
    swarm_commits = []
    
    for c in all_commits:
        meta = parse_gitswarm_metadata(c)
        if meta["worker_id"]:
            c["meta"] = meta
            swarm_commits.append(c)
            
    # Chronological order
    swarm_commits.reverse()
    
    if not swarm_commits:
        print("No GitSwarm worker commits found.")
        return None
        
    print(f"Loaded {len(swarm_commits)} GitSwarm worker commits.")
    
    # 1. Resolve short SHAs to full SHAs
    full_sha_map = {c["sha"][:7]: c["sha"] for c in swarm_commits}
    full_sha_map.update({c["sha"]: c["sha"] for c in swarm_commits})
    
    # 2. Build Dependency Graph (Physical parents + Informed-By semantic edges)
    dependencies = {} # sha -> set of cited shas
    dependents = {c["sha"]: set() for c in swarm_commits} # sha -> set of citing shas
    
    for c in swarm_commits:
        sha = c["sha"]
        deps = set()
        # physical parents within swarm
        for p in c["parents"]:
            if p in dependents:
                deps.add(p)
        # semantic informed_by
        for ref in c["meta"]["informed_by"]:
            resolved = full_sha_map.get(ref[:7], full_sha_map.get(ref))
            if resolved and resolved in dependents:
                deps.add(resolved)
        dependencies[sha] = deps
        for d in deps:
            dependents[d].add(sha)
            
    # 3. Analyze Nominations and Plurality Readout
    votes = {}
    nominations = []
    for c in swarm_commits:
        nom = c["meta"]["nomination"]
        if nom:
            target_sha = full_sha_map.get(nom[:7], full_sha_map.get(nom))
            if target_sha:
                votes[target_sha] = votes.get(target_sha, 0) + 1
                nominations.append({
                    "nominator": c["meta"]["worker_id"],
                    "nominator_sha": c["sha"][:7],
                    "target_sha": target_sha[:7],
                    "vote_commit": c["subject"]
                })
                
    # Deterministic winner selection: highest votes, tie-break by lexicographic full SHA
    winning_sha = None
    if votes:
        sorted_candidates = sorted(votes.keys(), key=lambda s: (-votes[s], s))
        winning_sha = sorted_candidates[0]
        
    # 4. Compounding Metrics
    total_non_nomination = [c for c in swarm_commits if c["meta"]["action_type"] != "nominate"]
    reused_commits = [c for c in total_non_nomination if len(dependents[c["sha"]]) > 0]
    reuse_rate = (len(reused_commits) / len(total_non_nomination) * 100) if total_non_nomination else 0.0
    
    # Negative result reuse rate
    negative_commits = [c for c in total_non_nomination if c["meta"]["outcome"] == "negative"]
    reused_negative = [c for c in negative_commits if len(dependents[c["sha"]]) > 0]
    negative_reuse_rate = (len(reused_negative) / len(negative_commits) * 100) if negative_commits else 0.0
    
    # Transitive Ancestry Coverage of the Winner
    transitive_ancestors = set()
    if winning_sha:
        queue = [winning_sha]
        visited = set()
        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)
            transitive_ancestors.add(curr)
            for parent_dep in dependencies.get(curr, []):
                if parent_dep not in visited:
                    queue.append(parent_dep)
                    
    ancestry_coverage = (len(transitive_ancestors) / len(total_non_nomination) * 100) if total_non_nomination else 0.0
    
    result = {
        "total_worker_commits": len(swarm_commits),
        "candidate_commits": len(total_non_nomination),
        "nomination_votes": nominations,
        "vote_tallies": {s[:7]: v for s, v in votes.items()},
        "winning_candidate_sha": winning_sha[:7] if winning_sha else None,
        "winning_candidate_full_sha": winning_sha,
        "compounding_metrics": {
            "contribution_reuse_rate_pct": round(reuse_rate, 1),
            "negative_results_total": len(negative_commits),
            "negative_results_reused": len(reused_negative),
            "negative_reuse_rate_pct": round(negative_reuse_rate, 1),
            "winner_ancestry_coverage_pct": round(ancestry_coverage, 1)
        }
    }
    
    print("\n" + "="*50)
    print(" GITSWARM READOUT RESULTS ")
    print("="*50)
    print(f"Total Swarm Contributions: {result['total_worker_commits']}")
    print(f"Candidate Solutions: {result['candidate_commits']}")
    print(f"Vote Tallies: {result['vote_tallies']}")
    print(f"Deterministic Winner: {result['winning_candidate_sha']}")
    print("\n[Compounding Inference Metrics]")
    print(f"- Contribution Reuse Rate: {reuse_rate:.1f}% ({len(reused_commits)}/{len(total_non_nomination)})")
    if negative_commits:
        print(f"- Negative Result Citation Rate: {negative_reuse_rate:.1f}% ({len(reused_negative)}/{len(negative_commits)})")
    print(f"- Winner Ancestry Coverage: {ancestry_coverage:.1f}% ({len(transitive_ancestors)}/{len(total_non_nomination)})")
    print("="*50 + "\n")
    
    return result

if __name__ == "__main__":
    analyze_gitswarm()
