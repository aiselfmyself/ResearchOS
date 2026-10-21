# 関係台帳（relations.jsonl）の実装報告 — SHELDON 読解メモ §5.7 手順1〜3

- 作成日：2026-10-21
- 作業ブランチ：`arena/0792d1db-researchos`（基準：`main` の `9f4b4f6`）
- 依頼の根拠：`docs/worker-prompts-next-stage-2026-10-21.md` の施策R・ワーカR1
- 設計の根拠：`contributions/2026-10-21_sheldon_reading.md` §5.0〜§5.5、§5.7（手順1〜3）
- 対象外：§5.7 の手順4〜7、`gap_scan.py`（R2）、verdict の投入（R4）

---

## 0. 結論

1. **手順1〜3を実施した。** `schemas/relation.json` と空の `state/relations.jsonl` を新設し、`validate_state.py` が関係台帳のスキーマと3種の参照（hypothesis / observation / source）を検査する。`REL` の採番は `scripts/new_id.py` で行える。
2. **既存5台帳のレコードは1件も変わっていない。** `state/` の5ファイルの SHA-256 を移行前と照合し、一致を確認した（§6.2）。
3. **REL-NNN（連番形式）は拒否される。** REL には凍結連番の範囲が無いため `LEGACY_MAX` にキーを足していない。拒否はテストで確認した（§4）。
4. **メモ内の REL 参照は検査7（`check_memo_ledger_refs.py`）で解決検査される。** 関係台帳は空なので、現時点で REL を参照するメモは dangling になる。これは仕様どおり。
5. **ゲートは8つ中6つが緑。残る2つ（ゲート1のうち3テスト、ゲート8）は、テスト件数 243→280 の更新が README.md と docs/minimal-core-and-ci.md に未反映なため赤。** 両ファイルは統合役の所有（`docs/parallel-work-ownership.md` §2）で、依頼文も README の編集を禁じているため、件数更新は行わなかった。文案は §5.1 にある。作業コピーで文案を適用すると8ゲートすべて緑になることを確認した（§6.3）。
6. **逸脱が2点ある。** どちらも §5 に理由つきで書いた。(a) 他セッションのメモ `contributions/2026-10-21_sheldon_reading.md` の §5.1 の例示 ID を、ゲート7が dangling と判定しないよう非トークンのプレースホルダに変えた。(b) `tests/test_minimal_core.py` の 1 テストを、連番を持たない REL に対応させた。

---

## 1. 差分一覧

| 区分 | ファイル | 変更内容 |
|---|---|---|
| 新規 | `schemas/relation.json` | 必須：`relation_id` / `hypothesis_id` / `observation_id` / `verdict`。`verdict` は enum `["support","refute","neutral","unresolved"]`。任意：`provisional`（boolean）、`source_id`、`rationale`、`recorded_at`（いずれも string。`provisional` のみ boolean） |
| 新規 | `state/relations.jsonl` | 空（0 バイト）。レコード投入は R4 |
| 変更 | `scripts/validate_state.py` | `COLLECTIONS` に `relations`、`ID_PREFIXES` に `REL` を追加。`check_references` に関係台帳の3参照と `claim.hypothesis_ids` の検査を追加。`ID_TOKEN_RE` の接頭辞に `REL` を追加。`check_id_format` の「連番範囲が無い接頭辞」のエラー文を明確化。docstring 更新 |
| 変更 | `scripts/new_id.py` | `PREFIXES` / `ID_KEYS` に `REL` を追加 |
| 変更 | `schemas/evidence.json` | 任意の string 3つ：`observation_key` / `observation_axis` / `observation_region` |
| 変更 | `schemas/hypothesis.json` | 任意：`hypothesis_region`（string）、`search_status`（enum `["retained","setaside"]`）、`cooldown_rounds`（integer）。既存 `status` は変更なし |
| 変更 | `schemas/claim.json` | 任意：`hypothesis_ids`（string 配列） |
| 新規 | `tests/test_relations.py` | 37 件（§4） |
| 変更 | `tests/test_minimal_core.py` | `test_legacy_max_matches_current_ledgers` に REL の分岐を1つ追加（§5.3） |
| 変更 | `contributions/2026-10-21_sheldon_reading.md` | §5.1 の JSON 例の `relation_id` を `REL-YYYYMMDD-xxxx` に置換（§5.2） |
| 新規 | `contributions/2026-10-21_relation_ledger_impl.md` | 本ファイル |

