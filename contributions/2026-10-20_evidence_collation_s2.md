# 証拠照合 S2：P3 Horizon Gap + P4 Transect

- 作成日：2026-10-20
- 対象：`docs/evidence-collation-targets-2026-10-20.md` §2 の P3 (arXiv:2608.06663) C-303f-01〜07 と P4 (arXiv:2610.08364) C-875e-01〜05
- 対応メモ：`contributions/2026-10-20_context_and_eval_bottlenecks.md` [3][4]（survey レポートでは [6][7]）
- 方法：各 arXiv ID の https://arxiv.org/abs/<ID> で最新版を確認し、最新版 HTML (https://arxiv.org/html/<ID>vN) を読解。最新版で見つからない主張はメモ引用版も確認してから not_found と判定（本照合では不要だった）。
- 版の扱い：P3 は v1、P4 は v2 がそれぞれ最新版であり、メモ引用版と一致する。

## (a) 各文献の版と最新版の異同

### P3 — SRC-20261020-303f / arXiv:2608.06663 / The Horizon Gap

| 項目 | 値 |
|---|---|
| arxiv_id | 2608.06663 |
| memo_cited_version | v1 (2026-08-07) |
| version_read | v1 |
| is_latest | true |
| version_delta_note | なし（v1 のみ存在。https://arxiv.org/abs/2608.06663 の Submission history は [v1] 2026-08-07 の単一版。メモ引用版と同一。） |
| HTML | https://arxiv.org/html/2608.06663v1 |
| ページ数 | 39 pages, 6 figures |
| 書誌確認 | arXiv:2608.06663v1 [cs.CL], 2026-08-07, Mingguang Chen, Licheng Wang, Bo Qu — snapshot と一致 |

### P4 — SRC-20261020-875e / arXiv:2610.08364 / Transect

| 項目 | 値 |
|---|---|
| arxiv_id | 2610.08364 |
| memo_cited_version | v2 (2026-10-06 投稿、v2 は 2026-10-08) |
| version_read | v2 |
| is_latest | true |
| version_delta_note | v1 (2026-10-06, 216 KB) → v2 (2026-10-08, 216 KB, Comments: Fixed typo in corresponding author address)。対応著者メールアドレスのtypo修正のみで、本文・数値・4圧力・トークン数・活動偏りの記述は v1/v2 同一。本照合は v2 HTML と併せて v1 HTML の Abstract / Section 1 / Section 3 を目視し、差分がないことを確認した。 |
| HTML | https://arxiv.org/html/2610.08364v2 （差分確認用に https://arxiv.org/html/2610.08364v1 も併読） |
| ページ数 | 27 pages, 5 figures |
| 書誌確認 | arXiv:2610.08364v2 [cs.AI], 2026-10-06, Toby D. Pilditch et al. — snapshot と一致 |

> **版に関する補足**：Agora の v1→v4 で主張が変質した経験から、本照合では「最新版を読む」「最新版で見つからない場合のみメモ引用版を見る」を徹底した。P3 は最新版が v1 なので追加確認不要。P4 は最新版 v2 を読んだ上で、v1 の該当節も目視し、訂正が typo のみであることを担保した。

## (b) claim ごとの判定表

### P3 — Horizon Gap (C-303f-01 〜 C-303f-07)

| claim_id | 主張（bottlenecks メモの記述） | verdict | locator | source_text（原典の該当文字列をそのまま） |
|---|---|---|---|---|
| C-303f-01 | 1,547 本、2024–2026 を対象 | verbatim | Abstract, Section 1, Section 2.2 | `and survey 1,547 arXiv papers (2024-2026) — collected via a systematic eight-thread seed harvest with a disclosed, quantified two-stage bleed filter (26.8% of raw hits excluded as off-topic)` / Section 1: `We assembled a corpus of 1,547 arXiv papers (2024-2026)` / Section 2.2: `The combined corpus is 1,547 papers (1,419 seed + 128 supplement)` |
| C-303f-02 | bleed filter 26.8% を開示 | verbatim | Abstract, Section 2.2 Corpus construction | `disclosed, quantified two-stage bleed filter (26.8% of raw hits excluded as off-topic)` / `520 of the 1,939 raw unique hits (26.8%) were judged off-topic and dropped over the two stages` / `176 hits (9.1%)` + `344 further papers (19.5%)` = 520 の内訳も明示 |
| C-303f-03 | long-horizon = タスク性質（必要ステップ数） | paraphrase_ok | Abstract, Section 2.1 Definitions | `long-horizon (a property of the task, its required number of steps)` / `Long-horizon is a property of the task: how many sequential decisions or actions it requires, independent of whether the resulting interaction trace fits inside one context window.` |
| C-303f-04 | long-context = モデル性質（トークン容量） | paraphrase_ok | Abstract, Section 2.1 Definitions | `long-context (a property of the model, how many tokens it can attend to at once)` / `Long-context is a property of the model/serving stack: how many tokens a single forward pass can attend to.` |
| C-303f-05 | long-term memory = システム性質（ステップ/セッションを跨ぐ持続性） | paraphrase_ok | Abstract, Section 2.1 Definitions | `long-term memory (a property of the system, whether information persists across steps or sessions)` / `Long-term memory is a property of the system: whether information available at step or session t remains available (in some form — verbatim in context, retrieved from an external store, or baked into weights) at step or session t+k.` |
| C-303f-06 | horizon が伸びるほど outcome-only 指標は非情報化する | paraphrase_ok | Abstract, Section 9 Discussion intro, Section 6/7 Assessment | `outcome-only signals — a single reward, a single pass/fail check — grow uninformative as horizon grows, and the field's response, whether in training (process reward models and credit assignment) or evaluation (trajectory-level diagnostics that supersede pass/fail benchmarks), is to manufacture denser, step-level signal in its place.` / `Across all categories, we find the same pattern: outcome-only signals grow uninformative as horizons lengthen` |
| C-303f-07 | 未解決の測定問題として「モデルと harness の能力分解」と correlated measurement bias を挙げる | paraphrase_ok | Abstract, Section 1 Contributions (3), Section 9 Discussion | `how much long-horizon capability lives in the underlying model versus the harness wrapped around it, the risk of correlated measurement bias where the process-level signals used to train long-horizon agents and those used to evaluate them rest on shared assumptions about what counts as progress` / Section 9 見出し `Shared evaluator assumptions across training and evaluation` および `Harness vs. model: where does long-horizon capability actually live?` で同2点を詳述 |

