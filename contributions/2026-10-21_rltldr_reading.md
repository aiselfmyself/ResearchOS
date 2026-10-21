# RLTL;DR（2609.37633）読解 — Verifier 出力の1文圧縮と、その再利用条件

**読解日**: 2026-10-21
**対象**: 2609.37633 **v2**（2026-10-19 改訂。v1 は 2026-09-29）[cs.LG; cs.AI, cs.CL, stat.ML]、全 16 チャンクを取得して読了
**著者**: Michael Kirchhof, Eleonora Gualdoni, Andrew Szot, Khashayar Gatmiry, Aryo Lotfi, Abbas Kazerouni, Omar Attia, Sanjoy Chowdhury, Alexander Toshev（9 名、Apple）
**題名**: "RLTLDR: Self-improvement by Internalizing Self-generated Feedback"（本文表記は `RLTL;DR`）
**成果物**: 本メモのみ。**`state/`・`schemas/`・`scripts/`・`tests/fixtures/` は一切変更していない**（§11 に SRC/EVD 候補、§1.3 に書誌登録の手順を記載）
**作業ブランチ HEAD**: `683df35f2c27da1d374dfd84971ddf3a549c3bfa`
**節番号の規約**: 引用の出典行（`— §x`）、`〔…〕` の内側、`Table n`、`Appendix X` は**論文 v2** を指す。本メモ自身の節は素の `§x` と書き、紛らわしい箇所では「本メモ §x」と明記する。

> **統合時の注記（2026-10-21）**：本メモは `arena/bd529270-researchos` のコミット `c40042f`（親 `683df35`）で作成されたが、当時は PR が作られず `main` に入っていなかった。人間の指示により、同日に統合役が取り込んだ。本文の実質は書き換えておらず、本注記の追加だけを行っている。
>
> §1.3 の「2609.37633 は書誌スナップショットに未収載」という記述は執筆時点の事実として残す。取り込み時点では、凍結したベースファイルではなく `tests/fixtures/arxiv_metadata_snapshot.d/2026-10-21-850175eaa62c.json` のシャードに同論文が収載されている。一方、台帳への SRC 登録と本メモの書誌表記の統一は本取り込みでは行っていない。
>
> §8.1 などのリポジトリ実測値も `683df35` 時点の値である。その後、台帳は凍結ベース＋シャードの統合ビューへ移行しているため、現在の件数や状態は本メモ本文ではなく `README.md` の「現在の状態」節を参照すること。

---

## 0. 結論（TL;DR）

1. **論文の insight は「1 文・約 15 語・動作の命令形・コードブロックを含まない」1 個の文字列である。**（API 名や enum 名は含む。Table 5 の実例がそうなっている——「タスクの語彙で書く」ことが要件であり、識別子の全否定ではない。） 生成器は 5 フィールドの JSON（summary / feedback / wrong_step_id / corrected_step / hint）を出すが、**使うのは `hint` だけ**で、残り 4 つは「生成精度を上げるための自己回帰的な足場（autoregressive crux）」と明記されている〔論文 §3.2・Appendix A.1〕。**記録形式としての insight は 1 フィールド、しかも出典・時刻・適用範囲を持たない。**
2. **圧縮で捨ててよいのは「エピソード固有の値」で、捨ててはいけないのは「どの検証が落ちたか」である。** 後者を落とすと訓練信号が崩壊する（失敗テストを隠すと Pass@1 が 21.4% → **3.4%**）〔Table 3〕。前者は ID・アクセストークン・検証器の内部ロジックで、保持すると別タスクへ移らない〔§6・Table 6〕。
3. **再利用は「検索」ではない。** 同一タスクの、同一バッチ内の、直前までの失敗 insight を**全部**（上限 16 件、常に最新を含む）連結して user メッセージとして挿入するだけ。**類似度検索も埋め込みもタグも無い**〔§3.2・Appendix A.2〕。挿入条件は「そのバッチの実行成功率 ≤ 50%」——**詰まっているときだけ**である〔Appendix A.2〕。
4. **論文の主張の芯は「重みへの内部化」であり、外部記録の再利用ではない。** insight を文脈に入れるだけでは eval 時の素の性能に移らず（λ=0 で eval 13.2%）、insight トークンに逆伝播してはじめて移る（λ=0.5 で eval 18.9%）〔Table 2〕。**本リポジトリは θ を持たないので、この主経路は原理的に使えない。**
5. **にもかかわらず、本リポジトリに持ち帰れるのは「圧縮の規約」ではなく「圧縮の統制」である。** 論文の圧縮は**何を落としたかを記録しない**。事実性が問題になる台帳では、これは「検証の根拠を消して結論だけ残す」ことに等しい。**提案の中心は §8 の「捨てたものを自己申告する」1 点に絞った。**
6. **論文の数値をそのまま本リポジトリに移すことはできない。** 論文の検証器は**二値・機械実行（unit test）**で、被験体は 9B モデルの rollout、評価は Pass@1 である。本リポジトリの検証は 31 件中 **11 件が判断型**（`logical_consistency` 9 + `falsifier_critic` 2、実測）で、消費者はモデルの重みではなく次に読む人間／エージェントである。**「適用推論」はすべて §7 に分離し、論文の実験結果と混ぜていない。**
7. **採用判断（§9）**: 規約として採るのは (a) 失敗時のみ生成、(b) 先行試行は捨てて 1 文だけ持ち越す、(c) 独立した文脈で生成し直す（連鎖させない）、(d) with/without の対照で効果を測る、の 4 点。**採らない**のは、単文・17 トークン上限、重みへの内部化、類似度検索、insight による rationale の置換。**スキーマは今回変更しない。**

---

## 1. 原典の取得・版・証拠段階

### 1.1 読んだ版

| 項目 | 内容 |
|---|---|
| abs ページ | `arxiv.org` の `abs/` 配下（末尾の ID は 2609.37633。2026-10-21 取得。URL をそのまま書かない理由は §1.3） |
| 投稿履歴 | v1: 2026-09-29 14:04:06 UTC / **v2: 2026-10-19 11:45:34 UTC（これが最新）** |
| 本文 | `https://arxiv.org/html/2609.37633v2`（HTML v2、全 16 チャンクを取得して通読） |
| 依頼時に示された URL | `https://arxiv.org/html/2609.37633v1`。**現行版が v2 だったため v2 を読んだ**（依頼文の指示どおり「実際の最新版を確認し、読んだ版を記録」） |
| ライセンス | CC BY-NC-ND 4.0 |
| 構成 | 本文 §1–§8、References、Appendix A–F（A: プロンプトと詳細、B: 再実装手順、C: insight の実例、D: 交絡を除いた評価、E: 追加分析、F: insight の単純化） |

**v1 と v2 の差分は取得していない。** 依頼文が v1 を指していたため、v1 にしかない記述がある可能性は排除できない（§10.2 に未確認点として記載）。本メモの引用はすべて **v2 の節番号・表番号**である。

### 1.2 取得方法と限界

- サンドボックスの `curl`／`python3` から arxiv.org へは到達できない（既存メモ `contributions/2026-10-21_sheldon_reading.md` §1 と同じ）。Arena の fetch ツールは到達できる。abs ページと HTML v2 の両方を取得した。
- **PDF は取得していない。** 数式・図は HTML のテキスト表現に依存する。図（Fig. 1, 2, 6, 11, 12 など）は**キャプションの文面のみ**を根拠にしており、グラフの読み取りはしていない。
- HTML 化に伴う数式の二重化（例: `→\rightarrow`、`≈\approx`）は引用時に正規化した。**語句そのものは変えていない。**
- `scripts/check_citations.py --live`（arXiv API 照合）は実行していない。

### 1.3 本メモでの書誌表記（重要・CI との関係）

本メモは arXiv ID を **`2609.37633`（`arXiv:` を付けない形）と HTML の URL で表記**している。理由は機械的で、次の 2 点を実測したためである（証拠段階 A）。

1. `scripts/check_memo_citations.py` は `contributions/*.md` 中の `arXiv:<ID>` と `arxiv.org/abs/<ID>` を抽出し、`tests/fixtures/arxiv_metadata_snapshot.json` に無い ID を **MISSING（exit 1）** にする。**2609.37633 は同スナップショットに未収載**である（実測: スナップショットの収載 21 件に含まれない）。
2. 本セッションの制約は「fixture を変更しない」である。したがって **`arXiv:` 形式で書くと CI ゲート 6 が赤になる**（実測: 一時ファイルで確認。`arXiv:` 形式 → `MISSING`／exit 1、HTML URL 形式 → exit 0）。

**これは回避ではなく、順序制約の記録である。** 正しい後続作業は次の 3 手順で、いずれも本セッションでは実施していない。

1. `tests/fixtures/arxiv_metadata_snapshot.json` の `entries` に 2609.37633 を追記する（§11.3 に転記用の値を記載）。
2. `state/sources.jsonl` に SRC を 1 件登録する（ID は `python3 scripts/new_id.py SRC`）。
3. 本メモの表記を `arXiv:` 形式へ直す（直した時点でゲート 6 の照合対象になる）。

> **運用上の発見（本リポジトリへの所見）**: この順序制約は「**スナップショットに無い論文はメモに引用できない**」という意味であり、`docs/worker-handoff-literature-2026-10-21.md` の「優先 5」が「ワーカー自身が fixture を追記してから SRC 登録」と指示している理由でもある。今回はその指示より狭い制約（fixture 不変更）が与えられたため、**書誌登録を伴わない読解メモ**という中間状態が発生した。中間状態を許すなら、`contributions/` の走査対象を「登録済み SRC を持つメモ」に限定するか、未登録 ID を WARN に落とす運用が要る。**本メモはゲートを緩めずに通る側を選んだ。**

