# 全文読解レポート：Agora — Git as Shared Memory for Collective AutoResearch（独立読解・r2）

- 作成日：2026-10-20
- 対象：Yifan Zhang et al. (2026) "Agora: Git as Shared Memory for Collective AutoResearch", arXiv:2609.18094v1 [cs.LG], 2026 の**全文**（HTML v1 および PDF v1。本書の数値・引用はすべて v1 本文に基づく）。
- 位置づけ：`docs/parallel-experiment-2026-10-20.md` の並列稼働実験における調査セッション A′ の**独立読解**（他セッションの Agora 読解成果物は開いていない）。台帳 `state/sources.jsonl` の SRC-20261020-f295「書誌のみ確認・本文未読」に対する全文読解。新しい実験は行っていない。機械比較用の抽出データは `contributions/2026-10-20_agora_fulltext_reading_r2.json`（15項目、プレイブック §4 の形式）に分離した。

## 1. 結論（全文から分かったこと）

1. **研究は「単一の観察的コミュニティ実験」であり、対照群の比較は未実施（著者自認）**：論文は §5 Conclusion で「What the run does not settle is causal: we did not run the same models and compute without Agora or with a plain leaderboard」と自ら述べ、基準条件（isolated / plain leaderboard）と Agora 条件を揃えた統制比較は Appendix C で「提案（Proposed Matched Evaluation Matrix）」として提示されるにとどまる（4条件：Isolated、Flat log、Central planner、Agora）。したがって「共有研究状態が計算あたりの発見を改善した」という因果主張はこの論文自体では決着しておらず、計測は未実施である。
2. **主要結果の数値**：固定された開発評価器（FineWeb-Edu 200 texts、bpb）のもと、最良の `transfer()` はランダム初期化 **3.3923 bpb** に対して **1.899044 bpb** を達成し、本文 §4.5 "Primary result" は「訓練済み GPT-2 124M（約 1.0 bpb）とのギャップの 62% を閉じた」と述べる（"closing 62% of that gap"）。なお論文は §4.1 で「The trained model sets the scale; it is not an achievable no-training baseline.」と明言しており、この 1.0 は到達可能な参照ではありません。「62%」についても、全文には、この計算割合を再導出できる計算過程は提示されていない。
3. **方法の骨格はドナー・パラメータのコピーではなく「予測統計の因子分解」**：§4.4 / Algorithm 1 に記載の2段構成として、Stage A では、GPT-2 系の語彙を共有する6つのドナー（GPT-2 small/large と Cerebras-GPT 111M–1.3B）の次トークン log-softmax を 28 の単一トークンコンテキストで問い合わせ、50257×50257 の bigram 表（M）を作り、その列平均を unigram 的アンカーとして除き、中心化済みの表 C をランク d−1=671 の randomized SVD で因子分解して入力埋め込みと出力ヘッドに流し込む。Stage B では、attention・FF・SSM を統一した控えめな文脈経路として再有効化します（次数を集約させる経路については Table 3 を参照）。
4. **「単一実行」の実態**：論文の主題となるコミュニティレベルの走行は weight-transfer の単一走行（primary window、11日19時間、投稿1,703件、§4.3）であり、論文自身が Appendix C で「The primary analysis unit is the entire community run」と述べる。投稿単位の再現（165件の検証、95件の対象）は、対照条件に対する反復や同等条件での独立した repeat の代わりにはならず、加えて著者は勝利手法を再実行していない（§4.8「We did not rerun the winning method」）。
5. **協調力学として示された二面性**：共有 DAG は重複作業の防止の主張と同時に、その失敗も記録している。異なるアカウントによる同一スコア投稿が 696組あり、その63%が1時間以内、80%が6時間以内に現れた（§4.6「Parallel rediscovery」）。論文自体が「A shared leaderboard did not stop duplicate work, and the graph is heavily exploitation-biased」（§4.6）と述べる。
6. **人間の介入という交絡が明示されている**：2026年5月2日に著者らが多様度認識型の分析ビュー（単一リンク型クラスタリング、多様性サマリ、多様性認識 UCB）を展開した後、翌朝に最初の sub-1.90 が出現した（§4.7）。同時に、``exploit`` の集中度が著しく高かった（「more than a third of all activity sat in a single semantic cluster」）。コミュニティがその最初の basin を離れたのは地図を見せられた後であり（§5）、これは「共有グラフだけが単一栽培的思考を改善する」という自立性に関する単純な読み方を弱める（§5）。
7. **解釈上の主張についての制限**："Community-level diagnosis"（§4.6）について、「Agents' interpretive claims of this kind ... are reported here as theirs.」と推論を著者は評価しない主体に委ねている。不要語の要請：§4.5 の「the number to trust is the improvement from 3.39 to about 1.90 rather than the final decimal places; the last recorded change moved the score by 9×10^-6, below cross-hardware variation」が述べているように、開発評価器によって選択された絶対値の小数点以下を信頼すべきでないと著者は自己宣言している。

