# 全文読解レポート：RRSI — Regularized Recursive Self-Improvement of Agent Harnesses

- 作成日：2026-10-21
- 対象：Peng Xia et al., *RRSI: Regularized Recursive Self-Improvement of Agent Harnesses*, arXiv:2609.24972 **v3**（2026-10-04改訂、cs.LG / cs.AI / cs.CL）
- ResearchOS登録：`SRC-20261021-a3a2`
- 読解方法：absページをArena `fetch_page`で確認し、HTML v3を全15チャンク通読（§1–§6、Limitations、Appendix A–F）。表1・2・3・4・5・6・7・8・9をテキストで確認。PDFと図画像自体は未確認。
- コード照合：公式 `google-research/rrsi` をgit cloneし、HEAD `be50316e1db05914068a973f322770ef08ed7ba1`（2026-09-23）を読み取り確認。論文v3の一次根拠と、v3以前の日付を持つ公式コードの実装詳細を区別する。コードは本リポジトリへ移植していない。
- 証拠段階：**A**＝論文本文・表の直接記述／数値、**B**＝直接記述・コード・本リポジトリの検査結果からの計算または対応づけ、**C**＝未検証の実装提案。本レポートと台帳EVD 8件の抜粋はA、ResearchOSとの対応判定はB、最小構成の提案はC。

## 1. 結論（先に回答）

1. **編集数上限**は「1ラウンドの総数」ではなく、**候補ハーネス1件に束ねる独立編集数**。式の上限 `b_max` は coding / engineering で **4**、agentic workspace で **3**、名目上 `b_min=1`。ただし論文の式は `t=0,...,T-1` のループと組み合わさると最終roundでも2となり、本文の「最後は1編集」と食い違う（§3）。上限超過時に自動切り詰めはせず、公式コードではproposerに修正を返し、直せなければその候補を評価しない。
2. **criticとhold-outは別物**。RRSI criticは**評価前に候補diffを読むリーク審査**。hold-out/OODは進化後に転移性能を報告する評価面であり、候補選択をhold-out上で行う仕組みではない。ResearchOSの`holdout_eval.py`はローカルdetectorの分割診断でありcriticではない。
3. **prunerの原典基準**は`has_tests`等の参照数ではない。最近の実測score gain、相対policy-token cost、noise bandを別々に用いる。低寄与判定は「直近4/5roundのcomponent別最大実測gainが正でない」。candidateのコスト許容はgainがnoiseを超えた場合 `ΔC ≤ β0 + β1ΔS`。本文に「too small / too expensive / no longer useful」の単一の閾値があるわけではない。
4. **evolution history**はround、component、仮説、source diff、score/cost差、採否をeditごとに持つ。棄却仮説を再提案しないよう負の証拠を渡し、停滞（直近3roundのscore進歩がnoise band以下）なら未計測componentへの候補枠を予約する。
5. **モデル学習なしはRRSIの障害ではない**。RRSIはバックボーンを固定しており、重みの学習をしない。全方式の再現に必要なのは、提案・分析・criticのLLM推論、固定タスク評価、scoreとpolicy-tokenの計測である。本リポジトリは8つの決定論的CI gateを持つが、benchmark task scoreやpolicy-token telemetryがないため、selection・noise calibration・measured pruningをそのまま再現できない。
6. 暫定実装2本の判定は、いずれも **要修正**（撤回・削除ではない）。`holdout_eval.py`は追加診断として残し、RRSIのcritic/selectorではないと位置づける。`prune_candidates.py`は非破壊の構造インベントリとして残し、測定寄与に基づくprunerとは呼ばない。人間判断が必要な削除・撤回は行っていない。

## 2. 書誌照合・範囲

absページで確認した現行版はv3（最終改訂2026-10-04）。初版は2026-09-21、v2は2026-09-23。著者14名、題名、投稿年はスナップショットと一致した。`tests/fixtures/arxiv_metadata_snapshot.json`のRRSI entryは`published: 2026-09-21`（初回投稿日）であり、これは正しい。fixtureは版番号・最終改訂日を照合する設計ではないので、v3/2026-10-04はsource recordのvenueと本レポートへ記録した。**書誌の訂正は不要**。ただし`docs/literature-inventory-2026-10-19.jsonl`の記録はv2だったためv3へ更新し、v2を10月19日に確認した履歴は訂正注記に残した。

