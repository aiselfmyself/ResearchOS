# 全文読解レポート：Stellar Colosseum

- 作成日：2026-10-21
- 対象：Honghao Lin, David P. Woodruff, Yuan Deng, Jieming Mao, Song Zuo, Vahab Mirrokni (2026) "Stellar Colosseum: A Many-Agent Harness for Long-Horizon Research in Mathematics and Theoretical Computer Science" arXiv:2609.15983v2 [cs.AI]（v1 2026-09-14／v2 2026-09-15）
- 台帳：`SRC-20261021-2b88`。証拠は `EVD-20261021-a8af` ほか計6件（一覧は §11）。書誌照合は `VER-20261021-147b`。
- 位置づけ：`docs/worker-handoff-literature-2026-10-21.md` の優先2。問いは「反証を影響箇所へ戻す修復ループの具体的データ構造」。本リポジトリの `state/verifications.jsonl` の VER は `target_id` を1個しか持たず、反証が主張のどの部分を崩すかを表現できない。本レポートはその設計例を原典から抽出する。**新しい実験・スキーマ変更は行っていない**（§7 で提案のみ）。
- 方法：arXiv HTML v2 を全17チャンク取得して通読。Appendix A のプロンプトは HTML に埋め込まれた base64 データをデコードし、描画テキストと突き合わせた。書誌は abs ページと `tests/fixtures/arxiv_metadata_snapshot.json` で照合した。

## 1. 結論（問いへの短い答え）

1. **readiness gate に数式・数値閾値はない。** あるのは LLM に出力させる4値分類と、obligation（未解決義務）の major/minor 規則である。DuoDiscover の τ ≥ 0.5 のような統計量とは種類が違う。判定式に相当するのは Appendix A.1 のゲートプロンプトで、本レポート §4 に逐語で写す。〔証拠段階 B：`EVD-20261021-a8af`, `EVD-20261021-12a7`〕
2. **「戻し方」は DAG ＋ 欠陥の局所化フィールドで表現される。** 分解結果は section 単位の subproblem と dependency indices からなる有向非巡回グラフ。グローバル検証の欠陥は「生じた section または claim」に束ねられ、cross-section 誤りでは「supporting section とそれを使う section の両端」が記録される。再実行は失敗 subproblem に局所化し、DAG 上の他の完成済み作業は保存する。〔B：`EVD-20261021-ea49`, `EVD-20261021-5d88`〕
3. **凝集は多数決ではなく合成である。** 重複ありランダム部分標本の還元木で、候補は批判レコードと束にして運ばれ、反対意見は平均化されず前方伝搬する。論文は「constructive rather than a vote or ranking」「a concrete fatal defect is sufficient to reject」と明記する。ただし TCS-Bench の run 選択だけは8批判中5票以上という閾値付き多数決で、これは本リポジトリの `gitswarm/readout_sim.py` の対象に近い。〔B：`EVD-20261021-cd59`, `EVD-20261021-30ed`〕
4. **そのままは転用できない。借用すべきはデータモデルの抽象だけ**——「型付き異論レコードが、影響ノードID・重大度・次アクションを持つ」という形。数学証明のような機械的正誤判定がない本リポジトリでは、fatal-defect-1個で却下という規則を決定論的には実装できない。具体的な VER 拡張案は §7 に留め、実装は人間承認の別作業とする。

## 2. 読解の範囲と書誌確認（正直な記録）

### 2.1 読了範囲

- **読了**：HTML v2 の全17チャンク。Abstract、§1 Introduction、§2 Related Work、§3 Colosseum Overview、§4 Architecture and Workflow（§4.1  adversarial generation と tree aggregation／§4.2 pipeline／§4.3 shared research knowledge／§4.4 inference configurations）、§5 Selected Research Results（5.1–5.7）、§6 TCS-Bench、§7 Codeforces、§8 Conclusion and Future Directions、参考文献（65件）、Appendix A（A.1–A.4 のプロンプトテンプレート）。
- **未読・未確認**：(a) PDF は取得していない（HTML のみの単一経路）。(b) v1 と v2 の差分比較は未実施（両者とも 89KB、投稿差1日）。(c) 図はキャプションのみ。Figure 1 の内部描画（ワークフロー図・還元木の図）は画像として確認していない。(d) `--live` の arXiv API 照合は未実施（CI はオフライン fixture 照合）。
- **base64 と描画 HTML の差異**：Appendix A のデータ URI（base64）をデコードしたところ、元データ側に軽微な符号化不備が2–3箇所あった（例：`jard obstruction`（描画 HTML は `hard obstruction`）、`recarse to the full history`（描画 HTML は `without recursively retelling the full history`））。本レポートと EVD の引用は、arXiv が描画する HTML テキストを正とし、base64 はプロンプトの入出力構造・フィールド構成の確認に用いた。意味に踏み込む引用に garbled token は使っていない。
- 英語引用はすべて取得テキストからの逐語（空白は正規化）。言い換えを引用符で囲んでいない。

