# 統合読解レポート：Agora — Git as Shared Memory for Collective AutoResearch

- 作成日：2026-10-20
- 作成者：統合役（integrator）
- 対象：Yifan Zhang, Yunheng Zou, Shaokun Zhang, Jian Hu, Hao Zhang, Binfeng Xu, Jan Kautz, Yi Dong. "Agora: Git as Shared Memory for Collective AutoResearch." arXiv:2609.18094
- 典拠の版：**v4（2026-09-30 13:03:05 UTC、最新）を統合役が照合**。セッション A と A′ は **v1（2026-09-16）** を読んでいる。
- 位置づけ：`docs/parallel-experiment-2026-10-20.md` の並列稼働実験において、読解セッション A と A′ が提出した 2 本のレポートを 1 本に統合したもの。あわせて、両セッションが読んでいない v2–v4 を統合役が確認し、差分を本レポートに反映した（§1）。
- 元の 2 本（`2026-10-20_agora_fulltext_reading.md` ＝ A、`2026-10-20_agora_fulltext_reading_r2.md` ＝ A′）は**削除しない**。E2（誤り相関の観測）の生データであり、計測器 `scripts/measure_agreement.py` が参照する `.json` と対になっているため、実験記録として保持する。

---

## 0. 要旨（この 1 本を読めば分かること）

1. Agora は「研究の状態を append-only の Git DAG として共有する」システムである。13 体のコーディングエージェントが約 12 日間、1,703 件の投稿を通じて、凍結した 119.6M パラメータのモデルを **3.3923 bpb → 1.899044 bpb** へ初期化し、学習済み GPT-2 124M（約 1.0 bpb）との差の **62%** を勾配更新なしで埋めた（§5.2）。
2. ただしこれは **1 コミュニティ・1 走行**である。Agora 有無を比較する統制実験は**提案のみで未実施**（Appendix C）。
3. **v4 は v1 から数値と解釈の両方を改訂している。** 特に (a) 「並行再発見」696 組 → **523 組**に訂正され、**「独立な再発見ではなく収束」と明示的に読み替えられた**。(b) 人間の介入が v1 の記述より大幅に多く開示された（サーバ 3 回変更、プロンプト 1 回変更、8 ワーカーへの個別指示、著者による手動セッション 3 回、DB 直接編集）。(c) **8 台の H100 ワーカーは同一ノード上の別コンテナであり、互いのプロセスを一覧できた**ことが新たに明記された（§1、§6.4）。
4. 本リポジトリの E2（誤り相関 ρ の観測）にとって、v4 は v1 より **情報量が増えたが、使える測定値にはならなかった**。Agora は誤り率を測っていない。ただし v4 は「同一ノードでのプロセス可視性」という、相関を生む具体的な**機構**を初めて名指ししており、これは将来の計測器設計への直接的な入力になる（§9）。

---

## 1. v1 → v4 の差分（統合役が 2026-10-20 に確認）

両セッションは v1 を読んだ。v4 は最新である。統合役が `https://arxiv.org/abs/2609.18094v4` と `https://arxiv.org/html/2609.18094v4`（全 12 チャンクのうち §1、§2 一部、§4.2–§5、References を照合）を取得し、以下を確認した。

### 1.1 版の履歴

| 版 | 投稿日 (UTC) | PDF サイズ |
|---|---|---|
| v1 | 2026-09-16 | 2,384 KB |
| v2 | 2026-09-18 | 2,396 KB |
| v3 | 2026-09-22 | 2,390 KB |
| **v4** | **2026-09-30 13:03:05** | **2,295 KB** |

分類（cs.LG / cs.AI / cs.CL）と DOI（10.48550/arXiv.2609.18094）は不変。**要旨（abstract）は v1 と v4 で数値が完全に一致する**（13 workers、約 12 日、141 donors、119.6M、1,703 contributions、3.39→1.899、62%、145 commits/15 accounts、165 verifications/95 targets/no failures、「per unit of compute の効果測定には matched comparison が必要」）。

### 1.2 変更点の一覧

**数値の変更**

| 項目 | v1（A・A′ が読んだ値） | v4（統合役が確認した値） | 影響 |
|---|---|---|---|
| 同一スコアを投稿したアカウント対 | 696 組（1 時間以内 63%、6 時間以内 80%、「Parallel rediscovery」という見出し） | **523 組**（76% / 90%）、検証と親子関係を除くと **499 組**（79% / 90%）。見出しは **「Equal-score convergence」** | 大。§6.3 参照 |
| 同スコア対の解釈 | 並行する「再発見」 | **「these pairs show convergence on the same results rather than independent rediscovery」** | 大。著者が自ら読み替えた |
| 高速搾取の内訳 | 最初の 8 件で約 70%、最初の 18 件で約 98% | **最初の 3 件で 93%**、最初の 18 件で約 98% | 中 |
| 陰性結果の件数 | 53 件 | **60 件が negative/null タグ、うち negative-result は 29 件** | 中 |
| 新最良を更新した scored result | 233 件 | **232 件** | 小 |
| クロスハードウェア再現の差 | 最大 1.3×10⁻³ bpb、ブリーフの許容範囲内 | 多くは **5×10⁻⁴** 以内。最大 **1.2×10⁻³** は**許容値（約 10⁻³）をわずかに上回る**が、検証者はハードウェア一定オフセットとして confirmed と投稿 | 中。§5.4 参照 |
| 軌跡 Table 4 の 5 月 1 日・attention 行 | 1.9043（5 月 1 日 10:28） | **1.9054（5 月 1 日 06:24、slurm_worker_5）** | 小。行の値・時刻・アカウントが変わっている |
| 主結果の最終改善幅 | 9×10⁻⁶ bpb（親に対して） | **3×10⁻⁷（直前の最良に対して）、9×10⁻⁶（親に対して）** | 小（v4 が詳しい） |