### 1.4 証拠段階

本リポジトリの 4 段階基準（`contributions/2026-10-21_sheldon_reading.md` §1 と同じ）に従う。

- **A：再実行可能** — §3.2 の語数計測、§4.4 の共有率の再計算、§8.1 の台帳実測、§8.3 の後方互換の実証、§1.3 のゲート挙動。すべて標準ライブラリのみで再現できる（§13 にコマンド）。
- **B：本文で逐語確認** — §3〜§6 の引用。v2 の本文・表・Appendix を読み、逐語で写した。
- **C：要旨・メタデータ確認** — 書誌（著者 9 名、投稿日、版、カテゴリ）。
- **D：伝聞・未検証** — 本メモには無い。**適用推論は D ではなく「推論」と明示して分離した**（§7 の各項に〔適用推論〕と付す）。

---

## 2. 機構の全体像（圧縮がどこに位置するか）

論文の手法は 3 段階で、**圧縮は第 1 段階の一部**である。この位置を押さえないと「何を捨てているか」を取り違える。

```text
[1] 逐次ロールアウトと insight 生成（論文 §3.2）
    attempt 1（insight なし）
      └─ 失敗 → verifier 実行（unit test）→ o_T に failed asserts
           └─ 新しい会話で「judge」プロンプトに rollout 全体＋verifier 出力を入れる
                └─ 5 フィールド JSON を生成 → **hint（1文）だけ採用、残り4つは破棄**
    attempt 2（insight 1 件を user メッセージとして挿入）
      └─ 失敗 → 同様に insight 2 を生成（attempt 2 の rollout には insight 1 が入っている）
    … K 回まで（上限 16 insight）

[2] GRPO（論文 §3.1）— 成功/失敗の報酬で方策を更新（本リポジトリに関係なし）

[3] 内部化（論文 §3.3）— insight トークンに SFT 損失をかけ、タスク記述 g だけから
    insight を予測させる（π_θ(f|g)）。**推論時には insight を生成しない。**
```

**圧縮は [1] の 1 箇所だけ**で起こる。しかも**二重**である：(i) rollout 全体＋verifier 出力 → 5 フィールド、(ii) 5 フィールド → 1 文。論文が分析しているのは (ii) だけで、(i) の情報落ち（観測の切り詰め）は分析されていない（§10.2）。

---

## 3. 調査項目 1：insight の形式・長さ・必須フィールド

### 3.1 生成物の構造 — 5 フィールド出力、1 フィールド採用

Appendix A.1 の「Prompt 1」は、出力を次の 5 部構成の JSON に固定している（逐語。HTML のエスケープ `\_` `\*` は復元）。

> "As a verifier, you now have to produce a json with FIVE parts: 1) Summarize the agent attempt, 2) Give feedback, 3) Give the step at which it went wrong, 4) Provide the corrected code for that step, 5) Give a one-sentence TL;DR hint."
>
> `{ "summary": "...", "feedback": "...", "wrong_step_id": "integer", "corrected_step": "...", "hint": "..." }`
> — Appendix A.1 "Insight generation"（Prompt 1）

| # | フィールド | 内容（プロンプトの指示） | 記録として使われるか |
|---|---|---|---|
| 1 | `summary` | エージェントの試行の 1 段落要約。「失敗テストはまだ見るな、批評するな」 | **捨てる** |
| 2 | `feedback` | 何が悪かったかの段落。**ground truth の値を明かすな**。最初に壊れた箇所で止める。**rollout に依存しない形にせよ** | **捨てる**（本メモの主対象。§4 参照） |
| 3 | `wrong_step_id` | 誤ったコードを出したステップ ID。特定できなければ -1 | **捨てる** |
| 4 | `corrected_step` | ドロップイン置換できる修正 Python コード | **捨てる** |
| 5 | `hint` | 1 文の TL;DR。「1 文・平易な言葉・コード無し」 | **これだけ使う** |

論文は 4 フィールドを捨てる理由を明示している。

> "We extract this via json parsing and only use the final one-sentence insight in the paper, the remainder is mostly an autoregressive crux to increase test-time compute before providing the insight."
> — Appendix A.1

> "We find that providing the long summary and feedback as hint for the next rollout does not outperform in Section 6. In fact, it reduces performance, likely because one-sentence insights are more general and internalizing them via backpropagation can transfer the knowledge to other similar tasks."
> — Appendix A.1

**したがって「必須フィールド」の答えは 1 個である**: `hint`（1 文）。ID・時刻・出典・信頼度・適用範囲は**持たない**。この欠落が本リポジトリとの最大の差であり、§8 の提案の出発点になる。

### 3.2 長さ

| 主張 | 出典 |
|---|---|
| "short and procedural: typically, a single sentence (**17 words** on average)" | 論文 §6 冒頭 |
| "each insight inserted into the context averages **17 tokens**" | 論文 §3.3 末尾 |
| "the self-generated insight tokens that are in the context (**≈17 tokens** per insight)" | 論文 §1 |

**「17 語」と「17 トークン」は両立しない。** 英語で 15 語の文は通常 19〜22 トークンである。どちらが正しいかを実例で確かめた（証拠段階 A）。

- 対象: Appendix C.1 Table 5 の insight 例 15 件＋ Appendix C.2 Table 6 の TL;DR insight 3 件＝**18 件**（本文に逐語で載っているもの全部）。
- 結果: **平均 15.1 語**（中央値 15、範囲 9〜23）、平均 89 文字、最長 125 文字。
- したがって実データが支持するのは **「17 語」の方**であり、「17 トークン」は過小推定である。差は 15〜20% 程度で結論は変わらないが、**「17 トークン」を根拠に文脈予算を見積もると 2 割ほど甘く出る**。

### 3.3 実例（正確な出典位置つき）

**Appendix C.1 Table 5「Example insight provided by the verifier」**（本文中で「もっとも頻繁に再発した insight」と説明される）。表は「Share / Correction / Examples of insight」の 3 列で、共有率は語彙的重複でクラスタリングした値。

| Share | 修正の型 | insight の例（逐語） |
|---|---|---|
| 15.3% | 大文字小文字 | "Use the uppercase Orange color enum instead of lowercase orange when updating the list color." / "Use uppercase PM instead of lowercase pm when setting the alarm’s AM/PM marker." / "Use the Priority enum value instead of a string when setting the reminder priority." |
| 11.8% | 記録されない動作 | "You need to mark the article as read rather than just viewing it." / "Use the unified search API instead of the ticker search to create a history record that contains the query text." / "You need to create a download event for the mobile listing instead of using the generic task completion function." |
| 11.2% | 余計な引数 | "Call complete_task without passing an answer parameter for non-QA tasks." |
| 5.5% | 保存されない設定 | "You need to set the default chart horizon preference instead of just viewing a chart." / "The list sorting preference needs to be saved to the database, not just the sort configuration updated." |
| 2.1% | 過剰な絞り込み | "Remove the route_type filter to see all hiking trails instead of getting no results." |
| 1.2% | 引数の位置 | "Pass the access token as the first positional argument, not as a keyword argument." |
| 52.3% | Other | "You need to confirm the brand ownership is properly recognized before adding items to cart." / "Use cash instead of checking as the account type." / "You need to actually read or scroll through the article content before completing the task to create a read history entry." / "Use the proper alphabetical sort field instead of title when updating the list sort configuration." |

表の直前の説明が形式を要約している。

> "Each insight names a single corrective action in the vocabulary of the task itself."
> — Appendix C.1

**Appendix C.2 Table 6** は、同じ失敗に対して「診断段落」「修正コード」「TL;DR insight」を並べた表で、**圧縮で何が落ちるかが最も直接に見える箇所**である（§4 で使う）。3 例のうち 2 例を引く。

| 失敗型 | 診断段落（捨てられる） | TL;DR insight（残る） |
|---|---|---|
| 非 QA タスクに answer 引数を渡した | "The task failed because the agent called complete_task() with an answer parameter, but non-QA tasks should not include an answer. The verifier only checks that the BPM filter was set to 125–125, the playlist search results were recorded, and the embed code exists in the database — not the submission method." | "Remove the answer parameter from the complete task call." |
| access token 無しで検索した | "In Step 6, the agent attempts to search for the 'Client Sync' task but fails to include the required access_token parameter in the search_tasks API call. …" | "Include the access token when making the search request so it can access your authenticated notes." |

そして表のキャプションが圧縮の設計思想を一文で述べている。

> "Specificity escalates from a transferable rule to episode-bound detail: the hint names an action, the paragraph names the verifier’s internal check, and the code carries concrete identifiers such as product_id=1 and, in the last row, an access token valid only for that episode."
> — Appendix C.2, Table 6 caption

### 3.4 文脈への挿入形式（実装上の「必須フィールド」）

記録形式ではないが、**再利用時に必ず付く 3 要素**がある。論文 §3.3 が特殊トークン込みの実例を挙げている。

```text
<|im_start|>user
==> A previous Attempt 1 on this same task FAILED the verifier. <==
Hint on what went wrong: <insight 本文>
```

- **何回目の試行か**（`Attempt 1`）
- **検証器に落ちたこと**（`FAILED the verifier`）
- **「何が悪かったかのヒント」というラベル**（`Hint on what went wrong:`）

