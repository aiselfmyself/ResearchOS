# 現況記録の監査（2026-10-21 / ワーカーA）

- 作成日：2026-10-21
- 対象：`main` HEAD = `6ea24b3`（マージコミット "Merge pull request #45"）。作業ブランチ `arena/cd154ec2-researchos`
- 目的：前回監査（`docs/incomplete-work-audit-2026-10-20.md`）および周辺文書の**状態記述が現在と食い違っていないか**を、リポジトリの実測と**読み取り専用の GitHub 確認**で洗い出し、統合役が安全に適用できる訂正案を出す
- **本稿は報告のみ。コード・台帳（`state/`）・既存文書・CI 定義・GitHub の Issue/PR/ブランチは一切変更していない。**
- 所有者：`docs/parallel-work-ownership.md` §2 に従い `README.md` / `state/` / `docs/minimal-core-and-ci.md` は**統合役のみ**が編集する。本稿は §3 の**文案**を提供するにとどめる

---

## 0. 結論（先に3行）

1. **台帳・テスト・CI の実測値は開始時点の既知値と完全に一致し、8 ゲートすべて緑**だった。食い違いは**すべて「文書が書かれた時点のスナップショットを、現在形の記述として残している」箇所**に集中している。
2. **最も重大なのは GitHub Issue の状態**——監査 ID 16/20 は「承認済み・実行待ち」と記録されているが、**#1/#3/#4/#5 は 2026-10-21T04:13Z にすべて CLOSED、OPEN 0 件**。完了済みである。
3. **検査8（`check_doc_numbers.py`）は `README.md` の現況記述をほぼ丸ごと見落としている。** 理由は除外規則「`>` で始まる行は叙述」で、README の現況ブロックが**全行ブロッククォート**で書かれているため。引用マークを外したコピーで走査したところ**7 件の陳腐化**を検出した（§4.1 / D-01）。

---

## 1. 現在確認した事実（根拠パス・行・コマンド）

### 1.1 実測値（全ゲート実行）

| # | コマンド | 結果 |
|---|---|---|
| 1 | `python3 -m unittest discover -s tests` | `Ran 242 tests` / `OK` |
| 2 | `python3 gitswarm/benchmarks/benchmark.py --check` | `PASS: benchmark artifact matches a fresh execution` |
| 3 | `python3 gitswarm/readout_sim.py --check` | `PASS: readout-sim artifact matches a fresh execution` |
| 4 | `python3 scripts/validate_state.py` | `PASS: research ledgers valid (sources=13, evidence=60, claims=9, verifications=31, hypotheses=2)` |
| 5 | `python3 scripts/check_citations.py` | `12 arXiv source(s) checked, 1 skipped, 0 failure(s)` |
| 6 | `python3 scripts/check_memo_citations.py` | `19 memo(s) scanned, 49 arXiv citation(s) checked, 2 skipped, 0 failure(s)` |
| 7 | `python3 scripts/check_memo_ledger_refs.py` | `0 dangling reference(s), 5 archived ID reference(s)` |
| 8 | `python3 scripts/check_doc_numbers.py` | `actual: tests=242 gates=8 sources=13 evidence=60 claims=9 verifications=31 hypotheses=2` / `0 stale number(s)` |

**8/8 緑。開始時点の既知値（sources=13 / evidence=60 / claims=9 / verifications=31 / hypotheses=2、tests=242、CI gates=8）はすべて実測と一致**した。したがって既知値の訂正は不要。

- テスト内訳（12 ファイル）は `README.md` §構成（L68–80）の記載と**1 件も違わない**：
  34 / 17 / 33 / 25 / 16 / 20 / 12 / 13 / 14 / 21 / 18 / 19 ＝ **242**
- CI ゲート数は `.github/workflows/core-check.yml` の `run:` を持つステップ数 ＝ **8**（`checkout` / `setup-python` は `uses:` のため算入されない）

### 1.2 台帳から機械的に求めた派生的な事実

| 項目 | 実測 | 根拠 |
|---|---|---|
| EVD を持たない SRC | **0 件**（13 ソースすべて ≥1） | `state/evidence.jsonl` の `source_id` 集計 |
| いずれの HYP にも紐づかない EVD | **54 / 60 ＝ 90.0%** | `hypotheses.jsonl` の `evidence_ids` 和集合との差 |
| CLM にも HYP にも紐づかない EVD | 42 / 60 | 同上 ＋ `claims.jsonl` の `evidence_ids` |
| `counterclaim_ids` が空の CLM | **6 / 9**（うち実質的な未設定は `CLM-006` と `CLM-20261021-7b3e` の 2 件。`CLM-20261021-7b3e` はフィールド自体が `None`） | `state/claims.jsonl` 全件 |
| `target_id: SRC-004` の VER | **2 件** | `state/verifications.jsonl` |
| VER の内訳 | 種別 `source_check` 14 / `logical_consistency` 9 / `deterministic` 6 / `falsifier_critic` 2（計 31）。結果 `pass` 16 / `warn` 10 / `fail` 5 | 同上 |

### 1.3 GitHub（**読み取り専用**で確認）

| コマンド | 結果 |
|---|---|
| `gh issue list --state all` | **4 件すべて CLOSED**。OPEN = **0 件** |
| `gh issue view {1,3,4,5} --json closedAt` | `2026-10-21T04:13:31Z` / `04:13:32Z` / `04:13:33Z` / `04:13:33Z`（すべて `closed=true`） |
| `gh pr list --state open` | **0 件**（最新マージは PR #45、2026-10-21T06:22Z） |
| `gh api repos/aiselfmyself/ResearchOS/branches` | **10 本**（`main` ＋ `arena/*` 9 本） |
| `gh api .../compare/main...<branch>` | `ahead=0` が **6 本**、 **`ahead=1` が 3 本** |
| `gh run list --branch main --limit 10` | 直近 10 本すべて `completed / success` |

**未マージ（`ahead=1`）の 3 ブランチ**——ここが本監査で最も見落とされやすい論点である。

