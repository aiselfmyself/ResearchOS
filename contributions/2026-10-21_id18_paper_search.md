# ID 18 文献探索：「同一タスク領域内でモデル能力差を変えた第3の実証論文」

- 日付：2026-10-21
- 担当：文献探索ワーカー（ID 18）
- 対象：`docs/incomplete-work-audit-2026-10-20.md` §13.11・§14.9、`docs/literature-triage-2026-10-21.md` §3、`contributions/2026-10-20_integrated_survey_report.md` の [8]・[9]
- 台帳：`state/sources.jsonl`・`state/evidence.jsonl`・fixture は**変更していない**。本書は書誌と逐語引用候補の報告にとどめる。

---

## 0. 結論（先に要約）

| 項目 | 判定 |
|---|---|
| ID 18 の要件（同一タスク領域・モデル能力差・ハーネス差を分けた数値）を**完全に**満たす論文 | **見つからなかった** |
| 要件に**部分的に**合う論文 | **1件**：arXiv:2606.08529（GAIA 上の 3 scaffold × 5 model 事前登録型比較）。ただし**タスク領域が [8] と異なる**・単著の arXiv プレプリント・複数の交絡あり |
| 同一タスク領域（SWE-bench 系）で、モデルとスキャフォールドの広がりを比較する論文 | 1件（arXiv:2609.17394）。ただし**観測データ**で因果は識別しないと著者自身が明記 |
| ID 18 の判定 | **部分的に前進**（「解決」ではない）。R の閾値 ~1 の検証として使える**反対側の観測**が増えた |

**最重要の発見**：探索した範囲では、R の符号・大きさが**論文・タスク領域によって一致しない**。
- [8]（SWE-bench Verified、自前の 3×3 格子）：R ≈ 0.36（ハーネス優位）
- GAIA（arXiv:2606.08529、自前の 3×5 格子）：私が Table 3 から再計算すると R ≈ 1.7〜6.3（モデル優位）
- SWE-bench 観測データ（arXiv:2609.17394）：fitted range の比 0.78、すなわち R ≈ 1.3 程度（観測的・因果ではない）

この不一致は「閾値 R~1 の枠組みが妥当か」「R がタスク領域依存か」を**まだ区別できない**ことを意味する。したがって ID 18 は未解決のまま、「部分的に前進」と判定する。

---

## 1. 検索条件と方法

### 1.1 ID 18 の要件（検索前の言い換え）

既存レポートが求める条件を次のように言い換えた。

1. **同一タスク／同一評価条件**の下で、複数の基盤モデルまたは能力水準を比較していること。
2. **モデル差とハーネス差**（scaffold、prompt、tool/control flow など）を区別できる実験設計・表・数値があること。
3. 題名・著者・公開日・版・一次資料 URL を確認できること。
4. [8]（SWE-bench Verified、100 タスク、3 モデル × 3 ハーネス）・[9]（AutoLab 由来 36 タスク、7 モデル）と**タスク領域・測定対象がどう違うか**を説明できること。

### 1.2 検索

- Web 検索：「SWE-bench scaffold vs model variance decomposition」「agent scaffold versus base model … arXiv 2026」「SWE-agent interface ablation GPT-4 Claude 3 Opus」（3 本）。
- 追加の検索・取得はすべて arXiv の HTML 版を `fetch_page` で読んだ（sandbox から arxiv への直接 curl は不可）。
- 一次資料の本文（表・節）を確認したものだけを「検証済み」と書く。検索スニペットのみのものは「未精読」と明記する。

### 1.3 除外した検索結果（理由つき）

