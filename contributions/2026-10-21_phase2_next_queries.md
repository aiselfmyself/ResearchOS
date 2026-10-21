# Phase 2：S0/S7 のクエリ計画（`next_queries.py`）

- 作成日：2026-10-21
- 種別：実装記録（計画の生成まで。**検索は実行していない**）
- 設計：`docs/2026-10-21_hypothesis-cycle-automation.md` §14
- 前段：`contributions/2026-10-21_phase2_prerequisites.md`（§13 の前提整備）

---

## 0. 3 行

1. `next_literature_questions` を**決定的に**クエリへ変換する `scripts/next_queries.py` を作った。
   モデルもネットワークも使わず、台帳は読むだけ。**計測器**でありゲートではない。
2. 分割前の 6 仮説には問いが無いので、`state/hypothesis_questions.jsonl`（overlay）に
   7 仮説 14 問いを置いた。レコードが既に問いを持つ場合は overlay がそれを**影にできない**（エラー）。
3. 初回の計画は **14 クエリ**。優先度の先頭は `HYP-001`（未決 11 件）。
   coverage は **0 件**——`unexplained` 25 件のどれにも `observation_key` が無い（§4 の発見）。

---

## 1. 生成規則（決定的・モデル無し）

```
小文字化 → 英数字とハイフン以外で分割 → stopword と重複を除去（順序は保つ）
→ 先頭 --max-terms 語（既定 10）→ 空白で連結
```

- ハイフン化合物（`self-preference` / `long-horizon` / `out-of-distribution`）は 1 語として残す。
- 内容語が残らない問いは**空クエリを作らず** `no_terms` として報告する。
- `--with-review` で仮説ごとに 1 本だけ `review` チャネル（先頭 4 語 + `survey`）を足す。
  S7 の「論文種別」はこれで満たす。問いごとに足すと review が keyword と同数並び、
  優先度の情報が消えるため 1 本に限った。

**やらないこと**：フレーズ検索・フィールド指定・類義語展開・クエリの言い換え。
どれも「もっともらしいが検証できない」変換であり、当たり外れは次ラウンドの
`hits` / `screened` でしか分からない。

---

## 2. 入力と重み

| 入力 | 使い方 |
|---|---|
| 仮説レコードの `next_literature_questions` | 一次ソース。あれば overlay は読まない |
| `state/hypothesis_questions.jsonl`（＋シャード） | 分割前レコード用。既知の仮説のみ・影にしない |
| `gap_scan.analyse` の `unresolved` | 仮説クエリの優先度 = 1 + 未決件数。`derived_from` に HYP と REL を並べる |
| `gap_scan.analyse` の `unexplained` | coverage クエリ。**明示的な `observation_key` がある場合だけ**種にする |
| `state/search_log.jsonl` | 実行済みのクエリは `already_searched` へ（完全一致・部分集合一致） |

`gap_scan.analyse` をそのまま呼ぶので、`unexplained` の定義（`derived_from` を除く）は
計測器と 1 か所で共有される。**新しい定義を足していない。**

---

## 3. なぜ overlay を足したか

7 仮説のうち **6 件は分割前の記録**で `next_literature_questions` を持たない。

| 案 | 判定 |
|---|---|
| 未設定はスキップ（設計 §13.5 の字面通り） | プランナは**永久に 0 件**。実データで一度も動かない成果物になる |
| 仮説レコードを書き換える | 追記専用に反する。同じ ID の 2 件目は重複 ID エラー |
| 旧 `next_observations` を代替に読む | ラウンド1で見つけた欠陥の再生産（文献の問いと自前実験が混在） |
| **問いの overlay**（採用） | `observation_key` overlay と同じ形。レコードは不変、ID も増えない |

overlay の規則：

- 1 仮説 1 レコード。**重複はエラー**（どちらかを黙って選ばない）。
- 既知の仮説だけを指せる（未知 ID はエラー）。
- **レコードが問いを持つ場合、overlay はそれを影にできない**（エラー）。二つの正は必ずずれる。
- 免除（`legacy_files` / `pre_split_files`）とは独立。overlay を持たない仮説は
  これまで通り報告してスキップされる。

問いは **LLM が起草**した（S5 の仕事）。S7 が禁じているのは「人がクエリを書くこと」で
あり、仮説の次の問いを書くことではない。起草の根拠は各レコードの `basis` に残した
（声明・反証条件・旧 `next_observations` の文献 2 件）。

