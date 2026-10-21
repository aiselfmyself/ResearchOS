# 別ワーカーへの引き継ぎプロンプト（2026-10-21）

`docs/literature-triage-2026-10-21.md` で優先順 5 件に絞った文献について、
**新しいチャットに貼り付けて開始できる**プロンプトをまとめた。

各プロンプトは**単独で完結**するように書いてある（前提知識を要求しない）。
上から順に優先度が高い。**1 チャット = 1 論文**を想定している。

---

## ⚠️ 全プロンプト共通の重要制約（必ず読んでから使うこと）

### 1. このサンドボックスからは arXiv に到達できない

 outbound が許可されているホストは
 `github.com` / `codeload.github.com` / `api.github.com` / `registry.npmjs.org` / `pypi.org` / `files.pythonhosted.org`
 のみ。**`arxiv.org` は含まれない。** したがって原典を自分で取得できない。

### 2. 5 件すべてが書誌スナップショットに存在しない

`tests/fixtures/arxiv_metadata_snapshot.json`（10件）に、今回の 5 件は**1件も入っていない**（確認済み）。

そして `scripts/check_citations.py` は、

```
entry = entries.get(arxiv_id)
if entry is None:
    report.append(f"MISSING {source_id} {arxiv_id} (not in metadata snapshot)")
```

**「スナップショットに無い arXiv ID」を `MISSING`＝失敗**として扱う（CI ゲート5）。

### 3. したがって——**原典なしで `sources.jsonl` に登録してはならない**

やると **CI が赤になる**。原典を確認できない状態で書誌を登録することは
**内容の捏造リスク**と**ゲート破損**の両方を招くので、禁止する。

### 4. 推奨する進め方（2 つの経路）

- **経路 A（推奨）**：人間が原典（PDF / HTML）を入手してチャットに添付する。
  ワーカーはそれを読み、`tests/fixtures/arxiv_metadata_snapshot.json` に
  **確認できた書誌（arxiv_id / title / authors / published）を追記**したうえで
  `state/sources.jsonl` に登録する。これなら全ゲートが緑を保てる。
- **経路 B（原典が無い場合）**：`state/` には**一切書き込まない**。
  代わりに `contributions/2026-10-2X_<paper>_triage.md` として
  「**未照合メモ**」を書き、冒頭に
  「**本メモは `abstract_summary_ja`（日本語要約）のみに基づく。原典未照合。証拠段階 C。
  `state/` には登録していない**」と明記する。

**どちらの経路を採るかは、プロンプト冒頭で人間が指定する。**

---

## 共通の前置き（各プロンプトに含めている内容）

- リポジトリ `/home/user/ResearchOS`、ブランチ `arena/ac3628ba-researchos`
- **報告は日本語**
- 証拠段階の使い分け：**A**＝自前で実行・測定した結果 / **B**＝原典の逐語引用 / **C**＝原典数値からの導出・未照合の記述
- ID は `python3 scripts/new_id.py SRC --count 1 --date 2026102X` で採番する（連番禁止・並行作業での衝突防止）
- `state/` と `README.md` への書き込みは統合役の担当（`docs/parallel-work-ownership.md` §2）。
  **経路 A で `sources.jsonl` を触る場合は、その旨を明示して報告すること**
- 変更後は**全 8 ゲート**を走らせる（下記）
- **「明らかな誤りは放置せず直す」**——ただし人間判断を要する削除は勝手に行わず、エスカレートする

```sh
python3 -m unittest discover -s tests            # ゲート1
python3 gitswarm/benchmarks/benchmark.py --check # ゲート2
python3 gitswarm/readout_sim.py --check          # ゲート3
python3 scripts/validate_state.py                # ゲート4
python3 scripts/check_citations.py               # ゲート5  ← 書誌を触るなら最重要
python3 scripts/check_memo_citations.py          # ゲート6
python3 scripts/check_memo_ledger_refs.py        # ゲート7
python3 scripts/check_doc_numbers.py             # ゲート8
```