| 候補 | 除外理由 |
|---|---|
| arXiv:2605.23950（[8] 本体、既存 SRC-20261020-07a3） | 既存の比較対象そのもの。第3論文ではない |
| arXiv:2607.13085（Baselines Before Architecture, XBOW pentest） | 同一モデル（GPT-5）で Codex/OpenCode/Pi を比べる harness 研究。**モデル能力の水準を変えた対照がハーネス格子と組になっていない**。ペンテスト領域で [8] と別 |
| arXiv:2609.09218（Double Measurement Confound） | 検索スニペットに 7 モデル × 2 × 2 の表と τ-bench の scaffold 比較があるが、本文は未精読。主題は「scaffold と scorer の二重の測定交絡」で、モデル差とハーネス差の分散比を主目的としない。**未精読のため判定保留** |
| arXiv:2605.27898（A Unified Framework for the Evaluation of LLM Agentic Capabilities） | 15 モデル・7 ベンチマーク（24 ドメイン）。固定 smolagents/ReAct の統一 scaffold で、原実装 vs 統一の比較は一部のペアのみ。モデル × ハーネスの格子も分散分解もなし。**本文一部精読（§2.4・§3.1・§3.3・§3.4 の表と Finding）**。※旧表記（2606 番台の別 ID）は誤り。確率論の別論文 |
| arXiv:2607.22585 | 次点として精読（§3.3）。2 モデルのみで R の分母・分子を比較する設計として弱い |
| arXiv:2610.00651 | 次点として精読（§3.4）。観測データの分散分解。決定的な数値ではない |

---

## 2. 候補比較表

| # | 論文（arXiv・版・公開日） | タスク領域 | モデル（能力水準の変化） | ハーネス変化 | 同一条件か | モデル差 vs ハーネス差の分離 | 精読状況 | ID 18 適合 |
|---|---|---|---|---|---|---|---|---|
| **A** | **Scaffold Effects on GAIA: A Controlled Comparison**（Starace, arXiv:2606.08529 v1, 2026-06-07 投稿） | GAIA validation L1（53 問）・L2（86 問）。汎用アシスタント型 | Opus 4.7・Sonnet 4.6・Haiku 4.5（Anthropic 内の階層）、Gemini 3.1 Pro Preview、GPT-5.5（別プロバイダ） | ReAct（S1）、Planner-Actor-Rater（S2）、Planner-then-Executor（S3） | 課題・試行回数（3）を固定。ただし S1 のツール面が事前登録と異なる（§3.6） | 3 × 5 格子で、per-cell 正答率と CI を報告。**モデル列とスキャフォールド列の広がりを同じ表から計算可能** | 本文・Table 2・3・4 を精読 | **部分的** |
| B | Coding Agents Have Converged（Liu et al., arXiv:2609.17394 v1, 2026-09-15 投稿） | SWE-bench Verified（500 件）ほか | 公開 SWE-bench 提出 254 件（4 split）から model × scaffold を公開メタデータで再構成（回帰は 20 cells・10 scaffolds・7 models の連結コア） | 公開メタデータ由来の scaffold | **観測データ**（一実行、54% は因子表に載らない） | §4.1 で fitted range：scaffold 37.6pp、model 47.9pp、比 0.78 | §4 を精読 | **同領域だが観測的** |
| C | Agent Evaluation Reliability（Hardy et al., arXiv:2610.00651 v1, 2026-09-30 投稿） | HAL の 9 ベンチマーク（SWE-bench Verified Mini を含む）・Harbor | 多数（HAL 54 モデル、うち 9 モデルが全ベンチマークに出現） | 13 scaffold（ベンチマークごとに 2〜3） | **観測データ、疎で不均衡** | 階層ベイズの G-theory 分解。プール分析で σ_M²−σ_A² の方向は約 50%（方向が定まらない） | §3.2・§5.2 を精読。ベンチマーク別の σ 値表は未抽出 | **分散分解の方法論として有用、ただし観測的** |
| D | The Scaffold Effect in Coding Agents（Vats & Golev, arXiv:2607.22585 v1, 2026-06-08 投稿） | Terminal-Bench Pro 50 タスク | 2 モデル（Qwen 3.6 Plus、MiniMax M2.5） | 3 harness（Goose・OpenCode・OpenHands-SDK） | 同一 50 タスク・同一 Harbor 基盤 | Table 6：ハーネス 0–8pp、モデル 4–10pp。論文自身が「bootstrap ノイズ内」と記す | §3.4・§4.2〜4.7 を精読 | **同一条件だがモデルが 2 つのみ** |
| E | [8] Stop Comparing LLM Agents…（Zhang (Y.) et al., arXiv:2605.23950） | SWE-bench Verified 100 件 | GPT-5.4・Kimi K2.6・GLM-5.1 | 3 harness | 同一タスク・格子 | HV/MV = 7.80（分散比）、R ≈ 0.36 | 既存レポートで精読済み（比較対象） | — |
| F | [9] Beyond Final Scores（Li et al., arXiv:2608.13417 v1） | AutoLab 36 タスク | 7 モデル | 既存レポートで扱い済み | — | avg@3 で R ≥ 4 | 既存レポートで精読済み（比較対象） | — |