読み取った範囲はarXiv HTML v3の本文と付録。参考文献の各原典を再確認していない。図はcaption以上の画像内容を確認していない。論文の自己申告では、バックボーンを固定し、Terminal-Bench 2.1 / Harvey LAB / EngDesignで進化させてheld-out/OODへ転移評価している。研究対象はその設定であり、ResearchOSに性能改善が移ることの証明ではない。

## 3. 主要な逐語証拠（A）

以下は論文の英語原文からの抜粋。引用と評価を混ぜず、解釈は§4以降で分ける。完全な抜粋・データは各EVDに格納した。

### EVD-20261021-13f8 — proposer budget（§3.2, Eq. 4）

> “An unconstrained proposer can bundle many unrelated modifications into one candidate. Such candidates have high effective capacity: they can fit more idiosyncrasies of the current feedback, and any measured change is difficult to attribute to a particular mechanism. We therefore cap the number of independently attributable edits that may be included in one proposal.”

### EVD-20261021-5b0d — critic（§3.3）

> “Before full evaluation, a critic reads each candidate diff and rejects edits that explicitly encode task names, entity names, task-specific values, answers, or other logic specific to the evolve benchmark, as well as edits that add inert machinery. The screen targets benchmark-specific content rather than particular harness components: generic prompt or tool-description improvements remain valid candidates.”

### EVD-20261021-71a3 — edit history（Appendix D.2）

> “Every atomic edit in an evaluated candidate is tagged with a component ℓ, a hypothesis h, and the candidate source diff d. A candidate containing multiple edits contributes one history record per edit; all edits in that candidate share the same measured ΔS, ΔC, and round outcome.”

### EVD-20261021-6347 — structural pruning（Appendix D.2）

> “Thus a component is marked as unproductive when it has been exercised but has produced no strictly positive measured gain in the recent pruning window. The proposer receives B_t together with any previously accepted edits associated with those components and is instructed to remove unproductive machinery in subsequent proposals.”

### EVD-20261021-b089 — stability/cost selection（§3.3, Appendix D.3）

> “The floor prevents the search from walking downhill through a sequence of regressions that are individually small enough to be mistaken for noise. The rule allows more inference cost only when accompanied by a larger measured improvement.”

### EVD-20261021-de29 — noise calibration（Appendix E.1）

> “Measured, not chosen. The noise tolerance δ is the spread of repeated evaluations of the unchanged base harness, that is, how far apart two evaluations of the same harness land. This gives 3 passes on Terminal-Bench 2.1, 60 criterion verdicts on Harvey LAB and 5 passes on EngDesign, the last read off the first percentile of a null built by half-splitting the base evaluation’s own trials.”

### EVD-20261021-0417 — main results（§4.2, Table 1 discussion）

> “RRSI posts the smallest evolve-set gain of any evolved harness and the only out-of-distribution average that clears H₀ by more than a point, 43.6 against 39.7, which is the trade the regularizers are designed to make.”

### EVD-20261021-6951 — cost headline and ablation（Abstract; §4.3, Table 2 discussion）

> “Without the acceptance constraints the evolve-set score rises from 90.5 to 91.5 while the out-of-distribution average falls from 43.6 to 41.0 and token cost rises by half, showing that an unconstrained selection rule spends most of its accepted edits on noise and on context rather than on mechanism.”

## 4. 方法の具體な復元

### 4.1 Proposer：temporally annealed budget

論文の式は次の通り。

`b_t = ceil(b_min + (b_max - b_min) × 1/2 × (1 + cos(πt/T)))`

Table 5の設定は`T=20`（coding/workspace）、`T=40`（engineering）、`b_min=1`、`b_max=4/3/4`。これを`ceil`込みで、記載通り` t=0,...,T-1`に適用した実際の値は以下。

| domain | T | 名目b_max → b_min | 実際のround別budget（候補1件あたり） |
|---|---:|---:|---|
| Coding | 20 | 4 → 1 | 4×8 round → 3×5 → 2×7 |
| Agentic workspace | 20 | 3 → 1 | 3×10 round → 2×10 |
| Engineering design | 40 | 4 → 1 | 4×16 round → 3×9 → 2×15 |

