"""Tests for the observation_key overlay (state/evidence_keys.jsonl + .d/).

WHY THIS EXISTS
---------------
SHELDON's ``provisional`` rule (contributions/2026-10-21_sheldon_reading.md
section 3.4) groups observations by ``observation_key``, and ``gap_scan``
refuses to count a refutation that no other source corroborates. The key
therefore has to live on the EVD -- but an EVD record is append-only, and a
second record with the same ``evidence_id`` is reported as a duplicate by
``ledger_store`` (by design: choosing one silently is the ``merge=union``
failure mode). The overlay adds the key from a separate file instead:

    state/evidence_keys.jsonl                        frozen base (empty)
    state/evidence_keys.d/<YYYY-MM-DD>-<12 hex>.jsonl

This file pins the properties that make it safe, on SYNTHETIC state
directories (the real repository is only read, never written):

  * a key is added where the EVD has none, and an existing key is never
    replaced (the overlay annotates, it does not correct);
  * two keys for one evidence_id are an error, not a silent pick;
  * an unknown evidence_id, a record without a key, a shard without its base
    and a wrongly named shard are all reported;
  * ``gap_scan`` sees the overlay keys, so the measured ``provisional`` count
    is the same one the validator checks;
  * ``new_ledger_shard.py`` can mint an overlay shard name in the convention.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import gap_scan as gs  # noqa: E402
import ledger_store  # noqa: E402
import new_ledger_shard as nls  # noqa: E402
import validate_state as vs  # noqa: E402

EVDS = [
    {"evidence_id": "EVD-001", "source_id": "SRC-A", "excerpt": "a",
     "interpretation": "a", "confidence": "high"},
    {"evidence_id": "EVD-002", "source_id": "SRC-B", "excerpt": "b",
     "interpretation": "b", "confidence": "high"},
    {"evidence_id": "EVD-003", "source_id": "SRC-A", "excerpt": "c",
     "interpretation": "c", "confidence": "high"},
]


def _write_jsonl(path: Path, records) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
        encoding="utf-8",
    )


def _state_dir(tmp: str, evidences=None, overlay=None, overlay_shard_name=None):
    """A throwaway state/ directory holding just the ledgers these tests need."""
    state = Path(tmp) / "state"
    state.mkdir()
    _write_jsonl(state / "sources.jsonl", [{"source_id": "SRC-A"}, {"source_id": "SRC-B"}])
    _write_jsonl(state / "evidence.jsonl", EVDS if evidences is None else evidences)
    _write_jsonl(state / "claims.jsonl", [])
    _write_jsonl(state / "verifications.jsonl", [])
    _write_jsonl(state / "hypotheses.jsonl", [{"hypothesis_id": "HYP-001", "statement": "s", "status": "testing"}])
    _write_jsonl(state / "relations.jsonl", [])
    # Every other collection must have a base file, or the validator reports
    # "file not found" for it (the hypothesis-cycle ledgers are new).
    for name, (ledger_rel, _schema, _id_key) in vs.COLLECTIONS.items():
        path = Path(tmp) / ledger_rel
        if not path.exists():
            _write_jsonl(path, [])
    shutil.copy(ROOT / vs.CYCLE_EXEMPTIONS, state / "cycle_exemptions.json")
    if overlay is not None:
        name = overlay_shard_name or "2026-10-21-0123456789ab.jsonl"
        path = state / "evidence_keys.d" / name
        _write_jsonl(path, overlay)
        base = state / "evidence_keys.jsonl"
        if not base.exists():
            base.write_text("", encoding="utf-8")
    return state


class ApplyTest(unittest.TestCase):
    def test_key_is_added_where_absent(self) -> None:
        records = vs.apply_evidence_keys(EVDS, {"EVD-001": "k1"})
        self.assertEqual(records[0]["observation_key"], "k1")
        self.assertNotIn("observation_key", records[1])

    def test_existing_key_is_not_replaced(self) -> None:
        evidences = [dict(EVDS[0], observation_key="original")]
        records = vs.apply_evidence_keys(evidences, {"EVD-001": "overlay"})
        self.assertEqual(records[0]["observation_key"], "original")

    def test_blank_existing_key_is_filled(self) -> None:
        evidences = [dict(EVDS[0], observation_key="   ")]
        records = vs.apply_evidence_keys(evidences, {"EVD-001": "overlay"})
        self.assertEqual(records[0]["observation_key"], "overlay")

    def test_input_records_are_not_mutated(self) -> None:
        vs.apply_evidence_keys(EVDS, {"EVD-001": "k1"})
        self.assertNotIn("observation_key", EVDS[0])

    def test_unknown_evidence_is_ignored_by_apply_and_reported_by_check(self) -> None:
        records = vs.apply_evidence_keys(EVDS, {"EVD-999": "k1"})
        self.assertTrue(all("observation_key" not in r for r in records))
        errors = vs.check_evidence_keys(EVDS, {"EVD-999": "k1"})
        self.assertEqual(len(errors), 1)
        self.assertIn("EVD-999", errors[0])


class LoadTest(unittest.TestCase):
    def test_missing_base_and_no_shards_is_not_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mapping, errors = vs.load_evidence_keys(Path(tmp) / "state" / "evidence_keys.jsonl")
        self.assertEqual((mapping, errors), ({}, []))

    def test_shard_without_base_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state"
            _write_jsonl(
                state / "evidence_keys.d" / "2026-10-21-0123456789ab.jsonl",
                [{"evidence_id": "EVD-001", "observation_key": "k"}],
            )
            mapping, errors = vs.load_evidence_keys(state / "evidence_keys.jsonl")
        self.assertEqual(mapping, {})
        self.assertEqual(len(errors), 1)
        self.assertIn("base file not found", errors[0])

    def test_duplicate_key_for_one_evidence_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = _state_dir(
                tmp,
                overlay=[
                    {"evidence_id": "EVD-001", "observation_key": "k1"},
                    {"evidence_id": "EVD-001", "observation_key": "k2"},
                ],
            )
            mapping, errors = vs.load_evidence_keys(state / "evidence_keys.jsonl")
        self.assertEqual(mapping, {"EVD-001": "k1"})
        self.assertEqual(len(errors), 1)
        self.assertIn("duplicate overlay key for EVD-001", errors[0])

    def test_missing_key_or_evidence_id_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = _state_dir(
                tmp,
                overlay=[
                    {"evidence_id": "EVD-001"},
                    {"observation_key": "k"},
                    {"evidence_id": "EVD-002", "observation_key": "  "},
                ],
            )
            mapping, errors = vs.load_evidence_keys(state / "evidence_keys.jsonl")
        self.assertEqual(mapping, {})
        self.assertEqual(len(errors), 3)

    def test_wrongly_named_shard_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = _state_dir(
                tmp,
                overlay=[{"evidence_id": "EVD-001", "observation_key": "k"}],
                overlay_shard_name="2026-10-21-not-12-hex.jsonl",
            )
            mapping, errors = vs.load_evidence_keys(state / "evidence_keys.jsonl")
        self.assertEqual(mapping, {"EVD-001": "k"})
        self.assertTrue(any("does not match" in e for e in errors), errors)


class ValidatorTest(unittest.TestCase):
    def test_synthetic_root_passes_with_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            # Symlink everything except state/ so schema and path checks work.
            for entry in ROOT.iterdir():
                if entry.name in {"state", ".git"}:
                    continue
                (root / entry.name).symlink_to(entry)
            shutil.copytree(ROOT / "state", root / "state")
            report = vs.run_all_checks(root)
        self.assertEqual(report["errors"], [], msg="\n".join(report["errors"]))

    def test_unknown_evidence_in_overlay_fails_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            for entry in ROOT.iterdir():
                if entry.name not in {"state", ".git"}:
                    (root / entry.name).symlink_to(entry)
            shutil.copytree(ROOT / "state", root / "state")
            _write_jsonl(
                root / "state" / "evidence_keys.d" / "2026-10-21-ffffffffffff.jsonl",
                [{"evidence_id": "EVD-XXXX", "observation_key": "k"}],
            )
            report = vs.run_all_checks(root)
        self.assertTrue(
            any("EVD-XXXX" in e for e in report["errors"]), report["errors"]
        )


class GapScanSeesOverlayTest(unittest.TestCase):
    def test_key_from_overlay_makes_corroboration_visible(self) -> None:
        """Two EVDs from different sources, keyed only through the overlay."""
        with tempfile.TemporaryDirectory() as tmp:
            state = _state_dir(
                tmp,
                overlay=[
                    {"evidence_id": "EVD-001", "observation_key": "shared"},
                    {"evidence_id": "EVD-002", "observation_key": "shared"},
                ],
            )
            records = gs.load_ledger("evidence", state)
            report = gs.analyse(
                records, [], [{"hypothesis_id": "HYP-001"}]
            )
        self.assertEqual(report["totals"]["provisional"], 1)
        self.assertEqual(report["totals"]["non_provisional"], 2)

    def test_overlay_error_is_a_measurement_error_not_a_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = _state_dir(
                tmp,
                overlay=[{"evidence_id": "EVD-001", "observation_key": "k"}],
                overlay_shard_name="2026-10-21-bad.jsonl",
            )
            with self.assertRaises(gs.LedgerError):
                gs.load_ledger("evidence", state)


class ShardToolTest(unittest.TestCase):
    def test_overlay_target_is_available_and_follows_the_convention(self) -> None:
        self.assertIn("evidence_keys", nls.TARGETS)
        self.assertEqual(
            nls.TARGETS["evidence_keys"], vs.EVIDENCE_KEYS_LEDGER
        )
        name = nls.shard_name("evidence_keys", "20261021")
        self.assertTrue(ledger_store.SHARD_NAME_RE.match(name), name)


class RealRepositoryTest(unittest.TestCase):
    """What the 2026-10-21 integration actually left in state/."""

    def test_validator_passes(self) -> None:
        report = vs.run_all_checks(ROOT)
        self.assertEqual(report["errors"], [], msg="\n".join(report["errors"]))

    def test_overlay_never_confuses_search_seeds_with_corroboration(self) -> None:
        mapping, errors = vs.load_evidence_keys(ROOT / vs.EVIDENCE_KEYS_LEDGER)
        self.assertEqual(errors, [])
        evidence = gs.load_ledger("evidence", ROOT / "state")
        by_id = {e["evidence_id"]: (i, e) for i, e in enumerate(evidence)}
        flags = gs.derive_provisional(evidence)
        # The Agentic Scientist registers one paper twice (SRC-20261021-7419
        # and SRC-20261021-8452); those EVDs must NOT share a key, or the
        # duplicate would look like independent corroboration.
        for evidence_id in (
            "EVD-20261021-6094", "EVD-20261021-05ed",
            "EVD-20261021-a1fa", "EVD-20261021-a6fd",
            "EVD-20261021-e31f",
        ):
            self.assertNotIn(evidence_id, mapping)
        # An unexplained EVD may now get a *singleton* key as a search seed.
        # That must not make it non-provisional: only a second distinct SRC
        # sharing the key can do that. This invariant also survives future
        # append-only corroboration without hard-coding today's group sizes.
        groups = {}
        for row in evidence:
            key = row.get("observation_key")
            if key:
                groups.setdefault(key, set()).add(row["source_id"])
        for evidence_id, key in mapping.items():
            i, e = by_id[evidence_id]
            independently_seen = any(src != e["source_id"] for src in groups[key])
            self.assertEqual(flags[i], not independently_seen, evidence_id)


if __name__ == "__main__":
    unittest.main()