---

## 3. 候補ごとの一次資料根拠

### 3.1 最有力候補 A：arXiv:2606.08529（GAIA）

**書誌**
- 題名：Scaffold Effects on GAIA: A Controlled Comparison
- 著者：Jason Starace（Independent Researcher、単著）
- 版：arXiv:2606.08529v1（Submitted on 7 Jun 2026）、cs.AI。CC BY 4.0
- URL：https://arxiv.org/abs/2606.08529 ／ HTML：https://arxiv.org/html/2606.08529v1
- DOI：10.48550/arXiv.2606.08529（arXiv 発行）
- 事前登録：「pre-registered by Starace (2026)」と記載。事前登録文書そのものは未確認

**実験設計（論文の記述・§3.5）**
- 3（scaffold）× 5（model）の因子設計、GAIA validation L1・L2（53 問・86 問）、試行 3 回。
- 完全設計は 6,255 試行。実行は 5,907 試行（§3.6：「The validation run completed 5,907 of these; 15 of the 30 (model, scaffold, level) cells are partial」）。

**同一に保たれた条件**
- 課題集合、試行回数（3）、評価器（GAIA 公式スコアラ）、推論設定（オフ、全セル共通）。
- 論文の言葉：「holding tasks and conditions fixed」（アブストラクト）。

**変えた要因**
- モデル：Anthropic 3 階層（Haiku 4.5 < Sonnet 4.6 < Opus 4.7）と、Gemini 3.1 Pro Preview・GPT-5.5（別プロバイダ）。
- ハーネス：S1 ReAct、S2 PAR（論文では「triframe-style」を改名）、S3 Planner-then-Executor。

**報告数値（逐語引用：論文の文）**
- アブストラクト（逐語）：「Scaffold choice alone moves measured accuracy by as much as 28 percentage points within a single model (Opus, Level 2, robust slice)」
- §4.1.3（逐語）：「At Level 1, the gap is small for the three frontier models (Opus 0.13, Gemini 0.06, GPT-5 0.04, primary slice) and largest for Haiku (0.23).」
- §4.1.4（逐語）：「The LRT rejects the null of no interaction in every slice」（χ²(8)=82.95 primary、p<0.0001）

**私の再計算（論文の報告値ではない）**
- 入力：Table 3（bootstrap 点推定値、primary・robust の 2 slice）。
- 方法：2 元配置（モデル 5 × scaffold 3、交互作用を残差）の主効果平方和（SS）を求め、平均平方（MS、自由度補正）から「ハーネス分散/モデル分散」を計算し、[8] と同じ定義（R = モデル間の広がり / ハーネス間の広がり、SD 比）に換算した。
- 結果：

| slice・レベル | モデル範囲（平均） | ハーネス範囲（平均） | MS_h / MS_m | R（モデル/ハーネス） |
|---|---|---|---|---|
| primary L1 | 0.459 | 0.105 | 0.038 | **5.15** |
| primary L2 | 0.479 | 0.132 | 0.090 | **3.34** |
| robust（SDK 不具合フラグを除外） L1 | 0.449 | 0.102 | 0.025 | **6.28** |
| robust（同） L2 | 0.465 | 0.197 | 0.342 | **1.71** |

- 解釈：この設計ではモデル差がスキャフォールド差を**上回る**（R > 1）。ただし以下の留意点が大きい（§3.3）。

**留意点（論文の記述に基づく）**
1. **タスク領域が [8] と異なる**：GAIA は汎用アシスタント型。[8] の SWE-bench Verified とは別。したがって「R の違いがタスク領域によるか」は本論文だけでは分からない。
2. **モデル因子が能力と提供元を混ぜている**：Gemini・GPT-5 は別プロバイダ。論文も「model family rather than capability tier the conditioning variable」と述べる。
3. **S1 のツール面が事前登録と異なる**：§3.6（逐語）「As run, S1 retained the unmodified inspect_evals tool set rather than the constant surface specified in the pre-registration; the resulting confound in s1 contrasts is discussed in Section 6」。
4. **推論を全セルでオフにした**：§3.6（逐語）「The runs applied no reasoning configuration, which Inspect AI treats as disabled」。事前登録は推論有効だった。
5. **SDK 不具合が Anthropic 側の結果を歪めた**：Appendix B・D。314 件が provider_serialization_bug と記録。robust slice はこれを除外した数値。
6. **データ欠損**：30 セル中 15 セルが partial（全て Anthropic 系）。Anthropic は credit 切れで 1,446 件が拒否された（Appendix D）。
7. **汚染リスク**：§6（逐語）「The high L1 accuracies here (top cells at 84% to 85%) may partially reflect memorization rather than capability.」
8. **単著・arXiv プレプリント**：査読は未確認。
9. **論文自身の解釈**：§5（逐語）「A reader comparing two models evaluated under different scaffolds could easily attribute to the model a difference that belongs to the agent loop.」

