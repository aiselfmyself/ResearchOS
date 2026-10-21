#!/usr/bin/env python3
"""Create a curated, provenance-preserving literary-material snapshot.

This tool only reads the supplied ResearchOS checkout. With --write it writes
this seed kit's state/materials.jsonl and migration/manifest.json; no upstream
file is modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

KIT_ROOT = Path(__file__).resolve().parents[1]
SELECTION_PATH = KIT_ROOT / "migration" / "selection.json"
MATERIALS_PATH = KIT_ROOT / "state" / "materials.jsonl"
MANIFEST_PATH = KIT_ROOT / "migration" / "manifest.json"


class ImportErrorDetail(Exception):
    pass


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ImportErrorDetail(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ImportErrorDetail(f"invalid JSON in {path}: {exc}") from exc


def read_ledger(root: Path, collection: str, id_key: str) -> dict[str, tuple[dict[str, Any], str]]:
    base = root / "state" / f"{collection}.jsonl"
    shard_dir = base.with_name(base.stem + ".d")
    files = [base] + (sorted(shard_dir.glob("*.jsonl")) if shard_dir.is_dir() else [])
    found: dict[str, tuple[dict[str, Any], str]] = {}
    for path in files:
        if not path.is_file():
            if path == base:
                raise ImportErrorDetail(f"missing ledger: {path}")
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise ImportErrorDetail(f"cannot read {path}: {exc}") from exc
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ImportErrorDetail(f"invalid JSON at {path}:{line_number}: {exc}") from exc
            if not isinstance(record, dict):
                raise ImportErrorDetail(f"record at {path}:{line_number} is not an object")
            identity = record.get(id_key)
            if not isinstance(identity, str) or not identity:
                raise ImportErrorDetail(f"record at {path}:{line_number} has no {id_key}")
            if identity in found:
                old_path = found[identity][1]
                raise ImportErrorDetail(f"duplicate {id_key} {identity}: {old_path} and {path}")
            found[identity] = (record, path.relative_to(root).as_posix())
    return found


def git_commit(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ImportErrorDetail(
            f"cannot determine upstream Git commit in {root}; pass a full ResearchOS checkout"
        )
    return result.stdout.strip()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def build_outputs(source_root: Path, *, reuse_pinned_commit: bool = False) -> dict[Path, str]:
    source_root = source_root.resolve()
    if not source_root.is_dir():
        raise ImportErrorDetail(f"source root is not a directory: {source_root}")
    selection_bytes = SELECTION_PATH.read_bytes()
    selection = read_json(SELECTION_PATH)
    if not isinstance(selection, dict):
        raise ImportErrorDetail("selection file must contain a JSON object")

    # A check should remain reproducible after this seed kit is committed into
    # ResearchOS: the current HEAD then changes, even though the selected
    # upstream records have not. --write intentionally refreshes to HEAD.
    commit = ""
    if reuse_pinned_commit and MANIFEST_PATH.is_file():
        old_manifest = read_json(MANIFEST_PATH)
        if isinstance(old_manifest, dict):
            pinned = old_manifest.get("upstream_commit")
            if isinstance(pinned, str) and len(pinned) >= 7:
                commit = pinned
    if not commit:
        commit = git_commit(source_root)

    selected_source_ids = selection.get("selected_sources")
    selected_evidence = selection.get("selected_evidence")
    memo_refs = selection.get("reference_memos")
    if not isinstance(selected_source_ids, list) or not all(isinstance(x, str) for x in selected_source_ids):
        raise ImportErrorDetail("selected_sources must be a list of IDs")
    if len(selected_source_ids) != len(set(selected_source_ids)):
        raise ImportErrorDetail("selected_sources contains duplicates")
    if not isinstance(selected_evidence, list) or not all(isinstance(x, dict) for x in selected_evidence):
        raise ImportErrorDetail("selected_evidence must be a list of objects")
    if not isinstance(memo_refs, list) or not all(isinstance(x, dict) for x in memo_refs):
        raise ImportErrorDetail("reference_memos must be a list of objects")

    source_records = read_ledger(source_root, "sources", "source_id")
    evidence_records = read_ledger(source_root, "evidence", "evidence_id")
    source_ids = set(selected_source_ids)
    missing_sources = sorted(source_ids - set(source_records))
    if missing_sources:
        raise ImportErrorDetail("selected source ID(s) missing upstream: " + ", ".join(missing_sources))

    evidence_ids = [entry.get("evidence_id") for entry in selected_evidence]
    if not all(isinstance(x, str) and x for x in evidence_ids):
        raise ImportErrorDetail("every selected_evidence entry needs an evidence_id")
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ImportErrorDetail("selected_evidence contains duplicate IDs")

    materials: list[dict[str, Any]] = []
    evidence_origins: dict[str, str] = {}
    used_sources: set[str] = set()
    for selection_entry in selected_evidence:
        evidence_id = selection_entry["evidence_id"]
        if evidence_id not in evidence_records:
            raise ImportErrorDetail(f"selected evidence ID missing upstream: {evidence_id}")
        evidence, evidence_path = evidence_records[evidence_id]
        source_id = evidence.get("source_id")
        if source_id not in source_ids:
            raise ImportErrorDetail(
                f"{evidence_id} points to {source_id}, which is not in selected_sources"
            )
        source, source_path = source_records[source_id]
        motifs = selection_entry.get("motif_ids")
        invitation = selection_entry.get("literary_invitation")
        scope = selection_entry.get("scope_note")
        if not isinstance(motifs, list) or not all(isinstance(x, str) for x in motifs):
            raise ImportErrorDetail(f"{evidence_id}: motif_ids must be a list of strings")
        if not isinstance(invitation, str) or not invitation.strip():
            raise ImportErrorDetail(f"{evidence_id}: literary_invitation is required")
        if not isinstance(scope, str) or not scope.strip():
            raise ImportErrorDetail(f"{evidence_id}: scope_note is required")

        material = {
            "material_id": f"MAT-{evidence_id}",
            "kind": "research_excerpt",
            "title": source.get("title", "Untitled source"),
            "source": {
                "source_id": source_id,
                "title": source.get("title", "Untitled source"),
                "authors": source.get("authors", []),
                "year": source.get("year", 0),
                "url": source.get("url", ""),
                "version_note": source.get("venue", source.get("doi", "")),
            },
            "passage": evidence.get("excerpt", ""),
            "passage_language": "en",
            "context": evidence.get("section_or_page", ""),
            "source_note": evidence.get("interpretation", ""),
            "literary_invitation": invitation,
            "scope_note": scope,
            "motif_ids": motifs,
            "origin": {
                "repository": selection.get("upstream_repository", ""),
                "commit": commit,
                "source_record_id": source_id,
                "evidence_record_id": evidence_id,
                "source_record_path": source_path,
                "evidence_record_path": evidence_path,
            },
        }
        materials.append(material)
        evidence_origins[evidence_id] = evidence_path
        used_sources.add(source_id)

    unused_selected = sorted(source_ids - used_sources)
    if unused_selected:
        raise ImportErrorDetail(
            "selected_sources must all be referenced by selected evidence; unused: "
            + ", ".join(unused_selected)
        )

    checked_memos: list[dict[str, Any]] = []
    for entry in memo_refs:
        path_value = entry.get("path")
        if not isinstance(path_value, str) or not path_value:
            raise ImportErrorDetail("each reference_memos entry needs a path")
        memo_path = source_root / path_value
        if not memo_path.is_file():
            raise ImportErrorDetail(f"referenced memo missing upstream: {path_value}")
        checked_memos.append({
            "path": path_value,
            "role": str(entry.get("role", "")),
            "copied": bool(entry.get("copy", False)),
        })

    manifest = {
        "manifest_version": 1,
        "upstream_repository": selection.get("upstream_repository"),
        "upstream_commit": commit,
        "selection_file": "migration/selection.json",
        "selection_sha256": hashlib.sha256(selection_bytes).hexdigest(),
        "coverage_note": selection.get("coverage_note", ""),
        "counts": {
            "selected_sources": len(used_sources),
            "selected_evidence": len(materials),
            "material_records": len(materials),
            "memo_references_not_copied": len(checked_memos),
        },
        "selected_source_ids": sorted(used_sources),
        "selected_evidence_ids": evidence_ids,
        "material_id_map": {evidence_id: f"MAT-{evidence_id}" for evidence_id in evidence_ids},
        "source_record_origins": {
            source_id: source_records[source_id][1] for source_id in sorted(used_sources)
        },
        "evidence_record_origins": evidence_origins,
        "reference_memos": checked_memos,
        "excluded_by_design": selection.get("excluded_by_design", []),
    }
    materials_text = "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
        for record in materials
    )
    return {MATERIALS_PATH: materials_text, MANIFEST_PATH: canonical_json(manifest)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path, help="Path to the original ResearchOS checkout")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--write", action="store_true", help="Write the curated snapshot and manifest")
    action.add_argument("--check", action="store_true", help="Check that committed outputs match the source snapshot")
    args = parser.parse_args()

    try:
        outputs = build_outputs(args.source_root, reuse_pinned_commit=not args.write)
    except (ImportErrorDetail, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.write:
        for path, text in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            print(f"WROTE {path.relative_to(KIT_ROOT)}")
    elif args.check:
        stale: list[str] = []
        for path, expected in outputs.items():
            if not path.is_file() or path.read_text(encoding="utf-8") != expected:
                stale.append(path.relative_to(KIT_ROOT).as_posix())
        if stale:
            print("STALE " + ", ".join(stale), file=sys.stderr)
            print("run with --write after reviewing the selected records", file=sys.stderr)
            return 1
        print("PASS: selected source/evidence snapshot and manifest match the upstream checkout")
    else:
        print(f"DRY RUN: would write {len(outputs)} files")
        for path, text in outputs.items():
            print(f"  {path.relative_to(KIT_ROOT)} ({len(text.encode('utf-8'))} bytes)")

    print(f"summary: materials={len(json.loads(outputs[MANIFEST_PATH])['selected_evidence_ids'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