> "each insight is inserted as a single user message after the task and before the start of the next rollout"
> — Appendix A.2

**示唆（適用推論は §7）**: insight は「単なる文字列」ではなく **`(試行番号, 失敗の事実, ラベル, 本文)` の 4 つ組**として消費される。台帳に記録する場合も、本文だけを残すと「それが失敗に基づく助言である」という文脈が失われる。

### 3.5 論文の形式が本リポジトリに不足しているもの

| 要素 | 論文 | 本リポジトリの VER（実測 31 件） | 欠落すると何が起きるか |
|---|---|---|---|
| 本文（1 文） | あり | 相当するものが**あり得る**（`suggested_actions[0]`。非空 18 件、平均 66 文字だが、1 文の規約は無い） | — |
| 出典ポインタ | **なし**（rollout は捨てられる） | `target_id` がある | insight 単体では検証できない。論文 §6 の 3.4% と同じ構図 |
| 何を捨てたか | **なし** | なし | 情報損失が事後監査できない（§8 の中心提案） |
| 時刻・方策状態 | **なし** | レコード ID の日付のみ | 陳腐化を判定できない（§5.5 の 0.82） |
| 適用範囲 | **なし**（同一タスクにしか使わないので不要） | なし | 横断再利用の可否を機械判定できない |
| 反証可能性 | 検証器が担保（失敗テスト） | `result` と `rationale` が担保 | insight だけになると失われる |

**この表が §8 の設計要求になる。** 論文の形式（1 フィールド）は「同一タスク・同一エピソード内でしか使わない」前提でのみ成立しており、**台帳のように横断再利用する用途には、そのままでは不足する**。

---

## 4. 調査項目 2：何をどう圧縮するか（保持と破棄の区別）

### 4.1 入力と出力

- **入力**: タスク記述 `g`、rollout 全体（最大 50 ステップ。各ステップ最大 768 think + 512 action トークン）、観測（"shortened if exceedingly long"）、検証器の出力（failed asserts）。
  - 上限の算術: 50 × (768 + 512) = **64,000 トークン**（Appendix A.4 のハイパーパラメータからの上限。**典型値ではない**）。
- **中間出力**: 5 フィールド JSON（think に最大 4096、生成に最大 4096 トークン。Appendix B）。
- **最終出力**: 1 文（平均 15.1 語 / 89 文字、§3.2）。
- **圧縮率**: 上限比較で 3 桁。ただし**この数字は「どれだけ捨てたか」であって「どれだけ失ったか」ではない**。論文は後者を測っていない。

### 4.2 破棄する 4 種（論文が明示的に落とすもの）

| 破棄対象 | 論文の根拠 | 落とす理由（論文の説明） |
|---|---|---|
| 試行の要約（何をしたか） | Appendix A.1（"Do NOT consider the failed tests yet"） | 一般性を上げるため。論文 §6 の Table 3 で「summary + 診断段落」は train 13.8% と最も悪い |
| 診断段落（検証器の内部ロジック） | 論文 §6、Table 6 caption | 「検証器の内部チェックに名前を付ける」＝ そのタスクに固有。転移しない |
| 修正コード | 論文 §6、Table 6 caption | エピソード固有のリテラル（`product_id=1`、**アクセストークン**）を含む。次エピソードでは無意味 |
| ground truth の値 | Appendix A.1（"Do NOT reveal ground-truth values (private_data.* and all numbers that are on the right in the unit test asserts)"） | 答えを漏らすと学習信号が壊れる（D.2 の "too-easy ratio"） |

### 4.3 保持する 2 種

| 保持対象 | 論文の根拠 | なぜ落としてはいけないか（実測） |
|---|---|---|
| **どの検証が落ちたか**（失敗の同定） | Table 3「失敗テストを見せない」行 | Pass@1 が 21.4% → **3.4%**（train）/ 19.2% → **10.0%**（eval）。「insight が失敗を正しく同定しているかが最も重要」と本文が明言 |
| **タスクの語彙での矯正動作**（1 つの動作） | Appendix C.1 | これが転移の単位。"names a single corrective action in the vocabulary of the task itself" |

> "What matters most is thus whether the insight correctly identifies the failure."
> — §6（"Insight generator" 段落の末尾）

**この 2 つは非対称である。** 前者を落とすと**品質が崩壊する**（21.4% → 3.4%）。後者を落とす（＝動作ではなく検証器の内部ロジックを書く）と**小幅に下がる**（train 21.4% → 20.3%、eval 19.2% → 18.6%）。要約まで足すとさらに下がる（train 13.8%）。論文の設計は「崩壊させない範囲で一般性を最大化する」であり、**「検証信号は必須、矯正動作の抽象度は調整可能」**という優先順位が読み取れる。

### 4.4 実測された「効く／効かない」（Table 3, SAPI-frontier split。14 行のうち 11 行を抜粋）

すべて **insight を文脈に入れない**状態の Pass@1（＝転移する学習信号の大きさ）。`n_fb` は文脈に入れる insight の上限。

| 設定 | `n_fb` | Train Pass@1 | Eval Pass@1 |
|---|---|---|---|
| 既定（TL;DR、self-generated with thinking） | 16 | 21.4% | **19.2%** |
| 診断段落に置換 | 16 | 20.3% | 18.6% |
| 要約＋診断段落 | 16 | 13.8% | 16.0% |
| 要約＋診断段落＋修正コード | 16 | 15.7%※ | 17.3% |
| **失敗テストの情報を与えない** | 16 | **3.4%** | **10.0%** |
| 生成器を GLM 5.2（thinking）に | 16 | 24.5% | 20.2% |
| 生成器を GLM 5.2（non-thinking） | **1** | 25.5% | 22.7% |
| insight 1 件 | 1 | 20.6% | 18.9% |
| insight 2 件 | 2 | 21.9% | 19.3% |
| insight 4 件 | 4 | 19.1% | 17.8% |
| insight 8 件 | 8 | 23.3% | 20.3% |

※ 論文 §6 本文は「15.6」と書くが Table 3 は「15.7」。**論文内の不一致**（§10.1）。

**読み方（重要）**: この表は「詳細な insight は**学習信号としては**劣る」ことを示す。しかし同じ論文 §6 が、**文脈に入れた場合**は逆だと述べている。

> "When we instead measure Pass@1 with insights in context, summary + diagnostic paragraph yields the largest benefit of any configuration tested, adding **+41.1%** over the Pass@1 of unaided rollouts, against **+36.0%** for TL;DR."
> — §6

> "This suggests that detailed hints help the agent solve the task at hand but do not provide a learning signal that can be internalized for the unaided setup, or generalized to other tasks, while TL;DR insights state reusable rules."
> — §6

**これは本リポジトリにとって決定的である。** 本リポジトリは重みを持たない＝**常に「in context」の側**にいる。したがって論文の Table 3 の主数値（転移しない側）を根拠に「1 文に圧縮せよ」と結論することはできず、むしろ**論文自身の in-context 測定（+41.1% vs +36.0%）が、詳細を残す側を支持する**。この反転は §7.2 の適用案 B に直結する。

### 4.5 圧縮基準の言語化（論文の記述から再構成）

論文は基準を 1 箇所にまとめてはいない。論文 §3.3・§6・Appendix A.1・C.2 から再構成すると次の 3 条件になる（**再構成であり、論文の逐語ではない**）。

1. **失敗を同定しているか**（must）。落とすと 3.4%。
2. **そのタスク集合の外でも真か**（should）。エピソード固有の値・ID・トークン・検証器の内部実装に依存していたら落とす。
3. **rollout を見せずに理解できるか**（must）。プロンプトが明示する。

> "Make it independent of the agent rollout, do NOT assume that the rollout will be shown along with your feedback."
> — Appendix A.1, 2) Give feedback

**この第 3 条件が、実は第 1 条件と衝突する。** rollout を見せずに「どの検証が落ちたか」を伝えるには、検証器の出力（assert の内容）を書くしかないが、それは条件 2（エピソード固有）に触れる。論文の解は「assert の**意味**をタスクの語彙に翻訳する」（例: "Playlist has length 2712 seconds but must be >= 3215 seconds" → "Remember to paginate search results" ではなく "You need to mark the article as read…"）。**この翻訳こそが圧縮の実体であり、同時に最大の情報損失点である。**

---

## 5. 調査項目 3：再利用の条件と検索方法

### 5.1 挿入条件（4 条件、すべて満たすとき）

> "Insight conditioning is triggered if there is at least one insights from a previous failure in the current batch (and thus task) and the running average success rate of the batch is ≤50%."
> — Appendix A.2

1. **同一タスク**（"in the current batch (and thus task)"）
2. **現在のバッチ内の、過去の失敗から生成された insight が 1 件以上ある**
3. **そのバッチの実行成功率（running average）が 50% 以下**（Goldilocks 帯の維持。論文 §3.2）
4. **過去の RL 更新フェーズの insight は含めない**

> "If the task has already been attempted in an earlier RL update phase, we do not include those insights."
> — Appendix A.2

**条件 4 が「有効期限」に相当する。** 別の更新フェーズ＝別の方策状態の産物は使わない。理由は明示されていないが、§5.5 の観測（insight は方策とともに変わる）と整合する。