**記述の追加・拡充**

| 箇所 | v4 で新たに書かれたこと |
|---|---|
| §1 Introduction | 5 月 2 日、集中探索 5 日目に検索集中度と未探索分岐のビューを追加し、**8 体のワーカーに「まずそれを読むよう」指示した**（"prompted eight of the workers to read them first"）。v1 の §1 にこの記述はない。 |
| §2 Related Work | 「Autonomous research agents」項が追加（AutoResearch ほか）。 |
| §4.2 | **8 台の H100 ワーカーは 1 台の 8-GPU ノード上の別コンテナ**。ファイルは共有しないが**互いのプロセスを一覧できた**。「several descriptions, **including the winning module's**, report choosing an experiment after seeing which scripts neighboring workers were running」。 |
| §4.2 | モデル別の内訳（H100 の 1,285 件中、Claude Opus 4.7 が 866、GPT-5.5 が 276、GPT-5.4 が 143）。v1 では「記載がない」と A が報告していた。 |
| §4.2 | **索引が 45 コミットを落としている**（初期投稿 21 件の削除と、80 秒以内に同じアカウントが再投稿した失敗 24 件）。「The server creates the commit before writing the index and does not undo it when the write fails.」 |
| §4.5 | 検証は **141 組の verifier–target 対**をなし、残り 24 件は同一対の再投稿。スコアに効くのは各対の最新判定のみ。 |
| §4.5 | 最良の祖先 145 コミットの著者 15 アカウントの内訳＝**ワーカー 13 全員 ＋ setup アカウント ＋ 著者自身のアカウント 1 つ**（§4.7 参照）。 |
| §4.7 | 走行中の変更は**サーバ 3 回 ＋ H100 プロンプト 1 回**。クラスタ閾値を既定 0.90 から **0.80** に変更（0.90 では最大クラスタは活動の約 8% にしかならず、「この診断も 30% トリガもこの設定に依存する」と著者が自認）。 |
| §4.7 | 5 月 3 日、**DAG 端点がそれまで最大 200 件しか返さず、親がその範囲外の辺を全て落としていた**バグを修正。H100 を 14:56–15:24 UTC に停止して再配置。 |
| §4.7 | 5 月 5 日、仮説投稿にダミー値 −1 が付いて指標リーダーの最上位に出たため、仮説のみのタグには指標値を拒否する変更を実施。さらに**「API では contribution を編集できないため、DB を直接書き換えてその値を消した。コミットには −1 が残り、いつ消したかの記録もない」**。 |
| §4.7 | **著者の 1 人が、ランチャー外で手動のコーディングエージェント・セッションを 3 回実行した**（各々、投稿直前に登録されたアカウント）。4 月 28 日の 1 回は 2 つの温度のグリッドを実行し、バイグラム温度を 0.926→0.924 に変える結果（1.9158 bpb）を投稿。**これは最良 contribution の祖先に含まれる**。5 月 1 日に検証 1 件、5 月 7 日に洞察 1 件。 |
| §4.7 | **「No separate intervention log survives」（介入ログは残っていない）**。上記の記述はサーバのコミット履歴・投稿記録・H100 ランチャーのログからの復元である。 |
| §4.8 | **「reproduction attempts that were never posted left no trace」（投稿されなかった再現試行は痕跡を残さない）**。 |
| §4.8 | 評価器ログなし。A100 ワーカーのモデルとプロンプトの記録なし。依存関係・ドナーモデル・FineWeb-Edu サンプル・トークナイザの**版固定なし**。 |

**記述の後退（v1 にあって v4 §5 にないもの）**

- v1 §5 の **「What the run does not settle is causal: we did not run the same models and compute without Agora or with a plain leaderboard」** は、v4 §5 には存在しない。v4 §5 の対応箇所は **「establishing its effect on discovery efficiency requires matched comparisons across tasks」** に置き換わっている（より穏やかな表現）。
- v1 §5 の **「the community left its first basin only after we showed it a map」** は v4 §5 にない。
- v1 §5 の **「調整層が、個々のエージェントよりも制約だった」** は v4 §5 にない。

→ **v4 は本文（§4.7）で介入の開示を大幅に増やす一方、結論（§5）の留保を弱めている。** この方向性は、本リポジトリが Agora を引用する際に明示しておくべき性質である。

### 1.3 未確認の範囲

v4 の **§3（Agora の設計）と §4.1（タスクと評価器）は統合役が未読**である（v4 は PDF が 89 KB 縮小しており、設計節の変更可能性は低いと判断したが、確認はしていない）。したがって本レポートの §3 と §4.1 は **A と A′ が読んだ v1 に基づく**。§4.2 以降は v4 で確認済みである。

---

## 2. 書誌

| 項目 | 値 |
|---|---|
| タイトル | Agora: Git as Shared Memory for Collective AutoResearch |
| 著者数 | 8 |
| 先頭著者 | Yifan Zhang |
| 所属 | NVIDIA（`{yifazhang,yidong}@nvidia.com`） |
| v1 投稿日 | 2026-09-16 |
| 最新（v4） | 2026-09-30 |
| 分類 | cs.LG / cs.AI / cs.CL |
| ライセンス | arXiv.org perpetual non-exclusive license（PDF 1 面フッターに「© 2026 NVIDIA. All rights reserved.」併記） |
| DOI | 10.48550/arXiv.2609.18094 |

台帳 `SRC-20261020-f295` の書誌（title・authors）は A が fixture（`tests/fixtures/arxiv_metadata_snapshot.json`）と照合して一致を確認している。

---

## 3. 設計（Agora とは何か） — v1 ベース（§1.3 参照）

### 3.1 貢献 DAG と来歴（§3.1–3.2）

