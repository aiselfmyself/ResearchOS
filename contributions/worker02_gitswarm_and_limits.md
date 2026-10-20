# Worker-02 Contribution: GitSwarm Architecture & Boundary Conditions

## Key Strengths
1. **Compounding Inference (累積推論):**
   - 従来のエージェントは独立試行の「成功／失敗」のみを記録し、道中の計算は破棄されていた。
   - GitSwarm はコミットとして保存し、94.7%が後続に再利用される。
2. **Negative Results の価値:**
   - 失敗コミットが 70.1% 引用され、後続ワーカーの「無駄な探索の回避」に直接貢献する。

## Critical Boundary Limitations
1. **多数決の危険性:** GitSwarm は「決定論的多重度推薦（Plurality Readout）」を採用しているが、これは証明問題やベンチマークのように解の正しさが後から確認できる課題で有効。
2. **文献調査・社会科学への適用限界:** 自然言語主体の研究で同質モデルに多数決をとらせると、共通のハルシネーションや偏見が最多得票になりうる。
