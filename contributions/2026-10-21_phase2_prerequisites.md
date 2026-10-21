# Phase 2 の前提整備：ラウンド1で見つかった 4 件の修正

- 作成日：2026-10-21
- 種別：実装記録（修正のみ。新しいラウンドは回していない）
- 起点：`contributions/2026-10-21_round1_hypothesis_cycle.md` §3・§5 の 1〜4
- 設計：`docs/2026-10-21_hypothesis-cycle-automation.md` §13

---

## 0. 何を直したか（4 行）

1. `next_observations` を **`next_literature_questions`（検索できる問い）** と
   **`next_internal_measurements`（内部計測）** に分割した。
2. 計測器の出力を **`EVD` として起票**する規約を定め、ラウンド0の自己支持率測定を
   その第 1 号にした（`EVD-20261021-d88a`、出典は `SRC-004`）。
3. `refutation_condition.threshold`（任意・機械可読）を仮説と予測の両方に足した。
4. `gap_scan.py` が **`derived_from` を支持から除外**するようにした（既定）。
   `--include-derived-from` で旧来の数え方を再現できる。

---

## 1. 修正1：`next_observations` の分割

### 1.1 何が問題だったか

ラウンド1で、既存 4 仮説の `next_observations` を実際に読むと **1 件も文献で答えられる
問いになっていなかった**（自前実験 3・内部計測 1）。Phase 2 のクエリ生成器は、この欄から
検索語を作る設計なので、**入力が空同然**だった。

### 1.2 どう変えたか

| 欄 | 必須 | 内容 |
|---|---|---|
| `next_literature_questions` | **非空** | 文献検索で答えられる問い。S7 がクエリに変換する |
| `next_internal_measurements` | **存在（空リスト可）** | 自リポジトリで測るもの。「内部計測は無い」も決定として書かせる |

`next_observations` は**後方互換のため残した**（免除ファイルのレコードが持つ）。
非免除ファイルでは、旧欄だけ書いても新しい 2 欄の代わりにはならない
（テスト `test_legacy_next_observations_does_not_satisfy_the_split`）。

### 1.3 免除の粒度を 1 段増やした

ラウンド1の仮説（`state/hypotheses.d/2026-10-21-00a42038e2b6.jsonl`）は、
分割前の記録なので旧欄しか持たない。ここで 2 つの選択肢があった。

- **ファイル全体を免除する**：単純だが、`round` / `derived_from_evidence_ids` /
  `refutation_condition` の検査まで外れる。**その 3 つを実演している唯一のレコード**の
  検査を落とすのは後退である。
- **分割だけを免除する**：`state/cycle_exemptions.json` に `pre_split_files` を足し、
  `next_*` の分割に限って旧欄を許す。他の検査は残る。

後者を採った。免除リストは 2 本になる。

| リスト | 免除する範囲 |
|---|---|
| `legacy_files` | サイクル機構そのもの以前。全検査を免除 |
| `pre_split_files` | 分割以前。`next_*` の分割だけを免除し、他は検査する |

両方に同じファイルを書くとエラーになる（`test_pre_split_and_legacy_must_not_overlap`）。
曖昧な免除を作らないためである。

**残る限界**：`HYP-20261021-00b4` は今後も `next_literature_questions` を持たない。
Phase 2 のプランナは、この欄が無い仮説を**スキップして報告**する必要がある
（黙って `next_observations` を読むと、ラウンド1で見つけた欠陥を再生産する）。

---

## 2. 修正2：計測器の出力に ID を与える

### 2.1 何が問題だったか

ラウンド1の検索は「新規 4 仮説の支持の 94〜100% が生成元」という測定に動機づけられたが、
**その測定は台帳の ID を持たなかった**。そのため `QRY-20261021-8da2.derived_from` を
空にせざるを得ず、「台帳の穴に紐づかないクエリは採用しない」という S0 の規律が
初回から形骸化した。

### 2.2 どう変えたか

**規約**：計測器（`gap_scan` / `holdout_eval` / `prune_candidates` / 手計算の測定）の出力を
根拠に検索や仮説生成を行う場合、その測定を **`SRC-004`（本リポジトリ）を出典とする `EVD`**
として起票する。`quote_type: "measurement"`、`data_points` に数値を入れる。

**適用の第 1 号**：`EVD-20261021-d88a`。ラウンド0の測定（4 仮説 94〜100%、`HYP-001` 25%、
`HYP-002` 18%、241 件中 refute 0）を `data_points` に構造化して記録した。
`quote_type: "measurement"` 自体は前例がある（`EVD-20261020-ffec`、`readout_sim.py` の測定）。
新しいのは「**測定を検索計画の根拠にするなら EVD にする**」という規約の適用である。

**関係**：`REL-20261021-7d12` を `HYP-20261021-00b4` に対して `neutral` で置いた。
本測定は「本リポジトリの裁定が自己選好の生じる条件にある」ことを示すが、
**課題型依存そのものは支持も反証もしない**ため neutral である。
`derived_from: false`（この測定は検索の動機だが、仮説の内容を生成した観測ではない）。

**注意**：`QRY-20261021-8da2` は**シャードであり不変**なので、`derived_from` は空のまま
残る。これは当時の正確な記録である。以後のクエリは `EVD-20261021-d88a` を参照できる。

---

## 3. 修正3：`refutation_condition.threshold`（任意・機械可読）

