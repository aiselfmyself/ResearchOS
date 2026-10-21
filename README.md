# ResearchOS

研究オペレーティングシステムの最小コア。研究の状態・証拠・実行・検証・履歴をモデルの外側で管理するための、小さく再実行可能な起点である。

> **状態（2026-10-20）**：2026-10-19 の実装線路はガバナンス機構の自己言及ループに陥り、`main` へのマージが0件のまま停滞した。経緯と分析は `docs/stagnation-analysis-2026-10-20.md`、最小コアへの立て直し方針は `docs/minimal-core-and-ci.md` を参照。本ブランチは「再実行できるものだけを `main` に載せる」ための最小抽出である。
>
> **同日の追加**：未完了要素の棚卸し（`docs/incomplete-work-audit-2026-10-20.md`）の指摘に基づき、統合レポート（`contributions/2026-10-20_integrated_survey_report.md`）、共通モード障害の決定論的測定（`gitswarm/readout_sim.py`）、反証の紐付け、既知の誤記2件の訂正、出典7件の台帳登録を行った。
>
> **2026-10-21 の進展（証拠の充実と誤りの訂正）**：3 セッションの並列照合（S1/S2/S3）が 6 論文 48 claim を原典と突き合わせ、統合役が裁定して **EVD 33 件を追加**した（evidence 14 → **47**）。**11 ソースすべてが 1 件以上の EVD を持つ**状態になった（照合開始前は 4/11）。照合の過程で**文献メモの誤り 2 件**を捕捉し、人間の承認を得て訂正した。
>
> - (a) arXiv:2605.23950 を「実験を持たない position paper」としていた誤り。原典 §4.2 は **3 モデル × 3 ハーネスの計画格子実験**を実施しており、**ハーネス分散はモデル分散の 7.80 倍**、**9 組中 6 組で順位逆転**を報告している。本リポジトリの問い（性能差はモデルか harness か）に対する最も直接的な先行測定だった。
> - (b) context engineering の 3 構成要素（Retrieval and Generation / Processing / Management）を「階層」としていた誤り。原典は**平坦な列挙**である。
>
> 統合レポートを**第2版**に改訂した（Agora 本文読解 §4.4・§5.6、自律研究の現在地 §5.7 を新設、[8] の自前実験を §3.3 に反映、各所の計数を更新）。監査 ID 15（SRC-004 への VER が 0 件）を解消し VER 2 件を追加した。**台帳は sources=11 / evidence=47 / claims=8 / verifications=27 / hypotheses=2。** <!-- drift-ok: 当時点のスナップショット -->
>
> **同日の整理**：監査 ID 11（旧ブランチのアーカイブ）を完了した。人間の承認を得て `arena/*` のリモートブランチ **36 本すべてを削除**し、**リモートのブランチは `main` のみ**になった。あわせて ID 12（記録数値のドリフト是正）を人間の判断で撤回した。これで `docs/incomplete-work-audit-2026-10-20.md` の**未対応項目はゼロ**になった。

