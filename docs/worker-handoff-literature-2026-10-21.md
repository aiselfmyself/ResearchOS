# 別ワーカーへの引き継ぎプロンプト（2026-10-21 / 2026-10-21 改訂）

`docs/literature-triage-2026-10-21.md` で優先順 5 件に絞った文献について、
**新しいチャットに貼り付けて開始できる**プロンプトをまとめた。

各プロンプトは**単独で完結**するように書いてある（前提知識を要求しない）。
上から順に優先度が高い。**1 チャット = 1 論文**を想定している。

---

## ⚠️ 初版の誤りを訂正した（2026-10-21）

**初版は「このサンドボックスからは arxiv.org に到達できない」と書いていた。これは誤りだった。**

人間の指摘で再確認した結果：

| 経路 | arxiv.org | 根拠 |
|---|---|---|
| サンドボックスの `curl` / `python3` | ❌ **到達できない** | `curl https://arxiv.org/abs/2609.24972` → `SSL_ERROR_SYSCALL`（実測） |
| **Arena の `fetch_page` / `web_search`** | ✅ **到達できる** | 実際に `https://arxiv.org/abs/2609.24972` と `.../2609.15983` を取得できた（実測） |

さらに **`tests/fixtures/arxiv_metadata_snapshot.json` の `capture_method` には
「arxiv abs pages read via web fetch tool」と書いてあった**——このリポジトリは
**すでに web fetch で arXiv を取得していた**。初版の制約は、システム側の
「outbound 許可ホスト」という記述を**過剰に一般化して**書いたものだった。

**したがって「経路A／経路B」の二分は撤回する。** ワーカーは**自分で原典を取得できる**。

### ただし 1 つだけ残る本当の制約

`scripts/check_citations.py` は、**スナップショットに無い arXiv ID を `MISSING`＝失敗**
として扱う（CI ゲート5）。

```
entry = entries.get(arxiv_id)
if entry is None:
    report.append(f"MISSING {source_id} {arxiv_id} (not in metadata snapshot)")
```

したがって **`state/sources.jsonl` に登録する前に、
`tests/fixtures/arxiv_metadata_snapshot.json` へ確認済み書誌を追記する**必要がある。
これは**原典を読めるかどうかとは無関係**の、CI をネットワーク非依存に保つための要件である。

**優先 1・2 については当方で追記済み**（下記の verified 書誌）。
優先 3〜5 を担当する場合は、自分で abs ページを取得して追記すること。

---

## 共通の前置き（各プロンプトに含めている内容）

- リポジトリ `/home/user/ResearchOS`
- **報告は日本語**
- 証拠段階：**A**＝自前で実行・測定した結果 / **B**＝原典の逐語引用 / **C**＝原典数値からの導出・未照合の記述
- ID は `python3 scripts/new_id.py SRC --count 1 --date 2026102X` で採番（連番禁止）
- `state/` と `README.md` への書き込みは統合役の担当（`docs/parallel-work-ownership.md` §2）
- 変更後は**全 8 ゲート**を走らせる
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

**verified 書誌（2026-10-21 に abs ページで確認済み／スナップショット追記済み）**

- Title: *RRSI: Regularized Recursive Self-Improvement of Agent Harnesses*
- Authors: Peng Xia, Rujun Han, Zifeng Wang, Yanfei Chen, Yufan Zhuang, Yoonho Lee,
  Chengsong Huang, Han Yu, Zhongying CuiZhu, Yifei Ming, Huaxiu Yao, Burak Gokturk,
  Tomas Pfister, Chen-Yu Lee（14名）
- 現在版 **v3**（2026-10-04）。v1 2026-09-21、v2 2026-09-23
  —— **インベントリは `v2` と記録していたので 1 世代古い**
- cs.LG / cs.AI / cs.CL
- **コード: https://github.com/google-research/rrsi** （`github.com` は**サンドボックスからも到達可能**）

