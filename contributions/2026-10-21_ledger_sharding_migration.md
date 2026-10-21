# 台帳シャーディング移行（方式B）実施記録

- 作成日：2026-10-21
- 対象：`state/*.jsonl`（研究6台帳）と `tests/fixtures/arxiv_metadata_snapshot.json`
- 採用方式：**B（不変の凍結ベース＋セッション別シャード＋読み取り時統合ビュー）**。S1 の推奨案（`contributions/2026-10-21_ledger_sharding_design.md` §1）を、人間が 2026-10-21 に採用した。
- 前提の確認：S2 の `scripts/merge_ledgers.py` が main に存在。他に開いているコード変更 PR は 0 件（`gh pr list`）。R1（`schemas/relation.json`・`state/relations.jsonl`）はマージ済みで、`validate_state.py` と `new_id.py` を触る他ワーカーはいない。
- 本メモの結論：**レコードは1件も動かしていない。** 変わったのは「どう読むか」だけである。移行前後の集合一致は、ベースファイルの SHA-256 一致と、独立実装による ID→内容ハッシュの差分ゼロで示す（§3）。台帳ファイルの並行追記はテキスト衝突ゼロ（§4）。全ゲート緑（§5）。

## 0. 開始時の停止と、人間の決定

S3 の前提行は `《ここに採用方式を人間が記入》` のまま未記入だった（`docs/worker-prompts-next-stage-2026-10-21.md` 147 行、実測 1 件）。手順どおり作業を開始せず、次の2点を確認した。

| 確認事項 | 人間の回答 |
|---|---|
| 採用方式 | **方式B**（S1 の推奨案） |
| 既存の赤ゲート（下記）の扱い | **README の数値追随を例外許可** |

開始時点の main（`352f8fe`）は既に 2 ゲートが赤だった。私の作業起因ではない。

- `python3 -m unittest discover -s tests` → `Ran 293 tests`、`FAILED (failures=2)`（`test_check_doc_numbers.RealRepoTest` の2件）
- `python3 scripts/check_doc_numbers.py` → 終了1、`actual: tests=293` に対し文書は `280`（README 3箇所＋`docs/minimal-core-and-ci.md` 1箇所）

README の数値追随は、人間の例外許可に加えて `docs/parallel-work-ownership.md` §2.2（`check_doc_numbers.py` が stale と報告した件数の更新は全セッションが承認なしで実施してよい。新しいテストファイルを一覧に1行追加するのも可）に根拠がある。**この2点以外で README を編集していない**（台帳配置の記述は §6 の文案として統合役へ渡す）。

## 1. S1 移行手順の転記と、手順ごとの実施・検証

| # | S1 §5 が求めること | 実施すること（本作業） | 検証方法と実測 |
|---|---|---|---|
| 1 | 現状を固定・記録する。既存 JSONL 5本と fixture のハッシュ・件数を記録し、内容・名前・配置を変えない | `git show main:<path>` の SHA-256 と件数を記録。以後 `state/` と `tests/fixtures/` は一切編集しない | §3(a)。7ファイルすべて main と SHA-256 一致。`git diff main -- state tests/fixtures` は 0 行 |
| 2 | まず読み取り側に後方互換を追加する。共通ローダーを導入し、現行フラット JSONL だけでも同じ結果を返す。重複IDは2つの出所を報告 | `scripts/ledger_store.py` を新設。`load_ledger` / `load_jsonl` / `load_snapshot` / `duplicate_ids`。`validate_state.load_jsonl` はローダーへ委譲（呼び出し側は無変更で統合ビューを読む） | §3(b) 独立実装との差分ゼロ。`tests/test_ledger_shards.py` の `UnionViewTest`・`BundledLedgerTest`。重複は `duplicate ...: <base>:<line> and <shard>:<line>` |
| 3 | 台帳の全読者を同じビューへ切り替える（`new_id`・`check_citations`・`check_memo_ledger_refs`・`check_doc_numbers`） | 4スクリプトを追随。`check_citations.load_ledger` は重複 source_id を `ValueError`。`check_doc_numbers.actual_ledger_counts` は非空行数→統合レコード数 | `ReaderIntegrationTest`（採番・件数・メモ参照・書誌）。§5 のゲート実測 |
| 4 | fixture の読取互換を追加する。共通スナップショットローダーが既存 JSON とサイドカー entries を統合。`holdout_eval.py` の JSON 直読も置き換える | `ledger_store.load_snapshot`。`check_citations.load_fixture` と `check_memo_citations.load_fixture` が同一ローダー。`holdout_eval.run_memo_citations` の直接 `json.loads` を削除 | `SnapshotShardTest`（統合・重複・命名・ヘッダー非上書き・部品エントリの可視性） |
| 5 | 読者と CI をテストしてから書き手の手順を切り替える。ベースのみ／ベース＋2シャード／重複ID／同一ID異内容／dangling／fixture 重複／fixture ヘッダー差分、2新規シャードの合成 Git マージ、8ゲート緑 | `tests/test_ledger_shards.py`（39件、§2）。並行追記は §4 の合成 Git 実験。8ゲートは §5 | §4・§5。全ゲート終了コード 0 |
| 6 | 追記方法と件数説明を更新する（`docs/record-id-scheme.md`・`docs/parallel-work-ownership.md`・`docs/minimal-core-and-ci.md` は統合役） | **未実施（担当外）**。更新文案を §6 に用意した | §6。数値のみ実測に追随済み（`docs/minimal-core-and-ci.md` 54行のテスト数） |
| 7 | 古いパスは削除せず互換ベースとして維持する。初回移行では削除しない | 配置変更ゼロ。旧パスは凍結ベースとして存続し、統合ビューの先頭部分になる | §3(a)。検査7（`check_memo_ledger_refs.py`）は 0 dangling のまま（§5）。台帳内パス検査も緑 |
| 8 | revert 手順を固定する | §7 に手順を固定し、実際に revert して全ゲート緑を確認 | §7 の実測 |

