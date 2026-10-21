# gap_scan ベースライン測定 — 現在の関係台帳に対する実測（R2）

- 作成日：2026-10-21
- 作業ブランチ：`arena/66c31140-researchos`（基準：`main` の `352f8fe`）
- 対象：`scripts/gap_scan.py`（本 PR で新設）を**現在の台帳**に当てた結果
- 根拠：`contributions/2026-10-21_sheldon_reading.md` §3.3（4述語）・§3.4（provisional 導出）・§5.6（提案6）・§6.3（予測）
- 位置づけ：**計測器**。ゲートではない。CI に接続していない。台帳は読み取りのみ。

---

## 0. 結論（TL;DR）

1. **未評価は全件。** 関係台帳 `state/relations.jsonl` は 0 レコード、EVD は 86 件。したがって `unassessed = 86 / 86（100.0%）`、`unexplained = 86 / 86（100.0%）` である。
2. **反駁は 0 件。** `observation_key` を持つ EVD は 86 件中 **0 件**なので、provisional 導出（fail-closed）により全 86 件が provisional になる。非 provisional は 0 件で、`refute` は両仮説とも 0。将来 `refute` の REL が入っても、独立出典による再遭遇が無い限り「抑止」として計上される。
3. **観測領域（source_id）23 個すべてが未評価。** 最大は `SRC-20261020-f295`（Agora）の 11 件、次いで `SRC-20261021-a3a2` の 8 件。EVD を持たない出典は 0 件。
4. **SHELDON メモ §6.3 の予測（全件未評価・refutation 0 件）は形状として的中した。** ただし絶対値は 54 件ではなく 86 件である。§6.3 の 54 は**メモ執筆時点（PR #45 相当）のスナップショット**であり、その後の複数の PR の取り込みで EVD が 32 件増えた。§6.1 の「12 領域」も現在は 23 領域。
5. **CI ゲートは 8/8 緑。** ただし開始時点（`352f8fe`）は 8 中 6 緑で、赤の 2 つは**本 PR の変更前から赤**だった（`README.md` の「合計 280件」に対し実測 293 件、`docs/minimal-core-and-ci.md` も同様）。計測器の欠陥ではなく、過去 PR のテスト追加に対する件数同期の漏れである。**承認を得て本 PR で件数を実測値（349 件）に同期**し、8/8 緑を確認した（§7）。

---

## 1. 実行方法

```bash
python3 scripts/gap_scan.py            # 人間可読
python3 scripts/gap_scan.py --json     # 機械可読（キー順・並び順は固定）
python3 scripts/gap_scan.py --state-dir <dir>   # 合成台帳を指す（テスト用）
```

- 標準ライブラリのみ。出力はソート済みで、同じ台帳に対して**バイト単位で同一**になる（`tests/test_gap_scan.py` の `test_two_runs_produce_identical_reports`）。
- 台帳の読み取りは `scripts/validate_state.py` の `COLLECTIONS`（ファイル名）と `load_jsonl`（パース）を再利用している。読み取り器の重複実装は無い。
- 終了コード：**0 = 測定完了**（穴が全件でも 0）、**2 = 使用法・入出力エラー**（台帳が無い／JSON でない／引数不正）。1 は設計上返さない。

---

## 2. 実測結果（2026-10-21、基準コミット `352f8fe`）

### 2.1 全体

| 項目 | 実測値 |
|---|---|
| EVD（観測） | 86 |
| REL（関係） | **0** |
| HYP（仮説） | 2 |
| provisional な EVD | 86 |
| 非 provisional な EVD | 0 |
| `unassessed` | **86 / 86（100.0%）** |
| `unexplained` | **86 / 86（100.0%）** |
| `unresolved` のみの観測（狭い読みの unassessed） | 0 |
| 参照異常（dangling / 重複 / 未知 verdict） | 0 |

### 2.2 述語の意味と、この台帳での値

