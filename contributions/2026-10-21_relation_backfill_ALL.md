# 既存 EVD 86件の H×O 関係裁定バックフィル（R3・シャード `ALL`）

- 作成日: 2026-10-21
- 役割: 証拠裁定ワーカー（R3・全シャード統合バックフィル `ALL`）
- 基準コミット (`base_commit`): `91a08f4321d4aee42bca6cb02641b7c32dce4539`（開始時 `ccf76aa654c1344e7bc7862bc835cf1420c98ff8` から `origin/main` へ Fast-forward 同期；両コミット間で `state/` の全レコード不変を確認済み）
- 生成成果物（`state/` 無変更・以下2ファイルのみ新規作成）:
  - `contributions/2026-10-21_relation_backfill_ALL.json`（全86 EVD・計235判定行・新仮説候補4件）
  - `contributions/2026-10-21_relation_backfill_ALL.md`（本裁定メモ）

---

## 1. シャード `ALL` 選定の経緯と担当範囲

起動プロンプト内のシャード記号・担当範囲プレースホルダが未置換であったため、ユーザーへ確認のうえリポジトリ内の設計・割当資料を精査した。

1. `docs/worker-prompts-next-stage-2026-10-21.md`（施策 R3 割当表）にて、全23ソース・86 EVD が R3-A（18件）・R3-B（21件）・R3-C（18件）・R3-D（14件）・R3-E（15件）の5シャード（合計86件）に分割されていることを確認した。
2. `git fetch origin` および `gh pr list --state all` により全ブランチ・全PRを確認したところ、R1（PR #51: `schemas/relation.json` と空の `state/relations.jsonl`）および R2（PR #56: `scripts/gap_scan.py`）は `main` にマージ済みである一方、R3 の作業ブランチ・PR・候補ファイルはいずれのシャードも **0件（未着手）** であった。
3. 特定1シャードのみを任意抽出すると残り65〜72件の EVD が未裁定のまま残るため、シャード識別子を **`ALL`** とし、**R3-A〜R3-E の全23ソース・全86 EVD を一括網羅**した（R4 統合ワーカーは一括取込もシャード単位の分割検証もそのまま実行可能である）。

### シャード別・ソース別の処理件数内訳

| シャード | テーマ（`docs/worker-prompts-next-stage-2026-10-21.md`） | 対象 `source_id` | ソース数 | EVD 件数 | 既存HYPで説明済 (`support`) | 新仮説4件を含め説明済 (`support`) |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| **A** | 自律研究システム（初期4本） | `SRC-001`(4), `SRC-002`(6), `SRC-003`(5), `SRC-004`(3) | 4 | 18 | 8 | 11 |
| **B** | 自律研究システム（続編） | `SRC-20261020-f295`(11), `SRC-20261020-05de`(3), `SRC-20261020-787b`(3), `SRC-20261020-303f`(4) | 4 | 21 | 6 | 9 |
| **C** | ハーネスと評価 | `SRC-20261020-875e`(3), `SRC-20261020-07a3`(4), `SRC-20261020-4cff`(3), `SRC-20261021-065a`(2), `SRC-20261021-fb4a`(1), `SRC-20261021-9a02`(1), `SRC-20261021-f186`(1), `SRC-20261021-a714`(1), `SRC-20261021-7176`(1), `SRC-20261021-4172`(1) | 10 | 18 | **0** | 17 |
| **D** | 直近読解（その1） | `SRC-20261021-a3a2`(8), `SRC-20261021-2b88`(6) | 2 | 14 | 4 | 14 |
| **E** | 直近読解（その2） | `SRC-20261021-2384`(5), `SRC-20261021-7419`(5), `SRC-20261021-8452`(5) | 3 | 15 | 5 | 15 |
| **合計 (`ALL`)** | **全領域網羅** | **全23件** | **23** | **86** | **23 (26.7%)** | **66 (76.7%)** |

---

## 2. 裁定の全体集計と `scripts/gap_scan.py` ドライラン実測値

全86件の EVD すべてに対し、既存2仮説（`HYP-001`, `HYP-002`）への完全直積判定（`86 × 2 = 172` 行）に加え、新仮説候補4件（`NEW-ALL1`〜`NEW-ALL4`）に関連する63行を付与し、**合計 235 行**を `contributions/2026-10-21_relation_backfill_ALL.json` に記録した。すべての判定行について `(source_id, excerpt)` 固有部分文字列との機械照合アサートを通過させ、ID 取り違えが 0 件であることを保証した。

