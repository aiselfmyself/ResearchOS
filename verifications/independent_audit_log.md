# Independent Audit Log (`Auditor-01`)

**Date:** 2026-10-19
**Target:** `arena/01673a58-researchos` @ `8763d08`
**Branch:** `arena/c4426c6b-researchos`
**Environment:** Python 3.11.2, git 2.39.5, gh 2.23.0, Linux x86_64

This log records the commands and observations of the follow-up independent
verification. It is intentionally terse; interpretation lives in
`reports/independent-verification-report.md`.

---

## 1. Merge the predecessor branch

```console
$ git fetch origin arena/01673a58-researchos
$ git merge origin/arena/01673a58-researchos \
    -m "merge: 前セッション (arena/01673a58-researchos) の成果と研究状態を統合"
Updating f0f3a47..8763d08
Fast-forward
 39 files changed, 2452 insertions(+)
```

The predecessor tip was `8763d08` (22 commits, 40 tracked files).

---

## 2. Baseline validator (predecessor version)

```console
$ python3 scripts/validate_researchos.py
Loaded: 3 Sources, 4 Evidence, 3 Claims, 4 Verifications
✓ Schema validation PASS
✓ Referential integrity PASS
✓ Git provenance Informed-By PASS
 ALL DETERMINISTIC CHECKS PASSED
```

Observation: this PASS says nothing about types, enums, ID uniqueness, or
ancestry (see §5).

---

## 3. Benchmark re-execution

```console
$ python3 - <<'PY'
from gitswarm.benchmarks.benchmark import run_benchmarks
print(run_benchmarks())
PY
greedy                mean=5521.41  min=5039.797  max=6296.501
random                mean=12279.86 min=11581.285 max=13337.465
two_opt               mean=4739.72  min=4401.480  max=5264.448
simulated_annealing   mean=4731.96  min=4396.027  max=5264.448
```

Committed `gitswarm/artifacts/benchmark_matrix.json` (pre-audit):

| Solver | committed mean | recomputed mean | delta |
| :--- | ---: | ---: | ---: |
| greedy | 5320.14 | 5521.41 | +201.27 |
| random | 13150.80 | 12279.86 | −870.94 |
| two_opt | 4792.40 | 4739.72 | −52.68 |
| simulated_annealing | 4410.25 | 4731.96 | +321.71 |

Determinism check: two runs with `PYTHONHASHSEED=1` and `PYTHONHASHSEED=2`
produced identical means. The discrepancy is not nondeterminism; the committed
values were hard-coded.

Per-seed SA vs two_opt:

| Seed | two_opt | SA | improvement |
| ---: | ---: | ---: | ---: |
| 42 | 4584.578 | 4551.257 | 0.727% |
| 100 | 4401.480 | 4396.027 | 0.124% |
| 777 | 5264.448 | 5264.448 | 0.000% |
| 999 | 4863.180 | 4863.180 | 0.000% |
| 2026 | 4584.903 | 4584.903 | 0.000% |

Mean improvement: **0.164%**.

Code inspection:

```console
$ grep -n "benchmark_summary\|run_benchmarks" gitswarm/run_simulation.py
# pre-audit: a literal dict is assigned; run_benchmarks() is never called
```

---

## 4. Readout scope

```console
$ python3 gitswarm/readout.py        # pre-audit: whole history
Total Swarm Contributions: 9
Candidate Solutions: 7
- Contribution Reuse Rate: 85.7% (6/7)
- Negative Result Citation Rate: 100.0% (1/1)
- Winner Ancestry Coverage: 57.1% (4/7)

$ python3 gitswarm/readout.py --path gitswarm   # post-fix default
Total Swarm Contributions: 7
Candidate Solutions: 5
- Contribution Reuse Rate: 100.0% (5/5)
- Negative Result Citation Rate: 100.0% (1/1)
- Winner Ancestry Coverage: 80.0% (4/5)
```

Cause: `^\[(Worker-[^\]]+)\]` also matches the ResearchOS role-play commits
`[Worker-01]` / `[Worker-02]` in `state/`. Path-scoping removes them.

---

## 5. Negative tests against the predecessor validator

