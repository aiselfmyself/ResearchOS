# 統合レポート：長期推論エージェントの文脈・協調・検証

- 作成日：2026-10-20
- 対象：`task/TASK.md` §4「Integrator による統合レポート作成（多数決ではなく証拠の強弱に基づく論証）」。`task/TASK.md` §2 の3項目を、既存メモの統合として1本にまとめる。
- 位置づけ：**既存 `contributions/` メモの統合であり、新規の文献取得・実験・台帳追記は行っていない**。数値はすべて既存メモの「本文確認済み」記載の転記で、出典は節付きで示す。本作業で行った確認は §8 に列挙する。

## 1. 統合結論

- 3つの設計——SLA [1]、GitSwarm [2]、DuoDiscover [3]——は「会話履歴を性能の源泉にしない」点で一致し、**状態の置き場所・決定の集中度・最終選択の接地先**で分かれる。優劣は決着しない（共通ベンチマークが存在しない）。
- **単一会話履歴の限界は直接比較で定量されている**。全履歴保持は 71.0% / 1,480,996 トークンに対し、選択的保持＋要約は 91.6% / 553,374 トークンで上回る [4]。SLA 全文読解でも、 Advisor の文脈再構成を外して全時系列記録を読ませる variant が全4設定でフル SLA を下回った（全文読解1 §1-5、Table 4）。**文脈は「入れるほど強く」ならず、管理こそが性能変数**である。
- **多数決を真理の判定器に据えた設計は3本とも存在しない**。SLA は投票機構なし、GitSwarm は検証可能な課題で readout を外し票を「調整信号であり独立検証ではない」と定義（[2] Appendix G.3）、DuoDiscover は票なしで真の評価 f に接地する。共通モード障害の**直接測定は依然0件**である（メモ1 §5、全文読解3 §8）。
- 検証は「何に接地するか」「その接地をどれだけ頻繁に再確認するか」の2軸で読むと3層に整理できる：SLA＝保護された評価器の測定値、GitSwarm＝検証性能（不能時のみ推薦多数決）、DuoDiscover＝f に対する順位相関（Kendall τ）の継続再検査（全文読解3 §9）。**未検証の代理指標は無いより悪い**——fidelity test なしの yardstick はベースラインを下回る（10.33×/66.91% < 12.85×/69.12%、[3] Table 4）。
- 評価そのものがボトルネックである。観測可能性はトランスクリプト膨張で縮小し [7]、harness の違いだけで Terminal-Bench 2 が 69.7%→77.0% と動く [5]、体系的評価の推論費は約10万米ドル [8]、真の評価1回は数時間に達する [3]。
- ResearchOS への含意（位置づけのみ・実験なし）：「状態をモデルの外に置く」と「fixture 付きの機械照合」は、文脈管理と評価接地の**両方**の文献上の方向と整合する。因果の分離は誰もしていない（§7）。

## 2. 調査範囲と方法

**素材（既存7メモ）。** 統合に使ったのは以下のみ。新規の文献取得は行わず、引用は本文中の既存記載をそのまま転記した。

| 素材 | 役割 |
|---|---|
| `worker01_stateless_analysis.md`、`worker02_gitswarm_and_limits.md` | 初期ノート。スコープの誤り（多数決の解釈等）はメモ1 §2 で訂正済みのため、統合では**訂正版の記述のみ**を採用 |
| `2026-10-20_stateless_vs_gitswarm.md`（メモ1・改訂版） | §2-2 の比較、§2-3 の多数決・独立検証。§3.4 の実数は GitSwarm 本文（HTML v1）で節番号付き確認済み |
| `2026-10-20_sla_fulltext_reading.md`（全文読解1） | SLA の全文事実：単一実行の偏り、予算による順位逆転、再構成 vs 全履歴の実測 |
| `2026-10-20_git_swarm_fulltext_reading.md`（全文読解2） | GitSwarm の全文事実：票=調整信号（G.3）、readout 除去（H.1）、substrate 統制実験（C） |
| `2026-10-20_duodiscover_fulltext_reading.md`（全文読解3） | DuoDiscover の全文事実：fidelity test の仕様、無効化率、負の結果（Table 4） |
| `2026-10-20_context_and_eval_bottlenecks.md`（メモ2） | §2-1（文脈管理）と評価ボトルネック3層の整理 |
| `worker01`/`worker02` を除く上記に加え、`state/` 台帳 | 主張・証拠の紐付け確認（統合での台帳変更なし） |

**統合ルール（証拠の強弱）。** 同一主張には最も強い裏付け——本文確認 ＞ abs/要旨 ＞ 二次引用——を採用する。数値は出典節を伴う既存記載だけを使い、本レポートでの再取得・再計測はない。内部記録への参照は文献引用ではない。

