# 台帳シャーディング移行の残課題（H1–H7）一括対応

- 作成日：2026-10-21
- 前提：`contributions/2026-10-21_ledger_sharding_migration.md`（方式Bの移行本体、PR #57）と、`contributions/2026-10-21_svm_single.md` の arXiv 引用を直した PR #60 が main に入っている状態から開始。
- 指示：人間が「残る宿題」7項目（H1〜H7）を**全て採用し、1 PR にまとめる**と決定。README の散文修正（H6）は `docs/parallel-work-ownership.md` §2 では統合役の担当だが、本作業はその指示により統合役の作業として実施した。
- 開始時の実測：`Ran 388 tests` / `OK`、8ゲートすべて緑（`origin/main` = `9830508`）。

## 1. 一覧と結果

| # | 課題 | 変更 | 状態 |
|---|---|---|---|
| **H3** | 回帰テストが旧定義（ベースの非空行数）のまま | `tests/test_check_doc_numbers.py` を統合ビュー比較へ | **完了** |
| **H1** | 規約文書が凍結ベースへの追記を指示 | `docs/record-id-scheme.md` §2、`docs/parallel-work-ownership.md` §2/§2.1、`docs/worker-prompts-next-stage-2026-10-21.md` の R4 | **完了** |
| **H2** | 「テキスト衝突は未解決」が実装と矛盾 | `docs/record-id-scheme.md` §4、`docs/parallel-work-ownership.md` §2.1 直後・§5・§6 | **完了** |
| **H4** | README の件数行が唯一の共有テキスト（案A+ を採用） | `scripts/sync_doc_counts.py` + テスト16件 | **完了** |
| **H5** | `check_doc_numbers.LEDGERS` に `relations` が無い | `LEDGERS` に追加、README の現況行に `relations=0` | **完了** |
| **H6** | README の構成記述が実態と違う | `state/`、`fixtures/`、scripts 一覧、現況節 | **完了** |
| **H7** | シャードの作り方が人の記憶頼み | `scripts/new_ledger_shard.py` + テスト16件 | **完了** |

## 2. H3：最初の台帳シャードで CI が赤になる問題（最重要）

### 2.1 症状（修正前の実測）

移行前の `tests/test_check_doc_numbers.py:76-83` は、チェッカーが統合ビューを数えるのに**ベースファイルの非空行数**と比較していた。`/tmp` のクローンに evidence シャードを1本だけ置いた実測：

```text
FAIL: test_ledger_counts_match_line_counts
AssertionError: 87 != 86 : evidence.jsonl
Ran 21 tests ... FAILED (failures=3)
```

連鎖して `RealRepoTest` の2件（README の `evidence=86` が実測87になる）も落ちる。**最初の台帳シャードを書いたセッションが、原因不明のまま赤になる**状態だった。

### 2.2 修正

比較を `scripts/ledger_store.load_jsonl`（統合ビュー）に変更し、テスト名も `test_ledger_counts_match_union_view` にした。エラーが混ざっていないことも検証する。

### 2.3 修正後の実測（同じ操作を再現）

```text
$ python3 scripts/new_ledger_shard.py evidence --create --date 20261021
state/evidence.d/<YYYY-MM-DD>-<12桁hex>.jsonl
$ # 1レコード書く
$ python3 scripts/validate_state.py
PASS: research ledgers valid (sources=23, evidence=87, claims=9, ...)
$ python3 scripts/sync_doc_counts.py
fixed README.md:65
  - - 台帳: sources=23 / evidence=86 / ...
  + - 台帳: sources=23 / evidence=87 / ...
synced: 1 number(s) changed, 0 stale number(s) remaining
$ python3 -m unittest discover -s tests
Ran 420 tests ... OK
$ 8ゲートすべて exit=0
```

**シャードを書く → 同期コマンド1回 → 全緑**、という流れになった。H4 が無い場合、この最後の1手（README の数値）が手作業になり、並行セッションと衝突する。

補足（仕様どおりの挙動で、欠陥ではない）：最初に書いた合成レコードは `quote_type` を持っておらず、`tests/test_minimal_core.py::test_every_evidence_declares_quote_type` が落ちた。これはスキーマ必須ではないが本リポジトリの慣習（全 EVD が quote_type を宣言する）を検査するテストである。新規セッションは EVD に `quote_type` を付ける必要がある。本作業では台帳にレコードを追加していないため、この点は変更していない。

## 3. H4：`scripts/sync_doc_counts.py`

ゲート8（`check_doc_numbers.py`）が stale と報告した**行の数値だけ**を書き換え、その後ゲート8を再実行する。残れば終了1。

