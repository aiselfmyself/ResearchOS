"""Adversarial append-only tests — PRP-002 rev3 (C2/A1).

REV-003 §3.4 found that ``test_append_only_hash_chain_is_enforced`` never
tampered with anything: it only fed a clean ``state/reviews.jsonl`` to
``resolve_effective`` and asserted there were no errors, so it passed on a
tampered tree.  REV-003 §3.1-§3.3 then showed three attacks that the guard
accepted:

1. rewriting the ``summary`` of ``REV-001`` in place;
2. deleting the ``REV-001`` line;
3. appending a new review line, committing it, and rewriting it afterwards.

Every test below performs one of those attacks **for real**, in a throwaway copy
of this repository, and asserts that the guard rejects it.  A test that does not
tamper cannot prove append-only, so none of these assertions are reachable
without modifying a ledger line first.

The copies are disposable: nothing in this module writes to the real repository.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from researchos_common import (  # noqa: E402
    GENESIS_HASH,
    anchored_ledgers,
    anchor_errors,
    append_jsonl,
    build_anchor_updates,
    head_at,
    ledger_lines,
    now_utc,
    prefix_heads,
    record_session_hint,
    rolling_head,
    session_from_branch,
)

REVIEWS = "state/reviews.jsonl"


# ---------------------------------------------------------------------------
# Throwaway repositories
# ---------------------------------------------------------------------------


def copy_into(workspace: Path) -> Path:
    """Copy the working tree (including ``.git``) into ``workspace/repo``.

    The copy carries the code under test *and* the committed history, so both
    the HEAD layer and the per-commit layer of ``check-append-only`` are live.
    """
    target = workspace / "repo"
    shutil.copytree(
        ROOT, target, symlinks=True, ignore=shutil.ignore_patterns("__pycache__")
    )
    return target


def throwaway_copy(case: unittest.TestCase) -> Path:
    """A per-test disposable copy that is removed when the test ends."""
    workspace = Path(tempfile.mkdtemp(prefix="researchos-tamper-"))
    case.addCleanup(shutil.rmtree, workspace, ignore_errors=True)
    return copy_into(workspace)


def run(repo: Path, *command: str, timeout: int = 600) -> subprocess.CompletedProcess:
    """Run a Python entry point of the copied repository."""
    return subprocess.run(
        [sys.executable, *command],
        cwd=str(repo),
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def git(repo: Path, *args: str, timeout: int = 600) -> subprocess.CompletedProcess:
    """Run git inside the copied repository."""
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def guard(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return run(repo, "scripts/researchos_guard.py", *args)


def tamper_line(repo: Path, relative_path: str, index: int, field: str, value) -> None:
    """Rewrite one field of one line, in place — the attack under test."""
    path = repo / relative_path
    lines = ledger_lines(path.read_text(encoding="utf-8"))
    record = json.loads(lines[index])
    record[field] = value
    lines[index] = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def delete_line(repo: Path, relative_path: str, index: int) -> None:
    path = repo / relative_path
    lines = ledger_lines(path.read_text(encoding="utf-8"))
    del lines[index]
    path.write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")


def commit_all(repo: Path, message: str, session: str, role: str) -> None:
    git(repo, "add", "-A")
    result = git(
        repo,
        "-c",
        "user.name=tamper-test",
        "-c",
        "user.email=tamper-test@example.invalid",
        "commit",
        "-q",
        "-m",
        f"{message}\n\nSession-Id: {session}\nSession-Role: {role}\nPolicy-Version: 1",
    )
    if result.returncode != 0:
        raise AssertionError(f"commit failed: {result.stdout} {result.stderr}")


# ---------------------------------------------------------------------------
# Anchor arithmetic (no git, no repository copy)
# ---------------------------------------------------------------------------


class RollingHeadTest(unittest.TestCase):
    def test_empty_ledger_heads_at_genesis(self) -> None:
        self.assertEqual(rolling_head([]), GENESIS_HASH)
        self.assertEqual(head_at([], 0), GENESIS_HASH)

    def test_head_commits_to_content_and_order(self) -> None:
        first, second = '{"a":1}', '{"b":2}'
        self.assertNotEqual(rolling_head([first, second]), rolling_head([second, first]))
        self.assertNotEqual(rolling_head([first]), rolling_head(['{"a":2}']))
        self.assertEqual(rolling_head([first, second]), rolling_head([first, second]))

    def test_head_at_walks_the_prefix(self) -> None:
        lines = ['{"a":1}', '{"b":2}', '{"c":3}']
        heads = prefix_heads(lines)
        self.assertEqual(len(heads), 3)
        self.assertEqual(head_at(heads, 1), rolling_head(lines[:1]))
        self.assertEqual(head_at(heads, 3), rolling_head(lines))
        with self.assertRaises(IndexError):
            head_at(heads, 4)


class AnchorLedgerTest(unittest.TestCase):
    """The anchor layer on a synthetic root: fast, git-free, and really tampered."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="researchos-anchors-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "state").mkdir(parents=True)
        for relative_path in anchored_ledgers():
            (self.tmp / relative_path).write_text("", encoding="utf-8")
        self.review = {
            "review_id": "REV-001",
            "proposal_id": "PRP-001",
            "session_id": "SES-b",
            "result": "pass",
            "summary": "original",
            "created_at": now_utc(),
        }
        append_jsonl(self.tmp / REVIEWS, self.review, anchor=False)
        self.reanchor()
        self.assertEqual(anchor_errors(self.tmp), [])

    def reanchor(self) -> None:
        for entry in build_anchor_updates(self.tmp, session_id="SES-test"):
            append_jsonl(self.tmp / "state/anchors.jsonl", entry, anchor=False)

    def test_pinned_ledger_is_consistent(self) -> None:
        self.assertEqual(anchor_errors(self.tmp), [])

    def test_rewriting_the_newest_line_breaks_the_anchor(self) -> None:
        """A1: the newest line is the one the revision chain never pinned."""
        tamper_line(self.tmp, REVIEWS, 0, "summary", "TAMPERED")
        errors = anchor_errors(self.tmp)
        self.assertTrue(
            any("was modified" in error for error in errors),
            errors,
        )

    def test_deleting_a_line_breaks_the_anchor(self) -> None:
        delete_line(self.tmp, REVIEWS, 0)
        errors = anchor_errors(self.tmp)
        self.assertTrue(any("deleted" in error for error in errors), errors)

    def test_re_anchoring_does_not_hide_a_rewrite(self) -> None:
        """Appending a fresh anchor for tampered content must not clean it.

        The older entry still pins the original prefix, so the rewrite stays
        visible no matter how many anchors are appended afterwards.
        """
        tamper_line(self.tmp, REVIEWS, 0, "summary", "TAMPERED")
        self.reanchor()
        errors = anchor_errors(self.tmp)
        self.assertTrue(
            any("was modified" in error for error in errors),
            f"re-anchoring hid the rewrite: {errors}",
        )

    def test_appending_without_re_anchoring_is_reported_as_stale(self) -> None:
        append_jsonl(
            self.tmp / REVIEWS,
            dict(self.review, review_id="REV-002", created_at=now_utc()),
            anchor=False,
        )
        errors = anchor_errors(self.tmp)
        self.assertTrue(any("stale" in error for error in errors), errors)
        self.reanchor()
        self.assertEqual(anchor_errors(self.tmp), [])

    def test_rewriting_an_earlier_anchor_line_is_detected(self) -> None:
        """The anchor ledger chains itself via prev_anchor_head_sha256."""
        anchors = self.tmp / "state/anchors.jsonl"
        self.reanchor()  # make sure there is more than one entry
        lines = ledger_lines(anchors.read_text(encoding="utf-8"))
        self.assertGreater(len(lines), 1)
        record = json.loads(lines[0])
        record["lines"] = int(record["lines"]) + 1
        lines[0] = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        anchors.write_text("\n".join(lines) + "\n", encoding="utf-8")
        errors = anchor_errors(self.tmp)
        self.assertTrue(
            any("prev_anchor_head_sha256" in error for error in errors),
            errors,
        )


