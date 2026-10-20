# 全文読解レポート 3：DuoDiscover

- 作成日：2026-10-20
- 対象：[D1] Agarwal et al. (2026) "DuoDiscover: Scaling Autonomous Discovery Beyond the Evaluation Bottleneck" arXiv:2610.17184v1 の全文
- 位置づけ：`task/TASK.md` §1 に対応する3本目の全文読解。既存 `2026-10-20_stateless_vs_gitswarm.md` は DuoDiscover を「代理評価器（yardstick）のドリフト」の根拠として1段落で扱っている。本レポートはその記述を一次本文で裏付け直し、検証設計・分散制御・負の結果を追加する。**新しい実験は行っていない**。実行した確認は §10 に列挙する。
- 方法：arXiv HTML v1 を全19チャンク取得して通読した（PDF は不使用。理由は §2）。書誌は HTML v1 冒頭の arXiv ID・投稿日・著者と `tests/fixtures/arxiv_metadata_snapshot.json` で照合した。数値は本文の表・節番号を付記する。

## 1. 結論（全文から新しく分かったこと）

1. **「検証」の実体は、独立した再投票ではなく、真の目的 f に対する順位相関の継続再検査である。** DuoDiscover の fidelity test は、安価な代理評価器（yardstick）が f と同じ順位を付けるかを Kendall の τ で測り、基準を満たさなければ無効化する（§2.4、Appendix A.1）。ここに複数エージェントの合意も票も介在しない。GitSwarm の推薦多数決（票は調整信号）とは、検証の接地先が違う。
2. **探索による reward hacking を設計前提に置いている。** 引用：「Since the search optimizes against its yardstick, it can be rewarded for edits that exploit the gap between the yardstick and f, a form of reward hacking」（§2.4）。したがって「一度妥当だった評価器」は探索の進行そのものによって壊れる。引用：「a yardstick that initially tracks f may fail to do so for the specific edits targeted during search.」
3. **未検証の yardstick はベースラインを下回る。** アブレーション（Table 4）で、fidelity test なしの yardstick を足すと SWE-fficiency 10.33×／SOL-Exec 66.91% となり、Claude Code の 12.85×／69.12% より悪い。「評価器を置く」こと自体ではなく「継続的に再検査する」ことが効いている（§4）。引用：「Untested yardsticks hurt because rank drift misguides search.」
4. **ドリフトは例外ではなく常態である。** 検証済み yardstick のうち、後に 41%（リポジトリ）／45%（カーネル）が無効化される。それでも false gain がゼロなのは、報告されるすべての改善を真の評価で確認しているからである（§4、Table 3）。引用：「This wastes budget but never counts a false gain, since every reported gain is confirmed by a true evaluation.」
5. **評価の粒度が性能を変える。** タスク全体に1つの高速評価器を置くと、リポジトリ 14.93→12.98×、カーネル 80.80→71.36% に落ちる（Appendix E.1）。理由は Amdahl 則で、部分領域の短縮は全体の短縮と一致しない。引用：「A task-wide evaluator cannot be both fast and correlated with the true evaluation.」
6. **「中央分解なし」は「中央制御なし」ではない。** ワーカーは自分でターゲットを選ぶが、LLM のオーケストレータが terminate / spawn / brief / transfer / combine を行う（§2.3、Appendix A）。SLA の Advisor（実験の割当）と GitSwarm のプランナーなしの中間に位置する。3本を並べる際の「決定の集中度」は二値ではなく三値で読むべきである。
7. **主張の強さには明確な限界がある。** メイン結果は単一実行（§3）。DPC4 の「自律」探索には人間による探索目的の変更が入っている（Appendix D.5）。そして本論文の "discovery" は、真の評価 f がスカラーで定義できる性能最適化であり、正解が曖昧な研究課題ではない。TASK.md の比較軸に直接加えるのではなく、検証設計の補助線として読むのが妥当である。

## 2. 読解の範囲と方法（正直な記録）

