# ID18 候補 B・C・D 本文確認（arena/007d7f60）のシャード変換記録

- 日付：2026-10-21
- 変換元：`arena/007d7f60-researchos` のコミット `89a6971`
- 変換元の親／現在の `main` との merge-base：`683df35`
- 変換先セッション：`arena/52267199-researchos`
- 目的：台帳凍結前に作られた原ブランチの内容を、凍結ベース `state/sources.jsonl` と `state/evidence.jsonl` を書き換えずに、現在のシャード形式で取り込む。

## 1. 結論

原ブランチの実質内容は、次の形で取り込んだ。

1. 新規 EVD 2 件は、原ブランチの JSON レコードをそのまま `state/evidence.d/2026-10-21-bd9cc94c8bb9.jsonl` に置いた。
2. 既存レコードへの変更 6 件は、同 ID の重複レコードとしては置かず、対象への `source_check` VER 6 件を `state/verifications.d/2026-10-21-efaf0684d2db.jsonl` に追記した。各 VER の `rationale` には、原ブランチが置換・追加予定だった文をそのまま含めた。
3. `contributions/2026-10-21_id18_paper_search.md` の §8.5 を取り込んだ。冒頭の台帳反映文だけは、凍結ベースを実際に更新しない変換後の表現に合わせて書き換えた。本文確認の実質的な所見と判定は原ブランチのままとした。
4. 凍結ベースへの差分は 0 行である。新しい REL verdict はこの変換では推論・追加していない。

変換後の統合ビュー件数は、sources=23、evidence=88、claims=9、verifications=40、hypotheses=6、relations=235 である。

## 2. 原ブランチ差分の棚卸し

`683df35` から `89a6971` へのレコード単位差分は次のとおりだった。変換前の現在の `main` では、変更対象 6 件はいずれも親バージョンのままで、新規 EVD 2 件は未収録だった。

| 台帳 | 原ブランチの差分 | 数 |
|---|---|---:|
| sources | 追加・削除なし。3 件の `note` だけを、abstract 中心の旧文から HTML v1 本文の読了範囲・確認結果へ置換 | 3 |
| evidence | 新規 EVD を追加 | 2 |
| evidence | 3 件の `section_or_page` を拡張し、`interpretation` 末尾へ「〔本文確認〕…」を追加。`excerpt` と `confidence` は不変 | 3 |
| ID18 メモ | §8.5「候補 B・C・D の本文確認」を追加 | 1 |

候補と対象レコードの対応は、候補 B が `SRC-20261021-fb4a`／`EVD-20261021-e06c`、候補 C が `SRC-20261021-9a02`／`EVD-20261021-589c`、候補 D が `SRC-20261021-f186`／`EVD-20261021-d78f` である。

## 3. 変換対応表

### 3.1 新規 EVD

| 追加レコード | 出典 | 場所 | confidence | 変換先 |
|---|---|---|---|---|
| `EVD-20261021-1439` | `SRC-20261021-fb4a` | §4.1 Holding the Model Fixed（HTML v1、本文） | medium | `state/evidence.d/2026-10-21-bd9cc94c8bb9.jsonl` |
| `EVD-20261021-8ebb` | `SRC-20261021-f186` | §4.1 Pass Rate、Table 2（HTML v1、本文） | medium | `state/evidence.d/2026-10-21-bd9cc94c8bb9.jsonl` |

両 ID は原ブランチで採番済みであり、現在の統合ビューに同 ID は無かったため、そのまま再利用した。再採番はしていない。

### 3.2 既存 SRC の `note` 置換

| 対象 | 変換後 VER | result | 表現 |
|---|---|---|---|
| `SRC-20261021-fb4a` | `VER-20261021-e038` | pass | 原ブランチの置換後 `note` 全文を `rationale` に保存 |
| `SRC-20261021-9a02` | `VER-20261021-8b40` | pass | 原ブランチの置換後 `note` 全文を `rationale` に保存 |
| `SRC-20261021-f186` | `VER-20261021-78d5` | pass | 原ブランチの置換後 `note` 全文を `rationale` に保存 |

書誌フィールドは原ブランチでも変更されていなかったため、SRC への検証対象は本文確認の範囲と結論に限られる。

### 3.3 既存 EVD の場所拡張と解釈追記

| 対象 | 変換後 VER | result | 表現 |
|---|---|---|---|
| `EVD-20261021-e06c` | `VER-20261021-2e00` | pass | 拡張後 `section_or_page` と追記文を `rationale` に保存 |
| `EVD-20261021-589c` | `VER-20261021-3e8b` | pass | 拡張後 `section_or_page` と追記文を `rationale` に保存 |
| `EVD-20261021-d78f` | `VER-20261021-2f0f` | warn | Table 2 との整合に加え、Table 4 の検算不一致を明示 |

`EVD-20261021-d78f` の `warn` は、既存 excerpt 自体の誤りを意味しない。本文確認で Table 2 との整合が取れた一方、同じ論文の Table 4 が Table 2 と 1–2 件ずれるため、引用時に表を区別する必要があるという警告である。

## 4. なぜ同 ID の更新版レコードをシャードへ置かないか

現在の `scripts/ledger_store.py` は、凍結ベースとシャードを ID の単純な和集合として読む。更新版レコードを同 ID でシャードへ入れると「新しい方が勝つ」のではなく重複 ID として検証に失敗する。反対に凍結ベースを直接書き換えれば、シャード変換という今回の要件と現在の凍結規律に反する。