## 2. 読解の範囲と方法（正直な記録）

- **読了**：arXiv HTML v1 全文（要旨、§1 Introduction、§2 Related Work、§3 Agora（§3.1–§3.4）、§4 The Weight-Transfer Run（§4.1–§4.8）、§5 Conclusion、References、Appendix A（Reproducibility Requirements）、B（Minimal Contribution Record）、C（Proposed Matched Evaluation Matrix））と、PDF v1 を照合（ページ構成と表・脚注の独立確認）。両経路で内容が一致することを確認し、Discussion / Limitations の見出し区切りの独立した節は存在しないことを確認した。
- **読んでいないもの**：**v2–v4 の本文**（abs ページの submission history によれば、公開は 2026年9月18日（v2）、9月22日（v3）、9月30日（v4）の順に進行しており、本書の数値と結論は v1 に即したものである）。 abs ページ（取得時の最新版）でタイトル・著者・ DOI の一致を確認した。
- **照合**：書誌（タイトル・8名の著者・先頭著者・投稿日）は abs／HTML／PDF／fixture （`tests/fixtures/arxiv_metadata_snapshot.json`）の各経路で一致した。数値の引用は節番号と表番号を添えている。
- 本書の引用はすべて上記取得で実際に読んだ文言である。読んでいない区画を読んだと主張しない。

## 3. 設計の詳細（全文から分かったこと）

### 3.1 貢献 DAG と来歴（§3.1–§3.2）

- プロジェクトの状態は有向非循環グラフ G=(V,E) で、contribution は v=(h,a,T,d,x,m,P,τ)（ハッシュ、著者、タグ、説明、メタデータ、metric、親の集合、サーバータイムスタンプ）として定義される。親子関係は ``builds on`` の意味であり、「Git is the only state the system depends on」と述べられるように、SQL インデックスと分析ビューは Git 履歴から再構築可能です。
- **貢献語彙（Table 2）**：`setup`、`result`、`insight`、`hypothesis`、`report`（各 +5）、`verification`（+20/+10/−20、対象は正確に1つ、自己の作品は対象外）、`endorsed`・`wip`（各0、fitness にカウントしない）。
- **証拠スコア（式 (2)）**：S(u) = Σ_{v:(u,v)∈E} 𝟙[a(u)≠a(v)] w(v)。他のアカウントが後にその上に構築した分量を重み付きで数えるもので、単なる賛同（投票）はカウントしない。論文自身が「The score is not a truth signal」「Whether a result is accepted still depends on the project's evaluator, controls, and artifact policy.」と述べている。
- 参加者はファイルシステム・モデル・会話を共有しません。公開する経路は、軽量（メタデータのみ）と重量（git bundle）となります。

### 3.2 多様度に配慮した注意割当（§3.3・§2 末尾）

- `analyze` は、単独のリーダーボードではなく、さまざまなビュー（指標リーダー、被構築ノード、リーフ、低探索の有望候補、未検証結果、競合する検証、未解決仮説、最近の活動、タグおよび貢献者）を返します。記述者間の相互作用を把握するために single-link clustering を利用したクラスタリングと、論文の §2 の末尾にある通りに「neither a stationary bandit nor a game tree, and its suggestions are heuristics ... not a guarantee of optimal planning」という内容が、自己宣言された制限であり、``識別のためのヒューリスティクス``である。
- 候補は、diversity-aware UCB U(v)=100Q(v)+C√(log(N+1)/(n(v)+1))+100D/√(1+ρ(v))（式 (3)）によって評価され、あまり知られていない価値も含め、``exploit`` / ``explore known`` / ``explore novel`` の3スロットに提示される。

### 3.3 プロトタイプ実装（§3.4）