---

# 優先 1：RRSI（`arXiv:2609.24972`）★ 最優先

> 以下のプロンプトを新しいチャットに貼り付けて開始してください。
> `【経路A】`/`【経路B】` はどちらか一方を消してください。

```
あなたは ResearchOS リポジトリ（/home/user/ResearchOS、ブランチ arena/ac3628ba-researchos）
の文献調査ワーカーです。報告は日本語でお願いします。

## 目的
arXiv:2609.24972 "RRSI: Regularized Recursive Self-Improvement of Agent Harnesses"
を精読し、本リポジトリ（arena.ai + GitHub による小規模 GitSwarm 型の研究運用）に
実装できる具體的な設計要素を抽出してください。

【経路A】原典を添付します。それを読んでください。
【経路B】原典はありません。docs/literature-inventory-2026-10-19.jsonl の
        paper_id=arXiv:2609.24972v2 の abstract_summary_ja と researchos_mapping と
        researchos_design_influence_assessment を根拠にしてください。

## なぜこの論文か（背景）
本リポジトリは「ハーネスが性能差の帰属先である」という論点を繰り返し扱ってきました
（arXiv:2605.23950 の HV/MV=7.80、監査 ID 14、報告 §3.3）。しかし
**「ではハーネスをどう改善するか」の方法論を持っていません**。
RRSI はそれに直接答える候補です。

すでに粗検討（docs/literature-triage-2026-10-21.md）で、RRSI の設計要素と
本リポジトリの既存機構の対応表を作ってあります。実装済なのは上 3 行だけで、
**下 2 行が未実装**です。ここを埋める具體手法を知りたい。

| RRSI の要素 | 本リポジトリ | 状態 |
|---|---|---|
| 差分単位でハーネス変更を評価 | PR ＋ CI 8 ゲート | ✅ |
| 変更の仮説・diff・スコア・採否を記録 | state/verifications.jsonl / hypotheses.jsonl | ✅ |
| 失敗を次ラウンドへ再投入 | 監査の「未対応」リスト | ✅ |
| **固定タスクへの過適合を避ける（hold-out/OOD 分離）** | — | ❌ 未実装 |
| **低寄与コンポーネントの剪定** | — | ❌ 未実装 |

## 特に知りたいこと（優先順）
1. **過適合回避の具體手法**：1ラウンドの編集数制限は「いくつ」か、その根拠は何か。
   過去の採否・仮説履歴をどう使って探索の偏りを抑えるのか。
   hold-out と OOD は**どう分けて**定義されているか。
2. **剪定の判定基準**：「価値の乏しいコンポーネント」をどう測るか。
   閾値・観測期間・統計的有意性の要件はあるか。**剪定の誤判定をどう防ぐか**。
3. **採用条件**：候補リーク・評価ノイズ・性能とコストの関係を、それぞれ
   どう検査して採用可否に織り込むか。
4. **再現に必要な最小構成**：本リポジトリ規模（並列セッション 2〜4、台帳 49 EVD、
   CI 8 ゲート、決定論的検査のみ、モデル学習なし）で**現実に実装できる部分**と
   **学習を前提とするため不可な部分**を分けてください。

## 制約（必ず守ること）
- **このサンドボックスからは arxiv.org に到達できません**（許可ホストは github.com 等のみ）。
  自分で取得しようとしないでください。
- 5 件すべて tests/fixtures/arxiv_metadata_snapshot.json に**存在しません**。
  scripts/check_citations.py は「スナップショットに無い arXiv ID」を MISSING＝失敗
  として CI ゲート5 を赤にします。**原典を確認できない状態で state/sources.jsonl に
  登録してはいけません。**
  - 【経路A】原典を読めた場合のみ、スナップショットに確認済み書誌を追記したうえで登録可。
  - 【経路B】state/ には一切書き込まないこと。
- ID は python3 scripts/new_id.py SRC --count 1 --date 2026102X で採番（連番禁止）。
- 証拠段階 A/B/C を必ず明記。原典未照合の記述は必ず C とラベル付けする。
- 原典を読んでいない内容を「読んだ」ように書かないこと。

## 成果物
【経路A】contributions/2026-10-2X_rrsi_reading.md ＋ state/sources.jsonl への SRC 登録
        ＋ 主要箇所の EVD（3〜6件）＋ VER 1件
【経路B】contributions/2026-10-2X_rrsi_triage.md のみ（state/ は触らない）。
        冒頭に「原典未照合・証拠段階 C・state/ 未登録」を明記。

## 完了条件
全 8 ゲートが exit 0 であること（下記を実行して確認）。

python3 -m unittest discover -s tests && python3 gitswarm/benchmarks/benchmark.py --check \
&& python3 gitswarm/readout_sim.py --check && python3 scripts/validate_state.py \
&& python3 scripts/check_citations.py && python3 scripts/check_memo_citations.py \
&& python3 scripts/check_memo_ledger_refs.py && python3 scripts/check_doc_numbers.py

## 途中で判断に迷ったら
人間判断を要する削除・撤回は**勝手に行わず**、報告して指示を仰いでください。
```