| 述語 | 定義（SHELDON メモ §3.3） | 実測 | 読み方 |
|---|---|---|---|
| `unassessed(o)` | o について REL レコードが 1 件も無い | 86 / 86 | 台帳に判定が 1 件も書かれていない |
| `unexplained(o)` | support の REL が 1 件も無い | 86 / 86 | 支持された観測が 1 件も無い |
| `refutation(h)` | refute かつ非 provisional な REL | 0 / 0（HYP-001 / HYP-002） | provisional ゲートにより反駁は成立しない |
| `discriminative(o)` | support/refute を持つ仮説の数 | 全件 0 | 判定が無いので判別力も測れない |

`unresolved` のみの観測が 0 件なのは、**REL 自体が 0 件**だからである。REL が入り始めると「未評価（レコードが無い）」と「未評価（`unresolved` と記録済み）」が分離する。本ツールは両方を別項目で出す（§5）。

### 2.3 仮説ごとの verdict（refute は非 provisional のみ）

| 仮説 | support | refute | neutral | unresolved | provisional による抑止 | other |
|---|---|---|---|---|---|---|
| `HYP-001` | 0 | 0 | 0 | 0 | 0 | 0 |
| `HYP-002` | 0 | 0 | 0 | 0 | 0 | 0 |

参考：`HYP.evidence_ids`（仮説→観測の既存の候補集合）は HYP-001 が 3 件、HYP-002 が 3 件を持つ。**これは支持の記録ではない**（SHELDON メモ §5.8）。REL が入るまで `support` は 0 のままである。

### 2.4 観測領域（source_id）別の未評価件数（多い順、全 23 領域）

| 観測領域（source_id） | EVD | unassessed | unexplained |
|---|---:|---:|---:|
| `SRC-20261020-f295`（Agora） | 11 | 11 | 11 |
| `SRC-20261021-a3a2` | 8 | 8 | 8 |
| `SRC-002`（GitSwarm） | 6 | 6 | 6 |
| `SRC-20261021-2b88` | 6 | 6 | 6 |
| `SRC-003`（DuoDiscover） | 5 | 5 | 5 |
| `SRC-20261021-2384`（SHELDON） | 5 | 5 | 5 |
| `SRC-20261021-7419` | 5 | 5 | 5 |
| `SRC-20261021-8452` | 5 | 5 | 5 |
| `SRC-001`（Stateless Language Agents） | 4 | 4 | 4 |
| `SRC-20261020-07a3` | 4 | 4 | 4 |
| `SRC-20261020-303f` | 4 | 4 | 4 |
| `SRC-004`（本リポジトリ自身） | 3 | 3 | 3 |
| `SRC-20261020-05de` | 3 | 3 | 3 |
| `SRC-20261020-4cff` | 3 | 3 | 3 |
| `SRC-20261020-787b` | 3 | 3 | 3 |
| `SRC-20261020-875e` | 3 | 3 | 3 |
| `SRC-20261021-065a` | 2 | 2 | 2 |
| `SRC-20261021-4172` | 1 | 1 | 1 |
| `SRC-20261021-7176` | 1 | 1 | 1 |
| `SRC-20261021-9a02` | 1 | 1 | 1 |
| `SRC-20261021-a714` | 1 | 1 | 1 |
| `SRC-20261021-f186` | 1 | 1 | 1 |
| `SRC-20261021-fb4a` | 1 | 1 | 1 |
| **合計** | **86** | **86** | **86** |

- 並びは `unassessed` の降順、同数なら `source_id` の昇順（決定的なタイブレーク）。この規則はテストで固定した。
- 23 領域すべてが「仮説と 1 本も紐づいていない」状態である。SHELDON の Explore の観点では、**未探索の観測領域が 23 個**あることになる。

### 2.5 内部状態（導出の前提）

| 項目 | 実測 |
|---|---|
| `observation_key` を持つ EVD | 0 / 86 |
| `observation_region` を持つ EVD | 0 / 86 |
| `observation_axis` を持つ EVD | 0 / 86 |
| `search_status` を持つ HYP | 0 / 2（既定は `retained`） |
| provisional の導出 | 全 86 件が provisional（`observation_key` が `evidence_id` に既定化され、同一キー・異出典の相手が存在しない） |

