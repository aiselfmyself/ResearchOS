# 証拠照合の対象リスト（2026-10-20）

## 0. これは何か

`contributions/2026-10-20_context_and_eval_bottlenecks.md`（以下「bottlenecks メモ」）と
`contributions/2026-10-20_integrated_survey_report.md`（以下「survey レポート」）は、
**7 件の文献について桁のある数値を含む主張を散文で述べているが、`state/evidence.jsonl` に裏付けが無い。**

```text
EVD を持つソース : SRC-001, SRC-002, SRC-003, SRC-004   （4件）
EVD を持たない   : SRC-20261020-05de, 787b, 303f, 875e, 07a3, 4cff, f295  （7件）
```

本リポジトリはすでに同種の欠陥を 2 件捕捉している。

- `CLM-20261020-b07e`：CLM-001 を支持していた引用文が**原典に存在しなかった**（EVD-011）
- `CLM-006`：Verifier が記録した著者名が**先頭著者と異なっていた**（EVD-009）

**この 2 件は、照合を通ったから見つかった。照合を通していない領域が 7/11 残っている。**
本リストはその残りを機械的に照合するための対象定義である。

- 照合の**実行**は並列セッションに出す（`docs/evidence-collation-prompts-2026-10-20.md`）。
- 照合結果の**裁定**と `state/evidence.jsonl` への追記は統合役が行う（`state/` は統合役専権、
  `docs/parallel-work-ownership.md` §2）。

---

## 1. 対象文献の対応表

**⚠️ 2 つのメモは `[n]` の番号体系が異なる。** `bottlenecks[n]` = `survey[n+3]` である。
**照合は必ず arXiv ID で指定すること。**

| 便宜ID | source_id | arXiv ID | 短名 | メモが引用した版 | bottlenecks | survey | 並列セッション |
|---|---|---|---|---|---|---|---|
| P1 | `SRC-20261020-05de` | 2507.13334 | Context Engineering survey | v2（2025-07-17） | [1] | [4] | S1 |
| P2 | `SRC-20261020-787b` | 2606.10209 | Less Context | v1（2026-06-08） | [2] | [5] | S1 |
| P3 | `SRC-20261020-303f` | 2608.06663 | Horizon Gap | v1（2026-08-07） | [3] | [6] | S2 |
| P4 | `SRC-20261020-875e` | 2610.08364 | Transect | v2（2026-10-06） | [4] | [7] | S2 |
| P5 | `SRC-20261020-07a3` | 2605.23950 | Stop Comparing | v1（2026-05-07） | [5] | [8] | S3 |
| P6 | `SRC-20261020-4cff` | 2608.13417 | Beyond Final Scores | v1（2026-08-13） | [6] | [9] | S3 |
| P7 | `SRC-003` | 2610.17184 | DuoDiscover | v1（2026-10-12） | [7] | [3] | S3（低優先） |

**P7 だけ既に EVD が 3 件ある**（EVD-004 / EVD-009 / EVD-011）。ただしいずれも yardstick・
fidelity tests・著者名に関するものであり、bottlenecks メモ §4.4 が述べる**性能数値は未照合**である。
したがって P7 は「性能数値のみ」を対象とし、時間がなければ飛ばしてよい。

**版の扱い**（Agora v1→v4 の経験による）：

- セッションは**最新版を読む**。読んだ版を `version_read` に記録する。
- 最新版で主張が見つからない場合、**メモが引用した版を見てから** `not_found` と判定する。
  版による記述変更と、メモの誤りを混同しないため。
- 最新版とメモ引用版が異なる場合は `version_delta_note` に何が変わったかを書く。

---

## 2. 照合対象（claim 一覧）

リスクの凡例：

- **R1（最優先）**：桁のある数値。誤りなら下流の主張が崩れる
- **R2**：定性主張。言い換えの範囲か、原典に無いかを判定する
- **R3**：書誌・体裁

### P1 — `SRC-20261020-05de` / arXiv:2507.13334 / Context Engineering survey

| claim_id | 主張（bottlenecks メモの記述） | リスク | 出典箇所 |
|---|---|---|---|
| C-05de-01 | 1,400 本超の survey である | R1 | §3.2 |
| C-05de-02 | context engineering を「情報ペイロードの体系的最適化」として定式化 | R2 | §3.2 |
| C-05de-03 | context retrieval and generation / processing / management の階層で整理 | R2 | §3.2 |
| C-05de-04 | 構造的ギャップは「理解側は高機能なのに長文生成側が伴わない非対称」 | R2 | §3.2 |
| C-05de-05 | ongoing work の survey である（査読済み確定知ではない） | R2 | §6 |
| C-05de-06 | 分類 cs.CL、投稿 2025-07-17 | R3 | 参考文献 |

### P2 — `SRC-20261020-787b` / arXiv:2606.10209 / Less Context

**このメモで最も数値が密集している。** 8 つの数値が 1 段落に並ぶ。

