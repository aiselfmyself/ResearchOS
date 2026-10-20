# 文献調査メモ 2：長期推論における文脈管理と評価のボトルネック

- 作成日：2026-10-20
- 対象：`task/TASK.md` §2 のうち未着手だった部分——項目1「単一エピソードに巨大な会話履歴を詰め込む従来型アーキテクチャの限界」と、項目3のうち評価・検証のボトルネックにあたる側面
- 位置づけ：arXiv プレプリント7本（新規6本＋既存1本の再掲）の調査メモ。新しい実験は行っていない。実行した確認は §8 に列挙する。

## 1. 結論

- 単一会話履歴に全履歴を載せる構成では、長期推論タスクで**文脈そのものが精度とコストの両方の律速**になる。全履歴保持を「選択的保持＋要約」が精度・トークン双方で上回る直接比較が [2] にある（完全履歴 71.0% / 1,480,996 トークン → 保持＋要約 91.6% / 553,374 トークン）。
- 文脈管理は実装詳細ではなく**性能変数**である。context engineering を専門分野として定式化する survey [1]、long-horizon / long-context / long-term memory を峻別する survey [3] が、同じ方向を別アングルから示している。
- 評価のボトルネックは3層で整理できる。(a) 最終スコアだけでは過程のボトルネックが見えない [6]、(b) 観測可能性の縮小——トランスクリプト膨張・人手レビュー・検出力・帰属 [4]、(c) モデル性能と harness 性能の誤帰属 [5]。
- 両者は同一の層で接続する。文脈構築・ツール仲介・検証を担う harness の変更が、モデル交代を超える幅で評価値を動かす [5]。つまり「文脈をどう詰めるか」と「評価値を誰に帰属させるか」は独立した問題ではない。
- 評価コスト自体が検出力を律速する。真の評価1回に数時間 [7]、体系的評価だけで約10万ドルの推論費 [6]。「評価できなければ検証も改善もできない」のがボトルネックの本体である。

## 2. 対象文献と確認方法

対象は [1]〜[7] の7本。うち [7] DuoDiscover はメモ1（`2026-10-20_stateless_vs_gitswarm.md` [3]）で書誌確認済みのため本メモでは評価ボトルネックの主題文献として再掲し、残り6本が新規である。2026-10-20 に Web 取得ツール経由で arXiv の abs ページ（[4] [5] は HTML の該当節も）を読んで書誌（arXiv URL・著者・出版年）と引用数値を実地確認した。このサンドボックスからは arXiv への直接 HTTP は通らないため、abs/API 相当の書誌は `tests/fixtures/arxiv_metadata_snapshot.json` に7件追記し（capture_note 更新）、`scripts/check_memo_citations.py` が本メモを含む `contributions/*.md` の引用をオフラインで照合する。実行結果は §8。文献の引用はこの7件のみで、内部記録への参照は文献引用ではない。

## 3. 文脈管理のボトルネック（§2 項目1）

### 3.1 全履歴保持は精度・コスト双方で最善ではない [2]

[2] は GPT-5 に4つの文脈構成を比較させた（50タスクのホテル経費明細化、5回の独立実行、ユーザーモデルは固定）。ユーザーモデルなしは 8.0%。全会話履歴の保持は 71.0% に達するが 1,480,996 トークン・14.56 時間を消費する。直近5ツール往復への刈り込みは 79.0%・535,274 トークン・5.39 時間。刈り込み＋自動要約が 91.6% 完了・平均金額 99.64%・553,374 トークン・5.79 時間で最良、Claude Sonnet 4.5 でも同じ方向の証拠を報告する。**「履歴は入れるほど強く」は成り立たず、費用は線形でもない。** 制約は対象が enterprise tool-use の1課題クラスである点（§6）。

### 3.2 文脈は分野として扱われる [1]

[1]（1,400本超の survey）は context engineering を、プロンプト作成を超えて「情報ペイロードの体系的最適化」として定式化し、context retrieval and generation / processing / management の階層で整理する。挙げている構造的ギャップは、理解側は高機能なのに**長文生成側が伴わない非対称**である。文脈管理の問題は入力だけでなく出力にも開いている。

### 3.3 horizon と context を混同しない [3]

[3]（1,547本、2024–2026、bleed filter 26.8% を開示）は3概念を峻別する——long-horizon はタスク性質（必要ステップ数）、long-context はモデル性質（トークン容量）、long-term memory はシステム性質（ステップ/セッションを跨ぐ持続性）。その上で全カテゴリ共通の発見として、**horizon が伸びるほど outcome-only 指標は非情報化する**と述べる。これは文脈問題を評価問題へ接続する橋であり、次節の出発点になる。

## 4. 評価のボトルネック（§2 項目3 の側面）

### 4.1 最終スコアは過程を見えないにする [6]

[6] はフロンティア7モデル×長期R&Dタスク36件を、LLM ジャッジではなく**規則ベースのプロセス指標**（Solution Framing / Execution / Feedback Control）で分解評価した。7モデル×36タスクの完全評価に推論費は約10万米ドル。結果は、実行は run 間で大きく揺れ、**似た最終スコアの背後には異なるプロセスのボトルネック**があり、本物の新規性は稀で、harness 設計が安定性を左右する、というもの。最終スコアは「どこで詰まったか」と「経験が次に活きたか」を同時に隠す。