閾値の感度（Table 9, SAPI hard 386/256 分割）: 0.1 → 14.2%、0.33 → 15.3%、**0.5 → 17.1%**、λ=0.5 で 19.6%。「最初の 10 rollout のうち 3 件以下なら入れる」方式は 19.2%。**閾値は効くが、単調ではない。**

### 5.2 検索は存在しない

- **類似度検索・埋め込み・タグ・BM25 のいずれも無い。** 「そのタスクの、そのバッチの insight を全部連結する」だけ。
- 順序は時系列。各 insight は**独立した user メッセージ**としてタスクの後ろに挿入（Appendix A.2）。
- **先行試行そのものは挿入しない**:

> "We do not insert the entire previous attempt / chat history, because we found this to introduce contextual drag."
> — Appendix A.2（この現象は論文が Cheng et al. 2026 "Contextual drag" を引いている。原典は未読）

**これが圧縮の存在理由である**（"contextual drag" の回避）。論文にとって insight は「検索の対象」ではなく「**履歴を捨てるための代替物**」である。

### 5.3 件数と切り捨て規則

- 既定の上限は **16 件**（`n_fb = 16`）。論文 §6 の ablation は 1 / 2 / 4 / 8。
- **常に最新の insight を含め、それに逆伝播する**:

> "Note that we always use (and backpropagate) the most recent insight."
> — §6

- 件数の効果は**ノイズの範囲**（eval 17.8〜20.3%、train 19.1〜23.3%）。論文 §6 は「run-to-run のばらつきの内側なので傾向として読む」と明記している。**「16 件が最適」という主張は論文に無い。**

### 5.4 効果（探索の改善）

凍結した Qwen 3.5 9B Thinking で、学習前の Pass@k を測ったもの（Appendix E.8）。

| 設定 | Pass@128≈0 のタスク（Fig. 11） | Pass@32≈0 のタスク（Fig. 12） |
|---|---|---|
| i.i.d. サンプリング（insight なし） | 約 6% | 約 13% |
| insight 1 件 | 約 38% | 約 54% |
| **逐次 insight（先行試行に条件づけ）** | **約 57%** | **約 66%** |

> "The largest gains appear in the first 5 insights."
> — Appendix E.8

**「1 件より累積が効く」「効くのは最初の 5 件まで」**は、件数上限を設計する際の唯一の実測根拠である。

### 5.5 insight は時間とともに変わる（陳腐化の実測）

> "Every task falls above the diagonal … with within-visit dissimilarity averaging 0.19 against 0.82 across visits (n=92 revisited tasks)."
> — Appendix E.4（Jaccard、内容語）

同じタスクでも、**同じ方策状態なら言い回しの差は 0.19、方策が進むと 0.82**。つまり記録された insight は「その方策状態における診断」であり、**別の時点では別の insight が出る**。

> "The insight a task receives thus varies substantially between visits, consistent with the policy adopting a different strategy as training progresses and the verifier consequently identifying a different type of failure."
> — Appendix E.4

**本リポジトリへの含意（推論）**: 過去の VER から作った insight を再利用するとき、それは「同じ対象を、同じ検証器で、同じ前提の下で見た結論」でなければ意味を持たない。**陳腐化判定は時刻ではなく「対象と検証条件が変わったか」で行うべき**（§8.5）。

### 5.6 論文自身が「学習できないモデル」向けの道を示している

論文 §7.4 は、insight をデータベース化して検索・挿入する系統（MemRL 等）に触れ、こう述べる。

> "There are multiple recent works that build databases of insights and use a search system to insert them in the prompt when a similar task comes up … We see this as **the most promising path when using untrainable (frontier) models**. However, if there is the possibility to train the model (or even just an adapter), we believe training insights into the model via L_SFT might be the simpler approach. This is because the backpropagation of the insight automatically generalizes it … This removes the need for a dedicated (and often complex) retrieval system."
> — §7.4 "Beyond insight databases"

**本リポジトリは「untrainable」の側である。** したがって論文の推奨に従えば、参照すべきは論文 §7.4 の DB＋検索の道であり、**RLTL;DR 本体（内部化）ではない**。しかし論文はその道を**設計も評価もしていない**（1 段落の見解のみ）。**本メモが「検索方法」について論文から引き出せるのはここまでで、それ以上は論文に無い。**

---

## 6. 調査項目 4：internalization と外部記録としての再利用の分離

### 6.1 論文の 3 層

| 層 | 何をするか | 推論時に insight が要るか | 出典 |
|---|---|---|---|
| **(L1) in-context 条件づけ** | `π_θ(a_t | g, f_1, …, f_I, …)`。学習中の rollout に insight を入れる | **要る** | 論文 §3.2 |
| **(L2) 内部化（internalization）** | `L_SFT` を insight トークンに掛け、`π_θ(f_1,…,f_I | g)` を学習。**推論時には insight を生成しない** | **要らない** | 論文 §3.3 |
| **(L3) SFTL;DR** | L2 だけを実行（GRPO 損失なし）。4k の (task, insight) タプルで学習 | **要らない** | 論文 §5 |

論文が明示的に断る:

> "RLTL;DR never *generates* insight via the π_θ(f|g) we backpropagate on, neither during training, where the inserted insight comes from analyzing previous failed attempts, nor at test time, where the agents needs to one-shot solutions without any insight or sequential attempts."
> — §3.3

**つまり L2 は「insight を生成する能力」を鍛えるのではなく、「タスク記述から insight を予測できるように重みを動かす」ことで、その内容を重みに埋め込む操作である。** insight は学習後には消える（使われない）。

### 6.2 数値で見る分離（Table 2, SAPI frontier 642 タスク、386 train / 256 eval）

| 設定 | Forward tokens | Backward tokens | Train Pass@1 | Eval Pass@1 |
|---|---|---|---|---|
| RLTL;DR（λ=0.5） | 720M | 12M | 21.5% | **18.9%** |
| λ=0.01 | 720M | 12M | 9.3% | 14.0% |
| **λ=0（insight への SFT なし）** | 720M | 11M | 6.1% | **13.2%** |
| GRPO 損失なし・SFT のみ | 9.2M | 839k | 20.0% | 17.0% |
| 通常 SFT（rollout 3.5k 本） | 400M | 6.6M | 28.0% | 20.9% |
| 通常 SFT（rollout 100 本） | 9.5M | 217k | 25.9% | 20.8% |
| SFTL;DR（insight のみ） | 2.9M | 292k | 17.8% | 16.8% |
| SFTL;DR（重複除去 4k） | 4.6M | 68k | 19.1% | 16.9% |

**読み取れること（論文の主張）**

1. **λ=0 だと in-context の効果が eval に移らない**（6.1% / 13.2%）。同じ rollouts・同じ insight を使っているのに、**逆伝播マスクを外すだけで消える**。
2. **λ を 0.5 → 0.01 に落とすだけで eval が 18.9% → 14.0%**。内部化の強さが効く。
3. **L2 だけで L1 のほぼ全性能に届く**（17.0% vs 18.9%）。GRPO 損失は「速く収束させる」ためだけに残す（E.3: 25% 多い環境相互作用で追いつく）。
4. **68k の逆伝播トークンで 6.6M のそれに近い eval**（16.9% vs 20.9%）。論文の言う "compacted training paradigm"。

> "learning to solve tasks with insights in the context does not directly transfer to solving tasks without insights in the context."
> — §3.3（L1 と L2 の分離を述べた一文）

**この一文が本メモの中心的な区別である**: **「文脈に入れる」と「身につける」は別の操作で、前者は後者を自動ではもたらさない。**

### 6.3 「内部化」と「外部記録の再利用」の対応表

| 軸 | 論文の internalization（L2） | 外部記録としての再利用（本リポジトリが取り得る唯一の道） |
|---|---|---|
| 搬体 | θ（重み） | 台帳のレコード＋決定的チェッカ＋CI |
| 書き込み | 逆伝播（マスク反転のみ） | 追記（人間／エージェントの判断） |
| 読み出し | 自動（プロンプトに現れない） | 明示的（誰かが読む・検索する） |
| 一般化 | 意味的平滑性に依存（論文 §7.1「LLMs act as semantic similarity machines」） | **存在しない**（同じ文言が同じ意味で当てはまるかは読む側の判断） |
| 検証 | 下流の Pass@1 で間接的にのみ | 対象を再実行すれば決定的（ただし insight 自体は再実行できない） |
| 情報損失 | **不可視**（何が落ちたか記録されない） | **可視化できる**（§8 の `dropped`） |
| 失効 | なし（次の更新で上書きされる） | git 履歴で判定できる |
| 監査 | 不可能（重みの中） | 可能（レコードが残る） |

### 6.4 本リポジトリにおける「内部化」の analogue は何か

〔適用推論〕本リポジトリに θ は無いが、**「一度きりの判断を、次回以降の判断を拘束する実体に変える」**という機能的対応物は存在する。候補は 3 つで、強さが違う。

| analogue | 実体 | 検証可能性 | 論文との類似度 |
|---|---|---|---|
| (a) 台帳への追記 | `state/*.jsonl` のレコード | 参照整合性のみ（意味は検証されない） | 低（記録であって拘束ではない） |
| (b) 決定的チェッカへの実装 | `scripts/*.py`、`tests/` | **再実行で決定的に検証できる** | 高（「判断」を「手続き」に落とす） |
| (c) CI ゲート化 | `.github/workflows/core-check.yml` | 同上＋マージを止める | 最高（拘束力がある） |