# ---------------------------------------------------------------------------
# End-to-end attacks on a throwaway copy of this repository
# ---------------------------------------------------------------------------


class TamperAttackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        workspace = Path(tempfile.mkdtemp(prefix="researchos-tamper-shared-"))
        cls.addClassCleanup(shutil.rmtree, workspace, ignore_errors=True)
        cls.repo = copy_into(workspace)

    def test_pristine_copy_passes(self) -> None:
        result = guard(self.repo, "check-append-only", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["ok"])

    def test_attack1_rewriting_a_committed_line_in_place_is_rejected(self) -> None:
        repo = throwaway_copy(self)
        tamper_line(repo, REVIEWS, 0, "summary", "TAMPERED at rev3 HEAD")
        result = guard(repo, "check-append-only")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn(REVIEWS, result.stdout)
        self.assertIn("append-only violation", result.stdout)
        everything = guard(repo, "check-all", "--json")
        self.assertEqual(everything.returncode, 1, everything.stdout)
        self.assertFalse(json.loads(everything.stdout)["ok"])

    def test_attack2_deleting_a_committed_line_is_rejected(self) -> None:
        repo = throwaway_copy(self)
        delete_line(repo, REVIEWS, 0)
        result = guard(repo, "check-append-only")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("append-only violation", result.stdout)
        self.assertFalse(json.loads(guard(repo, "check-all", "--json").stdout)["ok"])

    def test_attack2b_deleting_a_line_the_validator_also_fails(self) -> None:
        repo = throwaway_copy(self)
        delete_line(repo, REVIEWS, 0)
        result = run(repo, "scripts/validate_researchos.py", "--quiet")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_attack3_rewriting_a_newly_appended_committed_line_is_rejected(self) -> None:
        """The exact hole REV-003 §3.3 exploited: a line appended *after* the
        baseline, committed, then rewritten.  The baseline prefix can never see
        it; the HEAD layer and the per-commit layer must."""
        repo = throwaway_copy(self)
        helper = (
            "import sys; sys.path.insert(0, 'scripts');"
            "from pathlib import Path;"
            "from researchos_common import append_jsonl, now_utc;"
            "append_jsonl(Path('state/reviews.jsonl'), {"
            "'review_id': 'REV-9001', 'proposal_id': 'PRP-002',"
            "'session_id': 'SES-f99f5b7f',"
            "'checks': [{'name': 'policy', 'result': 'pass'}],"
            "'result': 'pass', 'summary': 'original',"
            "'environment': 'tamper-test', 'created_at': now_utc()})"
        )
        appended = run(repo, "-c", helper)
        self.assertEqual(appended.returncode, 0, appended.stderr)
        commit_all(repo, "[Verifier] review: append REV-9001", "SES-f99f5b7f", "verifier")

        clean = guard(repo, "check-append-only")
        self.assertEqual(
            clean.returncode,
            0,
            "a legitimate append + auto-anchor + commit must stay green:\n"
            + clean.stdout,
        )

        lines = ledger_lines((repo / REVIEWS).read_text(encoding="utf-8"))
        self.assertEqual(json.loads(lines[-1])["review_id"], "REV-9001")

        # 3a: rewrite it, leave the rewrite uncommitted (HEAD layer)
        tamper_line(repo, REVIEWS, len(lines) - 1, "summary", "TAMPERED after commit")
        uncommitted = guard(repo, "check-append-only")
        self.assertEqual(uncommitted.returncode, 1, uncommitted.stdout)
        self.assertIn(REVIEWS, uncommitted.stdout)
        self.assertIn("append-only violation", uncommitted.stdout)

        # 3b: hide it by re-anchoring, then commit (per-commit layer)
        run(repo, "scripts/researchos_anchor.py", "update")
        commit_all(repo, "[Verifier] review: rewrite REV-9001", "SES-f99f5b7f", "verifier")
        committed = guard(repo, "check-append-only")
        self.assertEqual(committed.returncode, 1, committed.stdout)
        self.assertIn("append-only violation", committed.stdout)
        self.assertFalse(json.loads(guard(repo, "check-all", "--json").stdout)["ok"])

    def test_attack4_rewriting_a_line_in_the_middle_is_rejected(self) -> None:
        repo = throwaway_copy(self)
        lines = ledger_lines((repo / "state/review_queue.jsonl").read_text(encoding="utf-8"))
        self.assertGreater(len(lines), 2)
        tamper_line(repo, "state/review_queue.jsonl", 1, "status", "cancelled")
        result = guard(repo, "check-append-only")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("review_queue.jsonl", result.stdout)

    def test_history_layer_catches_a_committed_rewrite_without_anchors(self) -> None:
        """Layer 3 alone: drop the anchor ledger, commit a rewrite, and the
        per-commit audit must still reject it."""
        repo = throwaway_copy(self)
        (repo / "state/anchors.jsonl").write_text("", encoding="utf-8")
        tamper_line(repo, REVIEWS, 0, "summary", "TAMPERED")
        commit_all(repo, "[Verifier] review: rewrite REV-001", "SES-f99f5b7f", "verifier")
        result = guard(repo, "check-append-only")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertTrue(
            any(
                "was modified or reordered against" in line
                for line in result.stdout.splitlines()
            ),
            result.stdout,
        )