**変更していないもの**：`state/` の既存5台帳、`README.md`、`docs/minimal-core-and-ci.md`、`.github/`、`gitswarm/`、`LEGACY_MAX`、`FROZEN_MAX_EXPECTED`。

---

## 2. §5.7 手順との対応

| §5.7 手順 | 内容 | 本 PR | 結果 |
|---|---|---|---|
| 1 | `relation.json` と `relations.jsonl` を新設（空） | 実施 | 検査 `validate_state` で `relations=0`、エラー 0 |
| 2 | evidence / hypothesis / claim に任意フィールドを追加 | 実施（§5.2・§5.3・§5.5 の全フィールド） | 既存レコードは全件 `validate_record` 合格（テスト `test_existing_records_remain_valid`） |
| 3 | `new_id.py` / `validate_state.py` に REL を追加。`LEGACY_MAX` は据え置き | 実施 | `REL` は `LEGACY_MAX` に無い。`REL-NNN` は拒否される |
| 4 | `gap_scan.py` を報告のみで新設 | 対象外（R2） | — |
| 5 | `observation_key` を人が付与 | 対象外（人手） | — |
| 6 | REL に裁定結果を書き込む | 対象外（R4） | — |
| 7 | `search_status` / `hypothesis_region` を付与 | 対象外（人手） | スキーマだけ用意した |

### 2.1 §5.1 の型との対応

| §5.1 の記述 | 実装 |
|---|---|
| 必須は relation_id / hypothesis_id / observation_id / verdict | `required` に一致 |
| `verdict` の enum は論文の4値 | 一致。`falsified` や `pass`（VER の語彙）は拒否される |
| `provisional` は boolean、省略時は §5.3 の導出規則で決まる | boolean のみ検査。**導出は未実装**（導出は R2 の `gap_scan` の仕事。§5.2 参照） |
| 参照：`relation.hypothesis_id → hypotheses` | 実装（必須参照） |
| 参照：`relation.observation_id → evidence` | 実装（必須参照。`claims` は解決先に含めない） |
| 参照：`relation.source_id → sources` | 実装（任意。省略可、あれば解決） |
| ID 形式は `PREFIX-YYYYMMDD-xxxx` | `check_id_format` が検査 |

### 2.2 §5.2・§5.3・§5.5 のフィールド

| 対象 | フィールド | 型 | 既定値（メモの記述） | 本 PR での扱い |
|---|---|---|---|---|
| evidence | `observation_key` | string | `evidence_id` | スキーマに追加。**既定値は適用しない**（読み出し側＝R2 の仕事） |
| evidence | `observation_axis` | string | `source_id` | 同上 |
| evidence | `observation_region` | string | `source_id` | 同上。未登録の領域名も保持できる（型のみ検査） |
| hypothesis | `hypothesis_region` | string | `subtasks[0]` | 同上 |
| hypothesis | `search_status` | enum `retained` / `setaside` | `retained` | 同上。**既存 `status` とは別フィールド**（テスト `test_new_optional_hypothesis_fields_are_accepted_and_separate_from_status`） |
| hypothesis | `cooldown_rounds` | integer | `3` | 同上 |
| claim | `hypothesis_ids` | string 配列 | 無し | 存在すれば `hypotheses` への参照を検査。無ければ何もしない |

---

## 3. 検証器の挙動（本 PR で増えた検査）