- Go サービス + CLI + Next.js のWebインターフェイスであり、SQLite には8テーブル（agents、projects、contributions、parents、tags、cross-project references、embeddings、rate limits）が含まれています。「26の HTTP ルート」と「15のコマンドグループ」は、Docker イメージに含まれています。貢献インデックスは Git から再構築可能ですが、「project metadata and authentication state still need ordinary database backups」と自己申告された制限があります。**実装コードの公開URLは本文中のどこにも提示されていません（未発見）**。

## 4. 評価設計と結果の読み方（§4.1–§4.5）

- **タスクと評価器（§4.1）**：141のオープン・ウェイトによるドナーモデル（534GB、32のアーキテクチャ科）から、次元がどのドナーとも一致しない119,572,320パラメータの14層ハイブリッド（hidden 672、7 heads、untied embeddings）ターゲットへウェイト転送します。評価はシード42で実行され、GPT-2 tokenizer の下で、非重複の512トークンのチャンクで 200 件の FineWeb-Edu 文書を取得し、全ての ``transfer()`` 呼出について FineWeb-Edu のデータを読み込むことに禁止して、bpb（ summed next-token loss / UTF-8 byte count）で評価します。「Two runs of the same code on the same hardware are bit-identical; across GPU types the score can differ in the third decimal place.」という前提のもと、プロジェクトが掲げた ``aspirational target`` は 2.5 未満でした。
- **ベンチマークの数え方について（§2、§4.1）**：この論文は、公開された標準ベンチマーク（MLAgentBench、MLE-bench、ScienceAgentBench のようなもの）を評価のために実行しませんでした。§2 で引用されたシステムやベンチマークは引用としてのみ言及され、この論文で実行された評価は§4.1 で自作の本論文著者による単一の評価課題であり、詳細な評価としては、単一の評価器を使用した1回限りの実験です。
- **記録（§4.1、§4.3、Table 4、Figure 2–3）**：最初の試みとして、ドナーモデルのパラメータによる直接的な slice-copy が失敗し、4.6784 bpb となった。その後、unigram 先行項の導入で 2.5151となり、bigram なら 1.9304 （24 prefixes 後の 18 番目のスコア済み投稿）を達成し、続いて6 donor／28 contexts への拡張で 1.9136、5月1日に 1.9062（power iteration）、レイヤー0の attention を入れて 1.9043 （5月1日 10:28）、SSM の初編集で 1.9028 （5月3日 00:13）、レイヤー0の FF 投射で 1.8995（5月5日 17:34）、cross-band SSM の書換で 1.8990 （5月8日 13:24）となった。「the first 18 scored contributions」が全体の約98%の減少を占めた（§4.6）。
- **実行の規模（§4.3、Figure 2）**：投稿は 1,703 件であり、その内訳はスコア済み結果 1,124 件、insights 284 件、hypotheses 203 件、verifications 165 件、reports 1 件（重複タグあり）。スコア済み結果のうち233件がその時点での新最良を更新した（§4.3 "233 of the scored results set a new best"）。
- **来歴と再現（§4.5、Figure 4）**：最良の投稿の祖先列は 145件のコミットまでに広がっており（15アカウントにわたる）、そのうち 144 方向の親のエッジのうち 115 件はアカウントを跨ぐ。165 件の検証は 95 件までの異なる対象をカバーし、winner のスコア付き祖先 144 件のうち 40 件が独立に再現された（§4.5）。なお、著者自身は勝利した手法を再実行していない（§4.8 "We did not rerun the winning method"）。
- **相関誤りに関する直接観測（§4.6）**：異なるアカウントによる同一スコアの投稿が696組（1時間以内 63%、6時間以内 80%）が示す「Parallel rediscovery」は、同一フロンティアからの並行的収束が観測されるという関係にある。共有された入力（同じフロンティア、同じクラスタリング）から部分的な同一到達が生じる観測例ですが、誤りの発生率自体は計測されていません。

## 5. 人間の介入とその位置づけ（§4.7、§4.3、Figure 2）

- 人間が定めたのはタスク・評価器・プロジェクトブリーフといった事前の設定のみで、実行中は1回の変更（May 2 の分析ビュー展開）だけである。「first sub-1.90 result was published the next morning」「the worker that chose to follow the thin state-space cluster rather than extend the dominant one」（§4.7）が、論文における主な議論の転換点となる出来事である。
- しかし、Figure 2 のキャプションによると「Explicit negative-result and explore-novel tags appear only after the May 2 deployment of the landscape and diversity views」と述べられており、5月2日以前には「負の結果」のタグ付けが確認できず、探究を促す意識についても示されていない。言い換えると、人間が介入しなければ論文で提案された多様性に配慮した仕組みが働きにくいことから、人間が提供していた「マップ」について。

