# 証拠照合 S3：P5 / P6 / P7 の原典照合結果

- 作成日：2026-10-20
- セッション：S3（並列照合、`docs/evidence-collation-prompts-2026-10-20.md` §S3）
- 対象：`contributions/2026-10-20_context_and_eval_bottlenecks.md`（以下「メモ」）が述べる
  arXiv 文献の数値・定性主張
- 照合対象論文（**arXiv ID で指定**）：
  - **P5** = arXiv:2605.23950（Stop Comparing LLM Agents Without Disclosing the Harness）
    = bottlenecks メモ `[5]` = survey レポート `[8]` = `SRC-20261020-07a3`
  - **P6** = arXiv:2608.13417（Beyond Final Scores）
    = bottlenecks メモ `[6]` = survey レポート `[9]` = `SRC-20261020-4cff`
  - **P7** = arXiv:2610.17184（DuoDiscover）
    = bottlenecks メモ `[7]` = survey レポート `[3]` = `SRC-003`（低優先だったが実施済み）
- 方法：各論文の `arxiv.org/abs/<ID>` で最新版を確認し、その HTML 全文を実地読解して
  判定した。新しい実験・測定は行っていない。図の画像は読んでいない（キャプションと本文のみ）。
  参考文献の原典は辿っていない（二次引用の指摘のみ）。

## (a) 版の確認と最新版の異同

| 文献 | abs ページの投稿履歴 | 最新版 | メモ引用版 | version_read | is_latest | 差分 |
|---|---|---|---|---|---|---|
| arXiv:2605.23950 | `[v1]` Thu, 7 May 2026 のみ | v1 | v1 | v1 | true | なし（単一版） |
| arXiv:2608.13417 | `[v1]` Thu, 13 Aug 2026 のみ | v1 | v1 | v1 | true | なし（単一版） |
| arXiv:2610.17184 | `[v1]` Mon, 12 Oct 2026 のみ | v1 | v1 | v1 | true | なし（単一版） |

3 論文とも abs ページに `[v1]` しかなく、最新版＝メモ引用版＝v1 である。
版による記述変更の余地はなく、`version_delta_note` は空（JSON には抄録を記録）。
したがって「最新版で見つからない主張」は存在せず、`not_found` 判定は 0 件。

## (b) claim ごとの判定表

### P5 — arXiv:2605.23950（`SRC-20261020-07a3`）

| claim_id | メモの主張 | verdict | 原典の箇所 | 備考 |
|---|---|---|---|---|
| C-07a3-01 | position paper であり自前の実験を持たない | **wrong_value** | Abstract / §4 / §4.2 / Appx. B | 「position paper」は正しいが「自前の実験を持たない」は誤り（後述 (c)） |
| C-07a3-02 | Binding Constraint Thesis を主張 | paraphrase_ok | Abstract / §3 | thesis 名と内容（harness 構成がモデル選択より分散を支配）は一致 |
| C-07a3-03 | モデル固定・harness のみ変更で Terminal-Bench 2 pass@1 が 69.7%→77.0% | verbatim | §1 / Table 1 | 数値は完全一致。**二次引用**（同論文 ref [17] = AHE 論文） |
| C-07a3-04 | 第三者の監視で SWE-bench Verified に scaffold のみで最大 15 ポイントの変動 | verbatim | §1 / §2.1 / §4.1 | 「up to 15 percentage points of scaffold-only variation」完全一致。**二次引用**（ref [4] = Epoch AI）。§2.1 には GPT-5 で 11pp、Kimi K2 Thinking で 15pp の内訳 |
| C-07a3-05 | SWE-bench Pro で SEAL scaffold 45.9% vs Claude Code 55.4% | verbatim | §2.1 / Table 1 | 2 数値とも完全一致。モデルは Claude Opus 4.5（メモはモデル名を省略）。**二次引用**（ref [25] = Morph leaderboard） |
| C-07a3-06 | 提案は harness 開示・locked-harness・factorial プロトコル | paraphrase_ok | §1 / §2.3 / §5 | 3 要素とも原典に存在（Harness Card 開示、locked-harness protocol、factorial protocol） |
| C-07a3-07 | 開示がない間は長期エージェントのリーダーボード比較は不完全かつ誤誘導的 | paraphrase_ok | Abstract 末尾 / §7 末尾 | "should be treated as incomplete and potentially misleading" の忠実な翻訳 |
| C-07a3-08 | 上記数値が二次引用であることの確認 | verbatim | §1 の引用マーカー / Table 1 Sources 行 | 確認。3 数値はいずれも外部ベンチマーク・監視レポート由来で、自前実験（§4.2）の数値ではない |