| claim_id | 主張 | リスク | 出典箇所 |
|---|---|---|---|
| C-787b-01 | GPT-5 に 4 つの文脈構成を比較させた | R2 | §3.1 |
| C-787b-02 | 50 タスクのホテル経費明細化 | R1 | §3.1 |
| C-787b-03 | 5 回の独立実行、ユーザーモデルは固定 | R1 | §3.1 |
| C-787b-04 | ユーザーモデルなし = **8.0%** | R1 | §3.1 |
| C-787b-05 | 全会話履歴の保持 = **71.0%**、**1,480,996** トークン、**14.56** 時間 | R1 | §3.1 |
| C-787b-06 | 直近 5 ツール往復への刈り込み = **79.0%**、**535,274** トークン、**5.39** 時間 | R1 | §3.1 |
| C-787b-07 | 刈り込み＋自動要約 = **91.6%** 完了、平均金額 **99.64%**、**553,374** トークン、**5.79** 時間 | R1 | §3.1 |
| C-787b-08 | Claude Sonnet 4.5 でも同じ方向の証拠を報告 | R2 | §3.1 |
| C-787b-09 | 対象は enterprise tool-use の 1 課題クラス（制約） | R2 | §6 |

### P3 — `SRC-20261020-303f` / arXiv:2608.06663 / Horizon Gap

| claim_id | 主張 | リスク | 出典箇所 |
|---|---|---|---|
| C-303f-01 | 1,547 本、2024–2026 を対象 | R1 | §3.3 |
| C-303f-02 | bleed filter **26.8%** を開示 | R1 | §3.3 |
| C-303f-03 | long-horizon = タスク性質（必要ステップ数） | R2 | §3.3 |
| C-303f-04 | long-context = モデル性質（トークン容量） | R2 | §3.3 |
| C-303f-05 | long-term memory = システム性質（ステップ/セッションを跨ぐ持続性） | R2 | §3.3 |
| C-303f-06 | horizon が伸びるほど outcome-only 指標は非情報化する | R2 | §3.3 |
| C-303f-07 | 未解決の測定問題として「モデルと harness の能力分解」と correlated measurement bias を挙げる | R2 | §5 |

### P4 — `SRC-20261020-875e` / arXiv:2610.08364 / Transect

| claim_id | 主張 | リスク | 出典箇所 |
|---|---|---|---|
| C-875e-01 | observability envelope という語を用いている | R2 | §4.2 |
| C-875e-02 | 圧力は 4 つ：within-run opacity / human attention bottleneck / insufficient statistical power / setup attribution uncertainty | R2 | §4.2 |
| C-875e-03 | 数百ページのトランスクリプトに専門家レビューが追いつかない | R2 | §4.2 |
| C-875e-04 | 実演は約 **1,300 万**トークンの AI R&D 評価 | R1 | §4.2 |
| C-875e-05 | 操作作業と論文執筆に偏り、持続的な仮説生成段階の証拠は乏しかった | R2 | §4.2 |

### P5 — `SRC-20261020-07a3` / arXiv:2605.23950 / Stop Comparing

**⚠️ bottlenecks メモ自身が §6 で「数値はいずれも同論文が引用した外部ベンチマークの二次引用である」と注記している。**
「原典に数値があるか」だけでなく「**それが二次引用か**」も判定対象に含めること。

| claim_id | 主張 | リスク | 出典箇所 |
|---|---|---|---|
| C-07a3-01 | position paper であり自前の実験を持たない | R2 | §4.3, §6 |
| C-07a3-02 | Binding Constraint Thesis を主張 | R2 | §4.3 |
| C-07a3-03 | モデル固定・harness のみ変更で Terminal-Bench 2 pass@1 が **69.7%→77.0%** | R1 | §4.3 |
| C-07a3-04 | 第三者の監視で SWE-bench Verified に scaffold のみで最大 **15 ポイント**の変動 | R1 | §4.3 |
| C-07a3-05 | SWE-bench Pro で SEAL scaffold **45.9%** vs Claude Code **55.4%** | R1 | §4.3 |
| C-07a3-06 | 提案は harness 開示・locked-harness・factorial プロトコル | R2 | §4.3 |
| C-07a3-07 | 「開示がない間は長期エージェントのリーダーボード比較は不完全かつ誤誘導的」 | R2 | §4.3 |
| C-07a3-08 | 上記数値が**二次引用**であることの確認 | R1 | §6 |

### P6 — `SRC-20261020-4cff` / arXiv:2608.13417 / Beyond Final Scores

| claim_id | 主張 | リスク | 出典箇所 |
|---|---|---|---|
| C-4cff-01 | フロンティア 7 モデル × 長期 R&D タスク 36 件 | R1 | §4.1 |
| C-4cff-02 | LLM ジャッジではなく規則ベースのプロセス指標で分解評価 | R2 | §4.1 |
| C-4cff-03 | 指標名は Solution Framing / Execution / Feedback Control | R2 | §4.1 |
| C-4cff-04 | 7 モデル × 36 タスクの完全評価に推論費 約 **10 万米ドル** | R1 | §4.1 |
| C-4cff-05 | 実行は run 間で大きく揺れる | R2 | §4.1 |
| C-4cff-06 | 似た最終スコアの背後には異なるプロセスのボトルネック | R2 | §4.1 |
| C-4cff-07 | 本物の新規性は稀 | R2 | §4.1 |
| C-4cff-08 | harness 設計が安定性を左右する | R2 | §4.1 |