| 入力 | 結果 | テスト |
|---|---|---|
| 空の `relations.jsonl` | 合格（`relations=0`） | `test_empty_relation_ledger_is_valid` |
| 正常な REL（3参照すべて解決） | 合格 | `test_valid_relation_is_accepted` / `test_new_format_rel_id_passes_the_whole_ledger_check` |
| `hypothesis_id` が存在しない | 拒否 | `test_dangling_hypothesis_reference_is_rejected` |
| `observation_id` が存在しない、または CLM を指す | 拒否 | `test_dangling_observation_reference_is_rejected` / `test_observation_id_resolves_to_evidence_not_claims` |
| `source_id` が存在しない | 拒否 | `test_dangling_source_reference_is_rejected` |
| `verdict` が enum 外（`banana` / `Support` / `falsified` / `pass` / 空文字） | 拒否 | `test_invalid_verdict_is_rejected` |
| 必須フィールドの欠落（4種） | 拒否 | `test_missing_required_field_is_rejected` |
| `provisional` が boolean でない | 拒否 | `test_provisional_must_be_boolean` |
| `REL-NNN`（連番形式） | 拒否。メッセージ：「REL has no grandfathered sequential range」 | `test_sequential_rel_id_is_rejected` / `test_sequential_rel_id_fails_the_whole_ledger_check` |
| `REL-YYYYMMDD-xxxx` | 受理 | `test_mint_produces_rel_ids` |
| 散文中の REL 参照（ID_TOKEN_RE 経由） | 未解決なら拒否 | `test_rel_token_in_prose_must_resolve` |
| `claim.hypothesis_ids` が解決する | 合格 | `test_claim_hypothesis_ids_must_resolve_to_hypotheses` |
| `claim.hypothesis_ids` に存在しない HYP（`HYP-NNN` 形式の仮の値）や EVD 形式の値 | 拒否（解決先は hypotheses のみ） | `test_claim_hypothesis_ids_must_resolve_to_hypotheses` / `test_claim_hypothesis_ids_do_not_accept_evidence_ids` |
| `claim.hypothesis_ids` が無い既存 claim | 影響なし | `test_claim_without_hypothesis_ids_is_unaffected` |
| 既存レコードに任意フィールドを足す | 合格（形状は不変） | `test_new_optional_*` / `test_existing_*` |
| `search_status: banana` / `cooldown_rounds: "3"` | 拒否 | `test_new_optional_hypothesis_fields_are_accepted_and_separate_from_status` |

### 3.1 REL 参照の検査7（メモ）

- `check_memo_ledger_refs.py` は `validate_state.ID_TOKEN_RE` を import している。そのため REL の追加は検査7にも自動で効く。
- `load_ledger_ids()` は `REL` のバケットを持つ（空集合）。
- 既存のメモに REL の実参照は無い（`contributions/` を全件走査して確認）。
- メモ内に REL 形式の token が出ると、関係台帳に存在しない限り dangling になる。**これは意図した挙動**であり、R4 が台帳にレコードを入れるまで REL を引用するメモは書けない。

---

## 4. 検証の追加（tests/test_relations.py、37件）

- 既存の `tests/test_minimal_core.py` と同じく、合成データ（in-memory）で参照検査を行う。
- 端から端までの検査（`run_all_checks`）は、**一時ディレクトリ**上の合成リポジトリで行う。`state/` だけを一時コピーし、他のディレクトリは元のリポジトリへのシンボリックリンクにした。実台帳は書き換えない。
- 変異テスト（§6.4）で、テストが実際に検出することを確かめた。

---

## 5. 逸脱提案（コードに反映していないものと、反映したもの）

### 5.1 `README.md` と `docs/minimal-core-and-ci.md` の件数は更新していない（**未解決・統合役の判断待ち**）

