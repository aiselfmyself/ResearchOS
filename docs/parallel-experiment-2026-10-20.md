# 並列稼働実験の設計（E1: ハーネス検証 ＋ E2: 誤り相関の観測）

- 作成日：2026-10-20
- 実行手順：[`docs/parallel-session-playbook-2026-10-20.md`](./parallel-session-playbook-2026-10-20.md)
- 種別：ハーネスの継続的改善（E1）＋ 本研究の未解決事項1位である `rho` / `c` の実測（E2）

---

## 1. 何を確かめたいか

### E1（ハーネス検証）

「複数セッションが並列で別ブランチを走らせ、`main` まで無事に着地するか」。具体的には：

- パス衝突・マージ衝突は起きるか。起きたら**当該セッションが自力で復旧できるか**（統合チャットは他ブランチに push できない）
- マージ後に不整合が残った場合、**統合チャットが事後修復できるか**（PR #19・#20 がこの実例）

### E2（`rho` / `c` の実測）

`rho`＝ワーカー間の誤り相関、`c`＝誤った共有見解への追従率。本研究の統合レポート §7 未解決事項の1位。

**同一タスクを2つの独立セッションに解かせ、出力を突き合わせる**ことで観測する。

#### ⚠️ 交絡について（正直に書く）

A と A' は**同じ論文を読む**。つまり入力が共有されている。これはモデルの `c`（共有見解への追従）チャネルそのものであり、`rho`（ワーカー自体の均質性）と分離できない。

観測されるのは **rho と c の合成効果**である。これを分けて測るには「入力を重ならせない」条件が必要だが、このリポジトリでは全メモが `contributions/` に集約されているため現実的でない。**したがって本実験では合成値を測り、交絡を明示したうえで報告する。**

「分離できていないものを分離できたと言わない」は、このリポジトリの一貫した方針である（[`docs/parallel-work-ownership.md`](./parallel-work-ownership.md) §1）。

#### 検出力について（正直に書く）

セッション数は **n = 1**（A と A' の1組）。**統計的検出力は極めて低く、存在証明の域を出ない。** 有意な相関の推定値は得られない。得られるのは「同じ誤りが実際に起きたか」の観測である。

---

## 2. 構成

| セッション | タスク | 排他的パス |
|---|---|---|
| **A** | Agora（arXiv:2609.18094）の全文読解レポート | `contributions/2026-10-2X_agora_fulltext_reading.{md,json}` |
| **A'** | **同じ論文**を独立に全文読解 | `contributions/2026-10-2X_agora_fulltext_reading_r2.{md,json}` |
| **B** | 2出力の一致率・相関誤りを計算するツール | `scripts/measure_agreement.py`、`tests/test_measure_agreement.py`、`contributions/2026-10-2X_agreement_measurement.md` |

**Agora を選んだ理由**：`tests/fixtures/arxiv_metadata_snapshot.json` に収録済みで、台帳にも `SRC-20261020-f295` として登録済みだが、**本文は未読**と明記されている唯一の文献だから。

**B を分けた理由**：B は `scripts/`・`tests/` を触る唯一のセッションであり、A / A' とはパスが重ならない。同時に、B が作るツールは A / A' の成果を測る道具として今後も再利用できる。

---

## 3. 抽出項目（A / A' 共通・固定）

15項目。機械比較しやすいよう、可能な限り**客観的に判定できる項目**にしてある。

| ID | 項目 | 型 |
|---|---|---|
| A1 | タイトル | 文字列 |
| A2 | 著者数 | 整数 |
| A3 | 先頭著者 | 文字列 |
| A4 | 投稿日 | 日付（YYYY-MM-DD） |
| A5 | ライセンス（無ければ "none"） | 文字列 |
| B1 | ベンチマーク数 | 整数 |
| B2 | ベンチマーク名 | リスト |
| C1 | 主要結果の代表値 1（数値＋出典節） | 文字列 |
| C2 | 主要結果の代表値 2 | 文字列 |
| C3 | 主要結果の代表値 3 | 文字列 |
| D1 | 最強ベースライン名 | 文字列 |
| E1 | 単一実行（n=1）か | true / false / unknown |
| E2 | 実行回数が明記されているか | true / false |
| F1 | 論文自認の限界の数 | 整数 |
| G1 | コード公開の有無 | true / false / unknown |

---

## 4. コピペ用プロンプト

### A（読解・第1）

