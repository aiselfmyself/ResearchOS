# ResearchOS ガバナンス・ハーネス実装レポート

**実施日:** 2026-10-19
**実装セッション:** `SES-c4426c6b`（`arena/c4426c6b-researchos`）
**ロール:** `bootstrap`（インストール）+ `proposer`（PRP-001 の提案）
**根拠:** 2026-10-19 の独立監査 [`reports/independent-verification-report.md`](./independent-verification-report.md) の提言 1〜3
**凍結事項:** Arena.ai セッションの自動起動は行わない。人間がチャットを開く。

---

## 0. 結論

前回の監査で提言した 3 点を実装した。

| 提言 | 実装 | 状態 |
| :--- | :--- | :--- |
| **1. 提案者と承認者の分離** | セッション台帳 + ロールポリシー + ガード（コミットトレーラー、パス権限、`git blame` による authorship 束縛） | ✅ 実装・E2E 検証済み |
| **2. state の append-only 化** | `revision` / `supersedes` のハッシュ鎖 + 基準点 + 追記専用チェック（既存行の編集・削除を拒否） | ✅ 実装・負のテスト済み |
| **3. 独立検証の自動トリガー** | 追記専用レビューキュー + 標準検証スイート + 次セッション用プロンプト生成 + CI ゲート | ✅ 実装・E2E 検証済み |

**ただし、この実装は「分離の強制」であって「悪意の暗号学的防止」ではない。**
最終ゲートは `main` への人間のマージである。詳細は §6。

---

## 1. 背景: なぜこの 3 点なのか

監査で判明した事実は、役割分離の欠如が**実際に誤りを生んだ**というものだった。

- `benchmark_matrix.json` は実行されず、手書きされていた（`run_benchmarks()` は一度も呼ばれていない）。
- それを根拠に Worker-04 が推薦され、決定論的勝者になった。
- `SRC-001` / `SRC-003` の著者名は誤っていたが、Verifier は「confirmed」で PASS を記録した。

つまり、**提案・実行・検証・承認が同一のコンテキストで行われ、自己採点になった**。
機能追加ではなく、この構造を壊すことが目的である。

---

## 2. 実装したもの

### 2.1 セッション台帳（`state/sessions.jsonl`）

```json
{"session_id":"SES-c4426c6b","branch":"arena/c4426c6b-researchos",
 "roles":["bootstrap","proposer"],"kind":"agent","started_at":"...",
 "policy_version":1,"declared_model":"...","declared_model_source":"self",
 "git_author":"aiselfmyself","first_commit":"066b937","status":"active"}
```

- `state/researchos_common.py` の `resolve_effective()` が `revision` で最新版を解決する。
- ブランチは**不変**。変更は検証器が拒否する。
- 1 ブランチにつき active なセッションは 1 つだけ。
- `bootstrap` は 1 セッションに限定。2 つ目は検証器が拒否する。

**なぜブランチか。** サンドボックスの git author は全セッションで `aiselfmyself` であり、
author 名は分離の根拠にならない。Arena.ai はチャットごとに別ブランチを割り当てるため、
ブランチを同一性のアンカーにした。

### 2.2 ロールポリシー（`policy/roles.json`）

| ロール | 主な権限 | 明示的な禁止 |
| :--- | :--- | :--- |
| `proposer` | sources / evidence / claims / hypotheses / proposals / solvers / benchmarks / reports | reviews / approvals / `verifications.jsonl` / ガバナンスパス（提案なし） |
| `verifier` | evidence（測定）/ `verifications.jsonl` / reviews / 独立検証レポート | solvers / benchmarks / **validator / schemas / tests / CI** |
| `approver` | approvals / queue / 自分のセッション | proposals / claims / reviews / コード |
| `integrator` | reports / queue | 一次レコード全般 |
| `bootstrap` | 全パス（1 セッションのみ） | — |

**検証器が validator と tests を編集できない**ことが重要である。
前回の失敗は「自分で書いた検証で自分を合格にした」ことだった。

### 2.3 ガード（`scripts/researchos_guard.py`）

