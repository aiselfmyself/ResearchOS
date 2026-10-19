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

## Approval Round (2026-10-19, Approver — SES-955f8586)

Third session in the `PRP-001` cycle: proposer `SES-c4426c6b`, reviewer
`SES-eb670d1f`, approver `SES-955f8586`. Entry sequence per
`state/NEXT_SESSION.md`: fast-forward merge of `arena/eb670d1f-researchos`
(`631e7bf`), then `researchos_session.py claim --role approver`. The session
holds **approver only**, so it can write `state/approvals.jsonl`, its own session
record, the queue, `state/plan.md` and `state/NEXT_SESSION.md` — and not
`reports/**` or `verifications/**`. That constraint is respected rather than
worked around: this section **is** the approver's evidence log, and no second
role was claimed to route around R2.

### 1. The review was re-executed, not trusted

| Check | Result here |
| :--- | :--- |
| `scripts/validate_researchos.py --quiet` | exit 0 |
| `python3 -m unittest discover -s tests` | 49 tests, OK |
| `gitswarm/benchmarks/benchmark.py --check` | PASS on a fresh run |
| fresh `benchmark.py --json` means | greedy 5521.41 / random 12279.86 / two_opt 4739.72 / simulated_annealing 4731.96 — equal to the committed artifact |
| `readout.py` vs `readout_snapshot.json` | matches |
| `researchos_guard.py check-all` | ok=true (policy, append_only, commits, authorship) |
| `researchos_verify.py` (read-only) | 6/8 pass; `role_separation` fail = "session does not hold the verifier role" — correct: an approver must not emit `REV-*` |

`REV-001`'s `pass` is therefore reproduced. Findings F1–F6 were also reproduced
in throwaway clones (nothing in this section was written to the real branch):

- **F1 confirmed** — commit forging `Session-Id: SES-c4426c6b` / `Session-Role:
  bootstrap` that edits `scripts/researchos_guard.py` itself, followed by a
  legitimate commit: `check-all` **ok=true**. The same forgery at HEAD: rejected.
- **F2 confirmed** — `.github/workflows/verify-github-actions.yml` changed with
  **no trailers at all** on a side branch, landed with `--no-ff`: `check-all`
  **ok=true**.
- **F3 confirmed, and sharper** — `check-commits --stage land` is not a CLI
  argument (exit 2). The CI step runs under `set -euo pipefail` with no
  `continue-on-error`, so the first push to `main` will turn that job **red**; and
  `gh run list --branch main` is empty, i.e. the land gate has **never executed**,
  so it is untested rather than only mis-wired.
- **F4 confirmed** — `researchos_session.py close` on your own session makes the
  close commit fail `check-commits` with `session 'SES-…' is closed`.
- **T/U (detection works)** — tampering `benchmark_matrix.json` (`greedy = 1.0`)
  is caught by `--check`; deleting a **pre-baseline-count** line in
  `state/claims.jsonl` is caught by `check-append-only`.

### 2. New findings (A1–A5), found while approving

| ID | Severity | Finding | Evidence |
| :--- | :--- | :--- | :--- |
| **A1** | High | R4 protects only the **prefix** as of `policy/state_baseline.json` `base_commit` (`066b937`), else the file's creation commit. `state/reviews.jsonl`, `state/approvals.jsonl`, `state/review_queue.jsonl` were created at/after that point → their appended lines are unprotected | REV-001 `summary` rewritten in place (and `result`/`checks` are in the same line): `check-all` ok=true, validator exit 0 |
| **A2** | High | An approval cites `review_ids` only — never the reviewed bytes — so a justification can be replaced after the fact | `schemas/approval.json` has no content binding; `APR-001` records `review_line_sha256 = d1bf998f…` voluntarily as an anchor |
| **A3** | Medium | The HEAD-only identity rule mis-fires on legitimate inheritance: after the documented `git merge` and **before commit 1**, `check-all` fails with `631e7bf: session 'SES-eb670d1f' belongs to branch 'arena/eb670d1f-researchos'` | observed in this session at claim time |
| **A4** | Low | F1 × A1 compose into the real threat: forge a session whose role *may* write the ledger (no HEAD check for non-HEAD commits), rewrite the review an approval cites — every gate stays green | same reproduction as F1 + A1 |
| **A5** | High | No reconciliation path for **parallel session lines**. `arena/e7ac466a` → `47c55a23` → `e09f19e4` → `f63b6887` forked the same parent and minted their own `REV-001`/`RQ-001`/`PRP-002` | union-merging `eb670d1f` + `f63b6887` in a scratch clone → 5 conflicted state files; after a keep-both-lines merge: **7 validator errors** (`REV-001: duplicate revision 1`, `RQ-001: revision 2 'supersedes' does not match the previous line hash`, …) while `check-all` reported **ok=true** |

The interesting asymmetry in A5: the `supersedes` **line-hash chain** caught the
collision that the append-only prefix check missed. The chain is the part worth
generalising; the static baseline is the part worth deleting.

### 3. Decision

`APR-001` = **approved**, scope-limited: *adopt the harness on `arena/*` session
branches*, with conditions C1–C6 recorded in the approval ledger (schema allows
only `approved|rejected`, so conditions live in `rationale` + `conditions`).
`main` merge withheld until `PRP-002` closes **C2 (A1)**, **C3 (A2)**, **C4
(F1/F2)** and **C6 (A5)**; C5 (A3) is advisory. Reading `REV-001` is not enough
for the next sessions: a `pass` there means "the eight required checks passed".

`reports/**` and `verifications/**` are not approver-writable, so the
PRP-002 draft spec lives here and in `state/NEXT_SESSION.md`.

### 4. State as left by this session

- `PRP-001` — `pending_review` in the proposal ledger (the approver may not
  rewrite it, R3); authoritative record is `APR-001 approved`.
- `RQ-001` — completed (by `SES-eb670d1f`).
- Nothing here enforces the conditions (a `blocking` condition is text plus
  human judgement, not a gate): honest note — the harness cannot even enforce
  what this round says it must enforce, which is the point of `PRP-002`.

### 5. One more, while writing the hand-off (A6)

`state/NEXT_SESSION.md` is generated from the ledger only (`--write`), and there is
no field in the harness for approval conditions. So the file the next session is
told to paste reads, among the "rules to obey", rule 3: *"`state/*.jsonl` は追記
のみ。既存行の編集・削除は `check-append-only` が拒否します"* — which A1 shows is
**false for the governance ledgers**, and the file is marked "手動で編集しないで
ください", so a compliant approver cannot correct it. The generated hand-off also
lists `PRP-001` as `pending_review` (the proposer's own status field, which R3
forbids an approver to rewrite) and "承認待ち: なし".

| ID | Severity | Finding |
| :--- | :--- | :--- |
| **A6** | Medium | The only hand-off channel a session is guaranteed to read is regenerated from data that cannot express conditions or corrections, and is protected from editing. Conditions recorded in `APR-001` are invisible to it. `PRP-002` should give `researchos_next.py` a `--notes` / conditions source (read `state/approvals.jsonl[].conditions`) instead of leaving the prompt purely derived from statuses. |

**Therefore, to whoever opens the next session:** paste `state/NEXT_SESSION.md`,
then read `state/approvals.jsonl` (`APR-001`, conditions C1–C6) and this plan
section before writing `PRP-002`. The `proposer` recommendation is right; the
`check-append-only` guarantee in rule 3 is not.
