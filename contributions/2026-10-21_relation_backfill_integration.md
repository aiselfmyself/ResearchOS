# 関係台帳（REL）の統合投入 — R4 実施記録

- 作成日: 2026-10-21
- 役割: 統合役ワーカー（R4: 関係台帳への統合投入）
- 対象候補: `contributions/2026-10-21_relation_backfill_ALL.json`（シャード `ALL`・235 判定行）
- **状態: 投入済み**（`state/` へ追記。既存レコードの書き換え・削除は 0）
- 承認: 2026-10-21、人間が次の 4 点を承認（本セッション内で確認）
  1. REL の台帳投入（172 行）— **承認**
  2. R3 の `refute` 4 行の扱い — **`unresolved` にする**
  3. 新仮説候補 `NEW-ALL1`〜`NEW-ALL4` の HYP 登録 — **4 件とも登録**
  4. `observation_key` の実装方式 — **オーバーレイ実装**
- 投入内容（実測）: **REL 235 行 / HYP 4 件 / observation_key 注釈 30 件**
- 関連メモ: `contributions/2026-10-21_relation_backfill_ALL.md`（R3 の裁定）、`contributions/2026-10-21_relation_ledger_impl.md`（R1 の台帳実装）、`contributions/2026-10-21_gap_scan_baseline.md`（R2 の基準値）

---

## 0. 結論

| 項目 | 実測 |
| --- | --- |
| 追記した REL レコード | **235**（既存 2 仮説への裁定 172 ＋ 新仮説 4 件への 63） |
| 追記先 | `state/relations.d/2026-10-21-a194d1a9b885.jsonl`（凍結ベース `state/relations.jsonl` は 0 バイトのまま） |
| 登録した HYP | **4**（`HYP-20261021-9f99` / `-fee7` / `-4cdb` / `-a10b`）→ `state/hypotheses.d/2026-10-21-3990b64b4fdb.jsonl` |
| observation_key の注釈 | **30 件**（`state/evidence_keys.d/2026-10-21-3ead52ec8d51.jsonl`。EVD レコード自体は無変更） |
| validate_state | **PASS**（`sources=23, evidence=86, claims=9, verifications=34, hypotheses=6, relations=235`） |
| gap_scan 前 → 後 | unassessed **86/86 (100.0%) → 0/86 (0.0%)**、unexplained **86/86 (100.0%) → 20/86 (23.3%)**、provisional **86/86 → 56/86** |
| 既存レコードの書き換え・削除 | **0 行**（`git diff` で確認。§8） |
| 全 8 ゲート | すべて `exit=0`（§8） |

**注意して読むべき点**：unassessed が 0 になったのは「穴が埋まった」からではない。2 仮説 × 86 観測の**直積を入れた**ので、定義上 0 になる（134 行は `neutral`）。数字の読み方は §5.3 に書いた。

---

## 1. 前提の確認と、承認が下りるまでの判断

作業開始時点では**承認を確認できなかった**ため、いったん「投入せずに統合プレビューまで」で止める判断をした（PR #65 の当初版）。確認した 5 経路は次のとおり。

| # | 確認したこと | 実測結果 |
| --- | --- | --- |
| 1 | `gh pr view 63 --json comments,reviews`（R3 の PR） | `COMMENTS []` / `REVIEWS []`。承認コメントなし |
| 2 | `gh pr list --state all` | R3 後続の R4 用 PR・承認 PR なし |
| 3 | リポジトリ内の「承認」記述の全文検索 | R3/R4 に関する承認記録 0 件（規定文のみ） |
| 4 | `docs/worker-prompts-next-stage-2026-10-21.md` | 「R4 は**人間の承認後**に台帳投入」「台帳投入（R4）は**人間がマージする**」 |
| 5 | `docs/autonomous-merge-policy-2026-10-21.md` §1 | 台帳の**追記**は承認不要。ただしこれは「構造の正しさ」を対象にした規約で、verdict という**推論結果**の投入は R4 プロンプトが別扱い |

そのうえで、承認後にそのまま実行できる裁定計画（`contributions/2026-10-21_relation_backfill_integration_plan.json`）と、隔離コピーでの乾燥実行による実測値を用意して報告し、**人間の承認を得てから投入した**。本文書はその最終記録である。

