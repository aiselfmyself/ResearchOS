# Worker-01 Contribution: Stateless Language Agents Analysis

## Findings
1. **会話履歴肥大化の弊害:** トークンコスト増加だけでなく、モデルが過去の自身の出力（特に中間的な誤りや迷走）にアテンションを奪われ、探索が硬直化する「Inference-time Sinkhole」が発生する。
2. **Stateless Harness の構造:**
   - 永続正本: ファイルシステム / 構造化State
   - モデルへの入力: 「現在のタスク定義 + 直近の観測 + 参照すべき証拠抜粋」のみ
3. **ResearchOS への示唆:**
   - ResearchOS Core が設計原則としている「会話履歴と永続研究状態の分離」は、最新の学術的発見（arXiv:2610.07625）と完全に一致している。