| Input | Expected | Predecessor | Hardened |
| :--- | :--- | :---: | :---: |
| `confidence: "banana"` | reject | PASS (bug) | reject |
| `year: "2026"` | reject | PASS (bug) | reject |
| `authors: "not-a-list"` | reject | PASS (bug) | reject |
| duplicate `evidence_id` | reject | PASS (bug) | reject |
| non-ancestor `Informed-By` | reject | PASS (bug) | reject |

The non-ancestor test creates a sibling branch commit, cites it from another
branch, then merges both into `HEAD`. `git log` contains the cited commit, but
`git merge-base --is-ancestor` is false. The hardened validator reports:

```
Commit <sha> cites non-ancestor Informed-By SHA: '<ref>' resolves to <sha>
which is not an ancestor
```

---

## 6. Source metadata check (2026-10-19 UTC)

| Source | Pre-audit author field | arXiv metadata |
| :--- | :--- | :--- |
| SRC-001 | Akshat Gupta, et al. | **Qizheng Zhang**, Changxiu Ji, Isaac Sun, … (18 authors) |
| SRC-002 | Vedant Shah, … (14) | Vedant Shah, Ankur Samanta, … (14) — correct |
| SRC-003 | Zichuan Lin, et al. | **Shubham Agarwal**, Akshat Gupta, Mike Heddes, … (24 authors) |

`Akshat Gupta` is the second author of SRC-003, not the first author of SRC-001.
`Zichuan Lin` is not in either author list.

---

## 7. Quote fidelity check (full-text, 2026-10-19 UTC)

| Evidence | Pre-audit excerpt | Full-text result |
| :--- | :--- | :--- |
| EVD-001 | "Accumulating conversation history … catastrophic forgetting … 100+ turn tasks" | **not found** in arXiv:2610.07625v1 |
| EVD-004 | "Swarm consensus reinforces deceptive local optima" | **not found** in arXiv:2610.17184v1 |
| EVD-003 | "Any worker may inspect … equal votes resolved lexicographically" | paraphrase; actual text: "harness selects the candidate with the most nominations … deterministic tie-breaking" |
| EVD-002 / 70.1% | 70.1% cited without scope | real: 497/709, NanoChat first 24 active hours, Section 3.3 / Appendix E.4 |

All evidence records now carry `quote_type` and, where relevant, a
`correction_note`.

---

## 8. Post-fix verification

```console
$ python3 scripts/validate_researchos.py
Loaded: 4 Sources, 14 Evidence, 7 Claims, 21 Verifications, 3 Hypotheses
✓ Schema validation PASS (types, enums, required fields, items)
✓ ID uniqueness PASS
✓ Referential integrity PASS
✓ Git provenance Informed-By PASS (existence + ancestry)
 ALL DETERMINISTIC CHECKS PASSED

$ python3 -m unittest discover -s tests -v
Ran 15 tests in 1.225s
OK

$ python3 gitswarm/benchmarks/benchmark.py --check
PASS: benchmark artifact matches a fresh execution

$ python3 gitswarm/readout.py --quiet --format json \
    --output gitswarm/artifacts/readout_snapshot.json
# snapshot: 7 worker commits, 5 candidates, 100% / 100% / 80%
```

---

## 9. Artifacts changed by this audit

- `gitswarm/benchmarks/benchmark.py` — executable benchmark, `--write` / `--check`, `_meta`, `per_seed`.
- `gitswarm/artifacts/benchmark_matrix.json` — regenerated from a real run.
- `gitswarm/readout.py` — path-scoped default, JSON output, invalid-nomination detection.
- `gitswarm/artifacts/readout_snapshot.json` — frozen scoped snapshot.
- `gitswarm/run_simulation.py` — no embedded code regeneration, no hard-coded benchmark.
- `scripts/validate_researchos.py` — hardened validator.
- `schemas/hypothesis.json` — new.
- `tests/test_integrity.py` — 15 regression tests.
- `state/*.jsonl` — 4 sources / 14 evidence / 7 claims / 21 verifications / 3 hypotheses.
- `.github/workflows/verify-github-actions.yml` — runs the tests and `benchmark.py --check`.

Historical commits were not rewritten.