---

## 3. SHELDON メモ §6.3 の予測との照合

| 述語 | §6.3 の予測（執筆時点） | 本測定（現在） | 判定 |
|---|---|---|---|
| `unexplained(o)` | 54 / 54 | **86 / 86（100.0%）** | 割合は一致。件数は台帳成長により増加 |
| `unassessed(o)` | 54 / 54 | **86 / 86（100.0%）** | 同上 |
| `refutation(h)` | 0 件 | **0 件** | 一致 |
| 仮説あたりの support 数 | 0 | **0** | 一致 |
| 観測領域数 | 12 | **23** | 台帳成長により増加 |

**差の原因は台帳の成長であり、述語の不一致ではない。** §6.3 の 54 は SHELDON 読解 PR 時点の EVD 数で、その後の取り込みで 86 になった（`README.md` の「現在の状態」節が 86）。**予測の主張（「装置が無いので全件未評価に見え、反駁は 0」）は、件数が変わってもそのまま成立している。**

また §6.1 の「12 領域のうち 9 領域が仮説と紐づいていない」は、現在は**23 領域すべてが紐づいていない**。REL が空である以上、領域の紐づきは 0 である。

---

## 4. R3 backfill 後の再測定の基準点

この節が本メモの実用上の目的である。R3（`observation_key` 付与と REL 投入）の後、同じコマンドを再実行して次を比べる。

| 観測されるべき変化 | どの項目で見るか | 現在値 |
|---|---|---|
| `observation_key` の付与で同一所見が束ねられる | `totals.provisional` / `totals.non_provisional` | 86 / 0 |
| REL の投入で未評価が減る | `unassessed.count` と `per_source[].unassessed` | 86 / 全領域 |
| support の投入で未説明が減る | `unexplained.count` | 86 |
| 非 provisional な観測への refute だけが数えられる | `per_hypothesis[].refute`（`refute_suppressed_provisional` と分離） | 0（抑止 0） |
| 判定済みだが `unresolved` の観測が現れる | `unresolved_only.count` | 0 |
| 参照の壊れが混入していない | `anomalies` の 4 配列 | すべて空 |

**注意（fail-closed の含意）**：`observation_key` を付けただけでは `refute` は増えない。**同一キー・異なる `source_id`** の EVD が要る。これは「独立した再遭遇が無い反駁は数えない」という §3.4 の規則そのものであり、R3 で `refute` を入れたい場合は**先に束ねる相手を用意する**必要がある。逆に、`refute` を入れたのに `refute_suppressed_provisional` が増えるなら、束ね方が足りない（または REL の `provisional` が明示 `true`）。

比較のため、本メモ §2 の表をそのまま差分の基準にしてよい。JSON で比較する場合は次のキーが安定である：`totals` / `unassessed.{count,total,rate}` / `unexplained.{count,total,rate}` / `unresolved_only.count` / `per_hypothesis[].{support,refute,neutral,unresolved,refute_suppressed_provisional}` / `per_source[].{source_id,evidence,unassessed,unexplained}` / `anomalies`。

---

## 5. 実装上の設計判断（仕様が一意でなかった点）

1. **provisional の優先順位（fail-closed）**
   1. `observation_id` が EVD に解決しない REL は**常に provisional**（確かめる相手が存在しないので、明示 `false` でも反駁にしない）。
   2. 解決する場合、REL の `provisional` が boolean ならそれが優先（`true` も `false` も）。
   3. それ以外は導出値（同一 `observation_key`・異 `source_id` の別 EVD が 0 件なら provisional）。
   4. boolean でない `provisional`（例 `"no"`）は無視して導出値に落とす。
   5. `source_id` が無い／空の EVD は provisional。かつ、その EVD は**他の EVD を corroborate しない**（欠損した出典を独立証拠として数えない）。