---

# 優先 2：Stellar Colosseum（`arXiv:2609.15983`）

```
あなたは ResearchOS リポジトリ（/home/user/ResearchOS、ブランチ arena/ac3628ba-researchos）
の文献調査ワーカーです。報告は日本語でお願いします。

## 目的
arXiv:2609.15983 "Stellar Colosseum: A Many-Agent Harness for Long-Horizon Research
in Mathematics and Theoretical Computer Science" を精読し、
**「反証を影響箇所へ戻す修復ループ」**の具體的なデータ構造を抽出してください。

【経路A】原典を添付します。それを読んでください。
【経路B】原典はありません。docs/literature-inventory-2026-10-19.jsonl の
        paper_id=arXiv:2609.15983v2 の各フィールドを根拠にしてください。

## なぜこの論文か（背景）
本リポジトリの台帳 state/claims.jsonl は counterclaim_ids（反証）を持ちます
（監査 ID 5 で空だったのを 4 件紐付け済み）。しかし
**反証を「記録」するだけで、その反証が主張のどの部分を崩すか＝影響箇所への
返し方を持っていません**。state/verifications.jsonl の VER は target_id を
1 つしか持たず、「どこへ返すか」が表現できない。

本論文の要約には「節単位の依存関係を持つサブ問題を作り、Verifier の指摘を
影響箇所へ戻す」とあります。**この「戻し方」のデータモデル**が知りたい。

## 特に知りたいこと（優先順）
1. **readiness gate の判定基準**：「分解可能な成熟度に達したか」を何で判定するか。
   閾値・シグナル・判定の失敗時の扱い。
2. **反証のルーティング**：Verifier の指摘を「影響箇所」へ戻すとき、
   影響箇所はどう表現されているか（グラフ？依存リスト？部分問題 ID？）。
   **具體的なフィールド名やデータ構造**があればそのまま写してください。
3. **並列候補の統合**：複数候補と批判をどう統合するか。多数決か、スコアか、
   構造的な差分か。本リポジトリの gitswarm/readout_sim.py（同質ワーカーの多数決＝
   共通モード障害の決定論的測定）との違いも論じてください。
4. **本リポジトリ規模で実装できる部分**：タスクは数学/TCS の証明構築であり、
   本リポジトリは「非定量的な研究プロセスの研究」です。
   **そのまま転用できるか、それとも抽象だけ借用すべきか**を明示してください。

## 制約（必ず守ること）
- **このサンドボックスからは arxiv.org に到達できません**（許可ホストは github.com 等のみ）。
- 本論文は tests/fixtures/arxiv_metadata_snapshot.json に**存在しません**。
  scripts/check_citations.py は「スナップショットに無い arXiv ID」を MISSING＝失敗として
  CI ゲート5 を赤にします。**原典を確認できない状態で state/sources.jsonl に
  登録してはいけません。**
  - 【経路A】原典を読めた場合のみ、スナップショットに確認済み書誌を追記したうえで登録可。
  - 【経路B】state/ には一切書き込まないこと。
- ID は python3 scripts/new_id.py SRC --count 1 --date 2026102X で採番（連番禁止）。
- 証拠段階 A/B/C を明記。原典未照合の記述は必ず C とする。

## 成果物
【経路A】contributions/2026-10-2X_stellar_colosseum_reading.md ＋ SRC 登録 ＋ EVD 3〜5件
【経路B】contributions/2026-10-2X_stellar_colosseum_triage.md のみ（state/ は触らない）

## 完了条件
全 8 ゲートが exit 0 であること。
```