### P7 — `SRC-003` / arXiv:2610.17184 / DuoDiscover（低優先）

| claim_id | 主張 | リスク | 出典箇所 |
|---|---|---|---|
| C-003-01 | SWE-fficiency で人間エキスパート平均の **2 倍**の改善 | R1 | §4.4 |
| C-003-02 | SOL-Exec で **235 カーネル中 121 カーネル**首位 | R1 | §4.4 |
| C-003-03 | vLLM/SQLite で **1.92× / 1.38×** | R1 | §4.4 |
| C-003-04 | CPU マイクロアーキテクチャ課題で ArchAgent v2 の改善量の **1.65×** を **16.7 日**で達成（既存手法は 40 日超） | R1 | §4.4 |
| C-003-05 | 評価に最大 **28 時間**かかる課題がある | R1 | §4.4 |

---

## 3. 判定の定義

| verdict | 意味 | 統合役の扱い |
|---|---|---|
| `verbatim` | 原典に逐語で（または数値が完全一致で）存在する | そのまま EVD 化 |
| `paraphrase_ok` | 逐語ではないが、原典の記述と意味的に矛盾しない | EVD 化するが `quote_type` は `paraphrase` にする |
| `wrong_value` | 該当箇所はあるが**数値が違う** | **訂正 EVD** を起こし、元メモに `correction_note` を付ける |
| `not_found` | 最新版・メモ引用版の**両方**に存在しない | **EVD にせず**、元メモの当該記述を削除または明示的な取消しとする |

`not_found` と `wrong_value` が出た場合、それは**このリポジトリにとって前進である**。
CLM-20261020-b07e（実在しない引用文）と CLM-006（著者名の誤り）と同種の欠陥を、
下流の主張に影響する前に捕捉できたことになる。**遠慮なく判定してよい。**

---

## 4. 照合の対象外

明確に線を引く。

- **図の画像そのもの**は読まない（キャプションと本文の記述のみ）。Agora でも未読のままにしている。
- **参考文献の原典**は辿らない（二次引用の**指摘**はするが、その先は確認しない）。
- **数値の再計算・再現実験**はしない。原典に書かれているかどうかだけを判定する。
- **`state/` には一切書き込まない**（統合役専権）。

---

## 5. 参考文献（照合対象。arXiv ID で指定する）

2507.13334 — Lingrui Mei, Jiayu Yao, Yuyao Ge, …, Shenghua Liu. "A Survey of Context Engineering for Large Language Models." arXiv:2507.13334v2 [cs.CL], 2025. https://arxiv.org/abs/2507.13334

2606.10209 — Abhilasha Lodha, Mahsa Pahlavikhah Varnosfaderani, Abir Chakraborty, Abhinav Mithal. "Less Context, Better Agents: Efficient Context Engineering for Long-Horizon Tool-Using LLM Agents." arXiv:2606.10209v1 [cs.AI], 2026. https://arxiv.org/abs/2606.10209

2608.06663 — Mingguang Chen, Licheng Wang, Bo Qu. "The Horizon Gap: Planning, Memory, Execution, Training, and Evaluation for Long-Horizon LLM Agents." arXiv:2608.06663v1 [cs.CL], 2026. https://arxiv.org/abs/2608.06663

2610.08364 — Toby D. Pilditch, Konstantinos Voudouris, Alexandra Abbas, Cozmin Ududec. "Transect: Retaining Observability for Long-Horizon LLM Agent Evaluations." arXiv:2610.08364v2 [cs.AI], 2026. https://arxiv.org/abs/2610.08364

2605.23950 — Yunbei Zhang, Janet Wang, Yingqiang Ge, Weijie Xu, Jihun Hamm, Chandan K. Reddy. "Stop Comparing LLM Agents Without Disclosing the Harness." arXiv:2605.23950v1 [cs.AI], 2026. https://arxiv.org/abs/2605.23950

2608.13417 — Yiwei Li, Wanli Yang, Hexiang Tan, …, Jingang Wang. "Beyond Final Scores: A Systematic Evaluation of Agents for Long-Horizon AI Research and Development." arXiv:2608.13417v1 [cs.AI], 2026. https://arxiv.org/abs/2608.13417

2610.17184 — Shubham Agarwal, Akshat Gupta, Mike Heddes, …, Chun-Liang Li. "DuoDiscover: Scaling Autonomous Discovery Beyond the Evaluation Bottleneck." arXiv:2610.17184v1 [cs.CL], 2026. https://arxiv.org/abs/2610.17184
