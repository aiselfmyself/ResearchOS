# ResearchOS Plan: Long-Horizon Agent Architectures

## Problem Decomposition
1. **Subtask 1 (Stateless Architecture):** Examine how externalizing state from LLM conversation memory enables long-horizon exploration without context saturation. (Target: arXiv:2610.07625)
2. **Subtask 2 (Decentralized Compounding):** Investigate GitSwarm's branching shared-repository memory and atomic commit model. Identify both strengths and boundary limitations. (Target: arXiv:2610.04862)
3. **Subtask 3 (Adversarial Critique & Verification):** Test whether swarm consensus is vulnerable to common-mode failure, evaluator drift, and proxy metric corruption. (Target: arXiv:2610.17184, arXiv:2609.15983)
4. **Subtask 4 (Synthesis):** Formulate the ResearchOS Hybrid Paradigm reconciling role-based supervision with decentralized compounding inference.

## Allocation
- Worker-01 -> Subtask 1 (Stateless Harnesses)
- Worker-02 -> Subtask 2 (GitSwarm Compounding & Boundary Limits)
- Critic -> Subtask 3 (Falsification & Adversarial Attack)
- Verifier -> Mechanical, schema, and citation verification
- Integrator -> Subtask 4 (Final Synthesis Report)

## Independent Verification Round (2026-10-19, Auditor-01)

Triggered as a follow-up worker on `arena/c4426c6b-researchos` after merging
`arena/01673a58-researchos` (8763d08). The goal is adversarial verification of the
prior session's artifacts, not a re-run of the same happy path.

1. **Reproduce the deterministic core.** Run `scripts/validate_researchos.py` and
   confirm the reported PASS.
2. **Re-execute the GitSwarm benchmark.** Compare `gitswarm/artifacts/benchmark_matrix.json`
   with a fresh run of the committed solvers and seeds.
3. **Re-run the readout under two scopes.** Whole-repository vs `gitswarm/`-scoped,
   and quantify the difference.
4. **Verify source metadata and quote fidelity.** Fetch the three arXiv papers and
   compare titles, author lists, and verbatim excerpts against `state/`.
5. **Attack the validator.** Negative-test schema types/enums and non-ancestor
   `Informed-By` references.
6. **Record corrections and prevent regressions.** Update `state/`, harden the
   validator, add unit tests and CI drift checks, and write an independent report.

## Governance Round (2026-10-19, Proposer)

Implements the three recommendations from the independent audit. Session launch
itself is frozen: Arena.ai chats are opened by a human, and the harness produces
a paste-ready hand-off prompt instead.

1. **Separation of duties.** `state/sessions.jsonl` binds a session to a branch,
   `policy/roles.json` defines path allowlists, and `scripts/researchos_guard.py`
   enforces commit trailers, path permissions, and `git blame` authorship.
2. **Append-only state.** Corrections are new lines with `revision` and
   `supersedes`; `check-append-only` rejects edits, deletions, and reordering.
3. **Independent review trigger.** `state/review_queue.jsonl` plus
   `scripts/researchos_verify.py` and `scripts/researchos_next.py` turn a
   proposal into a reviewable, claimable, reproducible unit.

Proposal `PRP-001` is `pending_review`. This session installed the harness
(bootstrap) and proposed it; it must not review or approve it. The next session
should claim the verifier role; a third session (or a human) approves.

## Verification Round (2026-10-19, Verifier — SES-eb670d1f)

Adversarial verification of `PRP-001` from a session other than the proposer.
Method: re-run the standard suite, then *attack* the harness in throwaway clones
to see whether it fails when it should. Log:
`verifications/verifier_eb670d1f_audit_log.md`; summary for approvers:
`reports/verification-prp-001-review.md`.

1. **Reproduce the standard suite.** 8/8 pass (`REV-001`).
2. **Confirm the benchmark is really executed.** Fresh run reproduces the
   committed matrix (greedy 5521.41 / random 12279.86 / two_opt 4739.72 /
   SA 4731.96); tampering the artifact or `per_seed` fails `--check`.
3. **Re-check the corrected metadata against primary sources.** SRC-001/002/003
   author lists match arXiv (18/14/23 authors).
4. **Attack the guard.** 7 ordinary violations are all caught (verifier writing
   `scripts/`, verifier writing `state/claims.jsonl`, missing trailers, unknown
   session, unheld role, edited state line, deleted state file), as are
   self-review, append-only violations, and forged record authorship (R5).
5. **Found gaps the suite cannot see.** F1 (High): `Session-Id` is self-declared
   and the branch binding is enforced for HEAD only, so a commit can impersonate
   another session — demonstrated by disabling the guard itself under a forged
   bootstrap identity with `check-all` returning ok. F2 (High): merge commits are
   skipped and `--first-parent` hides side-branch commits, so governance paths can
   be landed without trailers or a proposal. F3 (Medium): the CI land gate
   `check-commits --stage land` is not a CLI argument and exits 2. F4 (Medium):
   `researchos_session.py close` on your own session breaks `check-commits`.
6. **Follow-up required.** F1-F4 need a separate proposal (`PRP-002`) written by a
   proposer session; a verifier may not touch `scripts/`. Until `PRP-002` lands,
   the human merge to `main` remains the only effective gate.

`PRP-001` is reviewed (`REV-001`, pass with conditions) and waits for an approver
session that is neither `SES-c4426c6b` nor `SES-eb670d1f`.