> **〔2026-10-21 追記〕** 上記 2 文は**実行時点（PR #35 マージ直後）の記録**であり、現在は正しくない。
> - **リモートブランチは 2026-10-21 時点で 10 本**（`main` ＋ `arena/*` 9 本）ある。内訳は
>   マージ済み PR の作業ブランチ 6 本（`ahead=0`。内容は `main` に包含）と、未マージ 3 本
>   （`ahead=1`）。**ID 11 の全削除は事実だが、その後ふたたび `arena/*` が積み上がった。**
>   このうち RRSI 読解・Agentic Scientist 読解・ワーカー割当プロンプトの 3 本は
>   本日の現況監査で検出され、**PR #47 で `main` へ取り込まれた**（未マージ解消）。
>   残る 6 本（`ahead=0`）の削除は人間の承認を要する破壊的操作
>   （`docs/autonomous-merge-policy-2026-10-21.md`）であり、**未決着として残す**。
> - **「未対応項目はゼロ」は当時の記述としても正確ではない。** 記述時点で ID 16 は未対応であり、
>   **監査 ID 18**（閾値 R ~ 1 の検証に必要な「同一タスク領域内でモデル格差を変えた第3の論文」の
>   収集）は **2026-10-21 現在も未解決**（`docs/incomplete-work-audit-2026-10-20.md` §14.9）。
>   ID 16 は同日 04:13 UTC に Issue 4 件がクローズされ解消した。
>
> **「ハーネスは順位を変えるか」の決着（報告 §7 未解決 #9）**：[8]（9 組中 6 組で順位逆転）と [9]（順位ではなく安定性に効く）は**矛盾ではなく、同じ量 R =（モデル間の広がり）/（ハーネス間の広がり）の逆側にいる**——[8] は R = 0.358、[9] は R = 3.5〜16.9。閾値 R ~ 1 はリファレンス 3 ケースすべてで予測と観測が一致する（`scripts/harness_regime.py --reference`）。**ただしタスク領域（SWE-bench 修正 vs 長期 AI 研究）と交絡しており因果は未分離**で、データ点も 2 つのため仮説にとどまる（`EVD-20261021-c38d` / `VER-20261021-ab99`：3/3 一致だが **warn**）。
>
> **RRSI の 2 項目を実装（2026-10-21）**：`scripts/holdout_eval.py`（過適合回避・hold-out/OOD 分離）と
> `scripts/prune_candidates.py`（低寄与コンポーネントの剪定）。いずれも**計測器で、ゲートではない**。
> 剪定は**報告のみで削除しない**——ゲートの削除は `main` の保証を変えるため人間の判断とする。
>
> **〔2026-10-21 訂正〕** 上記は**抄録要約だけを根拠にした暫定実装**であった。RRSI v3 の本文を
> 読了した結果（`contributions/2026-10-21_rrsi_reading.md`、PR #47）、両者は RRSI の
> **critic / selector / pruner とは別物**と判定された——原典の critic は**評価前に**候補 diff を読んで
> ベンチマーク固有の内容を篩にかける機構であり、pruner は**実測した score gain と policy-token
> コスト**で判定する。当方の 2 本は「一般化の懸念だけを借りたローカルの診断・構造インベントリ」
> である。**撤回・削除ではなく位置づけの訂正**であり、挙動は変えていない。
>
> **`rho` の実測（報告 §7 未解決 #1）**：`scripts/estimate_rho.py` を新設し、`gitswarm/readout_sim.py` の自由パラメータだった共通モード項 `rho` を実データから推定する経路を与えた。**結論は「既存データでは測れない」**——本リポジトリ唯一の反復ペア（Agora A/A'）は正解既知の共同判定項目が 8 件・誤り 0 件で識別不能。検出力解析では `rho=0.30` の検出に約 1,454 件を要し、**8 件は 2〜3 桁不足**する。測定法を「対誤り相関の計数」から「過程の直接計装」へ切り替える必要がある（`EVD-20261021-4c6f`）。
>
> **証拠の紐付け完了**：`scripts/check_memo_ledger_refs.py` の新設に伴い調べたところ、
> **47 件中 18 件の EVD がどのメモからも参照されていなかった**（`task/TASK.md` §3 は
> 「主張には必ず証拠と出典を紐付けること」を要求する）。全件を紐付け、**未参照 EVD は 0** になった。
>
> **2026-10-21 の追加（SHELDON 読解）**：arXiv:2610.18025「SHELDON: Reasoning through Dual Search over Hypothesis and Observation Spaces」を全文読解し（`contributions/2026-10-21_sheldon_reading.md`）、**仮説空間と観測空間を分離し、その間の証拠関係を 4 値（Support/Refute/Neutral/Unresolved）で型付けする**データモデルを抽出した。**本リポジトリの台帳に欠けていたのはまさにこの関係表**である——実測すると **54 件の EVD のうち 48 件（88.9%）がいずれの HYP とも紐づいていない**。「どの EVD がどの HYP を支持／反駁するか」は VER 経由の間接参照しかなく、台帳上は概念として存在しない。検出手順は決定論的 CI で実装可能だが、**verdict の付与は推論を要し、一度台帳に記録されれば再実行は決定的**になる。backfill 手順（後方互換）と採否はメモ §5・§7 を参照。書誌 1 件・EVD 5 件・VER 1 件・CLM 1 件を追加、**台帳は sources=12 / evidence=54 / claims=9 / verifications=30 / hypotheses=2。** <!-- drift-ok: 当時点のスナップショット -->