- 理由：両ファイルは `docs/parallel-work-ownership.md` §2 で「統合役のみ」。依頼文も README の編集を禁じ、更新が必要なら文案をメモに書くよう指定している。
- 影響：テスト件数が 243 → 280 になったため、**ゲート1（unittest）の3テストと、ゲート8（check_doc_numbers）が赤になる**。
  - 赤の内訳：`test_check_doc_numbers.RealRepoTest` の2件と、`test_holdout_eval` の `doc_numbers` 検査1件（いずれも README / minimal-core の件数を読む）。
  - `check_doc_numbers.py` の出力：README.md:66 / :126 / :137、docs/minimal-core-and-ci.md:54 の4箇所が `found 243, expected 280`。
- 文案（統合役が適用する場合の差分。作業コピーで適用して検証済み）：

```diff
--- a/README.md
+++ b/README.md
@@ -63,7 +63,7 @@
 リポジトリからの再計算値を突き合わせて検査する。算出コマンドは下記「使い方」節。
 
 - 台帳: sources=23 / evidence=86 / claims=9 / verifications=34 / hypotheses=2
-- テスト: 合計 243件（`tests/` の 12 ファイル。内訳は下記 §構成）
+- テスト: 合計 280件（`tests/` の 13 ファイル。内訳は下記 §構成）
 - CI ゲート: 8ゲート（`.github/workflows/core-check.yml` の `run:` を持つステップ数）
 
 **なぜこの節を引用ブロック（`>`）で書かないか** —— ゲートは「`>` で始まる行」を**過去の
@@ -123,7 +123,8 @@
   test_check_doc_numbers.py    文書内の陳腐化した数値の検査テスト（21件）
   test_holdout_eval.py         hold-out 分割と過適合判定のテスト（18件）
   test_prune_candidates.py     低寄与コンポーネント報告のテスト（19件）
-                               ── 合計 243件
+  test_relations.py            関係台帳（REL）の検査・採番・メモ参照解決のテスト（37件）
+                               ── 合計 280件
 contributions/         研究ノート（統合レポート・調査メモ・全文読解レポート・共通モード測定）
 docs/                  分析レポートと設計記録（並行作業の所有マップは docs/parallel-work-ownership.md。強制力なし）
 .github/workflows/
@@ -134,7 +135,7 @@
 ## 使い方
 
 ```sh
-# 1. テスト（約5秒・243件）
+# 1. テスト（約5秒・280件）
 python3 -m unittest discover -s tests -v
 
 # 2. ベンチマークの再現性確認（fresh実行と成果物の照合）
--- a/docs/minimal-core-and-ci.md
+++ b/docs/minimal-core-and-ci.md
@@ -51,7 +51,7 @@
 
 ゲートするのは決定論的・再実行可能な**8検査**（2026-10-21 時点。初版は4検査で、2026-10-20 に 5・6 を、2026-10-21 に 7 を、同日 8 を追加した）：
 
-1. `python3 -m unittest discover -s tests -v` — **243テスト**（約3〜5秒）
+1. `python3 -m unittest discover -s tests -v` — **280テスト**（約3〜5秒）
 2. `python3 gitswarm/benchmarks/benchmark.py --check` — 成果物と fresh run の照合（許容誤差0.01）
 3. `python3 gitswarm/readout_sim.py --check` — 投票シミュレーション成果物と fresh run の照合
 4. `python3 scripts/validate_state.py` — 研究台帳のスキーマ・ID一意・参照整合性（**台帳内の** ID・パス参照の存在検査を含む）