## 2. 何を変え、何を変えていないか

### 2.1 変えていないもの

- `state/*.jsonl`（6本）と `tests/fixtures/arxiv_metadata_snapshot.json`：**バイト同一**（§3(a)）。既存154レコードの ID・内容・順序・配置は不変。
- 台帳スキーマ（`schemas/*.json`）、台帳 ID 体系（`LEGACY_MAX` を含む）、CI のゲート数（8）と実行コマンド。
- レコードの追加・削除・書換え：**0件**。

### 2.2 変えたもの（読み取り側のみ）

| 対象 | 変更 |
|---|---|
| `scripts/ledger_store.py`（新規） | 凍結ベース＋シャードの唯一の読み手。`state/<name>.d/《YYYY-MM-DD》-《12桁hex》.jsonl` をファイル名順に結合。fixture は `<base>.d/《...》.json`。重複IDは出所つきで報告し、どちらも黙って選ばない。日付で始まるのに読めないファイルは「NOT in the view」と報告（レコードの無言欠落を防ぐ） |
| `scripts/validate_state.py` | 全検査（スキーマ・ID 一意・ID 形式・参照・散文パス）を統合ビュー上で実行。重複は両方の出所を表示。`load_jsonl` は互換 API のまま統合ビューを返す |
| `scripts/new_id.py` | 衝突確認がシャードの ID も見る（シャードにしか無い ID との衝突を防ぐ） |
| `scripts/check_citations.py` | 台帳は統合ビュー、スナップショットはベース＋パーツ。source_id 重複はエラー |
| `scripts/check_memo_citations.py` | `load_fixture` を公開し、`check_citations` と同一ローダーを使用 |
| `scripts/check_memo_ledger_refs.py` | メモがシャードにしか無い ID を引用しても解決する |
| `scripts/check_doc_numbers.py` | 台帳件数＝統合ビューのレコード数（旧：ベースの非空行数） |
| `scripts/holdout_eval.py` | `memo_citations` 検出器の JSON 直読を廃止し共通ローダーへ |
| `scripts/ledger_digest.py`（新規） | レコード内容の SHA-256 を出力する計測器。`--raw-only` が移行前ビュー、既定が統合ビュー。両者の diff が空であることが集合一致の証明になる |
| `tests/test_ledger_shards.py`（新規39件） | 読取・件数・参照整合性の回帰（§2.3） |
| `README.md`・`docs/minimal-core-and-ci.md` | stale だったテスト数を実測に追随（最終 342件）。`test_ledger_shards.py` の一覧行を追加（`test_merge_ledgers.py` は main 側で追加済み） |

### 2.3 シャード配置の規則（実装した契約）

```text
state/<name>.jsonl                       凍結ベース（2026-10-21 以降、追記しない）
state/<name>.d/<YYYY-MM-DD>-<12桁hex>.jsonl   1セッション／1作業バッチ＝1ファイル（追記専用・後から編集しない）
tests/fixtures/arxiv_metadata_snapshot.json       凍結ベース
tests/fixtures/arxiv_metadata_snapshot.d/<YYYY-MM-DD>-<12桁hex>.json   追加エントリ（capture_note 等の由来を保持）
```