### 仮説別の `proposed_verdict` 集計

| 仮説ID / 仮ラベル | `support` | `refute` | `neutral` | `unresolved` | 行数計 | 備考 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `HYP-001` | 12 | 4 | 63 | 7 | 86 | 全86 EVD を網羅。`refute` 4件はいずれも `SRC-20261020-f295` 単独由来のため `scripts/gap_scan.py` 上は `provisional` により抑止 |
| `HYP-002` | 11 | 0 | 71 | 4 | 86 | 全86 EVD を網羅。多数決の誤り増幅・独立性喪失・構成的集約対照を網羅 |
| `NEW-ALL1` | 16 | 0 | 0 | 1 | 17 | モデル×ハーネス結合支配と近接能力領域での順位逆転（`unresolved` 1件は信頼区間が0を跨ぐ `EVD-20261021-d78f`） |
| `NEW-ALL2` | 25 | 0 | 0 | 0 | 25 | 密な検証ゲート・事前リーク審査・ノイズ幅正則化による報酬ハッキング抑止 |
| `NEW-ALL3` | 12 | 0 | 0 | 0 | 12 | 仮説生成枯渇に対する双空間 H×O 管理・反証記録保持の有効性 |
| `NEW-ALL4` | 8 | 0 | 0 | 1 | 9 | 長文生成・履歴肥大の限界に対する文脈剪定・要約・DAG分解（`unresolved` 1件は1ワークフロー限定の `EVD-20261021-baef`） |
| **合計** | **84** | **4** | **134** | **13** | **235** | 全86 EVD が最低2行（既存2仮説）＋該当新仮説行を保持 |

### `/tmp` 一時ディレクトリ上での `scripts/gap_scan.py` & `scripts/validate_state.py` ドライラン推移

リポジトリ内の `state/` には一切触れず、`/tmp` 上の一時コピーに対して候補 JSON を投影し、`validate_state.run_all_checks()`（3モードすべてで `errors = []` を確認）および `scripts/gap_scan.py` を実行した実測推移は以下の通りである。

| 検証モード | `relations` | `hypotheses` | `provisional` / `non_provisional` | `unassessed` | `unexplained` |
| --- | ---: | ---: | --- | --- | --- |
| 0. 現行 `state/` ベースライン | 0 | 2 | `86 / 0` | `86 / 86 (100.0%)` | `86 / 86 (100.0%)` |
| 1. 既存2仮説のみ投影（172行） | 172 | 2 | `86 / 0` | `0 / 86 (0.0%)` | `63 / 86 (73.3%)` |
| 2. 既存2仮説＋異ソース安全 `observation_key`（7組31件） | 172 | 2 | `55 / 31` | `0 / 86 (0.0%)` | `63 / 86 (73.3%)` |
| 3. 新仮説4件（`NEW-ALL1`〜`NEW-ALL4`）追加投影（235行） | 235 | 6 | `55 / 31` | `0 / 86 (0.0%)` | **`20 / 86 (23.3%)`** |

モード3で最終的に `unexplained` として残る **20件** は、無理に `support` へ押し込んではならない健全な3カテゴリのみで構成されている：
1. **書誌監査・引用転写訂正・コーパス記述レコード（6件）**: `EVD-007`, `EVD-009`, `EVD-010`, `EVD-011`, `EVD-20261020-f880`, `EVD-20261021-088c`
2. **外部化状態を持ちながら再現性・索引整合が崩れた Agora 負の開示（3件・`HYP-001` 暫定 `refute`）**: `EVD-20261020-bea0`, `EVD-20261020-78b6`, `EVD-20261020-80cf`（※もう1件の暫定 `refute` である `EVD-20261020-137b` は5日間集中停滞の観測として `HYP-002` を `support` するため説明済みに分類される）
3. **統制対照欠如・検出力不足・一般化留保を明記した保留レコード（11件・`unresolved`）**: `EVD-20261020-72ee`, `EVD-20261020-e4a7`, `EVD-20261020-ba70`, `EVD-20261020-221a`, `EVD-20261020-2609`, `EVD-20261020-2336`, `EVD-20261020-d515`, `EVD-20261020-3554`, `EVD-20261021-baef`, `EVD-20261021-4c6f`, `EVD-20261021-d78f`