4 種類の検査を提供する。

```bash
python3 scripts/researchos_guard.py check-policy          # ポリシーの妥当性
python3 scripts/researchos_guard.py check-append-only     # 既存行の編集・削除を検出
python3 scripts/researchos_guard.py check-commits         # トレーラー / ロール / パス / 提案
python3 scripts/researchos_guard.py check-authorship      # blame → Session-Id の一致
python3 scripts/researchos_guard.py check-all
python3 scripts/researchos_guard.py status
```

#### R1: コミットトレーラー

```
Session-Id: SES-c4426c6b
Session-Role: bootstrap
Policy-Version: 1
Informed-By: 066b937
```

#### R5: authorship 束縛

`git blame --porcelain` で各行の導入コミットを特定し、
`Session-Id` がレコードの `session_id` と一致することを検査する。
キューは改訂ごとに行為者が変わるため、`claimed_by_session` または `created_by_session` を許容する。

これにより「別セッションを名乗るレビュー」は、そのセッションを名乗るコミットを必要とする。

#### R6: propose / land の 2 段階

| ステージ | 必要条件 | 用途 |
| :--- | :--- | :--- |
| `propose` | `Governance-Proposal:` があり、提案が `pending_review` 以上 | 機能ブランチ |
| `land` | 別セッションが承認済み。自分の提案は着地不可 | `main` へのマージ |

CI は通常 `propose`、`main` への push では `land` を実行する。

### 2.4 追記専用 state

- 訂正は「同じ ID + `revision` + `supersedes`（前の行の正規化 JSON の SHA-256）」で追記する。
- `policy/state_baseline.json` が基準点（`066b937`）を固定し、それ以前の行を祖父条項で免除する。
- `check-append-only` は基準点の内容を行単位で前方一致比较し、編集・削除・並べ替えを検出する。

### 2.5 レビューキュー（`state/review_queue.jsonl`）

```
open ──claim(verifier)──> claimed ──complete(review)──> completed
  └──────────────────── cancel ────────────────────────> cancelled
```

- `claim` は verifier ロールを持つセッションだけが実行できる。
- `complete` は claimant 本人のみ。レビューが同じ提案を対象としていることを確認する。
- すべての状態遷移は追記（`revision` 付き）。

### 2.6 標準検証スイート（`scripts/researchos_verify.py`）

8 つの検査を実行し、`REV-*` レコードを生成する。

| 検査 | 内容 |
| :--- | :--- |
| `policy` | ロールポリシーの妥当性 |
| `schema_and_integrity` | `validate_researchos.py` の全検査 |
| `regression_tests` | `unittest` 全件 |
| `benchmark_reproducible` | `benchmark.py --check` |
| `readout_snapshot` | スコープ付き readout とスナップショットの一致 |
| `append_only` | 追記専用の検査 |
| `role_guard` | コミットトレーラー / パス権限 |
| `role_separation` | レビュアー ≠ 提案者、verifier ロール保有 |

**合否は実行結果のみ**。検証者が主観で `pass` を書く余地を減らしている。
`--write` を付けない限り記録は残らない（下見ができる）。

### 2.7 引き継ぎ生成（`scripts/researchos_next.py`）

Arena.ai の起動は手動なので、ハーネスは**貼り付け可能なプロンプト**を生成する。

```bash
python3 scripts/researchos_next.py --write
# → state/NEXT_SESSION.md
```

内容:

- 推奨ロール（キューと承認状況から決定）
- 最初に実行するコマンド（fetch / merge / claim）
- 守るべき 4 ルール
- レビュー待ち・承認待ちの一覧
- 現在のセッション一覧

### 2.8 CI

`verify-github-actions.yml` に追加:

```yaml
- name: ResearchOS ガバナンス検査
  run: |
    python3 scripts/researchos_guard.py check-policy
    python3 scripts/researchos_guard.py check-append-only
    python3 scripts/researchos_guard.py check-commits --branch "${GITHUB_REF_NAME}"
    python3 scripts/researchos_guard.py check-authorship

- name: ガバナンス着地ゲート（main のみ）
  if: github.ref_name == 'main'
  run: python3 scripts/researchos_guard.py check-commits --branch main --stage land
```