| ブランチ | HEAD 日時 | 変更内容 |
|---|---|---|
| `arena/1e74f6a0-researchos` | 06:36Z | `docs/` の `worker-assignment-prompts-2026-10-21.md` 新規（+209） |
| `arena/85f0cc80-researchos` | 05:35Z | **The Agentic Scientist 読解**（`contributions/` の `2026-10-21_agentic_scientist_reading.md` +307、SRC +1（末尾 4 桁 `7419`）、EVD +5、fixture に `2610.18933` 追記） |
| `arena/2411d5fb-researchos` | 05:43Z | **RRSI v3 読解**（`contributions/` の `2026-10-21_rrsi_reading.md` +224、SRC +1（末尾 4 桁 `a3a2`）、EVD +8、VER +1（末尾 4 桁 `508e`）、`docs/literature-triage-2026-10-21.md` §7 追加、`scripts/holdout_eval.py` / `prune_candidates.py` / 両テスト修正） |

残る 6 本（`ac3628ba` / `b7545cd1` / `bbc9c7b9` / `be8b5d01` / `7605f122` / `23370dd5`）は**いずれも `ahead=0`**＝マージ済み PR（#42/#39/#44/#45/#40・#41/#43）の作業ブランチが残置されたもので、内容は `main` に包含されている。

> **〔表記上の注意〕** 未マージブランチ上のレコード ID とファイルパスは、本稿では**末尾 4 桁のみ／ディレクトリ接頭辞なし**で記す。
> そのまま書くと**検査7（`scripts/check_memo_ledger_refs.py`）が `main` に存在しない参照として dangling を出し、CI を赤にするため**である（実際に初稿で 7 件検出された）。
> これは検査7の欠陥ではなく**設計どおりの挙動**だが、**「未マージの作業を `main` の文書から参照する」こと自体に機械的な抵抗がある**ことを意味する。
> 統合役がこれらのブランチをマージした後は、本稿の表記を実 ID に戻してよい（その時点で参照は解決する）。

### 1.4 検査8 の除外規則が README に効いていないことの実証

`scripts/check_doc_numbers.py` L188–190：

```python
if SKIP_MARKER in line:            # "drift-ok"
    continue
if line.lstrip().startswith(">"):  # narrative / historical snapshot
    continue
```

`README.md` の現況ブロック（L5–L36）は**全行 `>` で始まる**ため、L14・L30 の台帳件数は**検査対象から丸ごと外れている**。

これを実証するため、**リポジトリのファイルは一切触れず**、`>` を剥がしたコピーを `/tmp` に作って同じ検査器を走らせた（実測値の算出元は `ROOT` のまま変わらない）：

```sh
python3 scripts/check_doc_numbers.py --file /tmp/driftcheck/README_unquoted.md
```

```
actual: tests=242 gates=8 sources=13 evidence=60 claims=9 verifications=31 hypotheses=2
  STALE README_unquoted.md:14 [ledger:sources]      found 11, expected 13
  STALE README_unquoted.md:14 [ledger:evidence]     found 47, expected 60
  STALE README_unquoted.md:14 [ledger:claims]       found  8, expected  9
  STALE README_unquoted.md:14 [ledger:verifications] found 27, expected 31
  STALE README_unquoted.md:30 [ledger:sources]      found 12, expected 13
  STALE README_unquoted.md:30 [ledger:evidence]     found 54, expected 60
  STALE README_unquoted.md:30 [ledger:verifications] found 30, expected 31
summary: 1 doc(s) scanned, 7 stale number(s)   # exit=1
```

**7 件中 4 件（L14）は歴史スナップショットとして正当**、3 件（L30）は**最新の台帳件数として現在と食い違う**。いずれも本番のゲート8では検出されない。

---

## 2. 食い違い一覧（現記述 ／ 確認した現状 ／ 重大度）

重大度：**高**＝現況表明として誤読される／または完了済みなのに未了と読める ／ **中**＝部分・周辺の不整合 ／ **低**＝歴史スナップショットで許容だが所在明示が望ましい