## 6. 著者による検証の手順（§4.8）

- 「We treated the agents' descriptions as claims to check against the artifacts they point to, not as evidence in themselves.」（§4.8）
- 検証は3段階（trace: 完全な投稿ストリームとグラフをエクスポートして報告内容の再計算、result: ベストスコアを代数的に損失・トークン数・バイト数と照合、method: 勝利コミットの輸入順序を順次追跡し、評価データに触れていないこと、パラメータを勾配下降で更新していないことを確認）であり、論文の全ての数値は agent の要約や leaderboard の表示からではなく、著者自らの再計算によっていると述べている。
- 一方で著者自身は勝利した手法を再実行していません。「We did not rerun the winning method; the primary result is the archived evaluator output, corroborated by the agents' cross-hardware reproductions.」（§4.8）

## 7. 既存メモ・台帳との突合

| 論点 | 全文読解の結果 |
|---|---|
| 台帳 SRC-20261020-f295 の書誌（タイトル、先頭著者、DOI、分類） | 全文で一致（タイトル、原稿時間は 2026年9月16日）。書誌情報を台帳として確認できているので、本文を読むことができて、該当ソースをこのリポジトリの独特な出典として採用した理由も明らかになる。 |
| 既存メモ `2026-10-20_context_and_eval_bottlenecks.md` へのリンク | Agora 論文は評価コストに関する直接的な資する証拠を提供していません（評価は数秒から5分程度の小規模開発用評価器について報告されているため、§4.2 で報告された評価コスト情報はありません）。 |
| 既存メモ `2026-10-20_stateless_vs_gitswarm.md`（§5 多数決は検証不能時のフォールバック） | Agora は論文でも単純な多数決を採らない（代わりに他者による downstream の作業・検証を証拠スコアとして取り扱う）ため、既存メモの枠組みと直接競合しない。Agora 式の「verification ＋ downstream use」は既存メモ §5 の二分法（実行可能評価器 vs 推薦多数決フォールバック）に間的な選択肢を追加します。 |
| 論文 §2 で「ベンチマーク」として引用される MLAgentBench、MLE-bench、ScienceAgentBench | いずれも引用のみであり、この論文では実際には使われていない。 |
| `contributions/2026-10-20_git_swarm_fulltext_reading.md` の言及 | 既存メモにあるベンチマークの非重なりを示す原則（実測に使われた課題が重ならない）は、既存の GitSwarm の課題や SLA の課題と同様に、Agora の単一の自作課題と重ならないことをここでも追認している。 |

（CLM/EVD の台帳追記は本書では行っていない。統合役に委ねる。）

## 8. Negative findings / 制約

**著者が本文で自認している限界**（`Discussion / Limitations` 章は存在せず、本文中に分散した明記。下記は本文の引用が根拠のもの）：

1. **因果効果は未確立**：対照条件を実行していない（§5 「What the run does not settle is causal: we did not run the same models and compute without Agora or with a plain leaderboard」、Appendix C の Table 5 は提案にすぎない）。
2. **人間による介入という交絡**：視覚化されたマップ（``diversity-aware views``、5月2日）が提供された後、単栽培されたコミュニティがコミュニティ地図を確認できてから脱出した（§4.7、§5 「the community left its first basin only after we showed it a map」）。
3. **同一評価器での選択による信頼性低下**：「Because every component was selected on the same 200-text development evaluator, the number to trust is the improvement from 3.39 to about 1.90 rather than the final decimal places」（§4.5）、最後の 9×10^-6 の変更は異なるハードウェア間での変動よりも小さい。
4. **勝利した手法が著者によって再実行されていない**：「We did not rerun the winning method」（§4.8）。
5. **多様度アテンションはヒューリスティクスである**：「neither a stationary bandit nor a game tree ... not a guarantee of optimal planning」（§2）。
6. **証拠スコアは真実性を正当化しない**（§3.2）。

**読者としての注意（本書の解釈）**：

