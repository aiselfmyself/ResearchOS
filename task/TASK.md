# Research Task Definition: Long-Horizon Agent Architectures

## 1. Research Question
**「自律型AIエージェントにおける長期推論・分散協調アーキテクチャの最新動向（Stateless vs GitSwarm）」の学術文献調査**

## 2. Objectives
- 単一エピソードに巨大な会話履歴を詰め込む従来型アーキテクチャの限界を整理する。
- 外部化された永続メモリ（Stateless Harness）と、共有Gitリポジトリによる自律分散協調（GitSwarm）の設計思想・強み・弱点を比較する。
- 共通モード障害（Common-mode failure）、多数決の落とし穴、および独立検証（Verification）の必要性に関する知見を抽出する。

## 3. Ground Truth Requirements
- 参照文献は実在する一次資料（arXiv 等）とし、DOI/arXiv ID、著者、出版年、主要引用箇所を明記すること。
- 主張（Claim）には必ず対応する証拠（Evidence）と出典（Source）を紐付けること。
- 支持する証拠だけでなく、反証・制約条件・未解決事項（Negative findings / Counterclaims）を必ず記録すること。

## 4. Verification Protocol
- 機械的検証: `scripts/validate_state.py` による JSON スキーマ検査および参照整合性テスト（研究5台帳のみ。ガバナンス検査は2026-10-20に凍結）。
- 意味的検証: Critic / Falsifier による前提の攻撃的レビューおよび反証の記録。
- 統合: Integrator による統合レポート作成（多数決ではなく証拠の強弱に基づく論証）。