- プロジェクトの状態は有向非巡回グラフ `G=(V,E)`。contribution は `v=(h,a,T,d,x,m,P,τ)`（ハッシュ、著者、タグ、説明、メタデータ、metric、親の集合、サーバタイムスタンプ）。親子関係は **"builds on"** の意味。
- **"Git is the only state the system depends on"**。SQLite 索引と分析ビューは Git 履歴から再構築できる。
- **"The system does not try to decide what is true"**（§1）。スコアは「再現・後続利用された結果は行動しやすい」という狭い主張であり、真理の指標ではない。

**Table 1 の設計目標**：耐久的な記憶、フロンティアの可視化、証拠の質（**投票の否定**）、探索の多様性、監査可能性。

### 3.2 貢献語彙と証拠スコア（§3.2、Table 2、式 (2)）

| タグ | fitness への寄与 |
|---|---|
| `setup` / `result` / `insight` / `hypothesis` / `report` | 各 +5 |
| `verification` | +20 / +10 / −20。対象は**正確に 1 つ**、自己の作品は対象外 |
| `endorsed` / `wip` | 0（fitness に算入しない） |

証拠スコア：`S(u) = Σ_{v:(u,v)∈E} 𝟙[a(u)≠a(v)] w(v)`（式 (2)）。**他のアカウントが後続で築いた分量を重み付きで数える**ものであり、単なる賛同（投票）は数えない。"The score is not a truth signal"／"Whether a result is accepted still depends on the project's evaluator, controls, and artifact policy."

- 参加者はファイルシステム・モデル・会話を**共有しない**。公開経路は軽量（メタデータのみ）と重量（git bundle）。

### 3.3 多様性に配慮した注意割当（§3.3、式 (3)）

- `analyze` は単一のリーダーボードではなく複数のビューを返す：指標リーダー、被構築ノード、リーフ、低探索の有望候補、未検証結果、競合する検証、未解決仮説、最近の活動、タグ、貢献者。
- クラスタリングは単連結（コサイン閾値**既定 0.90**、埋め込み被覆 50% 以上、直近 5,000 件）。※本走行では **0.80** に変更（§6.2）。
- 候補の評価：`U(v) = 100Q(v) + C√(log(N+1)/(n(v)+1)) + 100D/√(1+ρ(v))`（式 (3)）。3 スロット **exploit / explore known / explore novel** に提示される。
- 著者自認の制限（§2）：「neither a stationary bandit nor a game tree, and its suggestions are heuristics ... not a guarantee of optimal planning」。
- **未定義の残存**：式 (3) の `D` は本文中で定義されていない。探索定数 `C` は「指標分布が密に集まるほど増える」とのみ。`Q(v)` の算出法も本文では確認できなかった（A）。

### 3.4 実装（§3.4）

- Go サービス ＋ CLI ＋ Next.js の Web インターフェース。プロジェクトごとの bare リポジトリ。
- SQLite 8 テーブル：agents、projects、contributions、parents、tags、cross-project references、embeddings、rate limits。
- HTTP ルート 26、CLI コマンド群 15。
- 自己申告の制限：「project metadata and authentication state still need ordinary database backups」。
- **実装コードの公開 URL は本文のどこにもない**（A′ が未発見、A も同旨）。

---

## 4. 実験の設定

### 4.1 タスクと評価器（§4.1） — v1 ベース

- **ドナー**：141 個の open-weight 事前学習モデル（534 GB、32 アーキテクチャ族）。
- **ターゲット**：14 層・隠れ次元 672・7 ヘッド・untied・**119,572,320 パラメータ**のハイブリッド（attention と簡略化 Mamba 型 SSM の交互配置）。どのドナーとも次元が一致しない。
- **制約**：ターゲットに対して学習データを使わず、勾配更新もしない。
- **評価器**：seed 42、GPT-2 トークナイザ、FineWeb-Edu の 200 テキストを 512 トークンの非重複チャンクに分割、**bpb**（summed next-token loss / UTF-8 byte count）。`transfer()` の内部から FineWeb-Edu を読むと例外になる。
- **基準値**：ランダム初期化 **3.3923 bpb**。学習済み GPT-2 124M 約 1.0 bpb は **"sets the scale; it is not an achievable no-training baseline"**（到達可能な基準ではない）。ブリーフの目標は 2.5 未満（"aspirational"）。
- **再現性**：同一コード・同一ハードは bit-identical。GPU 型が違うと第 3 位小数が変わる。
- 公開ベンチマーク（MLAgentBench、MLE-bench、ScienceAgentBench）は §2 で**引用のみ**、実行はしていない（A′）。

> **読解上の注意**：「学習データを使わない」はターゲットについての制約である。ドナーは大規模に事前学習されており、その振る舞いが転移している（A の指摘）。

### 4.2 エージェントと運用（§4.2–4.3） — v4 で確認

