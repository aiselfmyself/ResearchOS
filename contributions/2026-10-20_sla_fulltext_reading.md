# 全文読解レポート 1：Stateless Language Agents（SLA）

- 作成日：2026-10-20
- 対象：[1] Zhang et al. (2026) "Stateless Language Agents: Scaling Long-Horizon Automated Research" arXiv:2610.07625v1 の**全文**
- 位置づけ：`task/TASK.md` §1「Stateless vs GitSwarm」に対応する、既存 `contributions/2026-10-20_stateless_vs_gitswarm.md`（abs＋要旨＋GitSwarm部分節中心）の続編。**新しい実験は行っていない**。実行した確認は §9 に列挙する。
- 方法：arXiv の PDF 本文（取得ツールによるテキスト抽出、全14チャンク）を通読し、HTML 版と abs ページで書誌・数値を照合した。追加の資料検索は1件（コード公開の確認、§11 [4]）のみ。

## 1. 結論（全文から新しく分かったこと）

1. **主要結果の再現回数は極端に偏っている。** Anthropic カーネル＋Codex（3回）とチェックポイント継続アブレーション（各3回）以外は**すべて単一実行**である（§4.1 "Other main-result configurations use one run per method"、§5 Limitations）。既存メモはこの制約を記載しておらず、「全タスクで最良」という主張の強さを測る上で最重要の情報である。
2. **方法ランキングは評価予算で逆転する**（§1 finding "Method rankings depend on the evaluation horizon"）。FrontierSWE 4タスクすべてで SLA は 25% 予算時に最強ベースラインを下回り、100% で全タスク逆転して首位（Table 2）。既存メモ §6 の「短い評価は誤判断を生む」を定量化している。
3. **協調コストは役割設計で1桁以上変わる。** SLA の Advisor はトークンの 0.24–0.51%・コストの 1.20–2.29% に対し、SwarmResearch の Shepherd はトークンの 8.39–10.70%・コストの 6.14–7.35%（Table 5）。Shepherd の平均コールは約99K入力トークンを読み続ける（新規セッション開始時の約8Kの12倍超、§4.4）。
4. **SLA には多数決が一切存在しない。** 選択は「保護された評価器の測定値＋harness」のみで、GitSwarm が「検証不能時のフォールバック」として置く推薦多数決に相当する機構は設計にない（§3 全体、§4）。既存メモ §5 の「多数決は検証不能時のフォールバック」という整理を、対照側から裏付ける。
5. **コンテキスト再構成は「要約 vs 全履歴アクセス」の実測比較で勝っている。** Advisor 再構成を外した variant（全時系列記録を最大32コール・320K字で読む）は、共有チェックポイント継続の全4設定でフル SLA を下回る（Table 4）。既存メモ §4 の「要約の質に依存する」は「再構成は全履歴アクセスより良い」という実測結果に升级できる。
6. **隔離コストは時間とともに複利で悪化する。** Worker 隔離を外した場合、100M トークン継続では 5–11 cycle の差だが、1B 全走行では **224 cycle** の差（1336 vs 1112.0、§4.3）。短予算のアブレーションだけを見ると構造的リスクを過小評価する。
7. **公開コードリポジトリが存在する**（§11 [4]）。再現コストの議論（§8）で前提できる。

## 2. 読解の範囲と方法（正直な記録）

- **読了**：本文 §1–§5、Appendix A（関連研究拡張）、B（実験実装詳細）、C（追加結果）、D（トレース分析 D.1–D.3）、E（プロンプト集）の大半。
- **未読**：Appendix E の末尾数ページ（FrontierSWE Advisor プロンプトの途中以降）。取得ツールの PDF 解析上限（30ページ／本論文は32ページ）による。プロンプト集は分析の主対象ではなく、本文・Appendix A–D の分析に未読分は影響しない。
- **照合**：書誌（著者・年・タイトル）は abs／HTML／PDF の3経路で一致、`tests/fixtures/arxiv_metadata_snapshot.json`（PR #13）と一致。数値引用は本文の表・節番号を付記。
- **追加検索**：1件のみ（[4]）。文献そのものの追加収集は行っていない。
- 本レポートの引用はすべて上記取得で実際に読んだ文言である。読んでいない節を読んだと主張しない。