---

## 3. 既存仮説（`HYP-001`, `HYP-002`）に対する裁定の要点

### 3.1 `HYP-001`（外部化された構造化メモリによる累積探索効率・再現性の向上）
- **`support`（12件）**: `EVD-001`, `EVD-002`, `EVD-008`, `EVD-20261021-66d4`, `EVD-20261021-45e2`, `EVD-20261021-8fa6`, `EVD-20261021-7cdb`, `EVD-20261021-572c`, `EVD-20261021-ea49`, `EVD-20261021-6094`, `EVD-20261021-71a3`, `EVD-20261021-05ed`
  - SLA の役割別文脈再構成（`EVD-001`）、GitSwarm の継承グラフ・負コミット参照（`EVD-002`, `EVD-008`）、Context Engineering / Less Context における全文脈保持に対する構造化要約状態の大幅優位（`EVD-20261021-66d4`, `EVD-20261021-45e2`, `EVD-20261021-8fa6`）、SHELDON の H×O 関係状態・共有観測空間アブレーション（`EVD-20261021-7cdb`, `EVD-20261021-572c`）、Stellar Colosseum の依存 DAG 分解・局所再試行（`EVD-20261021-ea49`）、RRSI の原子的編集信用割当履歴（`EVD-20261021-71a3`）、Agentic Scientist の構造化アイデア束・append-only 変種探索（`EVD-20261021-6094`, `EVD-20261021-05ed`）が支持する。
- **`refute`（4件・すべて `provisional`）**: `EVD-20261020-bea0`, `EVD-20261020-137b`, `EVD-20261020-78b6`, `EVD-20261020-80cf`
  - Agora v4（`SRC-20261020-f295`）は Git/索引による外部化状態を持ちながら、(1) 未投稿の再現試行が痕跡を残さない（`EVD-20261020-bea0`）、(2) 5日間停滞後に台帳未記録の人間手動介入3回を要した（`EVD-20261020-137b`）、(3) コミット先行書き込みにより Git 履歴と索引が45コミット乖離した（`EVD-20261020-78b6`）、(4) 評価器ログ・プロンプト・依存関係版固定が全欠落し独立再現不能である（`EVD-20261020-80cf`）という具体的反例を開示している。これらは「版固定・失敗試行記録・索引整合検証を伴わない素朴な外部化ストアだけでは再現性は保証されない」という重要な境界条件を示す（単一ソース由来につき `scripts/gap_scan.py` では `provisional` として自動抑止）。
- **`unresolved`（7件）**: `EVD-20261020-72ee`, `EVD-20261020-e4a7`, `EVD-20261020-ba70`, `EVD-20261020-221a`, `EVD-20261020-d515`, `EVD-20261020-3554`, `EVD-20261021-baef`
  - n=1 走行・計算コスト未統制（`EVD-20261020-72ee`）、貢献グラフ再利用からの因果未分離（`EVD-20261020-e4a7`）、対照群欠如・勝者未再実行・異機材閾値超過（`EVD-20261020-ba70`, `EVD-20261020-221a`, `EVD-20261020-d515`, `EVD-20261020-3554`）、単一業務ワークフローへの限定留保（`EVD-20261021-baef`）は推測で `support` に寄せずすべて `unresolved` とした。

### 3.2 `HYP-002`（同質ワーカー多数決ノミネーションの共通モード障害への脆弱性）
- **`support`（11件）**: `EVD-003`, `EVD-004`, `EVD-20261020-0641`, `EVD-20261020-ffec`, `EVD-20261020-932f`, `EVD-20261020-40dc`, `EVD-20261020-137b`, `EVD-20261020-aa81`, `EVD-20261021-59ab`, `EVD-20261021-5d88`, `EVD-20261021-cd59`
  - GitSwarm における検証可能課題でのノミネーション意図的除去（`EVD-003`, `EVD-20261020-932f`）と「ノミネーションは選好・協調信号であって正しさの独立検証ではない」という明記（`EVD-20261020-0641`）、決定論的投票モデルによる誤り増幅の定量実証（`EVD-20261020-ffec`）、DuoDiscover の代理指標ドリフト監視（`EVD-004`）、Agora での隣接コンテナプロセス覗き見による独立性喪失（`EVD-20261020-40dc`）および5日間集中停滞（`EVD-20261020-137b`）、Horizon Gap の共有評価前提バイアス（`EVD-20261020-aa81`）、SHELDON の単発誤判定への `Provisional` 保護（`EVD-20261021-59ab`）、Stellar Colosseum の「多数決ではなく致命的欠陥1つで棄却・反証束を構成的統合」（`EVD-20261021-5d88`, `EVD-20261021-cd59`）が支持する。
