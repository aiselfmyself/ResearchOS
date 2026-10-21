# JSONL 台帳の3方向マージ道具

作成日: 2026-10-21

## 設計判断・使い方

S1 の `contributions/2026-10-21_ledger_sharding_design.md` を先に確認した。
推奨B（不変ベース＋バッチ・シャード＋統合ビュー）を置き換えず、現在の単一JSONLや抽出済みビューを手動統合する道具とする。シャード探索、Git driver、CIへの接続、台帳のスキーマ検査は非目標。S1の将来のシャード検査では同内容重複もエラーにすべきだが、本ツールでは依頼仕様どおりdedupする。この道具をシャード検査器として流用してはならない。

```sh
python3 scripts/merge_ledgers.py --base /tmp/base.jsonl \
  --ours /tmp/ours.jsonl --theirs /tmp/theirs.jsonl \
  --id-key evidence_id --out /tmp/merged.jsonl
```

- `--out` 省略時は標準出力。診断は標準エラー。
- 同じIDの全出現（base内・片側内の重複も含む）を比較し、異内容ならすべての出所・行番号・行内容を列挙して終了1。baseからの片側編集でも自動解決しない。
- 削除はどちらか一方にbaseのIDが欠ければ検出し、通常は終了1。`--allow-delete` は明示的な delete-wins（いずれかで消えたbase IDを結果から除く）。許可した削除も報告する。異内容競合はこの指定でも許可しない。
- baseの初出順、次に新規IDの文字列昇順。非空の文字列IDを要求し、旧／新ID形式の検証・採番はしない。
- 内容比較ではオブジェクトのキー順と空白は無視し、配列順・型・数値表記は区別する。JSON数値を独自文字列型で保持するため、巨大整数や浮動小数点丸めによる誤dedupを避ける。
- 行はbase、ours、theirsの優先順で初出の原文を保持（CRLFも保持）。空行は無視し、末尾改行がない行の後にレコードを足すときだけ区切り改行を補う。
- 不正JSON、オブジェクト以外、ID欠落／不正型、非標準NaN等、オブジェクト内キー重複は終了2。構文診断には入力パスと行番号を含める。I/Oエラーも終了2。
- 入力3本の検証と全競合の収集後にだけ出力を開く。意味競合・入力エラーでは既存の出力も上書きしない。書き込み中のI/O障害に対する原子的置換までは提供しない。

## 実台帳のドライラン（履歴上の実際の分岐）

PR #49 の「main取り込み」コミット `1e042a1cc07a6962ca1755376ffc00f541170ebb` の両親を用いた。最終PRマージ時の親同士では既に取り込み済みで片側が祖先になるため、実際に分岐していた取り込み前の両側を選んだ。

- base（merge-base）: `a933556cfa9533bdf9b82e30a44fe55f87dd7fb2`
- ours（PR側）: `fae2ef55d2804ca0499e015ee508f2cb0dee78eb`
- theirs（当時のmain側）: `773391d284ce12671a020ea1ff97d29c93da62ee`

`git show REV:<台帳パス>` で各版を `/tmp/researchos-ledger-diverged-3l6nxia4/` に抽出し、上記CLIを5台帳それぞれのIDキーで実行した。出力も同じ `/tmp` 配下の `NAME-merged.jsonl`。期待件数は別途 `json.loads` で読んだ3入力のID集合和から計算した。作業ツリーの実台帳は変更していない。

| 台帳 | base | ours | theirs | ours新規 | theirs新規 | 期待和集合 | 出力実測 | 終了 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| sources | 20 | 21 | 22 | 1 | 2 | 23 | 23 | 0 |
| evidence | 68 | 73 | 81 | 5 | 13 | 86 | 86 | 0 |
| claims | 9 | 9 | 9 | 0 | 0 | 9 | 9 | 0 |
| verifications | 31 | 33 | 32 | 2 | 1 | 34 | 34 | 0 |
| hypotheses | 2 | 2 | 2 | 0 | 0 | 2 | 2 | 0 |

5台帳とも競合・削除診断なし。特に当時テキスト衝突した verifications の双方の追加（2＋1）が残り、期待34件と一致した。

## 回帰テストと全ゲートの実測

新規 `tests/test_merge_ledgers.py` は合成データだけを使用。両側追加、同一内容dedup、全競合列挙、入力内競合、削除拒否／許可、削除許可時の編集拒否、2回実行の一致、行原文・改行保持、不正JSON・ID、空入力、旧新ID混在、JSON型の区別、標準出力・I/Oエラーを検証する。

単独実行 `python3 -m unittest discover -s tests -p test_merge_ledgers.py` は13件成功。

| 指定ゲート | 実測 |
|---|---|
| `python3 -m unittest discover -s tests` | 終了1、256件中3件失敗（下記） |
| `python3 gitswarm/benchmarks/benchmark.py --check` | 終了0、fresh execution一致 |
| `python3 gitswarm/readout_sim.py --check` | 終了0、fresh execution一致 |
| `python3 scripts/validate_state.py` | 終了0、台帳正常 |
| `python3 scripts/check_citations.py` | 終了0、22件照合・失敗0 |
| `python3 scripts/check_memo_citations.py` | 終了0、25メモ・61引用照合・失敗0 |
| `python3 scripts/check_memo_ledger_refs.py` | 終了0、25メモ・dangling 0 |
| `python3 scripts/check_doc_numbers.py` | 終了1、既存文書の総テスト数4箇所が古い |

### DoDと変更範囲の衝突（未解決）

既存文書は総テスト数243件と記載している。13件追加後の実数256件を検査器が正しく検出し、READMEの3箇所および docs/minimal-core-and-ci.md の1箇所を拒否する。unittest内でも同じ理由で `test_check_doc_numbers.RealRepoTest` の2件と `test_holdout_eval.RealRepoTest` の doc_numbers サブテスト1件が失敗する。

「新規3ファイルのみ」「既存文書変更禁止」「新規回帰テスト」「全ゲート緑」は現行の総数固定検査では同時に満たせない。テストを発見不能にしたり検査器を迂回したりせず、既存ファイルを変更しない制約を優先した。全ゲート緑のDoDは未達であり、CIが赤のまま自動マージしてはならない。解消には別途、既存2文書の件数更新を許可するか、統合側で更新する必要がある。
