# SVM 単一ワーカー実施報告（2026-10-21）

- 対象：`docs/single-vs-multi-experiment-2026-10-21.md` §4–§5 の全51項目。分岐元：`58d5f289d3818b9fe3a7e9a990f168718fb7f10b`。
- 一次資料：`https://arxiv.org/abs/2609.37633v2` および `https://arxiv.org/html/2609.37633v2` のみ。HTML 冒頭の版表記は **`arXiv:2609.37633v2 [cs.LG] 19 Oct 2026`**（fetch 表示では `[cs.LG]` はエスケープ付き）。abs の Submission history も v2 の改訂日を示した。PDF は使っていない。
- JSON は Q01–Q51 を各1件、項目表の型で回答した。根拠は各 `location` に記載。見つからず `null` にした項目はない。他アームのブランチ・PR・成果物は見ていない。

## 迷った点・取得時の注意

1. HTML の数式・単位のレンダリングが重複する箇所がある。Table 2 の重複除去 SFTL;DR 行の Backward Tokens は fetch 表示で `6868k` と見えるが、同じ §5.2 の本文には明確に `68k backwards (insight) tokens` とあり、表の重複レンダリングと判断して Q33 を **68,000**（`k`→×1,000）とした。Table 3 の対象行の `03.4%` も §6 本文の `3.4` と照合して Q36 を **3.4** とした。どちらも別版・別論文から補っていない。
2. Q27 は §4.1 Baselines で導入される3手法に限定し、`Strategy-guided Exploration (SGE)` は名称＋略称を1要素にまとめた。Q39 は Appendix A.3.1 の直下の見出しを3つ数えた。「Removing the standard deviation」は本文では Dr. GRPO に言及するが、項目の数え方（当該小節の各冒頭見出し）を優先して含めた。
3. Q35 の §6 冒頭の引用文は Appendix C.1 Table 5 の類似例と語句が異なる（`instead of just viewing it` 対 `rather than just viewing it`）。§6 冒頭の原文のみを転記した。Q43 は Table 8 行に続く脚注の **update 75** を採り、脚注番号らしいレンダリング文字列 `111` は値にしなかった。
4. 構造物の数は見出し・キャプションの実体のみを数えた（Q07: §1–§8、Q08: Appendix A–F、Q09: Table 1–9、Q10: Figure 1–13）。本文中の参照、Appendix Contents、表・図中の `(a)` 等は加算していない。

## 運用上の記録

Arena web fetch で HTML 全16チャンクと abs 冒頭を取得した。HTML の重複表示は本文との照合で解消できたため PDF への切り替えは不要だった。セッションログのツール回数は**成果物の内容確定まで**の自己申告（ゲート実行・PR操作は含まない）。UI 上のモデル名は確認できず `unknown` と記録する。設計文書の状態欄は「提案」のままで、D2 の承認可否は本アームでは判定していない。

台帳 `state/`・既存メモ・コード・設計文書は変更しない。この抽出を文献台帳に登録するなら、比較実験の全出力固定・評価後に、別の判断と別 PR で扱うことを提案する。8つのゲート結果は PR 本文に記録する。