- **読了**：HTML v1 の全19チャンク。Abstract、§1–§6、§6 末尾の Limitations、Acknowledgments、参考文献、Appendix A（手法詳細・A.1 fidelity test）、B（ベンチマークとベースライン）、C（拡張結果）、D（ケーススタディ D.1–D.5）、E（アブレーションとスケーリング）、F（yardstick と探索の分析）。独立した AI Usage Statement / Ethics Statement の節は HTML 上に見当たらなかった。
- **未読区間：なし**（テキストとして取得できた範囲）。ただし**図の内部数値（Figure 5・11・12 などの点列やヒートマップ）はテキスト化されていない**ため、本レポートは本文・表・図キャプションに明記された値のみを使う。図からしか読めない値は引用していない。
- **PDF を併用しなかった理由**：PDF は解析上限（約30ページ）で Appendix が途切れるため、最初から HTML v1 の全チャンクを取得した。結果として未読区間はないが、**PDF との二経路照合はしていない**（HTML v1 と fixture のみ。abs ページは今回再取得していない）。この点は SLA・GitSwarm レポート（PDF＋HTML＋abs）より弱い。
- **書誌**：arXiv:2610.17184v1 [cs.CL]、2026-10-12 投稿、ライセンス CC BY-NC-ND 4.0。著者は24名で、先頭は Shubham Agarwal, Akshat Gupta, Mike Heddes、末尾は Nanyun Peng, Chun-Liang Li。所属は UC Berkeley / Stanford / Google が混在（本文の記載どおり。所属が空の著者もいるため、個人別の所属は断定しない）。`state/sources.jsonl` の SRC-003 と `tests/fixtures/arxiv_metadata_snapshot.json` に一致（`scripts/check_citations.py` で OK）。
- **追加の資料検索：なし**。本文が参照する AlphaEvolve、SOL-ExecBench、SWE-fficiency 等は、[D1] の記載以上の内容を主張しない。
- 英語の引用はすべて取得テキストからの逐語コピーである。言い換えを引用符で囲むことはしていない。

### 主要引用箇所（逐語）

| 引用 | 節 | 何を支えるか |
|---|---|---|
| "since search can exploit gaps between a yardstick and the true objective, fidelity tests continually recheck each yardstick's ranking and invalidate any that drift" | Abstract | 検証機構の目的 |
| "the fleet is bottom-up, with no central decomposition of the problem. A lightweight orchestrator spawns and terminates agents, briefs running ones, and seeds new agents with others' confirmed work" | Abstract | 分散制御の位置づけ |
| "The absolute value of a yardstick does not need to track f, only the order it puts edits in" | §2.2 | 代理指標の要件は順序のみ |
| "The search is bottom-up, in that each agent picks its own target without an a priori decomposition of the problem, so the orchestrator's role is coordination rather than planning." | §2.3 | 「分解しない」の正確な意味 |
| "Since the search optimizes against its yardstick, it can be rewarded for edits that exploit the gap between the yardstick and f, a form of reward hacking" | §2.4 | ドリフトの構造的原因 |
| "the orchestrator re-tests every yardstick after every true evaluation" | §2.4 | 再検査の頻度 |
| "The best score seen during the run is never reported" | §3 Scoring | 楽観的選択の排除 |
| "Untested yardsticks hurt because rank drift misguides search." | §4 Ablations | 未検証代理指標の負の効果 |
| "A task-wide evaluator cannot be both fast and correlated with the true evaluation." | Appendix E.1 | 評価の粒度 |
| "The search was conducted by the agents autonomously, except for a few targeted interventions." | Appendix D.5 | 自律性の限界 |

## 3. 設計の詳細（§2、Appendix A）

### 3.1 問題設定（§2.1）

- プログラム状態 x の空間 X、初期状態 x0。編集は状態間の遷移。真の目的 f: X → R ∪ {⊥} はスカラーで高いほど良く、⊥ は正確性チェック失敗を表す。1回のコスト c_f は分〜時間（Table 8 では 3分〜28時間）。
- N エージェントが同一の wall-clock 予算と評価資源を共有する。c_f が大きいため、各エージェントが使える真の評価は「tens of true evaluations」程度に限られる（§2.1）。これが本論文の出発点である。

### 3.2 ターゲットと yardstick の共発見（§2.2）