### 3.2 候補 B：arXiv:2609.17394（SWE-bench leaderboard 監査）

**書誌**：Liu, F. et al.（Imperial College London ほか）、「Coding Agents Have Converged: Why the SWE-bench Leaderboard Can No Longer Order Its Top Entries, and What to Measure Instead」、arXiv:2609.17394v1（15 Sep 2026、cs.SE）。

**該当節**：§4「The Number Is Not a Property of the Model」（§4.1 Holding the Model Fixed）。

**逐語**
- §4.1：「A least-squares additive fit … on the connected core (20 cells, 10 scaffolds, 7 models) gives R²=0.989 with a fitted scaffold-effect range of 37.6pp against 47.9pp for models, a ratio of 0.78.」
- §4.1（著者の限定）：「The reading is not that scaffolds matter more than models, but that the fitted ranges are of the same order.」「These are observational associations on a sparse core, not causal effects or fractions of variance explained」

**評価**
- 同じ SWE-bench Verified 領域で、モデルとスキャフォールドを両方の因子として扱う点は ID 18 に近い。
- ただし**観測データ**（公開メタデータ由来、一実行、54% は因子表に載らない）で、著者が因果と分散寄与を否定している。
- 私の換算では、fitted range の比 0.78 は R ≈ 1.3（モデル優位寄り）に相当するが、これは**著者の値ではなく私の換算**であり、因果でも分散比でもない。

### 3.3 候補 D：arXiv:2607.22585（Terminal-Bench Pro、2 モデル × 3 ハーネス）

**書誌**：Vats, N. & Golev, O.（Sentient Labs）、「The Scaffold Effect in Coding Agents: Harness Choice as a Hidden Variable in Coding-Agent Evaluation」、arXiv:2607.22585v1（08 Jun 2026、cs.AI）。

**設計**：3 harness × 2 model × 50 タスク（Terminal-Bench Pro、層化抽出）＝ 300 試行。

**逐語**
- §4.7（Table 6 の記述）：「Pass-rate effects of harness and model upgrade are of comparable magnitude and within bootstrap noise at n=50.」
- Table 6：pass rate（paired）はハーネス 0–8 pp、モデル 4–10 pp。トークン/解決タスクはハーネス 40×、モデル 1.0–1.3×。

**評価**
- 同一タスクでモデルとハーネスを両方動かし、分散を分けて報告している点は ID 18 の条件に合う。
- ただし**モデルは 2 つだけ**で、「能力水準の広がり」を変えた比較ではない。論文も差が統計的ノイズ内だと認める。
- 「ハーネスは pass rate でなくコストを変える」という知見は、R の定義とは別軸。

### 3.4 候補 C：arXiv:2610.00651（HAL・Harbor の G-theory 分解）

**書誌**：Hardy, M.（Stanford）ほか、「Agent Evaluation Reliability: More Tasks Won't (Always) Fix An Agent Leaderboard」、arXiv:2610.00651v1（30 Sep 2026、cs.AI）。

**設計**：HAL の 9 ベンチマーク（SWE-bench Verified Mini を含む）、約 29,923 ロールアウト。モデル数・scaffold 数はベンチマークごとに異なる（疎で不均衡）。

**逐語**
- §5.2（プール分析）：「the contrast σM2−σA2 favors neither direction (posterior directional probability approximately 50%)」
- 同：「task-specific variation across scaffolds is larger than task-specific variation across models with posterior probability Pr(σ_IA[B]² > σ_IM[B]² | y) = 84%」