## 3. 設計の詳細（全文から分かったこと）

### 3.1 state / context の分離と文脈再構成（§3.1）

- harness が保持する **state**（global best、local candidates、outcome record）と、各エージェントが見る **context** を分離し、Advisor は epoch のたびに、Worker は trial のたびに文脈を再構成する。「what each role sees from that evidence also matters」（§4.3）— 全証拠を保持するだけでは足りず、**渡し方**が結果を変える。
- Advisor 文脈：タスク仕様＋global best＋harness が要約した evidence summary（方向別に群化、**measured non-improvement と implementation failure を区別**して「失敗＝方向枯渇」と誤読を防ぐ）。
- Worker 文脈：仕様＋assignment＋自分の保持 candidate＋直近の局所フィードバックのみ。他 Worker の作業場・全履歴には**アクセス不可**（§3.1）。

### 3.2 evidence-driven assignment（§3.2）

- Advisor は stateless なので「自分の過去の推理」ではなく**現時点の証拠から毎 epoch 割当をやり直す**。Worker は assignment の実装方法を局所 trial で決める。
- local candidate は global best に劣っていても保持され、時間が成熟する。割り替え時は global best から再出発（§3.2）。
- これにより**同質 Worker の重複作業**を中央割当で防ぐ。トレース（Appendix D.3）：assignment を外すと3つの独立 run で**全て同じ XML entity デコード実装**を同時並行で実施し誰もスコアを改善せず（trials 269–271、257–259、269–271）、別の run では2 Worker の提出ファイルが「ラベル名1箇所だけ違う同一物」だった（trials 293/296）。

### 3.3 「依頼」ではなく「実行」で担保する分離（§3.3、Appendix B.1）

- "Statelessness and isolation are enforced rather than requested."（§3.3）：Advisor は毎 epoch 新セッション、Worker は**非特権プロセス＋Linux Landlock**（他 Worker ディレクトリ・過去成果物へのアクセス遮断）、ネットワーク制限、trial 間で保存セッション消去、Codex の組み込みマルチエージェント機能も無効化。
- 評価は Worker 環境の**外**で保護された評価器により実施。候補コードは「untrusted data, never instructions」として prompt レベルでも明示（Appendix E）。
- checkpointing により「同一 research state からアブレーション」が可能 — これは本リポジトリの「再実行できるものだけ」方針と同型の、**成果物ではなく状態を保存する**設計。

## 4. 評価設計と結果の読み方