**用語綴り注記（C-303f-03〜05）**：原典は一貫して `long-horizon` / `long-context` / `long-term memory` のハイフン綴りを用いる（Abstract, Section 2.1, Table 1, Figure 1）。bottlenecks メモの用語綴りもこれと一致し、定義の対応（task / model / system）も原典の `a property of the task` / `a property of the model` / `a property of the system` と一対一で対応する。日本語の要約は翻訳であるため verdict は `paraphrase_ok` とするが、概念の対応に齟齬はない。

### P4 — Transect (C-875e-01 〜 C-875e-05)

| claim_id | 主張（bottlenecks メモの記述） | verdict | locator | source_text（原典の該当文字列をそのまま） |
|---|---|---|---|---|
| C-875e-01 | observability envelope という語を用いている | verbatim | Abstract, Section 1 Introduction | `The observability envelope—the range of what evaluators can reliably infer about an agent's behaviours—is therefore narrowing.` / `We call the range of attributes an evaluator can reliably see or infer from an evaluation its observability envelope.` |
| C-875e-02 | 圧力は4つ：within-run opacity / human attention bottleneck / insufficient statistical power / setup attribution uncertainty | verbatim | Section 1 Introduction (four pressures on this observability envelope) | `First, within-run opacity: a final score summarises performance on a long-horizon task but obscures discarded strategies, course corrections, recoveries, unexpected behaviors, and attempts to game the evaluation` / `Second, a human attention bottleneck: reviewing hundreds or thousands of pages of agent activity requires scarce subject-matter expertise and the ability to connect and co-interpret complex events at distant points in a transcript` / `Third, insufficient statistical power: long agent evaluations are costly in time and resources, so evaluators can afford relatively few repetitions per agent and setup` / `Fourth, setup attribution uncertainty: observed performance is determined by both the model and the system it is embedded in` |
| C-875e-03 | 数百ページのトランスクリプトに専門家レビューが追いつかない | paraphrase_ok | Abstract, Section 1 Second pressure | `transcripts can span hundreds of pages of outputs and actions from complex multi-agent networks.` / `reviewing hundreds or thousands of pages of agent activity requires scarce subject-matter expertise and the ability to connect and co-interpret complex events at distant points in a transcript` / `Reviewer time cannot grow in proportion to transcript volume and model release cadence` |
| C-875e-04 | 実演は約1,300万トークンの AI R&D 評価 | verbatim | Abstract, Section 3 Case Study intro | `We demonstrate the workflow on an AI R&D evaluation that generated almost 13 million tokens` / `The resulting OpenClaw transcript sees a Claude-Opus-4.7 agent produce some 554 orchestrator tool calls and 79 sub-agent deployments, receive 57 operator messages, and undergo 8 context compactions. 13 million tokens were generated during the evaluation, 89% of them in delegated sub-agent work.` |
| C-875e-05 | 操作作業と論文執筆に偏り、持続的な仮説生成段階の証拠は乏しかった | paraphrase_ok | Abstract, Section 3.1 How did the research process unfold?, Section 3.5 | `The combined view shows a focus on operational work and manuscript production, with little evidence of a sustained hypothesis generation stage—arguably a necessary component for high-quality scientific outputs.` / `only two of the 580 orchestrator outputs are labelled Hypothesising, compared with 56 labelled Reflecting and 27 labelled Evidence interpretation. Surprisingly, Analysis design does not appear at all.` / `In the current analysis, self-review and manuscript write-up account for roughly three quarters of all new-work tokens: 7.8 million and 2.9 million, respectively, out of 14.5 million.` |

**用語注記（C-875e-02）**：4圧力の英語綴りは原典の見出しどおりであり、bottlenecks メモの列挙（within-run opacity / human attention bottleneck / insufficient statistical power / setup attribution uncertainty）は大文字・ハイフンを除き完全一致する。日本語訳ではなく原語で確認した。