> **〔2026-10-21 追記〕** 上記 2 段落の台帳件数は**いずれもその時点のスナップショット**であり、
> 現在値ではない。**現在値は下記「現在の状態」節に機械検査対象として掲げる。**
> 本段落以降の差分は Stellar Colosseum 読解（PR #45）、RRSI 読解と Agentic Scientist 読解
> （PR #47）によるもので、同 PR マージ時点の EVD は **73** 件。
> その後、他セッションの PR #46 / #48 の取り込みで **81** 件になった（現在値は下記「現在の状態」節）。
>
> **マージ方針（2026-10-21 以降）**：**CI が緑の PR は、人間の承認を待たずに各セッションが `main` へマージしてよい。** 取り消しが安価なためである。破壊的操作（リモートブランチの削除、`--force` を伴う push、台帳レコードの削除、リポジトリ設定の変更）は**引き続き人間の明示的な承認を要する**。根拠・境界・前提は `docs/autonomous-merge-policy-2026-10-21.md`。

## 現在の状態（実測値・機械検査対象）

以下は**実測値**であり、`scripts/check_doc_numbers.py`（CI の 8 番目のゲート）が本文書の記述と
リポジトリからの再計算値を突き合わせて検査する。算出コマンドは下記「使い方」節。

- 台帳: sources=30 / evidence=100 / claims=9 / verifications=40 / hypotheses=7 / relations=255
- 仮説サイクル台帳（2026-10-21 新設）: search_log=11 / runs=3 / predictions=1
- 関係台帳の中身（`scripts/gap_scan.py` の実測・ゲート対象外）:
  unassessed **0 / 100 (0.0%)**、unexplained **29 / 100 (29.0%)**、unresolved のみ 0 件、
  provisional **70 / 100**（non-provisional 30 件）。
  `support` は**既定で `derived_from: true` を除外した REL 数**を数え、除外件数は
  `support_derived_from` として併記する。生成元からの支持しか無い観測は
  `unexplained` に残る。ただし旧 REL の支持 **85 件**にはフラグが無く、
  `gap_scan` はこれを false と同様に数える。**独立した出典85本を意味しない**。
  `self_support.py` は欠測を unknown とし、旧 `evidence_ids` との重なり 66 件を
  *生成元の証明ではない推定* として別枠に報告する（Phase 3 の詳細は
  `contributions/2026-10-21_phase3_round2.md`）。
- 観測キーの注釈: `state/evidence_keys.jsonl`（凍結ベース・空）＋`state/evidence_keys.d/*.jsonl` の **32 件**（旧30件＋S3の未説明観測2件）。新 EVD はレコードに直接キー7件を持つ。単一出典のキーは検索の種にはなるが独立再観測ではない
- 仮説の問いの注釈: `state/hypothesis_questions.jsonl`（凍結ベース・空）＋`state/hypothesis_questions.d/*.jsonl` の **7 件**（7 仮説・14 問い。分割前のレコード用）
- ラウンド3（`RUN-20261021-0f00`、Phase 4 の最初の1件）：新 SRC 3・EVD 3・REL 3（限定的support 1、neutral 2）・HYP 0。`unexplained` 27→29、refute 0のままsupport増で `cycle_readout.py` が停止を助言。**Phase 4 の3ラウンドDoDは未達、ラウンド4・5は未実行**（`contributions/2026-10-21_phase4_round3.md`）。独立二重選別・新RELの二重裁定は未実施。判断イベント率18/19は単位依存の参考値で、時間ベースの実質自動化率は未測定
- 統合レポート（[`contributions/2026-10-20_integrated_survey_report.md`](contributions/2026-10-20_integrated_survey_report.md)）を**第4版**に更新。DiscoveryRSI v1・DKGI v2 の対象課題と成績を、Naam の評論とともに既存の停止結果へ対照した（報告 §5.8）。研究台帳・停止判定・監査 ID 18 の凍結は変えていない
- テスト: 合計 616件（`tests/` の 24 ファイル。内訳は下記 §構成）
- CI ゲート: 8ゲート（`.github/workflows/core-check.yml` の `run:` を持つステップ数）
- 監査 ID 18: **凍結**（2026-10-21、人間の決定）。科学的には未解決のまま、ID 18 の解決を目的とした
  探索・追加抽出・モデル×ハーネス統制比較は割り当てない。正本は `docs/id18-freeze-2026-10-21.md`