**引用方針。** 本レポートが引用する文献は [1]〜[9] の9件で、すべて `tests/fixtures/arxiv_metadata_snapshot.json`（2026-10-20 取得）に収録済み。fixture・台帳への追加は行っていない。

## 3. §2 項目1：単一会話履歴の限界と文脈管理

- **限界の直接証拠**：企業業務のツール利用で、全会話履歴保持は 71.0% / 1,480,996 トークン / 14.56時間、直近5ツール往復への刈り込み＋要約は 91.6% / 553,374 トークン / 5.79時間（[4]、50タスク×5実行）。履歴は費用対効果が逓減し、**選択的保持が両軸で勝つ**。
- **代替の実測**：SLA は「呼び出しごとの文脈再構成」を採り、再構成を外して最大32コール・320K字の全時系列記録を読ませる variant は、共有チェックポイント継続の全4設定でフル SLA を下回った（全文読解1 §1-5、Table 4）。メモ1 §4 の「要約の質に依存する」は、この実測により「全履歴アクセスより良い」に強化されている。
- **概念枠組み**：context engineering は 1,400本超の survey で専門分野として定式化されている（[9]）。long-horizon（タスク）・long-context（モデル）・long-term memory（システム）の峻別と「outcome-only 指標の非情報化」は、文脈問題を評価問題へ接続する（[6]、メモ2 §3.3）。
- **帰属**：文脈構築は harness の決定であり [5]、文脈ポリシーの差は評価値に混入する（メモ2 §5）。したがって文脈管理の改善を「モデルの改善」として読むには、harness の開示が要る。

## 4. §2 項目2：Stateless（SLA）と GitSwarm の比較

**一致点（3）。** 会話履歴を性能の源泉にしないこと、並列探索を前提とすること、中間成果を保存して後続が再利用すること（メモ1 §4）。

**相違点（2＋1）。**

1. **決定の集中度**：SLA は stateless Advisor が実験を割り当て、GitSwarm は同質ワーカーが自律決定する（メモ1 §3.3）。全文読解3 により、DuoDiscover は「target は自己選択、資源配分はオーケストレータ」と中間に位置し、この軸は二値ではなく三値で読むべきとわかった（全文読解3 §1-6）。
2. **状態の表現**：SLA の harness 要約は文脈を小さく保つが要約の質に依存し、GitSwarm の履歴は情報を失わないが規模比例のコストを負う（メモ1 §4）。GitSwarm 自らが「永続履歴のコストはリポジトリ成長に比例し、benefits > costs の境界は長い horizon での評価が必要」と認めている（全文読解2 §7-4）。
3. **最終選択**：SLA は保護された評価器の測定値のみ（投票なし、全文読解1 §1-4）。GitSwarm は検証性能で選び、検証不能時のみ推薦多数決を使う（[2] §2.5、§3.3）。

**実数（GitSwarm 本文、メモ1 §3.4）。** ProgramBench 79.39% vs Forced Codex 65.12%、IMOProofBench-Advanced 30/30（単一実行）、分散ノミネーション 62.06±2.44% に対し中央セレクタ 64.40±1.49%。ただし9開発タスク×3シードで統計的同等性は主張されていない。再利用率は ProgramBench 94.7% に対し IMOProofBench 44.4% と2倍以上開き、証明では後続の多くが「拡張」ではなく「比較・採択」に使われる（全文読解2 §1-4）。

**SLA 側の実数。** 最大10億トークン、カーネルで最強ベースライン比 84% 以上少ないトークン、Advisor 消費はトークンの 0.6% 未満（メモ1 §3.1）。全文読解1 はさらに、Advisor はコストの 1.20–2.29% に対し SwarmResearch の Shepherd は 6.14–7.35%（Table 5）、FrontierSWE では25%予算時に最強ベースラインを下回り100%で首位と**順位が評価予算で逆転する**（§1-2）ことを確認した。

**決着しない理由。** ベンチマーク・モデル・予算が異なり同一条件の直接比較が存在しない（メモ1 §6）。加えて両論文とも大半が単一実行（全文読解1 §1-1、全文読解2 §1-7、§7-2）。

## 5. §2 項目3：多数決・独立検証・評価ボトルネック

**多数決の位置づけ（3設計で一貫）。** GitSwarm の票は「A nomination is a worker preference, not an independent verification of correctness」（[2] Appendix G.3）で、正確なコミット SHA に紐付くため改良のたびに票が分断される（全文読解2 §1-2）。SLA には投票機構自体がなく、DuoDiscover は票を使わない。**多数決は検証不能時のフォールバックに限定し、可能なら真の評価に置き換える**（メモ1 §5 の示唆）。