- 12桁hex（48ビット）は、同日に並行するセッションが同一ファイル名を作らないための要素である。日付だけの命名は衝突するので不可。
- シャードディレクトリが無いことは正常（ベース凍結後に追記が無い状態）。最初の追記時に作成する。
- シャード名の規則違反は**エラーとして報告**する。正しい拡張子ならレコードは読み、拡張子違いなら「NOT in the view」と明示する（黙って落とさない）。
- 統合ビューはメモリ上だけに存在し、追跡ファイルへ再生成しない（再生成物は再び共有末尾追記の衝突点になる。S1 §1）。

### 2.4 スナップショットのヘッダー

統合ビューのヘッダーは**ベースのヘッダーそのまま**（`captured_at`・`capture_note` を上書きしない）。パーツ側のヘッダーは `load_snapshot` の戻り値 `part_headers` に保持し、取得日・取得方法の由来を失わない。同一 arXiv ID がベースとパーツ、または2つのパーツに現れた場合は、内容が同一でもエラーにする（S1 §1 の要求）。

## 3. 移行前後の集合一致（DoD 1）

### 3.1 (a) ベースファイルのバイト同一性

移行コミットの作業ツリーと main（`352f8fe`）を比較。`git diff main -- state tests/fixtures` は **0行**。個別 SHA-256 も一致。

| ファイル | SHA-256（main と作業ツリーで同一） |
|---|---|
| `state/sources.jsonl` | `cafc5042beac0cb02641b97fe40d20e7e8e4db4e46d6182eb44f837043882918` |
| `state/evidence.jsonl` | `87a6db6dbd436ae8d40c52799ed3f01be2c3689b5c32c25b5a48717f9f54450b` |
| `state/claims.jsonl` | `c58f2af48ee44ef5a0d852f313988a6017e700233f7a004a75a3717fc0a8bae3` |
| `state/verifications.jsonl` | `6e8331e37fd00f57f5fa119af3d113e358d4cfd79992c0a11d01102cf9e06f7f` |
| `state/hypotheses.jsonl` | `7da895e6044d3887d2b73438837faac20aef1ee61b2bfafb024f2e874252ddf2` |
| `state/relations.jsonl` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（空） |
| `tests/fixtures/arxiv_metadata_snapshot.json` | `a346572fdd66436f036dfc4c77b97cfccb0d0cddbb335d3c1c26693f92c4e3b3` |

### 3.2 (b) ID→内容ハッシュの差分ゼロ（独立実装との突合）

手続き（`/tmp/s3-pre` は作業ツリー外）：

1. `git show main:state/<name>.jsonl` で移行前の6ファイルを `/tmp/s3-pre/state/` に取り出す。
2. **本移行のコードを一切 import しない**独立スクリプト（標準の `json` と `hashlib` のみ）で、各レコードを `sort_keys=True` の正規形にし、`ID<TAB>sha256` を ID 順に出力。台帳ごとの総合ハッシュも計算。
3. 移行後の作業ツリーで `python3 scripts/ledger_digest.py --records`（統合ビュー）を実行。
4. 2 と 3 を `diff`。

実測（`diff` の出力は空、終了コード 0）：

```text
=== DIFF EMPTY: 0 difference ===
# ledger	records	combined_sha256
claims	9	f76b636005337bc87a94739ebfdc31dd51f2486265d19434036ebe7b7f76a896
evidence	86	160ef7a93e2ebe16bcdec7f7bc660e8bcbb661fe1758e5879f06587f8275104b
hypotheses	2	8733286de60c200c25b10f1bd2a7045ac749ad8a3ab501f21eb3414f844198c2
relations	0	e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
sources	23	f68e19b276358412a64b71f5909ede2a7a1382377c5ba811c7bae0e7b9237a37
verifications	34	205e330ba6b3cc56d70510e9e623da6a475d148c9aaaecbe003b11d53d7b46fd
```

- レコード行は **154件**（9+86+2+0+23+34）。移行前後で1件の差もない。
- 内容ハッシュは、キー順・空白・行順・ファイル配置に依存しない正規形で計算している。したがって「ID と内容が同じ」ことを直接主張している。
- 併せて、`ledger_digest.py --raw-only`（ベースファイルのみ）と既定（統合ビュー）の出力も**完全一致**（シャード0件のため当然だが、ローダーが既存分を1件も落としていないことの確認になる）。