**論文の internalization に最も近いのは (b)(c) であり、(a) ではない。** 論文が L2 で達成したのは「insight を**判断のたびに参照しなくても済む形**に変えること」であり、本リポジトリで同じ効果を持つのは「VER の rationale を読まなくても同じ判定が再現できるチェッカ」である。**記録を増やすこと（a）は内部化ではなく、単なる蓄積である。**

ただし (b)(c) は**論文の意味での一般化をしない**。チェッカは書かれた条件しか検査しない。論文の「意味的平滑性による般化」に対応するものは本リポジトリには無く、**そこは人間の判断で埋めるしかない**。この非対称は §7 の失敗モード F6 になる。

### 6.5 検証可能性の非対称（本メモの結論の一部）

- 論文の L2 は、**成功したかどうかを下流の Pass@1 でしか判定できない**。個々の insight が正しかったかは測られていない（§10.2）。
- 外部記録は、**個々の insight が正しかったかを原理的に監査できる**（元の VER・EVD・原文に戻れる）。ただしそのためには**ポインタが必要**である。
- **したがって「圧縮の形式」を輸入する際、ポインタを落とす仕様だけは輸入してはならない。** これが §8 の設計制約になる。

---

## 7. 調査項目 5：ResearchOS への適用案と失敗モード

> **この節はすべて〔適用推論〕である。** 論文は本リポジトリについて何も述べていない。以下の各項で、根拠が論文の実験結果なのか本リポジトリの実測なのかを明示する。

### 7.1 前提の違い（5 点）

| 軸 | 論文 | 本リポジトリ | 帰結 |
|---|---|---|---|
| 検証器の型 | **二値・機械実行**（unit test、`binary reward r`。論文 §3.1） | 31 件中 `deterministic` 6・`source_check` 14・`logical_consistency` 9・`falsifier_critic` 2（実測）。**11 件（35.5%）が判断型** | 判断型では「どの検証が落ちたか」自体が争点なので、圧縮で最も落としてはいけないものが、最も落としにくい |
| 消費者 | モデルの重み（L2）／同一モデルの次 rollout（L1） | 次の人間またはエージェントのコンテキスト | 論文の主数値（転移しない側）が適用できない。**in-context 側の数値（+41.1%）が該当する** |
| 規模 | 458〜642 タスク、1B トークンの rollout | VER 31 件、rationale 合計 **8,296 文字**（平均 268、中央値 213、最大 769） | **全件を毎回読める規模**。検索基盤は不要（§8.6） |
| 時間 | 同一タスク内の連続試行（分〜時間） | 日〜週をまたぐ台帳（VER の日付は 2026-10-20〜21） | 「同一バッチ」の analogue が無い。有効期限を別途定義する必要（§8.5） |
| 独立性 | 生成器＝失敗した方策（ただし検証器は独立） | 検証器も生成器も同じモデル系（`logical_consistency` 等） | **共通モードの温床**（F7） |

### 7.2 適用案（採用候補 6 件、優先順）

#### A. 記録は「rationale（診断段落）＋ 1 文（矯正動作）」の 2 層にする

- **論文の根拠**: 5 フィールドのうち 2 つ（`feedback` と `hint`）がそれぞれ別の用途を持つ（Appendix A.1）。`hint` は次回の試行に、`feedback` は人間の診断に使われる。両方を残す設計は論文の構造そのもの。
- **本リポジトリの根拠（実測）**: `rationale` は平均 268 文字・平均 5.8 文（中央値 3 文）。**すでに「診断段落」である**。足りないのは 1 文の層だけ。しかも `suggested_actions` は全 31 件に存在し、18 件が非空（平均 66 文字）——**器はすでにある**。
- **差分**: 論文は `feedback` を捨てるが、本リポジトリは捨ててはならない。理由は §6.5（監査可能性）と、`rationale` が `target_id` の検証根拠そのものであるため。

#### B. 1 文の抽象度は「論文の TL;DR」より**詳細側**に置く

- **論文の根拠**: 論文の Table 3 は「詳細は学習信号として劣る」を示すが、同じ論文 §6 が **in-context では詳細が最良（+41.1% vs +36.0%）** と述べている。
- **本リポジトリの根拠**: 本リポジトリは常に in-context 側（θ を持たない）。よって**詳細側を選ぶのが論文のデータに忠実**。
- **注意**: 「+41.1%」は 9B モデルの同一タスク rollout の改善率であり、**人間／エージェントの検証作業の改善率ではない**。数値の移植は不可能で、方向だけを借りる。
- **具体的には**: 1 文に「どの検証が、何と食い違ったか」まで入れる。例（**本メモの作文例**）: 「`scripts/validate_state.py` の `LEGACY_MAX` 検査は ID 形式しか見ないため、参照先の存在は別途検査が要る」。**論文の「no code」（コードを書くな）という制約は採用しない**（§7.2-F）。識別子についても、論文は API 名や enum 名を残している（Table 5）ので、差は「エピソード固有の値か、永続的な参照か」である。

#### C. 生成は「失敗時のみ・独立文脈・連鎖させない」

- **論文の根拠**: (i) 失敗時のみ生成（論文 §3.2）、(ii) 新しい会話で生成し contextual drag を避ける（Appendix A.1）、(iii) 先行試行そのものは持ち越さず 1 文だけ持ち越す（Appendix A.2）。
- **本リポジトリの根拠（推論）**: 既存 VER のうち `pass` は 16/31。**insight を作る対象は 15 件**（`warn` 10・`fail` 5）に限られる。「全部に 1 文を付ける」運用は論文の設計から外れる。
- **「連鎖させない」の意味**: 過去の insight を要約して新しい insight を作るのではなく、**毎回 VER の rationale と対象から作り直す**。理由は論文の E.4（insight は方策状態で変わる）と、要約の要約による誤差蓄積の回避。論文自身は「新しい会話で rollout から生成」であり、**insight の要約を入力にしていない**。

#### D. with/without の対照を必ず取る（deconfounding）

- **論文の根拠**: Appendix D.1 が「insight 条件づけは交絡する」として、**insight の無い rollout だけで指標を計算する**設計を徹底している。D.2 は「insight advantage（with − without）は常に > 0 であるべき」とする。
- **本リポジトリの根拠（推論）**: 「insight を付けたら次の検証が速くなった」は、**付けた本人が読むので当然速い**（自己成就）。比較には「insight 無しで同じ検証をやり直した場合」が要る。31 件という規模でこれを測るのは高コストなので、**まずは §7.5 の安価な代理指標から始める**。

#### E. 台帳の外に「捨てたもの」を書く（§8 の中心提案）

- **論文の根拠**: 論文は 4 フィールドを捨てるが、**捨てたことを記録しない**。その結果、Table 6 が示すように「診断段落にあった検証器の内部ロジック」は永久に失われる。
- **本リポジトリの根拠（推論）**: 本リポジトリの存在理由は「状態をモデルの外で管理する」こと。**情報損失を自己申告しない圧縮は、この原則に反する。**

#### F. 「識別子を落とす」規則は**輸入しない**

- **論文の根拠**: `product_id`・アクセストークン・unit test の RHS を落とす（Appendix A.1、Table 6）。
- **本リポジトリの根拠（実測）**: 31 件の rationale のうち **21 件が台帳 ID（SRC/EVD/CLM/VER/HYP）を含み、9 件がリポジトリ内パスを含む。ポインタを 1 つも持たないのは 5 件だけ**。
- **区別が必要**: 論文の「ID」は**エピソード固有**（次のエピソードでは別の値）だが、本リポジトリの台帳 ID は**永続的な参照**である。**同じ「識別子」でも機能が逆**なので、一律に落とすと監査可能性が壊れる。
  - 落とす: コミット SHA、実行時刻、測定値の一時的な数値（該当 6 件がハッシュ様文字列を含む）
  - 残す: EVD/SRC/VER の ID、`scripts/…` 等のパス、検査名
- **なぜ危険か**: 論文の圧縮は「検証器の内部ロジックを名指ししない」ことで一般化を得ている（Table 6 caption）。本リポジトリではその「内部ロジックの名指し」が**検証の根拠そのもの**である。落とすと、insight は反証不能な助言になる。

### 7.3 圧縮による失敗モード（論文の証拠 → 本リポジトリでの現れ方）

