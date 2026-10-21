"""Tests for scripts/holdout_eval.py (RRSI: hold-out / OOD separation).

RRSI's point is that a harness tuned by evaluating candidates on a fixed task
set overfits to that set, and adoption must therefore be decided out of
sample. This repository has the same shape: `check_doc_numbers.py` was made
to stop reporting false positives by adding skip rules (blockquotes,
`drift-ok`) and narrowing the "N件" pattern -- **every one of those rules was
fitted to the corpus in front of the author.** Nothing checked whether they
generalise.

The instrument is only worth having if it actually fires, so the most
important test here is `test_detects_overfitting`: a synthetic corpus where
the dev partition is clean and the hold-out is not must be rejected with
status OVERFIT-SUSPECTED.

Also pinned:
  * the partition is deterministic and stable when files are added;
  * line-level fallback keeps each file separate (concatenating files would
    manufacture findings that exist in neither document);
  * a corpus too small to partition is reported as insufficient rather than
    silently producing a meaningless verdict;
  * exclusion density counts the skip markers a detector cannot see.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import holdout_eval as he  # noqa: E402


class PartitionTest(unittest.TestCase):
    def make(self, n: int) -> list:
        return [ROOT / f"contributions/fake_{i:02d}.md" for i in range(n)]

    def test_is_deterministic(self):
        paths = self.make(17)
        a = he.partition(paths, seed="s1")
        b = he.partition(paths, seed="s1")
        self.assertEqual(a, b)

    def test_seed_changes_the_split(self):
        paths = self.make(17)
        a = he.partition(paths, seed="s1")
        b = he.partition(paths, seed="s2")
        self.assertNotEqual(a, b)

    def test_size_matches_fraction(self):
        paths = self.make(20)
        dev, hold = he.partition(paths, seed="s1", holdout_frac=0.25)
        self.assertEqual(len(hold), 5)
        self.assertEqual(len(dev), 15)
        self.assertEqual(len(dev) + len(hold), len(paths))

    def test_split_is_stable_when_files_are_added(self):
        """Assignment depends on the path, not on the index.

        Otherwise adding one memo would reshuffle every partition and the
        hold-out would stop being a hold-out.
        """
        paths = self.make(10)
        dev1, hold1 = he.partition(paths, seed="s")
        extra = paths + [ROOT / "contributions/fake_99.md"]
        dev2, hold2 = he.partition(extra, seed="s")
        for p in hold1:
            self.assertIn(p, hold2, f"{p.name} moved out of hold-out")

    def test_empty_corpus(self):
        self.assertEqual(he.partition([], seed="s"), ([], []))


class ExclusionDensityTest(unittest.TestCase):
    def test_counts_blockquotes_and_drift_ok(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.md"
            p.write_text(
                "> historical evidence=47\n"   # blockquote -> excluded
                "plain line\n"
                "stale 3ゲート <!-- drift-ok -->\n"  # marker -> excluded
                "another plain line\n",
                encoding="utf-8",
            )
            stats = he.exclusion_density([p])
        self.assertEqual(stats["lines"], 4)
        self.assertEqual(stats["excluded"], 2)
        self.assertAlmostEqual(stats["density"], 0.5)

    def test_missing_file_is_ignored(self):
        self.assertEqual(he.exclusion_density([ROOT / "nope.md"])["lines"], 0)


class SyntheticDetectorTest(unittest.TestCase):
    """Inject a detector whose findings we control, to prove the signal fires."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self._saved_corpus = dict(he.CORPORA)
        self._saved_detectors = dict(he.DETECTORS)
        self.addCleanup(self._restore)

    def _restore(self):
        he.CORPORA.clear()
        he.CORPORA.update(self._saved_corpus)
        he.DETECTORS.clear()
        he.DETECTORS.update(self._saved_detectors)

    def _install(self, files):
        he.CORPORA["fake"] = lambda: sorted(files)
        he.DETECTORS["fake"] = {
            "corpus": "fake",
            "fn": self._count_bad,
            "unit": "lines",
        }

    @staticmethod
    def _count_bad(paths):
        lines = 0
        bad = 0
        for p in paths:
            if not Path(p).is_file():
                continue
            for line in Path(p).read_text(encoding="utf-8").splitlines():
                lines += 1
                if line.startswith("BAD"):
                    bad += 1
        return lines, bad

    def build_corpus(self, n=20, bad_text="BAD line"):
        """20 files so the file-level hold-out clears MIN_HOLDOUT_ITEMS.

        With 10 files and a 20% split the hold-out is 2 files, which falls
        back to line granularity -- not what these tests are exercising.
        """
        files = []
        for i in range(n):
            p = self.dir / f"doc_{i:02d}.md"
            p.write_text("clean line\n", encoding="utf-8")
            files.append(p)
        return files

    def test_detects_overfitting(self):
        """dev clean, hold-out dirty -> OVERFIT-SUSPECTED / reject.

        This is the whole reason the instrument exists. If it cannot fire,
        it is decoration.
        """
        files = self.build_corpus()
        _dev, hold = he.partition(files, seed=he.DEFAULT_SEED,
                                  holdout_frac=he.DEFAULT_HOLDOUT_FRAC)
        self.assertGreaterEqual(len(hold), he.MIN_HOLDOUT_ITEMS)
        self.assertTrue(hold, "synthetic hold-out must be non-empty")
        for p in hold:
            p.write_text("BAD line\n", encoding="utf-8")  # dirty only out of sample
        self._install(files)
        r = he.evaluate("fake")
        self.assertEqual(r["status"], "OVERFIT-SUSPECTED")
        self.assertEqual(r["verdict"], "reject")
        self.assertEqual(r["dev"]["findings"], 0)
        self.assertGreater(r["holdout"]["findings"], 0)

    def test_clean_on_both_is_adopted(self):
        files = self.build_corpus()
        self._install(files)
        r = he.evaluate("fake")
        self.assertEqual(r["status"], "clean")
        self.assertEqual(r["verdict"], "adopt")

    def test_findings_on_holdout_are_rejected(self):
        files = self.build_corpus()
        for p in files:
            p.write_text("BAD line\n", encoding="utf-8")
        self._install(files)
        r = he.evaluate("fake")
        self.assertEqual(r["status"], "findings-on-holdout")
        self.assertEqual(r["verdict"], "reject")

    def test_insufficient_when_corpus_too_small(self):
        """A 2-file corpus cannot support a hold-out; say so, do not guess."""
        files = self.build_corpus(2)
        self._install(files)
        r = he.evaluate("fake")
        self.assertEqual(r["status"], "insufficient-holdout")
        self.assertEqual(r["verdict"], "insufficient")
        self.assertIn("too small", r["reason"])

    def test_exclusion_asymmetry_warns(self):
        files = self.build_corpus()
        _dev, hold = he.partition(files, seed=he.DEFAULT_SEED,
                                  holdout_frac=he.DEFAULT_HOLDOUT_FRAC)
        for p in set(files) - set(hold):  # dev only
            p.write_text("> excluded\n" * 40, encoding="utf-8")
        self._install(files)
        r = he.evaluate("fake")
        self.assertGreater(r["exclusion_asymmetry"], 0.10)
        self.assertTrue(any("skip rules" in w for w in r.get("warnings", [])))