## 4. 並行追記の実証（DoD 2）

すべて `/tmp` の使い捨てクローンで実施した。**本リポジトリには使い捨てブランチを作っていない**（削除承認が必要な残留物は無い）。クローン元は移行コミット。

### 4.1 方式B：3ブランチが別シャードへ同時追記 → テキスト衝突0

3ブランチ（`session-a`/`session-b`/`session-c`）が、それぞれ `state/evidence.d/` に**自分の1ファイル**を追加（各1レコード、ID は `EVD-20261021-` + 4桁hex の合成値）。`main` へ順次マージした実測：

```text
--- merge session-a ---
Fast-forward
 state/evidence.d/<...>.jsonl | 1 +
--- merge session-b ---
Merge made by the 'ort' strategy.
 state/evidence.d/<...>.jsonl | 1 +
merge_exit=0
--- merge session-c ---
Merge made by the 'ort' strategy.
 state/evidence.d/<...>.jsonl | 1 +
merge_exit=0
=== validator after 3 merges ===
PASS: research ledgers valid (sources=23, evidence=89, claims=9, verifications=34, hypotheses=2, relations=0)
```

- **競合は0件**（`CONFLICT` の出現なし）。3回とも終了コード 0。
- 統合ビューは 86 → **89件**。3つの新 ID がすべて現れ、既存86件のハッシュは不変（`ledger_digest --records` で確認）。**レコードの喪失も重複もない。**

### 4.2 対照実験：同じ3ブランチが `state/evidence.jsonl` に直接追記 → 衝突

```text
--- merge append-a ---
 state/evidence.jsonl | 1 +
--- merge append-b (same text location) ---
Auto-merging state/evidence.jsonl
CONFLICT (content): Merge conflict in state/evidence.jsonl
Automatic merge failed; fix conflicts and then commit the result.
--- conflicted files ---
state/evidence.jsonl
--- merge append-c ---
CONFLICT (content): Merge conflict in state/evidence.jsonl
```

異なる ID を追記しているにもかかわらず、テキスト位置が同じため衝突する（S1 §4.1 の再現）。方式Bはこの衝突を消している。

### 4.3 残る唯一の共有テキスト：README の「現在の状態」件数行（実測）

台帳件数はゲート8が検査するため、追記したセッションは `README.md` の `- 台帳: ... evidence=N` 行も更新する必要がある（`docs/parallel-work-ownership.md` §2.2 が許可）。この行は台帳ではないが共有テキストである。2通りを実測した。

| 場合 | 結果 |
|---|---|
| 各セッションが同じ差分（+1）で同じ値に更新 | `README.md` は自動マージ（テキスト衝突なし）。ただし2本目のマージ後は件数が実測より1少なくなり、ゲート8が stale を報告する（追記後に1回の件数更新コミットが必要） |
| 各セッションが異なる差分（+1 と +3）で更新 | `Auto-merging README.md` → `CONFLICT (content): Merge conflict in README.md`。**衝突ファイルは `README.md` のみ**。実測の和（89+1+3=93）に解決して再実行すると、`validate_state` は `evidence=93` で PASS、ゲート8も 0 stale |

これは移行前から存在する性質（件数を散文に書く限り、その行は共有される）であり、本移行で悪化はしていない。台帳ファイル側の衝突は消え、残るのは1行の数値だけである。対策案は §8 に記す。

### 4.4 実リポジトリでの実例（`origin/main` の取り込み）

本PRの作業中に main が進み（PR #55、抽出採点器の追加）、`git merge origin/main` を実行した。実測：

```text
Auto-merging README.md
CONFLICT (content): Merge conflict in README.md
Auto-merging docs/minimal-core-and-ci.md
CONFLICT (content): Merge conflict in docs/minimal-core-and-ci.md
```

- 衝突したのは **`README.md` と `docs/minimal-core-and-ci.md` の現在値の数値行だけ**。`state/` の台帳、`tests/fixtures/` のスナップショット、`scripts/` のコードは**すべて自動マージ**された。
- すなわち §4.3 の予測は合成実験だけでなく、実際の並行開発でも再現した。
- 解決は「実測値（342 = 293 + 採点器10 + シャード39）に合わせ、main 側の一覧行を残し、`test_ledger_shards.py` の行を足す」だけだった。解決後のゲート8は 0 stale。

## 5. ゲート実測（移行後）