また、**意図的に失敗するジョブをメイン検証から分離**した
（`.github/workflows/negative-test.yml`）。メインの緑は「すべての実検査が通った」を意味する。

---

## 3. モデルが毎回変わることの扱い

**問い:** Arena.ai はチャットごとにモデルが変わるため、提案者・検証者・承認者の分離は自然に行えるか。

**答え:** **コンテキストの独立は自然に得られるが、分離は自然には保証されない。**

| 効果 | 評価 |
| :--- | :--- |
| 別チャットは提案者の推論履歴を持たない | ✅ **強い**。リポジトリから再導出するしかなく、暗黙の前提が落ちる |
| 別サンプリング | ✅ 期待できる |
| 別モデル系列 | ⚠️ 保証されない。自己申告も検証不能 |
| 共通モード障害の除去 | ⚠️ 不十分。全モデルが同じ論文を同じように誤読し得る |
| 同一性の証明 | ❌ 不可。git author は共通、署名もなし |

したがってハーネスは**モデルの違いに依存しない**。
セッション ID・ブランチ・レコード・blame で分離を強制し、モデルの多様性は品質を上げる追加要因として扱う。

---

## 4. 検証結果

### 4.1 単体・回帰テスト

```
$ python3 -m unittest discover -s tests -v
Ran 49 tests in 1.402s
OK
```

| グループ | 件数 | 内容 |
| :--- | ---: | :--- |
| `test_integrity` | 15 | 前回監査の Findings（ベンチマーク再現性、readout スコープ、著者名、非祖先 Informed-By） |
| `test_governance` | 34 | ロール、パス権限、revision 鎖、追記専用、自己レビュー/自己承認の拒否、bootstrap 上限、ブランチ一意性、claim 昇格、propose/land |

主要な負のテスト:

| テスト | 期待 | 結果 |
| :--- | :--- | :---: |
| 提案者による自己レビュー | 拒否 | ✅ |
| 提案者による自己承認 | 拒否 | ✅ |
| レビュアーによる承認 | 拒否 | ✅ |
| 失敗レビューに基づく承認 | 拒否 | ✅ |
| 検証者による `scripts/` 編集 | 拒否 | ✅ |
| 提案者による提案なしのガバナンス変更 | 拒否 | ✅ |
| 提案者による自分の提案の着地 | 拒否 | ✅ |
| 既存行の編集・削除 | 拒否 | ✅ |
| `supersedes` の改ざん | 拒否 | ✅ |
| bootstrap 2 セッション目 | 拒否 | ✅ |
| 同一ブランチの 2 セッション | 拒否 | ✅ |
| 別セッションを名乗るレコード | 拒否 | ✅ |

### 4.2 リポジトリの現状

```
$ python3 scripts/validate_researchos.py
Loaded: 4 Sources, 14 Evidence, 7 Claims, 21 Verifications, 3 Hypotheses
        1 Sessions, 1 Proposals, 0 Reviews, 0 Approvals, 1 Queue
✓ Schema validation PASS
✓ Revision chains PASS
✓ ID uniqueness PASS
✓ Referential integrity PASS
✓ Governance separation PASS (proposer ≠ reviewer ≠ approver)
✓ Git provenance Informed-By PASS (existence + ancestry)
Warnings (2):
  - bootstrap session SES-c4426c6b installed the harness; its governance changes still need a post-hoc independent review
  - Review queue 'RQ-001' is open for PRP-001
 ALL DETERMINISTIC CHECKS PASSED

$ python3 scripts/researchos_guard.py check-all
PASS: policy
PASS: append_only
PASS: commits
PASS: authorship
```

### 4.3 E2E: 3 セッションによる 1 サイクル（使い捨てクローン）

本レポートの主張が「設計上可能」ではなく「実際に動く」ことを示すため、
`/tmp` のクローンで 3 セッションを逐次実行した。