```
あなたは ResearchOS リポジトリ（/home/user/ResearchOS）の文献調査ワーカーです。
報告は日本語でお願いします。

## 目的
arXiv:2609.24972 "RRSI: Regularized Recursive Self-Improvement of Agent Harnesses"
を読み、本リポジトリ（arena.ai + GitHub による小規模 GitSwarm 型の研究運用）に
実装できる具體的な設計要素を抽出してください。

## 原典の取得方法（重要）
この環境からのアクセスには 2 種類あります。
- Arena の fetch_page / web_search ツール → **arxiv.org に到達できます**（実測済み）
- サンドボックスの curl / python3 → **到達できません**（SSL エラー）

したがって **fetch_page で取得してください**。
  https://arxiv.org/abs/2609.24972      （書誌・抄録）
  https://arxiv.org/html/2609.24972v3   （本文 HTML）
  https://github.com/google-research/rrsi （コード。github.com は curl でも可）
抄録だけでなく**本文に当たる**こと。特に §手法 の proposer / critic / pruner の
具體的なアルゴリズムと、表の数値を読み取ってください。

## なぜこの論文か（背景）
本リポジトリは「ハーネスが性能差の帰属先である」という論点を繰り返し扱ってきました
（arXiv:2605.23950 の HV/MV=7.80、監査 ID 14、報告 §3.3）。しかし
**「ではハーネスをどう改善するか」の方法論を持っていません**。RRSI はそれに直接答えます。

すでに粗検討（docs/literature-triage-2026-10-21.md）で対応表を作ってあり、
実装済なのは上 3 行だけで、**下 2 行が未実装**でした。

| RRSI の要素 | 本リポジトリ | 状態 |
|---|---|---|
| 差分単位でハーネス変更を評価 | PR ＋ CI 8 ゲート | ✅ |
| 変更の仮説・diff・スコア・採否を記録 | state/verifications.jsonl / hypotheses.jsonl | ✅ |
| 失敗を次ラウンドへ再投入 | 監査の「未対応」リスト | ✅ |
| **固定タスクへの過適合を避ける（hold-out/OOD 分離）** | scripts/holdout_eval.py | **当方で暫定実装済** |
| **低寄与コンポーネントの剪定** | scripts/prune_candidates.py | **当方で暫定実装済** |

**重要**：下 2 行は**抄録の要約だけを根拠に当方が設計した暫定実装**です。
あなたの仕事は「実装を擁護する」ことではなく、
**原典に照らして妥当かを判定し、ずれていれば設計を直すこと**です。遠慮なく指摘してください。

## 特に知りたいこと（優先順）
1. **proposer の temporally annealed budget**：編集数の上限は**具体的にいくつか**。
   時間とともにどう減衰するか。その根拠と、上限を破った場合の扱い。
2. **critic の判定基準**：「benchmark-specific な提案」を**どう見分けるか**。
   當方は hold-out 分割で代用しました（scripts/holdout_eval.py）が、
   原典の critic はそれとは別物の可能性があります。**差分を明示してください。**
3. **pruner の判定基準**：「too small / too expensive / no longer useful」の
   **それぞれの閾値と測り方**。當方は has_tests / referenced_in_docs / imported_by
   という代理指標を使いましたが、これは原典の基準ではありません。**原典の基準を寫してください。**
4. **evolution history による未探索軌跡の促進**：具體的に何を記録し、どう探索を偏らせるか。
5. **再現に必要な最小構成**：本リポジトリ規模（並列セッション 2〜4、EVD 49、CI 8 ゲート、
   決定論的検査のみ、**モデル学習なし**）で**現実に実装できる部分**と
   **学習を前提とするため不可な部分**を分けてください。
   なお RRSI は「30% fewer policy tokens」を成果に挙げています——
   **コスト削減が目的の一部**である点に注意してください。

## 制約（必ず守ること）
- **原典を読まずに結論を出さない。** 抄録だけで判断しないこと。
- `state/sources.jsonl` に登録する前に
  `tests/fixtures/arxiv_metadata_snapshot.json` へ確認済み書誌を追記する
  （**優先1は當方が追記済み**。内容が食い違っていたら**訂正して報告**すること）。
  追記しないと scripts/check_citations.py が MISSING として CI ゲート5 を赤にします。
- ID は python3 scripts/new_id.py SRC --count 1 --date 2026102X で採番（連番禁止）。
- 証拠段階 A/B/C を必ず明記。引用は逐語で、要約と混ぜない。
- 人間判断を要する削除・撤回は**勝手に行わず**、報告して指示を仰ぐ。

## 成果物
- contributions/2026-10-2X_rrsi_reading.md
- state/sources.jsonl への SRC 登録（スナップショットは追記済み）
- 主要箇所の EVD（5〜8件）＋ VER 1件
- **當方の暫定実装（holdout_eval.py / prune_candidates.py）への判定**：
  妥当／要修正／撤回 のいずれかを、根拠つきで明示する

## 完了条件
全 8 ゲートが exit 0 であること。
```