| コマンド | 実測 |
|---|---|
| `python3 -m unittest discover -s tests` | `Ran 342 tests in 5.936s` / `OK`（終了0） |
| `python3 gitswarm/benchmarks/benchmark.py --check` | `PASS: benchmark artifact matches a fresh execution`（0） |
| `python3 gitswarm/readout_sim.py --check` | `PASS: readout-sim artifact matches a fresh execution`（0） |
| `python3 scripts/validate_state.py` | `PASS: research ledgers valid (sources=23, evidence=86, claims=9, verifications=34, hypotheses=2, relations=0)`（0） |
| `python3 scripts/check_citations.py` | `summary: 22 arXiv source(s) checked, 1 skipped, 0 failure(s)`（0） |
| `python3 scripts/check_memo_citations.py` | `summary: 28 memo(s) scanned, 61 arXiv citation(s) checked, 3 skipped, 0 failure(s)`（0） |
| `python3 scripts/check_memo_ledger_refs.py` | `summary: 28 memo(s) scanned, 0 dangling reference(s), 5 archived ID reference(s)`（0） |
| `python3 scripts/check_doc_numbers.py` | `actual: tests=342 gates=8 sources=23 evidence=86 claims=9 verifications=34 hypotheses=2` / `summary: 2 doc(s) scanned, 0 stale number(s)`（0） |

検査7（`check_memo_ledger_refs.py`）は旧パスを残したまま **0 dangling**。`contributions/*.md` が参照する `state/*.jsonl` のパスは引き続き実在し、意味だけが「凍結ベース」に変わる。

## 6. 統合役へ渡す更新文案（README・docs）

### 6.1 README.md（台帳配置の記述／未適用）

`## 構成` の `state/` 行とスクリプト一覧に、次を追加する案。

```text
-state/                 研究台帳（JSONL。監査訂正済みデータ）
+state/                 研究台帳。2026-10-21 以降は凍結ベース（state/*.jsonl）と
+                       セッション別シャード（state/<台帳名>.d/）の和集合として読む。
+                       追記先はシャードで、ベースは書き換えない（scripts/ledger_store.py）

 scripts/ に追加：
+  ledger_store.py      台帳と書誌スナップショットの統合ビュー読み取り（ベース＋シャード）
+  ledger_digest.py     台帳レコードの内容ハッシュ（移行・revert の同一性証明。計測器）
 tests/ に追加：
+  test_ledger_shards.py        台帳シャードの読取・件数・参照整合性（39件）
```

`## 現在の状態` には、次の一文を足す案（数値行自体は現行のまま）。