- **エージェント**：Claude Code（Claude Opus 4.7）と Codex（GPT-5.5 または GPT-5.4）。
- **ランチャー**：コンテナ ＋ GPU ＋ Agora アカウント資格 1 つ ＋ ヘッドレス CLI ＋ 短いプロンプト。セッションが終わると空き資格で次を開始。
- **プロンプト**：プロジェクト記録に残る 1 行は「read program.md for full instructions, and run agora analyze to see what others have tried」。**ログが残るのは H100 ランチャーのみ**で、それには「指示を求めずに判断せよ」「投稿してからセッションを終えよ」が加わる（5 月 2 日に差し替え）。
- **`program.md`**：2 ページのブリーフで最初の node として commit されている。タスク・規則・評価器契約・毎回クリーンチェックアウトの要件・ループを規定。**"Apart from an SVD weight-projection baseline that ships with the brief as an example, nothing in the prompt or brief names a method, assigns a role, or ranks the participants."**
- **ワーカー**：13 アカウントが 1,703 件中 **1,699 件**を書いた。worker1–worker5 が A100（4 月 27 日〜）、slurm_worker_1–8 が H100（4 月 28 日〜カットオフ）。残り 4 件は setup commit 1 件と、著者が手動実行した 3 件（§6.2）。**全 17 アカウント**。
- **モデル別内訳**（H100 の 1,285 件中）：Claude Opus 4.7 が 866、GPT-5.5 が 276、GPT-5.4 が 143。「The server authenticates accounts, not the model or session behind them, so the analyses below are per account.」
- **各ワーカーが持つもの**：Agora CLI、Git、PyTorch と Transformers 入りの Python、ドナー zoo への読み取りアクセス、評価器、**80 GB GPU 1 枚**。
- **⚠️ 同一ノード**：8 台の H100 ワーカーは **1 台の 8-GPU ノード上の別コンテナ**。ファイルは共有しないが**互いのプロセスを一覧できた**。"several descriptions, **including the winning module's**, report choosing an experiment after seeing which scripts neighboring workers were running."
- **⚠️ 索引の欠落**：全カウントはサーバの contribution index に基づくが、この索引は **Git 履歴に残る 45 コミットを落としている**（削除された初期投稿 21 件と、80 秒以内に同じアカウントが再投稿した失敗 24 件）。
- **期間**：setup commit（4 月 26 日）からカットオフ（5 月 8 日）まで **11 日 19 時間**。
- **規模**：1 日あたり約 170 件（13 体が揃って以降）。4 月 30 日は H100 が 27 時間停止して 49 件に落ちた。
- **内訳**：scored 1,124、insight 284、hypothesis 203、verification 165、report 1（タグ重複あり）。scored のうち **232 件**がランダム初期化とそれまでの全スコアを同時に更新した。
- **投稿形式**：親とそのスコア、1 つの変更点、予測レンジ、測定結果、後続への指名。4 月 28 日以降 400 件超が測定前に予測レンジを宣言しているが、著者は「そのように求めてはいない」とする（v1、A）。
- **⚠️ タグの出現時期**："Explicit negative-result and explore-novel tags appear only after May 2, when we deployed the landscape and diversity views and changed the H100 workers' prompt"（§4.3）。→ 陰性結果の件数は、介入の産物でもある。

---

## 5. 結果

### 5.1 手法の鎖（§4.4、Algorithm 1、Table 3） — v4 で確認

- 最良 contribution は **73 個の Python モジュールの鎖**（各々が親を import して 1 つの変更を加える）。共有コードとして import される 10 個の旧版を合わせ、**import 閉包は 83 モジュール**。
- **Stage A（遷移事前分布）**：GPT-2 語彙を共有する 6 ドナー（GPT-2 small/large、Cerebras-GPT 111M–1.3B）に 28 文脈（文脈なし、EOT、単一トークン 22 種、2 トークン節開始 4 種＝'. The' / ', and' / '. This' / ', or'）で次トークン log-softmax を問い合わせ、固定ドナー重み（GPT-2 small に 0.725）と行ごとの文脈重みでブレンド → **50257×50257 のバイグラム表 M**。列平均 `u` を unigram 的アンカーとして分離し、中心化した `C` を **ランク d−1 = 671 の randomized SVD**（固定スケッチ、power iteration 1 回、固定 seed）で因数分解して入力埋め込みと出力ヘッドへ。サブレイヤは全てゼロ。
- **Stage B（構造的文脈経路）**：隠れ状態の **96 次元バンド** `B_k = [1+96k, 97+96k)`（k=0..5）、`B_6 = [576,672)` に対する疎な決定論的編集。
  - attention：一様な因果平均プール（同一バンドを読み書き）。
  - layer-0 SwiGLU：`0.009 × SVDProject(GPT-2 small MLP_0)`。
  - SSM：データ依存ゲートを定数にして、ゲート付き depthwise 因果畳み込みに帰着。
- **「Each constant was introduced as a single change on the then-current best and kept because the evaluator improved.」**
- Algorithm 1 と Table 3 はエージェントの説明文ではなく**コードから書き起こした**（§4.8）。

### 5.2 軌跡（§4.5、Table 4） — v4 で確認（全 12 行の完全版）

| 時刻 (UTC) | アカウント | bpb | 導入された変更 |
|---|---|---|---|
| — | — | **3.3923** | ランダム初期化 |
| Apr 27 00:24 | worker1 | 4.6784 | GPT-2 と Mamba の重みのスライス・コピー（ランダムより悪い） |
| Apr 27 00:57 | worker1 | 2.5151 | GPT-2 予測からの unigram 事前分布。残差サブレイヤをゼロ化 |
| Apr 27 01:50 | worker1 | 2.1284 | バイグラム遷移行列、randomized SVD で埋め込みとヘッドへ |
| Apr 27 06:55 | worker2 | 1.9319 | 24 プレフィックス、幾何平均集約 |
| Apr 27 13:30 | worker2 | **1.9304** | 平均前にプレフィックスごとの log-softmax（**18 番目の scored**） |
| Apr 28 04:31 | slurm_worker_4 | 1.9228 | 2 番目のドナー（Cerebras-GPT 111M）を分散・自然さ重み行に |
| Apr 29 11:04 | slurm_worker_2 | 1.9136 | 28 番目の文脈（2 トークン ', or'）を 6 ドナーのレシピに |
| May 1 05:10 | worker2 | 1.9062 | randomized SVD に power iteration を 1 回 |
| May 1 06:24 | slurm_worker_5 | 1.9054 | layer-0 attention を一様因果平均プールに |
| May 3 00:13 | slurm_worker_3 | **1.9028** | SSM 編集が主鎖に合流：layer-1 バンド平均プール。ランドスケープを読んで選択 |
| May 5 17:34 | slurm_worker_6 | 1.8995 | GPT-2 small からの layer-0 フィードフォワード射影 |
| May 8 13:24 | slurm_worker_1 | **1.8990** | layer 1, 3, 7 へのクロスバンド SSM 出力射影書き込み |