### 2.2 書誌照合（引継ぎ資料の誤記を1件訂正）

- title、著者6名、v1/v2 の日付は abs ページ・fixture・引継ぎ資料の3者で一致。fixture の `published: 2026-09-14` も v1 投稿日と一致するため、**fixture の修正は不要**。
- **カテゴリの誤記を訂正**：`docs/worker-handoff-literature-2026-10-21.md` は「cs.AI / cs.CL / cs.CL」と記すが、abs ページの実体は **cs.AI / cs.CL / cs.LG**（Machine Learning）である。同じ誤記が他のドキュメントにないか grep で確認したところ、該当は引継ぎドキュメントの1箇所のみで、`docs/literature-triage-2026-10-21.md` にはカテゴリ列挙自体がない。fixture にカテゴリ欄はないため fixture 側の変更はなく、`SRC-20261021-2b88` の venue 欄に正しい cs.LG を記録した。引継ぎドキュメントは人間が管理する文書であり、本レポートでは訂正せず報告のみとする（§8.4）。
- ライセンス：arXiv.org perpetual non-exclusive license。
- 主な数値（抄録・本文）：TCS-Bench 71.0%、Codeforces 218/222。TCS-Bench の他の値（直接 Pro 30.3%／DeepThink 52.0%／GPT-5.6 Pro 68.0%、Colosseum Pro 54.0%・Flash 55.0%、oracle 77.3%）と Codeforces の実行 probe 有無（218/222・rating 4263 と 213/222・3918）は本レポートの主題（修復ループのデータ構造）との関連が薄いため、§6.3 では選択規則の検証に必要な値だけを引用する。

## 3. アーキテクチャの全体像（2層構造）

Colosseum は推論を2層に編成する（Figure 1 キャプション、§1、§3）。

- **workflow 層**：strategy exploration →（readiness gate）→ decomposition → 並列 subproblem solving → assembly → global verification。却下された証明は revision（局所修理）または re-exploration（戦略の作り直し）に戻る。
- **stage 層**：どの難しい段階も単一のモデル継続に任せず、候補集団を生成し、各候補を targeted falsification にかけ、overlapping random-sample tree で合成する。候補の型（strategy／proof skeleton／section body／verifier assessment／revision）は段階で変わるが、この推論パターンは共通。
- 跨段階の文脈（§3.3、§4.3）：ラウンド内では current strategy・sectioned plan・完成 section・verifier findings が共有され、ラウンドを越えては前回の却下ドラフトとその verifier feedback が次の試行へそのまま渡る。さらに knowledge directory が探索全体の再利用知見を保持する。
- 論文が自認する設計動機の4課題（§3）：Strategic Uncertainty／Distributed Technical Difficulty／Long Outputs and Error Accumulation／**Failure and Partial Progress**。4番目が本レポートの主題に直結する——逐語：「Failed attempts may still yield useful counterexamples, restrictions, or intermediate results. To guide later work, this information must be recorded as specific mathematical claims or objections; a generic failure judgment does not explain what remains valid or what should change.」つまり「汎用の失敗判定」ではなく「何が有効なままで何を変えるべきか」を記録することが出発点にある。

## 4. 優先1：readiness gate の判定基準

### 4.1 本体（§4.2.1）——数値閾値のない質的ゲート

ゲートの問いは「証明が完成したか」ではなく「残った不確実性を、安定した証明アーキテクチャの中に局所化できるか」である。逐語：

> "The readiness gate asks whether one of these routes is concrete enough to support a proof plan. It tests whether the remaining uncertainty can be localized within a stable proof architecture, not whether the proof has already been completed. A route passes when its central reduction or mechanism is stable, its unresolved claims are precise enough to assign to proof sections, and no unresolved bridge is likely to change the target or the architecture of the argument. A central lemma may remain difficult; what matters is that its statement, role, and expected path to proof or verification are explicit. If these conditions are not met, exploration continues; otherwise, the selected route is passed to decomposition."

合格条件を分解すると3条件：