---

# 優先 2：Stellar Colosseum（`arXiv:2609.15983`）

**verified 書誌（2026-10-21 に abs ページで確認済み／スナップショット追記済み）**

- Title: *Stellar Colosseum: A Many-Agent Harness for Long-Horizon Research in
  Mathematics and Theoretical Computer Science*
- Authors: Honghao Lin, David P. Woodruff, Yuan Deng, Jieming Mao, Song Zuo,
  Vahab Mirrokni（6名）
- 現在版 **v2**（2026-09-15）。v1 2026-09-14
- cs.AI / cs.CL / cs.LG（2026-10-21 訂正：初版は「cs.AI / cs.CL / cs.CL」と cs.CL を重記していた。abs ページ https://arxiv.org/abs/2609.15983 で第3カテゴリが cs.LG（Machine Learning）と確認できたため、人間の承認を得て訂正。確認経緯は contributions/2026-10-21_stellar_colosseum_reading.md §2.2・§8.4）
- 抄録で判明済みの點：readiness gate（経路が分解可能か判定）／
  section-level subproblems／verifier の指摘を**影響箇所へ戻す**／
  **targeted falsification**／**overlapping random-sample tree aggregation**
  ／Google Antigravity の Teamwork framework に "Long Proof" pattern として統合済み

```
あなたは ResearchOS リポジトリ（/home/user/ResearchOS）の文献調査ワーカーです。
報告は日本語でお願いします。

## 目的
arXiv:2609.15983 "Stellar Colosseum: A Many-Agent Harness for Long-Horizon Research
in Mathematics and Theoretical Computer Science" を読み、
**「反証を影響箇所へ戻す修復ループ」**の具體的なデータ構造を抽出してください。

## 原典の取得方法（重要）
- Arena の fetch_page / web_search → **arxiv.org に到達できます**（実測済み）
- サンドボックスの curl / python3 → 到達できません

fetch_page で取得してください。
  https://arxiv.org/abs/2609.15983
  https://arxiv.org/html/2609.15983v2
抄録だけでなく**本文**に当たり、特に readiness gate の判定式と、
verifier の指摘を影響箇所へ戻すときの**データ構造（フィールド名）**を寫してください。

## なぜこの論文か（背景）
本リポジトリの state/claims.jsonl は counterclaim_ids（反証）を持ちます
（監査 ID 5 で空だったのを 4 件紐付け済み）。しかし
**反証を「記録」するだけで、その反証が主張のどの部分を崩すか＝影響箇所への
返し方を持っていません**。state/verifications.jsonl の VER は target_id を
1 つしか持たず、「どこへ返すか」が表現できない。

本論文の抄録には「節単位の依存関係を持つサブ問題を作り、Verifier の指摘を
影響箇所へ戻す」とあります。**この「戻し方」のデータモデル**が知りたい。

## 特に知りたいこと（優先順）
1. **readiness gate の判定基準**：「分解可能な成熟度に達したか」を**何で**判定するか。
   閾値・シグナル・判定失敗時の扱い。**數式または擬似コードがあればそのまま寫す。**
2. **反証のルーティング**：影響箇所をどう表現するか（グラフ？依存リスト？subproblem ID？）。
   **具體的なフィールド名やデータ構造**を寫す。
3. **overlapping random-sample tree aggregation**：候補と批判をどう統合するか。
   多数決か、スコアか、構造的差分か。本リポジトリの gitswarm/readout_sim.py
   （同質ワーカーの多数決＝共通モード障害の決定論的測定）との違いも論じる。
4. **本リポジトリ規模で実装できるか**：タスクは数学/TCS の証明構築であり、
   本リポジトリは「非定量的な研究プロセスの研究」です。
   **そのまま転用できるか、抽象だけ借用すべきか**を明示する。

## 制約（必ず守ること）
- **原典を読まずに結論を出さない。**
- `state/sources.jsonl` 登録前に `tests/fixtures/arxiv_metadata_snapshot.json` へ
  確認済み書誌を追記（**優先2も當方が追記済み**。食い違いがあれば訂正して報告）。
- ID は python3 scripts/new_id.py SRC --count 1 --date 2026102X で採番。
- 証拠段階 A/B/C を明記。引用は逐語。
- 人間判断を要する削除・撤回は報告して指示を仰ぐ。

## 成果物
contributions/2026-10-2X_stellar_colosseum_reading.md ＋ SRC 登録 ＋ EVD 4〜6件

## 完了条件
全 8 ゲートが exit 0 であること。
```