- Table 4 の注記：**「4 月 27 日 13:30 以降の行は、カットオフ時点の最良 contribution の祖先に乗っている。それより前の 4 行は記述上はその前身だが、親としては記録されていない」**。「Each row was selected on the same development evaluator, so adjacent rows are stages of a search, not a controlled ablation.」
- **物語**：最初のインデックス済み試行はパラメータ・スライスのコピーで 4.68（ランダムより悪い）→ 著者はそれを説明付きの陰性結果として公開。30 分後に同一アカウントが unigram 事前分布（2.52）に置換。6 時間以内に 3 アカウントが 3/6/12/24 プレフィックスのバイグラム統計へ拡張（1.93）。**これら 18 件の scored contribution が総低下量の約 98%**。残り 1,106 件が 0.03 を追加した。
- **Figure 3 キャプション（v4）**：「初日の統計的事前分布が低下のほぼ全体をもたらす…**最初の sub-1.90 は 5 月 2 日のランドスケープ・ビュー展開とプロンプト変更に続いて現れた**」。図は 5 月 9 日まで描かれているが、本報告の数値は 5 月 8 日までの最初の 1,703 件のみ。

### 5.3 主結果（§4.5） — v4 で確認

- **1.899044 bpb**（ランダム初期化 3.3923、学習済み GPT-2 124M 約 1.0）→ **ギャップの 62% を閉じた**。
- 「Every component was selected on the same 200-text development evaluator.」
- **「the last recorded improvement, 3×10⁻⁷ over the previous best (9×10⁻⁶ over its own parent), is far below cross-hardware variation.」**
- 「In this task, a low-rank approximation of donor next-token behavior transferred successfully across architectures, whereas the first indexed parameter-copying attempt performed worse than random initialization.」
- 62% の算出過程は本文からは再導出できない（A′）。

### 5.4 系譜と再現（§4.5） — v4 で確認

- 最良 contribution の祖先は **145 commits**、**17 アカウント中 15** が執筆（＝ワーカー 13 全員 ＋ setup アカウント ＋ **著者自身のアカウント 1 つ**）。
- 144 本の親辺のうち **115 本がアカウント境界を越える**。單一のワーカーは組み立てていない。
- **165 件の検証が 95 件の対象をカバー**。各々が対象を名指し、検証者は作者と異なり、**失敗報告は 0 件**。
  - **v4 で追加**：これらは **141 組の verifier–target 対**をなし、残り 24 件は同一対の再投稿。スコアに効くのは各対の最新判定のみ。
  - **v4 で追加**：同一ハードは bit-identical。クロスハード（A100 vs H100）の多くは **5×10⁻⁴** 以内。最大 **1.2×10⁻³**（勝者の祖先）は**ブリーフの許容値（約 10⁻³）をわずかに上回る**が、検証者は一定のハードウェア・オフセットとして confirmed と投稿した。
- 勝者の 144 祖先のうち **40 件**が作者以外のアカウントにより再現された。
- **⚠️ v4 §4.8**：**「reproduction attempts that were never posted left no trace」**。投稿されなかった再現試行は痕跡を残さない。→ 165 件・失敗 0 件という記録の**感度は不明**であり、失敗率ゼロは信頼性の証拠にならない。

### 5.5 陰性結果（§4.5） — v4 で確認

- プレフィックス集合を 48 に倍増すると悪化（4 つの統制変種で記録）。
- 特異値スペクトルの平坦化、ハイブリッド・ドナーからのネイティブ Mamba ブロック移植、GPT-2 埋め込み行列の直接コピー、別トークナイザ（Pythia）ドナーからの事前分布構築——いずれも悪化し、スコア付きで公開された。
- **v4**：ウィンドウ内で **60 件が negative または null タグ**、うち **negative-result は 29 件**（v1 は 53 件）。
- ⚠️ これらのタグ自体が **5 月 2 日の介入後にのみ現れる**（§4.3）。

---

## 6. 協調と介入

### 6.1 グラフの形（§4.6） — v4 で確認

1,703 ノード、1,894 辺、149 の多親ノード、**98.9% が単一の連結成分**。Figure 4 は「連続するリーダーの細い鎖と、短く捨てられた枝」。4 つのパターン：

1. **Fast exploitation（v4 で数値が変更）**：**最初の 3 件の改善で総低下量の 93%**、最初の 18 件で約 98%（v1 は「最初の 8 件で約 70%」）。
2. **Narrow spine**：1 つの系譜に後続作業が集中。側枝は短く、すぐ捨てられる。
3. **Equal-score convergence（v1 の「Parallel rediscovery」から改称・訂正）**：523 対中 **76% が 1 時間以内**、**90% が 6 時間以内**。検証と親子関係を除いた 499 対でも同じ傾向（79% / 90%）。**「Identical scores can still come from re-runs of a shared parent or from different methods, so these pairs show convergence on the same results rather than independent rediscovery.」**
4. **Community-level diagnosis**：1.90 bpb 近傍に複数のファミリが収束。エージェントは「評価器が大域的に線形」「ターゲットのサブレイヤが十分に使われていない」と説明し、バイグラム・レシピを強い局所最適と表現した。**「These explanations were proposed in the contributions but were not independently tested.」**

- **v4 で追加**：**232 件の新最良のうち 194 件**が 6 時間以内に少なくとも 1 つの他アカウントから後続作業を引いた（中央値 3 アカウント）。
- **v4 の総括**：「Shared visibility supported reuse, but did not by itself sustain broad exploration.」
- v1 には「A shared leaderboard did not stop duplicate work, and the graph is heavily exploitation-biased」（§4.6）という一文があった（A が引用）。v4 では同文を確認していない。

### 6.2 人間の介入（§4.7） — v4 で大幅に拡充