```

- 関係台帳の件数を README の「台帳」行（`sources=23 / … / hypotheses=2`）に加えるかどうかは統合役の判断。依頼文どおり本 PR では加えていない。同様に `check_doc_numbers.py` の `LEDGERS` にも relations を加えていない（台帳件数の検査対象に含めるかも統合役の判断）。

### 5.2 `contributions/2026-10-21_sheldon_reading.md` の §5.1 の例示 ID を書き換えた（**逸脱・要確認**）

- 変更：§5.1 の JSON 例の `relation_id`（日付入りの仮の具体値）を `REL-YYYYMMDD-xxxx` に置換（1行）。
- 理由：ID_TOKEN_RE に REL を入れた（依頼の必須要件、DoD 3）ため、この例示 ID が検査7で dangling と判定された。関係台帳は空なので解決しようがない。プレースホルダにすれば例の構造はそのまま伝わる。
- 逸脱の性質：他セッションが書いたメモの本文を変えた。`docs/parallel-work-ownership.md` は「他セッションの `contributions/` は書き換えない」と定める。その規則からの逸脱であることを明示する。
- 代替案：例示を残し、検査7を REL だけ例外扱いにする。ただし検査の意味を歪めるため採らなかった。統合役が例示の差し戻しを望むなら、その時点で検査7の除外規則を検討する。

### 5.3 `tests/test_minimal_core.py` の1テストに REL の分岐を追加した（**逸脱・要確認**）

- `test_legacy_max_matches_current_ledgers` は全台帳に連番レコードがあることを前提に `max()` を取る。REL には連番レコードが無いため、`ValueError: max() arg is an empty sequence` で失敗した。
- 変更：`prefix not in FROZEN_MAX_EXPECTED` の台帳について「`LEGACY_MAX` にキーが無いこと」を検査して `continue` する。
- 弱めていないこと：既存の5接頭辞（SRC / EVD / CLM / VER / HYP）の検査（連番の上限、`LEGACY_MAX == FROZEN_MAX_EXPECTED`）は従来どおり。`LEGACY_MAX` に `REL` を足すことは、この分岐が即座に失敗させる（変異 B で確認済み）。

### 5.4 `check_id_format` のエラー文を、連番範囲が無い接頭辞向けに分けた（**挙動は不変、文言のみ**）

- 従来は連番形式の REL に対して「extends the frozen sequential range (max 上限 0)」と出た。意味が通らないため、`legacy_max == 0` の場合だけ「has no grandfathered sequential range」の文に分けた。
- 既存の5接頭辞は `LEGACY_MAX > 0` なので、新しい分岐には入らない。判定ロジックは変わらない。

### 5.5 メモ §5.2・§5.3 の「既定値」は実装していない（**未実装・意図どおり**）

- メモ §5.2・§5.3 の既定値（`observation_key` → `evidence_id`、`observation_axis` / `observation_region` → `source_id`、`hypothesis_region` → `subtasks[0]`、`search_status` → `retained`、`cooldown_rounds` → `3`）と、`provisional` の導出規則（§3.4）は**実装していない**。
- 理由：既定値は読み出し側（R2 の `gap_scan.py` など）が解釈する意味論である。台帳の検証器が欠落を既定値で埋めると、欠落が見えなくなり、fail-closed の原則に反する。スキーマにも `default` は書いていない（本リポジトリの検証器は `default` を見ない）。

### 5.6 `recorded_at` は string のみ検査（**未実装・意図どおり**）

- 日付形式（YYYY-MM-DD）の検査は入れていない。検証器は `pattern` を扱わず、既存の台帳（evidence / claims 等）も string のみで検査している。依頼の「string」指定に従った。

---

## 6. 検証結果（実測）

### 6.1 全ゲート（移行前 → 本 PR）

| # | コマンド | 移行前（`9f4b4f6`） | 本 PR | 判定 |
|---|---|---|---|---|
| 1 | `python3 -m unittest discover -s tests` | OK（243件） | **FAIL 3件**（280件中。いずれも件数が README / minimal-core と不一致。§5.1） | **赤（件数のみ）** |
| 2 | `python3 gitswarm/benchmarks/benchmark.py --check` | PASS | PASS | 緑 |
| 3 | `python3 gitswarm/readout_sim.py --check` | PASS | PASS | 緑 |
| 4 | `python3 scripts/validate_state.py` | PASS（sources=23, evidence=86, claims=9, verifications=34, hypotheses=2） | PASS（同上 + relations=0） | 緑 |
| 5 | `python3 scripts/check_citations.py` | 0 failure(s) | 0 failure(s) | 緑 |
| 6 | `python3 scripts/check_memo_citations.py` | 0 failure(s) | 0 failure(s) | 緑 |
| 7 | `python3 scripts/check_memo_ledger_refs.py` | 0 dangling | 0 dangling（§5.2 の差し替え後） | 緑 |
| 8 | `python3 scripts/check_doc_numbers.py` | 0 stale（tests=243） | **4 stale**（tests=280。README 3箇所・minimal-core 1箇所） | **赤（件数のみ）** |

- ゲート1の3件の失敗は次のとおり。`test_main_exits_zero_on_the_real_repo` と `test_repo_docs_have_no_stale_numbers`（いずれも `check_doc_numbers` の実台帳検査）、`test_holdout_eval` の `doc_numbers` 検査（同じ検出器を過適合判定に通す検査）。原因はすべて件数のズレ。
- 件数の内訳：移行前 243 件 ＋ 本 PR 追加 37 件（`test_relations.py`）= 280 件。`test_minimal_core.py` は件数不変（分岐の追加のみ）。

### 6.2 既存台帳の不変性

`state/` の既存5ファイルの SHA-256 を移行前に記録し、本 PR 後と照合した。

```
state/claims.jsonl        OK
state/evidence.jsonl      OK
state/hypotheses.jsonl    OK
state/sources.jsonl       OK
state/verifications.jsonl OK
```

### 6.3 件数更新を適用した場合（作業コピーでの検証。リポジトリには反映していない）

- 作業コピーに §5.1 の差分を適用し、全ゲートを実行した。結果：unittest 280件 OK、benchmark PASS、readout_sim PASS、validate_state PASS、check_citations 0 failure、check_memo_citations 0 failure、check_memo_ledger_refs 0 dangling、check_doc_numbers 0 stale。**8ゲートすべて緑**。

### 6.4 変異テスト（テストが検出することの確認）

作業コピー上で検証器・スキーマに1か所ずつ変異を入れ、`tests/test_relations.py` と `tests/test_minimal_core.py` を実行した。

| 変異 | 結果 |
|---|---|
| ベースライン | 71件 OK |
| A：relation → hypothesis の参照検査を外す | 1件失敗（`test_dangling_hypothesis_reference_is_rejected`） |
| B：`LEGACY_MAX` に `REL: 5` を足す | 4件失敗（REL 連番の受理・`LEGACY_MAX` の不在の検査） |
| C：`ID_TOKEN_RE` から REL を外す | 5件失敗（メモ参照の検査） |
| D：verdict enum から `unresolved` を外す | 2件失敗 |
| E：relation → evidence の参照検査を外す | 2件失敗 |
| F：claim.hypothesis_ids の参照検査を外す | 2件失敗 |

変異テストのスクリプトは作業コピー（`/tmp/mut`）にのみあり、リポジトリには含めていない。

### 6.5 テストの実行時間

- `python3 -m unittest discover -s tests`：約5秒（280件）。

---

## 7. 次の担当への申し送り

1. **統合役：** §5.1 の件数更新を適用する。これでゲート1とゲート8が緑に戻る。関係台帳の件数を README に出すかは統合役が決める。
2. **R2（gap_scan）：** 任意フィールドの既定値（§5.5）と `provisional` の導出（§3.4）は R2 で実装する。`gap_scan.py` は報告専用で、台帳を変えない。
3. **R4（verdict 投入）：** REL は裁定で書く。`VER` の `fail` を `refute` に写してはならない（§5.4 の禁止）。REL のメモ参照は、台帳にレコードが入った後にのみ書ける（§3.1）。
4. **§5.7 手順5〜7** は人手の作業で、本 PR の対象外。

---

## 8. 参照

- `contributions/2026-10-21_sheldon_reading.md` §5.0〜§5.5、§5.7、§7.2
- `docs/record-id-scheme.md` §2（採番方法）
- `docs/parallel-work-ownership.md` §2（README と docs/minimal-core の所有）
- 台帳の現状：`state/hypotheses.jsonl`（HYP-001 / HYP-002）、`state/evidence.jsonl`（EVD 86件）