1. central reduction or mechanism が安定している；
2. 未解決 claim が proof section へ割り当てられる精密さを持つ；
3. target や argument の構造を変えかねない未解決 bridge がない。

中心補題が難しいままでもよく、必要なのは「その statement・role・証明または検証への期待経路が明示的」であること。不合格時の扱いは単純で、**exploration を継続するだけ**。別の閾値へのフォールバックやスコアはない。〔B：`EVD-20261021-a8af`〕

### 4.2 ゲートの出力スキーマ（Appendix A.1）——「判定式」に相当するもの

論文にアルゴリズム箱や擬似コードはない。ゲートのロジックはプロンプトとして与えられており、その出力仕様が実質の判定ルールである。デコードしたゲートプロンプトの核心は3部分。

**(a) 4値分類。**

> "Classify the strategy as ready for decomposition, eligible for decomposition with explicit obligations, in need of further exploration, or to be rejected."

**(b) fatal bridge 規則と major/minor obligation。**

> "A strategy with an unresolved fatal bridge cannot be marked ready. It may still proceed to decomposition, but only if the route and proof architecture are stable and every remaining obligation has a concrete proof or verification path. Treat these as minor obligations and assign each to an explicit proof or certificate section in the proof plan. An obligation is major if resolving it could require changing the route, reduced target, or core mechanism, or if it has no clear repair path. In such cases, return the strategy for further exploration."

major の定義は二項——(i) 解決が route／reduced target／core mechanism の変更を伴いうる、(ii) 明確な修理経路がない。どちらかなら探索へ差し戻す。minor は証明計画の明示 section/certificate に1個ずつ割り当てることを条件に decomposition 進行を許す。

**(c) 返却フィールド（8個、逐語）。**

> "Return the blocking issues, fatal bridge claims, theorem and criterion audits, hidden hard steps, minimal remaining obligations, obligation severity, whether decomposition is allowed, and the recommended next action."

〔B：`EVD-20261021-12a7`〕

### 4.3 読解としての注意

- 閾値らしき数値は論文全体で見ても tree aggregation の標本化計算（§6.1）だけで、ゲートには一切ない。「readiness gate の判定式」を期待して読むと、それは**フィールド名付きの定性判定**であって数式ではない、というのが正確な答えである。
- ゲートの入力には `{final strategy card}` と `{attached falser report}` があり、判定は1個の集約済み strategy card に対して下される。生成・反証・ゲートの役割分離がプロンプト上でも明示されている（"Do not solve the problem or repair the strategy. Decide whether the card is safe to turn into a proof decomposition."）。

## 5. 優先2：反証を影響箇所へ戻すルーティングのデータモデル

### 5.1 基盤データ構造：section DAG

分解器（§4.2.2、Appendix A.2）の出力は2個である。逐語：

> "The decomposer turns the selected route into a numbered, sectioned proof skeleton. Each section is associated with a subproblem specifying the mathematical content that must be established there. Dependency edges record which completed sections a subproblem may use, producing a directed acyclic graph. The document order controls the intended exposition, while the dependency graph controls the order in which the mathematical work can proceed."

プロンプトの返却仕様：

> "Return the master-document skeleton together with the same ordered list of subproblem titles, tasks, and dependency indices. Do not silently build on unresolved attacked claims. Isolate them as explicit subproblems, weaken them, or route around them."

したがって最小のデータ単位は **subproblem = {title, task, dependency indices} の三つ組**で、dependency indices は「その subproblem が依存する先行 subproblem のインデックス列」である。文書順（topological order）と依存グラフは分離されている。具体例は Table 4（Codeforces 2084F）で、`Node | Subproblem | Depends on` の3列、Node 5（C++ Implementation）の Depends on が `1,2,3,4` という実値が載る。〔B：`EVD-20261021-ea49`〕

### 5.2 欠陥の局所化——グローバル検証の「戻し方」

§4.2.3 の核心逐語：

> "Each defect is tied to the section or claim where it arises; for a cross-section dependency error, the review identifies both the supporting section and the section that uses it. This localization makes the global review actionable without reducing it to a collection of independent section checks."

Appendix A.4 のグローバル検証プロンプトは、却下時に「独立した行動可能な feedback document」を要求する：

> "If the proof is complete, accept it and preserve the complete document. Otherwise reject it and write a standalone, actionable feedback document that localizes every material defect."

そして多数決ではないことが明示される：

> "It is not a majority vote: a concrete fatal defect is sufficient to reject the proof, and generic acceptance judgments do not resolve it."

〔B：`EVD-20261021-5d88`〕

