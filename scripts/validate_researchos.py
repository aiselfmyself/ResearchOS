#!/usr/bin/env python3
"""
ResearchOS Deterministic Core Validator (hardened)

This validator is intentionally dependency-free (stdlib only) so that it can run
in a bare GitHub Actions runner.  It performs four classes of checks:

1. Schema validation (a practical subset of JSON Schema draft-07):
   type, enum, required, properties, additionalProperties, items,
   minItems/maxItems, minimum/maximum, and pattern.
2. Global ID uniqueness across every state file.
3. Referential integrity:
   evidence -> source, claim -> evidence/counterclaim, verification -> target,
   hypothesis -> evidence.
4. Git provenance: every `Informed-By:` trailer must resolve to a real commit
   that is an *ancestor* of the citing commit (not merely present in `git log`).

Exit code is 0 only when there are no errors.  Warnings are reported but do not
fail the build.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple

# --------------------------------------------------------------------------
# Loading helpers
# --------------------------------------------------------------------------


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    if not os.path.exists(path):
        return records
    with open(path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{idx}: {exc}") from exc
    return records


# --------------------------------------------------------------------------
# 1. Minimal JSON-Schema validator
# --------------------------------------------------------------------------


def _is_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def validate_node(value: Any, schema: Dict[str, Any], path: str) -> List[str]:
    """Recursively validate `value` against a JSON-Schema subset."""
    errors: List[str] = []

    expected = schema.get("type")
    if expected is not None:
        expected_types = expected if isinstance(expected, list) else [expected]
        if not any(_is_type(value, t) for t in expected_types):
            errors.append(
                f"{path}: expected type {expected_types}, got {type(value).__name__}"
            )
            return errors  # further checks are meaningless

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value {value!r} is not one of {schema['enum']}")

    if isinstance(value, dict):
        for req in schema.get("required", []):
            if req not in value:
                errors.append(f"{path}: missing required field '{req}'")

        props = schema.get("properties", {})
        for key, child in value.items():
            if key in props:
                errors.extend(validate_node(child, props[key], f"{path}.{key}"))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: unexpected additional property '{key}'")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: expected at least {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: expected at most {schema['maxItems']} items")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for idx, item in enumerate(value):
                errors.extend(validate_node(item, item_schema, f"{path}[{idx}]"))

    if isinstance(value, str) and "pattern" in schema:
        if re.search(schema["pattern"], value) is None:
            errors.append(
                f"{path}: string {value!r} does not match pattern {schema['pattern']!r}"
            )

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} is below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value} is above maximum {schema['maximum']}")

    return errors


def validate_record(
    record: Dict[str, Any], schema: Dict[str, Any], schema_name: str
) -> List[str]:
    """Validate one record and prefix every error with the schema name."""
    return [
        f"{schema_name}: {err}" for err in validate_node(record, schema, schema_name)
    ]


# --------------------------------------------------------------------------
# 2. ID uniqueness
# --------------------------------------------------------------------------


def validate_unique_ids(
    collections: Dict[str, Tuple[List[Dict[str, Any]], str]]
) -> List[str]:
    errors: List[str] = []
    seen: Dict[str, str] = {}
    for label, (records, key) in collections.items():
        for idx, record in enumerate(records, 1):
            rid = record.get(key)
            if not isinstance(rid, str) or not rid:
                errors.append(f"{label} record #{idx}: missing or invalid '{key}'")
                continue
            if rid in seen:
                errors.append(
                    f"duplicate id '{rid}' in {label} (already defined in {seen[rid]})"
                )
            else:
                seen[rid] = label
    return errors


# --------------------------------------------------------------------------
# 3. Referential integrity
# --------------------------------------------------------------------------


def validate_referential_integrity(
    sources: List[Dict[str, Any]],
    evidence: List[Dict[str, Any]],
    claims: List[Dict[str, Any]],
    verifications: List[Dict[str, Any]],
    hypotheses: Optional[List[Dict[str, Any]]] = None,
) -> List[str]:
    hypotheses = hypotheses or []
    source_ids = {s["source_id"] for s in sources}
    evidence_ids = {e["evidence_id"] for e in evidence}
    claim_ids = {c["claim_id"] for c in claims}
    hypothesis_ids = {h["hypothesis_id"] for h in hypotheses}
    all_targets = source_ids | evidence_ids | claim_ids | hypothesis_ids

    errors: List[str] = []

    # evidence -> source
    for e in evidence:
        if e.get("source_id") not in source_ids:
            errors.append(
                f"Evidence '{e.get('evidence_id')}' references non-existent source "
                f"'{e.get('source_id')}'"
            )

    # claim -> evidence / counterclaim
    for c in claims:
        for eid in c.get("evidence_ids", []):
            if eid not in evidence_ids:
                errors.append(
                    f"Claim '{c.get('claim_id')}' references non-existent evidence '{eid}'"
                )
        for cid in c.get("counterclaim_ids", []):
            if cid not in claim_ids:
                errors.append(
                    f"Claim '{c.get('claim_id')}' references non-existent counterclaim '{cid}'"
                )
            if cid == c.get("claim_id"):
                errors.append(
                    f"Claim '{c.get('claim_id')}' lists itself as a counterclaim"
                )

    # hypothesis -> evidence
    for h in hypotheses:
        for eid in h.get("evidence_ids", []):
            if eid not in evidence_ids:
                errors.append(
                    f"Hypothesis '{h.get('hypothesis_id')}' references non-existent "
                    f"evidence '{eid}'"
                )

    # verification -> target
    for v in verifications:
        if v.get("target_id") not in all_targets:
            errors.append(
                f"Verification '{v.get('verification_id')}' references non-existent "
                f"target '{v.get('target_id')}'"
            )

    return errors


# --------------------------------------------------------------------------
# 4. Git provenance (existence + ancestry)
# --------------------------------------------------------------------------


def _git(args: List[str], cwd: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=cwd, text=True, stderr=subprocess.DEVNULL
    ).strip()


def _resolve_commit(ref: str, cwd: str) -> Optional[str]:
    try:
        return _git(["rev-parse", "--verify", f"{ref}^{{commit}}"], cwd)
    except subprocess.CalledProcessError:
        return None


def _is_ancestor(ancestor: str, descendant: str, cwd: str) -> bool:
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.returncode == 0


def validate_git_provenance(root: str = ".") -> List[str]:
    """Check that every Informed-By trailer is a real ancestor of its commit."""
    try:
        raw_log = _git(["log", "--format=%H%x1f%P%x1f%s%x1f%b%x1e"], root)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        return [f"Unable to read git history: {exc}"]

    entries = [e for e in raw_log.split("\x1e") if e.strip()]
    if not entries:
        return ["Git history is empty; cannot verify provenance"]

    commits: Dict[str, Dict[str, Any]] = {}
    for entry in entries:
        parts = entry.strip().split("\x1f", 3)
        sha = parts[0]
        commits[sha] = {
            "parents": parts[1].split() if len(parts) > 1 and parts[1] else [],
            "subject": parts[2] if len(parts) > 2 else "",
            "body": parts[3] if len(parts) > 3 else "",
        }

    errors: List[str] = []
    for sha, commit in commits.items():
        for line in commit["body"].splitlines():
            match = re.match(r"(?i)^informed-by:\s*(.+)$", line.strip())
            if not match:
                continue
            for ref in match.group(1).split(","):
                ref = ref.strip().strip("`")
                if not ref or ref.lower() in ("none", "root"):
                    continue
                if not re.fullmatch(r"[0-9a-fA-F]{4,40}", ref):
                    errors.append(
                        f"Commit {sha[:7]} has malformed Informed-By reference '{ref}'"
                    )
                    continue
                resolved = _resolve_commit(ref, root)
                if resolved is None:
                    errors.append(
                        f"Commit {sha[:7]} cites non-existent Informed-By SHA: '{ref}'"
                    )
                    continue
                if resolved == sha:
                    errors.append(
                        f"Commit {sha[:7]} cites itself in Informed-By: '{ref}'"
                    )
                    continue
                if not _is_ancestor(resolved, sha, root):
                    errors.append(
                        f"Commit {sha[:7]} cites non-ancestor Informed-By SHA: "
                        f"'{ref}' resolves to {resolved[:7]} which is not an ancestor"
                    )

    return errors


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------


def _safe(records: List[Dict[str, Any]], key: str) -> Tuple[List[Dict[str, Any]], str]:
    return records, key


def run_all_checks(root: str = ".") -> Dict[str, Any]:
    """Run every check and return a structured report (no printing, no exit)."""
    root = os.path.abspath(root)
    schema_dir = os.path.join(root, "schemas")
    state_dir = os.path.join(root, "state")

    schema_files = ["source", "evidence", "claim", "verification", "hypothesis"]
    schemas = {
        name: load_json(os.path.join(schema_dir, f"{name}.json"))
        for name in schema_files
    }

    sources = load_jsonl(os.path.join(state_dir, "sources.jsonl"))
    evidence = load_jsonl(os.path.join(state_dir, "evidence.jsonl"))
    claims = load_jsonl(os.path.join(state_dir, "claims.jsonl"))
    verifications = load_jsonl(os.path.join(state_dir, "verifications.jsonl"))
    hypotheses = load_jsonl(os.path.join(state_dir, "hypotheses.jsonl"))

    errors: List[str] = []
    warnings: List[str] = []

    # Schema validation
    for record in sources:
        errors.extend(validate_record(record, schemas["source"], "Source"))
    for record in evidence:
        errors.extend(validate_record(record, schemas["evidence"], "Evidence"))
    for record in claims:
        errors.extend(validate_record(record, schemas["claim"], "Claim"))
    for record in verifications:
        errors.extend(
            validate_record(record, schemas["verification"], "Verification")
        )
    for record in hypotheses:
        errors.extend(validate_record(record, schemas["hypothesis"], "Hypothesis"))

    # ID uniqueness
    errors.extend(
        validate_unique_ids(
            {
                "Source": _safe(sources, "source_id"),
                "Evidence": _safe(evidence, "evidence_id"),
                "Claim": _safe(claims, "claim_id"),
                "Verification": _safe(verifications, "verification_id"),
                "Hypothesis": _safe(hypotheses, "hypothesis_id"),
            }
        )
    )

    # Referential integrity
    errors.extend(
        validate_referential_integrity(
            sources, evidence, claims, verifications, hypotheses
        )
    )

    # Git provenance
    errors.extend(validate_git_provenance(root))

    # Semantic warnings (not build failures)
    evidence_ids = {e["evidence_id"] for e in evidence}
    source_ids = {s["source_id"] for s in sources}
    for source in sources:
        if not any(e.get("source_id") == source["source_id"] for e in evidence):
            warnings.append(f"Source '{source['source_id']}' has no linked evidence")
    for claim in claims:
        if claim.get("status") == "supported":
            passed = any(
                v.get("target_id") == claim["claim_id"]
                and v.get("result") == "pass"
                for v in verifications
            )
            if not passed:
                warnings.append(
                    f"Claim '{claim['claim_id']}' is 'supported' but has no passing verification"
                )
        for eid in claim.get("evidence_ids", []):
            if eid not in evidence_ids:
                # already an error above; keep the warning list clean
                pass
    for ev in evidence:
        if "quote_type" not in ev:
            warnings.append(
                f"Evidence '{ev['evidence_id']}' does not declare quote_type "
                "(verbatim vs paraphrase)"
            )

    return {
        "root": root,
        "counts": {
            "sources": len(sources),
            "evidence": len(evidence),
            "claims": len(claims),
            "verifications": len(verifications),
            "hypotheses": len(hypotheses),
        },
        "errors": errors,
        "warnings": warnings,
        "source_ids": sorted(source_ids),
    }


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="ResearchOS deterministic core validation"
    )
    parser.add_argument(
        "--root", default=".", help="repository root (default: current directory)"
    )
    parser.add_argument("--quiet", action="store_true", help="only print failures")
    args = parser.parse_args(list(argv) if argv is not None else None)

    print("=" * 60)
    print(" ResearchOS Core Deterministic Validation (hardened) ")
    print("=" * 60)

    try:
        report = run_all_checks(args.root)
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not load research state: {exc}")
        return 1

    counts = report["counts"]
    print(
        "Loaded: {sources} Sources, {evidence} Evidence, {claims} Claims, "
        "{verifications} Verifications, {hypotheses} Hypotheses".format(**counts)
    )

    if report["errors"]:
        print(f"\nFAIL: {len(report['errors'])} deterministic check error(s):")
        for err in report["errors"]:
            print(f"  - {err}")
        return 1

    print("✓ Schema validation PASS (types, enums, required fields, items)")
    print("✓ ID uniqueness PASS")
    print("✓ Referential integrity PASS")
    print("✓ Git provenance Informed-By PASS (existence + ancestry)")

    if report["warnings"]:
        print(f"\nWarnings ({len(report['warnings'])}):")
        for warning in report["warnings"]:
            print(f"  - {warning}")

    print("=" * 60)
    print(" ALL DETERMINISTIC CHECKS PASSED ")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