**重要な内部不整合**：式を`t=T`で評価すれば`b_min=1`になるが、実験roundは`t=0,...,T-1`で終わる。したがって上表ではどのdomainも実際の最小値は2。Appendix E.1の「closing rounds carry a single edit」とTable 5の`b_min=1`は、式とround indexから出る値に一致しない。公式コードの`rrsi/schedule.py`も式を実装し、`budget_table(T,...)`は`range(T)`を返す。`rrsi/loop.py`のループも0からT−1。公式コードHEADは2026-09-23でv3以前なので実装履歴としての照合に限るが、論文の式・indexing自体に残る不整合は明記すべきである。

上限は**候補ごと**。公式コード設定は各round `m=2` candidateで、それぞれに`b_t`が適用されるため、round合計上限を誤って`b_t`と読まない。超過時の扱いは論文本文で細部まで規定されない。公式コードでは`done(edits=...)`で数を検査し、超過ならproposerへ「drop or merge edits if over budget」と修正を返す。自動切り詰めや評価はしない。制限内の提案を完了できず対話上限に達したcandidateは`no_proposal`として評価に進まない。

**ResearchOSへの含意（B）**：非同期PR運用にRRSIの`t/T`を持ち込むには、まず「round」と「同じbase commitから出た候補群」を定義する必要がある。Tが定まらない状態ではcosine scheduleをコピーしない方がよい。小規模導入なら「1 PR = 1主仮説／独立機構」を上限としてレビューする方が、未定義のround scheduleより監査しやすい。

### 4.2 Critic：benchmark-specificをdiffで判定

RRSI criticは評価前に候補diffを読む。論文§3.3が明記する基準は、task/entity名、task固有値、解答、evolve benchmark固有ロジック等の**diffへの持ち込み**を拒否し、汎用的なprompt/tool-description改善は候補として残すこと。Appendix Fは「候補の説明文に修正対象task名を書くこと」と「そのtask-specific内容が出荷diffに入ること」を区別する。criticはproposalの言い分だけを採点するのでなく、diffを見る。

Table 9は、単純な文字列/固有名チェックでは足りない例を示す。Meta-HarnessはHarveyの評価rubricに沿った730語の常設手順、TTHEは約8,500語のプロトコル群（うち約1,000語はredline/markup/track-changes形式向け）を蓄積した。タスク名がコードに出なくても、評価者や文書ジャンルに合わせた仕組みはOODに移らない。RRSIはHarvey LABの32候補中4編集を採択し、報告ではより汎用的な事前確定チェック／ファイル構造のprobeを残した。criticは「component種類」ではなく、「そのdiffがベンチマーク由来の情報へ過適合していないか」を審査する。

公式コードHEAD（`rrsi/critic.py`）は、汎用credential regex・domain patternのprecheckとLLM diff reviewを併用し、no-op/inert edits、grader gaming、宣言されていないbundling、memory/skillへのtask-specific state保存、unbounded work等もreject対象にする。修正依頼には上限がある。論文§4.1ではproposer・analyst・criticにClaude Opus 4.8を使う。**これは決定論的CI gateだけでは再現できない意味審査**だが、学習ではなく推論または人間レビューで代替できる。

### 4.3 Selector／pruner：三つの句を別の規則に分解

抽象の“too small / too expensive / no longer useful”を、論文本文では次のように具体化している。

| 原典の要素 | 測定／閾値 | 実装上の意味 |
|---|---|---|
| 「too small」相当 | `δ`＝H₀を反復評価して見積もるnoise band。候補gainが`ΔS≤δ`ならnoiseを超えた改善とは扱わない | file/moduleサイズやdiff行数の最小値ではない。noise帯内でも、within-band ruleによりcost削減や未採択のstructural noveltyがあればadmissibleになり得る |
| 「too expensive」 | `ΔS>δ`なら`ΔC ≤ β0 + β1ΔS`。`ΔC=(C′−C_t)/C_t`、Cは平均policy-token/trial | 追加tokenはscore gainで支払う。`β0`はgainなしで許される基本増分、`β1`はgainに応じた上積み。USD、CI秒、コード行数ではない |
| 「no longer useful」 | `g_t(l)=max{ΔS_i:l_i=l, t−t_i≤n_prune}`。`B_t={l∈T_t:g_t(l)≤0}` | 直近windowでcomponent別に**正の実測gainが一度もない**ものを削除targetにする。acceptedな機構をproposerに渡し、以後のproposalで除去を促す |

