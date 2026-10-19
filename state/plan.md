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
