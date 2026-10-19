# Critic / Falsifier Report: Adversarial Analysis of Swarm Consensus

## Target of Attack: Can Peer Swarms Self-Validate?
- **仮説:** 「十分な数の自律ワーカーが同一リポジトリで作業すれば、多数決・相互推薦により最善の解が自動選出される」
- **反証 (Falsification):**
  1. **Common-Mode Failure (共通モード障害):** 同一の基盤モデル（例: GPT-4o や Claude 3.5）をワーカーとして並列稼働させても、学習データのバイアス、推論の盲点、指示解釈の癖は共有される。票数を増やしても独立な証拠は増えない。
  2. **Evaluation Drift (DuoDiscover arXiv:2610.17184):** 代理評価器やエージェント相互評価は、一次資料や厳密テストへの接地（Grounding）を失うと急速にドリフトする。
- **結論:**
  ResearchOS の設計原則「多数決を正しさの代わりにしない（§5.3）」は、学術的に極めて正当。合意ではなく「反証への耐性」と「一次資料への追跡可能性」を合否基準とすべきである。