> 「承認が無いまま投入しなかった」ことと「承認後に投入した」ことの両方を残すため、§3 と §8 の判断記録は当初版のまま残している。

---

## 2. 候補の機械検証（R3 の主張を鵜呑みにせず再確認）

| 検査 | 方法 | 実測結果 |
| --- | --- | --- |
| シャード数 | `ls contributions/*relation_backfill*.json` | **1 ファイル**（`ALL`）。R3-A〜E の分割シャードは存在しない |
| 判定行数 | `len(items)` | **235**（既存 2 仮説への直積 172 ＋ `NEW-*` 63） |
| **重複ペア** | `Counter((hypothesis_id, evidence_id))` | **0 件** |
| **シャード間の verdict 食い違い** | シャードが 1 つ | **該当なし**（「食い違いが無い」ではなく「生む構造が無い」） |
| EVD 網羅 | 台帳 86 − 候補の evidence_id | **欠落 0 / 未知 0**（全 86 EVD が最低 2 行） |
| HYP 参照 | 候補の hypothesis_id − 台帳 | **未知 0**（`NEW-*` 以外） |
| `NEW-*` ラベル | 使用ラベル vs 宣言 | **一致**（`NEW-ALL1`〜`NEW-ALL4`） |
| rationale の数値 | excerpt+interpretation と機械照合 | **転写ずれ 0**（検出 19 件は `1,450万` vs `14.5 million`、`3e-7` vs `3×10⁻⁷` などの書式差） |
| excerpt の逐語重複 | 先頭 200 字 | **1 組**（`EVD-20261021-a1fa` / `EVD-20261021-a6fd`＝同一論文の重複登録） |
| 基準コミット | `git diff 91a08f4 origin/main -- state/ schemas/` | 差分 **0**（R3 の `base_commit` は台帳について現行 `main` と同一） |

**注意**：本クローンは shallow で、R3 の `base_commit`（`91a08f4…`）は最初 `bad object` だった。`git fetch --unshallow` で取得してから上記を確認している。

---

## 3. 裁定（投入した 235 行の内訳）

### 3.1 書き換えた 1 種類：`refute` 4 行 → `unresolved`（承認済み）

| EVD | R3 の rationale（要旨） | 裁定 |
| --- | --- | --- |
| `EVD-20261020-bea0` | 未投稿の再現試行が痕跡を残さない | `unresolved` |
| `EVD-20261020-137b` | 5 日間停滞、人間の手動介入 3 回を要した | `unresolved` |
| `EVD-20261020-78b6` | Git 履歴と索引が 45 コミット乖離 | `unresolved` |
| `EVD-20261020-80cf` | 評価器ログ等が全欠落で独立再現不能 | `unresolved` |

**理由**：`HYP-001` は「外部化された構造化メモリを持つエージェントは、**単一セッションの巨大プロンプトより**累積探索効率と再現性で優れる」という**比較命題**である。4 行はいずれも**外部化アーム単独の失敗**で、対照（単一セッション）が無い。したがって「外部化すれば再現性が保証される」というより強い読みを反駁するだけで、比較命題そのものの反駁にはならない。

- R3 の rationale は消さず、末尾に「【統合役裁定 2026-10-21】…」を追記して**境界条件として保存**した（plan JSON の `adjudication: refute_to_unresolved`）。
- この 4 行は `observation_key` の注釈対象外なので `provisional` のままであり、`gap_scan` の `refute` 集計には元から入らない（R3 案のままなら `refute_suppressed_provisional=4`、裁定案は `unresolved=11`）。

### 3.2 そのまま採用した 168 行

- `neutral` 134 行（`HYP-001` 63 ＋ `HYP-002` 71）／`support` 23 行（12 ＋ 11）／`unresolved` 11 行（R3 由来 7 ＋ 4）。
- 低信頼 `support` 3 行（`HYP-001`×`EVD-20261021-66d4`、`HYP-002`×`EVD-20261020-aa81`、`HYP-002`×`EVD-20261021-59ab`）はそのまま採用。R3 が confidence を下げて判断を明示しており、語彙に「低信頼の support」を禁じる規則は無いため（読み方の注意は §5.3）。

### 3.3 新仮説 4 件への 63 行（承認済み）

`HYP` を登録したうえで REL を投入した。仮ラベルとの対応は §6 の表。