**評価**
- 「モデル分散とスキャフォールド分散の大小」を直接推定している点で、R の推定法として参考になる。
- ただし観測データで、潜在ロジットスケールの分散であり、正答率スケールの R とは換算が必要。
- プール分析は「方向が定まらない」＝ R ≈ 1 を支持も否定もしない。ベンチマーク別の σ 値は未抽出のため、SWE-bench Verified Mini に限った判定はできない。

---

## 4. ID 18 に対する判定

**判定：部分的に前進（未解決のまま）**

理由：
1. **要件を完全に満たす論文は見つからなかった**。同一タスク領域（SWE-bench 系）× 能力水準を変えた × ハーネスを変えた × 分散を分けて数値化、の 4 条件を同時に満たすものは未発見。
2. **GAIA（A）は前進**：同一課題・事前登録型の 3 × 5 格子で、モデルとハーネスの広がりを同じ表から比較できる。ただし R > 1 側であり、[8] の R ≈ 0.36 と**反対側**の結果。タスク領域が異なるため、R の違いが「モデル/ハーネス」によるのか「タスク領域」によるのかは分離できない。
3. **SWE-bench 観測データ（B・C）は同領域だが観測的**。B は fitted range 比 0.78、C はプール分析で方向が定まらない。どちらも因果や分散比の決定的証拠にはならない。
4. **R ~ 1 を「検証済み」と言い換えてはならない**。A は R の値を報告していない（私が換算）。B・C も因果を識別しない。

**既存レポートへの含意**
- §13.11 の「2 論文を記述として両立させる枠組み」という位置づけは、A の追加でさらに弱まるのではなく、**R がタスク領域によって大きく変わる**という示唆を得た。
- 閾値 R~1 の仮説を検証するには、**同一タスク領域内で能力水準を変え、ハーネスも同時に変える**設計が必要。A はその設計に最も近いが、領域が違う。

---

## 5. 登録する場合の SRC / EVD 候補情報

**2026-10-21 に台帳へ登録済み。** 登録は state/sources.jsonl に 7 件（SRC-20261021-065a, fb4a, 9a02, f186, 4172, a714, 7176）、state/evidence.jsonl に 8 件（EVD-20261021-c1a2, 43a0, e06c, 589c, d78f, 1026, 887d, c029）。fixture（tests/fixtures/arxiv_metadata_snapshot.json）へは abs ページで確認した 8 件を追記（2026-10-21、人間の承認に基づく）。下表は登録時点の候補情報。EVD は abstract・本文で確認した逐語に絞り、未確認の本文表は根拠にしていない。

### 5.1 SRC 候補

| 候補 | 題名 | 著者 | 公開日・版 | URL | 種別 | 備考 |
|---|---|---|---|---|---|---|
| SRC-候補-1（SRC-20261021-065a） | Scaffold Effects on GAIA: A Controlled Comparison | Jason Starace | arXiv:2606.08529v1、2026-06-07 | https://arxiv.org/abs/2606.08529 | preprint | 単著、事前登録と称する（未確認）、CC BY 4.0 |
| SRC-候補-2（SRC-20261021-fb4a） | Coding Agents Have Converged: Why the SWE-bench Leaderboard Can No Longer Order Its Top Entries, and What to Measure Instead | Fengshuo Liu ほか 4 名 | arXiv:2609.17394v1、2026-09-15 | https://arxiv.org/abs/2609.17394 | preprint | 観測データの監査 |
| SRC-候補-3（SRC-20261021-9a02） | Agent Evaluation Reliability: More Tasks Won't (Always) Fix An Agent Leaderboard | Michael Hardy ほか | arXiv:2610.00651v1、2026-09-30 | https://arxiv.org/abs/2610.00651 | preprint | 観測データの G-theory 分解 |
| SRC-候補-4（SRC-20261021-f186） | The Scaffold Effect in Coding Agents: Harness Choice as a Hidden Variable in Coding-Agent Evaluation | Naman Vats, Oleg Golev | arXiv:2607.22585v1、2026-06-08 | https://arxiv.org/abs/2607.22585 | preprint | 2 モデル × 3 ハーネス |

### 5.2 EVD 候補（逐語引用候補）