```sh
python3 scripts/sync_doc_counts.py            # README と docs/minimal-core-and-ci.md
python3 scripts/sync_doc_counts.py --dry-run  # 変更予定の表示のみ
```

設計上の性質（テストで固定）：

- 検出は**ゲート8と同じコード**（`check_doc_numbers.scan_file`）を使う。したがって書いた値は定義上ゲート8を通る。
- 触るのは**指摘された行だけ**。散文・行順・余白は保存される。
- 引用ブロック（`>`）と `drift-ok` 行はゲート8が見ないので、ここでも変更しない。
- `evidence=860` のような値は**数全体**を置換する（`86` に続く `0` を残さない）。
- per-file 件数は、その行の別の数値を巻き込まない。
- `relations=` も他5台帳と同じく同期する。

### 3.1 並行追記の衝突を「機械的に」解決できることの実測

`/tmp` の合成リポジトリで、2ブランチがそれぞれ evidence を追記し、件数行も更新した場合：

| 場合 | 結果 |
|---|---|
| 同じ差分（同じ値になる） | `README.md` は自動マージ。ただし値は実測より小さいので、マージ後に `sync_doc_counts.py` で正す（実測：88 → 89 に修正、全緑） |
| 違う差分（90 と 92 になる） | `Auto-merging README.md` → `CONFLICT (content)`。**衝突ファイルは `README.md` のみ** |

違う差分の場合の解決手順（実測で緑を確認）：

```sh
git checkout --ours README.md     # どちらでもよい。値は直後に上書きされる
python3 scripts/sync_doc_counts.py # 実測値へ機械的に修正（90 -> 92）
git add -A && git commit --no-edit
# -> validate_state PASS / check_doc_numbers 0 stale / Ran 420 tests OK
```

台帳側は相変わらず衝突しない（別パスの追加のみ）。**残る衝突は数値1行だけで、判断は不要**になった。

## 4. H7：`scripts/new_ledger_shard.py`

```sh
python3 scripts/new_ledger_shard.py --list
python3 scripts/new_ledger_shard.py evidence --create     # 空の .jsonl を作る
python3 scripts/new_ledger_shard.py arxiv_snapshot --create  # entries:[] の .json を作る
python3 scripts/new_ledger_shard.py evidence --date 20261021
```

- 名前は `scripts/ledger_store.py` が読む正規表現を**そのまま使って**生成するので、規則違反の名前を作れない。
- 12桁hex（48ビット）は `secrets.token_hex(6)`。日付だけの命名は同日並行で衝突するため不可（`--date` で日付のみ固定できる）。
- `--create` は**ディレクトリも作る**（git は空ディレクトリを追跡しないため、その台帳の最初のシャードは置き場所が無い）。スナップショットは `entries: []` と由来欄（`captured_at` / `capture_method` / `capture_note`）を持つ雛形を書く。
- 既に「日付で始まるのに読めないファイル」がある場合は警告する（壊れたファイルの隣に正しいシャードを足して問題を隠さない）。
- `README.md` など日付で始まらないファイルは警告しない。

実測（`--list`）：

```text
arxiv_snapshot   base=tests/fixtures/arxiv_metadata_snapshot.json      shard_dir=exists shards=1
claims           base=state/claims.jsonl                               shard_dir=missing shards=0
evidence         base=state/evidence.jsonl                             shard_dir=missing shards=0
...
```

## 5. H1・H2・H6：文書の追随

| 文書 | 変更 |
|---|---|
| `docs/record-id-scheme.md` §2 | **追記先**を明記（`state/<台帳名>.d/` のシャード、`new_ledger_shard.py`、スナップショットも同じ規則、検証手順）。採番の説明はそのまま |
| `docs/record-id-scheme.md` §4 | テキスト衝突を**未解決 → 解決**（方式B、3ブランチ衝突0の実測を引用）。共有ファイル行に「数値行は `sync_doc_counts.py` で機械同期」を追記 |
| `docs/record-id-scheme.md` §6 | 変更履歴に1行 |
| `docs/parallel-work-ownership.md` §2 | `state/` 行を6台帳に直し、追記先がシャードであることを明記。補足の追記手順を3ステップ（シャード作成 → 採番 → 検証＋数値同期）に書き換え |
| 同 §2.1 | 操作表を「シャードへの追記（凍結ベースへは追記しない）」に。検査が統合ビュー対象であることを明記 |
| 同 §2.1 直後・§5・§6 | テキスト衝突を**解決**へ。数値行は運用で吸収する旨 |
| 同 §5 の残項目 | 「1レコード1ファイル分割は未実施」を、方式Bで解消済み・1レコード1ファイルは採用しない（理由つき）に更新 |
| `docs/minimal-core-and-ci.md` | ゲート4の説明に統合ビュー、§2.2 の件数表を「統合ビューのレコード数（6台帳、`relations` を含む）」に。テスト数は 420 に追随 |
| `docs/worker-prompts-next-stage-2026-10-21.md` | S3 の前提プレースホルダを「方式B（2026-10-21 決定・実施済み）」に。S1 依頼時点の前提節に「同日の移行で解消済み」の注記。**R4 の先頭に追記先の注記**（`state/relations.d/` を使い、凍結ベースは書き換えない） |
| `README.md` | `state/` の説明を凍結ベース＋シャードに、`fixtures/` に `.d/`、scripts 一覧に `new_ledger_shard.py` / `ledger_store.py` / `ledger_digest.py` / `merge_ledgers.py` / `sync_doc_counts.py`、現況節に `relations=0` と統合ビューの注記、テスト一覧に新規2ファイル |