```text
- 台帳は「凍結ベース＋シャード」の統合ビュー。件数はベースの行数ではなく統合ビューのレコード数
  （`scripts/check_doc_numbers.py` が算出）。旧 `state/*.jsonl` は凍結ベースであり全件一覧ではない。
```

### 6.2 docs（S1 §5 手順6 の担当分／未実施）

- `docs/record-id-scheme.md`：新規レコードの追記先を `state/<name>.d/` に変更。ID 採番は `new_id.py` のまま（統合ビューの ID と衝突確認する）。
- `docs/parallel-work-ownership.md`：§2.1 の追記手順に「1セッション1シャードファイル、既存シャードを編集しない」を追加。`state/` の分類（`ANY_SESSION_APPEND`）はそのままで良い。
- `docs/minimal-core-and-ci.md`：§2 のゲート4・8の説明に「台帳は統合ビュー」「件数は統合レコード数」を追記。テスト数は追随済み（342）。

## 7. 取り消し（revert）手順

移行は「読み手の切り替え」だけなので、**データを戻す必要がない**。したがって revert は単一で足りる。

1. マージコミットを1回 revert する：`git revert -m 1 <本PRのマージコミット>`。
2. `git diff <revert後> main -- state tests/fixtures` が空であること（データが動いていないので当然空）を確認。
3. 8ゲートを実行し、緑に戻ることを確認。

注意（将来シャードが存在する場合）：revert してもシャードファイルは残る。旧読み手は `state/*.jsonl` しか読まないため、**シャードのレコードが読まれなくなる**。その場合は (a) シャードも同じ revert で戻す（本PRの revert なら同時に戻る）、または (b) revert 前にシャードの内容をベースへ統合する、のいずれかを選ぶ。現時点でシャードは0件なので影響はない。

### 7.1 実測（`/tmp` の使い捨てクローンで、人間のマージを模擬）

main（`352f8fe`）に本ブランチを `--no-ff` でマージした木で全ゲートを実行し、その後に**1回だけ** `git revert -m 1 HEAD` した。

```text
=== merge the migration branch ===
merge commit: 667184f
=== gates on the merged tree ===
Ran 342 tests in 5.840s
OK
summary: 2 doc(s) scanned, 0 stale number(s)
PASS: research ledgers valid (sources=23, evidence=86, claims=9, ...)
=== single revert of the merge ===
revert commit: c918165
=== tree identity with the pre-migration main ===
diff vs pre-migration main (352f8fe): 0 lines
=== gates after revert ===
Ran 293 tests in 5.884s
FAILED (failures=2)
summary: 2 doc(s) scanned, 4 stale number(s)
PASS: research ledgers valid (sources=23, evidence=86, claims=9, ...)
```

- **単一 revert で元に戻る**（`git diff main HEAD` が 0 行）。移行で加わったファイル・変更はすべて消える。台帳データは動いていないので失うものがない。
- revert 後に再び赤になる2件は、**main が元から抱えていた陳腐化**（文書のテスト数 280 対 実数 293）であり、本移行が導入した失敗ではない。同じ PR で数値を追随したため、マージ後は緑になる。revert は「移行前の状態をそのまま戻す」ので、この既知の赤も一緒に戻る。
- 注意：将来シャードが存在する状態で revert すると、旧読み手はシャードを読まないためレコードが読まれなくなる。本PRの revert ならシャード（コミット済みなら）も同時に戻るが、他セッションが後から追加したシャードは残るので、§7 の (a)/(b) の判断が必要になる。

## 8. 残る未解決

1. **README の件数行が並行追記時の唯一の共有テキスト**（§4.3 で実測）。案：(a) 現行どおり統合時に1行解決する（衝突は1行、解決は機械的）、(b) 台帳件数を生成物（例：`state/` 配下の機械生成ファイル）へ移し、散文の現在値から外す、(c) 件数行の更新を統合役に限定する。本PRでは方式を変えていない（移行前からの性質で、悪化していない）。
2. **追記手順の文書更新が未実施**（§6.2）。`docs/record-id-scheme.md` 等は S1 の割当で統合役の担当。コードの docstring と本メモだけが現時点の規則の説明である。
3. **`check_doc_numbers.LEDGERS` は5台帳のまま**（`relations` を含まない）。移行前からの範囲で、今回の移行では変えていない。R3/R4 が REL を投入する前に、件数ゲートの対象に加えるかを決める必要がある。
4. **シャードディレクトリは空のまま git 管理されない**。最初の追記時に `mkdir -p state/<name>.d` が要る。規約はローダーの docstring と本メモにあるが、`docs/` への追記（§6.2）が済むまでは発見性が低い。
5. **旧パスが統合ビューそのものではないことの注記**（S1 §7）は未実施。§6.1 の文案で README に入れる想定。
6. **シャードに書かれなかった／マージされなかったレコードは検出できない**（S1 の既知の限界）。期待一覧のマニフェストは持たない。
7. **同一 ID・同一内容の重複もエラー**にしたため、意図的に同じレコードを2箇所へ置く運用はできない（意図した厳格化）。
8. 並行追記の実証は合成クローンのみ。実リポジトリでの使い捨てブランチ実験は行っていないため、**削除承認が必要なブランチは無い**。

## 9. 変更ファイル一覧

| ファイル | 種別 |
|---|---|
| `scripts/ledger_store.py` | 新規（共通ローダー） |
| `scripts/ledger_digest.py` | 新規（同一性証明の計測器） |
| `tests/test_ledger_shards.py` | 新規（39件） |
| `scripts/validate_state.py` | 変更（統合ビュー・重複の出所表示） |
| `scripts/new_id.py` | 変更（シャード ID との衝突確認） |
| `scripts/check_citations.py` | 変更（台帳／スナップショットの統合ビュー） |
| `scripts/check_memo_citations.py` | 変更（`load_fixture` 公開） |
| `scripts/check_memo_ledger_refs.py` | 変更（シャード ID の解決） |
| `scripts/check_doc_numbers.py` | 変更（件数＝統合レコード数） |
| `scripts/holdout_eval.py` | 変更（JSON 直読の廃止） |
| `README.md` / `docs/minimal-core-and-ci.md` | 変更（テスト数のみ。§0 の例外許可と §2.2 に基づく） |
| `state/*.jsonl` / `tests/fixtures/arxiv_metadata_snapshot.json` | **無変更** |