---

## 4. 採用しなかったもの（無言で捨てない）

### (a) `observation_key` の束ね案 9 組のうち **2 組 4 件**

| 組 | 判定 | 理由 |
| --- | --- | --- |
| `DUP_SAME_PAPER:agentic_scientist_dual_rubric_and_score_gate`（`EVD-20261021-6094` / `05ed`） | **適用しない** | 同一論文の重複登録（`SRC-20261021-7419` と `8452`）。共通キーを与えると `gap_scan` が「異ソース 2 件」とみなし**偽の独立再現**を作る |
| `DUP_SAME_PAPER:agentic_scientist_frozen_posthoc_diagnostics`（`EVD-20261021-a1fa` / `a6fd`） | **適用しない** | 同上（逐語重複ペア） |
| `verifier_fidelity_and_pre_evaluation_leakage_guard` の `EVD-20261021-e31f` | **適用しない**（1 件だけ除外） | この組の 4 件のうち `f7f8`（`7419`）と `e31f`（`8452`）が同一論文。R3 は「独立 4 ソース」と書いたが**実測は 3 ソース**。`e31f` を外して 3 件で適用した |

結果として `observation_key` を持つのは **30 件**（R3 の提案 31 件から `e31f` を除いた数）。キーを持たない EVD は `provisional` のまま（fail-closed）になる。

### (b) 凍結ベースへのフィールド追記という手段そのもの

R4 プロンプトは「observation_key の束ね案は該当 EVD への任意フィールド追記として扱う」としていたが、現行規約では**その手段が存在しない**。

| 問題 | 実測・根拠 |
| --- | --- |
| 凍結ベースへの追記は禁止 | `docs/record-id-scheme.md` §2、`docs/parallel-work-ownership.md` §2.1 |
| 同じ evidence_id で差分だけをシャードに書くこともできない | `ledger_store.duplicate_ids()` が統合ビューで ID 重複を**エラー**にする（同じ内容でも報告する設計） |

そこで**オーバーレイ方式**（人間の選択）を実装した。EVD レコードは 1 バイトも変えず、別ファイルで注釈する。

### (c) 捨てた行は 0

235 行すべてがいずれかに割り当てられている（REL 235 行＋§3.3 の HYP 4 件）。**「静かに落とした行は 0」**。

---

## 5. gap_scan の前後比較（実測）

### 5.1 測り方

- **投入前**：投入前のリポジトリで `python3 scripts/gap_scan.py`（実測）。
- **投入後**：実際に `state/` へ追記した後で `python3 scripts/gap_scan.py --json`（実測）。
- 途中段階（2・3）は、実台帳のレコードをメモリ上でフィルタして `gap_scan.analyse()` に渡した**再計算**である（リポジトリは変更していない。同じ台帳・同じコードで再現できる）。

### 5.2 前後比較表

| # | 状態 | `relations` | `hypotheses` | unassessed | unexplained | provisional / non-prov. |
| --- | --- | ---: | ---: | --- | --- | --- |
| 0 | **投入前**（実測） | 0 | 2 | **86 / 86 (100.0%)** | **86 / 86 (100.0%)** | 86 / 0 |
| 1 | 172 行のみ（既存 2 仮説・再計算） | 172 | 2 | 0 / 86 (0.0%) | 63 / 86 (73.3%) | 86 / 0 |
| 2 | 235 行（新仮説 4 件も登録・再計算） | 235 | 6 | 0 / 86 (0.0%) | 20 / 86 (23.3%) | 86 / 0 |
| 3 | **最終: 235 行 ＋ observation_key 30 件（実測）** | 235 | 6 | **0 / 86 (0.0%)** | **20 / 86 (23.3%)** | **56 / 30** |

**変化の要約**：unassessed `100.0% → 0.0%`（−86 件）、unexplained `100.0% → 23.3%`（−66 件、−76.7pt）。ただしその内訳は「既存 2 仮説で −23 件」「新仮説 4 件で −43 件」であり、**証拠が 66 件増えたわけではない**（§5.3）。

`observation_key` の注釈は `provisional` を `86 → 56` に下げたが、**unexplained は 1 件も動かなかった**（20 のまま）。今回 `refute` が 0 件なので、`provisional` は refute の集計にしか効かないためである。