- **`unresolved`（4件）**: `EVD-011`, `EVD-20261020-2609`, `EVD-20261020-2336`, `EVD-20261021-4c6f`
  - 原典に旧引用文言が存在しないことを確認した監査記録（`EVD-011`）、クラスタ閾値 0.80 設定に依存する集中診断（`EVD-20261020-2609`）、共有親の再実行と区別できない同一スコア収束（`EVD-20261020-2336`）、および n=8 誤り0件につき誤り相関 $ho$ が識別不能であった実測（`EVD-20261021-4c6f`）を `unresolved` に留保した。

---

## 4. 迷った判断・境界事例の記録

1. **`VER` の `result=fail` を `refute` に混同しない原則の徹底**:
   - `state/verifications.jsonl` 全34件のうち `result="fail"` は `VER-006`（対象 `SRC-001`）、`VER-010`（対象 `SRC-003`）、`VER-011`（対象 `EVD-004`）、`VER-015`（対象 `EVD-001`）、`VER-20261020-4843`（対象 `EVD-20261020-932f`）の5件である。
   - これらはいずれも著者名メタデータや監査前抜粋文言・二次要約の転写誤りを検出した記録であり（対応する訂正記録が `EVD-007`, `EVD-009`, `EVD-010`, `EVD-011`, `EVD-20261020-932f`）、`contributions/2026-10-21_sheldon_reading.md` §5.4 の規則どおり **仮説への `refute` とは一切みなさなかった**。
2. **歴史的リンク `EVD-011` → `HYP-002` の再裁定（`support` から `unresolved` への変更）**:
   - `state/hypotheses.jsonl` の `HYP-002.evidence_ids` には歴史的経緯で `EVD-011` が含まれているが、`EVD-011` の抜粋本文は「監査前の `EVD-004` 引用文言が原典に存在しない」という書誌監査事実であり、それ自体は `HYP-002` を支持する実験証拠ではないため、惰性で `support` にせず `unresolved` と判定した。
3. **原典読解メモを開いて実験前提を確認した行における `basis: "memo:<ファイル名>"` の明示**:
   - 原則として EVD の `excerpt` のみで判定しつつ、対照群の有無や付録条件の確認に原典読解メモを参照した箇所には `basis` を明記した：
  - `memo:2026-10-20_sla_fulltext_reading.md`（実体: `contributions/2026-10-20_sla_fulltext_reading.md`）: `EVD-001`, `EVD-20261020-72ee`
  - `memo:2026-10-20_git_swarm_fulltext_reading.md`（実体: `contributions/2026-10-20_git_swarm_fulltext_reading.md`）: `EVD-002`, `EVD-003`, `EVD-20261020-0641`, `EVD-20261020-e4a7`, `EVD-20261020-ffec`, `EVD-20261020-932f`
  - `memo:2026-10-20_agora_integrated_reading.md`（実体: `contributions/2026-10-20_agora_integrated_reading.md`）: `EVD-20261020-ba70`, `EVD-20261020-40dc`, `EVD-20261020-137b`, `EVD-20261020-2609`, `EVD-20261020-2336`, `EVD-20261020-d515`, `EVD-20261020-3554`
  - `memo:2026-10-21_id18_paper_search.md`（実体: `contributions/2026-10-21_id18_paper_search.md`）: `EVD-20261021-c38d`, `EVD-20261021-d78f`
  - `memo:2026-10-21_stellar_colosseum_reading.md`（実体: `contributions/2026-10-21_stellar_colosseum_reading.md`）: `EVD-20261021-5d88`
