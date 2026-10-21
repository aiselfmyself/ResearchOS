# 新規 EVD 2 件の関係 backfill（ID18 本文確認分）

- 日付：2026-10-21
- 実施理由：人間の指示により、`contributions/2026-10-21_id18_shard_conversion.md` §5 で残件とした新規 EVD 2 件へ REL を付ける
- 対象：`EVD-20261021-1439`、`EVD-20261021-8ebb`
- 追記先：`state/relations.d/2026-10-21-9792f6bc53d0.jsonl`
- 追記件数：6 件
- 既存レコードの書き換え・削除：なし

## 1. 結論

既存の R3／R4 の方式に合わせ、既存 2 仮説については両 EVD とも裁定し、新仮説については主題が直接関係する `HYP-20261021-9f99` だけを裁定した。

| REL | EVD | HYP | verdict |
|---|---|---|---|
| `REL-20261021-7029` | `EVD-20261021-1439` | `HYP-001` | neutral |
| `REL-20261021-af0d` | `EVD-20261021-1439` | `HYP-002` | neutral |
| `REL-20261021-d730` | `EVD-20261021-1439` | `HYP-20261021-9f99` | support |
| `REL-20261021-f9b3` | `EVD-20261021-8ebb` | `HYP-001` | neutral |
| `REL-20261021-45b1` | `EVD-20261021-8ebb` | `HYP-002` | neutral |
| `REL-20261021-ba06` | `EVD-20261021-8ebb` | `HYP-20261021-9f99` | unresolved |

これにより `scripts/gap_scan.py` の unassessed は 2 / 88 から 0 / 88 になった。ただし、これは対象ペアへ裁定を記録したという意味であり、ID18 の科学的な未解決性が解消したという意味ではない。

## 2. 裁定方法

### 2.1 対象ペアの選び方

- `HYP-001` と `HYP-002` は、既存 86 EVD のすべてに REL があるため、新規 2 件にも付ける。
- 新仮説 4 件は全 EVD との直積ではなく、主題が関係する観測だけに付ける既存方式を踏襲する。
- 両 EVD はモデル×ハーネスの広がりそのものを扱うため、`HYP-20261021-9f99` を対象にする。
- `HYP-20261021-fee7`（評価ゲート／OOD）、`HYP-20261021-4cdb`（H×O 分離による発見）、`HYP-20261021-a10b`（文脈・長文出力の限界）については、両 EVD がその機構や介入を測っていないため、行を作らない。行が無いことは refute ではなく、既存方式どおり「裁定対象として選んでいない」ことを意味する。

### 2.2 既存の親 EVD との整合

同じ出典・同じ所見を abstract から登録した既存 EVD には、すでに次の裁定がある。

| 既存 EVD | `HYP-001` | `HYP-002` | `HYP-20261021-9f99` |
|---|---|---|---|
| `EVD-20261021-e06c` | neutral | neutral | support |
| `EVD-20261021-d78f` | neutral | neutral | unresolved |

今回の 2 件は本文確認による詳細化であり、主題は変わらない。したがって骨格は親 EVD と揃え、本文で新たに分かった限定条件を rationale に反映した。

## 3. 個別裁定

### 3.1 `EVD-20261021-1439`

対象は SWE-bench リーダーボードにおけるモデル内 scaffold 範囲である。

- `HYP-001`：**neutral**。外部化された構造化メモリと単一セッションの累積探索効率・再現性を比べていない。
- `HYP-002`：**neutral**。同質ワーカーの多数決や共通モード障害を測っていない。
- `HYP-20261021-9f99`：**support**。モデル内 scaffold 範囲の中央値 15.6pp が上位 30 件全体の広がり 8.8pp を上回る。additive fit でも scaffold 効果範囲 37.6pp と model 効果範囲 47.9pp が同オーダーであり、近接能力群ではモデル単体ではなく結合系で評価すべきという主張に合う。

限定条件も rationale に残した。これは観測データであり、著者自身が因果効果や分散説明率ではないと明記している。また `EVD-20261021-e06c` と同一出典・同一所見の詳細化なので、support 行が増えたことを独立した支持証拠が増えたことと同一視してはならない。

### 3.2 `EVD-20261021-8ebb`

対象は 2 モデル×3 ハーネスの通過率である。

- `HYP-001`：**neutral**。外部化メモリの有無による累積探索効率・再現性の比較ではない。
- `HYP-002`：**neutral**。多数決ノミネーションや共通モード障害の観測ではない。
- `HYP-20261021-9f99`：**unresolved**。Table 2 ではモデル内ハーネス範囲が 2–8pp、ハーネス内モデル範囲が 4–10pp だが、モデルは 2 件のみで、各セルの 95% 信頼区間は約 ±14pp ある。本文も大半のペア差は 0 と区別できないとしており、Table 4 との 1–2 件の不一致もある。効果比 R の領域を判定するにはモデル軸と検出力が不足する。

`EVD-20261021-d78f` と同一出典・同一所見の本文確認であるため、この unresolved も独立した再現結果ではない。

## 4. `observation_key` を追加しない理由

今回は `state/evidence_keys.jsonl` とそのシャードへ新しい注釈を加えていない。

- `EVD-20261021-1439` は、すでに `model_harness_joint_dominance_and_rank_inversion` のキーを持つ `EVD-20261021-e06c` と同一出典・同一所見である。
- `EVD-20261021-8ebb` は `EVD-20261021-d78f` と同一出典・同一所見である。
- R4 では、同一論文の重複登録へ共通キーを付けると独立した再遭遇に見えるため、その束ねを採用しなかった。

したがって両 EVD は `gap_scan` 上 provisional のままである。将来、別出典で同じ観測が独立に得られた場合は、その時点でキー注釈を検討する。

HYP レコードの `evidence_ids` も書き換えていない。既存 HYP でもこの欄は REL の support 全件と同期した台帳ではなく、HYP–EVD のペア裁定は REL 側に記録する。

## 5. 前後比較

| 指標 | backfill 前 | backfill 後 |
|---|---:|---:|
| relations | 235 | 241 |
| unassessed | 2 / 88（2.3%） | 0 / 88（0.0%） |
| unexplained | 22 / 88（25.0%） | 21 / 88（23.9%） |
| provisional / non-provisional | 58 / 30 | 58 / 30 |
| support / neutral / unresolved / refute | 84 / 134 / 17 / 0 | 85 / 138 / 18 / 0 |
| `HYP-20261021-9f99` の support / unresolved | 16 / 1 | 17 / 2 |

unexplained が 1 件だけ減ったのは、`EVD-20261021-1439` に support が付いた一方、`EVD-20261021-8ebb` は neutral と unresolved のみで support が無いためである。

## 6. 検証

- `scripts/validate_state.py`：PASS（sources=23、evidence=88、claims=9、verifications=40、hypotheses=6、relations=241）。
- `scripts/gap_scan.py`：unassessed 0 / 88、unexplained 21 / 88、provisional 58 / 88、non-provisional 30 / 88。
- `scripts/sync_doc_counts.py` で README の台帳件数を同期し、gap_scan の散文値も現況節へ反映した。
- CI の 8 ゲート相当をすべて実行し、unittest 437 件、benchmark／readout の再現確認、台帳検証、書誌照合、メモ引用照合、台帳参照検査、文書数値検査がすべて PASS した。
- REL 全 241 件について、relation_id の重複 0、（hypothesis_id, observation_id）ペアの重複 0 を別途確認した。
