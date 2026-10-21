# 並行アーム P2（17項目）実施メモ — 単一 vs 3並行 比較実験

- 実行日：2026-10-21
- アーム：`parallel`／ワーカー：`P2`
- ブランチ：`arena/8a4884af-researchos`
- 一次資料（固定版）：`https://arxiv.org/html/2609.37633v2`、`https://arxiv.org/abs/2609.37633v2`
- 設計文書：[`docs/single-vs-multi-experiment-2026-10-21.md`](../docs/single-vs-multi-experiment-2026-10-21.md)
- 対応 JSON：`contributions/2026-10-21_svm_parallel_p2.json`

## 1. base_commit の不一致（重要・実施報告事項）

| 項目 | 値 |
|---|---|
| 指定された共通開始コミット | `ccf76aa654c1344e7bc7862bc835cf1420c98ff8` |
| 開始時に実際に見た HEAD（= `base_commit` として記録） | `241152453378166ed66577bafe24637cc1c76f94` |
| 関係 | HEAD は `ccf76aa` の**7コミット先**。HEAD はマージコミットで第1親が `ccf76aa`、第2親が別ブランチ（PR #57）の先端 |

- 初回指示では「共通開始コミットと異なる場合は停止」であったため、開始直後に**抽出を開始せず停止**し、人間へ報告した（1回目の応答）。
- 人間の再指示（2026-10-21）により、「共通開始コミットと異なる場合は停止」の条件は**本 P2 について解除**され、「厳密な同条件比較ではなく、開始コミット不一致を伴う参考実行」として継続する指示を得た。
- 作業再開時に HEAD を再確認し、`2411524…` のまま不変であることを確認した。**checkout・reset・rebase・ブランチ再作成は行っていない**（ブランチは割当どおり `arena/8a4884af-researchos`）。
- この不一致は本実行の限界であり、厳密な同条件比較として扱えない。最終評価は X4 と人間が行う。**他アームの成果物・PR・ブランチは参照していない**ため、差分の影響評価も行っていない。

## 2. 固定版の版表示（転記）

HTML 版冒頭（`https://arxiv.org/html/2609.37633v2`）の表示：

```
arXiv:2609.37633v2 [cs.LG] 19 Oct 2026
```

abs ページ（`https://arxiv.org/abs/2609.37633v2`）の表示：

```
arXiv:2609.37633v2 (cs)
[Submitted on 29 Sep 2026 (v1), last revised 19 Oct 2026 (this version, v2)]
```

- 版付き URL が別版へ誘導される形跡はなく、**v2 を確認**した。以降 v2 のみを読んだ。PDF は使用していない（HTML 版のみ、Arena の web fetch 経由）。

## 3. 担当17項目の回答

型は設計文書 §4.1 に従う。`location` は固定版一次資料内の所在。

| ID | 型 | 値 | 所在 | conf. |
|---|---|---|---|---|
| Q02 | 日付 | `2026-10-19` | abs ページ Submission history の `[v2]` 項（Mon, 19 Oct 2026 11:45:34 UTC） | high |
| Q05 | 数値 | `12` | Abstract（abs・HTML 共通）"a Pass@1 of 14–31% with insights in context during training and, crucially, 12–13% when no insight is in context at eval time" の下限 | high |
| Q08 | 数値（整数） | `6` | References 後の見出し `Appendix A`〜`Appendix F`。`Appendix Contents` は英大文字1字でないため不算入、`A.1` 等の小節も不算入 | high |
| Q14 | 列挙 | `["advantage collapse", "the learning cliff", "exploration inefficiency"]` | §2 Related Works「The learning barrier of RLVR.」段落 | high |
| Q18 | 数値 | `0.2` | §3.1、GRPO 損失式 (3.1) 直前 "clipped with ε=0.2" | high |
| Q19 | 数値 | `50` | §3.2 第1段落 "Whenever at the k-th attempt ≤50% of the attempts 1,…,k−1 are successful, we insert all insights collected so far" | high |
| Q21 | 数値 | `0.5` | §3.3 末尾 "λ=0.5 is a good default" | high |
| Q24 | 数値（整数） | `458` | §4.1 Datasets 第2段落 "This filters down SAPI to 458 tasks" | high |
| Q29 | 数値 | `33.7` | Table 1（Pass@1 on heldout eval sets）、行 `GRPO`・列 `Appworld` | high |
| Q32 | 数値 | `17.0` | Table 2、行 `RLTL;DR, no GRPO loss, only L_SFT`・列 `Eval Pass@1` | high |
| Q35 | 短文逐語 | `You need to mark the article as read instead of just viewing it` | §6 冒頭第1段落の引用（"see Appendix C" の直前） | high |
| Q37 | 列挙（整数） | `[1, 2, 4, 8]` | §6「Amount of insight.」段落 "We set the maximum number of insights in the context to 1, 2, 4, and 8, instead of the default 16" | high |
| Q39 | 列挙 | `["KL Divergence", "Token-level policy gradients", "Removing the standard deviation"]` | Appendix A.3.1「Changes taken over from DAPO」直下の各パラグラフ冒頭見出し | high |
| Q42 | 数値（整数） | `32` | Table 4（Hyperparameters used for train runs）、行 `Global batchsize`・列 `Leetcode` | high |
| Q45 | 短文逐語 | `Call complete_task without passing an answer parameter for non-QA tasks.` | Appendix C.1、Table 5 の行 `Extra parameter`（Share 11.2%）に掲げられた唯一の insight 例 | high |
| Q48 | 数値（整数） | `92` | Appendix E.4「Insight evolution over time」第2段落末 "(n=92 revisited tasks)" | high |
| Q51 | 数値 | `9.6` | Appendix F.2、Table 9、行 `Off-policy training`・列 `Eval Pass@1` | high |

