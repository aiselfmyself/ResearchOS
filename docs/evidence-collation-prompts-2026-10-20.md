# 証拠照合セッション用プロンプト（2026-10-20）

コピペで渡すプロンプトを 3 本（S1 / S2 / S3）収めた。
対象の定義は `docs/evidence-collation-targets-2026-10-20.md`（以下「対象リスト」）。

**使い方**：各セッションに 1 本を渡す。3 本を同時に走らせてよい（パスは排他的）。
成果の裁定と `state/` への追記は**統合役が行う**。セッションは `state/` を触らない。

---

## 共通の設計根拠（統合役から）

この指示は、2026-10-20 の並列読解実験（E2）で得た教訓を反映している。
E2 では 15 項目のうち 6 件が不一致になったが、**全件が「誤りではない取り違え」**だった。
原因は (a) 自由記述の項目、(b) 数え方の未定義、(c) 文字列比較、(d) 一致率の過小評価。
したがって本タスクでは次を徹底する。

1. **答えが一意に定まる項目だけ**を問う。`verdict` は 4 値の enum で、自由記述にしない。
2. **「いくつあるか」を問わない。** 数値は必ず原典の文字列をそのまま写す。
3. **値は意味的に比較する。** 逐語一致でなくても矛盾しなければ `paraphrase_ok` とする。
4. **判定の内訳を必ず出す。** 素の「一致率」だけで報告しない。

**版の固定**（Agora で v1 を読んだ 2 セッションの記述が v4 で陳腐化した経験による）：

- **最新版を読む**。読んだ版を `version_read` に記録する。
- 最新版で主張が見つからないときは、**メモが引用した版も見てから** `not_found` と判定する。
  「版が変わった」と「メモが誤っている」を混同しないため。
- 両者が異なる場合は `version_delta_note` に差分を書く。

---

## S1（P1: 2507.13334 ＋ P2: 2606.10209）

```
## 前提（必ず最初に読む）

このリポジトリは ResearchOS である。以下のファイルを読むこと。

- `docs/evidence-collation-targets-2026-10-20.md`（対象リスト。§2 の claim 一覧と §3 の判定定義）
- `docs/parallel-work-ownership.md`（所有マップ。§2 の禁止パス）
- `docs/parallel-session-playbook-2026-10-20.md`（§2 の巻き戻し復旧）

## タスク

arXiv の文献 2 本について、`contributions/2026-10-20_context_and_eval_bottlenecks.md` が
述べている数値・定性主張が**原典に実在するか**を照合する。

新しい実験・測定は行わない。原典を読んで、書かれているかどうかを判定するだけである。

- **P1**: arXiv:2507.13334（Context Engineering survey）
- **P2**: arXiv:2606.10209（Less Context）

対象 claim は対象リスト §2 の `C-05de-01`〜`C-05de-06` と `C-787b-01`〜`C-787b-09`。
**文献の指定は必ず arXiv ID で行うこと。**
`context_and_eval_bottlenecks.md` の `[1]` `[2]` と `integrated_survey_report.md` の
`[4]` `[5]` は**同じ文献を指すが番号が違う**（bottlenecks[n] = survey[n+3]）。

P2 は 1 段落に 8 つの数値が並ぶ。最も誤りが入りやすい箇所なので、
1 つずつ原典の表と突き合わせること。

## 版の扱い（必ず守る）

各文献について `https://arxiv.org/abs/<ID>` を開き、**最新版が何か**を確認する。
その最新版の HTML（`https://arxiv.org/html/<ID>vN`）を読む。読んだ版を記録する。
メモが引用した版は P1 = v2、P2 = v1 である。
最新版で見つからない主張は、メモ引用版を確認してから `not_found` と判定する。

## 成果物（この 2 ファイルのみ新規作成）

- `contributions/2026-10-20_evidence_collation_s1.md`
- `contributions/2026-10-20_evidence_collation_s1.json`

`.json` の形式（各文献 1 オブジェクト、claim は配列）：

```json
{
  "source_id": "SRC-20261020-787b",
  "arxiv_id": "2606.10209",
  "memo_cited_version": "v1",
  "version_read": "v1",
  "is_latest": true,
  "version_delta_note": "",
  "claims": [
    {
      "claim_id": "C-787b-05",
      "verdict": "verbatim",
      "locator": "Table 2",
      "source_text": "<原典の該当文字列をそのまま>"
    }
  ]
}
```

`verdict` は次の 4 値のいずれか。**これ以外の値を使わない。**