さらに候補はnoise-adjusted floor `S′(H′) ≥ S*−δ`（`S*`はbest-ever evolve score）を通る必要がある。これを下回ればcost savingやnoveltyだけでは救済されない。gainがnoise内のときはAppendix D.3の`w_sΔS − w_cΔC + w_nν_t(H′) > 0`を使う。νは、過去にwinning editとして採用されていないstructural component type（client_tool / skill / memory / subagent）を試す新規性。

Table 5のnoise/cost設定：

| domain | T | k | δ | b_max | n_prune | β0 | β1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Coding | 20 | 2 | 0.017 | 4 | 4 | 0.10 | 44.5 |
| Agentic workspace | 20 | 2 | 0.004 | 3 | 4 | 0.10 | 35.4 |
| Engineering design | 40 | 4 | 0.020 | 4 | 5 | 0.15 | 24.4 |

δはtuneせず、基準ハーネスの繰り返し測定から固定する。各domainで約3 passes / 60 criterion verdicts / 5 passes相当。β1はスコアが[0,1]であることを踏まえ、codingではpass 1件ごとに最大25%のtoken増、workspaceでは追加100 criteriaごとに25%、engineeringではpass 1件ごとに10%を許す値として校正される。**コスト効率は成果の副次的装飾でなく目的の一部**である。抽象の30% fewer policy tokensに対し、Table 2のworkspace ablationは3.80M→2.42M tokens/trial（約36.3%減）。これは表の当該設定の計算値であり、ResearchOSへの削減効果ではない。

コードのdomain configにはnoise内の`w_s/w_c/w_n`値もある（coding 0/15/0.5、workspace 1414/15/0.5、engineering 244/2/0.5）。ただしHTML Table 5の表示上はこの3重みが載らず、Appendix D.3本文はTable 5を参照している。よって厳密な再現では論文テキストだけでなく、どの版の設定ファイルを使ったかを記録する必要がある。公式コードはこの3重みをJSON設定に置く。

### 4.4 Historyが探索をどう偏らせるか

論文Appendix D.2の履歴はeditごとに`(t_i, ℓ_i, h_i, d_i, ΔS_i, ΔC_i, a_i)`、すなわちround・component・仮説・diff・測定score差・cost差・採否を記録する。候補の束ねeditは同じcandidate-level score/cost/outcomeを共有するため、結果が単独editの因果効果だと誤認しないよう、budgetを小さくするほど帰属を明瞭にする設計になっている。

この履歴から、測定済component集合`T_t`、未測定集合`U_t=K\T_t`、componentごとの直近最大gain`g_t(l)`を作る。`K`はprompt / control_flow / config / output_plumbing / context_mgmt / client_tool / skill / memory / subagent。停滞は`σ_t=1[S_t−S_{t−w}≤δ]`で定義し、`w=3`。stall時は`m_draft=1`のcandidate proposal枠を、測定例のない`U_t`から少なくとも1componentを試す枠にする。公式コードは各round `m=2`候補を作り、1枠を予約できるようにしている。これは「モデルを追加学習する」のでなく、歴史と未探索componentのリストをproposer promptへ与え、探索先を変える。

本リポジトリの`hypotheses.jsonl`、`verifications.jsonl`、`evidence.jsonl`、PR diff、監査の未対応リストはこのログの一部に似ている。しかし現行schema/運用に、各PR候補の共通score/cost測定・component別履歴・accepted winnerを一体で比較するフィールド／選択器はない。EVD件数そのものを性能scoreとして扱うこともできない。

## 5. 暫定実装への判定

### `scripts/holdout_eval.py` — **要修正**