v1 では「5 月 2 日の 1 回のみ」と読めていた（A は「著者はタスクの割り当て、レビュー、承認、個別セッションへの指示をしていない」と報告）。**v4 はこれを実質的に撤回している。**

**走行前**：タスク定義、ドナー zoo とターゲット構成の用意、評価器とブリーフの作成、プロジェクト作成、ワーカーの起動。

**走行中（サーバ 3 回 ＋ プロンプト 1 回）**：

1. **5 月 2 日（プロンプト変更）**：分析ビューが「活動の 3 分の 1 超が単一の意味クラスタに集中し、リーダーボードが停滞」と示したため、クラスタリング・多様性サマリ・多様性考慮 UCB を展開。**クラスタ閾値を既定 0.90 から 0.80 に変更**（0.90 では最大クラスタは活動の約 8% にしかならず、「この診断も、新プロンプトの 30% トリガもこの設定に依存する」と著者が自認）。19:13 UTC に H100 ランチャーを停止、21:20 UTC に新プロンプトで再開。新プロンプトは「まずランドスケープを読む」「最大クラスタが活動の 30% 超ならそのクラスタより explore-novel スロットかフロンティアを優先」「3 スロットから選ぶ」「失敗した着想には洞察を投稿」。
   - **効果**：H100 の記述のうち新ビューへの言及は、変更前 1% 未満 → 5 月 3 日 **86%**。**A100 ワーカーのプロンプトは記録されていない**。A100 の言及率は 5 月 3 日 26% → 5 月 5 日 66% → 5 月 8 日 29%（`analyze` と他ワーカーの投稿から知ったらしい）。
   - **著者の自認**：**「The immediate shift therefore reflects the prompt as much as the views, and the record cannot separate the two.」**（急激な変化はビューと同程度にプロンプトによるもので、記録からは分離できない）
2. **5 月 3 日（バグ修正）**：DAG 端点が**それまで最大 200 件しか返さず、親がその範囲外の辺を全て落としていた**問題を修正。Web UI に新ビューを追加（H100 を 14:56–15:24 UTC に停止）。
3. **5 月 5 日（ルール強制）**：仮説にダミー値 −1 が付いて指標リーダーの最上位に出たため、仮説のみのタグには指標値を拒否する変更を実施（Table 2 の規則の強制）。**さらに API では contribution を編集できないため DB を直接書き換えてその値を消去。コミットには −1 が残り、いつ消したかの記録もない。**

**著者自身による手動セッション（v4 で新たに開示）**：
> "One of us also ran three coding-agent sessions by hand, outside the launcher, each under an account registered shortly before its only post. Their text follows the same template as the workers' posts, which indicates that the agents, not a person, wrote them. On April 28 one of them ran a grid over the two temperatures and published a result that changed the bigram temperature from 0.926 to 0.924 (1.9158 bpb); **it lies on the ancestry of the best contribution.** On May 1 a verification confirmed a worker's result on H100 hardware, and on May 7 an insight summarized the landscape views."

→ **最良結果の祖先に、著者が手動で動かしたセッションが 1 つ含まれる**。

- なお「Workers continued to choose their own experiments and publish without human review.」（ワーカーは自分の実験を選び、人間のレビューなしで投稿し続けた）。
- **「No separate intervention log survives」（介入ログは残っていない）**。上記は全てサーバのコミット履歴・投稿記録・H100 ランチャーのログからの復元である。

### 6.3 「並行再発見」の読み替えについて（E2 に直結）

v1 の §4.6(3)「Parallel rediscovery（696 組中 63% が 1 時間以内）」は、両セッションが「共有フロンティアによる並行収束の観測」として報告し、本リポジトリでも「共有入力に起因する相関の例」と読めるとメモした。**v4 はこれを 523 組に訂正し、見出しを "Equal-score convergence" に改め、「独立な再発見ではなく同じ結果への収束」と明示した。**

含意：この観測値を「相関の証拠」として引用することは、**著者の現在の解釈に反する**。同一スコアは「同じ親の再実行」や「別手法」からも生じうる。相関の証拠として使える部分は残っていない。

### 6.4 相関を生む機構として新たに名指しされたもの（E2 に直結）

v4 §4.2 が初めて明記した：

> "The eight H100 workers ran as separate containers on one eight-GPU node. They shared no files, but they could list one another's processes, and several descriptions, **including the winning module's**, report choosing an experiment after seeing which scripts neighboring workers were running."

**これは v1 にはなかった記述であり、観測された相関生成機構である。** 8 体のうち大半（H100 の 8 アカウント、全投稿 1,285 件）が同一ノード上で互いのプロセスを可視できる状態にあり、**勝者モジュール自身がその影響を報告している**。独立と見なせる条件（独立なサンプル）が成立していないことは、著者が §4.2 で自ら示したことになる。

→ 本リポジトリの用語では、これは **Agora の走行が「独立な N 回」ではなく、強い共通モードを持つ事実上 1 回の走行である**ことを裏付ける。Appendix C の「The primary analysis unit is the entire community run」と整合する。

---

## 7. 著者自身の検証（§4.8） — v4 で確認

3 段階：

1. **trace**：完全な投稿ストリームとグラフをサーバから書き出し、報告された件数・統計・図を再計算。
2. **result**：最良スコアを記録された損失・トークン数・バイト数と照合。加えて、勝者手法とその祖先の再現記録を確認（クロスハードの一致は約 10⁻³ bpb 以内と報告されている）。
3. **method**：勝者コミットの import を最終編集から基底モジュールまで辿り、各モジュールを読む。「No step accessed the evaluation data or used gradient descent to update a parameter.」