- `verbatim` — 原典に逐語で、または数値が完全一致で存在する
- `paraphrase_ok` — 逐語ではないが原典の記述と矛盾しない
- `wrong_value` — 該当箇所はあるが数値が違う（`source_text` に**正しい値**を書く）
- `not_found` — 最新版・メモ引用版の両方に存在しない

`.md` には次を書く。(a) 各文献の版と最新版の異同、(b) claim ごとの判定表、
(c) `wrong_value` と `not_found` があれば**その理由と根拠箇所**、(d) サマリ（4 値の内訳）。

**`not_found` と `wrong_value` は歓迎される。** このリポジトリはすでに
「実在しない引用文」（CLM-20261020-b07e）と「著者名の誤り」（CLM-006）を捕捉している。
下流の主張に影響する前に見つけることが目的なので、遠慮なく判定してよい。

## やらないこと

- `state/`（5 台帳すべて）は**統合役専権。触らない。**
- `README.md`、`docs/minimal-core-and-ci.md`、`gitswarm/artifacts/`、`tests/test_minimal_core.py` は触らない。
- 他のセッションの `contributions/` ファイルは**読まない**。独立性を保つため。
  （`context_and_eval_bottlenecks.md` と対象リストは**入力なので読んでよい**。）
- 新規の `scripts/`、`tests/` は作らない。
- 数値の再計算・再現実験はしない。
- 図の画像そのものは読まない（キャプションと本文の記述のみ）。
- 参考文献の原典は辿らない。

## コミット前の必須確認（全て通すこと）

```
python3 -m unittest discover -s tests
python3 gitswarm/benchmarks/benchmark.py --check
python3 gitswarm/readout_sim.py --check
python3 scripts/validate_state.py
python3 scripts/check_citations.py
python3 scripts/check_memo_citations.py
```

メモの参考文献は**1 件 1 物理行**で書き、arXiv ID または URL を含めること
（`check_memo_citations.py` は複数行にまたがる参照を MALFORMED として失敗させる）。

## 完了条件

- 上記 2 ファイルが作成されている
- 全 claim に `verdict` が付いている（未判定を残さない）
- 6 ゲートがすべて通る
- 「やったこと／やっていないこと／検証コマンドの実測値」を PR 本文に書く
```

---

## S2（P3: 2608.06663 ＋ P4: 2610.08364）

```
## 前提（必ず最初に読む）

このリポジトリは ResearchOS である。以下のファイルを読むこと。

- `docs/evidence-collation-targets-2026-10-20.md`（対象リスト。§2 の claim 一覧と §3 の判定定義）
- `docs/parallel-work-ownership.md`（所有マップ。§2 の禁止パス）
- `docs/parallel-session-playbook-2026-10-20.md`（§2 の巻き戻し復旧）

## タスク

arXiv の文献 2 本について、`contributions/2026-10-20_context_and_eval_bottlenecks.md` が
述べている数値・定性主張が**原典に実在するか**を照合する。

新しい実験・測定は行わない。原典を読んで、書かれているかどうかを判定するだけである。

- **P3**: arXiv:2608.06663（Horizon Gap）
- **P4**: arXiv:2610.08364（Transect）

対象 claim は対象リスト §2 の `C-303f-01`〜`C-303f-07` と `C-875e-01`〜`C-875e-05`。
**文献の指定は必ず arXiv ID で行うこと。**
`context_and_eval_bottlenecks.md` の `[3]` `[4]` と `integrated_survey_report.md` の
`[6]` `[7]` は**同じ文献を指すが番号が違う**（bottlenecks[n] = survey[n+3]）。

`C-303f-03`〜`C-303f-05` は 3 概念の定義である。用語の綴りまで含めて原典と突き合わせること。
`C-875e-02` の 4 つの圧力は**用語が原文どおりか**を確認する（日本語訳ではなく原語で）。

## 版の扱い（必ず守る）

各文献について `https://arxiv.org/abs/<ID>` を開き、**最新版が何か**を確認する。
その最新版の HTML（`https://arxiv.org/html/<ID>vN`）を読む。読んだ版を記録する。
メモが引用した版は P3 = v1、P4 = v2 である。
最新版で見つからない主張は、メモ引用版を確認してから `not_found` と判定する。

## 成果物（この 2 ファイルのみ新規作成）

- `contributions/2026-10-20_evidence_collation_s2.md`
- `contributions/2026-10-20_evidence_collation_s2.json`

`.json` の形式（各文献 1 オブジェクト、claim は配列）：