### 4.2 観測可能性の縮小 [4]

[4] は長期評価で評価者が推論できる範囲（observability envelope）が狭まるとし、圧力を4つ挙げる——(i) within-run opacity：最終スコアが捨てられた方針・軌道修正・評価ゲーミングを目撃前に隠してしまう、(ii) human attention bottleneck：数百ページのトランスクリプトに専門家レビューが追いつかない、(iii) insufficient statistical power：長期実行は高コストなので反復回数が減り、最終スコアだけの測定がタスク分散と確率的揺らぎにさらされる、(iv) setup attribution uncertainty：成績はモデルとシステム（harness 含む）の両方の関数である。実演は約1,300万トークンの AI R&D 評価で、操作作業と論文執筆に偏り、**持続的な仮説生成段階の証拠は乏しかった**。

### 4.3 誤帰属：harness がモデルを超える [5]

[5]（position paper）は Binding Constraint Thesis を主張する——同等のフロンティア能力では、harness 構成がモデル選択より性能分散を支配する。具体例として、モデルを固定して harness だけ変えれば Terminal-Bench 2 pass@1 が 69.7%→77.0%、第三者の監視では SWE-bench Verified に scaffold のみで最大15ポイントの変動、同じモデルでも SWE-bench Pro で SEAL scaffold 45.9% vs Claude Code 55.4%。提案は harness 開示・locked-harness・factorial プロトコルであり、**開示がない間は長期エージェントのリーダーボード比較は不完全かつ誤誘導的**とする。数値はいずれも同論文が引用した外部ベンチマークの二次引用である（§6）。

### 4.4 評価コストが検出力を律速する [7]

[7] は「進捗を評価するコスト」を自律探索の根本ボトルネックと定義する——実環境では真の評価1回が数時間かかり、探索は数回しか真の評価を買えない。各ワーカーが最適化対象と速い proxy 評価器（yardstick）を共同発見し hill-climb、**fidelity tests が yardstick の順位を再検査してドリフトしたものを無効化する**。SWE-fficiency で人間エキスパート平均の2倍の改善、SOL-Exec で235カーネル中121カーネル首位、vLLM/SQLite で 1.92×/1.38×、評価に最大28時間かかる CPU マイクロアーキテクチャ課題で ArchAgent v2 の改善量の 1.65× を16.7日で達成（既存手法は40日超）。「評価器自体を検証する」点はメモ1 §5 の独立検証の知見と一致する。

## 5. 両者の接点（文脈管理 × 評価）

- harness は文脈構築・ツール仲介・リトライ・**出力検証**を決める層である [5]。したがって文脈管理ポリシー（どれを残し、どこで要約するか）の変更は、評価値に直接混入する。文脈を削りすぎた劣化はモデルの劣化として、harness の改善はモデルの改善として測定され得る。
- [3] が挙げる未解決の測定問題も同じ方向——モデルと harness の能力分解、そして訓練側プロセス信号と評価側指標が**共有前提に由来する相関バイアス**（correlated measurement bias）の管理である。[4] の setup attribution uncertainty はこれを評価者側の語彙で同じ問題として記述している。
- ResearchOS への示唆（本メモでは実験していない）。メモ1が整理した SLA/GitSwarm は「会話履歴を性能の源泉にしない」設計だった。[2] の選択的保持＋要約、[1] の管理された文脈は、状態をモデルの外に置く方向と整合する。評価側は、fixture 付き機械照合のような**帰属可能な検証**を増やす方向に効く。ただし文脈管理の改善が評価改善に直結する因果は、挙げた7本のいずれも分離していない（むしろ [5] が混同を警告している）。

## 6. Negative findings / 制約

- 7本中 [1] は ongoing work の survey（v2）、[3] は survey、[4] はツール＋評価実例、[5] は実験を持たない position paper、[2] は1課題クラスの企業業務、[6] は AI-R&D 専用の36タスクで高コスト、[7] は v1 の査読前プレプリント。**査読済み確定知は本メモには1件もない。**
- 共通モード障害と多数決の増幅は、今回追加した6本にも直接測定した研究は存在しない（メモ1 §5 の未解決事項がそのまま残る）。
- 「文脈管理の改善→評価指標の改善」を因果的に分離した研究は7本中に存在しない。[5] は因果の混同そのものを問題視する止まりである。
- 安い代替評価（proxy）の妥当性を体系的に検証したのは [7] の fidelity tests のみで、これは同システム内での機構にとどまり、第三者的な cross-system 検証ではない。
- 本メモの数値はすべて本文または abs/HTML の記載の転記であり、本リポジトリでの再実験は行っていない。

## 7. task/TASK.md §2 との対応