---

# 優先 3：The Agentic Scientist（`arXiv:2610.18933`）

**スナップショット未追記**——自分で abs ページを取得して追記すること。

```
あなたは ResearchOS リポジトリ（/home/user/ResearchOS）の文献調査ワーカーです。
報告は日本語でお願いします。

## 目的
arXiv:2610.18933 "The Agentic Scientist: Orchestrating Coding Agents for Automated
Scientific (Co-)Discovery" を読み、**段階別ルーブリック検証**の具體例を抽出してください。

## 原典の取得方法（重要）
- Arena の fetch_page / web_search → **arxiv.org に到達できます**（実測済み）
- サンドボックスの curl / python3 → 到達できません

fetch_page で取得してください。
  https://arxiv.org/abs/2610.18933
  https://arxiv.org/html/2610.18933v1
抄録だけでなく**本文**に当たってください。

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
   課しているか。表にまとめる。
2. **事後分析段階**の検証内容（本リポジトリに最も不足している部分）。
3. 段階の**遷移条件**——次へ進む基準と、戻る基準。
4. 本リポジトリの 8 ゲートと突き合わせ、**「自前で実験を持たない」本リポジトリに
   転用できる部分**とできない部分を分ける（本リポジトリは LLM 実験を実行できません）。

## 制約（必ず守ること）
- **原典を読まずに結論を出さない。**
- **本論文は tests/fixtures/arxiv_metadata_snapshot.json に未登録です。**
  自分で abs ページを取得し、確認できた書誌
  （arxiv_id / source_url / title / authors / published）を**追記してから**
  state/sources.jsonl に登録すること。追記しないと
  scripts/check_citations.py が MISSING として CI ゲート5 を赤にします。
- ID は python3 scripts/new_id.py SRC --count 1 --date 2026102X で採番。
- 証拠段階 A/B/C を明記。引用は逐語。

## 成果物
contributions/2026-10-2X_agentic_scientist_reading.md
＋ スナップショット追記 ＋ SRC 登録 ＋ EVD 3〜5件

## 完了条件
全 8 ゲートが exit 0 であること。
```

---

# 優先 4：SHELDON（`arXiv:2610.18025`）

**スナップショット未追記**——自分で abs ページを取得して追記すること。

```
あなたは ResearchOS リポジトリ（/home/user/ResearchOS）の文献調査ワーカーです。
報告は日本語でお願いします。

## 目的
arXiv:2610.18025 "SHELDON: Reasoning through Dual Search over Hypothesis and
Observation Spaces" を読み、**仮説空間と観測空間を分離して管理するデータモデル**
を抽出してください。

## 原典の取得方法（重要）
- Arena の fetch_page / web_search → **arxiv.org に到達できます**（実測済み）
- サンドボックスの curl / python3 → 到達できません

fetch_page で取得してください。
  https://arxiv.org/abs/2610.18025
  https://arxiv.org/html/2610.18025v1
抄録だけでなく**本文**に当たること。

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
4. 本リポジトリの台帳（EVD 49 / CLM 8 / VER 29 / HYP 2）に適用した場合の
   **スキーマ変更の具體案**。後方互換（既存レコードを壊さない）を前提とする。

## 制約（必ず守ること）
- **原典を読まずに結論を出さない。**
- **本論文は tests/fixtures/arxiv_metadata_snapshot.json に未登録です。**
  自分で abs ページを取得し、確認できた書誌を**追記してから** sources.jsonl に登録する。
- ID は python3 scripts/new_id.py SRC --count 1 --date 2026102X で採番。
- 証拠段階 A/B/C を明記。引用は逐語。

## 成果物
contributions/2026-10-2X_sheldon_reading.md ＋ スナップショット追記 ＋ SRC 登録 ＋ EVD 3〜5件

## 完了条件
全 8 ゲートが exit 0 であること。
```