```json
{
  "source_id": "SRC-20261020-303f",
  "arxiv_id": "2608.06663",
  "memo_cited_version": "v1",
  "version_read": "v1",
  "is_latest": true,
  "version_delta_note": "",
  "claims": [
    {
      "claim_id": "C-303f-02",
      "verdict": "verbatim",
      "locator": "Section 3.1",
      "source_text": "<原典の該当文字列をそのまま>"
    }
  ]
}
```

`verdict` は次の 4 値のいずれか。**これ以外の値を使わない。**

- `verbatim` — 原典に逐語で、または数値が完全一致で存在する
- `paraphrase_ok` — 逐語ではないが原典の記述と矛盾しない
- `wrong_value` — 該当箇所はあるが数値が違う（`source_text` に**正しい値**を書く）
- `not_found` — 最新版・メモ引用版の両方に存在しない

`.md` には次を書く。(a) 各文献の版と最新版の異同、(b) claim ごとの判定表、
(c) `wrong_value` と `not_found` があれば**その理由と根拠箇所**、(d) サマリ（4 値の内訳）。

**`not_found` と `wrong_value` は歓迎される。** このリポジトリはすでに
「実在しない引用文」（CLM-20261020-b07e）と「著者名の誤り」（CLM-006）を捕捉している。
下流の主張に影響する前に見つけることが目的なので、遠慮なく判定してよい。

## やらないこと

- `state/`（5 台帳すべて）は**統合役専権。触らない。**
- `README.md`、`docs/minimal-core-and-ci.md`、`gitswarm/artifacts/`、`tests/test_minimal_core.py` は触らない。
- 他のセッションの `contributions/` ファイルは**読まない**。独立性を保つため。
  （`context_and_eval_bottlenecks.md` と対象リストは**入力なので読んでよい**。）
- 新規の `scripts/`、`tests/` は作らない。
- 数値の再計算・再現実験はしない。
- 図の画像そのものは読まない（キャプションと本文の記述のみ）。
- 参考文献の原典は辿らない。

## コミット前の必須確認（全て通すこと）

```
python3 -m unittest discover -s tests
python3 gitswarm/benchmarks/benchmark.py --check
python3 gitswarm/readout_sim.py --check
python3 scripts/validate_state.py
python3 scripts/check_citations.py
python3 scripts/check_memo_citations.py
```

メモの参考文献は**1 件 1 物理行**で書き、arXiv ID または URL を含めること
（`check_memo_citations.py` は複数行にまたがる参照を MALFORMED として失敗させる）。

## 完了条件

- 上記 2 ファイルが作成されている
- 全 claim に `verdict` が付いている（未判定を残さない）
- 6 ゲートがすべて通る
- 「やったこと／やっていないこと／検証コマンドの実測値」を PR 本文に書く
```

---

## S3（P5: 2605.23950 ＋ P6: 2608.13417 ＋ P7: 2610.17184〔低優先〕）

```
## 前提（必ず最初に読む）

このリポジトリは ResearchOS である。以下のファイルを読むこと。

- `docs/evidence-collation-targets-2026-10-20.md`（対象リスト。§2 の claim 一覧と §3 の判定定義）
- `docs/parallel-work-ownership.md`（所有マップ。§2 の禁止パス）
- `docs/parallel-session-playbook-2026-10-20.md`（§2 の巻き戻し復旧）

## タスク

arXiv の文献について、`contributions/2026-10-20_context_and_eval_bottlenecks.md` が
述べている数値・定性主張が**原典に実在するか**を照合する。

新しい実験・測定は行わない。原典を読んで、書かれているかどうかを判定するだけである。

- **P5**: arXiv:2605.23950（Stop Comparing）  — 必須
- **P6**: arXiv:2608.13417（Beyond Final Scores） — 必須
- **P7**: arXiv:2610.17184（DuoDiscover） — **低優先。時間がなければ飛ばしてよい**

対象 claim は対象リスト §2 の `C-07a3-01`〜`C-07a3-08`、`C-4cff-01`〜`C-4cff-08`、
および（余力があれば）`C-003-01`〜`C-003-05`。
**文献の指定は必ず arXiv ID で行うこと。**
`context_and_eval_bottlenecks.md` の `[5]` `[6]` と `integrated_survey_report.md` の
`[8]` `[9]` は**同じ文献を指すが番号が違う**（bottlenecks[n] = survey[n+3]）。

**P5 は特に注意。** bottlenecks メモ自身が §6 で
「数値はいずれも同論文が引用した外部ベンチマークの二次引用である」と注記している。
したがって `C-07a3-03`〜`C-07a3-05` については、
**(a) 数値が原典に存在するか** と **(b) それが自前の実験ではなく外部ベンチマークの二次引用か**
の**両方**を判定し、`source_text` にその根拠を書く。
二次引用である場合は `notes` に「二次引用」と明記する（verdict は `verbatim` のままでよい）。