- **target T**：コードの領域（カーネルの関数、リポジトリのモジュールなど）。X_T は T の内部だけを変えて到達できる状態集合。
- **yardstick g_T**：X_T → R ∪ {⊥} の安価な採点器。エージェントがスクリプトとして書き、スコアと正確性フラグを返す。c_g ≪ c_f。
- オーケストレータは安さを r = c_f / c_g として測り、エージェントに返す。エージェントは続行可否を自分で決める。
- **yardstick に要求されるのは順序の一致だけ**である。引用：「The absolute value of a yardstick does not need to track f, only the order it puts edits in, since the yardstick is used only to decide which edits to pursue.」形式的には、任意の x, x' について sign(g_T(x) − g_T(x')) = sign(f(x) − f(x')) を理想とする。
- **Amdahl 則による上限**：target が真のスコアの w_T を占めるなら、その領域を無限に速くしても全体の改善は 1/(1−w_T) 倍まで。エージェントは w_T の粗い推定値も書く。これは「どの target を選ぶか」の判断材料になる。
- **共発見の意味**：target は、f と相関する安価な yardstick が作れる場合にのみ価値があり、yardstick は f を実際に動かせる target に対してのみ価値がある。引用：「By co-discovery we mean that the target and the yardstick are chosen together.」

### 3.3 二重ループとオーケストレータ（§2.3）

- **fast loop**：target を編集し、yardstick で採点し、改善すれば残し、悪化すれば戻す。時間の大半はここ。
- **slow loop**：yardstick が報告した改善を真の評価 f で確認する。
- **bottom-up**：各エージェントが自分の target を選ぶ。事前の分解はない。引用：「The search is bottom-up, in that each agent picks its own target without an a priori decomposition of the problem, so the orchestrator's role is coordination rather than planning.」
- オーケストレータは LLM と補助コードからなり（Appendix A）、定期的に各エージェントの短い進捗要約を読んで3種類の行動を取る：**terminate**（進捗のないエージェント）、**spawn**（有望または未カバーの target）、**brief**（他が何を見つけたかの短い通知）。spawn は (i) 新規、(ii) 最良エージェントの確認済み状態の **transfer**、(iii) 複数エージェントの確認済み変更を1箇所に **combine**（各変更は真の評価で確認）の3形態。
- run は予算切れ、目標スコア到達、fleet の空のいずれかで終了する。

**重要な留保**：抽象の「no central decomposition」は、target の分解を中央が決めないという意味である。資源配分（どの target に多くのエージェントと真の評価を回すか）はオーケストレータが決める（§2.3、Appendix B）。したがって「プランナーなし」と読むのは誤りである。

### 3.4 fidelity test（§2.4、Appendix A.1）

- **統計量**：yardstick g_T と f の順位相関（Kendall の τ）。ただし**真の評価が分解できるペアだけ**を数える。ペア (i, j) は |f(x_i) − f(x_j)| > 2σ̂ f̄_ij のとき resolved。σ̂ は同一スナップショットの反復評価から推定した相対ノイズで、その95%上側信頼限界を使う（幸運な低サンプルでノイズを過小評価しないため）。最低分離 1% も課す。yardstick 側で同点のペアは除外する。
- **検証（validated）条件**：ノイズが測定済み、少なくとも m = 6 個の異なる状態がノイズを超えて分離、τ ≥ τ_min = 0.5、片側置換検定が α = 0.05 で独立性を棄却。引用：「A yardstick is validated when the noise has been measured, at least m=6 distinct states resolve beyond it, τ ≥ τ_min = 0.5, and the permutation test rejects independence at level α = 0.05.」
- **無効化（invalidated）条件**：同じだけの証拠があるのに τ < 0.5。有意に負の τ は即時の種類変更を強制する。無効化後、オーケストレータはその yardstick の下で登った状態に真の評価を費やすのを止め、エージェントは yardstick を建て直すか target を移る。
- **再検査の頻度**：真の評価のたびに全 yardstick を再検査する。引用：「the orchestrator re-tests every yardstick after every true evaluation.」
- **yardstick が1つも検証されない場合**：エージェントは f だけで候補を採点する（A.1）。これがフォールバックであり、性能の下限になる（F.5）。
- **設計意図**：探索が yardstick に最適化する以上、yardstick と f の隙間を突く編集が報酬になる（reward hacking）。引用：「Since the search optimizes against its yardstick, it can be rewarded for edits that exploit the gap between the yardstick and f, a form of reward hacking.」したがって検証は一度きりでは足りない。引用：「a yardstick that initially tracks f may fail to do so for the specific edits targeted during search.」

## 4. 評価設計と主要結果（§3）

### 4.1 セットアップ（§3、Appendix B）

- **ベンチマーク6種**：FormulaCode（25タスク、人手専門家の PR は 1.048×）、SWE-fficiency（100タスク、専門家パッチ 6.90×）、SOL-Exec（235カーネル）、FA4（24構成）、JAXBench（17カーネル）、TPU-Inference（7カーネル）。
- **ケーススタディ5種**：vLLM、FreeToken、SQLite、zstd、DPC4 のデータプリフェッチャ設計。
- **公平性の設計**：原則として全手法が同一ハードウェア、同一 wall-clock 予算、同一エージェント数（4）、同一同時実行数。既定は8時間・4エージェント（FormulaCode の長いタスクは24時間、TPU-Inference は10時間）。
- **スコアの取り方**：最終候補を複数回再評価した中央値を、下側信頼限界と Student-t 区間で選ぶ。引用：「The reported score of a run is the median of several re-evaluations of its final candidate, chosen by lower confidence bound, with a Student-t interval. The best score seen during the run is never reported, and a candidate that fails the correctness check is reported as no result.」— **run 中に見た最高値を報告しない**という設計は、楽観的選択（cherry-picking）を構造的に排除する。
- **反復**：メイン結果は単一実行。分散は §4 で50カーネル・20タスクを3シードで測る。引用：「Main results are single-run.」

### 4.2 主要結果（Table 1）

| 手法 | FormulaCode (×) | SWE-fficiency (×) | SOL-Exec (% SOL) | FA4 (%) | JAXBench (×) | TPU-Inference (×) |
|---|---|---|---|---|---|---|
| Claude Code | 1.778 | 12.81 | 67.31 | 7.05 | 3.82 | 2.38 |
| OpenEvolve | 1.161 | 3.76 | 52.36 | 1.48 | 2.66 | 1.14 |
| PerfAgent | 1.774 | 12.27 | 64.10 | 6.86 | 4.08 | 2.14 |
| KDA | – | – | 70.22 | 8.93 | – | – |
| **DuoDiscover** | **2.156** | **15.02** | **79.74** | **11.97** | **4.62** | **2.68** |

- FormulaCode では最強エージェント系ベースライン（Claude Code 1.778×）比 +21%。人手専門家 PR の 1.048× も上回る。変更規模は平均22ファイル・51関数・1,800行で、PerfAgent（14ファイル・800行）や OpenEvolve（2ファイル・250行）より広い。
- SWE-fficiency では専門家パッチ 6.90× に対し 15.02×。Claude Code 12.81×、PerfAgent 12.27×。
- SOL-Exec では 235カーネル中1位が121、2位が61、3位が30（上位3位以内で212）。平均 79.74% は2位エントリの 78.95% を上回る（2026-09-10 時点のリーダーボード）。
- FA4 では 11.97%（KDA 8.93%、AVO 4.11%、cuDNN 1.30%）。JAXBench 4.62×（PerfAgent 4.08×）。TPU-Inference 2.68×（Claude Code 2.38×）。
- **注意**：TPU-Inference の分母は最適化済み Pallas カーネルで、JAXBench の分母（XLA）とは異なる。論文自身が「the two suites should not be compared」と明記している（Appendix C.6）。

### 4.3 ケーススタディ（§3.2、Appendix D）

| 系 | DuoDiscover | Claude Code | 真の評価回数／候補規模 |
|---|---|---|---|
| vLLM（8×B200、20時間） | 1.92×（p99 decode 2.94×低減、first-token 3.61×低減、電力21%減、throughput 不変） | 1.07× | 7 vs 12 |
| FreeToken（L40S、20時間） | 1.44×（batch 1 で 1.17×、batch 8 で 1.76×） | 1.05× | 6 vs 14 |
| SQLite（10時間） | 1.38× | 1.12× | 17 vs 45 |
| zstd（10時間） | 1.16×（命令数比） | 1.05× | 7 vs 21 |
| DPC4 プリフェッチャ（16.7日） | +6.31%（FullBW +9.08%、LimitBW +5.93%、MC +3.93%） | –（ArchAgent v2 +3.82%、BertiGO +3.52%） | 候補 8,000（真の評価に到達したのは FullBW 38・LimitBW 27・MC 18） vs ArchAgent v2 は5段階の最初の段階のみで 12,000+ 候補・40日超 |

- vLLM では、4エージェントすべてが throughput を狙って失敗した後、オーケストレータが1体を終了し、残り3体に探索を指示。p99 decode latency・電力・first-token latency の target を見つけ、decode コストモデル（秒）と負荷スイープ（13分）で yardstick を作った。負荷スイープは高負荷で順位が反転して無効化され、2つの到着率で建て直して再度検証された（D.1）。**この「無効化→建て直し」は論文の主張を支える具体例である。**
- SQLite では、yardstick が最良確認候補より上と ranking した2候補が、真の評価では下だった（D.3）。zstd でも同様の2件がある（D.4）。**yardstick の誤順位は実在する**が、真の評価を通っていないので採用されていない。

## 5. 分析（§4）

### 5.1 yardstick の速度と忠実性（Table 3、F.1）

- 速度：リポジトリ 40秒 vs 真の評価15分（**22×**）、カーネル 16秒 vs 14分（**53×**）。
- 検証率：リポジトリは 9.2 target 中 5.3、カーネルは 15 target 中 11。
- 順位相関：検証済み yardstick の中央値は τ = 0.66（リポジトリ）、0.76（カーネル）。
- ドリフト：検証済みのうち 41%（リポジトリ）、45%（カーネル）が後に無効化される。無効化はカーネルで約15候補、リポジトリで約19候補の後。再検査は確認済みの真の評価を再利用するため、**追加の真の評価を消費しない**（F.2）。
- 引用：「This wastes budget but never counts a false gain, since every reported gain is confirmed by a true evaluation.」（§4）

### 5.2 探索効率とコスト（§4、F.3）

- カーネルで Claude Code の最終スコア 69.12% に **2.8時間**で到達。その時点でトークンは74%少なく（0.93M vs 3.6M）、真の評価は83%少ない（13 vs 76）。API コストは $309 → **$79.60**（Claude Code の全走行の25.8%）。
- 8時間完走時は 80.80%（4.4M トークン、54回の真の評価）で、50カーネル中41で Claude Code を上回る。
- リポジトリでは Claude Code のスコアに中央値 2.5時間で到達する。
- **注意**：8時間を完走すると DuoDiscover の API コストは $375 で、Claude Code の $309 より高い。優位は「同じスコアに早く着く」ことであり、総コストの安さではない（F.3、Table 17）。GPU 時間は含まない。

### 5.3 分散とアブレーション（§4）

- **シード間分散**：DuoDiscover はカーネル ±1.12%、リポジトリ ±1.8%。Claude Code は ±3.27%、±5.21%。確認された改善のうち 78%（カーネル）／81%（リポジトリ）が少なくとも2/3の run で再現する。
- **Table 4（部品を1つずつ追加）**：

| 構成 | SWE-fficiency (×) | SOL-Exec (% SOL) |
|---|---|---|
| Claude Code (N=4) | 12.85 | 69.12 |
| + target | 12.71 | 69.68 |
| + yardstick（fidelity test なし） | **10.33** | **66.91** |
| + fidelity test | 13.25 | 72.57 |
| + co-discovery | 13.76 | 74.43 |
| + orchestrator（DuoDiscover） | **14.93** | **80.80** |

  **fidelity test なしの行がベースラインを下回る**ことが最重要である。未検証の代理指標は探索を誤導し、何もしないより悪い。引用：「Untested yardsticks hurt because rank drift misguides search.」
- **Table 5（機構を1つずつ除去）**：spawn/terminate 除去で 14.10×/77.93%、allocate by progress 除去で 14.30×/78.23%、brief 除去で 14.28×/78.49%、transfer 除去で 13.92×/77.46%、combine 除去で 14.03×/76.38%。除去損失の合計は orchestrator の正味の利得より大きい。引用：「The removal losses sum to more than the orchestrator's net gain, so its actions depend on one another.」
- **backbone 一般化**：Antigravity/Gemini 3.8 Flash では 9.72→12.66×、58.79→73.26%。改善幅は 1.30×/1.25× で、Claude Code/Opus 5 の 1.16×/1.17× より大きい。DuoDiscover 適用後の Gemini はリポジトリで Opus 5 にほぼ並び（12.66 vs 12.85）、カーネルでは上回る（73.26% vs 69.12%）。

## 6. 付録で分かったこと（A・E・F）

### 6.1 ターゲット別 yardstick vs タスク全体評価器（E.1）

| 系 | 方式 | スコア | 検証率 | コスト（真の評価1回比） |
|---|---|---|---|---|
| SWE-fficiency | DuoDiscover | 14.93× | 58% | 4% |
| SWE-fficiency | タスク全体に1評価器 | 12.98× | 21% | 29% |
| SOL-Exec | DuoDiscover | 80.80% | 73% | 2% |
| SOL-Exec | タスク全体に1評価器 | 71.36% | 33% | 18% |

タスク全体の評価器は「速い」と「f と相関する」を両立できない。Amdahl 則により、部分領域の短縮率は全体の短縮率と一致しないため、異なる領域の編集をまたいで順位を誤る。引用：「A task-wide evaluator cannot be both fast and correlated with the true evaluation.」

### 6.2 fleet のスケーリング（E.2、E.3）

- N = 1 では DuoDiscover 70.26% vs Claude Code 66.47%。N = 16 では 85.96% vs 72.20%。差は 3.8 → 13.8 SOL に広がる。
- N = 16 は4エージェントの最終スコアに 2.2× 速く到達（3.4時間 vs 7.6時間）。Claude Code は 1.3×（5.4時間 vs 6.8時間）。
- 差の説明は、オーケストレータが発見を転送するのに対し、孤立エージェントは探索を重複させること。

### 6.3 探索行動（F.2、Table 16）

| 指標 | SWE-fficiency: Claude Code → DuoDiscover | SOL-Exec: Claude Code → DuoDiscover |
|---|---|---|
| 追求した target 数 | 2–4 → 9.2 | 3–7 → 15 |
| 検証された yardstick | – → 5.3 | – → 11 |
| 候補の採点数 | 72 → 358（5.0×） | 76 → 285（3.8×） |
| 真の評価回数 | 72 → 59（0.8×） | 76 → 54（0.7×） |
| 確認された改善 | 6.2 → 12.3（2.0×） | 16 → 21（1.3×） |
| 真の評価あたりの改善率 | 8.6% → 17.5% | 21.1% → 37.0% |

- yardstick は真の評価の前に候補の 81%（カーネル）／84%（リポジトリ）をふるい落とす。
- 確認された改善は「パラメータ調整」ではなく書き換え：カーネルの98%が100行超、83%が200行超、中央値約430行。リポジトリは中央値4–5ファイル・約800行。
- 探索と活用の配分：同一または関連 target にいるエージェントの割合は 5–15%（カーネル）／18%（リポジトリ）で、Claude Code の 40–60%／55% より少ない。15 target のうち8つ（53%）は改善を確認せず、早期に落とされるため真の評価の19%（カーネル）／20%（リポジトリ）しか使わない。

### 6.4 コストの内訳（F.3、Table 17）

- 8時間・4エージェント・1カーネルあたり：DuoDiscover は 276.7M トークン・$375、Claude Code は 228.0M・$309。
- DuoDiscover は 1,990 turn、Claude Code は 1,640 turn。turn あたり平均 2.2k 生成、130k キャッシュ読み、4.8k 追記。200k の文脈上限で 60k に圧縮する回数は 68 vs 56。
- 上記のとおり、スコア到達時点では $79.60 で済む。**総コストと到達時間は別の指標である。**

### 6.5 堅牢性（F.5、Table 18）

| 条件 | 挙動 |
|---|---|
| 信頼できる yardstick がない | 真の評価だけで探索。Claude Code の探索と同等（手法の下限）。カーネルで15 target 中4、リポジトリで20タスク中2が該当 |
| 誤導する yardstick を植える | 3–5回の真の評価で不一致を検出して棄却。真の評価の5–9%を費やすが、ベースラインを下回らない |
| 真の評価にノイズ | run 自身のノイズを測って検定に織り込む。timing jitter による false gain は出ない |
| α を 0.01–0.10 に振る | 確認スコアは1.4%以内。0.01 が最も低い |
| 3シード | 上記 §5.3 の分散 |

## 7. Negative findings / 制約

**論文自認（§6 Limitations、§3、Appendix D.5）：**

1. **yardstick が作れない場合のフォールバック**：信頼できる yardstick が構築できない target では、高価な真の評価による標準的探索に戻る。性能の下限はベースライン並みである。引用：「when no faithful yardstick can be constructed for a target, DuoDiscover falls back to standard search over the expensive true objective.」
2. **短い予算では不利**：yardstick の構築と初期 fidelity test には warmup コストがかかる。評価予算が極端に短い場合、優位は小さくなる（§6）。
3. **メイン結果は単一実行**：分散評価は §4 の50カーネル・20タスク・3シードのみ。Table 1 の主要数値は n=1 である。
4. **DPC4 の「自律」には人間の介入がある**：引用：「The search was conducted by the agents autonomously, except for a few targeted interventions.」具体的には、day 4 に探索スコアを FullBW 単独から FullBW と LimitBW の幾何平均に変更、day 6 に L2 プリフェッチャの編集を許可し LLC の変更も採点対象に追加、day 8 にエージェントが（指示なしで）最初の LLC プリフェッチャを書いた。最終 run では4コアの15 mix を探索スコアに追加した（D.5）。**目的関数そのものを人間が途中で変えている**ため、「完全自律の探索が人間設計を上回った」と読むのは過大である。
5. **DPC4 はプロトコルが異なる**：3エージェント、トレース並列実行、ベースラインは再実行せず論文値を使用（Table 8 の注記、B.2）。他のベンチマークと同じ比較条件ではない。
6. **FA4 の AVO・cuDNN は再実行していない**：AVO 論文の報告値をそのまま採用（Table 9、C.4）。
7. **TPU-Inference の KDA カーネルは公開リポジトリにない**：vLLM TPU-inference チームとのやり取りで提供された（C.6）。また JAXBench と TPU-Inference は分母が異なり比較不可（C.6）。
8. **SOL-Exec の順位はスナップショット**：2026-09-10 時点の公開リーダーボード。投稿は1回（C.3）。

**読者としての注意（本レポートの解釈）：**

9. **本論文の「discovery」は性能最適化である**：真の評価 f がスカラーで定義でき、正確性チェックが機械的に行える最適化課題（リポジトリ、カーネル、CPU 設計）が対象である。正解が曖昧な文献調査や仮説の真偽判定は評価対象外であり、そのまま転用できる証拠ではない。TASK.md の「長期推論・分散協調アーキテクチャ」の比較に直接加えるのではなく、**検証設計の補助線**として読むのが妥当である。
10. **fidelity test は「正しさの証明」ではない**：τ ≥ 0.5 は順位相関の緩い下限であり、ノイズで分解できるペアだけを対象にする。yardstick が f の絶対値を追う必要がない以上、yardstick のスコアを進捗として報告することはできない。通過は「今回観測した状態の範囲で、偶然よりは順位が合っている」ことを意味するに過ぎない。
11. **τ の推定には選択効果がある**：真の評価は yardstick が推薦した候補にしか行かず、検証済み yardstick だけが集計される。F.1 自身が「Two selection effects pull τ in opposite directions」と明記している。τ = 0.66/0.76 を無作為標本の推定値として扱わない。未検証 yardstick の中央値は 0.03 である。
12. **「bottom-up」は「中央なし」ではない**：§3.3 のとおり、target の分解は中央が決めないが、資源配分・終了・転送・統合はオーケストレータが決める。GitSwarm の「中央の知的プランナーなし」とは同義でない。
13. **比較対象に GitSwarm と SLA がない**：3本の間に共通ベンチマークはなく、本論文の結果を他2本と直接比較することはできない。
14. **図の内部数値は未確認**：Figure 5・11・12 などの点列はテキスト化されておらず、本レポートは本文・表・キャプションの値のみを使った。

## 8. 既存メモ・台帳との突合

| 既存の記述（場所） | 全文読解の結果 |
|---|---|
| メモ §5「DuoDiscover も、代理評価器（yardstick）が真の目的から乖離し得るため、忠実性テストで順位を再検査し、ドリフトした評価器を無効化する必要を述べる」 | **一致＋具体化**：§2.4 と A.1 で、τ ≥ 0.5・m = 6・α = 0.05・真の評価ごとの再検査を確認。無効化率 41%/45%、再検査は追加の真の評価を消費しない（F.2） |
| メモ §5「両者は『評価器そのものを検証する』方向で一致する」 | **維持**：GitSwarm は 128→512 例の再評価で誤順位を 5/12→1/12 に減らす（[2] §3.3）。DuoDiscover は τ の継続再検査でドリフトを無効化する。どちらも「評価の分解能・忠実性を上げる」方向だが、**手段は統計的検定 vs 標本拡大で異なる** |
| EVD-004 / CLM-003（多数決が誤りを増幅しうる、candidate） | **直接証拠にはならない**：本論文は投票も合意も実験対象にしていない。EVD-004 の scope_note（代理指標のドリフトの証拠として扱う）は妥当であり、CLM-003 の status は candidate のままでよい |
| EVD-003 / CLM-003（GitSwarm は検証可能なら readout を外す） | **補強**：DuoDiscover は「真の評価があるなら、代理指標は f に接地させ、最終採用は必ず f で確認する」という別実装。多数決を検証の代わりにしない点で方向が一致する |
| CLM-001（Stateless Harness は文脈埋没・重複作業を防ぐ） | **矛盾しない**：DuoDiscover もエージェントごとに独立ワークスペースを持ち、オーケストレータが確認済み状態を transfer する。ただし状態の表現は台帳ではなくコードベース＋オーケストレータであり、SLA の harness とも GitSwarm の Git 履歴とも異なる |
| CLM-002（Git 上のアトミックコミットと informed_by で推論が累積する） | **別機構**：DuoDiscover の累積は transfer / combine（確認済み変更の移植・統合）であり、Git の祖先関係や意味的依存の記録ではない。CLM-002 の証拠にはしない |
| HYP-002（同質多数決の共通モード障害、testing） | **変化なし**：直接実験は依然として存在しない。本論文の強みは「未検証の代理指標がベースラインを下回る」という負の結果であり、これは**代理指標一般**のリスクであって多数決のリスクではない |
| SRC-003 の書誌（Agarwal ほか24名、2026、cs.CL） | **一致**：HTML v1 冒頭と fixture で一致。`check_citations.py` で OK（abs ページの照合は SRC-003 の 2026-10-19 の記録であり、今回は再取得していない） |
| メモ §3.3「最終選択：SLA は規則未確認」 | **SLA 側は解消済み**（SLA 全文読解レポート §6）。本メモの表を更新した（§3.3） |

（CLM/EVD の台帳追記は本レポート単体では行っていない。G.3 の EVD 追記は承認済みの別作業として本 PR に含める。§10 参照。）

## 9. 3本の比較への示唆

1. **検証の三層**：3本を並べると、最終選択の接地先は3種類に整理できる。
   - SLA：保護された評価器の測定値（harness が保持）。投票なし。
   - GitSwarm：検証性能。検証不能時のみ推薦多数決（票は調整信号、独立検証ではない）。
   - DuoDiscover：真の評価 f。代理指標は f に対する順位相関で継続的に再検査し、採用は必ず f で確認。
   「多数決か独立検証か」の二項対立ではなく、**「何に接地するか」と「その接地をどれだけ頻繁に再確認するか」**の2軸で読む方が正確である。この整理は本レポートの解釈であり、論文の主張ではない。
2. **未検証の代理指標は害になる**：Table 4 の 10.33×/66.91% は、ResearchOS の「ゲートを回す」規約に対する強い補強である。ゲートを置くだけでは不十分で、**変更のたびに再実行する**ことが本体だという主張と同型である。ただし DuoDiscover の検証は統計的検定であり、ResearchOS の決定論的ゲート（同一入力→同一出力）とは種類が違う。同型性を主張しすぎない。
3. **粒度の設計**：ターゲット別 yardstick がタスク全体評価器に勝つ理由は Amdahl 則である。ResearchOS の台帳が「主張ごとに証拠を紐付ける」粒度を持つことは、この結果と方向が似ている。ただし本論文は性能最適化の話であり、研究台帳の粒度を正当化する直接証拠ではない。
4. **「中央分解なし」の多義性**：GitSwarm は知的プランナーなし、DuoDiscover は分解なしだが資源配分あり、SLA は Advisor が割当。3者を「集中 vs 分散」の一次元で並べると誤読する。少なくとも「target の決定」「資源配分」「最終選択」を分けて比較する必要がある。
5. **評価の正直さ**：DuoDiscover の「run 中に見た最高値を報告しない」「最終候補の再評価中央値」「失敗候補は no result」という規則は、CLM-004（手書きベンチマーク）の教訓と正面から整合する。ResearchOS の benchmark --check も「再実行で一致する値だけを載せる」点で同方向である。

## 10. 本レポート作成時に実行した確認

**変更前（2026-10-20、Python 3.11.2）：**

- `python3 -m unittest discover -s tests` → **45件 OK**（1.754秒）
- `python3 gitswarm/benchmarks/benchmark.py --check` → **PASS: benchmark artifact matches a fresh execution**
- `python3 scripts/validate_state.py` → **PASS: research ledgers valid (sources=4, evidence=14, claims=7, verifications=21, hypotheses=3)**
- `python3 scripts/check_citations.py` → **3 checked / 1 skipped / 0 failures**（SRC-001/002/003 が title・authors・year 一致、SRC-004 は arXiv ID なしで SKIP）

**読解：**

- `https://arxiv.org/html/2610.17184v1` を chunk 0–18 の**全19チャンク**取得して通読。PDF は取得していない。
- 書誌は HTML v1 冒頭（arXiv ID・投稿日・著者）と `tests/fixtures/arxiv_metadata_snapshot.json` で照合。abs ページ（`https://arxiv.org/abs/2610.17184`）は今回再取得していない（SRC-003 の記録は 2026-10-19 のもの）。
- 追加の文献検索・外部実験・`--live` 照合は**行っていない**。

**state/ への追記（承認済み）：**

- `python3 scripts/new_id.py EVD` で採番した **EVD-20261020-0641** を `state/evidence.jsonl` に追記した。内容は GitSwarm Appendix G.3 の逐語引用（票は調整信号であり独立検証ではない）で、source_id は SRC-002、confidence は high。CLM-003 へのリンクは行っていない（§11 提案1）。

**変更後（2026-10-20、Python 3.11.2）：**

- `python3 -m unittest discover -s tests` → **45件 OK**（1.668秒）
- `python3 gitswarm/benchmarks/benchmark.py --check` → **PASS**
- `python3 scripts/validate_state.py` → **PASS: research ledgers valid (sources=4, evidence=15, claims=7, verifications=21, hypotheses=3)**
- `python3 scripts/check_citations.py` → **3 checked / 1 skipped / 0 failures**

以上4ゲートは変更前・変更後の両方で緑である。`--live` 照合と外部実験は行っていない。

## 11. 提案（本レポートでは実行していない）

1. **CLM-003 と G.3 の EVD を明示的にリンクする**：今回は EVD を追記しただけで、`claim.evidence_ids` は変更していない。CLM-003 の status を変えるか、VER を追加するかは別途の承認が要る。
2. **fidelity test 型の再検査を ResearchOS に持ち込むかの検討**：ただし ResearchOS のゲートは決定論的であり、統計的検定（τ・置換検定）とは目的も失敗モードも違う。混同しない形での設計が必要。
3. **「真の評価が定義できない領域」での検証設計**：本論文の限界（f がスカラーで定義できること）は、文献調査・仮説生成ではそのまま使えない。ResearchOS の証拠台帳は、この空白を埋める設計として位置づけられるか、別の一次資料で検討する価値がある。
4. **未読区間の追加確認は不要**：HTML 全チャンクを読了しており、図の内部数値のみ未確認である。Figure 11/12 の点列が必要になった場合だけ、画像取得で補完する。

## 12. 参考文献

[D1] Shubham Agarwal, Akshat Gupta, Mike Heddes, Dilara Soylu, Rui Meng, Patrick Tser Jern Kon, Jiefeng Chen, Mert Cemri, Shu Liu, Abe Gonzalez, Akanksha Jain, Bhavana Dalvi Mishra, Linfeng Song, Vilobh Meshram, Xiangru Tang, Jinsung Yoon, Aditya Parameswaran, Ion Stoica, Vahab Mirrokni, Burak Gokturk, Parthasarathy Ranganathan, Tomas Pfister, Nanyun Peng, Chun-Liang Li. "DuoDiscover: Scaling Autonomous Discovery Beyond the Evaluation Bottleneck." arXiv:2610.17184v1 [cs.CL], 2026（投稿 2026-10-12）. https://arxiv.org/abs/2610.17184 / DOI: 10.48550/arXiv.2610.17184

[D2]（対照、本レポートでは再読していない）Vedant Shah, Ankur Samanta, Paras Dahal, …, Anirudh Goyal. "GitSwarm: Decentralized Compounding Inference." arXiv:2610.04862v1 [cs.AI], 2026. — 引用は本リポジトリの全文読解レポート 2（`2026-10-20_git_swarm_fulltext_reading.md`）に基づく。

[D3]（対照、本レポートでは再読していない）Qizheng Zhang, Changxiu Ji, Isaac Sun, …, Kunle Olukotun. "Stateless Language Agents: Scaling Long-Horizon Automated Research." arXiv:2610.07625v1 [cs.LG], 2026. — 引用は本リポジトリの全文読解レポート 1（`2026-10-20_sla_fulltext_reading.md`）に基づく。

（内部記録 `state/`・`contributions/` への参照は文献引用ではない。数値・引用はすべて [D1] の HTML v1 全19チャンクに基づく。）