- **タスク8種**（§4.1）：FrontierSWE 4（libexpat、Git→Zig、Dart→Haskell、Lua）、Anthropic VLIW SIMD カーネル、SOL-ExecBench 3（#1/#58/#210、2026-08-01 時点の最多提出から選定）、FrontierCS Structured-LWE。選定基準は明示的に「**予算内に headroom があるタスク**」（§4.1、§2.2）。
- **主要比較**（Table 1–3）：カーネル 1B で SLA 1112.0±8.9 cycle vs 最強ベースライン SwarmResearch 1275.7±133.9（3 run が全て9ベースライン run に勝る：1122 vs 1191）。到達トークンでは 67.9M vs 986.3M＝**93.1% 削減**（Claude Code 構成では 84.4%）、SOL #58 では 95.9% 削減。ただし **SOL #1 では EvoX が先に到達**する例外も明記（§4.2）。
- **FrontierSWE の逆転**（Table 2）：175M で SLA は全タスク劣後（−0.85〜−11.27点）、700M で全タスク優位（+0.86〜+6.75点、平均 +4.95点）。
- **協調コスト**（Table 5、§4.4）：§1 結論3のとおり。トークンの9割超がキャッシュ入力のため「トークンシェアはキャッシュ再利用が少ない役割のコストを過小評価する」との注記付きで、コストシェアでも同順位。
- **Worker 数**（Table 6）：W=1→15 で時間 6.6×（カーネル）・7.3×（FrontierSWE 平均）。25% 予算で W=7 が337 cycle 劣後も100% では全幅 1107–1113 cycle に収束。ただし FrontierSWE の最適幅はタスクごとに異なり、**W=15 はどの FrontierSWE タスクでも100%予算で最良にならない**。既定 W=3 は最良から5 cycle／3.2点以内。
- **Worker モデル選択**（§4.4、Appendix C.1）：$100 揃えで GPT-5.4 mini Worker が Git→Zig では GPT-5.5 Worker に勝つ（20.88 vs 19.68）がカーネルでは負ける。安価モデルが勝つかはタスク次第。
- **乱数・感度**（Appendix C.2）：局所 trial 数（1/3/5）は4設定中3で既定3が最良、カーネルでは全設定が1標準偏差内 — この範囲では超パラメータ感度は小さい。
- **信頼性の限度**（§4.1、§5）：上記のとおりメイン結果の大半は n=1。比較はトークン一致だが**実験・評価の計算コストは見積もりに含まれない**。アブレーションが変えるのは「何を見るか」であって「会話を持ち越すか否か」ではなく、後者は未検証（§5）。

## 5. アブレーションとトレース分析（全文の骨格）

- **Table 4**（共有チェックポイントから各 +100M、3 run 平均）：reconstruction 除去で進捗 −23.3〜−72.2%、isolation 除去で −17.4〜−74.8%、assignments 除去で −10.5〜−84.2%。**全比較でフル SLA が勝る**（§4.3）。
- **フル走行での隔離除去**：1336 cycle（1112.0 比で +224 悪化）。「the cost of unfocused Worker contexts compounds over longer horizons」（§4.3）。
- **D.1（CORAL Lua）**：2時間前のノートを読み直した agent が、別系統リードで失われていた機能を再実装し 88.46→89.01。**ただし同時刻に同じノートを読んだ他2 agent も同一機能を再実装**（attempt 149/151/158）— 33試行に渡って機能が欠落し続ける、記録と並行化の競合。
- **D.2（CORAL libexpat）**：13分間に同一2 agent が同一機能を2回ずつ実装。「Recorded findings thus do not by themselves coordinate what parallel agents try next」（D.2）。focus note（この方向は俺がやる宣言）も重複を防げなかった。
- **D.3（SLA assignment アブレーション）**：§3.2 記載の重複実装事例と、逆に assignment により Worker1 の改善（UTF-8/name、18.99）を Worker2 が引き継いで 19.64 に伸ばした事例。ただし著者自身が「これらの trace は挙動を**測定したものではない**」と注記（D.3末尾）。
- **Figure 2／§2.2（ベースライン側の失敗モード）**：26-circle packing は5Mトークンで4手法が 2.3×10⁻¹⁰ 以内に飽和。CORAL カーネル run は最終改善が231Mトークンで、最終1,500セッションの98%がツール呼び出しゼロ。

## 6. 既存メモ・台帳との突合