### 5.3 仮説ごとの内訳（最終・実測）

| 仮説 | `support` | `refute` | `neutral` | `unresolved` | 計 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `HYP-001`（外部化メモリ） | 12 | 0 | 63 | 11 | 86 |
| `HYP-002`（多数決の共通モード） | 11 | 0 | 71 | 4 | 86 |
| `HYP-20261021-9f99`（旧 `NEW-ALL1`） | 16 | 0 | 0 | 1 | 17 |
| `HYP-20261021-fee7`（旧 `NEW-ALL2`） | 25 | 0 | 0 | 0 | 25 |
| `HYP-20261021-4cdb`（旧 `NEW-ALL3`） | 12 | 0 | 0 | 0 | 12 |
| `HYP-20261021-a10b`（旧 `NEW-ALL4`） | 8 | 0 | 0 | 1 | 9 |
| 合計 | 84 | 0 | 134 | 17 | 235 |

**数字を読むときの注意（重要）**

1. **unassessed 0 は「穴が埋まった」以上の意味を持たない。** 2 仮説 × 86 観測の直積を入れたので定義上 0 になる。134 行は `neutral`（対象外）である。
2. **`HYP-001` の `support` 12 行は独立 12 件ではない。** 出典は 9 `source_id`、うち `SRC-20261021-7419` と `8452` は同一論文なので **独立 8 論文**。さらに `EVD-20261021-66d4`（サーベイの概念整理・confidence `low`）、`EVD-20261021-7cdb`・`ea49`（設計記述で性能差の測定ではない）を含む。**実測比較に基づく support は 7 件程度**。
3. **`HYP-002` の `support` 11 行も同様。** `EVD-20261020-aa81`・`EVD-20261021-59ab` は「整合する」レベルの間接支持（`low`）、`EVD-004` は代理指標ドリフトの指摘で投票の話ではない。直接の定量は `EVD-20261020-ffec` ほか数件。
4. **`refute` が 0 件なのは「反駁が無い」ではない。** §3.1 で `unresolved` に裁定した 4 件と、`provisional` の fail-closed 規則（`observation_key` の無い単独出典の反駁は数えない）による。
5. **新仮説 4 件はすべて `status: proposed`**。`support` が付いたのは R3 の判定行であって、独立した追試ではない。特に `HYP-20261021-fee7`（25 件）には同一論文の重複 4 件が含まれる（§4(a)）。

### 5.4 領域（`source_id`）別（最終）

全 23 ソースで `unassessed = 0`。`unexplained` が残るのは 9 ソースのみ。

| source_id | EVD | unexplained |
| --- | ---: | ---: |
| `SRC-20261020-f295` | 11 | 9 |
| `SRC-001` | 4 | 3 |
| `SRC-003` | 5 | 2 |
| `SRC-002` | 6 | 1 |
| `SRC-004` | 3 | 1 |
| `SRC-20261020-05de` | 3 | 1 |
| `SRC-20261020-303f` | 4 | 1 |
| `SRC-20261020-787b` | 3 | 1 |
| `SRC-20261021-f186` | 1 | 1 |

**最も穴が深い領域**は `SRC-20261020-f295`（Agora。11 件中 9 件）で、§3.1 の反例群を含む。

### 5.5 残る 20 件

| 分類 | 件数 | EVD |
| --- | ---: | --- |
| 書誌監査・引用転写訂正・コーパス記述（仮説の対象外） | 6 | `EVD-007`, `EVD-009`, `EVD-010`, `EVD-011`, `EVD-20261020-f880`, `EVD-20261021-088c` |
| 外部化しても再現性・索引整合が崩れた負の開示（Agora） | 3 | `EVD-20261020-bea0`, `EVD-20261020-78b6`, `EVD-20261020-80cf` |
| 統制欠如・検出力不足・一般化留保による保留 | 11 | `EVD-20261020-72ee`, `EVD-20261020-e4a7`, `EVD-20261020-ba70`, `EVD-20261020-221a`, `EVD-20261020-d515`, `EVD-20261020-3554`, `EVD-20261020-2336`, `EVD-20261020-2609`, `EVD-20261021-4c6f`, `EVD-20261021-baef`, `EVD-20261021-d78f` |

いずれも「support を付けるべき観測」ではない。