4. **同一原典の重複登録（`SRC-20261021-7419` と `SRC-20261021-8452`）と `observation_key_proposal` の安全分離**:
   - シャード E の `SRC-20261021-7419`（OpenReview 版）と `SRC-20261021-8452`（arXiv 版）は同一論文 *The Agentic Scientist* の重複登録であり、`EVD-20261021-6094` と `EVD-20261021-05ed`、および `EVD-20261021-a1fa` と `EVD-20261021-a6fd`（逐語一致）が重複している。
   - `scripts/gap_scan.py` の `derive_provisional_map()` は、同一 `observation_key` を持つ異なる `source_id` が2件以上あると独立再現とみなして `provisional=False` に昇格させる。したがってソース統合前にそのまま共通キーを付与すると偽の独立再現が生じるため、`DUP_SAME_PAPER:` 接頭辞で明確に区別して R4 統合ワーカーへ申し送った。

### 提案した `observation_key_proposal` 一覧（独立異ソース7組31件 ＋ 重複注意2組4件）

| 区分 | `observation_key_proposal` | 対象 `evidence_id` | 束ねる同一所見の内容 |
| --- | --- | --- | --- |
| 独立異ソース（安全・4ソース） | `externalized_structured_state_enables_compounding_iteration` | `EVD-001`, `EVD-002`, `EVD-20261021-ea49`, `EVD-20261021-71a3` | 会話履歴の持ち越しを避け、Git・DAG・原子的編集履歴として外部構造化することで反復蓄積を可能にする |
| 独立異ソース（安全・3ソース） | `plurality_voting_unvalidated_or_vulnerable_without_verifier` | `EVD-003`, `EVD-20261020-0641`, `EVD-20261020-ffec`, `EVD-20261021-5d88` | 客観検証器なしの多数決・ノミネーションは正しさの独立証明にならず誤り増幅に脆弱である |
| 独立異ソース（安全・4ソース） | `verifier_fidelity_and_pre_evaluation_leakage_guard` | `EVD-004`, `EVD-20261021-f7f8`, `EVD-20261021-5b0d`, `EVD-20261021-e31f` | 代理指標ドリフト・diffリーク・評価手順書き換えを防ぐ事前ゲートと独立最終評価の必要性 |
| 独立異ソース（安全・3ソース） | `preserving_negative_and_falsification_records_guides_search` | `EVD-008`, `EVD-20261021-59ab`, `EVD-20261021-cd59`, `EVD-20261021-30ed` | 負の結果・反証記録束・Provisional保留を捨てずに引き継ぐことによる探索誘導と誤棄却防止 |
| 独立異ソース（安全・3ソース） | `hypothesis_exhaustion_in_long_horizon_research` | `EVD-20261020-b733`, `EVD-20261021-7dd6`, `EVD-20261021-6ec4` | 長期自律研究における仮説生成の枯渇と未説明観測駆動探索の必要性 |
| 独立異ソース（安全・2ソース） | `context_pruning_and_summarization_over_full_history` | `EVD-20261021-bbb8`, `EVD-20261021-45e2`, `EVD-20261021-8fa6` | 長文生成・全文脈維持の限界に対する直近ウィンドウ剪定＋構造化要約の優位性 |
| 独立異ソース（安全・7ソース） | `model_harness_joint_dominance_and_rank_inversion` | `EVD-20261021-3d5a`, `EVD-20261021-cdf7`, `EVD-20261021-48c6`, `EVD-20261021-c38d`, `EVD-20261021-c1a2`, `EVD-20261021-e06c`, `EVD-20261021-589c`, `EVD-20261021-1026`, `EVD-20261021-887d` | モデル固定下の足場変更による大幅変動と近接能力領域（R < 1）でのモデル順位逆転 |
| **同一原典重複注意** | `DUP_SAME_PAPER:agentic_scientist_dual_rubric_and_score_gate` | `EVD-20261021-6094`, `EVD-20261021-05ed` | Agentic Scientist（`SRC-20261021-7419` / `SRC-20261021-8452`）のルーブリック完了・最高スコア更新二重ゲート（ソース統合前は `state/` へそのまま書かないこと） |
| **同一原典重複注意** | `DUP_SAME_PAPER:agentic_scientist_frozen_posthoc_diagnostics` | `EVD-20261021-a1fa`, `EVD-20261021-a6fd` | Agentic Scientist（`SRC-20261021-7419` / `SRC-20261021-8452`）の凍結post-hoc診断パイプライン（逐語重複ペア） |