したがって今回は、既存レコードの本文確認を追記専用の VER として表した。これは汎用的なレコード修正 overlay を新設するより小さく、原ブランチの文面も失わない。

ただし限界は明示する。凍結ベースの対象 SRC／EVD だけを読むと、`note`、`section_or_page`、`interpretation` は旧文のままである。VER の `rationale` はローダによって対象フィールドへ合成されない。対象レコードを使う際は、対応 VER と `contributions/2026-10-21_id18_paper_search.md` §8.5 を併せて読む必要がある。将来、汎用的な record-amendment overlay が採択される場合は、今回の VER 6 件が移行元になる。

## 5. 関係（REL）についての残件

この変換は原ブランチの保存が目的であり、新しい仮説関係の裁定は追加していない。そのため新規の `EVD-20261021-1439` と `EVD-20261021-8ebb` は、変換直後の `scripts/gap_scan.py` ではまだ REL の無い evidence として数えられる。実測は unassessed 2 / 88（2.3%）、unexplained 22 / 88（25.0%）、provisional 58 / 88、non-provisional 30 / 88 である。これは隠れた欠落ではなく、次の関係 backfill の対象として残したものである。既存 3 EVD に付いている REL は変更していない。

## 6. 検証結果

本変換では CI の 8 ゲート相当と、件数同期・カバレッジ計測・凍結ベース無変更の確認を実行した。

- `scripts/validate_state.py`：PASS（sources=23、evidence=88、claims=9、verifications=40、hypotheses=6、relations=235）。
- unittest：437 件成功。
- `gitswarm/benchmarks/benchmark.py --check` と `gitswarm/readout_sim.py --check`：いずれも PASS。
- `scripts/check_citations.py`：22 件確認、1 件 skip、失敗 0。
- `scripts/check_memo_citations.py`：38 メモ、67 件確認、3 件 skip、失敗 0。
- `scripts/check_memo_ledger_refs.py`：38 メモ、dangling reference 0。
- `scripts/check_doc_numbers.py`：stale number 0。台帳件数の現在値行は `scripts/sync_doc_counts.py` で同期し、`scripts/gap_scan.py` の散文値も README の現況節へ反映した。
- `git diff -- state/sources.jsonl state/evidence.jsonl`：出力なし。凍結ベース 2 ファイルは変更していない。

原ブランチ自体の削除は破壊的操作であり、本変換の範囲外である。本変換がマージされた後は、原ブランチの内容は本記録とシャードによって置き換えられたものとして扱える。

## 付録：原ブランチが対象フィールドへ入れる予定だった文

以下は監査用の転記であり、同じ文が対応 VER の `rationale` にも入っている。

### SRC の置換後 `note`

- `SRC-20261021-fb4a`：「2026-10-21 に本文（HTML v1, chunk 0・2 の §3.2、§4.1–4.2）を確認。EVD-e06c の 29.8pp は §4.1 で確認（単一モデル値）。Holm 検定 6/9 も §4.2 で確認。」
- `SRC-20261021-9a02`：「2026-10-21 に本文（HTML v1, chunk 0・1・4・5、§1、§2、§3.2、§5.1、§5.2、§5.3）を確認。EVD-589c の範囲（系 0.935–0.994、モデル 0.148–0.841）は §5.1 で確認。『σM²−σA² favors neither direction (posterior ~50%)』と『84%』は §5.2 で確認。OnlineMind2Web の 0.148→0.153（§5.3）も確認。本文の Table 2（HAL 設計）は確認済み。」
- `SRC-20261021-f186`：「2026-10-21 に本文（HTML v1, chunk 0・1・2、§3.1–3.5、§4.1–4.7、Table 2–6）を確認。abstract の『0–8 pp』は Table 2 のペア差と整合（本文は『harness range 2–8 pp』）。ただし本文 Table 4 の solved 数は Table 2 と 1–2 件ずれ、検算不一致（EVD-8ebb）。モデル 2 のみ、n=50。」

### EVD の拡張後 `section_or_page` と追記文

- `EVD-20261021-e06c`：場所は「Abstract; §4.1 Holding the Model Fixed（本文確認済み 2026-10-21）」。追記は「〔本文確認〕§4.1 で 29.8pp は claude-3-5-sonnet 単一モデルの値、モデル内中央値は 15.6pp と確認（EVD-1439 参照）。」
- `EVD-20261021-589c`：場所は「Abstract; §5.1 Reliability depends on the measurement goal（本文確認済み 2026-10-21）」。追記は「〔本文確認〕§5.1 で『estimated system reliability ... [0.935, 0.994], whereas model reliability is ... [0.148, 0.841]』（9 ベンチマーク）と確認。§5.2 で σM²−σA² は約 50%、task 固有の scaffold 分散が model を上回る確率 84% を確認。ただし『reliability』は観測データの decision study（ベイズ G-theory）の値で、統制格子の分散比ではない。」
- `EVD-20261021-d78f`：場所は「Abstract; §4.1 Pass Rate Table 2; §4.7 Table 6（本文確認済み 2026-10-21）」。追記は「〔本文確認〕§4.1 Table 2 と整合（EVD-8ebb 参照）。ただし本文 Table 4 と 1–2 件ずれる検算不一致あり。」