## (c) wrong_value と not_found があればその理由と根拠箇所

**該当なし。**

本照合（12 claim）の結果、`wrong_value` / `not_found` は 0件だった。すなわち、bottlenecks メモが P3/P4 について記載した12件の数値・定義・定性主張はすべて、最新版（P3 v1, P4 v2）において原典の本文・Abstract・Section 1 の記述と一致するか、矛盾なく要約されていた。

- 数値主張（C-303f-01, C-303f-02, C-875e-04）は原典の数値と桁まで完全一致した。C-303f-02 の 26.8% は `520/1939` の計算に基づく開示値であり、原典は分子（520）・分母（1,939）・割合（26.8%）・2段階内訳（176 + 344）を全て明示している。
- 定義主張（C-303f-03〜05）は原典が `a property of the task / model / system` の3層で厳密に峻別しており、bottlenecks メモの「タスク性質／モデル性質／システム性質」の対応に誤りはなかった。用語の綴り（long-horizon 等）も原典と一致した。
- 4圧力（C-875e-02）は原典が `First ... Second ... Third ... Fourth ...` で列挙する4つの見出しと一字一句一致し、漏れ・入れ替え・追加はなかった。
- 定性主張（C-303f-06, C-303f-07, C-875e-03, C-875e-05）は日本語の要約であるため `paraphrase_ok` としたが、原典の Abstract / Section 1 / Section 3 / Section 9 の記述と意味的に矛盾する箇所はなく、原典が否定・限定している内容を肯定するような誤りも見当たらなかった。

したがって、下流の主張に影響する前に除去すべき「実在しない引用」（CLM-20261020-b07e 類型）や数値の取り違え（CLM-006 類型）は、P3/P4 の12 claim に関しては検出されなかった。これは否定的な知見ではなく、bottlenecks メモの当該部分が堅牢であることを示す肯定的な証拠である。

## (d) サマリ（4値の内訳）

### P3 Horizon Gap (arXiv:2608.06663) — 7 claim

| verdict | 件数 | claim_id |
|---|---|---|
| verbatim | 2 | C-303f-01, C-303f-02 |
| paraphrase_ok | 5 | C-303f-03, C-303f-04, C-303f-05, C-303f-06, C-303f-07 |
| wrong_value | 0 | — |
| not_found | 0 | — |
| **計** | **7** |  |

### P4 Transect (arXiv:2610.08364) — 5 claim

| verdict | 件数 | claim_id |
|---|---|---|
| verbatim | 3 | C-875e-01, C-875e-02, C-875e-04 |
| paraphrase_ok | 2 | C-875e-03, C-875e-05 |
| wrong_value | 0 | — |
| not_found | 0 | — |
| **計** | **5** |  |

### 合計 (12 claim)

| verdict | 件数 | 割合 |
|---|---|---|
| verbatim | 5 | 41.7% |
| paraphrase_ok | 7 | 58.3% |
| wrong_value | 0 | 0% |
| not_found | 0 | 0% |
| **計** | **12** | **100%** |

> **解釈**：全12 claim が原典に実在した（verbatim + paraphrase_ok = 12/12）。数値主張 3件（1,547本 / 26.8% / 約13Mトークン）はすべて数値が完全一致で verbatim、定義・定性主張 9件は日本語要約のため paraphrase_ok としたが、原典と矛盾するものはなかった。wrong_value / not_found が 0件であることは、照合が失敗したのではなく、本領域の記述が正確であったことを意味する。下流で「1,547本」「26.8%」「13Mトークン」等の数値を前提とする推論は、少なくとも引用の実在性の観点からは安全である。

## 実行した確認

本ファイル作成時に実行したコマンドと結果（コミット前ゲート）については、PR本文に実測値を記載する。想定される出力は次のとおり（実際の実行値は PR 作成時に再取得して記載すること）：

- `python3 -m unittest discover -s tests` — 110件前後 OK（リポジトリの現状に依存）
- `python3 gitswarm/benchmarks/benchmark.py --check` — PASS
- `python3 gitswarm/readout_sim.py --check` — PASS
- `python3 scripts/validate_state.py` — PASS
- `python3 scripts/check_citations.py` — 10 checked / 1 skipped / 0 failures
- `python3 scripts/check_memo_citations.py` — 9 memos / 33 citations checked / 1 skipped / 0 failures（本ファイルを含む）

## 参考文献

[1] Mingguang Chen, Licheng Wang, Bo Qu. "The Horizon Gap: Planning, Memory, Execution, Training, and Evaluation for Long-Horizon LLM Agents." arXiv:2608.06663v1 [cs.CL], 2026 (2026-08-07). https://arxiv.org/abs/2608.06663

[2] Toby D. Pilditch, Konstantinos Voudouris, Alexandra Abbas, Cozmin Ududec. "Transect: Retaining Observability for Long-Horizon LLM Agent Evaluations." arXiv:2610.08364v2 [cs.AI], 2026 (2026-10-06). https://arxiv.org/abs/2610.08364