データモデル上の要点は、欠陥レコードが**1端点ではなく2端点を持ちうる**ことである。通常の欠陥は `section or claim where it arises`（1端点）。cross-section の依存誤りは `supporting section` と `the section that uses it`（2端点）。本リポジトリの VER が `target_id` 単体であるのとの最大の差がここにある。

### 5.3 戻り先の3経路

検証結果は次のどれかに流れる（§4.2.1–§4.2.3、Appendix A.3/A.4）。

1. **local retry（局所再実行）**：section が incomplete か local review が未解決欠陥を見つけた場合。逐語："the same subproblem is run again with the failed section and the review as additional input. The retry is local to the affected subproblem: completed work elsewhere in the dependency graph is preserved." 入力スロットには `{previous attempt and attached criticism, on retry}` があり、前回作業と批判がセットで渡る。
2. **revision（全体修理）**：戦略は生きている場合。section body の差し替えまたは outline 修正。Appendix A.4 は outline cleanup で許される変更を列挙し、section 追加・placeholder 捏造・計画順変更・新戦略導入を禁じる。section revision は "fix every review issue that affects that section"（その section に影響する問題だけを直す）。
3. **re-exploration（探索へ戻る）**："If the verifier's findings undermine the central strategy, the system returns to exploration instead." readiness gate の major obligation 差戻しと同じ終着点。

### 5.4 stage 内の型付きレコード（フィールド名の総覧）

反証がどの形で運ばれるか。Appendix A のプロンプトが要求する出力フィールドを、原語のまま整理する。

| レコード（段階） | フィールド（原文の名前） | 判定語彙 |
|---|---|---|
| **strategy card**（explorer, A.1） | normalized problem／primary route・backup routes（厳密に1個と最大2個）／supporting evidence and risky lemmas／first hard obstruction／active obligations／concrete next task／readiness assessment | — |
| **falser report**（adversarial reviewer, A.1） | overall assessment／categorized objections／cheap falsification tests／unresolved objections that later stages must preserve／minimal weakenings to try／verdict | verdict は4値：**survives / requires weakening or repair / should be rejected / has been falsified** |
| **readiness-gate report**（A.1） | blocking issues／fatal bridge claims／theorem and criterion audits／hidden hard steps／minimal remaining obligations／obligation severity／whether decomposition is allowed／recommended next action | 4値分類（§4.2）＋ obligation の major/minor |
| **decomposition**（decomposer, A.2） | master-document skeleton／ordered list of **subproblem titles, tasks, and dependency indices** | — |
| **section solution**（solver, A.3） | 確立した theorem/lemma/reduction/partial result／bridge claims（依存）／unproved obligations／status／retry 要求 | status は3値：**solved / partial / blocked** |
| **local falser report**（A.3） | concise summary／fatal objections／claims that later stages must not treat as established | 3値：**ready / conditional / rejected**（"Any explicit gap precludes a ready verdict."） |
| **synthesized section**（section aggregator, A.3） | claimed result／essential bridge claims／unresolved obligations／completion status／concrete reason that another attempt is needed | — |
| **global verifier feedback**（A.4） | standalone, actionable feedback document。各 material defect を発生 section/claim に局所化（cross-section は両端） | accept / reject |
| **knowledge directory entry**（curator, §4.3.2） | 4種類：theorems and lemmas／failed approaches（failure points と variants 条件付き）／references／observations。"Entries retain their source and relevant caveats." | — |

さらに §8.2 は、ハーネスが軌跡として記録するものを列挙する："candidate strategies, falsifier critiques, aggregation decisions, dependency graphs, intermediate drafts, and revision histories."

〔B：`EVD-20261021-30ed`（strategy card／falser report）、`EVD-20261021-ea49`（DAG）、`EVD-20261021-5d88`（global feedback）〕

### 5.5 反証の添付と5つの処理選択

反証は候補から分離したレコードではない。§4.1.2："Falsification records remain attached to the candidate." 集約ノードは候補とその falser report の対を入力に取り、各深刻な異論について5択で処理する（A.1 aggregator プロンプト、逐語）：

> "Address every serious falser objection: reject, weaken, or repair the attacked claim; refute the objection with a specific mathematical reason; or carry the unresolved objection forward."

すなわち **reject / weaken / repair / refute / carry forward**。carry forward された異論は後段が保存義務を負い、黙って捨てることはできない（"unresolved objections that later stages must preserve"）。なお「欠陥不発見は正しさの証明ではない」という留保も §4.1.2 にある："Here falsification refers to the search objective; failure to find a defect does not establish correctness."