class LineLevelFallbackTest(unittest.TestCase):
    def test_keeps_each_file_separate(self):
        """Concatenating files would let one document supply context for
        another and manufacture findings present in neither."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            sources = []
            for name, n in (("a.md", 50), ("b.md", 30)):
                p = tmp / name
                p.write_text("\n".join(f"{name} line {i}" for i in range(n)),
                             encoding="utf-8")
                sources.append(p)
            dev, hold = he.split_lines(sources, "seed", 0.2, tmp / "out")
            self.assertEqual(len(dev), 2)
            self.assertEqual(len(hold), 2)
            self.assertEqual({p.name for p in dev}, {"a.md", "b.md"})
            self.assertEqual({p.name for p in hold}, {"a.md", "b.md"})
            total = sum(len(p.read_text(encoding="utf-8").splitlines())
                        for p in dev + hold)
            self.assertEqual(total, 80)

    def test_doc_numbers_falls_back_to_line_granularity(self):
        """Its corpus is 2 files -- too small for a file-level hold-out."""
        r = he.evaluate("doc_numbers")
        self.assertEqual(r["granularity"], "line")
        self.assertIn("file-level split unusable", r["file_level_note"])
        self.assertGreater(r["holdout_lines"], 0)


class RealRepoTest(unittest.TestCase):
    def test_all_detectors_evaluate_without_error(self):
        for name in list(he.DETECTORS):
            with self.subTest(detector=name):
                r = he.evaluate(name)
                self.assertIn(r["status"], {
                    "clean", "findings-on-holdout", "OVERFIT-SUSPECTED",
                    "dev-only-findings", "insufficient-holdout",
                })
                self.assertIn(r["verdict"],
                              {"adopt", "adopt-with-caveat", "reject",
                               "insufficient"})

    def test_main_exits_zero(self):
        """An instrument, not a gate -- it must never fail the build."""
        self.assertEqual(he.main([]), 0)

    def test_unknown_detector_exits_two(self):
        self.assertEqual(he.main(["--detector", "nope"]), 2)

    def test_no_detector_is_judged_overfit(self):
        """No detector may be rejected as overfit against today's corpus.

        Scope note: asserting *zero findings* here would duplicate gate 8
        (`check_doc_numbers`), whose job is to catch stale numbers -- and it
        would then fail on every test addition, since the documented test
        count is part of the corpus. This instrument answers a different
        question: **does a detector behave the same out of sample?** A stale
        number is gate 8's business; a detector that only works on the
        partition it was tuned against is this one's.
        """
        for name in ("memo_citations", "memo_ledger_refs", "doc_numbers"):
            with self.subTest(detector=name):
                r = he.evaluate(name)
                self.assertNotEqual(r["status"], "OVERFIT-SUSPECTED", name)
                self.assertNotEqual(r["verdict"], "reject", name)


if __name__ == "__main__":
    unittest.main()