| 既存の記述（場所） | 全文読解の結果 |
|---|---|
| 既存メモ §3.1「最終選択：測定結果を所有（**規則は未確認**）」 | **規則を特定**：harness が local best／global best を測定値で保持・更新（§3、§3.2）。local candidate は劣っていても保持され、SOL の prompt では "SLA alone keeps or rejects the measured candidates"（Appendix E）。タスク間で共通の選択規則そのものより「評価器＋harness」が選ぶ、という構造が本体 |
| 既存メモ §4「前者（SLA）は文脈を小さく保てるが**要約の質に依存**」 | **実測で upgrade**：再構成 vs 全履歴アクセスの直接比較で再構成が全4設定で勝つ（Table 4）。要約失敗リスクは残るが、現時点の測定では要約なしより良い |
| 既存メモ §5「多数決は検証不能時のフォールバック」「独立検証は別手続きで」 | **対照側から支持**：SLA に多数決はなく（§3–§4）、評価器は Worker 環境外の保護実装（§3.3）。ただし SLA は検証不能タスクを**扱っていない**（§5 "goals that are vague or slow to evaluate remain untested"）ため、曖昧タスクでの優劣は未検証のまま |
| 既存メモ §6「SLA と GitSwarm のベンチマークは重ならない」 | **維持**：SLA は FrontierSWE4＋カーネル2種＋SOL3＋FrontierCS1、GitSwarm は IMOProofBench／ProgramBench／NNアーキテクチャ。重複ゼロ |
| 既存メモ §3.3 表「失敗モード：状態・要約・Advisor への依存（**本メモの整理**）」 | 整理は妥当だが、**論文自身の限界記述**（§5）に置き換え・追補可能：n=1 の偏り、評価器込みの計算コスト除外、曖昧タスク未検証、research state 自体が悪さ（game する候補）を持ち得ること |
| CLM-001（supported、EVD-001）：Stateless Harness は文脈埋没・重複作業を防ぐ | **全文の実測でさらに支持**：重複作業は D.3 で直接観測、埋没対策は §2.2／Liu et al. [R2]（長大セッションは独立サンプリングを下回る）で動機付け。EVD-001 の abstract 引用は本文照合でも一致 |
| CLM-003（candidate）：同質ワーカー多数決は誤りを増幅しうる | SLA は多数決なしなので**直接の証拠にならない**が、同質性の問題は自覚的（§4.1 主実験では Advisor/Worker 同一 LLM「gains cannot come from a stronger Advisor」＝同質性をあえて維持）。検証は引き続き GitSwarm 側・合成実験の課題（既存メモ §8 提案） |
| CLM-006／EVD-007：SRC-001 著者訂正 | abs・HTML・PDF の3経路すべてで先頭著者は Qizheng Zhang。訂正済みデータと一致 |

（CLM/EVD の台帳追記は本レポートでは行っていない。追加は提案 §10 参照。）

## 7. Negative findings / 制約（論文自認＋読者としての注意）

**論文自認（§5 Limitations、§4.1）：**

1. 主要構成の大半が単一実行。複製は Anthropic カーネル＋Codex とチェックポイントアブレーションのみ。
2. 比較はトークン一致であって**コスト一致ではない**。実験実行・評価の計算コストは見積もり外。
3. アブレーションは「会話を持ち越すか」ではなく「何を見るか」のみ変更。stateless 化そのものの寄与は未分離。
4. 全タスクが実行可能評価器付き。**曖昧・低速評価のタスクは未検証**。
5. research state 自体が問題を持ち得る（評価器を game する候補コード）→ 保護評価器は必須。

**読者としての注意（本レポートの解釈）：**

6. タスクは「headroom があるもの」から選定されており、負の結果（SOL #210：どの手法も +0.02 未満）を含む。**タスク選定が主張の外挿範囲を規定する**。
7. ベースラインは著者らが pinned 版で構成した adaptation（EvoX はコーディングエージェント化、§4.1／B.2）。実装適配の質が比較に影響し得る点は原著の限界ではないが留意要。
8. v1 査読前プレプリント。外部再現は公開コード（§11 [4]）があっても10億トークン規模の予算が壁。

## 8. ResearchOS への示唆