class AnchorAuthorshipTest(unittest.TestCase):
    """An anchor line is a record, so it must name the session that wrote it.

    ``check-authorship`` compares each record line against the ``Session-Id``
    trailer of the commit that introduced it.  During this rework an auto-pin for
    ``state/review_queue.jsonl`` — whose rows carry ``created_by_session``, not
    ``session_id`` — was written as ``"unknown"`` and turned
    ``check-all --stage propose`` red.  These tests keep that from coming back.
    """

    def test_record_session_hint_covers_the_ledger_variants(self) -> None:
        self.assertEqual(record_session_hint({"session_id": "SES-a"}), "SES-a")
        self.assertEqual(record_session_hint({"created_by_session": "SES-b"}), "SES-b")
        self.assertEqual(record_session_hint({"claimed_by_session": "SES-c"}), "SES-c")
        self.assertEqual(
            record_session_hint({"session_id": "SES-a", "created_by_session": "SES-b"}),
            "SES-a",
        )
        self.assertIsNone(record_session_hint({}))
        self.assertIsNone(record_session_hint({"session_id": ""}))

    def test_session_from_branch_maps_arena_branches(self) -> None:
        self.assertEqual(session_from_branch("arena/deadbeef-researchos"), "SES-deadbeef")
        self.assertEqual(session_from_branch("main"), "SES-main")
        self.assertEqual(session_from_branch("HEAD"), "")
        # An empty branch name means "not supplied": fall back to the repository.
        self.assertEqual(session_from_branch(""), session_from_branch(None))

    def test_auto_pin_falls_back_to_the_branch_session(self) -> None:
        """No explicit session and no record hint -> the branch, never 'unknown'."""
        with tempfile.TemporaryDirectory(prefix="researchos-authorship-") as tmp:
            root = Path(tmp)
            (root / "state").mkdir(parents=True)
            for relative_path in anchored_ledgers():
                (root / relative_path).write_text("", encoding="utf-8")
            git(root, "init", "-q", "-b", "arena/deadbeef-researchos")
            with mock.patch.dict(os.environ):
                os.environ.pop("GITHUB_REF_NAME", None)
                os.environ.pop("GITHUB_HEAD_REF", None)
                entries = build_anchor_updates(root)
            self.assertTrue(entries)
            self.assertEqual({entry["session_id"] for entry in entries}, {"SES-deadbeef"})
            for entry in entries:
                append_jsonl(root / "state/anchors.jsonl", entry, anchor=False)
            self.assertEqual(anchor_errors(root), [])

    def test_repository_anchor_lines_name_a_real_session(self) -> None:
        """The committed pin ledger must not contain an 'unknown' author."""
        path = ROOT / "state/anchors.jsonl"
        lines = ledger_lines(path.read_text(encoding="utf-8"))
        self.assertTrue(lines, "state/anchors.jsonl is empty")
        for raw in lines:
            record = json.loads(raw)
            self.assertNotEqual(record.get("session_id"), "unknown", raw)
            self.assertRegex(str(record.get("session_id", "")), r"^SES-.+")


if __name__ == "__main__":
    unittest.main()