| 候補 | 対象 SRC | 逐語引用（原文） | 格付け案 | 注意 |
|---|---|---|---|---|
| EVD-候補-A1 | SRC-候補-1（SRC-20261021-065a） | "Scaffold choice alone moves measured accuracy by as much as 28 percentage points within a single model (Opus, Level 2, robust slice)" | 証拠段階 B（単一プレプリント・自前実験） | 「28pp」は robust slice の値。primary では 0.704–0.830 の L1 Opus の 13pp など |
| EVD-候補-A2 | SRC-候補-1（SRC-20261021-065a） | "At Level 1, the gap is small for the three frontier models (Opus 0.13, Gemini 0.06, GPT-5 0.04, primary slice) and largest for Haiku (0.23)." | 証拠段階 B | 同上 |
| EVD-候補-A3 | SRC-候補-1（SRC-20261021-065a） | "A reader comparing two models evaluated under different scaffolds could easily attribute to the model a difference that belongs to the agent loop." | 論文の解釈（引用のみ） | 論文の主張そのもの |
| EVD-候補-B1 | SRC-候補-2（SRC-20261021-fb4a） | "The reading is not that scaffolds matter more than models, but that the fitted ranges are of the same order." | 証拠段階 C（観測） | 著者の限定を必ず併記 |
| EVD-候補-C1 | SRC-候補-3（SRC-20261021-9a02） | "the contrast σM2−σA2 favors neither direction (posterior directional probability approximately 50%)" | 証拠段階 C（観測・ベイズ） | 潜在ロジットスケール |
| EVD-候補-D1 | SRC-候補-4（SRC-20261021-f186） | "Pass-rate effects of harness and model upgrade are of comparable magnitude and within bootstrap noise at n=50." | 証拠段階 B（同一タスク、2 モデル） | 2 モデルのみ |

**私の再計算（EVD に入れるなら必ず「推論」と明示）**：A の R 換算値（5.15 / 3.34 / 6.28 / 1.71）は**論文の報告値ではない**。Table 3 の点推定から私が計算したもの。

---

## 6. 残る限界

1. **同一タスク領域での直接比較が未達**：[8] の SWE-bench Verified 格子と同じ領域・同じ課題で、能力水準を変えた第3論文は見つからなかった。
2. **A の交絡が多い**：ツール面の不一致（S1）、推論オフ、SDK 不具合、Anthropic 側の欠損、validation 集合の汚染、単著プレプリント、モデルがプロバイダと能力を混ぜている。
3. **R の定義の揺れ**：[8] は HV/MV（分散比）、B は fitted range 比、C は σ²の差、A は範囲と MS 比。単位と定義をそろえずに比べられない。本書の R（A）は私が [8] と同じ SD 比の定義に換算したもので、論文の値ではない。
4. **観測データ（B・C）は因果を識別しない**：著者自身が明記している。
5. **精読の範囲**：arXiv:2609.09218 と arXiv:2605.27898 は本文の一部（§8 参照）。全 chunk・付録表の網羅的確認は未了。arXiv:2609.32459 の SWE-bench Pro 結果は図にのみあり、本文テキストから数値を取れない（§8）。
6. **検索範囲の限界**：探索は英語の Web 検索 3 本と、既存文献集の範囲に限られる。SWE-bench 系の未発見論文（例：公式の model × scaffold 表を持つ技術報告）は残っている可能性がある。
7. **事前登録の確認なし**：A の「pre-registered」は論文の記述に基づく。事前登録文書（Starace 2026）は未確認。

---

## 7. 次の一手（提案。実行は人間の判断）

1. **arXiv:2609.32459 の図の数値取得**（SWE-bench Pro の 5+5 モデル × 2 ハーネス）。取得できれば、同一モデルファミリ内の model range と harness range を R 型に計算できる候補になる。TeX ソースは未取得。
2. **未確認の次候補**：「A Jagged Frontier」（4 モデル × mini-SWE-agent / OpenCode、SWE-bench Verified・Pro。検索スニペットのみ）、「Finding the Right Fit」（モデル × 5 ハーネスの行列、TUA-Bench 等。スニペットのみ）。両者とも本文の表で格子と分散の要件を確認する必要がある。
3. A を登録する場合、**R の値を論文の数値として書かない**。タスク領域の違いを必ず併記する。
4. ID 18 の状態は「部分的に前進」とし、「解決」には変更しない。

---

## 8. 追補（2026-10-21）：未精読 2 本の本文確認と新候補

### 8.1 arXiv:2609.09218（Zhang et al., "The Double Measurement Confound in Agent Benchmarks", v1 2026-09-06, cs.SE 系）

