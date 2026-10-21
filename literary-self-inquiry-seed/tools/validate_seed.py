#!/usr/bin/env python3
"""Validate the seed ledgers and their cross-references (stdlib only).

Implements the JSON-Schema subset used in schema/*.schema.json plus checks
that IDs referenced across JSONL collections actually exist.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COLLECTIONS = {
    "questions": ("questions.jsonl", "question_id", "question.schema.json"),
    "motifs": ("motifs.jsonl", "motif_id", "motif.schema.json"),
    "materials": ("materials.jsonl", "material_id", "material.schema.json"),
    "fragments": ("fragments.jsonl", "fragment_id", "fragment.schema.json"),
    "relations": ("relations.jsonl", "relation_id", "relation.schema.json"),
    "sessions": ("sessions.jsonl", "session_id", "session.schema.json"),
}


def matches_type(value: Any, expected: str) -> bool:
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


def resolve_ref(root_schema: dict[str, Any], ref: str) -> dict[str, Any] | None:
    if not ref.startswith("#/"):
        return None
    node: Any = root_schema
    for piece in ref[2:].split("/"):
        piece = piece.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or piece not in node:
            return None
        node = node[piece]
    return node if isinstance(node, dict) else None


def validate_value(value: Any, spec: dict[str, Any], root_schema: dict[str, Any], path: str, errors: list[str]) -> None:
    ref = spec.get("$ref")
    if isinstance(ref, str):
        target = resolve_ref(root_schema, ref)
        if target is None:
            errors.append(f"{path}: unresolved schema reference {ref}")
            return
        validate_value(value, target, root_schema, path, errors)
        return

    expected = spec.get("type")
    if isinstance(expected, str) and not matches_type(value, expected):
        errors.append(f"{path}: expected {expected}, got {type(value).__name__}")
        return

    if "enum" in spec and value not in spec["enum"]:
        errors.append(f"{path}: value {value!r} is not in enum {spec['enum']!r}")
    if isinstance(value, str) and isinstance(spec.get("minLength"), int) and len(value) < spec["minLength"]:
        errors.append(f"{path}: string shorter than minLength {spec['minLength']}")

    if isinstance(value, list):
        if spec.get("uniqueItems") is True:
            try:
                if len(value) != len({json.dumps(item, sort_keys=True, ensure_ascii=False) for item in value}):
                    errors.append(f"{path}: array items must be unique")
            except TypeError:
                errors.append(f"{path}: array items are not JSON-serializable")
        item_spec = spec.get("items")
        if isinstance(item_spec, dict):
            for index, item in enumerate(value):
                validate_value(item, item_spec, root_schema, f"{path}[{index}]", errors)

    if isinstance(value, dict):
        required = spec.get("required", [])
        if isinstance(required, list):
            for key in required:
                if key not in value:
                    errors.append(f"{path}: missing required field {key!r}")
        properties = spec.get("properties", {})
        if not isinstance(properties, dict):
            properties = {}
        if spec.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(f"{path}: unexpected field {key!r}")
        for key, child_spec in properties.items():
            if key in value and isinstance(child_spec, dict):
                validate_value(value[key], child_spec, root_schema, f"{path}.{key}", errors)


def load_jsonl(path: Path, id_key: str, errors: list[str]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    if not path.is_file():
        errors.append(f"{path.relative_to(ROOT)}: ledger file is missing")
        return records
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path.relative_to(ROOT)}:{lineno}: invalid JSON: {exc}")
            continue
        if not isinstance(record, dict):
            errors.append(f"{path.relative_to(ROOT)}:{lineno}: record must be an object")
            continue
        identity = record.get(id_key)
        if not isinstance(identity, str) or not identity:
            errors.append(f"{path.relative_to(ROOT)}:{lineno}: missing {id_key}")
            continue
        if identity in records:
            errors.append(f"{path.relative_to(ROOT)}:{lineno}: duplicate {id_key} {identity}")
            continue
        records[identity] = record
    return records


def check_refs(
    collection_name: str,
    records: dict[str, dict[str, Any]],
    field: str,
    target_name: str,
    target_records: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    for record_id, record in records.items():
        values = record.get(field, [])
        if not isinstance(values, list):
            continue  # schema validation reports the shape error
        for value in values:
            if value not in target_records:
                errors.append(f"{collection_name}:{record_id}: {field} references unknown {target_name} ID {value!r}")


def main() -> int:
    errors: list[str] = []
    collections: dict[str, dict[str, dict[str, Any]]] = {}

    for name, (filename, id_key, schema_filename) in COLLECTIONS.items():
        path = ROOT / "state" / filename
        records = load_jsonl(path, id_key, errors)
        collections[name] = records
        schema_path = ROOT / "schema" / schema_filename
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{schema_path.relative_to(ROOT)}: cannot load schema: {exc}")
            continue
        if not isinstance(schema, dict):
            errors.append(f"{schema_path.relative_to(ROOT)}: schema must be a JSON object")
            continue
        for record_id, record in records.items():
            validate_value(record, schema, schema, f"{name}:{record_id}", errors)

    questions = collections.get("questions", {})
    motifs = collections.get("motifs", {})
    materials = collections.get("materials", {})
    fragments = collections.get("fragments", {})
    relations = collections.get("relations", {})
    sessions = collections.get("sessions", {})

    check_refs("questions", questions, "motif_ids", "motif", motifs, errors)
    check_refs("questions", questions, "material_ids", "material", materials, errors)
    check_refs("questions", questions, "previous_question_ids", "question", questions, errors)
    check_refs("motifs", motifs, "question_ids", "question", questions, errors)
    check_refs("motifs", motifs, "material_ids", "material", materials, errors)
    check_refs("materials", materials, "motif_ids", "motif", motifs, errors)
    check_refs("fragments", fragments, "question_ids", "question", questions, errors)
    check_refs("fragments", fragments, "motif_ids", "motif", motifs, errors)
    check_refs("fragments", fragments, "material_ids", "material", materials, errors)
    check_refs("sessions", sessions, "question_ids", "question", questions, errors)
    check_refs("sessions", sessions, "context_material_ids", "material", materials, errors)
    check_refs("sessions", sessions, "produced_fragment_ids", "fragment", fragments, errors)
    check_refs("sessions", sessions, "new_question_ids", "question", questions, errors)

    for fragment_id, record in fragments.items():
        session_id = record.get("session_id")
        if session_id and session_id not in sessions:
            errors.append(f"fragments:{fragment_id}: session_id references unknown session {session_id!r}")

    endpoint_collections = {
        "question": questions,
        "motif": motifs,
        "material": materials,
        "fragment": fragments,
        "session": sessions,
    }
    for relation_id, relation in relations.items():
        for endpoint in ("left", "right"):
            ref = relation.get(endpoint)
            if not isinstance(ref, dict):
                continue
            target = endpoint_collections.get(ref.get("type"))
            if target is None or ref.get("id") not in target:
                errors.append(
                    f"relations:{relation_id}: {endpoint} references unknown "
                    f"{ref.get('type')} ID {ref.get('id')!r}"
                )

    if errors:
        print("FAIL: literary inquiry seed has errors")
        for error in errors:
            print("  - " + error)
        return 1

    counts = ", ".join(f"{name}={len(records)}" for name, records in collections.items())
    print(f"PASS: literary inquiry seed valid ({counts})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