| ID | 失敗モード | 論文内の証拠 | 本リポジトリでの現れ方 | 検出手段（提案） | 重大度 |
|---|---|---|---|---|---|
| **F1** | **検証信号の喪失** — 「何が落ちたか」を落とす | 失敗テストを隠すと Pass@1 **3.4%**（Table 3） | insight が「気をつける」一般論になり、`result` を再導出できない | insight から元の `result` を予測できるか（replay、§7.5） | **高** |
| **F2** | **エピソード固有リテラルの混入** | 修正コードに `access_token='b334de24-…'` が実際に残った（Table 6 最終行。模擬環境のサンプル値と見られる）。ガードはプロンプト指示のみ | 秘密・一時値がメモや台帳に流入する／逆に、永続 ID まで落として参照不能になる | トークン様文字列の走査、`target_id` の解決可否 | 中（秘密漏洩は高） |
| **F3** | **過一般化** — 1 つのタスク族でしか真でない規則 | 共有率で「その他」が **52.3%**、名前付き規則は合計 **47.1%**（Table 5 から再計算。合計 99.4% は端数） | レキシカルに同一の修正としてまとまらない insight が過半（52.3%）。共通の規則として括れないものを横断適用すると誤る | `scope` を持たせ、未設定は再利用しない（fail-closed） | 高 |
| **F4** | **検証器への適合（checker gaming）** — 「検証が通る方法」を学ぶ | Table 6 の insight が "for the verifier to detect" と**検証器を名指し**する | 「主張が正しいか」ではなく「CI が緑になるか」を最適化する。**本リポジトリで最も危険** | insight を主張の語彙で書くことを要求し、検証器名を禁じる | **高** |
| **F5** | **陳腐化** — 古い診断を現在の事実として使う | 訪問間の非類似度 **0.82**（同一訪問内 0.19、n=92、E.4） | 対象ファイルが変わった後の古い insight を適用する | 対象パスの git 更新時刻と記録時刻の比較 | 中 |
| **F6** | **誤った insight が記録されない** | insight の正しさを測る指標が無い（下流の Pass@1 のみ。D.2） | 誤った 1 文が台帳に残り、後続の判断を汚染する（＝捏造 EVD と同型） | 必ず `derived_from` を持たせ、1 文単体では台帳に置かない | **高** |
| **F7** | **共通モード** — 失敗した側が自分の失敗を診断する | 生成器を GLM 5.2 にしても eval 20.2〜22.7%（学生 19.2%）で大差なし。**ただし検証器の信号は常に与えている**。論文 §7.2 は「automated scientific research では insight を得るのに解決と同程度の能力が要るかもしれない」と警告 | `logical_consistency`・`falsifier_critic`（11/31）は検証器自体が判断型。**独立性の担保が無い** | 生成器と検証器の分離（別セッション・別根拠）、`verifier_type` 別の集計 | 高 |
| **F8** | **分布の偏り** — 難しい失敗だけから学ぶ | Pass@128=0 のタスクのみ。成功率 ≤50% のときだけ insight を挿入 | 記録される insight は「珍しい失敗」に偏る。日常的な `pass` の理由は記録されない | 偏りを明示（`population` 相当の注記）。全件に insight を付けない | 低〜中 |

**F4 と F7 が本リポジトリ固有の危険**である。論文の設計ではどちらも問題にならない（検証器が独立で、最適化対象が Pass@1 だから）。**台帳では「検証が通ること」と「主張が正しいこと」が一致しない**ので、F4 は論文より重い。

### 7.4 論文 §7.2 の警告（そのまま引く価値がある）

> "we believe that there might be some domains in which finding a good insight requires the same capability level as generating a valid solution in the first place. While we did not observe this in the tool calling and coding benchmarks in this paper (potentially because we have the privileged information of the verifier), **it might become problematic in domains like automated scientific research**. There, internalizing insight might still work as good as learning from full rollouts, but coming up with the insight might be too hard for our sequential rollout strategy."
> — §7.2 "Limits of (task, insight) learning"

**本リポジトリの領域（文献調査・事実性の検証）は、論文自身が名指しで「問題になるかもしれない」と言った領域に該当する。** これは「適用しない」根拠としては弱い（"might"）が、「無条件に適用する」根拠にはならない。

### 7.5 情報損失の評価設計（論文の指標を移植する案・未実装）

論文 Appendix D.2 は、insight の質を**学習なしで**測る 3 指標を定義している。これは本リポジトリにそのまま移植できる形をしている。

| 論文の指標 | 定義（論文） | 本リポジトリへの読み替え（推論） | 実装コスト |
|---|---|---|---|
| **insight advantage** | 同一タスクで insight あり／なしの Pass@1 差。常に > 0 であるべき | 同じ検証を (a) insight あり／(b) 元の rationale のみ でやり直し、`result` の一致率の差を取る | 高（判断が要る） |
| **insight too-easy ratio** | insight 条件つき rollout が**全部**正解になるタスクの割合。< 20% を目標 | insight を読んだ reviewer が**無条件に**元と同じ `result` を出す割合。高い＝独立検証が確認作業に堕している | 中 |
| **insight too-hard ratio** | insight 条件つき rollout が**全部**不正解になるタスクの割合。< 50% を目標 | insight を読んでも `result` を再導出できない割合 | 中 |

**「too-easy ratio」の読み替えが本メモの工夫である。** 論文では「易しすぎる insight は学習信号を壊す」だが、検証の文脈では**「易しすぎる insight は独立検証を破壊する」**——読む者が考えずに同意してしまう。これは HYP-002（共通モード障害）と同じ構造のリスクであり、**圧縮の副作用として最も見落とされやすい**。

**安価な代理指標（実装可能・未実装）**: 1 文が元の `rationale` の判別要素（パス・台帳 ID・検査名）を保持しているか。実測では rationale の 26/31 が何らかのポインタを持つので、**「1 文がポインタを 1 つ以上保持しているか」は機械で判定できる**。

---

## 8. 調査項目 6：`state/verifications.jsonl` の既存構造に対する後方互換の提案

> **本節は提案であり、`schemas/`・`state/`・`scripts/` を一切変更していない。** 変更したのは本メモだけである。

### 8.1 現状の実測（証拠段階 A、HEAD `683df35`）

| 項目 | 値 |
|---|---|
| VER レコード数 | **31** |
| 必須フィールド（`schemas/verification.json`） | `verification_id` / `target_id` / `verifier_type` / `result` / `rationale` |
| 任意フィールド | `suggested_actions`（array of string） |
| `additionalProperties` | **未指定**（＝追加フィールドを許す） |
| `suggested_actions` を持つ | **31/31**（空 13・1 件 9・2 件以上 9） |
| `suggested_actions[0]` の平均長（非空 18 件） | **66 文字**（最長 207 文字。それはパスと SHA を含む「作業指示」で、1 文の insight ではない） |
| `rationale` の長さ | 合計 **8,296 文字**、平均 268、中央値 213、最大 769、最小 43 |
| `rationale` の文数 | 平均 5.8、中央値 3、最大 19 |
| 台帳 ID を含む `rationale` | **21/31** |
| リポジトリ内パスを含む `rationale` | **9/31** |
| ポインタを 1 つも含まない `rationale` | **5/31** |
| **スキーマに無いフィールドを既に持つレコード** | **`supersedes` を持つものが 4 件**（`VER-005`→`VER-001`、`VER-006`→`VER-002`、`VER-007`→`VER-004`、`VER-010`→`VER-003`） |
| `verifier_type` の内訳 | `source_check` 14 / `logical_consistency` 9 / `deterministic` 6 / `falsifier_critic` 2 |
| `result` の内訳 | `pass` 16 / `warn` 10 / `fail` 5 |

**2 つの重要な事実**:

1. **`supersedes` という未宣言フィールドが既に本番で使われており、`validate_state.py` はそれを許している。** つまり「スキーマファイルを変えずにフィールドを足す」前例が**すでに 4 件ある**。これは後方互換性の議論を抽象論から実測に落とす。
2. **`rationale` は既に「診断段落」であり、`suggested_actions[0]` は既に「短い行動」である。** 論文の 2 層構造（`feedback` + `hint`）は、**名前を変えれば既に存在する**。

### 8.2 層 0（推奨・スキーマ変更ゼロ）：規約だけで 2 層を作る

**提案**: `suggested_actions` の**先頭要素**を「insight スロット」と定め、次の 5 条件を満たすものを *insight*、満たさないものを *action item* と呼ぶ**文書上の規約**にする（スキーマもコードも変えない）。

| 条件 | 内容 | 根拠 |
|---|---|---|
| 1 | 1 文である | 論文 §6（"a single sentence"） |
| 2 | 25 語以内（日本語なら 60 字以内） | 論文の実測は平均 15.1 語・最長 23 語（§3.2）。**上限は実測の最大に合わせる**（17 語に固定しない） |
| 3 | 矯正動作または判定条件を述べる（名詞句で終わらない） | Appendix C.1（"names a single corrective action"） |
| 4 | **永続ポインタを 1 つ以上含む**（台帳 ID かリポジトリ内パス） | 論文と**逆**の要求。§7.2-F の理由（監査可能性）。実測で 26/31 が満たす |
| 5 | エピソード固有のリテラル（SHA・時刻・一時値）を含まない | 論文 Appendix A.1・Table 6 |

- **後方互換**: 既存 31 件は**一切変更しない**。条件を満たさない既存の `suggested_actions[0]` は「action item」と呼ばれるだけで、検証結果は変わらない。
- **測定（実装するなら計測器のみ）**: 条件 2・4・5 は決定論的に判定できる（語数・正規表現）。**条件 1・3 は判定できない**ので、機械判定は 3/5 に留める。**ゲートにしない**（`prune_candidates.py` と同じ「報告のみ」の位置づけ）。
- **欠点**: 「捨てたもの」を記録できない（層 1 で補う）。

### 8.3 層 1（提案・未実装）：任意フィールド `insight` を足す

**後方互換の実証（証拠段階 A）**: `scripts/validate_state.py` の `validate_record()` は「必須フィールドの存在」「型」「enum」「配列要素の型」のみを検査し、未知のフィールドを無視する。実測:

```text
既存レコード単体              → エラー 0
既存レコード + 未知フィールド 2 つ → エラー 0
スキーマ未宣言で台帳に実在するフィールド: {'supersedes'}（4 件）
```

したがって**任意フィールドの追加は、既存 31 件の検証結果を変えない**。ただし `schemas/verification.json` を編集する必要があるため、**本セッションでは実施しない**（人間の承認を要する変更として記録する）。