### 5.6 未実装の拡張（§8.1）——ローカルな DAG 組み替え

将来方向として、失敗 subproblem の境界自体を組み替える案がある："It might split the failed subproblem, change the tasks of adjacent sections, introduce an intermediate section, or redirect local dependency edges. The revised neighborhood would retain its interface with the rest of the proof and remain acyclic"。これは現行版の機能ではない。現行の local retry は subproblem と依存関係を固定したまま section を再生成するだけである。この区別を既実装と混同してはならない。

## 6. 優先3：overlapping random-sample tree aggregation

### 6.1 数式（§4.1.3、逐語転記）

候補 `z_i` は「その候補の全 falsification record との束」である。

- 初期集団：`C^(0) = {z_1, ..., z_n}`
- 木の形：`(m_0, m_1, ..., m_L)`、ただし `m_0 = n, m_L = 1`
- レベル ℓ から ℓ+1 の各集約ノードは、現在集団から `k_l` 個の相異なる入力を一様抽出する：

  `G_j^(l) ~ Unif{ G ⊆ C^(l) : |G| = k_l },  j = 1, ..., m_{l+1}`

  「1グループ内は重複なし、ノードが異なれば標本は独立で重複しうる。partition を作らない」（"Sampling is without replacement within one group, but groups for different aggregation nodes are drawn independently and may overlap. They do not form a partition."）
- 段階特化の集約器 `A`、入力 artifact `x`、文脈証拠 `K` に対し：

  `s_j^(l+1) = A(x, K, G_j^(l))`, `C^(l+1) = {s_j^(l+1)}`
- 固定ノードが次段グループに含まれる回数の期待値：

  `E[R_i^(l)] = m_{l+1} k_l / m_l`

通常の収縮層は期待再利用が2–3になるよう幅と標本サイズを選ぶ。例は「128ノードから64、sample size 5 で期待再利用 2.5」。重複の設計意図は「各候補に複数の貢献機会を与えつつ、各集約コンテキストは小さく保つ」。

集約の性質（逐語）："Intermediate aggregation is constructive rather than a vote or ranking: it may merge compatible components, retain competing branches, repair a localized flaw, or declare an unresolved conflict. Substantive disagreements and falsification evidence are carried forward rather than averaged away."

〔B：`EVD-20261021-cd59`〕

### 6.2 実際の設定（§4.4 Table 1）

| 設定 | 段階 | 木の幅 m | k |
|---|---|---|---|
| TCS-Bench | strategy exploration | (32,16,8,5,1) | 5 |
| Codeforces | strategy exploration | (32,16,8,5,1) | 5 |
| 3設定共通 | それ以外の全段階 | (16,8,5,1) | 5 |
| オープン問題研究 | strategy exploration | 可変（100葉超の構成もあり） | 可変 |

レベル ℓ の実効標本サイズは `min{k, m_l}`。モデル呼出総数は section 数・local retry・global revision 回数にも依存し、この表では確定しない。

### 6.3 `gitswarm/readout_sim.py` との比較（本レポートの解釈、段階 C を含む）

`readout_sim.py`（`SRC-004`、既存証拠 `EVD-20261020-ffec`）は、同質ワーカーが1候補をノミネートし plurality（最多票・同点は決定論的処理）で1つを選ぶ規則を、共通モード項 `rho`（共有見解への追従率）と共有見解の正しさ `c` で決定論的にシミュレートする。Colosseum の tree aggregation との差は4点。

1. **出力関数の種類が違う。** readout は投票で1候補を選ぶ。Colosseum の集約は LLM による合成で、複数 branch の併存・局所修理・未解決衝突の宣言を許す。「平均化しない」設計は、plurality が共有誤りを隠すという §1 の問題認識と対になっている。逐語："Agreement among candidates can still hide a shared error, so a flat vote over final answers offers limited guidance for proofs."
2. **候補の多様性の作り方が違う。** Colosseum は seeds・temperature・prompt perspective・tool access・攻撃線の差で**意図的に異質な**候補を作る（§4.1.1）。readout は同一分布からの同質標本を前提にする。
3. **批判が添付される。** readout のワーカー出力は候補1個。Colosseum の `z_i` は candidate-critique bundle で、集約器は批判も消費する。
4. **共通モード障害の測定はどこにもない（段階 C の解釈）。** Colosseum は集約失敗時のワーカー間相関を実測していない。`rho` に相当するパラメータも、`c` に相当する共有見解の正しさの測定もない。したがって readout が測る現象（追従率と増幅の関係）について、この論文は直接の証拠を提供しない。`HYP-002`・`CLM-003` のステータスを動かす証拠にはならない。