1. **台帳＝harness-owned state の実例**：SLA は「状態はモデルの外側に置き、checkpoint して rollback できる」ことを安全性の根拠にする（§5）。本リポジトリの state/ ＋検証器（`scripts/validate_state.py`）は同一の発想。一方「state が semantic な誤りを持ち得る」（§5）は、監査で見つけた「手書き成果物」問題と同型で、**構造的保証（スキーマ・再実行）と意味保証（人間レビュー）の二層が必要**という当リポジトリの方針を論文側も認めている形。
2. **評価は複数予算で**：ランキング逆転（§4 結論2）は、本リポジトリの gitswarm ベンチや今後の比較実験を「単一ポイントの数値」で報告しない理由を与える。`benchmark.py` の複数シード設計はその最小形。
3. **n=1 を n=1 と書く**：SLA 論文が自ら明記した通り、長い走行は高コスト。ResearchOS の報告でも「実行していない／単一実行」を明示する規約（既存メモ §7、本 §9）は同じ教訓。
4. **中央割当 vs 自律 readout の対比が確定**：次の行動決定を誰がするか（SLA=Advisor 割当、GitSwarm=ワーカー自律＋readout フォールバック）は、優劣ではなく**設計軸**として記録する。検証可能な ResearchOS の課題では SLA 型（harness が割当・選択）、曖昧な課題では GitSwarm 型の readout をどう扱うかは §10 提案の実験対象。
5. **短い invocation の列**としてタスクを切る発想（post-training 含む、§5）は、今後の ResearchOS タスク分解（task/TASK.md のサブタスク化）に対応する。

## 9. 本レポート作成時に実行した確認

- `python3 -m unittest discover -s tests` → **45件 OK**（既存28＋PR #13 の17）
- `python3 gitswarm/benchmarks/benchmark.py --check` → PASS
- `python3 scripts/validate_state.py` → PASS（sources=4, evidence=14, claims=7, verifications=21, hypotheses=3）
- `python3 scripts/check_citations.py` → 3 checked / 1 skipped / 0 failures
- 書誌照合：abs／HTML／PDF の3経路のタイトル・著者・年が fixture と一致

（Python 3.11.2、2026-10-20。上記以外の実験・実行は行っていない。）

## 10. 提案（本レポートでは実行していない）

1. 本レポートの知見を反映する EVD/CLM の追記（`scripts/new_id.py` で採番、PR 経由で人間レビュー）— 特に「再現回数の偏り」と「予算によるランキング逆転」は将来の主張に対する counterclaim 素材。
2. GitSwarm [2] の全文読解レポート（本レポートと同じ方法で、既存メモの §5 中心部を一次本文で裏付け直す）。
3. DuoDiscover [3] の全文読解（既存メモは要旨のみ）。
4. 公開コード（[4]）を使った再現性調査 — ただし計算予算が実質不可のため、まず「コードの公開範囲と README の実行条件」の調査に留めるのが現実的。

## 11. 参考文献

[1] Qizheng Zhang, Changxiu Ji, Isaac Sun, …, Kunle Olukotun. "Stateless Language Agents: Scaling Long-Horizon Automated Research." arXiv:2610.07625v1 [cs.LG], 2026（投稿 2026-10-06）. https://arxiv.org/abs/2610.07625 / DOI: 10.48550/arXiv.2610.07625

[2]（本レポート内の対照引用）Vedant Shah, Ankur Samanta, Paras Dahal, …, Anirudh Goyal. "GitSwarm: Decentralized Compounding Inference." arXiv:2610.04862v1 [cs.AI], 2026. https://arxiv.org/abs/2610.04862 — 書誌は既存 `2026-10-20_stateless_vs_gitswarm.md` §9 と同一。

[3]（言及のみ）Shubham Agarwal, Akshat Gupta, Mike Heddes, …, Chun-Liang Li. "DuoDiscover: Scaling Autonomous Discovery Beyond the Evaluation Bottleneck." arXiv:2610.17184v1 [cs.CL], 2026. https://arxiv.org/abs/2610.17184

[4] 論文 HTML の著者注記に記載されたコードリポジトリを Web 検索で確認：Papers with Code の該当ページも同じ URL を codeRepository として保持 — https://github.com/Alex-q-z/stateless-language-agents （2026-10-20 確認。リポジトリ内容自体は未検証）

（内部記録 `state/`・`contributions/` への参照は文献引用ではない。数値・引用はすべて [1] の本文取得（PDF 全14チャンク＋HTML 照合）に基づく。）