| §2 の項目 | 状態 | 根拠 |
|---|---|---|
| 1. 単一会話履歴の従来型アーキテクチャの限界 | **未着手 → 本メモで処理**（§3） | 既存メモ5本のどれもこれを主題にしていなかった |
| 2. Stateless（永続メモリ外部化）vs GitSwarm の比較 | 完了（本メモでは重複回避） | `2026-10-20_stateless_vs_gitswarm.md` §3–4、全文読解レポート1・2 |
| 3. 共通モード障害・多数決・独立検証 | 一部完了（メモ1 §5）＋本メモで評価ボトルネック面を処理（§4） | 多数決と独立検証はメモ1が処理済み。共通モード障害の直接測定は**未着手のまま**（誰も測っていない、§6） |

## 8. 本メモ作成時に実行した確認

- `python3 -m unittest discover -s tests` → 74件 OK（既存45件＋新規29件）
- `python3 scripts/check_citations.py` → summary: 3 arXiv source(s) checked, 1 skipped, 0 failure(s)
- `python3 scripts/check_memo_citations.py` → summary: 6 memo(s) scanned, 18 arXiv citation(s) checked, 1 skipped, 0 failure(s)
- `python3 scripts/validate_state.py` → PASS: research ledgers valid (sources=4, evidence=14, claims=7, verifications=21, hypotheses=3)
- `python3 gitswarm/benchmarks/benchmark.py --check` → PASS: benchmark artifact matches a fresh execution

（Python 3.11.2、2026-10-20。上記以外の実験・再実行は行っていない。書誌の実地確認は Web 取得ツール経由の arXiv abs/HTML 読みのみで、arXiv API の実アクセス（`--live`）は行っていない。）

## 9. 提案（本メモでは実行していない）

- `core-check.yml` に `check_memo_citations.py` を**オフライン検査**として追加する（ネットワーク非依存なのでゲート化可能。ただし今回の DoD に含まれないため未実施）。
- 今回追加した6本を `state/sources.jsonl` に非連番ID（`scripts/new_id.py`）で追記し、台帳側からも照合可能にする。
- Agora（arXiv:2609.18094、GitSwarm 全文読解 [G3] で書誌のみ確認済み・本文未読）の全文読解。
- 同一 harness・同一モデルで文脈ポリシーだけを変える ablation（[2] の本リポジトリ規模への転用）。

## 10. 参考文献

[1] Lingrui Mei, Jiayu Yao, Yuyao Ge, …, Shenghua Liu. "A Survey of Context Engineering for Large Language Models." arXiv:2507.13334v2 [cs.CL], 2025（投稿 2025-07-17）. https://arxiv.org/abs/2507.13334 / DOI: 10.48550/arXiv.2507.13334

[2] Abhilasha Lodha, Mahsa Pahlavikhah Varnosfaderani, Abir Chakraborty, Abhinav Mithal. "Less Context, Better Agents: Efficient Context Engineering for Long-Horizon Tool-Using LLM Agents." arXiv:2606.10209v1 [cs.AI], 2026（投稿 2026-06-08）. https://arxiv.org/abs/2606.10209 / DOI: 10.48550/arXiv.2606.10209

[3] Mingguang Chen, Licheng Wang, Bo Qu. "The Horizon Gap: Planning, Memory, Execution, Training, and Evaluation for Long-Horizon LLM Agents." arXiv:2608.06663v1 [cs.CL], 2026（投稿 2026-08-07）. https://arxiv.org/abs/2608.06663 / DOI: 10.48550/arXiv.2608.06663

[4] Toby D. Pilditch, Konstantinos Voudouris, Alexandra Abbas, Cozmin Ududec. "Transect: Retaining Observability for Long-Horizon LLM Agent Evaluations." arXiv:2610.08364v2 [cs.AI], 2026（投稿 2026-10-06）. https://arxiv.org/abs/2610.08364 / DOI: 10.48550/arXiv.2610.08364

[5] Yunbei Zhang, Janet Wang, Yingqiang Ge, Weijie Xu, Jihun Hamm, Chandan K. Reddy. "Stop Comparing LLM Agents Without Disclosing the Harness." arXiv:2605.23950v1 [cs.AI], 2026（投稿 2026-05-07）. https://arxiv.org/abs/2605.23950 / DOI: 10.48550/arXiv.2605.23950

[6] Yiwei Li, Wanli Yang, Hexiang Tan, …, Jingang Wang. "Beyond Final Scores: A Systematic Evaluation of Agents for Long-Horizon AI Research and Development." arXiv:2608.13417v1 [cs.AI], 2026（投稿 2026-08-13）. https://arxiv.org/abs/2608.13417 / DOI: 10.48550/arXiv.2608.13417

[7] Shubham Agarwal, Akshat Gupta, Mike Heddes, …, Chun-Liang Li. "DuoDiscover: Scaling Autonomous Discovery Beyond the Evaluation Bottleneck." arXiv:2610.17184v1 [cs.CL], 2026（投稿 2026-10-12）. https://arxiv.org/abs/2610.17184 / DOI: 10.48550/arXiv.2610.17184

（[1][6][7] の著者は紙幅のため先頭3名と末尾1名を記載。全著者は各 arXiv URL を参照。）