読了範囲：abstract、§1、§5.3–5.5、§6、§7、Appendix A.2–A.7（HTML v1、chunk 0・6・7・9・10）。

- **ID 18 での位置づけ**：タスクは ComtradeBench（trade-data 抽出、単一の seeded generator）。コーディング／SWE 系ではない。主題は「scaffold が実行判断を握るとき、スコアは model を識別しない」という測定の交絡の指摘である。モデル能力差とハーネス差の分散比を主張する論文ではない。
- **逐語（§5.4）**："Changing nothing but the scaffold flag moves the same model's reward by up to 0.267 and reorders the models (GPT-4o ties Sonnet under act yet finishes last under react)"（τ-bench、3 モデル × 4 scaffold、n=15/cell、符号検定は非有意）。
- **逐語（§5.4）**："the same slice attributes η²=0.0293 to the scaffold main effect against 0.0080 for the model."。著者は "Both shares are small against the task-level residual, and the design is single-trial, so we read only their ratio and only as an ordering" と限定している。
- **私の算出（論文の報告値ではない）**：scaffold/model の η² 比は 0.0293 / 0.0080 ≈ 3.7。単一試行・3 モデル・τ-bench の 1 スライスであり、R の証拠としては使えない。
- **2×2 本体（Table 1 相当）**：序文の要約「production scaffold では 7 モデルの payload が byte-identical」は本文で確認。Table 1 の数値は未確認。
- **制限（§6）**：Single domain（trade-data）、B1 は大効果にしか検出力がない（power 0.998 at n=20 for Δ=0.209）。

判定：**ID 18 の候補としては不適合（主題・領域が異なる）**。ただし「モデル差とハーネス差を分離する設計」と、η² を用いた順序の読み方は参考になる。

### 8.2 arXiv:2605.27898（A Unified Framework for the Evaluation of LLM Agentic Capabilities, v1 2026-05-27, cs.AI）

読了範囲：§2.4、§2.5、§3.1 の Table 2（Orig. vs Ours）、§3.3 の Finding 1–2、§3.4 の Finding 1–3、Table 3（抜粋）。

- **設計**：smolagents を標準 scaffold に固定。原実装（Orig.）と統一実装（Ours）を、ベンチマーク × モデルの一部のペアで比較。
- **逐語（§3.3 Finding 2）**："Comparing Orig. to Online isolates the framework effect, since both share the same live retrieval stack. The gaps remain large and directionally inconsistent: Qwen3-30B-A3B on BFCL rises from 17.5 to 24.5, while Llama-3.1-70B on MAB drops from 80.8 to 26.3."
- **逐語（§3.4 Finding 1）**："Under a unified scaffold, model-intrinsic capability differs in kind, not just in degree"。
- **欠けている要件**：モデル × ハーネスの格子がない。Orig. と Ours は各モデルで一部のみ。モデル差とハーネス差の分散比や R 型の指標を論文は出していない。Table 3 は統一 scaffold 下の 4 モデル（単一ハーネス）であり、ハーネス軸を含まない。

判定：**不適合（格子がない）**。ハーネス効果が「方向も大きさも不一致」だという定性的な証拠として、§5 の「既存比較」に補助的に引ける。

### 8.3 arXiv:2609.32459（Hu et al., "Beyond the Model: Demystifying Harness Effects in SE Agents", v1 2026-09-26, cs.SE）

読了範囲：abstract、§1、§3.2、§4.1–4.4、§5.1（Table 3–5）、§5.2（Table 6）、§5.3 冒頭（HTML v1、chunk 0, 2–5）。