---

## 4. 初回の実測（2026-10-21）

```
仮説 7 件 / 問いあり 7 件（record 0 / overlay 7） / 計画 14 件（keyword 14・review 0）
既出 0 / 語なし 0 / 上限で除外 0
coverage: 未説明 25 件 / 種あり 0 件 / 種なし 25 件
```

| 優先度 | 仮説 | クエリ |
|---:|---|---|
| 12 | HYP-001 | `externalized structured memory agents outperform long-context cumulative exploration efficiency` |
| 12 | HYP-001 | `file-based state stores improve reproducibility multi-session agent runs` |
| 5 | HYP-002 | `heterogeneous judge panels reduce common-mode evaluation errors relative homogeneous majorities` |
| 5 | HYP-002 | `homogeneous llm worker majorities reproduce common-mode errors judging subjective outputs` |
| 3 | HYP-20261021-9f99 | `agent benchmark model rankings stable harness changes capability gaps small` |
| 3 | HYP-20261021-9f99 | `factorial designs agent benchmark variance explained model harness interaction` |
| 2 | HYP-20261021-a10b | `context pruning automatic summarization affect completion rate token cost long-horizon` |
| 2 | HYP-20261021-a10b | `dependency graph decomposition outperform full-context prompting long document generation` |
| 1 | HYP-20261021-4cdb | `autonomous agents keep provisional single observations avoid premature hypothesis rejection` |
| 1 | HYP-20261021-4cdb | `dual hypothesis observation space falsification records increase new diversity autonomous` |
| 1 | HYP-20261021-fee7 | `gates prevent reward hacking overfitting self-improving long-horizon research agents` |
| 1 | HYP-20261021-00b4 | `judge replacement blind evaluation reduce llm self-preference support rates` |
| 1 | HYP-20261021-fee7 | `large exploration versus frozen held-out out-of-distribution score gap self-improving agents` |
| 1 | HYP-20261021-00b4 | `llm self-preference vary evaluation task type text quality numeric prediction` |

### 4.1 発見：coverage の種が 0 件

`gap_scan` が `unexplained` とする 25 件のうち、`observation_key` を持つものは **0 件**。
注釈 30 件はすべて「既に説明済み」の観測に付いている。したがって

- 未説明観測を検索で攻めるには、**まず S3 が観測キーを与える**必要がある。
- プランナは推測でキーを作らない。作れば `gap_scan` の「独立支持が無い」判定まで汚す。

これは欠陥ではなく、Phase 2 が最初に出した**作業指示**である。次の S3 では、
`unexplained` の 25 件に優先してキーを付ける。

---

## 5. 検証

```
python3 -m unittest discover -s tests  → 559 OK（504 → 559、+55）
python3 scripts/validate_state.py      → PASS（overlay の未知 ID・shadowing・重複を検査）
python3 scripts/check_doc_numbers.py   → 0 stale
8 ゲートすべてローカルで緑
```

新しいテスト 55 件の内訳：トークン化 7・overlay の読み込み 7・overlay の検査 7・
計画 10・検索ログ照合 5・coverage 4・レポート形状 2・CLI 7・実リポジトリ 6。

**台帳は 1 バイトも変わっていない**（`test_the_cli_does_not_modify_the_ledgers`）。
計画は `QRY` を書かない——`QRY` になるのは S1 が実際に検索したときだけである。

---

## 6. この実装が主張しないこと

- **クエリの良し悪しは測っていない。** 内容語の袋であって、フレーズでもフィールド指定でもない。
- **overlay の問いが正しい保証は無い。** 声明から起こした起草であり、文献が実際に
  その問いに答えているかは検索して初めて分かる。
- **coverage は未説明観測を「検索できる形」にしか変換しない。** キーが無ければ何もしない。
- **計測器は CI に入らない。** `gap_scan` / `self_support` と同じ standing。

---

## 7. 次

**Phase 3**：`self_support.py`（自己支持率の計測器。ラウンド0の測定を毎ラウンド再計算）と
二重裁定の一致率。計画（本 PR）と計測器（Phase 3）が揃うと、1 ラウンドを
「計画 → 検索 → 裁定 → 生成 → 採点」で回したときに、**どこで支持が増えたか**を
生成元込みで説明できる。3 ラウンド実走（Phase 4）はその後。