**ただし例外が1箇所ある。** TCS-Bench の run 間選択（§6）は本物の閾値付き多数決である。逐語："Gemini 3.7 Flash produces eight independently sampled critiques of the Gemini 3.1 Pro proof. If at least five critiques judge that proof correct, it is submitted; otherwise, the Gemini 3.7 Flash proof is submitted. The benchmark grader is used only to score the selected proof and plays no role in the selection rule." この批判信号の弁別力は AUC 0.896、Gemini 3.1 Pro の内部 verifier 単独の routing は 64.7%。ついでに言うと、この8批判5票ルールは「証明 artifact の構築」ではなく「固定2候補の選択」に使われており、それでもなお独立した ground-truth grader を選択規則から排除している点が、GitSwarm が検証不能時のみ readout に頼る構成（`EVD-003`）と近い。

## 7. 優先4：本リポジトリ規模での実装可能性

結論：**パイプラインと閾値は転用不可。データモデルの抽象だけ借用候補。**

### 7.1 転用を阻む3つの非互換

1. **正誤判定の接地先がない。** Colosseum の「fatal defect 1個で reject」は、Lean 証明・実行 probe・形式的 statement という機械的接地があって決まる。本リポジトリの対象は非定量的な研究プロセスで、VER の pass/fail/warn/falsified は人間または LLM の判断であり、決定論的 checker ではない。
2. **DAG の密度が違う。** 論文の証明は数十 section の依存グラフ（46頁・75頁のドラフト例、§5.6）。本リポジトリの台帳は claims=8・evidence=55 規模で、claim 間リンクは疎であり、証明のような全順序的構造を持たない。
3. **計算量が違う。** 1段階あたり16–100超の葉ノード（=多数の LLM 呼出）と多段還元木。本リポジトリのワークフローは数セッション・人間統合役で動いている。

### 7.2 借用できる抽象（設計メモ、実装はしない）

Colosseum のデータモデルのうち、本リポジトリの欠け目（VER が `target_id` 1個で「どこへ返すか」を表現できない）に対応する部分は3つ。

1. **影響箇所フィールド**：欠陥を1端点だけでなく2端点（supporting／using）で持つ。VER の任意追加フィールドとして、例えば影響先 ID 列と重大度を持つ案（`affected_ids`／`severity: major|minor`／`routing_action: retry|revise|reopen`）。`schemas/verification.json` は追加フィールドを許容する設計なので後方互換は保てるが、**ガバナンス凍結の経緯（`docs/minimal-core-and-ci.md` §1.2）に照らし、人間承認の別 PR で DoD を先に書くところから**。本レポートでは追加していない。
2. **obligation としての未解決義務**：「黙って継承させず明示する」規律は、本リポジトリの claim の `status`／`limitations` 運用と同方向で、新機構なしで強化できる（反証付き claim の limitations に影響箇所を文章で明記する等）。
3. **修理の局所化**：local retry が他の完成ノードに触れない原則は、本リポジトリの訂正運用（影響範囲を限定した memo 修正＋ correction_note）と同型。既に実践されている。

### 7.3 転用してはいけないもの

- readiness gate の4値分類そのもの。「安定した証明アーキテクチャ」に対応する客観状態が文献調査にはなく、導入すれば判定者の主観をゲートの形式で覆い隠すだけになる。
- 「fatal defect 1個で reject」ルールの決定論的運用。人間判断を伴う warn を持つ現在の VER 体系の方が領域には適合する。
- tree aggregation の木構造。計算量に見合う候補多様性と機械的接地の両方がない。

## 8. 制約・負の結果・誤記訂正の扱い

### 8.1 論文側の制約（本文から）

- オープン問題研究の成果（§5.1–5.5）は companion papers に属し、Colosseum の各構成要素の寄与分離はされていない。§2.3 の逐語："Differences in human involvement, disclosure, and evaluation make it difficult to isolate the contribution of any one workflow component to these outcomes."
- TCS-Bench は300タスクで各問題1 proof ずつの評価。grader 自身は別の100件の expert-labeled proof で90%超の精度に最適化された自動採点器で、人間採点ではない。
- §8.1 の clustered exploration は "Preliminary, non-systematic runs" で、系統的評価は今後。
- ハーネス本体のコード公開は本文中で言及されていない。GitHub リンク（dpwoodru/erdos、dpwoodru/knuthCycles）は証明成果物であり、Colosseum 実装ではない。
- Erdős 再発見（§5.7）は internet access 無効、15 exploration rounds、22頁ドラフト。独立再発見であって厳密な対照実験ではない。