---

## 6. 新仮説（登録済み）

| 仮ラベル | 登録 ID | 主張（要旨） | 反証条件（要旨） | 根拠 EVD |
| --- | --- | --- | --- | --- |
| `NEW-ALL1` | **`HYP-20261021-9f99`** | 到達性能はモデル単体でなく「モデル×ハーネス」の結合系で決まり、効果比 R = Δmodel / Δharness が 1 未満の近接能力領域ではハーネス変更で順位逆転が起きる。R > 1 では順位は保存される | 近接能力群（R < 1）に複数ハーネスを直交交差させても順位逆転が有意に生じない、または大差領域（R > 1.5）で軽微な足場変更のみで頻繁に逆転する | 16 件（`EVD-20261020-aa81`, `4c61`, `EVD-20261021-3d5a`, `cdf7`, `48c6`, `8319`, `1564`, `7dd6`, `c38d`, `c1a2`, `43a0`, `e06c`, `589c`, `1026`, `887d`, `c029`）＋ `unresolved` 1（`d78f`） |
| `NEW-ALL2` | **`HYP-20261021-fee7`** | 指標ハッキング・過適合・偽の改善を防ぎ OOD 汎化を得るには、探索評価と最終評価の分離＋事前リーク／評価改変審査＋ノイズ幅 δ・複雑度正則化を組み込んだ段階ゲート付受容規則が要る | いずれかのゲートを欠いた系でも、凍結ホールドアウトで改変・過適合・トークン肥大を起こさず完備系と同等以上の OOD 利得を複数課題で維持できる | 25 件（`EVD-004`, `EVD-20261020-0766`, `4c61`, `EVD-20261021-c1b4`, `d833`, `2aad`, `a8af`, `12a7`, `5d88`, `f7f8`, `6094`, `f75d`, `a1fa`, `9959`, `13f8`, `5b0d`, `6347`, `b089`, `de29`, `0417`, `6951`, `05ed`, `a6fd`, `e31f`, `5607`） |
| `NEW-ALL3` | **`HYP-20261021-4cdb`** | 長期自律研究では仮説生成が枯渇しやすい。H と O を分離し、負の結果・反証記録を保持し、単発観測を Provisional で保護し、未説明観測へ探索を誘導すると発見性能が上がる | 双空間台帳を持つ系と単一バックログ駆動系を同条件で比べ、後半ラウンドの新規仮説率・未説明解消率・誤棄却率に改善が見られない | 12 件（`EVD-008`, `EVD-20261020-b733`, `EVD-20261021-7dd6`, `7cdb`, `4ad6`, `59ab`, `6ec4`, `572c`, `cd59`, `30ed`, `71a3`, `2804`） |
| `NEW-ALL4` | **`HYP-20261021-a10b`** | 現行モデルは長文生成・履歴維持に弱い。全履歴の持ち越しより、役割別の文脈再構成＋直近剪定＋自動要約＋DAG 局所分解が低コストで高い完遂率を出す | 複数の研究・証明・業務ワークフローで統制比較し、剪定＋要約＋DAG がトークン効率でも完遂率・検証通過率でも優位を示さない | 8 件（`EVD-001`, `EVD-20261020-e9fb`, `04b2`, `EVD-20261021-66d4`, `bbb8`, `45e2`, `8fa6`, `ea49`）＋ `unresolved` 1（`baef`） |

**登録時にした判断**

1. `status` はすべて **`proposed`**。まだ 1 本も直接実験していないため `testing` にしない。
2. `evidence_ids` には `support` と判定した EVD を入れた（`unresolved` の 2 件は入れていない）。
3. 反証条件と次に集めるべき観測は `notes` に原文のまま保存（スキーマに専用フィールドが無いため）。
4. 分割の検討（`NEW-ALL2` は 2 機構、`NEW-ALL3` は 3 機構の複合）は**登録後に別途**行う。今回は承認どおり 4 件のまま登録した（§9 の残課題）。

---

## 7. observation_key のオーバーレイ実装（承認済みの方式）

### 7.1 なぜオーバーレイか

EVD レコードは追記専用で、同じ `evidence_id` の 2 行目は重複エラーになる（§4(b)）。しかし SHELDON の `provisional` 規則は `observation_key` を必要とする。そこで**台帳を書き換えずに注釈する**別ファイルを置いた。