台帳の件数は**凍結ベースとシャードの統合ビューのレコード数**である。既存の `state/*.jsonl` は
凍結ベースであり、2026-10-21 以降の追記先は `state/<台帳名>.d/<YYYY-MM-DD>-<12桁hex>.jsonl`。
旧パスは**全件一覧ではない**（履歴的な参照はそのまま解決する）。

**関係台帳（REL）は 2026-10-21 に投入された。** 初回投入は既存 2 仮説への裁定 172 行と
新仮説 4 件（`HYP-20261021-*`）への 63 行の計 235 行。その後、ID18 本文確認で追加された
新規 EVD 2 件へ 6 行を backfill した。2026-10-21 のラウンド1が 5 行、Phase 2 の前提整備が 1 行、ラウンド2が4行、ラウンド3が3行を追加し、現在は **255 行**である（`HYP-001` 13/0/67/11、
`HYP-002` 12/0/73/4。順に support/refute/neutral/unresolved）。記録上の `refute` は **0 件**だが、
「反駁が存在しない」という意味ではない。単独出典は `provisional` に留まり、対象の違う否定材料を refute に水増ししない（fail-closed）。判断の記録は
`contributions/2026-10-21_relation_backfill_integration.md` と
`contributions/2026-10-21_relation_backfill_id18_new_evidence.md` にある。

**なぜこの節を引用ブロック（`>`）で書かないか** —— ゲートは「`>` で始まる行」を**過去の
スナップショット**として数値検査から除外する。上の各段落で日付付きに述べた件数はその時点の
記録として正当だが、**現在の状態を述べる数値を `>` で書くと検査が効かなくなる。**
実際、上記の引用ブロック内に陳腐化した台帳件数が 7 件滞留していた（`>` を外して走査したときのみ
検出された。現況監査 ID 21。`docs/minimal-core-and-ci.md` §4 の「書式上の注意」と同じ事由）。
**したがって現況の数値は必ずこの節に追記する**こと。

ラウンド1終了時点の参考スナップショット（**現況ではない**。ゲートの検査対象外。算出方法は `contributions/2026-10-21_current-status-audit.md` §1.2 と
`scripts/gap_scan.py`）：出典 25 件のうち EVD を持たないものは 0 件。EVD 93 件のうち計上可能な support の
REL を持たないものは **25 件（26.9%）**。この 25 件は「書誌監査など仮説の対象外 6 件」「外部化しても
再現性が崩れた負の開示 3 件」「統制欠如・検出力不足による保留 12 件」「ラウンド1で予測設計の
基準線として取得し、意図的に未裁定のまま残した 1 件」「生成元からの支持しか持たない 2 件
（`EVD-20261021-539a` / `-970a`。`derived_from` を除外した結果、独立支持なしと数えられる）」
「ラウンド0の測定 `EVD-20261021-d88a`（neutral のみ）」に分かれ、独立した support を付けるべき観測ではない。
ID18 本文確認で追加された新規 EVD 2 件のうち、1 件は support、もう 1 件は
検出力不足のため unresolved と裁定した
（`contributions/2026-10-21_relation_backfill_id18_new_evidence.md`）。

## 構成