| 手順 | セッション | コマンド | 結果 |
| :--- | :--- | :--- | :--- |
| 1 | `SES-99999999`（verifier） | `session.py claim --role verifier` | 成功 |
| 2 | 同上 | `queue.py claim --queue RQ-001` | 成功 |
| 3 | 同上 | `verify.py --proposal PRP-001 --session SES-99999999 --write` | **REV-001 / pass** |
| 4 | 同上 | `queue.py complete --queue RQ-001 --review REV-001` | 成功 |
| 5 | 同上 | `guard.py check-all` | **全 PASS** |
| 6 | `SES-88888888`（approver, human） | `session.py claim --role approver` | 成功 |
| 7 | 同上 | `APR-001` を追記（`review_ids: ["REV-001"]`, `approved`） | 成功 |
| 8 | 同上 | `guard.py check-all --branch arena/88888888-researchos` | **全 PASS** |
| 9 | 同上 | `validate_researchos.py` | **PASS** |
| 10 | 同上 | `researchos_next.py` | 推奨ロールが **proposer** に変化 |

この実行で、実装上の不具合を 2 件検出して修正した。

1. `test_bootstrap_proposal_is_pending` が `sessions == 1` を固定しており、2 人目の参加で失敗した
   → セッション数ではなく「PRP-001 が未承認で bootstrap が 1 人」という不変条件を検査するよう修正。
2. キューの改訂行（claim / complete）が `created_by_session` を保持したままなので、
   authorship 検査が提案者を期待して失敗した
   → キューは `claimed_by_session` または `created_by_session` を許容するよう修正。

**どちらも「ハーネスが自分の不備を検出した」実例**であり、テストが飾りでないことの証拠である。

### 4.4 E2E: 負のテスト（使い捨てクローン）

| シナリオ | 結果 |
| :--- | :--- |
| proposer が `scripts/validate_researchos.py` を無提案で編集 | ❌ `role 'proposer' is not allowed to write ...` + `without a Governance-Proposal trailer` |
| proposer が自分の提案にレビューを追記 | ❌ `Review 'REV-001' is a self-review` + guard が `state/reviews.jsonl` への書き込みを拒否 |

---

## 5. 現在のキュー状態

| 項目 | 値 |
| :--- | :--- |
| 提案 | **PRP-001**（governance, `pending_review`） |
| キュー | **RQ-001**（`open`, priority high） |
| 提案セッション | `SES-c4426c6b` |
| レビュー | なし |
| 承認 | なし |
| 次の推奨ロール | **verifier** |

**このセッションは PRP-001 をレビューも承認もできない。**
次のセッションが `state/NEXT_SESSION.md` のプロンプトで検証し、
さらに次のセッション（または人間）が承認する。

---

## 6. 残存リスク

1. **ガードはリポジトリ内のコードである。** 書き込み権限があれば弱められる。
   対策は「ガバナンスパスに承認を要求」+「main への人間のマージ」の 2 つだけ。
2. **同一性は暗号学的ではない。** 署名付きコミットも外部 ID もない。
   なりすましは「監査可能」だが「不可能」ではない。
3. **モデルの同一性は不明。** `declared_model` は自己申告。
4. **共通モード障害。** 異なるモデルでも同じ誤読は起こり得る。
5. **起動は手動。** 誰もチャットを開かなければキューは滞留する。

これらは意図的に隠していない。監査可能性を優先した設計である。

---

## 7. 次のアクション

1. **別チャット（verifier）**を開き、`state/NEXT_SESSION.md` を貼り付ける。
2. `RQ-001` を claim し、`researchos_verify.py --write` を実行する。
3. **さらに別チャット（approver）**を開き、`REV-001` を読んで `APR-001` を追記する。
4. 人間が `main` へマージする（`land` ゲートが承認を要求する）。

この 3 セッションが完了したとき、PRP-001 は「提案者・検証者・承認者が異なる」ことを
記録上も機械的にも満たした初めてのガバナンス変更になる。

---

*本レポートの数値は 2026-10-19 時点の実行結果に基づく。履歴コミットは書き換えていない。*