2. **`unassessed` の 2 つの読みを併記**：主定義は「REL が 1 件も無い」。SHELDON の `unresolved` は「未評価」を意味するため、「REL はあるが全 verdict が `unresolved`」を `unresolved_only` として別に出す。片方だけを黙って選ばない。
3. **`unexplained` は support のみで判定**（provisional でも support は使える：SHELDON §4.2 の非対称ゲート）。§3.3 の `h ∈ wH` 条件は、`search_status` 未設定＝既定 `retained` かつ `setaside` が 0 件のため、全仮説を見るのと同値である。**`setaside` が入った時点でこの同値は崩れる**ので、そのときは仕様の再確認が要る（本実装は `setaside` を除外しない）。
4. **領域は `source_id`**（仕様どおり）。スキーマには `observation_region` もあるが、全件未設定であり、暗黙に上書きすると報告の領域が「まだ誰も使っていないフィールド」に依存するため使わない。
5. **参照異常は計測器の仕事ではない**が、黙って落とさない：dangling な hypothesis / observation、未知の verdict、重複ペアを `anomalies` に列挙する。本来の検査は `validate_state.py`（CI 4 番目のゲート）。
6. **`refute` の数え上げは 1 箇所**だけゲートされる。`support` / `neutral` / `unresolved` は REL の記録どおりに数える。

---

## 6. テスト（`tests/test_gap_scan.py`、46 件）

合成台帳（一時ディレクトリ）のみを使い、実台帳の数値には依存しない。固定した性質：

- REL が空なら全件が `unassessed` / `unexplained`（100%）、EVD 0 件でもゼロ除算しない
- support の付与で `unexplained` から外れ、`unassessed` からも外れる。support は名指しした仮説にだけ計上
- **同一 `observation_key`・異 `source_id` の EVD がある場合のみ** `refute` が数えられる。キー無し／同一出典／キーが違う／`source_id` 欠損はすべて抑止
- 明示 `provisional` の優先（`true` で抑止、`false` で解除、非 boolean は導出に落ちる、dangling は `false` でも抑止）
- 領域別集計の降順とタイブレーク、`source_id` 欠損のラベル
- `--json` の形（トップレベル 8 キー、`rate` が 0〜1 の float、`per_hypothesis` の 6 キー、`per_source` の 4 キー、`anomalies` の 4 配列）
- 終了コード：全件未評価でも 0、台帳欠落／不正 JSON／ディレクトリ欠落／引数不正は 2
- 台帳を書き換えないこと、2 回の実行が同一であること

実行：`python3 -m unittest tests.test_gap_scan -v` → **46 件 OK**（実測）。

---

## 7. ゲート実測（8 つ）

`docs/minimal-core-and-ci.md` の 8 ゲートを、**本 PR の変更を入れた最終状態**で実行した結果：

| # | コマンド | 終了コード | 結果 |
|---|---|---|---|
| 1 | `python3 -m unittest discover -s tests` | 0 | **349 件 OK** |
| 2 | `python3 gitswarm/benchmarks/benchmark.py --check` | 0 | PASS |
| 3 | `python3 gitswarm/readout_sim.py --check` | 0 | PASS |
| 4 | `python3 scripts/validate_state.py` | 0 | PASS（`sources=23, evidence=86, claims=9, verifications=34, hypotheses=2, relations=0`） |
| 5 | `python3 scripts/check_citations.py` | 0 | PASS（22 checked / 1 skipped / 0 failures） |
| 6 | `python3 scripts/check_memo_citations.py` | 0 | PASS（27 memos / 61 citations / 3 skipped / 0 failures） |
| 7 | `python3 scripts/check_memo_ledger_refs.py` | 0 | PASS（27 memos / 0 dangling / 5 archived） |
| 8 | `python3 scripts/check_doc_numbers.py` | 0 | PASS（0 stale） |

### 7.1 開始時点の赤と、その解消（実測）

**本 PR の変更を 1 つも入れていない状態**（`git status` 空、HEAD = `352f8fe`）で同じ 8 つを実行した：