```text
state/evidence_keys.jsonl                         凍結ベース（0 バイトのまま）
state/evidence_keys.d/2026-10-21-3ead52ec8d51.jsonl   注釈 30 件
```

1 レコードは `{"evidence_id": …, "observation_key": …, "recorded_at": …, "basis": …, "note": …}`。

### 7.2 実装（3 ファイル）

| ファイル | 変更 |
| --- | --- |
| `scripts/validate_state.py` | `load_evidence_keys()`（base＋shard を読む／欠落は正常、重複キー・空キー・未知 EVD・base の無い shard はエラー）／`apply_evidence_keys()`（**既存キーは上書きしない**、入力レコードも破壊しない）／`check_evidence_keys()`。`run_all_checks()` が evidence の統合ビューに適用するので、スキーマ・ID・参照・散文の各検査が同じ view を見る |
| `scripts/gap_scan.py` | evidence を読むときに同じオーバーレイを適用。**エラーは測定エラー（exit 2）**として扱い、0 件と混同しない |
| `scripts/new_ledger_shard.py` | `evidence_keys` を target に追加（命名規則を手で書かせない） |

`tests/test_evidence_keys.py` を新設（17 件）：付与・**非上書き**・空キーの補完・入力の非破壊・未知 EVD の報告・base の無い shard・**重複キー**・不正な shard 名・gap_scan が同じ view を読むこと・実リポジトリで重複論文 5 件がキーを持たないこと。

### 7.3 適用した 30 件（変更した EVD 一覧）

EVD レコード自体は**無変更**。注釈を付けた EVD は次の 30 件（7 組）。

| observation_key | EVD |
| --- | --- |
| `externalized_structured_state_enables_compounding_iteration` | `EVD-001`, `EVD-002`, `EVD-20261021-ea49`, `EVD-20261021-71a3` |
| `plurality_voting_unvalidated_or_vulnerable_without_verifier` | `EVD-003`, `EVD-20261020-0641`, `EVD-20261020-ffec`, `EVD-20261021-5d88` |
| `verifier_fidelity_and_pre_evaluation_leakage_guard` | `EVD-004`, `EVD-20261021-5b0d`, `EVD-20261021-f7f8` |
| `preserving_negative_and_falsification_records_guides_search` | `EVD-008`, `EVD-20261021-59ab`, `EVD-20261021-cd59`, `EVD-20261021-30ed` |
| `hypothesis_exhaustion_in_long_horizon_research` | `EVD-20261020-b733`, `EVD-20261021-6ec4`, `EVD-20261021-7dd6` |
| `context_pruning_and_summarization_over_full_history` | `EVD-20261021-bbb8`, `EVD-20261021-45e2`, `EVD-20261021-8fa6` |
| `model_harness_joint_dominance_and_rank_inversion` | `EVD-20261021-3d5a`, `cdf7`, `48c6`, `c38d`, `c1a2`, `e06c`, `589c`, `1026`, `887d` |

### 7.4 効果と限界

- `provisional` は `86 → 56`、`non_provisional` は `0 → 30`。**`unexplained` は 20 のまま**（`refute` が 0 件なので、現時点では集計に効かない）。
- 残り 56 件は `provisional` のまま。**これは「独立再現が無い」という正しい表示**であり、annotation の不足ではない（同一論文の重複 5 件を含む）。
- オーバーレイは**キーの追加だけ**ができる。キーの付け替え・削除はできず、それが必要になったら新しいシャードに別の運用記録を足す設計にした（値の上書きを許すと台帳が自己矛盾する）。

---

## 8. 検証

### 8.1 台帳が追記のみであること（`git diff`）

```text
$ git diff --name-status origin/main...HEAD
M  README.md
M  docs/minimal-core-and-ci.md
M  scripts/gap_scan.py
M  scripts/new_ledger_shard.py
M  scripts/validate_state.py
M  tests/test_relations.py
A  contributions/2026-10-21_relation_backfill_integration.md
A  contributions/2026-10-21_relation_backfill_integration_plan.json
A  state/evidence_keys.jsonl
A  state/evidence_keys.d/2026-10-21-3ead52ec8d51.jsonl
A  state/hypotheses.d/2026-10-21-3990b64b4fdb.jsonl
A  state/relations.d/2026-10-21-a194d1a9b885.jsonl
A  tests/test_evidence_keys.py

$ git diff --stat origin/main...HEAD -- state/
 （既存の state/*.jsonl への差分は 0 行。追加は A のみ）
```