- **残せる部分**：現在のローカルmemo/docs上で、決定論的detectorがhash分割のdevとhold-outで異なる挙動をするかを見る、非CIの補助診断。偽陽性のskip-ruleを過剰追加していないか点検する一材料にはなる。
- **原典と違う部分**：RRSI criticのようにcandidate diffを評価前に読み、task/entity/value/answer/logicを検出する機能はない。RRSIのselectorがhold-outでadoptionを決めるわけでもない。スクリプト内の既存corpusはルール開発で既に参照されており、分割はpristine OOD benchmarkでもない。
- **修正**：本文の誤った対応づけ「RRSIのadoptionはhold-outで決める」を削り、ツール説明とtest説明を「ローカルdetectorの分割診断でありcritic/selectorではない」と訂正した。機能と終了コード（instrument、exit 0）は変更していない。`adopt`等の出力語はローカルheuristicのラベルとして読む。今後selectorとして使うなら、採用判断の前にcandidate diffをレビューする別工程が要る。

### `scripts/prune_candidates.py` — **要修正**

- **残せる部分**：CI inclusion、tests有無、doc参照、importer等を一覧化し、人間が保守点検する非破壊の構造インベントリ。gateは常に`keep`、削除操作を持たない現在の安全性は妥当。
- **原典と違う部分**：これらは参照・テスト構造であって、candidate変更のΔS、policy-token ΔC、recent `n_prune` windowのcomponent別yieldを測らない。`has_tests`がfalseでも効用が低いとは限らず、CIにないgateやdeterrent checkを未使用と断定できない。
- **修正**：script / testの説明を、実測寄与prunerではなく「static usage inventory / human maintenance triage」と明示した。判定ロジック・削除動作は変えていない。真のRRSI式に近づけるには、比較可能なtask scoreとtoken telemetryを取り、`g_t(l)≤0`を複数round観測した後、人間の承認付きで削除候補を提示する必要がある。費用超過は別のselector ruleで扱う。

**両方とも撤回ではない。** 独立したローカル計測器としての効用は残る。一方、「RRSIを暫定実装した」とは呼べない。人間判断を要する削除・撤回はしていない。

## 6. 表の数値・結果（A）

### Table 1：agentic workspace、RRSIと4 baseline

| Method | Harvey LAB (Evolve) | Harvey LAB (ID held-out) | JobBench (OOD) | GDPval (OOD) | APEX-Agents (OOD) |
|---|---:|---:|---:|---:|---:|
| H₀ (no evolution) | 89.4 | 86.9 | 36.0 | 48.8 | 34.2 |
| Meta-Harness | 93.0 | 89.2 | 37.1 | 49.1 | 35.7 |
| AHE | 90.7 | 88.7 | 37.2 | 47.2 | 33.1 |
| TTHE | 91.1 | 88.5 | 35.2 | 47.0 | 31.7 |
| HarnessX | 91.8 | 89.1 | 36.3 | 48.5 | 34.3 |
| RRSI | 90.5 | 89.2 | 40.7 | 52.3 | 37.9 |

RRSIはevolveでMeta-Harnessの93.0やTTHEの91.1を上回らないが、3 OOD平均は43.6（H₀ 39.7）で最良。ID held-out Harveyは89.2（H₀ 86.9）。この比較は「evolve scoreの最大化」だけを目標としない設計を示す。

### Table 2：ablationとpolicy-token cost

| Variant | Harvey Evolve | Harvey ID held-out | OOD Avg. | Tokens/trial (million) |
|---|---:|---:|---:|---:|
| H₀ | 89.4 | 86.9 | 39.7 | 1.56 |
| Unregularized evolution | 92.8 | 88.9 | 40.3 | 3.80 |
| w/o proposal regularizers | 90.7 | 88.8 | 41.9 | 2.69 |
| w/o acceptance regularizers | 91.5 | 88.7 | 41.0 | 3.59 |
| RRSI | 90.5 | 89.2 | 43.6 | 2.42 |

Abstractの逐語表現（EVD-20261021-6951）：

> “while producing a harness that runs on 30% fewer policy tokens than the unregularized evolution.”

Table 2のworkspace ablationではRRSIはunregularizedよりOOD Avg.が3.3 point高く、tokens/trialが3.80Mから2.42Mへ約36.3%低い。proposal regularizersを外すとOOD 41.9、acceptance regularizersを外すと41.0、両方を外すと40.3。論文本文も、両群のregularizerを外すとevolve scoreは上がる一方、transferと費用が悪化すると解釈する。Abstractの30% headlineとTable 2のこのworkspace ablation値は出典範囲を分けて記録し、無理に同一値として扱わない。