**独立検証＝評価器そのものの再検査。** GitSwarm の Looped Transformer では 128例評価が12組中5組の順位を誤り、512例の再評価で1組に改善（[2] §3.3）。DuoDiscover は fidelity test で τ ≥ 0.5・m=6・α=0.05 を要求し、真の評価のたびに全 yardstick を再検査、検証済みのうち 41%（リポジトリ）/45%（カーネル）が後に無効化されても false gain は出ない（全報告が f 確認済み、全文読解3 §1-4、§5.1）。**手段は標本拡大 vs 統計的検定で異なるが、方向は同じ**（全文読解3 §8）。

**負の結果（統合で最も重要な1項）。** fidelity test なしの yardstick はベースラインを下回る（[3] Table 4）。「評価器を置く」ことではなく「継続的に再検査する」ことが効く。ドリフトは例外ではなく常態（無効化率 41%/45%）。これは**代理指標一般**のリスクであって多数決のリスクではない（全文読解3 §7）。

**評価ボトルネック3層（メモ2 §4 の統合）。** (a) 最終スコアは過程のボトルネックを隠す——7モデル×36タスクで、似た最終スコアの背後には異なるプロセスの詰まりがあり、完全評価に約10万ドル [8]。(b) 観測可能性の縮小——within-run opacity・人手レビュー・統計的検出力・setup 帰属の4圧力 [7]。(c) 誤帰属——harness 固定でモデルだけ替えても harness 差が 69.7%→77.0% を動かし得る [5]。評価コストそのものが検出力を律速する（真の評価1回に数時間 [3]、§1）。

**共通モード障害（未解決のまま）。** 同質ワーカーが同じ誤解を共有すれば並列化は独立証拠を増やさない——これは理論的懸念であり、9件の文献のいずれも直接測定していない（メモ1 §5、全文読解3 §8「HYP-002 変化なし」）。

## 6. 3設計の比較（統合表）

| 軸 | SLA [1] | GitSwarm [2] | DuoDiscover [3]（検証設計の補助線） |
|---|---|---|---|
| 状態の所在 | harness（要約済み証拠＋測定値） | 共有 Git リポジトリ（履歴） | 独立ワークスペース＋オーケストレータ |
| 決定の集中度 | Advisor が実験を割当 | 各ワーカー自律（中央プランナーなし） | target は自己選択、資源配分はオーケストレータ |
| 中間成果の保存 | harness の状態 | アトミックコミット＋`informed_by=` | transfer / combine（確認済み変更の移植・統合） |
| 最終選択の接地先 | 保護された評価器の測定値 | 検証性能。不能時のみ推薦多数決 | 真の評価 f。代理指標は τ で継続再検査 |
| 票の位置づけ | なし | 調整信号（独立検証ではない、G.3） | なし |
| 主な失敗モード | 要約・Advisor 依存、単一実行 | 評価雑音、票分断、履歴の肥大 | ドリフト（未検証なら害）、単一実行 |

（表は本レポートの整理。裏付けは各メモの本文確認箇所——メモ1 §3.3、全文読解1・2・3——にある。失敗モード行は論文の主張ではない。）

## 7. Negative findings / 未解決事項

- **査読済みの知見は0件**：引用9件はすべて v1/v2 の査読前プレプリント（[9] は ongoing work の survey）。
- **単一実行が優勢**：SLA は主要構成の大半が1実行（全文読解1 §7-1）、GitSwarm は IMO 30/30 が単一実行（メモ1 §6）、DuoDiscover の Table 1 は n=1（全文読解3 §7-3）。
- **直接比較が存在しない**：9件の間に共通ベンチマークはなく、SLA/GitSwarm/DuoDiscover の優劣は証拠によって決着しない（メモ1 §6、全文読解3 §7-13）。
- **共通モード障害・多数決増幅の直接測定ゼロ**：理論的懸念のまま（§5）。
- **曖昧正解領域は未検証**：自然言語主体で正解が曖昧な文献調査への転用は全論文の評価対象外（メモ1 §6、全文読解3 §7-9）。SLA も「実行可能評価器付きタスク」のみ（全文読解1 §7-4）。
- **文脈管理→評価改善の因果分離ゼロ**：[5] はむしろ harness とモデルの混同を警告する。[5] の数値は二次引用である点も留保（メモ2 §6）。
- **内部記録（文献外）**：2026-10-19 の監査で、GitSwarm 模擬実験の成果物が実行値ではなく手書きだったこと、readout がコミット範囲に依存することが確認済み（`state/claims.jsonl` CLM-004/005/007。メモ1 §6）。

## 8. 本レポート作成時に実行した確認

- `python3 -m unittest discover -s tests` → 90件 OK
- `python3 scripts/check_citations.py` → summary: 3 arXiv source(s) checked, 1 skipped, 0 failure(s)
- `python3 scripts/check_memo_citations.py` → summary: 8 memo(s) scanned, 31 arXiv citation(s) checked, 1 skipped, 0 failure(s)
- `python3 scripts/validate_state.py` → PASS: research ledgers valid (sources=4, evidence=15, claims=7, verifications=21, hypotheses=3)
- `python3 gitswarm/benchmarks/benchmark.py --check` → PASS: benchmark artifact matches a fresh execution