```text
あなたは ResearchOS リポジトリの調査セッション A です。以下を実行してください。

## 前提（必ず最初に読む）

- リポジトリ：aiselfmyself/ResearchOS
- `docs/parallel-session-playbook-2026-10-20.md` を読み、**パス規律・ブランチ手順・提出形式**に従うこと
- `docs/parallel-experiment-2026-10-20.md` の §3「抽出項目」の表を読むこと

## タスク

arXiv:2609.18094（Agora）の**全文**を読み、読解レポートを書く。
この文献は `tests/fixtures/arxiv_metadata_snapshot.json` に書誌のみ収録済みで、
`state/sources.jsonl` では SRC-20261020-f295 として登録されているが、**本文は未読**である。

- abs ページだけでなく、必ず **HTML版（https://arxiv.org/html/2609.18094v1）または PDF の本文**を読むこと
- 要旨だけで済ませないこと

## 成果物（この2ファイルのみ新規作成）

1. `contributions/2026-10-2X_agora_fulltext_reading.md`
   - 既存の `contributions/2026-10-20_sla_fulltext_reading.md` を**構成の手本**にすること
   - レポートは日本語
   - 「本文で確認できたこと」と「確認できなかったこと」を分けて書くこと
2. `contributions/2026-10-2X_agora_fulltext_reading.json`
   - プレイブック §4 の形式で、§3 の15項目すべてを埋める
   - 本文に書いていない推測には `"location": null` と `"confidence": "low"` を付ける

## やらないこと

- 自分の2ファイル以外を変更しない（`state/`、`README.md`、`tests/`、`scripts/` は触らない）
- 他のセッションのファイルを書き換えない
- **PR は作るが、自分でマージしない**
- 台帳（`state/`）への追記は統合役の担当。必要なら判断だけを自分のメモに書く

## コミット前の必須確認

```bash
git fetch origin <自分のブランチ>
git log --oneline origin/<自分のブランチ>..HEAD
```

出力が空でなければ、プレイブック §2 の `git reset --soft` 手順で付け替えてからコミットする。

## 完了条件

- 上記2ファイルが作成されている
- 全6ゲートが通る（`python3 -m unittest discover -s tests` / `gitswarm/benchmarks/benchmark.py --check` / `gitswarm/readout_sim.py --check` / `scripts/validate_state.py` / `scripts/check_citations.py` / `scripts/check_memo_citations.py`）
- PR を作成し、本文に「やったこと／やっていないこと／検証コマンドの実測値」を書く
```

### A'（読解・第2）

```text
あなたは ResearchOS リポジトリの調査セッション A' です。以下を実行してください。

## 前提（必ず最初に読む）

- リポジトリ：aiselfmyself/ResearchOS
- `docs/parallel-session-playbook-2026-10-20.md` を読み、**パス規律・ブランチ手順・提出形式**に従うこと
- `docs/parallel-experiment-2026-10-20.md` の §1 と §3 を読むこと

## 重要：このタスクの位置づけ

あなたは**セッション A とまったく同じタスク**を、**独立に**解く。

これは意図的な実験である。2つの独立した出力を突き合わせ、
「同じタスクを別セッションが解いたとき、同じ誤りをするか」を測る
（本研究の未解決事項1位：`rho`＝ワーカー間の誤り相関）。

したがって：
- **他のセッションの成果物を読んではならない**（相関が壊れるため）
- `contributions/2026-10-2X_agora_fulltext_reading.md` とその `.json` は**開かない**
- 既存メモ（`2026-10-20_sla_fulltext_reading.md` など）を構成の手本として読むのは可

## タスク

arXiv:2609.18094（Agora）の**全文**を読み、読解レポートを書く。
abs ページだけでなく、必ず **HTML版（https://arxiv.org/html/2609.18094v1）または PDF の本文**を読むこと。

## 成果物（この2ファイルのみ新規作成）

1. `contributions/2026-10-2X_agora_fulltext_reading_r2.md`
2. `contributions/2026-10-2X_agora_fulltext_reading_r2.json`
   - プレイブック §4 の形式で、§3 の15項目すべてを埋める
   - 本文に書いていない推測には `"location": null` と `"confidence": "low"` を付ける

## やらないこと

- 自分の2ファイル以外を変更しない
- **セッション A のファイルを読まない・書き換えない**
- PR は作るが、自分でマージしない

## コミット前の必須確認

```bash
git fetch origin <自分のブランチ>
git log --oneline origin/<自分のブランチ>..HEAD
```

出力が空でなければ、プレイブック §2 の `git reset --soft` 手順で付け替えてからコミットする。

## 完了条件

- 上記2ファイルが作成されている
- 全6ゲートが通る
- PR を作成し、本文に「やったこと／やっていないこと／検証コマンドの実測値」を書く
```