```json
{
  "insight": {
    "text": "1文。条件は §8.2 の5条件。",
    "derived_from": {
      "verification_id": "VER-…",
      "target_id": "EVD-…",
      "evidence_ids": ["EVD-…"]
    },
    "dropped": ["diagnostic_detail", "episode_literals", "corrected_code"],
    "scope": {"verifier_type": "source_check", "target_kind": "ledger_record"},
    "falsifiable": true,
    "recorded_at": "2026-10-21"
  }
}
```

| フィールド | 型 | 必須 | なぜ要るか（論文の失敗モードとの対応） |
|---|---|---|---|
| `text` | string | ○ | 本体（F1 の防止: 検証信号を含む） |
| `derived_from` | object | ○ | **論文に無い**。無いと insight を検証できない（F6） |
| `dropped` | array of string | ○ | **論文に無い**。情報損失の自己申告（§7.2-E）。空配列は「何も落としていない」の明示 |
| `scope` | object | ○ | 横断再利用の可否を機械判定する（F3）。未設定は再利用しない（fail-closed） |
| `falsifiable` | boolean | ○ | 反証不能な助言を台帳に置かないためのフラグ（F1・F6） |
| `recorded_at` | string | ○ | 陳腐化判定の起点（F5）。レコード ID の日付でも代用可 |

**論文の形式との差分は 4 フィールド**（`derived_from` / `dropped` / `scope` / `falsifiable`）。**この 4 つが「外部記録としての再利用」に必要な最小追加**であり、論文はこれを全部持っていない。持っていない理由は明快で、**論文の insight は捨てられる前提**（重みに移されるか、同一タスク内で消費される）だからである。

### 8.4 層 2（提案・未実装）：再生成ビュー

- insight を**台帳のフィールドとして保存しない**。代わりに、`state/verifications.jsonl` から**毎回決定的に再生成するビュー**（例: `rationale` の第 1 文＋`suggested_actions[0]`）を計算する。
- **利点**: 台帳が単一の真実源のまま。陳腐化しない（常に現在の rationale から作る）。レコードの二重管理が無い。
- **欠点**: 生成器（LLM）を挟むと非決定的になる。**決定的な抽出規則に限る**なら CI に載せられる。
- **論文との関係**: 論文の L2（内部化）に最も近い運用はこれである——「読まなくても済む形に変換する」が、**記録としては残さない**。

### 8.5 再利用の条件（決定論的な規則案）

論文の 4 条件（本メモ §5.1 に整理）を本リポジトリに写像する。**すべて機械判定可能**な形にする。

| 論文の条件 | 本リポジトリの規則 | 判定方法 |
|---|---|---|
| 同一タスク | `target_id` の種別が同じ（例: `EVD-*` を検証した VER を、別の `EVD` の検証に使う） | `target_id` の接頭辞 |
| 同一バッチ内 | 直近の VER（例: 同一セッション・同一日）に限る | ID の日付部分 |
| 成功率 ≤ 50% | 同一 `verifier_type` の**直近 4 件のうち 2 件以上**が `warn`/`fail` のときだけ参照する（論文の閾値と同じ「半分」） | `verifier_type` と `result` の計数（機械的） |
| 過去フェーズは使わない | **`target_id` の対象が記録後に変更されていない**こと | 対象パス（`rationale` 中のパス）の `git log` |
| （追加）最新を必ず含む | 同種の insight が複数あるとき、**最も新しい 1 件以外は表示しない** | 日付 |
| （追加）supersede された VER は使わない | `supersedes` を持つレコードは参照しない | 既存フィールドのみで判定可能 |

**「検索しない」という結論（実測に基づく）**: VER 31 件・`rationale` 合計 8,296 文字。**全部読んでも 1 つのコンテキストに収まる。** 埋め込み検索や索引を作るコストは、全件を読むコストを上回る。論文 §7.4 の DB＋検索の道は、**規模が 2〜3 桁大きくなったときの選択肢**であり、現在の規模では過剰設計である（`docs/literature-triage-2026-10-21.md` §2.2(6) の判断と一致）。

### 8.6 やらないこと（明示）

1. `rationale` を insight で**置換しない**（F1・F6。監査可能性の毀損）。
2. insight を**自動で注入しない**（F4・F7。独立性の毀損）。参照は人間／エージェントの明示的な操作にする。
3. **ゲートにしない**（本リポジトリの `measure_agreement.py` / `estimate_rho.py` / `prune_candidates.py` と同じく計測器に留める）。
4. 既存 31 件の **backfill を一括でやらない**。`rationale` から機械的に 1 文を作ると、まさに F1（検証信号の喪失）を量産する。**新しい VER から規約を適用する**のが最小リスク。

---

## 9. 適用しない／保留する結論

| 項目 | 判断 | 理由 |
|---|---|---|
| 重みへの内部化（L2） | **適用しない** | θ を持たない。原理的に不可能 |
| 単文・17 トークン上限 | **適用しない** | 論文の in-context 測定（+41.1% vs +36.0%）が詳細側を支持。本リポジトリは常に in-context |
| 識別子・コードの除去 | **適用しない** | 永続ポインタは監査の前提。論文の「ID」とは機能が逆（§7.2-F） |
| 類似度検索・埋め込み DB | **適用しない（現規模では）** | 全 VER が 8.3KB。全件読みの方が安い |
| insight による `rationale` の置換 | **適用しない** | F1・F6 |
| insight の自動注入 | **適用しない** | F4・F7 |
| 2 層記録（rationale ＋ 1 文） | **採用（規約として）** | 既存構造で実現可能（§8.2）。論文の構造と一致 |
| 「捨てたもの」の自己申告 | **採用（提案として）** | 本メモの中心。論文に無い、本リポジトリ固有の要求 |
| 失敗時のみ生成・独立文脈・連鎖禁止 | **採用（規約として）** | 論文 §3.2・Appendix A.1・A.2 |
| with/without 対照 | **採用（評価原則として）** | Appendix D.1 |
| replay テスト・3 指標の実装 | **保留** | 判断コストが高く、まず規約の定着を待つ |
| 横断タスクでの再利用効果の測定 | **保留（論文に無い）** | 論文はこれを測っていない。**本リポジトリで測るなら独自実験になる** |

---

## 10. 情報損失・未確認点・論文内の不整合

### 10.1 論文内の不整合（5 件、いずれも結論を変えない）

| # | 内容 | 箇所 |
|---|---|---|
| 1 | insight の長さが **「17 words」** と **「17 tokens」** の両方で書かれている。実例 18 件の実測は平均 15.1 語・最長 23 語で、「語」が正しい | 論文 §6 vs §1・§3.3 |
| 2 | 「要約＋診断段落＋修正コード」の Train Pass@1 が本文 **15.6%**、表 **15.7%** | 論文 §6 本文 vs Table 3 |
| 3 | Table 5 の共有率の合計が **99.4%**（47.1% + 52.3%）。端数と思われるが、合計は明記されていない | Appendix C.1 |
| 4 | 要旨・§4.2 の「12–13%（insight なしの eval）」と Table 2 の「18.9%（eval）」は**別の分割**（前者は §4.2 が扱う 3 データセット全体についての記述、後者は SAPI-frontier 642 タスク）。混同しやすいが矛盾ではない | 論文 Abstract/§4.2 vs Table 2 |
| 5 | §6 本文の "the gap grows to about 55 points (26.2 vs. 21.4)" は HTML の数式崩れで、実際は **約 5 ポイント**（26.2 − 21.4 = 4.8） | 論文 §6（HTML v2 の表記） |

### 10.2 未確認点（論文が測っていない・本メモが確認していない）

**論文側**

1. **圧縮の第 1 段階（rollout → 5 フィールド）の情報損失が未分析。** 観測は "shortened if exceedingly long" と書かれるだけで、切り詰めの影響を測った ablation が無い（Appendix A.1）。
2. **個々の insight の正しさを測っていない。** 指標はすべて下流の Pass@1（D.2）。「間違ったが下流でたまたま通った insight」の頻度は不明。F6 の根拠。
3. **横断タスクでの再利用を一切評価していない。** 同一タスク内の逐次利用のみ（論文 §7.4 は見解のみで実験なし）。
4. **v1 と v2 の差分を確認していない。** 依頼文は v1 を指していた。v2 で結論が変わった可能性は排除できない。
5. **図の読み取りをしていない**（キャプションのみ）。Fig. 2・6・11・12 の曲線形状は未確認。
6. **"insight advantage"・"too-easy/too-hard ratio" の実測値が本文に無い**（定義のみ）。D.2 は「追跡している」と書くが数値を報告していない。

**本リポジトリ側（本メモの限界）**

7. **適用案は 1 つも実装・試行していない。** 効果の見積もりは無い。
8. **replay テストの実現可能性を検証していない。** 「同じ `result` を再導出できるか」の判定者を誰にするか（人間／LLM／スクリプト）で結果が変わる。
9. **既存 31 件の insight 相当（`suggested_actions[0]`）の品質を評価していない。** §8.2 の 5 条件を既存 18 件に当てた採点は未実施。
10. **`supersedes` 4 件の意味を確認していない。** スキーマ未宣言のフィールドであり、いつ・誰が・どの規則で使ったかは未調査。

### 10.3 圧縮が「やってはいけない」ケースの要約

本メモの結論として、**圧縮してはいけない条件**を 3 つに絞る。