| ID | 箇所 | 現記述 | 確認した現状 | 重大度 |
|---|---|---|---|---|
| **D-01** | `README.md:30` | 「**台帳は sources=12 / evidence=54 / claims=9 / verifications=30 / hypotheses=2。**」 | **sources=13 / evidence=60 / claims=9 / verifications=31 / hypotheses=2**（Stellar Colosseum 読解 PR #45 による 書誌1・EVD6・VER1 の追加後） | **高** |
| **D-02** | `README.md:16` | 「`arena/*` のリモートブランチ **36 本すべてを削除**し、**リモートのブランチは `main` のみ**になった」 | **リモートは 10 本**（`main` ＋ `arena/*` 9 本）。6 本は `ahead=0` の残置、3 本は `ahead=1` の実作業 | **高** |
| **D-03** | `docs/incomplete-work-audit-2026-10-20.md:1008, 1040, 1048, 1059, 1393` | ID 16 は「**未対応・人間判断待ち**」/「**承認済み・実行待ち**（トークン権限不足）」、ID 20 も同旨 | **Issue #1/#3/#4/#5 はすべて CLOSED**（2026-10-21T04:13:31–33Z）、**OPEN 0 件**。**ID 16・ID 20 は完了** | **高** |
| **D-04** | `README.md:16` | 「これで `docs/incomplete-work-audit-2026-10-20.md` の**未対応項目はゼロ**になった」 | **ID 18 は未解決のまま**（監査 §14.9 L1157 / §14.4 / L1393 が明記）。**記述時点でも ID 16 が未対応だったため、書かれた時点ですでに不正確** | **高** |
| **D-05** | `docs/literature-triage-2026-10-21.md:104–105` | 「固定タスクへの過適合を避ける | **未実装**」「低寄与コンポーネントの剪定 | **未実装**」 | **両方実装済**（`scripts/holdout_eval.py` / `scripts/prune_candidates.py`、PR #42）。※ **未マージの `arena/2411d5fb-researchos` がこの 2 行の書き換えを既に含む**（§3.5 参照） | **中**（重複編集リスクあり） |
| **D-06** | `docs/literature-triage-2026-10-21.md:102, 143` | 「`state/verifications.jsonl`（**29件**）」「メモ17件・**EVD 49件**」 | verifications **31** / evidence **60**。メモは **19 件** | 中 |
| **D-07** | `docs/literature-triage-2026-10-21.md:28, 257` | 「**本文は未読**」/「優先 1・2 は abs ページで書誌・抄録を確認済み（**本文は未読**）」 | **RRSI 本文（HTML v3 全15チャンク）は読了済**（`arena/2411d5fb-researchos` の `contributions/` の `2026-10-21_rrsi_reading.md`）。`main` には**未マージ** | 中 |
| **D-08** | `docs/worker-handoff-literature-2026-10-21.md:299–301, 323, 338, 343` | 優先4 SHELDON：「**スナップショット未追記**」「`state/evidence.jsonl` は **49 件**」「台帳（EVD 49 / CLM 8 / VER 29 / HYP 2）」「fixture に**未登録**」 | **完了・登録済**（PR #44 / `SRC-20261021-2384` / `contributions/2026-10-21_sheldon_reading.md` / fixture に `2610.18025` 追記済＝snapshot 13 件）。実測は **EVD 60 / CLM 9 / VER 31 / HYP 2** | **中** |
| **D-09** | `docs/worker-handoff-literature-2026-10-21.md:165`（優先2 Stellar Colosseum） | 未了として扱われている | **完了・登録済**（PR #45 / `SRC-20261021-2b88` / `contributions/2026-10-21_stellar_colosseum_reading.md`）。引継ぎ資料のカテゴリ誤記（cs.CL→cs.LG）も同 PR で訂正済 | 中 |
| **D-10** | `README.md:119` / `docs/minimal-core-and-ci.md:44` | 「凍結中である（**記録は `arena/*` ブランチに残る**）」「凍結（`arena/*` ブランチに記録として残る）」 | **凍結記録を含む旧 `arena/*` は ID 11 で全削除済**（監査 §13.8(1)）。現存する 9 本の `arena/*` は**別目的の作業ブランチで、凍結記録ではない**。参照先が死んでいる | **中** |
| **D-11** | `README.md:21–22` / `docs/minimal-core-and-ci.md:66` | 「RRSI の 2 項目を**実装**」/「いずれも **RRSI の設計要素の実装である**」 | RRSI v3 本文照合の結果、両者は RRSI の **critic / selector / pruner とは別物**と判定されている（未マージ `contributions/` の `2026-10-21_rrsi_reading.md` §1-6「いずれも**要修正**（撤回・削除ではない）」）。マージ後は過大表明になる | **中** |
| **D-12** | `docs/incomplete-work-audit-2026-10-20.md:1010, 1088–1101` | 「対応済み 14件 / 撤回 1件 / **未対応 1件**（ID 16）」「残る論点は新 ID 17〜20 の 4 件」 | **対応済み 15 / 撤回 1 / 未対応 1（ID 18）**。ID 16・19・20 は完了、ID 17 は凍結 | 中 |
| **D-13** | `README.md:30` | 「**54 件の EVD のうち 48 件（88.9%）**がいずれの HYP とも紐づいていない」 | **54 / 60 ＝ 90.0%**（HYP 未紐付けは 6 件のまま、EVD だけ増えた） | 低 |
| **D-14** | `README.md:9` | 「**11 ソースすべて**が 1 件以上の EVD を持つ」 | **13 ソースすべて**が ≥1 件（SRC-20261021-2384 / -2b88 が追加） | 低 |
| **D-15** | `docs/literature-triage-2026-10-21.md:187` | 優先1 RRSI「**本リポジトリの未実装 2 項目に直結**」 | 2 項目は暫定実装済（D-05）。直結する論点は「原典の基準とどう違うか」に移っている | 低 |
| **D-16** | `state/claims.jsonl`（台帳） | 監査 ID 5 は「✅ 完了（反証4件を紐付け）」 | **`CLM-006` と `CLM-20261021-7b3e` は `counterclaim_ids` が空／`None`**（後者はフィールド欠落）。`schemas/claim.json` は `counterclaim_ids` を required にしておらず CI は緑。**ID 5 と同型の未達が再発生**している | 中 |
| **D-17** | `docs/worker-handoff-literature-2026-10-21.md:240, 281`（優先3） | Agentic Scientist は「**スナップショット未追記**」 | `main` の fixture に `2610.18933` は**依然として未登録**（実測 `grep -c` = 0）。ただし **未マージの `arena/85f0cc80-researchos` が追記済**。優先5（RLTL;DR）は未着手 | 低 |

**一致しており訂正不要と確認したもの**（監査対象の過半）：

- `README.md` §構成のテスト一覧（L68–80）と「合計 242件」——**実測と完全一致**
- `README.md` L84「全8ゲート」、L91「テスト（約5秒・242件）」——**一致**
- `docs/minimal-core-and-ci.md` L52「**8検査**」、L54「**242テスト**」、§4 DoD 第1項「全ゲート——2026-10-21 時点で **8 つ**」——**一致**（ID 14 の是正が効いている）
- `docs/minimal-core-and-ci.md` §2.3 / §2.4（holdout_eval / prune_candidates の記述）——**実装と一致**
- `README.md` L125「実 LLM ワーカー群の `rho` と `c` は未測定」——**現況と一致**（ID 17 凍結中）
- 監査 §14.9「ID 18 はこのインベントリからは解決しない」——**現況と一致**（未解決のまま正当）

---

## 3. 統合役向けの具体的な訂正文案

**方針（全提案に共通）**：履歴として正しい古いスナップショットは**消さない・書き換えない**。すべて**日付付きの追記**で現在状態を明示し、必要な場合のみ「現在の状態」を述める表のセルを更新する（監査 §14 が「§14.1 の表を正本とする」と定めているため、表セルだけは更新を許容する）。