### B（計測ツール）

```text
あなたは ResearchOS リポジトリの計測ツール実装セッション B です。以下を実行してください。

## 前提（必ず最初に読む）

- リポジトリ：aiselfmyself/ResearchOS
- `docs/parallel-session-playbook-2026-10-20.md` を読み、**パス規律・ブランチ手順**に従うこと
- `docs/parallel-experiment-2026-10-20.md` の §1（E1/E2 の目的と**交絡・検出力の但し書き**）と §3（抽出項目）を読むこと
- 関連する既存実装：`gitswarm/readout_sim.py`（同質ワーカーの多数決モデル）

## タスク

2つの独立セッションが**同じタスク**から出した抽出結果を突き合わせ、
一致率と**相関誤り**を計算するツール `scripts/measure_agreement.py` を作る。

### 入力

プレイブック §4 の形式の JSON を2つ（`--a` と `--b`）、任意で正解ファイル（`--truth`）。

### 出力（最低限）

1. **項目ごとの判定**：`agree` / `disagree` / `both-missing`
2. **一致率**：agree / 全項目
3. **Cohen's kappa**：偶然を超えた一致の程度
4. **正解が与えられた場合のみ**：
   - 各ワーカーの誤り率 `p1`, `p2`
   - 実際に両者が同時に誤った割合 `P(both wrong)`
   - 独立なら期待される `p1 * p2`
   - **lift = P(both wrong) / (p1 * p2)** … 1 を超えれば誤りが相関している

   `lift` は `gitswarm/readout_sim.py` の増幅率と同じ発想である。
   「独立なら `p1*p2` のはずが、実際にはそれより高い」＝相関、という読み方。
5. `--json` で機械可読な出力

### CLI

```text
python3 scripts/measure_agreement.py --a <file1.json> --b <file2.json> [--truth <truth.json>] [--json]
```

終了コードは常に 0（これは**ゲートではなく計測器**である。CI にはつながない）。

### 比較の実装方針

- 数値項目は許容誤差（既定 1e-6、 `--tol` で変更可）で比較
- 文字列項目は空白・大文字小文字を正規化して比較
- リスト項目は順序を無視して比較
- `unknown` / `null` は**誤りでも正解でもない**として別扱いにする（ここを雑にすると lift が歪む）

## 成果物（この3ファイルのみ新規作成）

1. `scripts/measure_agreement.py`
2. `tests/test_measure_agreement.py`（回帰テスト。合成データで期待値を固定する）
3. `contributions/2026-10-2X_agreement_measurement.md`
   - 何を測る道具か、**測れないものは何か**を明記する
   - §1 の交絡（`rho` と `c` が分離できないこと）と検出力（n=1）の但し書きを**必ず書く**

## やらないこと

- 自分の3ファイル以外を変更しない。**`tests/test_minimal_core.py` には触らない**（他セッションと衝突する）
- `state/`、`README.md` は触らない（統合役専用）
- PR は作るが、自分でマージしない

## コミット前の必須確認

```bash
git fetch origin <自分のブランチ>
git log --oneline origin/<自分のブランチ>..HEAD
```

出力が空でなければ、プレイブック §2 の `git reset --soft` 手順で付け替えてからコミットする。

## 完了条件

- 上記3ファイルが作成されている
- `python3 -m unittest discover -s tests` が通る（既存テストを壊さないこと）
- 合成データで「完全一致」「完全不一致」「独立な誤り」「相関した誤り」の4パターンが期待通りに出ることをテストで固定
- PR を作成し、本文に「やったこと／やっていないこと／検証コマンドの実測値」を書く
```

---

## 5. 実験後に統合役がやること

1. A / A' の両 PR をマージする（衝突すれば当該セッションに復旧させる）
2. B のツールで A と A' の JSON を突き合わせ、**lift** を算出する
3. 結果を `contributions/` の測定メモとして記録する。**交絡と検出力の但し書きを必ず添える**
4. E1 について、何が起きたか（衝突の有無・復旧の可否・統合に要した PR 本数）を
   `docs/incomplete-work-audit-2026-10-20.md` §13.1 に追記する
5. 2本の読解レポートは**統合するか併存させるかを人間が判断する**（PR #17/#18 と同じ論点）
