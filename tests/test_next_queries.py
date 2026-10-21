"""Regression tests for scripts/next_queries.py and the questions overlay.

Phase 2 of docs/2026-10-21_hypothesis-cycle-automation.md is the S0/S7
planner: turn each hypothesis's ``next_literature_questions`` into a concrete
query, weight it by the gap_scan measurement, and never propose a search that
the log shows was already run.

The properties pinned here, all on SYNTHETIC ledgers unless the test says
``RealRepoTest``:

  * the query rule is deterministic: lower-case, split on non-alphanumerics,
    keep hyphenated compounds, drop stopwords/duplicates, cap at --max-terms;
  * a hypothesis with no questions is *reported and skipped*, never planned
    from the legacy ``next_observations`` field;
  * questions come from the record when it has them, from the overlay when it
    does not, and the overlay may never shadow a record;
  * priority is 1 + the number of ``unresolved`` relations, and ``derived_from``
    names the hypothesis plus those relations;
  * a planned query that the search log already contains is moved to
    ``already_searched`` (exact or subset match), not proposed again;
  * coverage queries are built only from an explicit ``observation_key``; an
    unexplained observation without one is counted, never invented;
  * the planner is an instrument: exit 0 for any completed plan, 2 only for
    usage / I/O, and the ledgers are never written to.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT, ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import hypothesis_questions as hq  # noqa: E402
import next_queries as nq  # noqa: E402
import validate_state as vs  # noqa: E402


# --------------------------------------------------------------------------
# Fixture helpers
# --------------------------------------------------------------------------
def hyp(hypothesis_id: str, questions=None, **overrides) -> dict:
    record = {
        "hypothesis_id": hypothesis_id,
        "statement": "synthetic statement",
        "status": "proposed",
    }
    if questions is not None:
        record["next_literature_questions"] = questions
    record.update(overrides)
    return record


def evd(evidence_id: str, key=None, source_id: str = "SRC-A") -> dict:
    record = {
        "evidence_id": evidence_id,
        "source_id": source_id,
        "excerpt": "synthetic excerpt",
        "interpretation": "synthetic interpretation",
        "confidence": "high",
    }
    if key is not None:
        record["observation_key"] = key
    return record


def rel(relation_id: str, hypothesis_id: str, evidence_id: str, verdict: str = "support", **overrides) -> dict:
    record = {
        "relation_id": relation_id,
        "hypothesis_id": hypothesis_id,
        "observation_id": evidence_id,
        "verdict": verdict,
    }
    record.update(overrides)
    return record


def qry(query_id: str, text: str) -> dict:
    return {
        "query_id": query_id,
        "query": text,
        "executed_at": "2026-10-21",
        "channel": "keyword",
        "hits": 1,
    }


def write_jsonl(path: Path, records) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record) + "\n")


def make_state(
    tmp: str,
    *,
    hypotheses,
    evidence=(),
    relations=(),
    search_log=(),
    overlay=None,
) -> Path:
    state = Path(tmp) / "state"
    state.mkdir(parents=True, exist_ok=True)
    write_jsonl(state / "hypotheses.jsonl", hypotheses)
    write_jsonl(state / "evidence.jsonl", evidence)
    write_jsonl(state / "relations.jsonl", relations)
    write_jsonl(state / "search_log.jsonl", search_log)
    if overlay is not None:
        write_jsonl(state / "hypothesis_questions.jsonl", overlay)
    return state


def run_cli(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = nq.main(args)
    return code, out.getvalue(), err.getvalue()


def report_for(hypotheses, evidence=(), relations=(), search_log=(), overlay=None, **kwargs):
    return nq.plan(
        list(hypotheses),
        list(evidence),
        list(relations),
        list(search_log),
        {} if overlay is None else overlay,
        **kwargs,
    )


# --------------------------------------------------------------------------
# Text -> query
# --------------------------------------------------------------------------
class TokenizerTest(unittest.TestCase):
    def test_lowercases_and_splits_on_punctuation(self):
        self.assertEqual(
            nq.tokenize("Does LLM self-preference, matter?"),
            ["does", "llm", "self-preference", "matter"],
        )

    def test_hyphenated_compounds_stay_one_token(self):
        self.assertEqual(
            nq.tokenize("long-horizon out-of-distribution"),
            ["long-horizon", "out-of-distribution"],
        )

    def test_drops_stopwords_and_duplicates_but_keeps_order(self):
        terms = nq.query_terms("The harness and the harness effect on the model")
        self.assertEqual(terms, ["harness", "effect", "model"])

    def test_respects_max_terms(self):
        sentence = "alpha beta gamma delta epsilon zeta eta theta"
        self.assertEqual(nq.query_terms(sentence, 3), ["alpha", "beta", "gamma"])

    def test_question_without_content_terms_has_no_query(self):
        self.assertIsNone(nq.build_query("自己選好は課題型に依存するか"))
        self.assertIsNone(nq.build_query("the and of to"))

    def test_build_query_joins_the_surviving_terms(self):
        self.assertEqual(
            nq.build_query("Do judge panels reduce common-mode errors?"),
            "judge panels reduce common-mode errors",
        )

    def test_normalise_query_matches_the_generated_form(self):
        self.assertEqual(
            nq.normalise_query("Self-Preference, LLM  evaluator"),
            nq.normalise_query("self-preference llm evaluator"),
        )


# --------------------------------------------------------------------------
# Overlay
# --------------------------------------------------------------------------
class OverlayLoadTest(unittest.TestCase):
    def test_missing_overlay_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            overlay, errors = hq.load(Path(tmp) / "state" / "hypothesis_questions.jsonl")
        self.assertEqual(overlay, {})
        self.assertEqual(errors, [])

    def test_reads_and_strips_questions(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(
                tmp,
                hypotheses=[hyp("HYP-1")],
                overlay=[{"hypothesis_id": "HYP-1", "questions": ["  a question  "]}],
            )
            overlay, errors = hq.load(state / "hypothesis_questions.jsonl")
        self.assertEqual(errors, [])
        self.assertEqual(overlay, {"HYP-1": ["a question"]})

    def test_shard_without_base_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state" / "hypothesis_questions.jsonl"
            write_jsonl(
                Path(tmp) / "state" / "hypothesis_questions.d" / "2026-10-21-abcdef123456.jsonl",
                [{"hypothesis_id": "HYP-1", "questions": ["q"]}],
            )
            overlay, errors = hq.load(path)
        self.assertEqual(overlay, {})
        self.assertTrue(any("base file not found" in e for e in errors), errors)

    def test_record_without_hypothesis_id_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp, hypotheses=[], overlay=[{"questions": ["q"]}])
            overlay, errors = hq.load(state / "hypothesis_questions.jsonl")
        self.assertEqual(overlay, {})
        self.assertTrue(any("hypothesis_id" in e for e in errors), errors)

    def test_empty_questions_are_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(
                tmp,
                hypotheses=[],
                overlay=[{"hypothesis_id": "HYP-1", "questions": []}],
            )
            _, errors = hq.load(state / "hypothesis_questions.jsonl")
        self.assertTrue(any("questions" in e for e in errors), errors)

    def test_blank_question_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(
                tmp,
                hypotheses=[],
                overlay=[{"hypothesis_id": "HYP-1", "questions": ["ok", "  "]}],
            )
            overlay, errors = hq.load(state / "hypothesis_questions.jsonl")
        self.assertEqual(overlay, {})
        self.assertTrue(any("non-empty string" in e for e in errors), errors)

    def test_duplicate_hypothesis_records_are_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(
                tmp,
                hypotheses=[],
                overlay=[
                    {"hypothesis_id": "HYP-1", "questions": ["first"]},
                    {"hypothesis_id": "HYP-1", "questions": ["second"]},
                ],
            )
            overlay, errors = hq.load(state / "hypothesis_questions.jsonl")
        self.assertEqual(overlay, {"HYP-1": ["first"]})
        self.assertTrue(any("duplicate overlay record" in e for e in errors), errors)


class OverlayCheckTest(unittest.TestCase):
    def test_unknown_hypothesis_is_an_error(self):
        errors = hq.check({"HYP-NOPE": ["q"]}, [hyp("HYP-1")])
        self.assertTrue(any("unknown hypothesis_id" in e for e in errors), errors)

    def test_shadowing_a_record_is_an_error(self):
        errors = hq.check({"HYP-1": ["q"]}, [hyp("HYP-1", ["own question"])])
        self.assertTrue(any("must not shadow" in e for e in errors), errors)

    def test_valid_overlay_passes(self):
        errors = hq.check({"HYP-1": ["q"]}, [hyp("HYP-1")])
        self.assertEqual(errors, [])

    def test_record_wins_when_it_has_questions(self):
        questions, source = hq.questions_for(hyp("HYP-1", ["own"]), {"HYP-1": ["overlay"]})
        self.assertEqual(questions, ["own"])
        self.assertEqual(source, "record")

    def test_overlay_is_used_when_the_record_has_none(self):
        questions, source = hq.questions_for(hyp("HYP-1"), {"HYP-1": ["overlay"]})
        self.assertEqual(questions, ["overlay"])
        self.assertEqual(source, "overlay")

    def test_none_when_neither_has_questions(self):
        questions, source = hq.questions_for(hyp("HYP-1"), {})
        self.assertIsNone(questions)
        self.assertEqual(source, "none")

    def test_an_empty_record_list_does_not_block_the_overlay(self):
        questions, source = hq.questions_for(hyp("HYP-1", []), {"HYP-1": ["overlay"]})
        self.assertEqual(questions, ["overlay"])
        self.assertEqual(source, "overlay")


# --------------------------------------------------------------------------
# Planning
# --------------------------------------------------------------------------
class PlanTest(unittest.TestCase):
    def test_one_question_becomes_one_keyword_query(self):
        report = report_for(
            [hyp("HYP-1", ["Do judge panels reduce common-mode errors?"])]
        )
        self.assertEqual(len(report["queries"]), 1)
        entry = report["queries"][0]
        self.assertEqual(entry["query"], "judge panels reduce common-mode errors")
        self.assertEqual(entry["channel"], "keyword")
        self.assertEqual(entry["kind"], "hypothesis")
        self.assertEqual(entry["hypothesis_ids"], ["HYP-1"])
        self.assertEqual(entry["source_questions"], ["Do judge panels reduce common-mode errors?"])
        self.assertEqual(entry["derived_from"], ["HYP-1"])

    def test_hypothesis_without_questions_is_reported_and_skipped(self):
        report = report_for([hyp("HYP-1"), hyp("HYP-2", ["a real question"])])
        self.assertEqual(report["totals"]["hypotheses_without_questions"], 1)
        reasons = {item["hypothesis_id"]: item["reason"] for item in report["skipped"]}
        self.assertEqual(reasons, {"HYP-1": "no_questions"})

    def test_legacy_next_observations_is_never_read(self):
        record = hyp("HYP-1", next_observations=["文献: 何かを探す"])
        report = report_for([record])
        self.assertEqual(report["queries"], [])
        self.assertEqual(report["skipped"][0]["reason"], "no_questions")

    def test_unsearchable_question_is_reported(self):
        report = report_for([hyp("HYP-1", ["自己選好は課題型に依存するか"])])
        self.assertEqual(report["queries"], [])
        self.assertEqual(report["totals"]["skipped_no_terms"], 1)
        self.assertEqual(report["skipped"][0]["reason"], "no_terms")

    def test_priority_is_one_plus_the_open_verdicts(self):
        report = report_for(
            [hyp("HYP-1", ["a real question"])],
            evidence=[evd("EVD-1")],
            relations=[
                rel("REL-1", "HYP-1", "EVD-1", "unresolved"),
                rel("REL-2", "HYP-1", "EVD-1", "unresolved"),
                rel("REL-3", "HYP-1", "EVD-1", "support"),
            ],
        )
        entry = report["queries"][0]
        self.assertEqual(entry["priority"], 3)
        self.assertEqual(entry["weight_reasons"], {"unresolved_relations": 2})
        self.assertEqual(entry["derived_from"], ["HYP-1", "REL-1", "REL-2"])

    def test_higher_priority_sorts_first(self):
        report = report_for(
            [hyp("HYP-1", ["zeta question"]), hyp("HYP-2", ["alpha question"])],
            evidence=[evd("EVD-1")],
            relations=[rel("REL-1", "HYP-2", "EVD-1", "unresolved")],
        )
        self.assertEqual(
            [entry["hypothesis_ids"] for entry in report["queries"]],
            [["HYP-2"], ["HYP-1"]],
        )

    def test_identical_queries_merge_their_provenance(self):
        report = report_for(
            [
                hyp("HYP-1", ["Do judge panels reduce errors?"]),
                hyp("HYP-2", ["Do judge panels reduce errors?"]),
            ]
        )
        self.assertEqual(len(report["queries"]), 1)
        entry = report["queries"][0]
        self.assertEqual(entry["hypothesis_ids"], ["HYP-1", "HYP-2"])
        self.assertEqual(len(entry["source_questions"]), 1)
        self.assertEqual(entry["derived_from"], ["HYP-1", "HYP-2"])

    def test_limit_truncates_and_counts(self):
        report = report_for(
            [hyp("HYP-1", ["alpha question", "beta question", "gamma question"])],
            limit=2,
        )
        self.assertEqual(len(report["queries"]), 2)
        self.assertEqual(report["totals"]["truncated"], 1)

    def test_review_variant_is_one_per_hypothesis(self):
        report = report_for(
            [hyp("HYP-1", ["first question", "second question"])],
            with_review=True,
        )
        channels = [entry["channel"] for entry in report["queries"]]
        self.assertEqual(channels.count("review"), 1)
        review = [e for e in report["queries"] if e["channel"] == "review"][0]
        self.assertEqual(review["query"], "first question survey")
        self.assertEqual(review["variant_of"], "first question")

    def test_plan_is_deterministic_and_does_not_mutate_inputs(self):
        hypotheses = [hyp("HYP-1", ["a question"]), hyp("HYP-2")]
        evidence = [evd("EVD-1")]
        relations = [rel("REL-1", "HYP-1", "EVD-1", "unresolved")]
        before = json.dumps([hypotheses, evidence, relations], sort_keys=True)
        first = report_for(hypotheses, evidence, relations)
        second = report_for(hypotheses, evidence, relations)
        after = json.dumps([hypotheses, evidence, relations], sort_keys=True)
        self.assertEqual(first, second)
        self.assertEqual(before, after)


class SearchLogTest(unittest.TestCase):
    def test_exact_match_moves_the_query_to_already_searched(self):
        report = report_for(
            [hyp("HYP-1", ["Do judge panels reduce errors?"])],
            search_log=[qry("QRY-1", "judge panels reduce errors")],
        )
        self.assertEqual(report["queries"], [])
        self.assertEqual(report["already_searched"][0]["query_ids"], ["QRY-1"])
        self.assertEqual(report["already_searched"][0]["match"], "exact")

    def test_normalised_match_ignores_case_and_punctuation(self):
        report = report_for(
            [hyp("HYP-1", ["Do judge panels reduce errors?"])],
            search_log=[qry("QRY-1", "Judge: panels. reduce, ERRORS?")],
        )
        self.assertEqual(report["queries"], [])
        self.assertEqual(report["already_searched"][0]["match"], "exact")

    def test_subset_match_counts_as_covered(self):
        report = report_for(
            [hyp("HYP-1", ["Do judge panels reduce errors?"])],
            search_log=[qry("QRY-1", "judge panels reduce errors in blind review")],
        )
        self.assertEqual(report["queries"], [])
        self.assertEqual(report["already_searched"][0]["match"], "subset")

    def test_a_single_word_query_is_not_treated_as_covered(self):
        # "judge" is a subset of the executed query, but one word is too
        # generic to count as covered -- the plan must keep it.
        report = report_for(
            [hyp("HYP-1", ["judge"])],
            search_log=[qry("QRY-1", "judge panels reduce errors")],
        )
        self.assertEqual(len(report["queries"]), 1)
        self.assertEqual(report["already_searched"], [])

    def test_unrelated_query_does_not_hide_the_plan(self):
        report = report_for(
            [hyp("HYP-1", ["Do judge panels reduce errors?"])],
            search_log=[qry("QRY-1", "self-preference LLM evaluator")],
        )
        self.assertEqual(len(report["queries"]), 1)
        self.assertEqual(report["already_searched"], [])


class CoverageTest(unittest.TestCase):
    def test_an_explicit_key_produces_a_coverage_query(self):
        report = report_for(
            [hyp("HYP-1", ["a question"])],
            evidence=[evd("EVD-1", key="externalized_memory_compounding")],
        )
        coverage = [e for e in report["queries"] if e["kind"] == "coverage"]
        self.assertEqual(len(coverage), 1)
        self.assertEqual(coverage[0]["query"], "externalized memory compounding")
        self.assertEqual(coverage[0]["derived_from"], ["EVD-1"])
        self.assertEqual(report["coverage"]["with_seed"], 1)

    def test_an_observation_without_a_key_is_counted_not_invented(self):
        report = report_for(
            [hyp("HYP-1", ["a question"])],
            evidence=[evd("EVD-1"), evd("EVD-2", key="shared_key")],
        )
        self.assertEqual(report["coverage"]["without_seed"], ["EVD-1"])
        self.assertEqual(
            [e["query"] for e in report["queries"] if e["kind"] == "coverage"],
            ["shared key"],
        )

    def test_coverage_can_be_disabled(self):
        report = report_for(
            [hyp("HYP-1", ["a question"])],
            evidence=[evd("EVD-1", key="a_key")],
            include_coverage=False,
        )
        self.assertEqual(report["coverage"]["queries"], 0)
        self.assertFalse(report["coverage"]["enabled"])
        self.assertEqual(
            [e["kind"] for e in report["queries"]], ["hypothesis"]
        )

    def test_coverage_queries_sort_after_hypothesis_queries_at_equal_priority(self):
        # One open verdict lifts the hypothesis query to priority 2; the
        # coverage query is 1 + one unexplained observation = 2 as well.
        report = report_for(
            [hyp("HYP-1", ["a question"])],
            evidence=[evd("EVD-1", key="a_key"), evd("EVD-2")],
            relations=[rel("REL-1", "HYP-1", "EVD-2", "unresolved")],
        )
        self.assertEqual(
            [entry["kind"] for entry in report["queries"]],
            ["hypothesis", "coverage"],
        )


class ReportShapeTest(unittest.TestCase):
    def test_totals_account_for_every_question(self):
        report = report_for(
            [
                hyp("HYP-1", ["a question", "自己選好の問い"]),
                hyp("HYP-2"),
            ],
            search_log=[qry("QRY-1", "another question")],
        )
        totals = report["totals"]
        self.assertEqual(totals["questions"], 2)
        # one planned + one no_terms; nothing is silently dropped
        self.assertEqual(
            totals["planned"] + totals["already_searched"] + totals["skipped_no_terms"],
            totals["questions"],
        )

    def test_json_round_trip(self):
        report = report_for([hyp("HYP-1", ["a question"])])
        self.assertEqual(json.loads(json.dumps(report)), report)


# --------------------------------------------------------------------------
# CLI and the real repository
# --------------------------------------------------------------------------
class CliContractTest(unittest.TestCase):
    def test_exit_zero_when_nothing_can_be_planned(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp, hypotheses=[hyp("HYP-1")])
            code, out, _ = run_cli(["--state-dir", str(state)])
        self.assertEqual(code, 0)
        self.assertIn("計画: 0 件", out)
        self.assertIn("no_questions", out)

    def test_json_output_is_valid_and_reports_the_same_totals(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp, hypotheses=[hyp("HYP-1", ["a question"])])
            code, out, _ = run_cli(["--state-dir", str(state), "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["totals"]["planned"], 1)
        # "a" is a stopword; the query is what survives the rule.
        self.assertEqual(payload["queries"][0]["query"], "question")

    def test_missing_state_directory_is_exit_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run_cli(["--state-dir", str(Path(tmp) / "nope")])
        self.assertEqual(code, 2)
        self.assertIn("state directory not found", err)

    def test_missing_ledger_is_exit_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state"
            state.mkdir()
            write_jsonl(state / "hypotheses.jsonl", [hyp("HYP-1")])
            code, _, err = run_cli(["--state-dir", str(state)])
        self.assertEqual(code, 2)
        self.assertIn("file not found", err)

    def test_unknown_hypothesis_is_exit_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(tmp, hypotheses=[hyp("HYP-1", ["a question"])])
            code, _, err = run_cli(
                ["--state-dir", str(state), "--hypothesis", "HYP-NOPE"]
            )
        self.assertEqual(code, 2)
        self.assertIn("unknown hypothesis_id", err)

    def test_hypothesis_filter_limits_the_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(
                tmp,
                hypotheses=[hyp("HYP-1", ["a question"]), hyp("HYP-2", ["b question"])],
            )
            code, out, _ = run_cli(
                ["--state-dir", str(state), "--json", "--hypothesis", "HYP-2"]
            )
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["totals"]["hypotheses"], 1)
        self.assertEqual(payload["queries"][0]["hypothesis_ids"], ["HYP-2"])

    def test_broken_overlay_is_exit_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(
                tmp,
                hypotheses=[hyp("HYP-1")],
                overlay=[{"hypothesis_id": "HYP-1", "questions": []}],
            )
            code, _, err = run_cli(["--state-dir", str(state)])
        self.assertEqual(code, 2)
        self.assertIn("hypothesis_questions", err)


class RealRepoTest(unittest.TestCase):
    def test_the_overlay_validates_against_the_real_hypotheses(self):
        overlay, errors = hq.load(ROOT / hq.LEDGER)
        self.assertEqual(errors, [])
        hypotheses, load_errors = vs.load_jsonl(ROOT / "state" / "hypotheses.jsonl")
        self.assertEqual(load_errors, [])
        self.assertEqual(hq.check(overlay, hypotheses), [])
        self.assertEqual(len(overlay), len(hypotheses))

    def test_the_planner_runs_on_the_real_ledgers(self):
        report = nq.measure(ROOT / "state")
        totals = report["totals"]
        self.assertEqual(totals["hypotheses"], 7)
        self.assertEqual(totals["hypotheses_without_questions"], 0)
        self.assertEqual(totals["questions"], len(report["queries"]) + totals["skipped_no_terms"] + totals["already_searched"] + totals["truncated"])
        for entry in report["queries"]:
            self.assertTrue(entry["query"].strip())
            self.assertTrue(entry["derived_from"])
            self.assertGreaterEqual(entry["priority"], 1)

    def test_every_unexplained_observation_is_accounted_for(self):
        report = nq.measure(ROOT / "state")
        coverage = report["coverage"]
        self.assertEqual(
            coverage["with_seed"] + len(coverage["without_seed"]),
            coverage["unexplained"],
        )

    def test_the_cli_does_not_modify_the_ledgers(self):
        before = {
            path.name: path.read_bytes()
            for path in (ROOT / "state").glob("*.jsonl")
        }
        code, out, _ = run_cli(["--json"])
        after = {
            path.name: path.read_bytes()
            for path in (ROOT / "state").glob("*.jsonl")
        }
        self.assertEqual(code, 0)
        self.assertEqual(before, after)
        self.assertEqual(json.loads(out)["totals"]["hypotheses"], 7)

    def test_validate_state_accepts_the_overlay(self):
        report = vs.run_all_checks(ROOT)
        self.assertEqual(report["errors"], [], msg="\n".join(report["errors"]))

    def test_overlay_shards_follow_the_naming_convention(self):
        base = ROOT / hq.LEDGER
        import ledger_store

        for path in ledger_store.shard_files(base, ledger_store.SHARD_SUFFIX):
            self.assertRegex(path.name, r"^\d{4}-\d{2}-\d{2}-[0-9a-f]{12}\.jsonl$")


if __name__ == "__main__":
    unittest.main()