`docs/incomplete-work-audit-2026-10-20.md` は**書き換えていない**。2026-10-20 時点の監査記録であり、「未解決」はその時点の事実である（本リポジトリは履歴文書を遡って書き換えない方針。`check_doc_numbers` の対象外でもある）。

## 6. ゲート実測（本PRの作業ツリー）

| コマンド | 実測 |
|---|---|
| `python3 -m unittest discover -s tests` | `Ran 420 tests` / `OK` |
| `python3 gitswarm/benchmarks/benchmark.py --check` | PASS |
| `python3 gitswarm/readout_sim.py --check` | PASS |
| `python3 scripts/validate_state.py` | PASS（sources=23, evidence=86, claims=9, verifications=34, hypotheses=2, relations=0） |
| `python3 scripts/check_citations.py` | 22 checked, 1 skipped, 0 failure |
| `python3 scripts/check_memo_citations.py` | 31 memos, 64 citations, 0 failure |
| `python3 scripts/check_memo_ledger_refs.py` | 31 memos, 0 dangling, 5 archived |
| `python3 scripts/check_doc_numbers.py` | 0 stale（tests=420, gates=8） |

台帳（`state/*.jsonl`）と書誌スナップショットのベースは無変更（レコードの追加・削除・書換え 0 件）。

## 7. 残る未解決

1. **数値行は依然として共有テキスト**である。衝突は消えていないが、解決が「片側採用＋コマンド1回」で機械化された。件数を生成物へ移す案（旧 §8 の案C）は採らない：生成物も共有テキストで、衝突が「再生成」に置き換わるだけである。
2. **`quote_type` の慣習がスキーマに無い**（§2.3）。新規 EVD は `tests/test_minimal_core.py` が要求するが `schemas/evidence.json` の `required` には入っていない。スキーマへ昇格させるかは別判断。
3. **ベースが凍結されたことの機械的な証明は無い**。`state/*.jsonl` を書き換えても現在のゲートは緑のまま通る（スキーマ的に妥当なため）。凍結を示すハッシュ・マニフェストの導入は、正当な訂正にも1手間増やすので本PRでは見送った。必要なら `tests/fixtures/` に固定ハッシュを置く案がある。
4. **シャードの「書き忘れ・マージ忘れ」は検出できない**（S1 の既知の限界）。期待一覧のマニフェストは持たない。
5. **R4（関係台帳の投入）は未実施**。`relations=0` のままで、`gap_scan` の対象も空である。追記先の注記は入れたが、実行は別作業。

## 8. 変更ファイル

| ファイル | 種別 |
|---|---|
| `scripts/new_ledger_shard.py` | 新規（H7） |
| `scripts/sync_doc_counts.py` | 新規（H4） |
| `tests/test_new_ledger_shard.py` | 新規（16件） |
| `tests/test_sync_doc_counts.py` | 新規（16件） |
| `tests/test_check_doc_numbers.py` | 変更（H3） |
| `scripts/check_doc_numbers.py` | 変更（H5: `LEDGERS` に `relations`） |
| `docs/record-id-scheme.md` | 変更（H1・H2） |
| `docs/parallel-work-ownership.md` | 変更（H1・H2） |
| `docs/worker-prompts-next-stage-2026-10-21.md` | 変更（H1） |
| `docs/minimal-core-and-ci.md` | 変更（H2・件数） |
| `README.md` | 変更（H5・H6・件数） |
| `state/*.jsonl` / `tests/fixtures/arxiv_metadata_snapshot.json` | **無変更** |