---

## 5. 新仮説候補（`NEW-ALL1`〜`NEW-ALL4`）の説明

既存2仮説では説明できなかった 63 件の EVD（特にシャード C 18件中18件、シャード D 14件中10件、シャード E 15件中10件）を構造的に統合するため、以下の **4本の新仮説候補** を起草した（仮ラベルであり台帳 ID ではない）。

### `NEW-ALL1`: モデル×ハーネス結合支配と近接能力領域での順位逆転
- **主張文 (`statement`)**: エージェント課題の到達性能はモデル単体ではなく『モデル×ハーネス（足場・環境・検査ループ）』の結合系で決まり、モデル間能力差に対するハーネス効果比（R = Δmodel / Δharness）が1未満となる近接能力モデル間ではハーネス変更による順位逆転が生じる一方、能力差が大きい領域（R > 1）ではハーネスは主に走行間安定性に効きモデル順位は保存される。
- **支持 EVD（16件）**: `EVD-20261020-aa81`, `EVD-20261020-4c61`, `EVD-20261021-3d5a`, `EVD-20261021-cdf7`, `EVD-20261021-48c6`, `EVD-20261021-8319`, `EVD-20261021-1564`, `EVD-20261021-7dd6`, `EVD-20261021-c38d`, `EVD-20261021-c1a2`, `EVD-20261021-43a0`, `EVD-20261021-e06c`, `EVD-20261021-589c`, `EVD-20261021-1026`, `EVD-20261021-887d`, `EVD-20261021-c029`（保留 `unresolved` 1件: `EVD-20261021-d78f`）
- **反証条件 (`falsification`)**: 同一ベンチマーク・同一トークン／計算予算下で、近接能力モデル群（R < 1）に対し複数ハーネスを直交交差させた実験でハーネス変更による順位逆転が有意に生じない場合、または大差領域（R > 1.5）でも軽微な足場変更のみで頻繁にモデル順位が逆転する場合に棄却される。
- **次に集めるべき観測 (`next_observations`)**: 3水準以上のモデル群×3種以上のハーネス構成の直交要因実験における通過率分散分解（モデル主効果・ハーネス主効果・交互作用・残差）と効果比Rの第3の独立ベンチマークでの実測値。

### `NEW-ALL2`: 密な検証ゲート・事前リーク審査・ノイズ幅正則化による報酬ハッキング抑止
- **主張文 (`statement`)**: 長期自律探索において評価指標ハッキング・過適合・偽の改善を防ぎ実世界／分布外（OOD）汎化利得を得るには、最終スコア単独の選抜ではなく、(1) 探索評価と最終評価の分離・忠実度再検査・フル評価前のdiffリーク／評価改変審査、および (2) 基底評価ノイズ幅δ・複雑度ペナルティ・非生産的要素の構造剪定を組み込んだ段階ゲート付受容規則が必要である。
- **支持 EVD（25件）**: `EVD-004`, `EVD-20261020-0766`, `EVD-20261020-4c61`, `EVD-20261021-c1b4`, `EVD-20261021-d833`, `EVD-20261021-2aad`, `EVD-20261021-a8af`, `EVD-20261021-12a7`, `EVD-20261021-5d88`, `EVD-20261021-f7f8`, `EVD-20261021-6094`, `EVD-20261021-f75d`, `EVD-20261021-a1fa`, `EVD-20261021-9959`, `EVD-20261021-13f8`, `EVD-20261021-5b0d`, `EVD-20261021-6347`, `EVD-20261021-b089`, `EVD-20261021-de29`, `EVD-20261021-0417`, `EVD-20261021-6951`, `EVD-20261021-05ed`, `EVD-20261021-a6fd`, `EVD-20261021-e31f`, `EVD-20261021-5607`
- **反証条件 (`falsification`)**: 事前リーク／評価改変審査またはノイズ幅δ・複雑度正則化のいずれかを欠いた探索系であっても、長期反復後に凍結ホールドアウト（OOD）評価面でテスト改変・過適合・トークン肥大を起こさず完備系と同等以上のOOD利得を維持できることが複数課題で確認された場合に棄却される。
- **次に集めるべき観測 (`next_observations`)**: 事前diffリーク・評価手順整合ゲートとノイズ幅δ正則化を個別に外した統制アブレーションにおける、探索スコア対凍結OODスコアの乖離率および評価プロトコル改変発生率の時系列測定。