- 前提：「We treated the agents' descriptions as claims to check against the artifacts they point to, not as evidence in themselves.」
- **「We did not rerun the winning method; the primary result is the archived evaluator output, corroborated by the agents' cross-hardware reproductions.」**
- **v4 で追加された留保**：
  - 「A verification record names its target and verdict, but the evaluator and hardware appear only in its free text, and **reproduction attempts that were never posted left no trace**.」
  - 「The run also left no evaluator logs, no record of the A100 workers' models and prompts or of sampling settings beyond the command-line flags, and **no pinned versions of the dependencies, donor models, FineWeb-Edu sample, or tokenizer**.」

---

## 8. 限界

### 8.1 著者が自認しているもの

| # | 内容 | 箇所 | 版 |
|---|---|---|---|
| 1 | 因果は未決着。Agora 無し／平板リーダーボードとの同一条件比較は**未実施**。Appendix C は提案のみ | §5 | **v1 の明示的な一文は v4 §5 にはなく、「matched comparisons across tasks が必要」という穏やかな表現に置換** |
| 2 | 人間の介入という交絡 | §4.7 | v4 で大幅に拡充（§6.2） |
| 3 | 全構成要素が同じ 200 テキスト開発評価器で選択された。「信じるべきは 3.39→約 1.90 の改善幅で、最終桁ではない」 | §4.5 | v1 / v4 とも同旨 |
| 4 | 勝者手法を再実行していない | §4.8 | v1 / v4 とも同旨 |
| 5 | 多様性アテンションはヒューリスティクスであり、最適計画の保証ではない | §2 | v1 ベース |
| 6 | 証拠スコアは真実性を保証しない | §3.2 | v1 ベース |
| 7 | **（v4 で追加）** 投稿されなかった再現試行は痕跡を残さない。評価器ログ・A100 のモデル/プロンプト記録・版固定なし | §4.8 | v4 |
| 8 | **（v4 で追加）** 索引が 45 コミットを落としている | §4.2 | v4 |
| 9 | **（v4 で追加）** クラスタ閾値の設定に診断が依存する | §4.7 | v4 |

> 集計規則の注意：A は「限界の数」を 3、A′ は 6 と数えた。これは**どこまでを「限界」と数えるかの規則が異なるため**であり、どちらも誤りではない（A は §4.6 の 2 点と §5 の因果 1 点、A′ は §2・§3.2・§4.5・§4.7・§4.8・§5 の 6 点）。**この項目は「1 つの正解がない」ため、正解データを作らない**（[`2026-10-20_agora_ground_truth_integrator.json`](2026-10-20_agora_ground_truth_integrator.json) で F1 = `null`）。

### 8.2 読者としての注意（統合役の判断）

1. **1 コミュニティ・1 走行**であり、手法の選択は走行中に起き、Table 4 の各行は事後的に選ばれた探索段階である（著者の注記）。
2. **held-out がない**。全選択が同じ 200 テキスト評価器上で行われたため、1.899 は楽観的に出ている可能性がある。過学習の度合いは測られていない。
3. **「独立」の範囲は狭い**。同じブリーフ、同じ評価器、同じリポジトリ、同系統の基盤モデル、そして（v4 で判明）**同一ノード上でのプロセス可視性**。
4. **介入は v1 の記述より多い**。8 ワーカーへの個別指示、著者の手動セッション（勝者の祖先に 1 件）、DB 直接編集、閾値の恣意的設定、そして介入ログが存在しない。
5. **「検証 165 件・失敗 0 件」は信頼性の証拠にならない**。投稿されなかった再現に痕跡がなく、最大のクロスハード乖離（1.2×10⁻³）は許容値超過にもかかわらず confirmed と投稿されている。
6. **v4 は結論の留保を弱めている**（§1.2）。Agora を引用する際は、§4.7 の開示と §5 の表現を**別々に**扱うべきである。
7. 著者は自分のシステムを評価している（所属 NVIDIA）。利益相反・資金の記載は本文に見当たらない（A）。
8. 「無訓練」はターゲットに限った話である。

---

## 9. ResearchOS への示唆

### 9.1 E2（誤り相関 ρ）について — 結論を更新する

[`2026-10-20_parallel_experiment_results.md`](2026-10-20_parallel_experiment_results.md) §4 は「Agora は本研究に最も近い実例」と書いた。**v4 の確認により、この評価は次のように更新される。**

- **測定値としては使えない（これは v1 の時点でも同じ）**：Agora は誤り率を測っていない。検証 165 件・失敗 0 件は、失敗が「存在しない」のではなく「投稿されなかった場合に痕跡を残さない」設計である（§7）。したがって ρ は推定不能。
- **v1 で「相関の観測例」として引用した並行再発見は、v4 で撤回された**（§6.3）。引用してはならない。
- **v4 は相関を生む機構を初めて名指しした**（§6.4）。同一ノードでのプロセス可視性、同一ブリーフ、同一評価器、同一フロンティア。これは「複数エージェントを並走させても独立サンプルにならない」ことの**実例**であり、本リポジトリが `gitswarm/readout_sim.py` で同質ワーカーの多数決をモデル化している前提を裏付ける。
- **設計への入力**：将来 ρ を測るなら、(a) ワーカーを**物理的に分離**すること（プロセス可視性を断つ）、(b) 失敗を含む全試行を**投稿させ、記録に残す**こと（痕跡のない試行をゼロにする）、(c) 介入を**その場でログに書く**こと（Agora はこれを欠いたため、v4 での開示が「復元」に留まった）——の 3 点が必須である。(c) は本リポジトリが既に `state/` の追記専用台帳で満たしている。

### 9.2 その他の示唆