- `state/` は **4 ファイルの追加のみ**。**既存レコードの変更 0・削除 0**（`state/relations.jsonl` は 0 バイトのまま、`state/evidence.jsonl` も無変更）。
- 実行した確認：`git diff --numstat origin/main...HEAD -- state/` の出力が `state/` 配下の *追加行のみ*（`-` 行が無い）であること。

### 8.2 全 8 ゲート（実測）

| # | ゲート | コマンド | 結果 |
| --- | --- | --- | --- |
| 1 | 単体テスト | `python3 -m unittest discover -s tests` | `Ran 437 tests` / `OK` |
| 2 | ベンチマーク再現性 | `python3 gitswarm/benchmarks/benchmark.py --check` | `PASS` |
| 3 | 投票シミュレーション再現性 | `python3 gitswarm/readout_sim.py --check` | `PASS` |
| 4 | 研究台帳 | `python3 scripts/validate_state.py` | `PASS (sources=23, evidence=86, claims=9, verifications=34, hypotheses=6, relations=235)` |
| 5 | 書誌照合 | `python3 scripts/check_citations.py` | 22 source・**失敗 0** |
| 6 | メモ内引用照合 | `python3 scripts/check_memo_citations.py` | 37 メモ・67 引用・**失敗 0** |
| 7 | メモ内 ID・パス参照 | `python3 scripts/check_memo_ledger_refs.py` | 37 メモ・**dangling 0** |
| 8 | 文書内数値 | `python3 scripts/check_doc_numbers.py` | 2 文書・**stale 0** |

### 8.3 既存テストの更新（2 件）

R4 の完了を前提に書かれていた 2 テストが、投入によって**意図どおり**赤になった。テストが固定していたのは「R4 前の一時状態」なので、規則の側を固定するよう書き換えた。

| テスト | 変更 |
| --- | --- |
| `test_relations.RelationLedgerFilesTest.test_empty_relation_ledger_is_valid` → `test_frozen_base_is_empty_and_the_union_is_valid` | 「統合ビューが空」ではなく「**凍結ベースは 0 バイトのまま**で、統合ビューは有効」。verdict の enum も確認 |
| `test_relations.MemoRelReferenceTest.test_ledger_id_map_has_a_rel_bucket` | `ids["REL"]` が空であることではなく、**統合ビューの ID 集合と一致**することを確認 |

### 8.4 README の現況反映（統合役として実施）

`README.md` の「現在の状態」節に、引用ブロックではなく**現況節**として REL を反映した（数値はすべて実測）。

- 台帳行を `hypotheses=6 / relations=235` に更新（ゲート 8 の stale 6 件のうち 2 件）。
- REL の中身（unassessed 0/86、unexplained 20/86 (23.3%)、provisional 56/86）と、**`refute` 0 件が「反駁なし」ではない**旨を追記。
- 観測キーの注釈 30 件、`state/evidence_keys.*` の説明、`tests/test_evidence_keys.py` の行を追加。
- 検査対象外だった参考段落（「出典 22 件 / EVD 81 件 / 75 件（92.6%）」）を実測（23 / 86 / 20 件 23.3%）に更新した。**この段落はゲートの対象外**なので、機械検査は今後も効かない（§10-5）。
- テスト件数は `sync_doc_counts.py` で 420 → 437 に同期（ゲート 8 の残り 4 件）。

---

## 9. 次に集めるべき観測の提案

