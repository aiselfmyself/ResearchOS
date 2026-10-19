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