### 8.2 本読解の制約

§2.1 のとおり HTML v2 単一経路、PDF なし、v1/v2 差分なし、図の内部未確認。数値は本文・表・キャプションに明記されたものだけを使い、図から読み取る値は使っていない。

### 8.3 証拠段階の注記

- 本レポートの EVD 6件はすべて**段階 B**（原典の逐語引用）。
- 段階 A に相当する自前測定は新規に行っていない。`readout_sim.py` 側の記述は既存の `EVD-20261020-ffec`（段階 A の決定論的測定）に依拠した。
- §6.3 の「Colosseum には共通モード測定がない」、§7 の転用判定は**段階 C**（原典記述からの導出・解釈）。

### 8.4 人間判断を要する事項（報告のみ、操作していない）

1. `docs/worker-handoff-literature-2026-10-21.md` のカテゴリ誤記（「cs.AI / cs.CL / cs.CL」→ 正は cs.AI / cs.CL / **cs.LG**。該当はこの1箇所のみで、`docs/literature-triage-2026-10-21.md` にはカテゴリ列挙なし）。ドキュメントの改訂を伴うため、本レポートでは訂正していない。
2. §7.2 の VER スキーマ拡張案。台帳スキーマの変更であり、人間の承認と DoD の先行記述を要する。
3. 削除・撤回に該当する操作は一切行っていない。台帳は追記のみ（sources 11→12、evidence 49→55、verifications 29→30）。

## 9. 既存台帳との突合

| 既存レコード | 本論文との関係 | ステータスへの影響 |
|---|---|---|
| `CLM-003`（多数決は誤りを増幅しうる、candidate） | 定性的に補強。§1 の "a flat vote over final answers offers limited guidance for proofs" と §4.2.3 の "not a majority vote" は同方向。ただし同質ワーカーの相関障害の実測ではない | 変更なし。証拠追加はしない（対象は数学証明でドメインが異なるため） |
| `HYP-002`（共通モード障害、testing） | Colosseum は rho 相当を測定していない。§6.3 のとおり直接証拠にならない | 変更なし |
| `EVD-20261020-ffec`（readout_sim の決定論的測定、段階 A） | §6.3 の比較の自前側根拠として参照 | 変更なし |
| `SRC-004`（本リポジトリ自身） | §7 の転用判定の対象。新たな VER は不要 | 変更なし |
| DuoDiscover（`SRC-003`、τ≥0.5 の統計的ゲート） | §4.3 の対比。Colosseum のゲートが数値閾値を持たない点を際立たせる参照 | 変更なし |

## 10. 本レポート作成時に実行した確認

**変更前（2026-10-21）：** 全8ゲートが exit 0（tests 242件 OK、benchmark --check PASS、readout_sim --check PASS、validate_state PASS（sources=11/evidence=49/claims=8/verifications=29/hypotheses=2）、check_citations 10 checked/1 skipped/0 failures、check_memo_citations 17 memos/45 citations/0 failures、check_memo_ledger_refs 0 dangling、check_doc_numbers 0 stale）。

**読解：**

- `https://arxiv.org/abs/2609.15983` を取得し、書誌（title・6著者・v1/v2 日付・カテゴリ cs.AI/cs.CL/cs.LG）を確認。
- `https://arxiv.org/html/2609.15983v2` を全17チャンク取得して通読。Appendix A の base64 プロンプト10個をデコード。
- 外部実験・`--live` 照合・PDF 取得は行っていない。

**state/ への追記（追記のみ）：**

- `python3 scripts/new_id.py SRC --count 1 --date 20261021` → `SRC-20261021-2b88` を `state/sources.jsonl` に追記。
- `python3 scripts/new_id.py EVD --count 6 --date 20261021` → EVD 6件（§11）を `state/evidence.jsonl` に追記。全件 source_id は新 SRC、confidence high、quote_type は verbatim または verbatim_excerpts。
- `python3 scripts/new_id.py VER --count 1 --date 20261021` → `VER-20261021-147b`（source_check、pass）を `state/verifications.jsonl` に追記。
- 削除・既存レコードの改変・スキーマ変更はなし。

**変更後：** 全8ゲートの再実行結果は §12 に記載する。

## 11. 追記した EVD 一覧（全て証拠段階 B、confidence high）