---

# 優先 3：The Agentic Scientist（`arXiv:2610.18933`）

```
あなたは ResearchOS リポジトリ（/home/user/ResearchOS、ブランチ arena/ac3628ba-researchos）
の文献調査ワーカーです。報告は日本語でお願いします。

## 目的
arXiv:2610.18933 "The Agentic Scientist: Orchestrating Coding Agents for Automated
Scientific (Co-)Discovery" を精読し、**段階別ルーブリック検証**の具體例を抽出してください。

【経路A】原典を添付します。それを読んでください。
【経路B】原典はありません。docs/literature-inventory-2026-10-19.jsonl の
        paper_id=arXiv:2610.18933v1 の各フィールドを根拠にしてください。

## なぜこの論文か（背景）
本リポジトリは草案化→調査→統合→報告を、並列セッションと統合役の裁定で
**すでに非形式に**回しています。したがって「新しい設計」としては小さいです。
価値があるとすれば**段階別ルーブリック**の具體例です。

本リポジトリは現在、長文生成物を CI の 8 ゲートで機械検査しています
（監査 ID 11 / ID 19）。しかし**検査は段階を区別していません**——
草案・調査・統合・報告のどの段階でも同じ検査をかけています。
本論文の「段階別ルーブリック」は、**段階ごとに検査を設計する**際の参考になります。
特に**「事後分析」段階**のルーブリックに注目してください。

## 特に知りたいこと（優先順）
1. 各段階（草案化／アイデア生成／計画／サンドボックス実験／結果統合／
   ベースライン・アブレーション／事後分析／報告）に**それぞれどんな検証基準**を
   課しているか。表にまとめてください。
2. **事後分析段階**の検証内容（本リポジトリに最も不足している部分）。
3. 段階の**遷移条件**——次へ進む基準と、戻る基準。
4. 本リポジトリの 8 ゲートと突き合わせ、**「自前で実験を持たない」本リポジトリに
   転用できる部分**とできない部分を分けてください（本リポジトリは LLM 実験を
   実行できません）。

## 制約（必ず守ること）
- **このサンドボックスからは arxiv.org に到達できません**（許可ホストは github.com 等のみ）。
- 本論文は tests/fixtures/arxiv_metadata_snapshot.json に**存在しません**。
  scripts/check_citations.py は「スナップショットに無い arXiv ID」を MISSING＝失敗として
  CI ゲート5 を赤にします。**原典を確認できない状態で state/sources.jsonl に
  登録してはいけません。**
  - 【経路A】原典を読めた場合のみ、スナップショットに確認済み書誌を追記したうえで登録可。
  - 【経路B】state/ には一切書き込まないこと。
- ID は python3 scripts/new_id.py SRC --count 1 --date 2026102X で採番（連番禁止）。
- 証拠段階 A/B/C を明記。原典未照合の記述は必ず C とする。

## 成果物
【経路A】contributions/2026-10-2X_agentic_scientist_reading.md ＋ SRC 登録 ＋ EVD 3〜5件
【経路B】contributions/2026-10-2X_agentic_scientist_triage.md のみ（state/ は触らない）

## 完了条件
全 8 ゲートが exit 0 であること。
```