```text
task/                  研究課題定義（Long-Horizon Agent Architectures 文献調査）
schemas/               研究オブジェクトのスキーマ（source/evidence/claim/verification/hypothesis/
                       relation/search_log/run/prediction）
state/                 研究台帳。凍結ベース（state/*.jsonl）＋セッション別シャード
                       （state/<台帳名>.d/*.jsonl）の統合ビューとして読む（scripts/ledger_store.py。
                       追記はシャードへ。ベースは書き換えない）
                       evidence_keys.jsonl(+.d/) は EVD に observation_key を足す注釈
                       （既存キーは上書きしない。validate_state / gap_scan が同じ view を読む。
                       単独キーは次の検索の種であり、別 SRC の裏付けを作るものではない）
                       hypothesis_questions.jsonl(+.d/) は分割前の仮説に
                       next_literature_questions を足す注釈（レコードが既に持つ場合は
                       影にできない。validate_state と next_queries が同じ view を読む）
                       search_log/runs/predictions は仮説サイクルの記録（2026-10-21 新設・空で開始。
                       round / derived_from_evidence_ids / refutation_condition /
                       next_literature_questions を必須にする来歴ゲートは
                       docs/minimal-core-and-ci.md §2.5）。cycle_exemptions.json は
                       2026-10-21 以前のレコードを持つファイルの一覧（免除は ID ではなくファイル単位）
scripts/
  validate_state.py    研究台帳の決定論的検証器（標準ライブラリのみ）
  new_id.py            非連番レコードIDの採番器（並行作業のID衝突対策。統合ビューのIDと衝突確認）
  new_ledger_shard.py  台帳／書誌スナップショットのシャードファイルを作る（命名規則の強制）
  ledger_store.py      台帳とスナップショットの統合ビュー読み取り（凍結ベース＋シャード）
  ledger_digest.py     台帳レコードの内容ハッシュ（移行・revert の同一性証明。計測器）
  merge_ledgers.py     単一JSONLの3方向マージ道具（IDキーで和集合・競合は停止。手動修復用）
  check_citations.py   書誌のarXiv照合（オフラインfixture、--liveは手動専用）
  check_memo_citations.py 調査メモ内引用のarXiv照合（オフラインfixture、--liveは手動専用）
  check_ownership.py   並行作業の所有マップによるパス分類（助言専用・CI非接続）
  check_memo_ledger_refs.py メモ内の台帳ID・パス参照の存在検査（CI7番目のゲート）
  measure_agreement.py  2セッションの抽出結果の一致率と相関誤り（計測器・CI非接続）
  estimate_rho.py       相関誤りから共通モード項 rho を推定＋検出力解析（計測器）
  harness_regime.py     「ハーネスは順位を変えるか」を R = モデル間/ハーネス間の
                        広がり比で判定し、[8] と [9] の見かけの矛盾を両立させる
                        （計測器・閾値 R ~ 1、リファレンス3ケースで一致）
  check_doc_numbers.py  文書内の陳腐化した数値（テスト件数・ゲート数・台帳件数）を
                        実測値と突き合わせて検出する（**CI8番目のゲート**。
                        監査 ID 19。監査は ID 12 と ID 14 で同型の欠陥を
                        2 回とも手作業で見つけていた）
  sync_doc_counts.py    ゲート8が stale と報告した数値だけを機械的に同期する
                        （README と docs/minimal-core-and-ci.md の現在値の行）
  holdout_eval.py       検査器を dev / hold-out 分割で評価し、過適合を検出する
                        （計測器。RRSI の hold-out/OOD 分離の実装）
  prune_candidates.py   低寄与コンポーネントを報告する（計測器。**何も削除しない**。
                        RRSI の剪定の実装。削除は人間の判断）
  gap_scan.py           関係台帳（REL）から仮説カバレッジの穴を報告する
                        （計測器・CI非接続。unassessed / unexplained /
                        仮説別 verdict / 領域別の未評価件数。provisional は
                        fail-closed で、独立出典の再遭遇が無い反駁は数えない）
  next_queries.py       S0/S7 のクエリ計画。next_literature_questions（無ければ
                        hypothesis_questions overlay）を決定的にクエリへ変換し、
                        gap_scan の unresolved / unexplained で重み付けする
                        （計測器・CI非接続。台帳は読むだけ。計画は提案）
  hypothesis_questions.py 分割前の仮説のための問い overlay の読み込みと検査
                        （既知の仮説のみ・レコードの問いを影にしない）
  self_support.py       support REL の自己生成元フラグを数える計測器（欠測は
                        unknown。旧 evidence_ids との重なりは別の proxy）
  relation_agreement.py S4 の二つの判定ファイルを仮説×観測で突き合わせる計測器
                        （一致率・κ・旧 support 残存率。独立性・正解は保証しない）
  cycle_readout.py      S8 のRUNスナップショットから停止警告を判定する非ゲート計測器
                        （欠測を0と推測しない。停止でも終了コード0）
gitswarm/
  problem.py solvers/  30都市TSPの決定論的ソルバ群（greedy/random/two_opt/SA）
  benchmarks/          複数シード実行＋成果物照合（--write/--check）
  readout.py           GitSwarm readout解析器（履歴が貯まれば使う道具）
  readout_sim.py       同質ワーカーの多数決＝共通モード障害の決定論的測定（--write/--check）
  artifacts/           実行で再生成できる成果物（ベンチマーク行列・投票スイープ行列）
tests/
  fixtures/            arXiv書誌スナップショット（オフライン照合用・2026-10-20取得。
                       凍結ベース＋arxiv_metadata_snapshot.d/ の追加パーツ）
  test_minimal_core.py         履歴非依存の回帰テスト（34件）
  test_check_citations.py      書誌照合テスト（17件・ネットワーク非依存）
  test_check_memo_citations.py 調査メモ内引用の照合テスト（33件）
  test_merge_ledgers.py        JSONL三者マージの合成テスト（13件）
  test_score_extraction.py     単一対並行の抽出採点テスト（10件）
  test_measure_agreement.py    並列セッション間一致度の測定テスト（25件）
  test_ownership.py            所有マップによるパス分類テスト（17件）
  test_readout_sim.py          共通モード障害シミュレータの回帰テスト（20件）
  test_check_memo_ledger_refs.py メモ内ID・パス参照の検査テスト（12件）
  test_estimate_rho.py         rho 推定器の回帰テスト（13件）
  test_harness_regime.py       R の単位変換と閾値判定の回帰テスト（14件）
  test_check_doc_numbers.py    文書内の陳腐化した数値の検査テスト（21件）
  test_holdout_eval.py         hold-out 分割と過適合判定のテスト（18件）
  test_prune_candidates.py     低寄与コンポーネント報告のテスト（19件）
  test_relations.py            関係台帳（REL）の検査・採番・メモ参照解決のテスト（37件）
  test_gap_scan.py             仮説カバレッジの穴（unassessed / unexplained / provisional ゲート）の報告テスト（56件）
  test_ledger_shards.py        台帳シャード（凍結ベース＋サイドカー）の読取・件数・参照整合性（39件）
  test_new_ledger_shard.py     シャード作成道具（命名規則・作成・警告）のテスト（16件）
  test_sync_doc_counts.py      文書内数値の機械同期のテスト（16件）
  test_evidence_keys.py        observation_key 注釈（overlay）の付与・非上書き・重複検出・gap_scan 連携のテスト（17件）
  test_cycle_records.py        仮説サイクルの記録（QRY/RUN/PRD）と3つの来歴ゲートのテスト（57件）
  test_next_queries.py         S0/S7 のクエリ生成・重み付け・検索ログとの重複判定・質問 overlay のテスト（55件）
  test_phase3_instruments.py  自己支持（欠測区別）・裁定一致率の計測器（39件）
  test_cycle_readout.py       S8 の停止警告・欠測・イベント率の非ゲートテスト（18件）
                               ── 合計 616件
contributions/         研究ノート（統合レポート・調査メモ・全文読解レポート・共通モード測定）
docs/                  分析レポートと設計記録（並行作業の所有マップは docs/parallel-work-ownership.md。強制力なし）
.github/workflows/
  core-check.yml       最小CI（全8ゲート：テスト・ベンチマーク再現性・投票シミュレーション
                       再現性・台帳検証・書誌照合・メモ引用照合・メモ内ID参照・文書内数値）
```