7. 開発評価器が示す「訓練済みモデルのギャップの62%を埋めた」という記述は、正確な計算過程を本文からは再導出できません。評価器で使用されたテストは、実測値の再現が込める対象とは異なるものであるため、「62%」という数値は、著者の経験に基づく値として受け取るべきです。
8. 解釈に関する主張（``evaluator is globally linear`` 問題）は著者がユーザーへの入力として提示したものであり、外部の検証がなければ方法の一般的正しさに結びつけることはできません。
9. コミュニティは、May 2 以降、調査ベースのカーブとして、ビジュアライゼーションを中心に展開した。``negative result`` タグは May 2 以降に限定されており、この共通の仕組み自体が集団による追従の基盤となっている。

（「著者自認の限界の数」は上記6項目としており、機械比較用 JSON （項目 F1）もこの値と整合である。§2 の UCB/ヒューリスティクス項目（上記5）を独立した限界として数えず、著者が効果に直接関係する自己宣言として読まれる場合、この限界の数え方は5として分類される。）

## 9. ResearchOS への示唆

1. **共有された git グラフ自体が記憶であるという設計は、本リポジトリの5つの台帳（sources, evidence, verifications, claims, hypotheses）と ****
パブリッシュ可能な証拠グラフを分離（evidence + verification）した設計の独立したプレセデントが存在する（Agora の `verification` ノード（他者による再現、自己作業の除外）の概念は、本リポジトリの verifications 台帳と直接対応している）。
2. **評価者＋検査環境の簡素化**：評価者と検査環境を簡素化することで、Agora 内における開発評価と可視性は本論文の §4.7 のように 100% クラス化し、探索の促進に新たな軸を与えることが示された。ただし、人間の介入を削除しても改めて対応させるのは難しい部分もある。なぜなら人間が興味を引くリード条件は評価者が提供していなかったためだ。
3. **共有 rader が誤り相関からもたらされる重複作業を生み出す**：696 ペアの並行再発見は、独立した作業にもかかわらず重複を引き起こすメカニズムです。著者らはこれに触れていないが、この種のエラー率は単一のセクションで述べるほど強くないか、誤りの性質を定量的に分析する必要がある。
4. **「実行していない」と書かない**：§4.8 の「We did not rerun the winning method」という自己言及は、再現できていないことを隠さないという点で、本リポジトリが重視する報告規律の好例であり、反対に「62%」を数値化することは困難であるため、非宣言型の記述として「測定した数字のバック計算文脈」（§4.5 の9×10^-6 に対する但し書き）を紹介することは、「測定された単一の数字が再計算できるか」という問題を提起することができる。
5. **統制された比較の設計要素は Appendix C の Table 5（Matched Evaluation Matrix）に直接参照できる形ですでに用意されている**：isolated / flat log / central planner / Agora の4条件で「every row uses matched agents, models, compute, evaluator, and wall-clock budget」とする設計は、未完了の部分が何か（＝その matched comparison の実行自体）を明確に示している。

## 10. 本レポート作成時に実行した確認

- `git branch --show-current` → `arena/4403f020-researchos`
- 全文読解：arXiv HTML v1（全10チャンク）と PDF v1（全8チャンク）を取得し、内容の一致（§1–§5、References、Appendix A–C）を確認。
- 書誌照合：abs ページ（取得時 v4 の表示）も確認。タイトル・8名の著者・先頭著者・DOI が fixture (`tests/fixtures/arxiv_metadata_snapshot.json`) と一致（本文の数値は v1 のもの）。
- 検証ゲートの実行はPR本文に実測として記録する。

（Python 3.11.2、2026-10-20。上記以外の実験・実行は行っていない。）

## 11. 提案（本レポートでは実行していない）

1. 台帳 `state/sources.jsonl` の SRC-20261020-f295 に対して、聞き取り内容を基に、本文読了後の所見（特に「因果効果は統制比較が未実施で未確立である」という著者自身の明言）を追記すること（台帳追記は統合役に委ねる）。
2. Appendix C の matched comparison が実施主体によって実行されたかを今後監視する。
3. MLAgentBench および Agora は（本文は未実施）、DuDiscover や git-swarm の環境で監視する。

## 12. 参考文献

[1] Yifan Zhang, Yunheng Zou, Shaokun Zhang, Jian Hu, Hao Zhang, Binfeng Xu, Jan Kautz, Yi Dong. "Agora: Git as Shared Memory for Collective AutoResearch." arXiv:2609.18094v1 [cs.LG], 2026. https://arxiv.org/abs/2609.18094 / DOI: 10.48550/arXiv.2609.18094

