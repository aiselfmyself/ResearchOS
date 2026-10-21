# 単一ワーカー対3並行ワーカー比較実験：並行アーム P3 抽出メモ（2026-10-21・参考実行）

- 種別：実験実行ワーカー（並行アーム P3）の項目抽出成果物。設計文書 [`docs/single-vs-multi-experiment-2026-10-21.md`](../docs/single-vs-multi-experiment-2026-10-21.md) §5 の「担当」列で P3 に割り当てられた **17 項目のみ**を扱う。
- 対応 JSON：[`contributions/2026-10-21_svm_parallel_p3.json`](./2026-10-21_svm_parallel_p3.json)
- 位置づけ：**参考実行**。開始時の HEAD が当初予定の共通開始コミットと一致しなかったため、同条件比較の厳密な一員としては扱わない（詳細は §6）。条件逸脱の評価と統合は X4 と人間が行う。
- 本メモは統合・真値確定・他アームの採点を行わない。他アーム・他ワーカーのブランチ、PR、成果物は見ていない。

---

## 1. 実行の基本情報

| 項目 | 値 |
|---|---|
| arm | `parallel` |
| worker | `P3` |
| branch | `arena/f53b7182-researchos` |
| base_commit（開始時の実 HEAD） | `91a08f4321d4aee42bca6cb02641b7c32dce4539` |
| 当初予定の共通開始コミット | `ccf76aa654c1344e7bc7862bc835cf1420c98ff8` |
| 一致・不一致 | **不一致**（実 HEAD は予定コミットの 13 コミット子孫。`git merge-base --is-ancestor` で祖先関係を確認） |
| 開始時刻（UTC） | `2026-10-21T09:09:19Z`（`date -u +%Y-%m-%dT%H:%M:%SZ`） |
| 成果物 JSON の内容確定時刻（UTC） | JSON の `session_log.finished_at_utc` を正とする（ゲート実行と PR 作成はこの時刻に含めない） |
| UI 上の表示モデル名 | unknown（表示を確認できなかったため `unknown` と記録） |

## 2. 固定版一次資料の版確認（転記）

| 取得元 | 版表示（実測の転記） |
|---|---|
| `https://arxiv.org/html/2609.37633v2` | HTML 冒頭の表示：`arXiv:2609.37633v2 [cs.LG] 19 Oct 2026`（見出しは `RLTLDR: Self-improvement by Internalizing Self-generated Feedback`、著者ブロックの所属は `Apple`、日付行は `October 19, 2026`） |
| `https://arxiv.org/abs/2609.37633v2` | `arXiv:2609.37633v2 (cs)`、`last revised 19 Oct 2026 (this version, v2)`、Submission history の `[v2] Mon, 19 Oct 2026 11:45:34 UTC` |

- 版付き URL から別版へ誘導される形跡は無く、**v2 を確認**した。版なし URL・別版・PDF は使っていない。
- 取得経路：Arena の web fetch（HTML v2 を 16 チャンク、abs v2 を 1 チャンク）。PDF は未使用。
- リポジトリ内要約（インベントリ等）は根拠に使っていない。

## 3. 担当 17 項目の回答（型は設計文書 §4.1 に従う）

| ID | 型 | 回答 | 一次資料内の所在 | confidence |
|---|---|---|---|---|
| Q03 | 列挙 | `["cs.LG", "cs.AI", "cs.CL"]` | abs ページ（v2）Subjects 欄 | high |
| Q06 | 数値 | `13` | 要旨（abs・HTML 共通。「12–13% when no insight is in context at eval time」の上限） | high |
| Q09 | 数値（整数） | `9` | HTML 版全体の「Table N:」キャプション（Table 1〜Table 9） | high |
| Q10 | 数値（整数） | `13` | HTML 版全体の「Figure N:」キャプション（Figure 1〜Figure 13） | high |
| Q12 | 数値（整数） | `17` | §1 Introduction（insight を導入する段落、「≈17 tokens per insight」） | high |
| Q15 | 列挙 | `["source", "explicitness", "transfer mechanism"]` | §2 Related Works の小段落「Guiding exploration with privileged information」 | high |
| Q16 | 列挙 | `["SDPO", "RLTF"]` | §2 Related Works の小段落「Internalizing context into weights」 | high |
| Q22 | 短文逐語 | `Sort the notes to find the most recent one.` | §3.3 Insight internalization（具体例の段落） | high |
| Q23 | 短文逐語 | `Qwen 3.5 9B (with thinking)` | §4.1 Experiment setup / Datasets（Pass@128=0 選別の段落） | medium |
| Q26 | 数値（整数） | `1624` | §4.1（held-out 集合の説明段落、「SAPI has 1624 tasks on 4 unseen apps」） | high |
| Q30 | 数値 | `42.2` | Table 1（RLTF-SD 行、Leetcode 列） | high |
| Q33 | 数値（整数・換算済み） | `68000` | Table 2（`SFTL;DR on insights, deduplicated` 行、Backward Tokens 列） | medium |
| Q34 | 数値 | `0.6` | Table 2 キャプション（「All results are ±0.6% standard deviation」） | high |
| Q40 | 数値 | `75` | Appendix A.3.2 Positive-ratio filtering | high |
| Q43 | 数値（整数） | `75` | Appendix F.1、Table 8 の脚注 | high |
| Q46 | 短文逐語 | `Remove the answer parameter from the complete task call.` | Appendix C.2、Table 6（Failure type: answer argument passed to a non-QA task の TL;DR insight 行） | high |
| Q49 | 数値 | `0.034` | Appendix E.5 Insight reliance（「Insight reliance remains mild.」段落） | high |