## 使い方

```sh
# 1. テスト（約5秒・616件）
python3 -m unittest discover -s tests -v

# 2. ベンチマークの再現性確認（fresh実行と成果物の照合）
python3 gitswarm/benchmarks/benchmark.py --check

# 3. 共通モード障害の測定の再現性確認（fresh実行と成果物の照合）
python3 gitswarm/readout_sim.py --check

# 4. 研究台帳の検証
python3 scripts/validate_state.py

# 5. 書誌のarXiv照合（オフラインfixtureのみ。ネットワーク不要）
python3 scripts/check_citations.py

# 6. 調査メモ内引用のarXiv照合（オフラインfixtureのみ。CIゲート対象）
python3 scripts/check_memo_citations.py

# 成果物の再生成（実行できることの証明。数値は不変のはず）
python3 gitswarm/benchmarks/benchmark.py --write
python3 gitswarm/readout_sim.py --write

# 次の検索計画（S0/S7 の計測器。CI ゲートではない）
python3 scripts/next_queries.py            # 優先度順の計画
python3 scripts/next_queries.py --json     # 機械可読（queries / already_searched / skipped）
python3 scripts/self_support.py --json     # 明示フラグ内の自己支持率＋欠測・推定を分ける
python3 scripts/relation_agreement.py --a contributions/2026-10-21_round2_adjudication_A.json \
  --b contributions/2026-10-21_round2_adjudication_B.json --json  # 再裁定の一致（独立性は保証しない）
python3 scripts/cycle_readout.py --json    # S8 の警告。stopでも終了コード0、CIゲートではない

# 台帳に追記するとき（凍結ベースは書き換えない。docs/record-id-scheme.md §2）
python3 scripts/new_ledger_shard.py evidence --create   # シャードのパスを作る
python3 scripts/new_id.py EVD                          # IDを採番する
python3 scripts/sync_doc_counts.py                     # 件数の数値行を実測へ同期する
```