| EVD ID | 対象節 | 内容 |
|---|---|---|
| `EVD-20261021-a8af` | §4.2.1 | readiness gate の3合格条件と不合格時の exploration 継続（数値閾値なし） |
| `EVD-20261021-12a7` | Appendix A.1 | ゲートの4値分類・fatal bridge 規則・major/minor obligation・出力8フィールド |
| `EVD-20261021-ea49` | §4.2.2, A.2 | section DAG（titles/tasks/dependency indices）と local retry の局所性 |
| `EVD-20261021-5d88` | §4.2.3, A.4 | 欠陥の section/claim 局所化と cross-section 両端リンク、多数決否定、feedback document |
| `EVD-20261021-cd59` | §4.1.3, §4.4 | 重複ランダム標本木の数式・期待再利用・constructive-not-vote・Table 1 設定 |
| `EVD-20261021-30ed` | §4.1.1–4.1.2, A.1 | strategy card 8フィールド、falser report 6フィールドと4値 verdict、批判の添付 |

## 12. 変更後の全8ゲート結果

2026-10-21、Python 3.12（CI と同系統）で実行。全て exit 0。

| # | ゲート | コマンド | 結果 |
|---|---|---|---|
| 1 | 単体テスト | `python3 -m unittest discover -s tests` | Ran 242 tests — OK |
| 2 | ベンチマーク再現性 | `python3 gitswarm/benchmarks/benchmark.py --check` | PASS: benchmark artifact matches a fresh execution |
| 3 | 投票シミュレーション再現性 | `python3 gitswarm/readout_sim.py --check` | PASS: readout-sim artifact matches a fresh execution |
| 4 | 台帳検証 | `python3 scripts/validate_state.py` | PASS: research ledgers valid (sources=12, evidence=55, claims=8, verifications=30, hypotheses=2) |
| 5 | 書誌照合 | `python3 scripts/check_citations.py` | 11 arXiv source(s) checked, 1 skipped, 0 failure(s)（新 SRC は OK SRC-20261021-2b88 2609.15983） |
| 6 | メモ引用照合 | `python3 scripts/check_memo_citations.py` | 18 memo(s), 46 arXiv citation(s) checked, 1 skipped, 0 failure(s)（本メモ [S1] も title/authors/year match） |
| 7 | メモ内台帳ID・パス参照 | `python3 scripts/check_memo_ledger_refs.py` | 18 memo(s) scanned, 0 dangling reference(s), 5 archived ID reference(s) |
| 8 | 文書内陳腐化数値 | `python3 scripts/check_doc_numbers.py` | actual: tests=242 gates=8 sources=12 evidence=55 claims=8 verifications=30 hypotheses=2 / 0 stale number(s) |

### 12.1 補足：`origin/main`（PR #44 マージ後）とのマージ後の再実行

本ブランチの PR 作成時、main は並行セッションの PR #44（SHELDON 読解、`contributions/2026-10-21_sheldon_reading.md`）をマージ済みで、共通祖先は 964005e だった。`state/sources.jsonl`・`state/evidence.jsonl`・`state/verifications.jsonl` の3ファイルで末尾追記の衝突が発生したが、両側とも基底行の変更ゼロの純粋な追記であることを diff で確認し、main 側レコード＋本ブランチの追記レコード（SRC 1・EVD 6・VER 1）の union で解決した。ID 衝突はなし（`new_id.py` のランダム接尾辞）。

マージコミット上で全8ゲートを再実行し、全て exit 0。マージ後の台帳規模は **sources=13, evidence=60, claims=9, verifications=31, hypotheses=2**（`validate_state.py` の実測）。上表の値はコミット 82110b1 単体時点の歴史的記録であり、マージで無効になるものではない。

## 13. 参考文献

[S1] Honghao Lin, David P. Woodruff, Yuan Deng, Jieming Mao, Song Zuo, Vahab Mirrokni. "Stellar Colosseum: A Many-Agent Harness for Long-Horizon Research in Mathematics and Theoretical Computer Science." arXiv:2609.15983v2 [cs.AI], 2026（v1 投稿 2026-09-14、v2 2026-09-15）. https://arxiv.org/abs/2609.15983 / HTML: https://arxiv.org/html/2609.15983v2 / DOI: 10.48550/arXiv.2609.15983

（内部記録 `state/`・`contributions/`・`gitswarm/`・`schemas/`・`docs/` への参照は文献引用ではない。英語引用はすべて [S1] の HTML v2（本文及び Appendix A のデコード済みプロンプト）に基づく逐語である。）