### P6 — arXiv:2608.13417（`SRC-20261020-4cff`）

| claim_id | メモの主張 | verdict | 原典の箇所 | 備考 |
|---|---|---|---|---|
| C-4cff-01 | フロンティア 7 モデル × 長期 R&D タスク 36 件 | verbatim | Abstract / §1 / §2.1 | "seven frontier models on 36 long-horizon tasks"。36 件は AutoLab 由来（4 ファミリに 7/15/10/4 件） |
| C-4cff-02 | LLM ジャッジではなく規則ベースのプロセス指標で分解評価 | verbatim | §1 / §3.1 | "rule-based metric computed deterministically … rather than LLM judgments"。LLM ジャッジは新奇性分析（§6）の補助分析にのみ使用 |
| C-4cff-03 | 指標名は Solution Framing / Execution / Feedback Control | verbatim | §1 / §3.1 | C1 / C2 / C3 と番号付けも一致 |
| C-4cff-04 | 7 モデル × 36 タスクの完全評価に推論費 約 10 万米ドル | verbatim | §1 | "approximately one hundred thousand U.S. dollars in model inference"（full evaluation = 756 rollouts） |
| C-4cff-05 | 実行は run 間で大きく揺れる | paraphrase_ok | Abstract / §1 / §2.2 | "performance varies substantially across runs"。avg@3 の最強−最弱開き 0.237 vs best@3 0.122 |
| C-4cff-06 | 似た最終スコアの背後には異なるプロセスのボトルネック | paraphrase_ok | Abstract / §3.2 | "distinct process bottlenecks behind similar final outcomes"。GPT-5.5 と Gemini-3.1-Pro が具体例 |
| C-4cff-07 | 本物の新規性は稀 | paraphrase_ok | Abstract / §6 | "genuine methodological novelty remains rare"。252 解中 3 解（1.2%）のみ novel |
| C-4cff-08 | harness 設計が安定性を左右する | paraphrase_ok | Abstract / §5.1 | "harness designs that affect performance stability"。§5.1: 安定性が主に変化し順位は保存 |

### P7 — arXiv:2610.17184（`SRC-003`）※低優先指定だったが実施済み

| claim_id | メモの主張 | verdict | 原典の箇所 | 備考 |
|---|---|---|---|---|
| C-003-01 | SWE-fficiency で人間エキスパート平均の 2 倍の改善 | verbatim | Abstract / §3.1 | "doubles the average speedup of human experts"。本文では 15.02× vs エキスパート 6.90×（≈2.18 倍） |
| C-003-02 | SOL-Exec で 235 カーネル中 121 カーネル首位 | verbatim | Abstract / §3.1 | "ranks first on 121 of 235 kernels and in the top three on 212" |
| C-003-03 | vLLM/SQLite で 1.92× / 1.38× | verbatim | Abstract / §3.2 | "achieves 1.92× and 1.38× gains over the base code"。本文の該当数値と一致 |
| C-003-04 | CPU マイクロアーキテクチャ課題で ArchAgent v2 の改善量の 1.65× を 16.7 日で達成（既存手法は 40 日超） | verbatim | Abstract / §3.2 Table 2 | "1.65× ArchAgent v2's gain … over 16.7 days, against … more than 40 days for ArchAgent v2"。Table 2: +6.31% vs +3.82% |
| C-003-05 | 評価に最大 28 時間かかる課題がある | verbatim | Abstract / §3.2 | "evaluations of up to 28 hours"。本文: 1 回の true evaluation が最大 28 時間（1,700 simulations） |

## (c) `wrong_value` の理由と根拠箇所

**C-07a3-01（`wrong_value`）**：メモ §4.3・§6 の「[5] は実験を持たない position paper」のうち、
「position paper」は正しい（Abstract: "This position paper argues that…"）が、
「自前の実験を持たない」は原典と矛盾する。根拠：

- §4 Evidence の冒頭："We support the thesis with two kinds of evidence:
  observational data from public leaderboards **and a controlled factorial experiment
  under matched conditions**."