CI（`core-check.yml`）は上記1〜6に加え、**7. メモ内の台帳ID・パス参照の存在検査**と
**8. 文書内の陳腐化した数値の検査**をゲートする。Python 3.12固定。

## 意図的に含まれないもの（ガバナンス凍結）

役割分離・追記専用台帳・レビューキュー・コミットtrailer検査・landゲートは含まない。これらは形式的完全性を追求する過程で進捗を止めたため、凍結中である（記録は `arena/*` ブランチに残る）。凍結の解除には「DoDを3行以内で先に書く」ことが条件。詳細は `docs/minimal-core-and-ci.md` §1.2。

## 次の段階（設計思想レポートのPhase順序に従う）

1. 単一Workerのベースライン：`task/TASK.md` の文献調査を人間が読める短いレポートとして完成させる ✅ 完了（2026-10-20：`contributions/2026-10-20_integrated_survey_report.md`。`task/TASK.md` §4 の Integrator 統合レポート。§2 の目的1〜3を証拠の強弱4段階で論証）
2. 捏造対策は1点に絞る：arXiv APIによる引用の機械照合 ✅ 完了（2026-10-20：`scripts/check_citations.py`。オフラインfixture照合をCIでゲート、実API照合 `--live` は手動専用）
3. 共通モード障害の直接測定 ✅ 一部完了（2026-10-20：`gitswarm/readout_sim.py`。決定論的投票モデルで増幅の条件を測定。**ただしワーカーはモデル上の標本であり、実 LLM ワーカー群の追従率 `rho` と共有見解の正しさ `c` は未測定**。測定の限界は `contributions/2026-10-20_common_mode_measurement.md` §6）
4. その後、必要性が実証されたときに複数Worker・Supervisor・検証の拡張を検討する（Phase 4は最後）