- **設計**：SWE-bench Pro（N=300 ランダム抽出、RQ1.1）で、Qwen 5 モデル（Qwen3-Max〜Qwen3.7-Max）と DeepSeek 5 モデル（R1〜V4-Pro）を、mini-SWE-agent と OpenCode の 2 ハーネスで評価。temperature 0.0、non-thinking。モデルは同一ファミリ内で能力差をつけている（著者の論点）。
- **ID 18 に対して有利な点**：同一タスク（SWE-bench Pro）・同一ハーネス対の下で、能力階層を持つ。モデル軸とハーネス軸の両方を持つ「格子」の設計である。
- **不利な点（重要）**：
  - Figure 1 の「19.4 pt（ハーネス範囲）」と「22.8 pt（Claude モデル範囲）」は、**公開 SWE-bench Verified リーダーボードからの引用**であり、本論文の統制実験ではない。
  - SWE-bench Pro の 10 モデル × 2 ハーネスの各セルの数値は**図（Figure 5・6）にのみ**あり、本文テキストからは取れない。テキストにあるのは、Qwen の OpenCode 優位の縮小（6.00 → 2.67 pt）と、DeepSeek-V4-Pro の 34.3（OpenCode）vs 33.7（mini-SWE）の 2 点のみ。
  - 分散分解や R 型の指標は論文にない。
  - ProgramBench の結果（N=70）と GitTaskBench（N=54）はタスクが異なり、ID 18 の領域外（ただし SWE 系は ProgramBench 以外）。
  - 単一の実行（seed は未報告）。
- **逐語（§5.1.1）**："the OpenCode advantage decreases from about 6 pp for Qwen3-Max to 2.67 pp for Qwen3.7-Max, indicating that stronger Qwen models rely less on the additional scaffolding provided by the product-level harness."
- **逐語（§5.1.1）**："OpenCode brings little improvement for DeepSeek-R1, larger gains for intermediate models ... and then converges with mini-SWE-agent again for DeepSeek-V4-Pro, where the final scores are 34.3 for OpenCode and 33.7 for mini-SWE-agent."

判定：**部分的に適合（最有力の新候補）**。SWE-bench Pro の 10 モデル格子は ID 18 の要件に近い。ただし R を計算するには、図の数値（または TeX ソース内の表）が必要である。図の数値を読んだ時点で、再判定する。

### 8.4 本追補のまとめ（ID 18 の判定）

- 検証済みの一次資料で ID 18 の要件（同一タスク × 能力水準の複数 × ハーネスの格子 × 数値）を**完全に満たす論文はまだない**。
- 候補の状況：GAIA（2606.08529、部分的）、SWE-bench Pro（2609.32459、部分的、数値は図）。
- 「R ≈ 1」を検証済みとは言わない。既存の交絡（タスク領域、評価方式、予算、provider）は未解消。

### 8.5 候補 B・C・D の本文確認（2026-10-21、HTML v1）

前回 abstract のみだった 3 件を本文で確認した。台帳は EVD-20261021-e06c / 589c / d78f を更新し、EVD-20261021-1439 / 8ebb を追加した。

- **arXiv:2609.17394（候補 B）**：abstract の 29.8pp は §4.1 で確認。ただし、単一モデル（claude-3-5-sonnet, 9 scaffold）の値で、モデル内 scaffold 範囲の中央値は 15.6pp。additive fit では scaffold 効果範囲 37.6pp、model 効果範囲 47.9pp、比 0.78（R²=0.989）。論文は「not causal effects or fractions of variance explained」と明記。観測データであり、R の証拠としては弱い。
- **arXiv:2610.00651（候補 C）**：abstract の範囲（系 0.935–0.994、モデル 0.148–0.841）は §5.1 で確認（9 ベンチマーク）。§5.2 の「σM²−σA² は約 50%」「task 固有の scaffold 分散が model を上回る確率 84%」も確認。ただし、これは HAL・Harbor の観測データに対するベイズ G-theory の decision study であり、統制格子の分散比ではない。
- **arXiv:2607.22585（候補 D）**：abstract の「0–8 pp」は §4.1 Table 2 のペア差と整合（本文は「harness range 2–8 pp」「across models 4–10 pp」）。モデルは 2 のみ、n=50、95% CI は約 ±14pp で、本文自身が「most pairwise pass-rate differences are not statistically distinguishable from zero」と述べる。
- **検算不一致**：本文 Table 4（失敗カテゴリ別の solved 数）は Table 2 と 1–2 件ずれる（Goose Qwen 23 vs 24、Goose MiniMax 17 vs 19、OpenCode MiniMax 22 vs 23、OpenHands MiniMax 21 vs 23）。Table 2 と Table 5 の合計は一致。Table 4 を使うと harness 差は 10pp となり、本文の範囲と食い違う。論文の表の内部整合性の限界として記録する。

判定：候補 B・C・D はいずれも ID 18 の要件（同一タスク × 能力水準の格子 × 統制）は満たさない。どれも R の証拠としては使えない。候補 D は 2 モデルのみで、model 軸が弱い。