| # | 提案 | 対応する穴 |
| --- | --- | --- |
| 1 | **比較対照のある実験**（`HYP-001` の比較形を直接検証） | 残る 20 件のうち 3 件（Agora の負の開示）と、`unresolved` にした 4 行。同一モデル・同一予算で「外部化構造化状態」対「単一セッション巨大プロンプト」を 3 課題以上で走らせ、累積探索効率と再現性（同一手順の再実行一致率）を測る |
| 2 | **`HYP-002` の直接測定を測るか降りるか決める** | `EVD-20261021-4c6f`（n=8 で ρ 識別不能。ρ=0.20 検出に 7,359 項目）。`estimate_rho.py` の検出力解析に沿って規模を見積もり、測らないなら `HYP-002` の `status` を `inconclusive` に落とす |
| 3 | **同一論文の重複登録の解消** | `SRC-20261021-7419` / `8452`。ソース統合はレコード削除＝**人間の承認事項**。統合するまで `observation_key` は付けない（§4(a) の運用を続ける） |
| 4 | **`HYP-20261021-fee7` / `4cdb` の分割** | 支持 25 件・12 件のうち、それぞれ 2 機構・3 機構が混在。分割すると反証条件が sharper になる。分割は新 HYP の追加＋REL の付け替え（付け替えは追記で表現できる） |
| 5 | **書誌・監査系 6 件の扱いを固定する** | `gap_scan` の分母 86 に残り続ける。「説明対象外」フラグか分母からの除外規則を決める（現行は分母固定） |
| 6 | **新仮説の反証実験を 1 本ずつ** | `HYP-20261021-9f99`: 3 モデル×3 ハーネスの直交要因実験で分散分解と R。`-fee7`: リーク審査と δ 正則化を個別に外すアブレーション。`-4cdb`: `gap_scan` 運用前後での推移。`-a10b`: D365 以外の課題で剪定＋要約対全文脈 |
| 7 | **`README` 参考段落の機械検査** | §8.4。現況節の全文を対象にするか、少なくとも本件のような「件数を含む参考段落」を対象に加えるか |

---

## 10. 限界・未解決（「解決」と書かない）

1. **verdict の意味的な正しさは検証していない。** 確認したのは rationale の数値と excerpt の一致、ID の実在、網羅性、重複の不在まで。原典との逐語照合は R3 の作業を信頼している（`docs/parallel-work-ownership.md` §2.1 の「意味的な正しさは未解決」と同じ構造）。
2. **`refute` は依然 0 件**で、反駁の材料は `unresolved` の rationale と §3.1 の裁定注記にしかない。`gap_scan` の「refute 0」を「反駁されていない」と読むのは誤り（§5.3-4）。
3. **`observation_key` はキーの追加しかできない。** 付け替え・削除の手段は無く、誤った束ねを直すには新しい運用（別キーでの再注釈）が要る。今のデータでは 30 件すべてが 2 ソース以上で、誤束ねは検出されていない（テストで固定）。
4. **新仮説 4 件は `proposed`**。`support` 84 行のうち 63 行がこの 4 件に依存しており、4 件が棄却されれば `unexplained` は 20 → 63 に戻る。**この数字は仮説の採否に強く依存する**。
5. **README の参考段落はゲート対象外**のまま（§8.4）。今回手で直したが、次に陳腐化しても機械は止めない。
6. **基準コミットの同一性確認は shallow クローンの制約下**で始めた（`git fetch --unshallow` で解消）。R3 が読んだ時点の `contributions/` 全体の同一性は見ていない。
7. **`provisional` 56 件のうち 5 件は「同一論文の重複」由来**で、独立追試が無いことの正しい表示である。ただし残り 51 件も独立再現が無いだけであり、`observation_key` を足せば下がる種類のものではない。

---

## 11. 変更ファイル一覧

| 種別 | パス |
| --- | --- |
| 台帳（追記） | `state/relations.d/2026-10-21-a194d1a9b885.jsonl`（235 行） |
| 台帳（追記） | `state/hypotheses.d/2026-10-21-3990b64b4fdb.jsonl`（4 行） |
| 注釈（新規） | `state/evidence_keys.jsonl`（空の凍結ベース）、`state/evidence_keys.d/2026-10-21-3ead52ec8d51.jsonl`（30 行） |
| 実装 | `scripts/validate_state.py`、`scripts/gap_scan.py`、`scripts/new_ledger_shard.py` |
| テスト | `tests/test_evidence_keys.py`（新規 17 件）、`tests/test_relations.py`（2 件を更新） |
| 文書 | `README.md`（現況節・構成・参考段落）、`docs/minimal-core-and-ci.md`（件数同期） |
| 記録 | `contributions/2026-10-21_relation_backfill_integration.md`（本文書）、`contributions/2026-10-21_relation_backfill_integration_plan.json`（裁定計画。`status` を `inserted` に更新） |