---

# 優先 4：SHELDON（`arXiv:2610.18025`）

```
あなたは ResearchOS リポジトリ（/home/user/ResearchOS、ブランチ arena/ac3628ba-researchos）
の文献調査ワーカーです。報告は日本語でお願いします。

## 目的
arXiv:2610.18025 "SHELDON: Reasoning through Dual Search over Hypothesis and
Observation Spaces" を精読し、**仮説空間と観測空間を分離して管理するデータモデル**
を抽出してください。

【経路A】原典を添付します。それを読んでください。
【経路B】原典はありません。docs/literature-inventory-2026-10-19.jsonl の
        paper_id=arXiv:2610.18025v1 の各フィールドを根拠にしてください。

## なぜこの論文か（背景）
本リポジトリの state/hypotheses.jsonl（2件）は**仮説しか持っておらず、
観測（EVD）との対応がありません**。state/evidence.jsonl は 49 件ありますが、
どの EVD がどの HYP を支持／反駁するかの紐付けは VER 経由の間接的なものだけです。

本論文は「仮説が説明できない観測から理解の欠落を検出する」とあります。
**これは本リポジトリが持っていない機能**です——現在は「EVD が増えた」ことしか
分からず、「どの EVD が既存仮説と矛盾するか」は人間が読まないと分かりません。

なお本リポジトリでは ID 17（`rho`/`c` の実測）を**凍結**しています。
理由は「非定量的なテーマでは難問」であって、**仮説管理が不要という意味ではありません**。

## 特に知りたいこと（優先順）
1. 仮説空間と観測空間を**どう別々に表現**するか（スキーマ・ID・関係）。
2. 「仮説が説明できない観測」を**どう検出**するか。決定論的に判定できるか、
   それとも推論が要るか。**本リポジトリの決定論的 CI で実装可能か**が要点です。
3. 検出後に**何を誘発**するか（新しい調査？新しい仮説？）と、その優先付け。
4. 本リポジトリの台帳（EVD 49 / CLM 8 / VER 29 / HYP 2）に適用した場合、
   **スキーマ変更の具體案**をください。後方互換（既存レコードを壊さない）を前提とすること。

## 制約（必ず守ること）
- **このサンドボックスからは arxiv.org に到達できません**（許可ホストは github.com 等のみ）。
- 本論文は tests/fixtures/arxiv_metadata_snapshot.json に**存在しません**。
  scripts/check_citations.py は「スナップショットに無い arXiv ID」を MISSING＝失敗として
  CI ゲート5 を赤にします。**原典を確認できない状態で state/sources.jsonl に
  登録してはいけません。**
  - 【経路A】原典を読めた場合のみ、スナップショットに確認済み書誌を追記したうえで登録可。
  - 【経路B】state/ には一切書き込まないこと。
- ID は python3 scripts/new_id.py SRC --count 1 --date 2026102X で採番（連番禁止）。
- 証拠段階 A/B/C を明記。原典未照合の記述は必ず C とする。

## 成果物
【経路A】contributions/2026-10-2X_sheldon_reading.md ＋ SRC 登録 ＋ EVD 3〜5件
【経路B】contributions/2026-10-2X_sheldon_triage.md のみ（state/ は触らない）

## 完了条件
全 8 ゲートが exit 0 であること。
```

---

# 優先 5：RLTL;DR（`arXiv:2609.37633`）