- ゲート 1：`Ran 293 tests` → `FAILED (failures=2)`（`test_check_doc_numbers.RealRepoTest` の 2 件）
- ゲート 8：`actual: tests=293` に対し文書側 280 → 4 件 STALE（`README.md` ×3、`docs/minimal-core-and-ci.md` ×1）

つまり **`main` の `352f8fe` は既に赤**であった。原因は、テストを追加した過去の PR が `README.md` と `docs/minimal-core-and-ci.md` の件数（280）を更新しなかったこと。`tests/test_merge_ledgers.py`（13件）と本 PR の `tests/test_gap_scan.py`（46件）が文書の一覧から漏れており、実測は 293 → 339 になっていた（その後 `main` は PR #55 で `tests/test_score_extraction.py`（10件）を取り込み、文書を 303 に同期した）。

本 PR の依頼条件は「成果物は新規作成のみ、既存ファイル・`state/` は変更しない」だったため、当初はこの同期を**行わずに報告**した。**承認を得たうえで**、次の最小限の同期を行った（R1 が同じ状況を承認込みで解消した前例に倣う：`contributions/2026-10-21_relation_ledger_impl.md` §9）。

| ファイル | 変更 |
|---|---|
| `README.md` | 「現在の状態」のテスト件数 → **349**、ファイル数 → **16**。§構成に `scripts/gap_scan.py` と `tests/test_gap_scan.py`（46件）を追加し、合計を 349 に更新。§使い方の件数も 349 |
| `docs/minimal-core-and-ci.md` | §2 のゲート1の件数 → **349テスト** |

`main` は本 PR の作業中に PR #55（`scripts/score_extraction.py` と 10 テスト）を取り込み、同じ件数行を 303 に更新していた。**競合は件数行のみ**で、両方の追加（`test_score_extraction.py` 10件 と `test_gap_scan.py` 46件）を残したうえで合計を 349 に統一した。`scripts/score_extraction.py` の README §構成への追記は本 PR の範囲外（別 PR の持ち分）として行っていない。

**台帳（`state/`）・スキーマ・CI 設定・ゲートの意味論は変更していない。** 変更は件数の文字列のみで、テストの追加・削除は無い（`def test_` の計数が 349 であることはゲート 8 が再計算して確認している）。

### 7.2 マージ判断

依頼条件は「CI が緑でコンフリクトがなければ自分でマージしてよい」。**8/8 緑・コンフリクト無しを確認して `main` へマージした。** 計測器自体はゲートの意味論を変えない（CI 非接続・台帳非変更）。

---

## 8. 限界

1. **verdict の質は測らない。** REL が空である以上、この測定が示すのは「装置が動き、現状を 100% 未評価と報告する」ことだけである。§3.3 の 4 述語は**本リポジトリの導出**であり、SHELDON 論文の形式的定義ではない（同メモ §8）。
2. **1 時点のスナップショット。** 台帳は増え続けるため、§2 の数値は基準コミット `352f8fe` に固定された記録である。
3. **`refute` の 0 は「反駁が無い」ではなく「反駁を数える条件が満たされていない」。** `observation_key` を人間が付与する手順（同メモ §5.7 手順5）が済むまで、この 0 は情報量を持たない。
4. **`discriminative(o)` は実装していない。** 仕様の 4 出力に含まれないため。REL が入れば同じ台帳から算出できる（次段の課題）。
5. **`wH`（`search_status = setaside` の除外）は未実装**（§5.3）。現状 `setaside` が 0 件なので結果に影響しない。

---

## 9. 本 PR で行っていないこと

- 台帳（`state/` の 6 ファイル）の変更、`observation_key` の付与、REL の投入
- スキーマ・CI 設定・ゲートの意味論の変更、CI への接続（ゲート化）
- 既存メモの記述の書き換え（`README.md` と `docs/minimal-core-and-ci.md` は §7.1 の件数同期のみ）
- `discriminative(o)` の実装、`wH`（`setaside` 除外）の実装

（2026-10-21。上記の実行以外は行っていない。）