- §4.2 Controlled Factorial：GPT-5.4 / Kimi K2.6 / GLM-5.1 の 3 モデル ×
  H1 (Minimal) / H2 (Improved) / H3 (Full) の 3 ハーネスの計画格子を、
  SWE-bench Verified の難度層化済み 100 タスク subset で実施（各セル 2 回の独立実行、
  50-step budget、120s per-step timeout）。
- Table 2 に結果（各セルの pass@1、HV/MV）があり、"Aggregate HV¯/MV¯ ratio: 7.80×.
  Ranking reversal pairs: 6 out of 9"、Appendix B（Table 5–8）に subset 構成・モデル API
  設定・ハーネス全仕様が記されている。

すなわち同論文は position paper でありながら、**自前の計画格子実験を 1 件持つ**。
メモの「実験を持たない」はこの §4.2 を見落としている。
（なお C-07a3-03〜05 の 3 数値が二次引用であること自体は正しく、
それらはこの自前実験の数値ではない。両者は別の話である。）

`not_found` は 0 件（3 論文とも単一版 v1 で、該当箇所がすべて原典に存在した）。

## (d) サマリ（verdict 4 値の内訳）

| 文献 | verbatim | paraphrase_ok | wrong_value | not_found | 計 |
|---|---|---|---|---|---|
| P5 arXiv:2605.23950 | 4 | 3 | 1 | 0 | 8 |
| P6 arXiv:2608.13417 | 4 | 4 | 0 | 0 | 8 |
| P7 arXiv:2610.17184 | 5 | 0 | 0 | 0 | 5 |
| **計** | **13** | **7** | **1** | **0** | **21** |

- P5 の 3 つの R1 数値 claim（C-07a3-03/04/05）はいずれも数値が原典に完全一致して存在するが、
  **すべて二次引用**（外部ベンチマーク／第三者監視レポート由来）。メモ §6 の注記どおりであり、
  C-07a3-08 の確認は正しい。`verbatim` のまま「二次引用」を notes に明記した。
- P6 は 8 claim すべてが原典の記述と一致（数値 2 件は完全一致、定性 6 件は矛盾しない言い換え）。
- P7 は 5 claim すべてが Abstract・本文の数値と完全一致。
- 捕捉すべき欠陥は C-07a3-01 の 1 件（定性主張の矛盾）。統合役による裁定と、
  必要に応じた訂正 EVD・メモへの `correction_note` 付与を推奨する。

## 参考文献（照合対象。1 件 1 物理行）

[5] Yunbei Zhang, Janet Wang, Yingqiang Ge, Weijie Xu, Jihun Hamm, Chandan K. Reddy. "Stop Comparing LLM Agents Without Disclosing the Harness." arXiv:2605.23950v1 [cs.AI], 2026（投稿 2026-05-07）. https://arxiv.org/abs/2605.23950

[6] Yiwei Li, Wanli Yang, Hexiang Tan, …, Jingang Wang. "Beyond Final Scores: A Systematic Evaluation of Agents for Long-Horizon AI Research and Development." arXiv:2608.13417v1 [cs.AI], 2026（投稿 2026-08-13）. https://arxiv.org/abs/2608.13417

[7] Shubham Agarwal, Akshat Gupta, Mike Heddes, …, Chun-Liang Li. "DuoDiscover: Scaling Autonomous Discovery Beyond the Evaluation Bottleneck." arXiv:2610.17184v1 [cs.CL], 2026（投稿 2026-10-12）. https://arxiv.org/abs/2610.17184

## 検証コマンドの実測値

6 ゲートすべて実行済み（Python 3.11 系、2026-10-20）。実測値：

```
$ python3 -m unittest discover -s tests
Ran 145 tests in 4.536s
OK

$ python3 gitswarm/benchmarks/benchmark.py --check
PASS: benchmark artifact matches a fresh execution

$ python3 gitswarm/readout_sim.py --check
PASS: readout-sim artifact matches a fresh execution

$ python3 scripts/validate_state.py
PASS: research ledgers valid (sources=11, evidence=14, claims=8, verifications=25, hypotheses=2)

$ python3 scripts/check_citations.py
summary: 10 arXiv source(s) checked, 1 skipped, 0 failure(s)

$ python3 scripts/check_memo_citations.py
summary: 15 memo(s) scanned, 41 arXiv citation(s) checked, 1 skipped, 0 failure(s)
（本ファイルの参考文献 [5][6][7] も OK。inline mention 3 件も snapshot に存在）
```

すべて green。`state/` には一切書き込んでいない（統合役専権）。