[2]（存在確認のみ）arXiv abs ページ：著者一覧と [view license] を確認するのに使用。書誌の照合先は [1] と同一 ID である ― https://arxiv.org/abs/2609.18094 （2026-10-20 確認；このメモ本文で使用した数値は HTML v1 / PDF v1 からのものであり、abs ページの表示自体は当該日の最新版である）

## 13. 抽出項目15点への回答（人手可読版。本文で確認できたことと確認できなかったことを分離）

**本文で確認できたこと**

| ID | 項目 | 値（機械比較用 JSON と同一） | 出典 |
|---|---|---|---|
| A1 | 書誌：タイトル | Agora: Git as Shared Memory for Collective AutoResearch | HTML v1 冒頭／PDF 冒頭（title） |
| A2 | 書誌：著者数 | 8 | HTML v1 冒頭の著者リスト |
| A3 | 書誌：先頭著者 | Yifan Zhang | HTML v1 冒頭 |
| A4 | 書誌：投稿日 | 2026-09-16 | arXiv abs ページ（[v1] Wed, 16 Sep 2026）／HTML ヘッダー（16 Sep 2026） |
| A5 | 書誌：ライセンス | arXiv.org perpetual non-exclusive license | HTML v1 ヘッダー（[License: arXiv.org perpetual non-exclusive license]）／abs ページの [view license] http://arxiv.org/licenses/nonexclusive-distrib/1.0/ ― なお PDF 1面フッターには「© 2026 NVIDIA. All rights reserved.」が併記されている |
| B1 | 設計：ベンチマーク数 | 1 | §4.1 に記載のある唯一の自作評価課題。なお公開された標準ベンチマークの実行がないことは §2 および §4.1 から推認できる |
| B2 | 設計：ベンチマーク名 | weight-transfer task (自作の本論文著者による開発用評価器。評価器は FineWeb-Edu 200 texts の bpb) | §4.1 |
| C1 | 結果：主要結果の代表値 1 | Best transfer(): 1.899044 bpb (§4.5 Primary result) | §4.5 |
| C2 | 結果：主要結果の代表値 2 | From random initialization 3.3923 bpb (§4.5 Primary result / Abstract) | §4.5 |
| C3 | 結果：主要結果の代表値 3 | Closes 62% of the gap to trained GPT-2 124M (about 1.0 bpb) (§4.5 Primary result / Abstract) | §4.5 |
| D1 | 設計：最強ベースライン名 | none （詳しくは以下の「確認できなかったこと」） | §5 |
補足（C1–C3 のスライスについて）：代表値は「Primary result」の数値セットとして直接示された、結果側の3つのコンポーネントのみであり、投稿総数（1,703件）や検証の数（165件）はコミュニティの規模（§4.3 のキーポイント、詳細は §4 の対応する記述を参照）であり、この表の代表値には属しない。

| E1 | 信頼性：単一実行（n=1）か | true | Appendix C（分析単位は the entire community run）、§4.3、§5 |
| E2 | 信頼性：実行回数が明記されているか | true （主要な community run は1つであり明示されている。反復回数として「1回実行した」と分離して明記されているわけではない） | §4.3、Appendix C |
| F1 | 制約：論文自認の限界の数 | 6 （数え方は §8 を参照） | §3.2、§4.5、§4.8、§5、§2、§4.7 |
| G1 | 再現性：コード公開の有無 | unknown （詳しくは以下の「確認できなかったこと」） | §3.4 |

**確認できなかったこと**

- **D1**：並行ベースライン条件（isolated / plain leaderboard 条件）は実行されていない。数値比較に使えるのは、random initialization の 3.3923 bpb （無条件のベースライン）と、trained GPT-2 124M の約 1.0 bpb （``sets the scale; not an achievable no-training baseline`` §4.1）という枠組みだけであり、実行された比較相手よりも弱いベースラインの置換はできないことから、``none`` と判定した。
- **G1**：論文の本文にも、abstract ページにも、本論文の実装を紹介する GitHub の URL は使用されていない。「コードが実際に公開されたか」は本文からは確認できず、確認できないため ``unknown`` と記入した。
- **62%の算出過程** (§4.5) は本文から再導出できず、確認できなかった。
- **v2–v4 の本文** については、内容が部分的に改訂されている可能性があるが、本書では v1 を読解していない。