```json
"refutation_condition": {
  "observable": "…", "would_refute": "…", "expected_if_true": "…",
  "threshold": {"metric": "residual_support_rate", "operator": "<=", "value": 0.7}
}
```

- **任意**。書けない仮説も有効である（文章の反証条件だけでも成立する）。
- **書いた場合は厳格に検査する**（`metric` 非空文字列、`operator` は 6 種、
  `value` は数値。bool は数値として扱わない）。**壊れた閾値は、閾値が無いより悪い**
  ——検査可能に見えて検査不能だからである。
- **ゲートにはしない**（書けないことを失敗にしない）。書けたものだけが
  `PRD` に昇格し、機械採点の対象になる。

補足：`PRD-20261021-1f70`（「10 件中 7 件以下」）は既にこの形に落ちる。
次ラウンドで `threshold` を付けて再登録するかは、予測の**書き換え**になるため
`superseded_by` を使う必要がある（登録済みの予測を黙って編集しない）。

---

## 4. 修正4：`gap_scan` が `derived_from` を除外する

### 4.1 何が問題だったか

`gap_scan` は verdict をそのまま数えていたため、`HYP-20261021-00b4` を
**support=3**（3 件とも生成元）と表示していた。README には「引用しないこと」と
注意書きを置いていたが、**道具が誤った数を出す状態を放置するのは注意書きでは直らない。**

### 4.2 どう変えたか

- **既定で除外**：`support` は `derived_from` が無いか false の REL だけを数える。
- **隠さない**：除外した件数を `support_derived_from` として併記する。
  両者を足すと旧来の数え方に一致する。
- **`unexplained` も同じ規則**：生成元からの支持しか無い観測は、独立には説明されていない。
- **`--include-derived-from`**：旧来の数え方を再現する（比較用）。
- 表示にも「うち生成元=N」を出す。

### 4.3 実測（2026-10-21）

| 対象 | 修正前 | 修正後 |
|---|---:|---:|
| `HYP-20261021-00b4` の support | 3 | **0**（うち生成元=3） |
| `unexplained` | 22 / 92 | **25 / 93** |
| `unassessed` | 1 / 92 | 1 / 93 |

`unexplained` が増えたのは、**生成元からの支持しか持たない 2 件**
（`EVD-20261021-539a`、`EVD-20261021-970a`）が正しく「独立には説明されていない」と
数えられるようになったためである。数字が悪化したのではなく、**以前の数字が甘かった**。

**既存 241 関係は変わらない**：`derived_from` を持たないため false と解釈される
（`test_absent_flag_counts_as_not_derived`）。

### 4.4 残る限界：フラグはラウンド1以降にしか無い

`derived_from` を書く規約ができたのはラウンド1からで、**それ以前の関係には 1 件も
フラグが無い**。したがって `gap_scan` の新しい既定が実際に除外しているのは
`HYP-20261021-00b4` の 3 件だけで、**既存 4 仮説の support（9f99=17 / fee7=25 /
4cdb=12 / a10b=8）は生成元を含んだまま**である。これは使い方の誤りではなく、
遡って書き換えない（追記専用）という規約の帰結である。

遡って同定する材料は台帳にある。ラウンド0の 4 仮説は `derived_from_evidence_ids` を
持たないが、**生成に使った EVD は `evidence_ids` に入っている**。実際
`EVD-20261021-d88a` の測定は `evidence_ids` との突き合わせで再現できた
（9f99 16/17、fee7 25/25、4cdb 12/12、a10b 8/8）。この再計算は Phase 3 の
`self_support.py` の仕事であり、`gap_scan` に推測を入れない——**推測でフラグを立てると、
ゲートが「記録が無い」ことを検出できなくなる**。

したがって Phase 2 の間、`gap_scan` の `support` は「**フラグされた生成元を除いた**支持」
であって「生成元をすべて除いた支持」ではない。後者が要るときは `self_support.py` を待つ。

---

## 5. 検証

```
python3 -m unittest discover -s tests   → Ran 504 tests / OK（480 → 504、+24）
python3 scripts/validate_state.py       → PASS
python3 scripts/gap_scan.py             → support の定義が変わる（上表）
python3 scripts/check_doc_numbers.py    → 0 stale（同期後）
```

新規テスト 24 件の内訳：サイクル記録 **+14 件**（分割 6・閾値 8・免除（`pre_split`）2。
うち 2 件は旧 `next_observations` の存在／非空を前提にしていたテストの置き換え）、
`gap_scan` **+10 件**。差し引きで 480 → 504。

---

## 6. Phase 2 に進める状態か

**進める。** ただし 2 つの注意が残る。

1. `HYP-20261021-00b4`（および免除ファイルの 5 仮説）は `next_literature_questions` を
   持たない。プランナは**未設定を報告してスキップ**すること。空リストと同じ扱いにして
   黙って先へ進むと、「問いが無いのに検索した」記録が生まれる。
2. 閾値を書けない反証条件は依然として人間か LLM の判定に依存する。
   **反証可能性の水準は、`threshold` を書けた仮説とそうでない仮説で違う。**
   この差は `gap_scan` ではなく Phase 3 の計測器が数える（ゲートにしない）。

Phase 2 の `next_queries.py` は、`next_literature_questions` を入力に、
`gap_scan --json` の `unexplained` と `unresolved` を重みとして使う設計にする。
本 PR でその入力は初めて揃った。