### 3.1 `README.md:30` の直後——追記（**L30 自体は変更しない**）〔D-01 / D-13 / D-14〕

```markdown
> **〔2026-10-21 追記・現況監査〕** 上 2 段落の台帳件数は**いずれもその時点のスナップショット**であり、
> 現在値ではない。**現在の実測は sources=13 / evidence=60 / claims=9 / verifications=31 /
> hypotheses=2**（`python3 scripts/validate_state.py`、HEAD `6ea24b3`）。本段落以降の差分は
> Stellar Colosseum 読解（PR #45）による 書誌1件・EVD 6件・VER 1件 の追加である。
> **EVD と HYP の未紐付けは 54/60（90.0%）に増えた**（本段落の 48/54 は SHELDON 読解時点の値）。
> EVD を持つソースは **13 ソースすべて**。台帳件数の正本は台帳であり、本文中の件数は
> 「その時点の記録」として残す。
```

> **注（統合役向け）**：この段落は `>` で始まるため `check_doc_numbers.py` の検査対象外になる（§1.4）。現況を述べる数値を `>` の外に出す場合は **`drift-ok` を付ける**か、**実測値を使う**こと。

### 3.2 `README.md:16` の直後——追記（**L16 自体は変更しない**）〔D-02 / D-04〕

```markdown
> **〔2026-10-21 追記・現況監査〕** 上記 2 文は**実行時点（PR #35 マージ直後）の記録**である。
> - **リモートブランチは現在 10 本**（`main` ＋ `arena/*` 9本）。内訳は マージ済み PR の
>   作業ブランチ 6 本（`ahead=0`、内容は `main` に包含）と、未マージ 3 本
>   （`ahead=1`: `arena/1e74f6a0` / `arena/85f0cc80` / `arena/2411d5fb`）。
>   **ID 11 の全削除は事実だが、その後ふたたび `arena/*` が積み上がっている。**
>   削除は人間の承認を要する破壊的操作（`docs/autonomous-merge-policy-2026-10-21.md`）であり、
>   本稿は現況の記録にとどめる。
> - **「未対応項目はゼロ」は当時の記述としても正確ではない。** 記述時点で ID 16 は未対応であり、
>   **監査 ID 18（閾値 R ~ 1 の検証に必要な「同一タスク領域内でモデル格差を変えた第3の論文」の
>   収集）は現在も未解決**（`docs/incomplete-work-audit-2026-10-20.md` §14.9）。
>   ID 16 は同日 04:13 UTC に Issue 4 件がクローズされ解消した。
```

### 3.3 `docs/incomplete-work-audit-2026-10-20.md` §14.3 の末尾——追記（**403 の記録は消さない**）〔D-03〕

```markdown
**〔2026-10-21 追記・現況監査ワーカーによる再確認〕** 上記の「承認済み・実行待ち」は**解消済み**である。

    gh issue list --state all            → 4 件すべて CLOSED、OPEN 0 件
    gh issue view 1 --json closedAt      → 2026-10-21T04:13:31Z
    gh issue view 3 --json closedAt      → 2026-10-21T04:13:32Z
    gh issue view 4 --json closedAt      → 2026-10-21T04:13:33Z
    gh issue view 5 --json closedAt      → 2026-10-21T04:13:33Z

**ID 16 は完了、ID 20 も完了**とする。上記の HTTP 403 の記録は
「当該サンドボックスのトークンでは `issues: write` を実行できなかった」という**事実の記録**であり、
歴史として残す（書き換えない）。統合役が `gh issue close` を再実行する必要はない。
誰が・どの経路でクローズしたかは本リポジトリに記録がなく、GitHub 側の履歴以外に残っていない。
```

併せて **§14.1 の表（正本）の ID 16 行のみ**更新を提案する（D-12）：

```markdown
| 16 | 動作確認 Issue #1/#3/#4/#5 のクローズ | 放置 | ✅ **完了** | 2026-10-21T04:13Z に 4 件すべて CLOSED、OPEN 0 件。§14.3 末尾の追記を参照。403 の記録は歴史として保持 |
```

および **L1393 の末尾要約**：

```markdown
**未対応（2026-10-21 再確認）**：**ID 18 のみ**（第3の論文の収集——既存文献集では解決しないと判明。§14.9。
別探索を別ワーカーが実施中）。ID 16 は Issue 4 件が 2026-10-21T04:13Z にクローズ済みで**解消**、
ID 17 は**凍結**、ID 19・ID 20 は**完了**。
```

### 3.4 `docs/literature-triage-2026-10-21.md`——**§2.1(1) の 2 行は編集しない**（重複回避）〔D-05〕

**未マージの `arena/2411d5fb-researchos` が、L104–107 を次のように書き換える変更を既に含んでいる**（実測：同ブランチの `compare` API で patch を確認）：

```diff
-| 固定タスクへの過適合を避ける | **未実装**（A7 の教訓はあるが、hold-out の仕組みはない） |
-| 低寄与コンポーネントの剪定 | **未実装**（監査 ID 19 で「使われていない数値」は検出したが…） |
+| 固定タスクへの過適合を避ける | `scripts/holdout_eval.py` を暫定追加。ただしRRSIのcritic／selectorではなく…（RRSI読解 §5） |
+| 低寄与コンポーネントの剪定 | `scripts/prune_candidates.py` を暫定追加。ただし構造インベントリであり…（同 §5） |
```

**したがって統合役は同ブランチをマージし、本稿から重複して編集しないこと。** マージが見送られた場合の代替文案：

```markdown
| 固定タスクへの過適合を避ける | `scripts/holdout_eval.py`（2026-10-21 暫定追加。**計測器・ゲートではない**。RRSI v3 本文照合の結果、原典の critic／selector とは別物と判定） |
| 低寄与コンポーネントの剪定 | `scripts/prune_candidates.py`（同上。**何も削除しない**。原典の pruner 基準＝実測 score gain／token cost ではない） |
```

**L102 / L143 の件数（29件 / EVD 49件）は変更せず**、文末（L257 の前行）に追記する：

```markdown
> **〔2026-10-21 追記・現況監査〕** 本文中の `verifications.jsonl（29件）`、`EVD 49件`、
> 「メモ17件」は**本稿作成時点のスナップショット**である。現在の実測は
> **verifications=31 / evidence=60 / メモ 19 件**（`python3 scripts/validate_state.py`、
> `python3 scripts/check_memo_citations.py`）。§6 の改訂時点の記述は歴史としてそのまま残す。
```

**L28 / L257 の「本文は未読」** も同様に、文末 §7（マージ後に存在）または追記で現在状態を示す：

```markdown
**〔2026-10-21 追記〕** 優先 1（RRSI）の**本文は読了済**（HTML v3 全15チャンク、Appendix A–F、
表1–9）。ただし本稿執筆時点では `main` に**未マージ**（`arena/2411d5fb-researchos`）。
マージ後は本稿 §7 および `contributions/` の `2026-10-21_rrsi_reading.md` が現在の読解状態の正本となる。
```

### 3.5 `docs/worker-handoff-literature-2026-10-21.md`——冒頭に進捗バナーを追記（**各プロンプト本文は変更しない**）〔D-08 / D-09 / D-17〕

プロンプト本文は「1 チャット = 1 論文」で単独完結するよう書かれており、**書き換えると再利用時に破損する**。 そのため 冒頭（「## ⚠️ 初版の誤りを訂正した」の直後）にバナーを置く：

```markdown
> **〔2026-10-21 追記・進捗（現況監査）〕** 以下のプロンプトは **2026-10-21 05:20 時点**の
> 前提で書かれている。**台帳件数は目安として読み替えること**
> （実測：EVD **60** / CLM **9** / VER **31** / HYP 2 / sources **13**）。
>
> | 優先 | 論文 | 現在の状態（2026-10-21） |
> |---|---|---|
> | 1 | RRSI `2609.24972` | **本文読了済・未マージ**（`arena/2411d5fb-researchos`。新規 SRC 1 件（末尾 4 桁 `a3a2`）、EVD 8、VER 1。暫定実装 2 本は「要修正」と判定） |
> | 2 | Stellar Colosseum `2609.15983` | **✅ 完了・登録済**（PR #45 / `SRC-20261021-2b88` / `contributions/2026-10-21_stellar_colosseum_reading.md`。本稿 L174 のカテゴリ誤記 cs.CL→cs.LG も訂正済） |
> | 3 | The Agentic Scientist `2610.18933` | **成果物あり・未マージ**（`arena/85f0cc80-researchos`。新規 SRC 1 件（末尾 4 桁 `7419`）、EVD 5、fixture に `2610.18933` 追記） |
> | 4 | SHELDON `2610.18025` | **✅ 完了・登録済**（PR #44 / `SRC-20261021-2384` / `contributions/2026-10-21_sheldon_reading.md` / fixture 追記済） |
> | 5 | RLTL;DR `2609.37633` | **未着手** |
>
> 優先 2・4 のプロンプトは**実行済みであり再実行しないこと**。
```

### 3.6 `README.md:119` と `docs/minimal-core-and-ci.md:44`——追記（**本文は変更しない**）〔D-10〕

`README.md` L119 の直後（または L119 末尾に括弧で）：

```markdown
（**〔2026-10-21 追記〕** 凍結記録を含む旧 `arena/*` ブランチは、監査 ID 11 で**全削除済**
——`docs/incomplete-work-audit-2026-10-20.md` §13.8(1)。現在リモートにある `arena/*` 9 本は
**別目的の作業ブランチであり、凍結記録ではない**。凍結機構の来歴は同 §13.8 と
`docs/stagnation-analysis-2026-10-20.md` を参照。）
```

`docs/minimal-core-and-ci.md:44`：

```markdown
| `policy/`、`GOVERNANCE.md`（`main` には存在しない。凍結時に除外された旧ファイル） | ガバナンス定義。凍結（`arena/*` ブランチに記録として残る —— **〔2026-10-21 追記〕当該ブランチは監査 ID 11 で全削除済み。凍結の来歴は `docs/incomplete-work-audit-2026-10-20.md` §13.8(1) を参照**） |
```

### 3.7 `README.md:21–22` / `docs/minimal-core-and-ci.md:66`——追記〔D-11〕

`docs/minimal-core-and-ci.md:66` の直後：

```markdown
**〔2026-10-21 追記〕** 上記は**抄録要約に基づく暫定実装**である。RRSI v3 本文の照合の結果、
`holdout_eval.py` は RRSI の**critic／selector ではなく**ローカル検出器の分割診断、
`prune_candidates.py` は**実測寄与に基づく pruner ではなく**非破壊の構造インベントリと判定された
（`contributions/` の `2026-10-21_rrsi_reading.md` §1-6、§5。**未マージ** `arena/2411d5fb-researchos`）。
いずれも**撤回・削除ではなく「要修正」**であり、本リポジトリの診断道具としての価値は維持される。
```

`README.md` L21–22 にも同旨の 1 文を追記（または「RRSI の 2 項目を**暫定**実装」とだけ補う）。

### 3.8 新規監査項目の提案（統合役の判断用・**採番は行わない**）

**ID 21（提案）：検査8 が `README.md` の現況記述を検査できていない。**

- 事実：`check_doc_numbers.py` は `>` で始まる行を除外する。`README.md` の現況ブロック（L5–L36）は**全行ブロッククォート**であり、**台帳件数・ソース数の記述がすべて検査対象外**。
- 実測：引用マークを外しただけで **7 件の陳腐化**を検出（§1.4）。うち 3 件は最新の台帳件数。
- **推奨する対策は (a)** —— 検査器の除外規則を広げると `docs/minimal-core-and-ci.md` L111 ・L134 のような正当な歴史記述（`drift-ok` 付き）まで巻き込む恐れがある：
  - **(a) 文書側**：現況を述べる数値は `>` の外に出す（箇条書きにする）。`docs/minimal-core-and-ci.md` §4 の「書式上の注意」に倣う。
  - (b) 検査器側：除外を「日付または『時点』の明示がある行のみ」に絞る（**偽陽性リスクあり・非推奨**）。
- **ID 19 と同型の教訓**：「ゲートを足した」は「ゲートが効いている」を意味しない。

**ID 22（提案）：未マージ 3 ブランチの統合とテキスト衝突。**

- `arena/85f0cc80` と `arena/2411d5fb` は**どちらも `state/sources.jsonl` と `state/evidence.jsonl` を変更**する。`docs/parallel-work-ownership.md` §4 / `docs/record-id-scheme.md` §4 が「未解決（自認）」とする**同一ファイルへのテキスト衝突**が、実際に発生しうる状態にある。
- ID 採番は非連番方式（`scripts/new_id.py`）のため **ID 自体は衝突しない**（実測：新規 ID は SRC が `7419` と `a3a2`、VER が `508e`。いずれも既存と重複なし）。衝突するのは**行の追加位置**のみであり、解決は機械的に可能。
- 統合役の作業：(1) 両ブランチを `main` に取り込み、`state/` の追記順序を統制する。(2) 取り込み後に全 8 ゲートを再実行する（とくに ゲート5＝書誌照合、ゲート8＝数値検査）。

---

## 4. 3 区分（真に未解決 / 意図的凍結 / 完了済みだが記録更新待ち）

### 4.1 【A】真に未解決——手が付いていない、または解けていない

| # | 項目 | 状態 | 根拠 |
|---|---|---|---|
| A-1 | **監査 ID 18**：閾値 R ~ 1 の検証に必要な「**同一タスク領域内でモデルの広がりを変えた第3の論文**」の収集 | **未解決**。既存インベントリ（54件）からは解決しないことが確定済み（§14.9）。別探索が進行中（`docs/` の `worker-assignment-prompts-2026-10-21.md` ワーカーB） | 監査 §13.11 / §14.9 / §14.4 |
| A-2 | **SHELDON 型の HYP–EVD 関係表の採否と backfill** | **未決着**。README L30 が「採否はメモ §5・§7 を参照」と保留したまま。実測 **54/60（90.0%）が未紐付け**で、**台帳スキーマは未変更**（`evidence.jsonl` / `hypotheses.jsonl` に verdict フィールドなし） | `state/` 全件走査、README L30 |
| A-3 | **`counterclaim_ids` の未設定が再発**（D-16） | **`CLM-006` が空、`CLM-20261021-7b3e` はフィールド欠落**。監査 ID 5 は「完了」と記録されているが、新規 CLM には適用されていない。`schemas/claim.json` が required にしないため CI は緑 | `state/claims.jsonl` 全件 |
| A-4 | **リモート `arena/*` 9 本の扱い**（D-02） | **人間の承認待ち**。うち 6 本は `ahead=0` の残置で冗長。**ID 11 を完了した直後に同型の問題が再生産されている** | `gh api .../branches` / `compare` |
| A-5 | **未マージ 3 ブランチの統合**（とくに 85f0cc80 × 2411d5fb のテキスト衝突） | **未了**。§7.5 が「未解決（自認）」とする同一ファイル追記の衝突が現実化しうる | §3.8 / `gh api .../compare` |
| A-6 | 優先5 **RLTL;DR** の読解 | **未着手**（成果物なし、fixture 未追記） | `contributions/` 一覧、fixture 13件 |
| A-7 | **ID 21（提案）**：検査8 が README 現況を検査できない | **未対応**（本稿で検出のみ） | §1.4 / §3.8 |

### 4.2 【B】意図的凍結——**ラベルを外してはならない**（人間の指示による）

| # | 項目 | 凍結の根拠と再開条件 |
|---|---|---|
| B-1 | **ID 17**：`rho` / `c` の代替経路（過程の直接計装） | 監査 §14.8。**人間の指示により凍結**（理由：非定量的テーマでは難問）。再開条件＝実ワーカー群を並列実行できる環境、または過程から直接測る手段の獲得。**到達点は有効な知見として残る**：対誤り相関による推定は検出力が 2〜3 桁不足（`rho=0.30` の検出に共同判定項目 約1,454 件、手持ち 8 件）。`rho > 0` の直接観測は既に存在（`EVD-20261020-40dc`）。**割当メモも「どのワーカーにも再開タスクとして割り当てない」と明示** |
| B-2 | ガバナンス5機構の凍結（役割分離／追記専用台帳／レビューキュー／trailer 検査／land ゲート） | 監査 §7.1 / §14.5。解除条件「DoD を 3 行以内で先に書く」は**未達** |
| B-3 | `gitswarm/readout.py` が `main` で恒久的に使えない | 監査 §6.3。**意図的中断**。Phase 4 まで死に道具であり続ける想定 |
| B-4 | 所有マップが解決しない 3 項目（テキスト衝突／共有ファイル同時編集／作者識別） | `docs/parallel-work-ownership.md` §4 が**自ら「未解決」と明記**。見つかった未完了ではなく、宣言された未完了 |
| B-5 | **ID 12**（記録数値のドリフト是正）の**撤回** | 監査 §13.8(2)。人間の判断で監査項目自体を撤回。**ID 21（提案）は ID 12 を覆すものではない**——将来の陳腐化を防ぐものであり、過去の記録値を書き換えるものではない |

### 4.3 【C】完了済みだが記録更新待ち——**記録だけが遅れている**

| # | 項目 | 完了の根拠 | 更新すべき記録 |
|---|---|---|---|
| C-1 | **監査 ID 16 / ID 20**：動作確認 Issue 4 件のクローズ | **Issue #1/#3/#4/#5 すべて CLOSED**（2026-10-21T04:13:31–33Z）、OPEN 0 件 | 監査 §14.1 表（ID 16 行）、§14.3 末尾、§14.6、L1393 → §3.3 |
| C-2 | RRSI 未実装 2 項目の**実装**（`holdout_eval.py` / `prune_candidates.py`） | PR #42、両ファイル実在、テスト 18＋19 件、8 ゲート緑 | `docs/literature-triage-2026-10-21.md` L104–107 → **§3.4（マージで解消。重複編集禁止）** |
| C-3 | **SHELDON** の読解・SRC 登録・fixture 追記 | PR #44 / `SRC-20261021-2384` / `contributions/2026-10-21_sheldon_reading.md` / snapshot に `2610.18025` あり | handoff 優先4（L299–301, 323, 338, 343）→ §3.5 |
| C-4 | **Stellar Colosseum** の読解・SRC 登録・カテゴリ誤記訂正 | PR #45 / `SRC-20261021-2b88` / `contributions/2026-10-21_stellar_colosseum_reading.md` / handoff L174 訂正済 | handoff 優先2（L165）→ §3.5 |
| C-5 | **RRSI v3 本文の読解** | `arena/2411d5fb-researchos` に `contributions/` の `2026-10-21_rrsi_reading.md`（224行）＋ EVD 8・SRC 1・VER 1 | triage L28 / L257「本文は未読」→ §3.4 |
| C-6 | **The Agentic Scientist** の読解 | `arena/85f0cc80-researchos` に `contributions/` の `2026-10-21_agentic_scientist_reading.md`（307行）＋ SRC 1・EVD 5・fixture 追記 | handoff 優先3（L240, 281）→ §3.5 |
| C-7 | README の**台帳件数 3 か所**（sources / evidence / verifications） | 実測 13 / 60 / 31 | README L30 → §3.1（追記） |
| C-8 | README の「**リモートのブランチは `main` のみ**」 | 実測 10 本 | README L16 → §3.2（追記） |
| C-9 | 凍結記録の参照先（`arena/*` ブランチ）の消失 | ID 11 で全削除済 | README L119 / minimal-core-and-ci.md L44 → §3.6 |
| C-10 | 「RRSI の設計要素の実装」という表現の過大表明 | RRSI v3 本文照合で「別物」と判定 | README L21–22 / minimal-core-and-ci.md L66 → §3.7 |

---

## 5. 実行した検査と結果

### 5.1 リポジトリ内（すべて読み取りまたは `/tmp` へのみ書き込み）

```text
環境: /home/user/ResearchOS、HEAD = 6ea24b3、ブランチ arena/cd154ec2-researchos

python3 -m unittest discover -s tests 2>&1 | grep -E "^(Ran|OK)"
    → Ran 242 tests / OK
    12 ファイルの内訳: 34/17/33/25/16/20/12/13/14/21/18/19 = 242（grep で合算検証）
python3 gitswarm/benchmarks/benchmark.py --check  → PASS  (exit 0)
python3 gitswarm/readout_sim.py --check           → PASS  (exit 0)
python3 scripts/validate_state.py                 → PASS  (sources=13, evidence=60, claims=9, verifications=31, hypotheses=2)
python3 scripts/check_citations.py                → 12 checked / 1 skipped / 0 failure   (exit 0)
python3 scripts/check_memo_citations.py           → 19 memos / 49 citations / 2 skipped / 0 failure (exit 0)
python3 scripts/check_memo_ledger_refs.py         → 0 dangling / 5 archived              (exit 0)
python3 scripts/check_doc_numbers.py              → 0 stale number(s)                    (exit 0)
                                                     actual: tests=242 gates=8 sources=13 evidence=60
                                                             claims=9 verifications=31 hypotheses=2
    → 全 8 ゲート exit 0

python3 （state/*.jsonl の集計スクリプト）
    → EVD を持たない SRC: 0 / 13
    → HYP 未紐付け EVD: 54/60 = 90.0%
    → CLM・HYP いずれにも紐づかない EVD: 42/60
    → counterclaim_ids が空の CLM: 6/9（CLM-006 は []、CLM-20261021-7b3e は None）
    → VER: source_check 14 / logical_consistency 9 / deterministic 6 / falsifier_critic 2 = 31
           結果内訳 pass 16 / warn 10 / fail 5、target_id=SRC-004 は 2 件
    → HYP: HYP-001 supported (evidence_ids 3)、HYP-002 testing (3)

python3 （tests/fixtures/arxiv_metadata_snapshot.json の走査）
    → entries 13 件。内訳: 2610.17184 / 2610.08364 / 2610.07625 / 2610.04862 / 2609.24972 /
      2609.18094 / 2609.15983 / 2608.13417 / 2608.06663 / 2606.10209 / 2605.23950 / 2507.13334 /
      2610.18025
    → capture_method = "arxiv abs pages read via web fetch tool"、captured_at 2026-10-20
    → 2610.18933（Agentic Scientist）は main に未登録（grep -c = 0）
    → 2609.24972（RRSI）は登録済（grep -c = 3）

grep -n -E "sources=|evidence=|claims=|verifications=|hypotheses=|件|テスト|ゲート" README.md
    → 台帳件数の記述は L14 と L30 の 2 か所のみ、いずれも `>` ブロッククォート内
grep -n "未実装|29件|EVD 49件|本文は未読" docs/literature-triage-2026-10-21.md
    → L102 / L104 / L105 / L143 / L257
grep -n "未追記|EVD 49|VER 29|未登録" docs/worker-handoff-literature-2026-10-21.md
    → L44 / L45 / L136 / L240 / L281 / L301 / L323 / L338 / L343 / L359 / L379 / L400 / L418 / L419
grep -n "arena/\*" README.md docs/minimal-core-and-ci.md
    → README.md L16 / L119、docs/minimal-core-and-ci.md L44

【検査8 の盲点の実証】リポジトリのファイルは変更せず、/tmp にコピーして実行
mkdir -p /tmp/driftcheck && python3 - <<'PY'   # README.md の行頭 "> " のみ剥がして /tmp へ書出し
python3 scripts/check_doc_numbers.py --file /tmp/driftcheck/README_unquoted.md
    → 7 stale number(s)（L14: sources 11/13・evidence 47/60・claims 8/9・verifications 27/31
                        L30: sources 12/13・evidence 54/60・verifications 30/31）  exit=1
```

### 5.2 GitHub（**すべて読み取り専用**）

```text
gh issue list --state all --limit 50
    → 5  CLOSED  [動作確認] REST作成テスト2
      4  CLOSED  [動作確認] REST作成テスト
      3  CLOSED  [動作確認] 権限再現テスト
      1  CLOSED  [動作確認] GitHub Connections 接続テスト
gh issue list --state open --limit 10 --json number -q 'length'   → 0
gh issue view {1,3,4,5} --json number,state,closed,closedAt
    → いずれも state=CLOSED, closed=true
      closedAt = T04:13:31Z / T04:13:32Z / T04:13:33Z / T04:13:33Z（すべて 2026-10-21）
gh issue view 2 --json number,state,title
    → Issue #2 は存在しない（#2 は PR）

gh pr list --state all --limit 60    → PR #2〜#45。OPEN 0 件。最新 MERGED は #45（06:22:19Z）
gh pr list --state open              → （空）

gh api repos/aiselfmyself/ResearchOS/branches --paginate
    → 10 本: main ＋ arena/{ac3628ba, b7545cd1, bbc9c7b9, be8b5d01, 1e74f6a0, 85f0cc80,
                             2411d5fb, 7605f122, 23370dd5}-researchos
gh api .../compare/main...<branch>  --jq '"\(.ahead_by) \(.behind_by)"'
    → ahead=0: ac3628ba / b7545cd1 / bbc9c7b9 / be8b5d01 / 7605f122 / 23370dd5  （6 本）
      ahead=1: 1e74f6a0 / 85f0cc80 / 2411d5fb                                    （3 本）
gh api .../commits/<branch>          → 各ブランチ HEAD の日時と 1 行目のコミットメッセージ（§1.3 の表）
gh api .../compare/main...arena/2411d5fb-researchos --jq '.files[]|"\(.status) \(.filename)"'
    → 11 ファイル。docs/literature-triage-2026-10-21.md の patch を確認（§3.4 の diff）
gh api .../contents/<path>?ref=<branch> --jq .content | base64 -d
    → 2026-10-21_rrsi_reading.md（先頭 40 行）、
      worker-assignment-prompts-2026-10-21.md（全 215 行）を読み取り
      （いずれも未マージブランチ上のファイル。`main` には存在しない）

gh run list --branch main --limit 10 → 直近 10 本すべて completed / success
gh api repos/aiselfmyself/ResearchOS -i | grep -i x-oauth-scopes
    → X-Oauth-Scopes: （空）／ X-Accepted-Github-Permissions: metadata=read
      …監査 §14.3 が記録した「issues: write 権限がない」という状況と矛盾しない
```

### 5.3 やっていないこと（明示）

- **ファイルの変更は一切なし**（`state/`、`README.md`、`docs/`、`scripts/`、`tests/`、CI 定義、fixture すべて未変更。`/tmp` のみに一時コピーを作成）
- **Issue のクローズ・オープン・コメント、PR の作成・マージ・クローズ、ブランチの削除**は一切していない
- `git commit` / `git push` は未実施（本稿の新規作成のみ。所有マップ §2 が `contributions/<自分のファイル>.md` を各セッションに許容）
- `--live` による arXiv API 実照合、外部実験、原典の新規取得は実施していない（未マージブランチの内容は**読み取りのみ**で確認）
- 未マージ 3 ブランチの**内容の正しさ**（読解の妥当性・引用の逐語性）は評価していない。本稿は**「存在する／しない」と「文書との食い違い」**のみを扱う

---

## 6. 所見

1. **実測値は健全で、腐っているのは文書だけ。** 8 ゲート緑、直近 10 本の CI 成功、台帳件数も既知値どおり。食い違い 17 件のうち**コード・台帳の不具合は 1 件もない**（唯一の台帳側の指摘 D-16 も「スキーマが required にしない」という設計判断の帰結）。
2. **「完了したが記録が追いつかない」が 10 件を占める。** とくに **RRSI 本文読解と Agentic Scientist 読解は成果物まで完成しながら未マージ**で、`main` 側の文書は「未読・未登録」のまま。**未マージの作業を「未着手」と読む誤りは、完了報告の二重計上と同じ方向の失敗**である。
3. **ID 19 の教訓が ID 19 自身に当てはまる。** 検査8 は「数値のハードコード」を閉じるものだったが、**現況記述が `>` で書かれているだけで丸ごと検査対象から外れる**（§1.4、7 件検出）。`docs/minimal-core-and-ci.md` §4 の「書式上の注意」が同じ罠を既に指摘しているにもかかわらず、**その注意は `README.md` に適用されていない**。ID 21 として登録を提案する。
4. **ID 11 は完了したが、問題は再生産されている。** 「`main` のみになった」直後から `arena/*` が 9 本に積み上がった（うち 6 本は `ahead=0` の残置）。**ブランチの削除は対症療法であり、運用が変わらなければ再発する。** 監査 §14.6 の「一度直したは直り続けているを意味しない」は、ID 5→D-16、ID 11→D-02 と**2 回とも的中している**。
5. **GitHub 側の記録がリポジトリに残らない構造的な隙がある。** Issue 4 件がクローズされた事実はリポジトリのどこにもなく、監査は「実行待ち」のまま。**クローズ時刻（04:13:31–33Z）から、PR #41（04:09）と PR #42（04:50）の間の人間による操作と推定される**が、確証はない。今後は「変更を記録した場所」を文書側にも残す運用を検討してよい。

---

*2026-10-21、現況監査ワーカー（A）。台帳・コード・既存文書・GitHub の状態は変更していない。*