1. **圧縮の入力に「検証器の判定」が含まれない場合** — 論文の 3.4% は「検証信号を落とした」結果であり、検証信号の無い insight は学習にも再利用にも耐えない。
2. **圧縮後が反証不能になる場合** — 「気をつける」「適切に扱う」型の 1 文は、反証できないので台帳に置いてはいけない（`falsifiable=false`）。
3. **圧縮の消費者が「独立に検証する者」である場合、詳細を落とすと独立性が壊れる** — F4（checker gaming）と too-easy ratio の読み替え（§7.5）。

---

## 11. SRC/EVD 候補（台帳には未登録。ID は採番していない）

> **ID を書かない理由**: `scripts/check_memo_ledger_refs.py` はメモ中の `PREFIX-YYYYMMDD-xxxx` 形式のトークンを台帳と突き合わせ、存在しなければ exit 1 にする（実測済み・ゲート 7）。本セッションは台帳を変更しないため、**実在しない ID をメモに書くことはできない**。採番は登録時に行う（`python3 scripts/new_id.py SRC`）。

### 11.1 SRC 候補（1 件）

| フィールド | 値 |
|---|---|
| `source_id` | （未採番。`scripts/new_id.py SRC`） |
| `title` | RLTLDR: Self-improvement by Internalizing Self-generated Feedback |
| `authors` | Michael Kirchhof, Eleonora Gualdoni, Andrew Szot, Khashayar Gatmiry, Aryo Lotfi, Abbas Kazerouni, Omar Attia, Sanjoy Chowdhury, Alexander Toshev |
| `year` | 2026 |
| `url` | `https://arxiv.org/html/2609.37633v2`（**v2 を読んだ**。v1 は 2026-09-29、v2 は 2026-10-19） |
| `type` | `preprint` |
| `venue` | arXiv 2609.37633v2 [cs.LG; cs.AI, cs.CL, stat.ML] |
| `abstract_summary` | RLVR は Pass@128=0 のような難タスクで学習信号を失う。失敗後に検証器の出力を見せて方策自身に 1 文の insight を書かせ、次の rollout の文脈に入れる逐次サンプリングと、その insight トークンへの SFT 損失（内部化）を組み合わせる。Qwen 3.5 9B で Pass@1 0–1% → 12–13%（insight なしの eval）。4k の (task, insight) タプルだけでも大部分が再現する。 |

### 11.2 EVD 候補（5 件）

| # | 種別 | 逐語（抜粋） | 出典位置 | 解釈 |
|---|---|---|---|---|
| 1 | insight の形式 | "The insight we provide the model is short and procedural: typically, a single sentence (17 words on average)" | 論文 §6 冒頭 | insight は 1 文・平均 15〜17 語。コードブロックは含まないが、API 名などのタスク語彙は含む |
| 2 | 5 フィールド出力と 1 フィールド採用 | "We extract this via json parsing and only use the final one-sentence insight in the paper, the remainder is mostly an autoregressive crux to increase test-time compute before providing the insight." | Appendix A.1 | 記録されるのは 1 フィールドのみ。要約・診断・ステップ・修正コードは捨てられる |
| 3 | 検証信号の不可欠性 | 失敗テストの情報を与えない設定で Train Pass@1 3.4% / Eval 10.0%（既定は 21.4% / 19.2%） | 論文 §6, Table 3 | 圧縮で「どの検証が落ちたか」を落とすと品質が崩壊する |
| 4 | 再利用は検索ではない | "Insight conditioning is triggered if there is at least one insights from a previous failure in the current batch (and thus task) and the running average success rate of the batch is ≤50%." | Appendix A.2 | 同一タスク・同一バッチ・成功率 50% 以下のときだけ。類似度検索は無い |
| 5 | 内部化と in-context の分離 | "learning to solve tasks with insights in the context does not directly transfer to solving tasks without insights in the context." ＋ Table 2 の λ=0（eval 13.2%）vs λ=0.5（eval 18.9%） | 論文 §3.3, Table 2 | 文脈に入れることと身につけることは別。内部化は逆伝播マスクに依存する |

（任意で 6 件目）"Specificity escalates from a transferable rule to episode-bound detail: the hint names an action, the paragraph names the verifier’s internal check, and the code carries concrete identifiers such as product_id=1 and, in the last row, an access token valid only for that episode." — Appendix C.2, Table 6 caption。**圧縮で何が落ちるかを最も直接に述べた一文**。

### 11.3 fixture 追記用の値（未実施）

`tests/fixtures/arxiv_metadata_snapshot.json` の `entries` に追記する場合の値。既存エントリのキー構成に合わせること（`scripts/check_citations.py` を参照）。

既存エントリのキーは **`arxiv_id` / `source_url` / `title` / `authors` / `published` の 5 つだけ**である（実測。`primary_category` や `venue` は持たない）。追加する値は次のとおり。

| キー | 値 |
|---|---|
| `arxiv_id` | `2609.37633` |
| `source_url` | 既存エントリと同じ形式（`…/abs/` + ID）。**本メモ内にはこの形の URL を書かない**（§1.3 の理由） |
| `title` | `RLTLDR: Self-improvement by Internalizing Self-generated Feedback` |
| `authors` | 上記 9 名（順序どおり） |
| `published` | v1 の提出日 `2026-09-29`（既存エントリの `published` は v1 基準であることを 2610.18025 で確認） |

---

## 12. 参照したリポジトリ内資料

- `state/verifications.jsonl`（31 件、実測）
- `schemas/verification.json`（必須・任意フィールドの確認）
- `scripts/validate_state.py`（`validate_record` の検査範囲、`ID_TOKEN_RE`/`PATH_TOKEN_RE`）
- `scripts/check_memo_citations.py`（ゲート 6 の挙動）
- `scripts/check_memo_ledger_refs.py`（ゲート 7 の挙動）
- `tests/fixtures/arxiv_metadata_snapshot.json`（2609.37633 が未収載であることの確認のみ。**変更していない**）
- `state/hypotheses.jsonl`（HYP-002 との関係）
- `contributions/2026-10-21_sheldon_reading.md`（証拠段階の基準、メモの構成）
- `docs/literature-triage-2026-10-21.md` §2.2(6)（本論文の位置づけ）
- `docs/worker-handoff-literature-2026-10-21.md`（優先 5 の依頼内容と、本来は fixture 追記を含む作業だったこと）

---

## 13. 再現手順（本メモの実測値）

```sh
# §3.2 insight の長さ（18 例の語数）
#   → 平均 15.1 語 / 中央値 15 / 範囲 9–23 / 平均 89 文字（本メモ §3.2 に値を記載）

# §8.1 台帳の実測
python3 - <<'EOF'
import json,re,statistics
recs=[json.loads(l) for l in open('state/verifications.jsonl') if l.strip()]
L=[len(r['rationale']) for r in recs]
print(len(recs), sum(L), round(statistics.mean(L)), statistics.median(L), max(L))
print(sum(1 for r in recs if 'suggested_actions' in r),   # 31（フィールドを持つ）
      sum(1 for r in recs if r.get('suggested_actions')))   # 18（非空）
ledger=re.compile(r'\b(?:SRC|EVD|CLM|VER|HYP)-(?:\d{3}|\d{8}-[0-9a-f]{4})\b')
path=re.compile(r'\b(?:scripts|tests|state|docs|schemas|gitswarm)/[\w./-]+\.(?:py|md|json|jsonl|yml)\b')
print(sum(bool(ledger.search(r['rationale'])) for r in recs),
      sum(bool(path.search(r['rationale'])) for r in recs))
print(sorted({k for r in recs for k in r} - {'verification_id','target_id','verifier_type','result','rationale','suggested_actions'}))
EOF

# §8.3 後方互換の実証
python3 - <<'EOF'
import json,sys
sys.path.insert(0,'scripts'); import validate_state as vs
schema=json.load(open('schemas/verification.json'))
rec=json.loads([l for l in open('state/verifications.jsonl') if l.strip()][-1])
print(vs.validate_record(rec,schema,'x'))
rec['insight']={'text':'…','derived_from':{'verification_id':'x'},'dropped':[],'falsifiable':True}
print(vs.validate_record(rec,schema,'x'))
EOF

# §1.3 ゲート 6 の挙動（一時ファイル。リポジトリは変更しない）
# 1 つ目は「arXiv + コロン + ID」の形を作る（本メモ自身がその形を踏まないよう \x3a で組む）
printf '[1] A. "B" %s2609.37633v2 [cs.LG], 2026.\n' "$(printf 'arXiv\x3a')" > /tmp/m1.md
python3 scripts/check_memo_citations.py --memos /tmp/m1.md   # → MISSING / exit 1
printf '[1] A. "B" 2609.37633v2 [cs.LG], 2026. https://arxiv.org/html/2609.37633v2\n' > /tmp/m2.md
python3 scripts/check_memo_citations.py --memos /tmp/m2.md   # → exit 0

# 全ゲート
python3 -m unittest discover -s tests && python3 scripts/validate_state.py \
  && python3 scripts/check_citations.py && python3 scripts/check_memo_citations.py \
  && python3 scripts/check_memo_ledger_refs.py && python3 scripts/check_doc_numbers.py
```

---

## 参考文献

[1] Michael Kirchhof, Eleonora Gualdoni, Andrew Szot, Khashayar Gatmiry, Aryo Lotfi, Abbas Kazerouni, Omar Attia, Sanjoy Chowdhury, Alexander Toshev. "RLTLDR: Self-improvement by Internalizing Self-generated Feedback." 2609.37633v2 [cs.LG], 2026. https://arxiv.org/html/2609.37633v2