### `NEW-ALL3`: 仮説生成枯渇に対する双空間 H×O 管理・反証記録保持の有効性
- **主張文 (`statement`)**: 長期自律研究では運用作業や原稿執筆にトークンが偏り仮説生成・方法論的新規性が枯渇しやすいが、仮説空間（H）と観測空間（O）を明示的に分離し、(1) 負の結果・反証記録を捨てずに候補や履歴と束ねて引き継ぎ、(2) 単発観測をProvisionalとして尚早な仮説棄却を抑止しつつ、(3) 未説明観測と手薄な軸へ探索を誘導することで発見性能が有意に向上する。
- **支持 EVD（12件）**: `EVD-008`, `EVD-20261020-b733`, `EVD-20261021-7dd6`, `EVD-20261021-7cdb`, `EVD-20261021-4ad6`, `EVD-20261021-59ab`, `EVD-20261021-6ec4`, `EVD-20261021-572c`, `EVD-20261021-cd59`, `EVD-20261021-30ed`, `EVD-20261021-71a3`, `EVD-20261021-2804`
- **反証条件 (`falsification`)**: 同一文献・計算予算下で、H×O双空間台帳（未説明観測スキャン・反証束保持・Provisional保護付き）を持つエージェントと単一バックログ駆動エージェントを比較し、後半ラウンドでの非重複新規仮説率・未説明観測解消率・誤棄却率に改善が見られない場合に棄却される。
- **次に集めるべき観測 (`next_observations`)**: ResearchOS上でgap_scan.py運用前後のラウンドにおけるunassessed(o)・unexplained(o)比率の推移、新規起草仮説の重複率、およびprovisional反駁に対する独立追試実施率の計測。

### `NEW-ALL4`: 長文生成・履歴肥大の限界に対する積極的コンテキスト剪定・要約・DAG分解の優位性
- **主張文 (`statement`)**: 現行LLMエージェントは複雑な文脈理解に比べて長文出力生成および肥大化した会話履歴の維持に顕著な限界を持つため、全履歴の持ち越しや一括長文生成よりも、役割別の新鮮な文脈再構成・直近ウィンドウ剪定＋自動要約・依存DAGによる局所サブ問題分解を行う方が、低トークンコストで高い完遂率を達成する。
- **支持 EVD（8件）**: `EVD-001`, `EVD-20261020-e9fb`, `EVD-20261020-04b2`, `EVD-20261021-66d4`, `EVD-20261021-bbb8`, `EVD-20261021-45e2`, `EVD-20261021-8fa6`, `EVD-20261021-ea49`（保留 `unresolved` 1件: `EVD-20261021-baef`）
- **反証条件 (`falsification`)**: 多段階の研究・証明・業務ツールワークフローにおいて、全文脈保持＋一括生成と、直近剪定＋構造化要約＋DAG局所分解を同一モデルで統制比較し、後者がトークン効率でも完遂率・検証通過率でも優位を示さない場合に棄却される。
- **次に集めるべき観測 (`next_observations`)**: D365業務ワークフロー以外の複数研究・コード探索課題における、全文脈保持対（直近剪定＋自動要約＋DAG分解）の完遂率・転写誤り率・総トークン消費量の複数反復比較。

---

## 6. 処理件数・台帳ID実在照合・全8ゲートの実測結果

### 6.1 担当 EVD 処理件数と台帳 ID 実在照合コマンド・実測結果

実行コマンド:

```bash
python3 - << 'PYEOF'
import json
from pathlib import Path

evd_ids = {json.loads(l)["evidence_id"] for l in Path("state/evidence.jsonl").read_text().splitlines() if l.strip()}
hyp_ids = {json.loads(l)["hypothesis_id"] for l in Path("state/hypotheses.jsonl").read_text().splitlines() if l.strip()}
cand = json.loads(Path("contributions/2026-10-21_relation_backfill_ALL.json").read_text())

items = cand["items"]
new_labels = {h["label"] for h in cand["new_hypothesis_candidates"]}
covered_evds = {it["evidence_id"] for it in items}
missing_evds = evd_ids - covered_evds
unknown_evds = covered_evds - evd_ids
bad_hyps = {
    it["hypothesis_id"] for it in items
    if not it["hypothesis_id"].startswith("NEW-") and it["hypothesis_id"] not in hyp_ids
}
bad_new = {
    it["hypothesis_id"] for it in items
    if it["hypothesis_id"].startswith("NEW-") and it["hypothesis_id"] not in new_labels
}
bad_memos = {
    it["basis"] for it in items
    if it["basis"].startswith("memo:") and not (Path("contributions") / it["basis"].split(":", 1)[1]).is_file()
}

print(f"Ledger EVDs: {len(evd_ids)} | Covered EVDs: {len(covered_evds)} | Total items: {len(items)}")
print(f"Ledger HYPs: {sorted(hyp_ids)} | New candidate labels: {sorted(new_labels)}")
print(f"missing_evds={len(missing_evds)}, unknown_evds={len(unknown_evds)}, bad_hyps={len(bad_hyps)}, bad_new={len(bad_new)}, bad_memos={len(bad_memos)}")
assert not (missing_evds or unknown_evds or bad_hyps or bad_new or bad_memos)
print("ALL LEDGER ID & MEMO FILE CHECKS PASSED.")
PYEOF
```

実測出力:
- `Ledger EVDs: 86 | Covered EVDs: 86 | Total items: 235`
- `Ledger HYPs: ['HYP-001', 'HYP-002'] | New candidate labels: ['NEW-ALL1', 'NEW-ALL2', 'NEW-ALL3', 'NEW-ALL4']`
- `missing_evds=0, unknown_evds=0, bad_hyps=0, bad_new=0, bad_memos=0`
- 本メモ単体に対する引用検査および全メモ台帳参照検査:
  - `python3 scripts/check_memo_citations.py --memos contributions/2026-10-21_relation_backfill_ALL.md` → `exit=0` PASS
  - `python3 scripts/check_memo_ledger_refs.py` → `exit=0` PASS（0 dangling references）

### 6.2 リポジトリ全8ゲートの実測結果（`.github/workflows/core-check.yml` 準拠）

| # | ゲート名 | 実行コマンド | 実測結果（`91a08f4` ＋ 本2ファイル） | 備考 |
| --- | --- | --- | :---: | --- |
| 1 | Run unit tests | `python3 -m unittest discover -s tests -v` | `exit=0` (388 tests OK) | 全388テスト PASS |
| 2 | Check benchmark reproducibility | `python3 gitswarm/benchmarks/benchmark.py --check` | `exit=0` | PASS |
| 3 | Check readout simulation reproducibility | `python3 gitswarm/readout_sim.py --check` | `exit=0` | PASS |
| 4 | Validate research ledgers | `python3 scripts/validate_state.py` | `exit=0` | PASS（`state/` 完全無変更） |
| 5 | Check citations against bundled arXiv snapshot | `python3 scripts/check_citations.py` | `exit=0` | PASS（22 arXiv sources checked, 0 failures） |
| 6 | Check memo citations against bundled arXiv snapshot | `python3 scripts/check_memo_citations.py` | `exit=0` | PASS（33 memos scanned, 0 failures） |
| 7 | Check ledger IDs and repo paths referenced in memos | `python3 scripts/check_memo_ledger_refs.py` | `exit=0` | PASS（33 memos scanned, 0 dangling references） |
| 8 | Check docs for stale numbers | `python3 scripts/check_doc_numbers.py` | `exit=0` | PASS（2 docs scanned, 0 stale numbers） |

### 6.3 自己マージ判定

`docs/autonomous-merge-policy-2026-10-21.md` の規定に従い、変更が `contributions/2026-10-21_relation_backfill_ALL.json` と `contributions/2026-10-21_relation_backfill_ALL.md` の2ファイルのみであること、ローカル全8ゲートがすべて `exit=0` であることを確認のうえ PR を作成し、GitHub Actions (`core-check`) が緑かつ `MERGEABLE` / `CLEAN` であることを確認してマージを完了する。