```
あなたは ResearchOS リポジトリ（/home/user/ResearchOS、ブランチ arena/ac3628ba-researchos）
の文献調査ワーカーです。報告は日本語でお願いします。

## 目的
arXiv:2609.37633 "RLTL;DR: Self-improvement by Internalizing Self-generated Feedback"
を精読し、**Verifier の評価を短い知見に圧縮して再利用する形式**を抽出してください。

【経路A】原典を添付します。それを読んでください。
【経路B】原典はありません。docs/literature-inventory-2026-10-19.jsonl の
        paper_id=arXiv:2609.37633v1 の各フィールドを根拠にしてください。

## なぜこの論文か（背景）
本リポジトリの state/verifications.jsonl（29件）の rationale は**長文で、
書かれた後に再利用されていません**。統合役が次に同じ種の判断をするとき、
過去の VER を読み直す必要があります。

本論文は「失敗後に Verifier が出した評価を、短い insight へ圧縮し、次の rollout へ
渡す」とあります。**この圧縮形式**が本リポジトリの運用に使えそうです。

## 重要な但し書き
本リポジトリは **LLM の学習を行いません**。したがって論文の主眼である
"internalize"（推論時に insight を明示しなくても性能を保つ＝モデル内部化）は
**採用できません**。**必要なのは「形式」だけ**です。
論文を読む際は「内部化」の部分と「圧縮形式」の部分を分けて整理してください。

## 特に知りたいこと（優先順）
1. insight の**具體的な形式**：長さ・構造・必須フィールド。実例を写してください。
2. **圧縮の手続き**：何から何を落とすか。捨てられる情報と捨てられない情報の基準。
3. **再利用の条件**：どんなときに過去の insight を引くか（類似度？タグ？）。
4. 本リポジトリへの適用案：VER レコードに insight フィールドを足すなら、
   どんなスキーマか。**既存 29 件を壊さない後方互換案**をください。
5. **失敗モード**：圧縮で何が失われるか。本リポジトリのように「事実性」が
   重要な用途で、圧縮が危険なケースはあるか。

## 制約（必ず守ること）
- **このサンドボックスからは arxiv.org に到達できません**（許可ホストは github.com 等のみ）。
- 本論文は tests/fixtures/arxiv_metadata_snapshot.json に**存在しません**。
  scripts/check_citations.py は「スナップショットに無い arXiv ID」を MISSING＝失敗として
  CI ゲート5 を赤にします。**原典を確認できない状態で state/sources.jsonl に
  登録してはいけません。**
  - 【経路A】原典を読めた場合のみ、スナップショットに確認済み書誌を追記したうえで登録可。
  - 【経路B】state/ には一切書き込まないこと。
- ID は python3 scripts/new_id.py SRC --count 1 --date 2026102X で採番（連番禁止）。
- 証拠段階 A/B/C を明記。原典未照合の記述は必ず C とする。

## 成果物
【経路A】contributions/2026-10-2X_rltldr_reading.md ＋ SRC 登録 ＋ EVD 3〜5件
【経路B】contributions/2026-10-2X_rltldr_triage.md のみ（state/ は触らない）

## 完了条件
全 8 ゲートが exit 0 であること。
```

---

## 使い方

1. 上から順に、**1 チャットにつき 1 本**貼り付けて開始する。
2. 各プロンプトの `【経路A】` / `【経路B】` は**必ずどちらかを消す**こと
   （両方残すと指示が矛盾する）。
3. **経路 A を採る場合**、原典（PDF または HTML のテキスト）をチャットに添付する。
4. ワーカーが `state/` を触った場合、**統合役が内容を確認してから** `main` へ取り込む。
5. 優先 1（RRSI）の成果は、本リポジトリの**未実装 2 項目**
   （過適合回避・剪定）に直結する。最優先で回すこと。

## 残っている前提リスク

本トリアージは**要約に基づく暫定選別**であり、原典に当たっていない。
インベントリ自身が次を明記している：

> 「RRSI と ResearchOS の間には設計上の高い関連があるが、ResearchOS で
> 実装済み／採用済みと確認できる証拠はない」

すなわち **RRSI を優先 1 としたのは要約の内容であって、設計時に実際に参照されたという
来歴ではない**。この 2 つを混同しないこと。原典を読んだ結果、
期待外れであった場合は**遠慮なく順位を下げてよい**。