## 版の扱い（必ず守る）

各文献について `https://arxiv.org/abs/<ID>` を開き、**最新版が何か**を確認する。
その最新版の HTML（`https://arxiv.org/html/<ID>vN`）を読む。読んだ版を記録する。
メモが引用した版は P5 = v1、P6 = v1、P7 = v1 である。
最新版で見つからない主張は、メモ引用版を確認してから `not_found` と判定する。

## 成果物（この 2 ファイルのみ新規作成）

- `contributions/2026-10-20_evidence_collation_s3.md`
- `contributions/2026-10-20_evidence_collation_s3.json`

`.json` の形式（各文献 1 オブジェクト、claim は配列）：

```json
{
  "source_id": "SRC-20261020-07a3",
  "arxiv_id": "2605.23950",
  "memo_cited_version": "v1",
  "version_read": "v1",
  "is_latest": true,
  "version_delta_note": "",
  "claims": [
    {
      "claim_id": "C-07a3-03",
      "verdict": "verbatim",
      "locator": "Table 1",
      "source_text": "<原典の該当文字列をそのまま>",
      "notes": "二次引用（外部ベンチマークの結果）"
    }
  ]
}
```

`verdict` は次の 4 値のいずれか。**これ以外の値を使わない。**

- `verbatim` — 原典に逐語で、または数値が完全一致で存在する
- `paraphrase_ok` — 逐語ではないが原典の記述と矛盾しない
- `wrong_value` — 該当箇所はあるが数値が違う（`source_text` に**正しい値**を書く）
- `not_found` — 最新版・メモ引用版の両方に存在しない

`.md` には次を書く。(a) 各文献の版と最新版の異同、(b) claim ごとの判定表、
(c) `wrong_value` と `not_found` があれば**その理由と根拠箇所**、(d) サマリ（4 値の内訳）。

**`not_found` と `wrong_value` は歓迎される。** このリポジトリはすでに
「実在しない引用文」（CLM-20261020-b07e）と「著者名の誤り」（CLM-006）を捕捉している。
下流の主張に影響する前に見つけることが目的なので、遠慮なく判定してよい。

## やらないこと

- `state/`（5 台帳すべて）は**統合役専権。触らない。**
- `README.md`、`docs/minimal-core-and-ci.md`、`gitswarm/artifacts/`、`tests/test_minimal_core.py` は触らない。
- 他のセッションの `contributions/` ファイルは**読まない**。独立性を保つため。
  （`context_and_eval_bottlenecks.md` と対象リストは**入力なので読んでよい**。）
- 新規の `scripts/`、`tests/` は作らない。
- 数値の再計算・再現実験はしない。
- 図の画像そのものは読まない（キャプションと本文の記述のみ）。
- 参考文献の原典は辿らない（二次引用の**指摘**はするが、その先は確認しない）。

## コミット前の必須確認（全て通すこと）

```
python3 -m unittest discover -s tests
python3 gitswarm/benchmarks/benchmark.py --check
python3 gitswarm/readout_sim.py --check
python3 scripts/validate_state.py
python3 scripts/check_citations.py
python3 scripts/check_memo_citations.py
```

メモの参考文献は**1 件 1 物理行**で書き、arXiv ID または URL を含めること
（`check_memo_citations.py` は複数行にまたがる参照を MALFORMED として失敗させる）。

## 完了条件

- 上記 2 ファイルが作成されている
- P5 と P6 の全 claim に `verdict` が付いている（未判定を残さない）
- P7 を飛ばした場合は `.md` に「P7 は未実施」と明記する（やっていないことを隠さない）
- 6 ゲートがすべて通る
- 「やったこと／やっていないこと／検証コマンドの実測値」を PR 本文に書く
```

---

## 統合役が後にやること

1. 3 本の PR をマージする（衝突すれば当該セッションに復旧させる）
2. `verdict` を裁定する。セッション間で判定が割れた場合は原典を自分で見る
3. `not_found` / `wrong_value` の**訂正 EVD** を起こし、元メモに `correction_note` を付ける
   （EVD-010 / EVD-011 が前例）
4. `verbatim` / `paraphrase_ok` の claim を `state/evidence.jsonl` に追記する
   （ID は `python3 scripts/new_id.py EVD` で採番）
5. 全 6 ゲートを通し、`docs/incomplete-work-audit-2026-10-20.md` に結果を追記する
6. 照合の網羅率（11 ソース中、EVD を持つ割合）を記録する