### Table 3–4：policy間transfer

- Claude Opus 4.8：Terminal-Bench 2.1 74.2→80.2（+6.0）、SWE-bench Verified 82.0→83.8（+1.8）。
- Gemini 3.5 Flash：Terminal-Bench 2.1 64.6→78.7（+14.1）、SWE-bench Verified 76.8→79.0（+2.2）。
- Gemini 3.5 Flashで進化させたハーネスを未使用のGemini 3.1 Flash Liteに適用：Terminal-Bench 11.2→14.6（+3.4）。

### Table 6–8：不確実性・再走行・具体的採否

- Table 6のtask-level paired bootstrap（10,000 resamples）の9比較はすべて95% CIが正。例：Terminal-Bench +6.0 [4.3, 9.3]、SWE-bench +1.8 [1.1, 4.0]、JobBench +4.7 [2.9, 7.4]、Frontier-Eng +4.3 [1.1, 12.1]。
- Table 7は同条件で別のproposer randomnessによる再走行を報告。agentic workspaceのOOD平均は43.6と43.7。両runで全評価splitがH₀を上回る。ただし同研究内の独立再走行であり、外部研究者による追試ではない。
- Table 8：Coding R0-Aのbounded verification audit＋non-blocking pollingは+3.93点で採用。類似R0-Bは+1.69点・cost +26.1%で棄却。R8-Bはtoken cost −13.6%でもscore −2.81点でnoise-adjusted floorにより棄却。Engineering R2の既存workdirエラー向けbounded recovery hintは122/244→128/244 pass、token +1.6%で採用。scoreだけ、costだけで採否を決めない例である。

## 7. ResearchOS規模での最小構成と境界

| RRSI要素 | 学習なしで実装可能か | 現状／必要条件 |
|---|---|---|
| diff単位の仮説・変更・CI評価 | **可能・一部あり** | PR diff、HYP/VER/EVD、8 deterministic gateが土台。ただしcandidateごとの比較可能なscoreとcost、採択winnerを一体記録していない。 |
| per-candidate編集budget | **可能** | PRごとに1主機構を宣言する運用ルールはすぐ可能。cosine schedule再現には固定round数Tと同一baseの候補群が必要。paperのindex不整合を解決するまで数値は移植しない。 |
| critic | **可能だが意味審査が必要** | 人間/agentのPR review checklist、またはLLM inferenceでdiffを事前審査できる。決定論的8 gateだけではbenchmark-specific intentを十分判定できない。 |
| edit history／負の証拠／未探索component | **可能** | 2–4並列sessionならcomponent taxonomyと候補履歴をJSONL/handoffで持ち、同じ仮説の再提出を避け、3-round停滞時に未試行componentをレビュー対象にできる。score/採否を記録しない限り探索biasは手作業の誘導にとどまる。 |
| held-out/OOD評価 | **限定的に可能** | `holdout_eval.py`は静的detectorのpartition stress testとして利用可能。RRSIに近い転移評価には、候補選択に使わない固定のtask-level held-out/OODが必要。現在のmemo/docs partitionはpristineではない。 |
| noise-adjusted acceptance | **現状は困難** | RRSIのδはbaseline task-evaluationの反復差。8 gateは決定論的でありpass/fail以外の連続scoreがない。CI passを満たすことは妥当なrelease条件だが、δの代用ではない。 |
| token-cost selection／30%削減の再現 | **計測器なしでは不可** | state schemaとverificationsにpolicy-token/trial・ΔCの履歴がない。CI所要時間やEVD件数をpolicy-token cost/scoreにすり替えない。Arena側で利用可能なusage telemetryを保存し、同じtask・同じpolicy・同じ評価windowでbaseline/candidateを測る必要がある。 |
| measured component pruning | **現状は不可。安全な調査だけ可能** | `prune_candidates.py`の参照・テスト情報は保守点検用。実測ΔSとwindowがないため`g_t(l)≤0`を計算できない。削除候補の提示にも人間承認を残し、自動削除しない。 |
| model training | **不要** | RRSIはfrozen backboneが前提で、重み更新を扱わない。proposer/analyst/criticのLLM呼出しは推論。学習をしないことではなく、モデル推論・benchmark実行・score/token観測の不足が再現範囲を制限する。 |