- 見つからず `value: null` とした項目は**ない**（17/17 で所在を特定）。したがって「探した範囲」の空欄報告は無いが、探索範囲は §4 に記す。

## 4. 探索範囲の記録

- HTML 版 `https://arxiv.org/html/2609.37633v2` を **16チャンクすべて**取得して通読した（Abstract、§1〜§8、References、Appendix A〜F、Table 1〜9、Figure 1〜13 のキャプション）。
- abs ページ `https://arxiv.org/abs/2609.37633v2` を取得し、Submission history と Subjects・DOI を確認した。
- 数値表は HTML の表レンダリングをそのまま読み、行ラベル×列ラベルでセルを特定した。Gecko/MathML 由来の重複表記（例 `720 720M`、`03.4%`）が見られたが、対象セルはいずれも一意に読めた。
- Q08 の数え方：`Appendix + 英大文字` の見出しを全見出しから数えた。`Appendix Contents`（目次見出し、英大文字1字でない）と `A.1`〜`F.2` の小節は除外した。

## 5. 規律・独立性

- 他アーム・他ワーカーのブランチ、PR、成果物は**参照していない**。PR 一覧等で他条件を調べていない。統合・真値確定は行っていない。
- 担当外（Q01, Q03, Q04, Q06, Q07, Q09〜Q13, Q15〜Q17, Q20, Q22, Q23, Q25〜Q28, Q30, Q31, Q33, Q34, Q36, Q38, Q40, Q41, Q43, Q44, Q46, Q47, Q49, Q50）の回答は出力していない。
- `state/`、既存メモ、コード、fixture、設計文書は変更していない。新規作成は本メモと対応 JSON の2件のみ。
- 使用した道具：`bash`（git・日時確認・ゲート実行）、ページ取得（Arena web fetch）、ファイル読取、ファイル書込。回数は JSON の `session_log.tool_calls` に自己申告で記す。

## 6. 表記上の注意（誤りではなく書式の判断）

- **Q39**：原典の見出しは太字＋末尾ピリオド（例 `KL Divergence.`）。列挙要素として末尾のピリオドを落として提出した（§9 の「語末句読点の有無」に該当する書式差）。見出しの語順・語形は原典どおり。
- **Q45**：HTML ではアンダースコアが `complete\_task` とエスケープ表示されるが、原典の識別子は `complete_task` である。エスケープを外した素の表記で提出した。
- **Q35**：同じ趣旨の文が Table 5 の「Unrecorded action」行に `You need to mark the article as read rather than just viewing it.` と別表記で存在する。Q35 が指すのは **§6 冒頭段落の引用文**（"instead of" 側）であり、Table 5 の文ではない。取り違えを避けるため明記する。
- **Q32 / Q42**：Table 2・Table 4 には `Global batchsize (avg tokens)` など近接する別行がある。Q42 は `Global batchsize` 行（`avg tokens` 行ではない）を採った。

## 7. 待機・逸脱の記録

- 2026-10-21T08:50:35Z に開始。`date -u` の直後に HEAD 不一致を検出し、抽出を開始せず停止して人間へ報告。再指示を受けて 2026-10-21T08:57:12Z に HEAD を再確認して再開した。**待機時間は M2 に含まれる**（`started_at_utc` は最初の記録時刻を維持）。
- 逸脱：なし（base_commit 不一致は指示により解除済みの条件。ただし参考実行である旨を §1 に明記）。
- UI 上の表示モデル名：確認できる表示が無いため `unknown`。

## 8. ゲート

8コマンドの実行結果は PR 本文に記載する（本メモの内容確定はゲート実行より前のため、結果を本メモへ焼き込まない）。