（Python 3.11.2、2026-10-20。上記以外の実験・新規の文献取得・`--live` 照合は行っていない。本レポートの全引用は上記 `check_memo_citations.py` のオフライン照合で機械検証済み。）

## 9. 提案（本レポートでは実行していない）

- `core-check.yml` に `check_memo_citations.py` をオフライン検査として追加する（DoD 外の保留提案）。
- 新規引用7件を `state/sources.jsonl` に非連番IDで追記し、台帳側からも照合可能にする（同上）。
- Agora（arXiv:2609.18094、本文未読）の全文読解（同上）。
- 同一モデル・同一予算の共通ベンチマークで SLA 型と GitSwarm 型を比較する（メモ1 §8）。
- CLM-003 と EVD-20261020-0641 の明示的リンク（全文読解3 §11 提案1）。

## 10. 参考文献

[1] Qizheng Zhang, Changxiu Ji, Isaac Sun, …, Kunle Olukotun. "Stateless Language Agents: Scaling Long-Horizon Automated Research." arXiv:2610.07625v1 [cs.LG], 2026（投稿 2026-10-06）. https://arxiv.org/abs/2610.07625 / DOI: 10.48550/arXiv.2610.07625

[2] Vedant Shah, Ankur Samanta, Paras Dahal, …, Anirudh Goyal. "GitSwarm: Decentralized Compounding Inference." arXiv:2610.04862v1 [cs.AI], 2026（投稿 2026-10-04）. https://arxiv.org/abs/2610.04862 / DOI: 10.48550/arXiv.2610.04862

[3] Shubham Agarwal, Akshat Gupta, Mike Heddes, …, Chun-Liang Li. "DuoDiscover: Scaling Autonomous Discovery Beyond the Evaluation Bottleneck." arXiv:2610.17184v1 [cs.CL], 2026（投稿 2026-10-12）. https://arxiv.org/abs/2610.17184 / DOI: 10.48550/arXiv.2610.17184

[4] Abhilasha Lodha, Mahsa Pahlavikhah Varnosfaderani, Abir Chakraborty, Abhinav Mithal. "Less Context, Better Agents: Efficient Context Engineering for Long-Horizon Tool-Using LLM Agents." arXiv:2606.10209v1 [cs.AI], 2026（投稿 2026-06-08）. https://arxiv.org/abs/2606.10209 / DOI: 10.48550/arXiv.2606.10209

[5] Yunbei Zhang, Janet Wang, Yingqiang Ge, Weijie Xu, Jihun Hamm, Chandan K. Reddy. "Stop Comparing LLM Agents Without Disclosing the Harness." arXiv:2605.23950v1 [cs.AI], 2026（投稿 2026-05-07）. https://arxiv.org/abs/2605.23950 / DOI: 10.48550/arXiv.2605.23950

[6] Mingguang Chen, Licheng Wang, Bo Qu. "The Horizon Gap: Planning, Memory, Execution, Training, and Evaluation for Long-Horizon LLM Agents." arXiv:2608.06663v1 [cs.CL], 2026（投稿 2026-08-07）. https://arxiv.org/abs/2608.06663 / DOI: 10.48550/arXiv.2608.06663

[7] Toby D. Pilditch, Konstantinos Voudouris, Alexandra Abbas, Cozmin Ududec. "Transect: Retaining Observability for Long-Horizon LLM Agent Evaluations." arXiv:2610.08364v2 [cs.AI], 2026（投稿 2026-10-06）. https://arxiv.org/abs/2610.08364 / DOI: 10.48550/arXiv.2610.08364

[8] Yiwei Li, Wanli Yang, Hexiang Tan, …, Jingang Wang. "Beyond Final Scores: A Systematic Evaluation of Agents for Long-Horizon AI Research and Development." arXiv:2608.13417v1 [cs.AI], 2026（投稿 2026-08-13）. https://arxiv.org/abs/2608.13417 / DOI: 10.48550/arXiv.2608.13417

[9] Lingrui Mei, Jiayu Yao, Yuyao Ge, …, Shenghua Liu. "A Survey of Context Engineering for Large Language Models." arXiv:2507.13334v2 [cs.CL], 2025（投稿 2025-07-17）. https://arxiv.org/abs/2507.13334 / DOI: 10.48550/arXiv.2507.13334

（[1][3][6][8][9] の著者は紙幅のため先頭3名と末尾1名を記載。全著者は各 arXiv URL を参照。内部記録 `state/`・`contributions/` への参照は文献引用ではない。）