### 小規模GitSwarm運用向けの案（C、未検証）

1. まず「round」を共通base commitから分岐した候補PR群と定義する。2–4 sessionを並列候補にするなら、全候補を同じbase・同じゲート・同じtask評価で比較し、mergeでbaseが変わった後の候補を同じroundの比較対象に混ぜない。
2. 各PRは主仮説1つ、component 1つ、diff、予測される影響、CI結果、採否理由を明記する。現在のHYP/VER/EVDに、後で実装するならscore/cost・baseline commit・round・component・acceptedを追加する。測れない値はnull/未計測とし、EVD総数をscoreとみなさない。
3. merge/評価前にreview checklistでtask name/ID、answer、task-specific constant/path、graderの参照・操作、runtime memoryへのtask data蓄積、inert edits、独立した変更の無申告bundling、unbounded loopをdiffから見る。これはRRSI criticの人間主導の近似であり、自動保証ではない。
4. 今の段階では8 CI gateを決定論的な安全条件として維持する。別のtask-level性能scoreとpolicy-token計測が導入されるまでは、noise floor・β式・30%削減の再現を主張しない。
5. prune inventoryは候補調査にのみ使い、削除・撤回は人間の指示を待つ。将来、測定可能なtask/componentができたら、δをbaseline反復で固定し、最近4–5roundのcomponent gainとtoken costを記録する。

## 8. 留保・確認事項

- 論文Limitationsはfrozen model設定、有限evolve set、regularization hyperparameter依存、異なるagent architecture/tool ecosystem/長期runへの追加検証を未解決として挙げる。
- 結果の評価judgeにはLLM判定のものもある一方、EngDesign/Frontier-Engには固定simulator/testbenchも用いる。表6のCIはtask-level bootstrapであり、同一task内のtrialを独立とはみなさない。
- Eq. (4)の最終round問題、Table 5に見えないwithin-band weight、abstractの30%とTable 2のworkspace別計算値は、論文本文と公開コードを混同せず個別に扱う。
- 本読解は論文本文の設計を本リポジトリへ移す妥当性を評価したものであり、ResearchOSでのagent性能向上・費用削減の実験結果ではない。

## 9. 台帳・変更記録

- Source：`SRC-20261021-a3a2`
- Evidence（8件、すべて原典v3から）：`EVD-20261021-13f8`, `EVD-20261021-5b0d`, `EVD-20261021-71a3`, `EVD-20261021-6347`, `EVD-20261021-b089`, `EVD-20261021-de29`, `EVD-20261021-0417`, `EVD-20261021-6951`
- Verification：`VER-20261021-508e`（source check、warn）
- **Evidence stage**：上記EVDの逐語引用と書誌/表の転記＝A。budget端点の再計算、コードとlocal scriptの対応監査＝B。§7の小規模運用案＝C。Aは原典に記載されたこと、ResearchOSでの効果は別問題。
- 本タスクで更新した説明：`scripts/holdout_eval.py`、`tests/test_holdout_eval.py`、`scripts/prune_candidates.py`、`tests/test_prune_candidates.py`のRRSI対応説明。検出ロジック・CI gate・削除動作は変更していない。
- 初期状態ではEVD 49件だった。今回8件を追記し、現在57件。

## 参考文献

[R1] Peng Xia, Rujun Han, Zifeng Wang, Yanfei Chen, Yufan Zhuang, Yoonho Lee, Chengsong Huang, Han Yu, Zhongying CuiZhu, Yifei Ming, Huaxiu Yao, Burak Gokturk, Tomas Pfister, Chen-Yu Lee. "RRSI: Regularized Recursive Self-Improvement of Agent Harnesses." arXiv:2609.24972v3 [cs.LG], 2026. https://arxiv.org/abs/2609.24972

[C1] Google Research. RRSI official code repository, checkout `be50316e1db05914068a973f322770ef08ed7ba1` (2026-09-23); files `rrsi/schedule.py`, `rrsi/propose.py`, `rrsi/critic.py`, `rrsi/history.py`, `rrsi/selection.py`, and `domains/*/rrsi.json`. https://github.com/google-research/rrsi