---

# 優先 5：RLTL;DR（`arXiv:2609.37633`）

**スナップショット未追記**——自分で abs ページを取得して追記すること。

```
あなたは ResearchOS リポジトリ（/home/user/ResearchOS）の文献調査ワーカーです。
報告は日本語でお願いします。

## 目的
arXiv:2609.37633 "RLTL;DR: Self-improvement by Internalizing Self-generated Feedback"
を読み、**Verifier の評価を短い知見に圧縮して再利用する形式**を抽出してください。

## 原典の取得方法（重要）
- Arena の fetch_page / web_search → **arxiv.org に到達できます**（実測済み）
- サンドボックスの curl / python3 → 到達できません

fetch_page で取得してください。
  https://arxiv.org/abs/2609.37633
  https://arxiv.org/html/2609.37633v1
抄録だけでなく**本文**に当たること。

## なぜこの論文か（背景）
本リポジトリの state/verifications.jsonl（29件）の rationale は**長文で、
書かれた後に再利用されていません**。統合役が次に同じ種の判断をするとき、
過去の VER を読み直す必要があります。

## 重要な但し書き
本リポジトリは **LLM の学習を行いません**。したがって論文の主眼である
"internalize"（推論時に insight を明示しなくても性能を保つ＝モデル内部化）は
**採用できません**。**必要なのは「形式」だけ**です。
「内部化」の部分と「圧縮形式」の部分を分けて整理してください。

## 特に知りたいこと（優先順）
1. insight の**具體的な形式**：長さ・構造・必須フィールド。実例を寫す。
2. **圧縮の手続き**：何から何を落とすか。捨ててよい情報と捨ててはいけない情報の基準。
3. **再利用の条件**：どんなときに過去の insight を引くか（類似度？タグ？）。
4. 本リポジトリへの適用案：VER レコードに insight フィールドを足すならどんなスキーマか。
   **既存 29 件を壊さない後方互換案**を出す。
5. **失敗モード**：圧縮で何が失われるか。本リポジトリのように「事実性」が
   重要な用途で、圧縮が危険なケースはあるか。

## 制約（必ず守ること）
- **原典を読まずに結論を出さない。**
- **本論文は tests/fixtures/arxiv_metadata_snapshot.json に未登録です。**
  自分で abs ページを取得し、確認できた書誌を**追記してから** sources.jsonl に登録する。
- ID は python3 scripts/new_id.py SRC --count 1 --date 2026102X で採番。
- 証拠段階 A/B/C を明記。引用は逐語。

## 成果物
contributions/2026-10-2X_rltldr_reading.md ＋ スナップショット追記 ＋ SRC 登録 ＋ EVD 3〜5件

## 完了条件
全 8 ゲートが exit 0 であること。
```

---

## 使い方

1. 上から順に、**1 チャットにつき 1 本**貼り付けて開始する。
2. ワーカーは**自分で原典を取得できる**（Arena の `fetch_page`）。添付は不要。
3. **優先 1・2 は書誌を當方がスナップショットに追記済み**。
   優先 3〜5 は**ワーカー自身が追記してから** `sources.jsonl` に登録する。
4. ワーカーが `state/` を触った場合、**統合役が内容を確認してから** `main` へ取り込む。
5. 優先 1（RRSI）の最重要の成果は、**當方の暫定実装
   （`scripts/holdout_eval.py` / `scripts/prune_candidates.py`）への判定**である。
   これらは抄録要約だけを根拠に設計したもので、**原典の基準とは異なる可能性が高い**。

## 残っている前提リスク

本トリアージの**優先順位**はインベントリの要約に基づく暫定選別である。
インベントリ自身が次を明記している：

> 「RRSI と ResearchOS の間には設計上の高い関連があるが、ResearchOS で
> 実装済み／採用済みと確認できる証拠はない」

すなわち **RRSI を優先 1 としたのは要約の内容であって、設計時に実際に参照されたという
来歴ではない**。原典を読んだ結果、期待外れであれば**遠慮なく順位を下げてよい**。

また、**インベントリの版情報が 1 世代古い**（RRSI を `v2` と記録、実際の現在版は `v3`）。
インベントリの他の書誌情報も古い可能性があるため、**数値や版を引用する前に必ず原典で確認する**こと。
