"""Synthetic CLI regression tests; no real ledgers or third-party packages."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "merge_ledgers.py"


class MergeLedgersTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_merge(self, base="", ours="", theirs="", *extra, sentinel=False):
        command = [sys.executable, str(SCRIPT), "--id-key", "id"]
        for name, text in (("base", base), ("ours", ours), ("theirs", theirs)):
            path = self.root / name
            path.write_bytes(text.encode())
            command.extend(["--" + name, str(path)])
        self.out = self.root / "out"
        if sentinel:
            self.out.write_text("untouched", encoding="utf-8")
        elif self.out.exists():
            self.out.unlink()
        return subprocess.run(command + ["--out", str(self.out)] + list(extra),
                              capture_output=True, text=True)

    @staticmethod
    def record(identity, value=1):
        return json.dumps({"id": identity, "value": value}) + "\n"

    def test_both_append_legacy_and_new_sorted(self):
        base = self.record("EVD-001")
        result = self.run_merge(base, base + self.record("EVD-20261021-bbbb"),
                                base + self.record("EVD-20261021-aaaa"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.out.read_text(), base + self.record("EVD-20261021-aaaa")
                         + self.record("EVD-20261021-bbbb"))

    def test_dedup_and_original_base_bytes(self):
        base = '{ "value": 1, "id": "z" }\r\n'
        variant = '{"id":"z","value":1}\n'
        result = self.run_merge(base + base, variant * 2, variant)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.out.read_bytes(), base.encode())

    def test_all_conflicts_reported_without_touching_output(self):
        a, b = self.record("a"), self.record("b")
        result = self.run_merge(a + b, self.record("a", 2) + b,
                                a + self.record("b", 3), sentinel=True)
        self.assertEqual(result.returncode, 1)
        for text in ("conflict ID 'a'", "conflict ID 'b'", "base:", "ours:", "theirs:"):
            self.assertIn(text, result.stderr)
        self.assertEqual(self.out.read_text(), "untouched")
        self.assertEqual(result.stdout, "")

    def test_intra_input_conflict(self):
        result = self.run_merge("", self.record("a") + self.record("a", 2), "")
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.out.exists())

    def test_delete_rejected_on_either_side(self):
        a = self.record("a")
        for ours, theirs in ((a, ""), ("", a), ("", "")):
            result = self.run_merge(a, ours, theirs)
            self.assertEqual(result.returncode, 1)
            self.assertIn("deletion ID 'a'", result.stderr)
            self.assertFalse(self.out.exists())

    def test_allow_delete_is_delete_wins(self):
        a, b = self.record("a"), self.record("b")
        result = self.run_merge(a, a + b, "", "--allow-delete")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("(allowed)", result.stderr)
        self.assertEqual(self.out.read_text(), b)

    def test_allow_delete_never_hides_edit(self):
        result = self.run_merge(self.record("a"), self.record("a", 2), "", "--allow-delete")
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.out.exists())

    def test_deterministic_and_base_order(self):
        base = self.record("z") + self.record("b")
        expected = base + self.record("a") + self.record("c")
        outputs = []
        for _ in range(2):
            result = self.run_merge(base, base + self.record("c"), base + self.record("a"))
            self.assertEqual(result.returncode, 0, result.stderr)
            outputs.append(self.out.read_bytes())
        self.assertEqual(outputs, [expected.encode()] * 2)

    def test_invalid_json_and_missing_ids_line_numbers(self):
        for invalid in ('{broken', '{}', '[]', '{"id":null}', '{"id":4}',
                        '{"id":""}', '{"id":"x","v":NaN}', '{"id":"a","id":"b"}'):
            with self.subTest(invalid=invalid):
                result = self.run_merge("", self.record("ok") + invalid + "\n", "", sentinel=True)
                self.assertEqual(result.returncode, 2)
                self.assertIn(":2:", result.stderr)
                self.assertEqual(self.out.read_text(), "untouched")

    def test_empty_files(self):
        result = self.run_merge()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.out.read_bytes(), b"")

    def test_missing_newline_separated(self):
        base = '{"id":"z"}'
        result = self.run_merge(base, base + '\n' + self.record("a"), base)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.out.read_text(), base + '\n' + self.record("a"))

    def test_json_types_not_conflated(self):
        for value in ('true', '"1"', '1.0'):
            result = self.run_merge('{"id":"a","v":1}',
                                    '{"id":"a","v":' + value + '}', "")
            self.assertEqual(result.returncode, 1)

    def test_stdout_and_missing_input(self):
        paths = [self.root / name for name in ("b", "o", "t")]
        for path in paths:
            path.write_text(self.record("a"))
        command = [sys.executable, str(SCRIPT), "--base", str(paths[0]),
                   "--ours", str(paths[1]), "--theirs", str(paths[2]), "--id-key", "id"]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, self.record("a"))
        paths[2].unlink()
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