1. **台帳設計**：`verification` ノード（他者による再現、自己作業の除外）は、本リポジトリの `verifications` 台帳と直接対応する。公開可能な証拠グラフ（evidence ＋ verification）を分離する設計の独立した前例である（A′）。
2. **報告規律の好例**：§4.8 の "We did not rerun the winning method"、§4.7 の "No separate intervention log survives"、v4 §4.2 の索引欠落の開示——いずれも「できないことを隠さない」写法であり、本リポジトリが重視する規律と同じ方向にある。
3. **Appendix C の 4 アーム（Isolated / Flat log / Central planner / Agora）** は、E1/E2 の設計の参照点になるが、**実行されていない**。
4. **不変の識別子（Appendix A）**：プロンプト、シード、ハード、評価器の版などの列挙は、再現性メタデータの最低限の項目として参照できる。ただし v4 §4.8 は Agora 自身がこれを満たしていない（版固定なし）と認めている。
5. **単位の扱い**：主結果を「コミュニティ走行」という 1 単位で報告し、commit 単位を独立サンプルとして扱わない。本実験で n=1 を明記する方針と同じ規約である。

---

## 10. 確認できなかったこと（A・A′ の指摘を統合・整理）

**本文に記載がないもの**

- held-out 評価（過学習の度合い）
- 不確かさの推定（信頼区間、複数評価器での結果）
- 対照実験（Agora 無し／平板ログ／中央計画）
- 勝者手法の独立した再実行（著者は再実行していない）
- GPT-2 124M ≈ 1.0 の測定条件（同じ評価器で測ったか）
- 「確定」判定の許容差の数値（v1。v4 は「約 10⁻³」と明記）
- 計算資源の総量（トークン数、API 費用、GPU 時間の総計）
- コード・データの公開（本文に URL なし。Agora 本体の公開範囲も不明）
- 利益相反・資金の記載
- 数式の未定義部分（式 (3) の `D`、`C` の具体式、`Q(v)` の算出法）
- カットオフを 5 月 8 日とした選択理由（"our cutoff" とのみ）

**統合役が確認していないもの**

- **v4 の §3（設計）と §4.1（タスクと評価器）**。本レポートの §3 と §4.1 は v1 ベースである。
- v4 の Appendix A–C（v1 では A＝再現性要件、B＝レシピ定数、C＝提案する比較行列）
- 図 1–5 の画像そのもの（キャプションのみ。図中の数値は読み取っていない）
- 参考文献の原典

**A が指摘した既存メモとの不整合**

- `2026-10-20_git_swarm_fulltext_reading.md` が Agora の設計として挙げる「物理親と `informed_by=` の分離」「plurality readout」は、**Agora 本文では確認できなかった**（`informed_by` という語はなく、Table 1 は投票を否定している）。出典は GitSwarm 側の本文で確認する必要がある。

---

## 11. 既存メモ・台帳との突合

| 既存の記述（場所） | 統合後の判定 |
|---|---|
| `2026-10-20_git_swarm_fulltext_reading.md`（Agora を「Git-parent 多重親 ＋ diversity-aware frontier view」と記述） | **概ね一致**（多親 DAG、多様性考慮 UCB）。ただし「`informed_by=` の分離」「plurality readout」は Agora 本文で確認できず。 |
| `2026-10-20_stateless_vs_gitswarm.md` §5「多数決は検証不能時のフォールバック」（CLM-003 関連） | Agora は多数決を採らない。ただし **v4 §4.2 が示す同一ノードでのプロセス可視性は、同質ワーカーの収束という CLM-003 の前提に沿う実例**である。CLM-003 は `candidate` のまま。 |
| `2026-10-20_context_and_eval_bottlenecks.md` | Agora は評価コストについて直接的な証拠を提供しない（評価は数秒、遷移行列の構築が H100 で約 5 分）。 |
| `2026-10-20_sla_fulltext_reading.md` §6「SLA と GitSwarm のベンチマークは重ならない」 | Agora は weight transfer という別タスクであり、どちらとも重ならない。追認。 |
| 台帳 `SRC-20261020-f295` | 書誌は一致。**v1 を 2 セッションが読了、v4 を統合役が照合**。v2–v4 のうち v4 のみ確認（v2・v3 は未読）。 |
| `2026-10-20_parallel_experiment_results.md` §4 | **更新が必要**（§9.1 参照）。本レポートが更新版である。 |

---

## 12. 参考文献

[1] Yifan Zhang, Yunheng Zou, Shaokun Zhang, Jian Hu, Hao Zhang, Binfeng Xu, Jan Kautz, Yi Dong. "Agora: Git as Shared Memory for Collective AutoResearch." arXiv:2609.18094v4 [cs.LG], 2026（v1: 2026-09-16, v4: 2026-09-30）. https://arxiv.org/abs/2609.18094 / DOI: 10.48550/arXiv.2609.18094

### 本レポートが統合した元データ（リポジトリ内）

- セッション A：`contributions/2026-10-20_agora_fulltext_reading.md` および `contributions/2026-10-20_agora_fulltext_reading.json`（v1 ベース）
- セッション A′：`contributions/2026-10-20_agora_fulltext_reading_r2.md` および `contributions/2026-10-20_agora_fulltext_reading_r2.json`（v1 ベース）
- 正解データ：`contributions/2026-10-20_agora_ground_truth_integrator.json`

---

## 13. 本レポート作成時に実行した確認

Python 3.11.2、2026-10-20。全ゲートを実行し、すべて終了コード 0 を確認した（後述のコミット時点）。

- `python3 -m unittest discover -s tests`
- `python3 gitswarm/benchmarks/benchmark.py --check`
- `python3 gitswarm/readout_sim.py --check`
- `python3 scripts/validate_state.py`
- `python3 scripts/check_citations.py`
- `python3 scripts/check_memo_citations.py`
- 本文の取得：`https://arxiv.org/abs/2609.18094v4`（2 チャンク）および `https://arxiv.org/html/2609.18094v4`（全 12 チャンク中、chunkIndex 0, 4, 5, 6, 7 を照合）。

上記以外の実行はしていない。図の画像確認、v2・v3 の本文取得、v4 §3 および §4.1 と Appendix の取得、参考文献の原典確認は行っていない。
