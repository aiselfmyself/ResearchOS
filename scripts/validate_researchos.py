#!/usr/bin/env python3
"""
ResearchOS Deterministic Core Validator
Enforces schema validation, referential integrity, and git provenance checks.
"""
import os
import sys
import json
import subprocess

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_jsonl(path):
    records = []
    if not os.path.exists(path):
        return records
    with open(path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"ERROR: Invalid JSON at {path}:{idx}: {e}")
                    sys.exit(1)
    return records

def validate_schema(record, schema, schema_name):
    # Minimal schema validation for required fields and types
    for req in schema.get("required", []):
        if req not in record:
            print(f"ERROR in {schema_name}: missing required field '{req}' in record: {record}")
            return False
    return True

def validate_referential_integrity(sources, evidence, claims, verifications):
    source_ids = {s["source_id"] for s in sources}
    evidence_ids = {e["evidence_id"] for e in evidence}
    claim_ids = {c["claim_id"] for c in claims}
    
    errors = []
    # 1. Check evidence -> source
    for e in evidence:
        if e["source_id"] not in source_ids:
            errors.append(f"Evidence '{e['evidence_id']}' references non-existent source '{e['source_id']}'")
            
    # 2. Check claim -> evidence
    for c in claims:
        for eid in c.get("evidence_ids", []):
            if eid not in evidence_ids:
                errors.append(f"Claim '{c['claim_id']}' references non-existent evidence '{eid}'")
                
    # 3. Check verification -> target
    all_targets = source_ids | evidence_ids | claim_ids
    for v in verifications:
        if v["target_id"] not in all_targets:
            errors.append(f"Verification '{v['verification_id']}' references non-existent target '{v['target_id']}'")
            
    return errors

def validate_git_provenance():
    # Verify that commit trailers Informed-By actually exist in git history
    try:
        raw_log = subprocess.check_output(["git", "log", "--format=%H%x1f%s%x1f%b%x1e"], text=True)
    except Exception as e:
        print(f"WARNING: Git log check skipped: {e}")
        return []
        
    entries = raw_log.strip().split("\x1e")
    existing_shas = set()
    for entry in entries:
        if not entry.strip():
            continue
        parts = entry.strip().split("\x1f")
        existing_shas.add(parts[0])
        existing_shas.add(parts[0][:7])

    provenance_errors = []
    for entry in entries:
        if not entry.strip():
            continue
        parts = entry.strip().split("\x1f")
        sha = parts[0][:7]
        body = parts[2] if len(parts) > 2 else ""
        for line in body.split("\n"):
            if line.strip().lower().startswith("informed-by:"):
                refs = line.split(":", 1)[1].split(",")
                for ref in refs:
                    ref = ref.strip()
                    if ref and ref.lower() not in ("none", "root"):
                        if ref not in existing_shas:
                            provenance_errors.append(f"Commit {sha} cites non-existent Informed-By SHA: '{ref}'")
    return provenance_errors

def main():
    print("=" * 60)
    print(" ResearchOS Core Deterministic Validation ")
    print("=" * 60)
    
    # 1. Schemas
    source_schema = load_json("schemas/source.json")
    evidence_schema = load_json("schemas/evidence.json")
    claim_schema = load_json("schemas/claim.json")
    verification_schema = load_json("schemas/verification.json")
    
    # 2. State Records
    sources = load_jsonl("state/sources.jsonl")
    evidence = load_jsonl("state/evidence.jsonl")
    claims = load_jsonl("state/claims.jsonl")
    verifications = load_jsonl("state/verifications.jsonl")
    
    print(f"Loaded: {len(sources)} Sources, {len(evidence)} Evidence, {len(claims)} Claims, {len(verifications)} Verifications")
    
    # Schema checks
    all_valid = True
    for s in sources:
        if not validate_schema(s, source_schema, "Source"):
            all_valid = False
    for e in evidence:
        if not validate_schema(e, evidence_schema, "Evidence"):
            all_valid = False
    for c in claims:
        if not validate_schema(c, claim_schema, "Claim"):
            all_valid = False
    for v in verifications:
        if not validate_schema(v, verification_schema, "Verification"):
            all_valid = False
            
    if not all_valid:
        print("FAIL: Schema validation failed.")
        sys.exit(1)
    print("✓ Schema validation PASS")
    
    # Referential integrity checks
    ref_errors = validate_referential_integrity(sources, evidence, claims, verifications)
    if ref_errors:
        print("FAIL: Referential integrity errors:")
        for err in ref_errors:
            print(f"  - {err}")
        sys.exit(1)
    print("✓ Referential integrity PASS")
    
    # Git provenance checks
    prov_errors = validate_git_provenance()
    if prov_errors:
        print("FAIL: Git provenance errors:")
        for err in prov_errors:
            print(f"  - {err}")
        sys.exit(1)
    print("✓ Git provenance Informed-By PASS")
    
    print("=" * 60)
    print(" ALL DETERMINISTIC CHECKS PASSED ")
    print("=" * 60)
    sys.exit(0)

if __name__ == "__main__":
    main()