値が見つからず `null` とした項目は無い（17 項目すべてで所在を特定できた）。

## 4. 数え方・換算・書式についての処理メモ

- **Q03**：Subjects は `Machine Learning (cs.LG); Artificial Intelligence (cs.AI); Computation and Language (cs.CL); Machine Learning (stat.ML)`。設問が `cs.XX` 形式に限るため `stat.ML` は含めていない。値はコード表記のみ（分野名は付けない）。
- **Q09・Q10**：§4 の数え方（「Table N:」「Figure N:」のキャプションを持つ実体のみ、本文中の参照言及は数えない）に従い、HTML 全文（本文＋付録）を通して数えた。Figure 2／9／10 は (a)(b)(c) の複数パネルだが、キャプションは各 1 つなので 1 実体として数えた。HTML には付録 C.1 の本文で Table 5 を「Figure 5」と表示する参照リンクの表記揺れがあるが、キャプション自体は `Table 5:` であり、別途 E.4 に実体としての `Figure 5:` が存在するため、表 9・図 13 の計数は変わらない。
- **Q12**：原典表記は `≈17 tokens`。近似記号を除いた整数部分 `17`。§3.3 末尾にも「averages 17 tokens」と再掲がある。
- **Q15**：原典は「These approaches differ along three axes: the source of the guidance, its explicitness, and the transfer mechanism …」。斜体で名指しされた 3 語をそのまま列挙した。
- **Q22**：§3.3 の例では 1 つ目の insight が `Remember to paginate search results.`、2 つ目が本項目の文。設問は「2 番目」を問うため後者を採った。
- **Q23**：指定箇所（§4.1 Datasets の Pass@128=0 選別段落）の表記は `Qwen 3.5 9B (with thinking)`。原典には `Qwen 3.5 9B Thinking`（§1・§E.8）や `Qwen 3.5 9B`（§4.1 Baselines）の表記も併存するため confidence は medium とした。設計文書 §5 の注が「書式差分類の対象になりやすい項目」として事前に名指ししている項目である。
- **Q33**：Table 2 の Backward Tokens 欄は HTML 上で数字が二重に描画される（例：`1212M`＝12M、`6868k`＝68k）。同一表の他の行（`839839k`＝839k、`217217k`＝217k、`292292k`＝292k、`6.66.6M`＝6.6M）と §5.2 本文の「4.6M forward … 68k backwards」で整合を確認し、`68k` = 68,000 と確定した。HTML の表記確定が難しい項目として設計文書が事前に名指ししているため confidence は medium とした。
- **Q34**：`±0.6%` の数値部分 `0.6`。% 記号は付けない。
- **Q40**：`ensure that 75% have a positive reward` の数値部分 `75`。
- **Q43**：Table 8 の `Self-play insight SFT` 行の脚注「This run's training crashed at update 75」。表本体の値ではなく脚注の更新番号を採った。
- **Q46**：Table 6 の当該行の TL;DR insight は `Remove the answer parameter from the complete task call.`（末尾のピリオドを含め原典どおり。引用符は付けない）。
- **Q49**：`+0.034 over the second`（訓練の後半で平均した insight reliance）。符号は付けず数値 `0.034`。

## 5. 独立性・規律の遵守

- 他アーム・他ワーカーのブランチ、PR、成果物の内容は読んでいない。PR 一覧も参照していない（`gh` 未使用）。
- `git fetch origin <ccf76aa の SHA>` と `git fetch --unshallow origin` を実行した（祖先関係の確定のため）。ブランチの切替・reset・rebase・改名・削除は行っていない。
- ブランチは `arena/f53b7182-researchos` のみを使用した。
- `state/`、既存メモ、コード、fixture、設計文書は変更していない。作成したファイルは本メモと対応 JSON の 2 件のみ。
- 付随的な露出：オフライン書誌スナップショットの分割ファイル（`tests/fixtures/arxiv_metadata_snapshot.d/`）の注記に他アームの成果物ファイル名が現れたが、そのファイルの内容は開いていない（ゲート 6 の前提確認のためにスナップショット側のみを確認）。また、`git diff --name-status` の出力に他アーム成果物の**ファイル名**が含まれる（内容は未読）。いずれも内容の参照はしていない。

## 6. 逸脱・待機・再指示（計測への影響）

1. 前回の投入（2026-10-21T09:04:27Z 開始）では、開始 HEAD が当初予定の共通開始コミットと一致せず、さらに同一担当列の成果物が既に存在したため、人間の指示により**抽出を開始せず停止**した（成果物なし・ゲート未実行）。本実行はその後の再指示による。
2. 本実行は「開始コミット不一致を許容した参考実行」である。予定コミット `ccf76aa654…` から開始したのではなく、実 HEAD `91a08f43…` から開始した。**予定コミットから開始したという記録はしていない。**
3. 実 HEAD は予定コミットの 13 コミット子孫であり、その差分にはゲート用スクリプト（`scripts/validate_state.py` 等）の変更が含まれる。したがって本実行のゲートは当初の共通開始時点とは異なるスクリプト版で走っている。この条件差の評価は行わない（X4 と人間の担当）。
4. 待機：本実行中に人間の応答待ちは無い。前回停止分の待機は上記 1 に含まれる。

## 7. 検証

- 担当 ID・件数・重複・型・必須欄の自己検査は、JSON 確定後に `python3` による機械検査で行う（担当 17 件、重複なし、`arm`/`worker`/`base_commit`/`items`/`session_log` の必須欄、`session_log` の必須 9 欄）。
- 8 ゲートは JSON と本メモの確定後に実行し、終了コードと実測結果は PR 本文に転記する。本メモ確定時点ではゲート未実行である。
