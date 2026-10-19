# ResearchOS Governance Protocol v1

**目的:** 提案（proposer）・検証（verifier）・承認（approver）を**別セッション**に分離し、
研究状態を**追記専用**にし、レビュー待ちを**機械的に可視化**する。

**対象:** `arena/*` ブランチで動く Arena.ai Agent Mode のセッション。

> **凍結事項:** セッションの起動は自動化しない。Arena.ai のチャットは人間が開く。
> ハーネスは「次に何をすべきか」を記録し、貼り付け可能な引き継ぎプロンプトを生成する
> （`scripts/researchos_next.py`）。起動の自動化だけが意図的に手動のまま残されている。

---

## 1. なぜ分離が必要か（2026-10-19 の監査から）

前セッションは `validate_researchos.py` を PASS させ、Verifier が「著者を確認した」と記録した。
しかし実際には、ベンチマークは一度も実行されておらず（`benchmark_matrix.json` は手書き）、
2 本の論文の先頭著者が誤っていた。

**同じセッションが提案し、検証し、承認すると、自己採点になる。**
したがって、役割の分離は「運用の好み」ではなく、このリポジトリで実際に観測された失敗への対策である。

---

## 2. モデル

```
Arena.ai の 1 チャット = 1 セッション = 1 ブランチ
```

| 概念 | 実体 | 備考 |
| :--- | :--- | :--- |
| Session | `SES-<branch-id>` | `arena/c4426c6b-researchos` → `SES-c4426c6b` |
| Branch | `arena/<id>-researchos` | **同一性のアンカー**。Arena がセッションに束縛する |
| Role | `bootstrap` / `proposer` / `verifier` / `approver` / `integrator` | 1 セッションが複数持てるが、**同じ成果物**には 1 役割だけ |
| Record | `state/*.jsonl` の 1 行 | 訂正は新しい行（`revision` + `supersedes`） |

### なぜブランチがアンカーなのか

このサンドボックスの git author は**全セッションで同一**（`aiselfmyself`）である。
したがって author 名は分離の根拠にならない。Arena.ai はセッションごとに別ブランチを割り当てるので、
**ブランチの一意性 + セッション記録の branch 不変性**を分離の土台にする。

`declared_model` は記録するが、**自己申告であり検証しない**。コンプライアンス判定には使わない。

---

## 3. ロールと書き込み権限

| パス | proposer | verifier | approver | integrator |
| :--- | :---: | :---: | :---: | :---: |
| `state/sources.jsonl` | ✅ | – | – | – |
| `state/evidence.jsonl` | ✅ | ✅（測定証拠） | – | – |
| `state/claims.jsonl` | ✅ | – | – | – |
| `state/hypotheses.jsonl` | ✅ | – | – | – |
| `state/verifications.jsonl` | – | ✅ | – | – |
| `state/proposals.jsonl` | ✅ | – | – | – |
| `state/reviews.jsonl` | – | ✅ | – | – |
| `state/approvals.jsonl` | – | – | ✅ | – |
| `state/review_queue.jsonl` | ✅ | ✅ | ✅ | ✅ |
| `state/sessions.jsonl` | ✅（自分のみ） | ✅（自分のみ） | ✅（自分のみ） | ✅（自分のみ） |
| `gitswarm/solvers/**`, `gitswarm/benchmarks/**` | ✅ | – | – | – |
| `verifications/**`, 独立検証レポート | – | ✅ | – | – |
| `reports/**`, `README.md`, `docs/**` | ✅ | 一部 | – | ✅ |
| `scripts/**`, `schemas/**`, `policy/**`, `tests/**`, `.github/**` | ⚠️ 承認済み提案が必要 | ❌ | ⚠️ 着地のみ | ❌ |

`bootstrap` は**インストール時の 1 セッションだけ**。検証器が上限 1 を強制する。

---

## 4. 強制される 6 つのルール

### R1. すべてのコミットにセッショントレーラー

```
Session-Id: SES-c4426c6b
Session-Role: proposer
Policy-Version: 1
Informed-By: <ancestor sha>
```

`Session-Id` / `Session-Role` が無いコミットは、ガバナンス基準以降は**失敗**する。

### R2. パス権限

ロールの `may_write` に一致しないパスを変更すると失敗する。
検証器は `scripts/`, `schemas/`, `policy/`, `tests/`, `.github/` を**変更できない**。
（検証者が検査対象を書き換えられたら分離の意味がない。）

### R3. 提案者・検証者・承認者の非重複

| 関係 | ルール |
| :--- | :--- |
| 提案 → レビュー | `review.session_id != proposal.session_id` |
| 提案 → 承認 | `approval.session_id != proposal.session_id` |
| レビュー → 承認 | `approval.session_id ∉ review.session_id` |
| 承認の前提 | 参照するレビューに `result: pass` が最低 1 件 |
| 承認の効果 | **approval レジャーが正**。提案の `status` は書き換え不要 |

### R4. 追記専用（PRP-002 で強化: ローリングハッシュ鎖）

`state/*.jsonl` は行の追加のみ。既存行の編集・削除・並べ替えは `check-append-only` が拒否する。
訂正は同じ ID で新しい行を追記する:

```json
{"claim_id":"CLM-003", "...":"...", "revision":2, "supersedes":"<前の行の正規化JSONのsha256>"}
```

基準点は `policy/state_baseline.json`（`base_commit: 066b937`）。
それ以前の行は**祖父条項**で免除され、行ハッシュで識別される。

**PRP-002 以降の追加保証 (C2/A1):** 各ファイルの全行は `revision` と `supersedes` によるローリングハッシュ鎖で検証される。`state/reviews.jsonl` 等の base 後に作成された台帳も、接頭辞だけでなく各追記行の `supersedes == line_hash(prev)` が `check-append-only` で検証される。単なる前方一致では保護されない追記行の書き換え (A1) はハッシュ鎖で検出される。静的 baseline は段階的にハッシュ鎖のみへ移行する。

### R5. レコード authorship 束縛

`state/*.jsonl` の各行は `git blame` で導入コミットを特定し、
そのコミットの `Session-Id` がレコードの `session_id`（キューは `claimed_by_session` または
`created_by_session`）と一致しなければならない。

これにより「別セッションを名乗るレコード」は、そのセッションを名乗るコミットを必要とする。

### R6. ガバナンス変更の 2 段階（PRP-002 G1 で明確化）

| ステージ | 必要条件 | 使う場面 |
| :--- | :--- | :--- |
| `propose` | `Governance-Proposal: PRP-xxx` があり、提案が `pending_review` 以上。`bootstrap` はこのステージのみ `Governance-Proposal` 無しで許可 (インストール時の1回限り) | 機能ブランチでの変更 |
| `land` | 提案が**別セッションにより承認済み**。自分の提案は着地できない。**`bootstrap` も例外なく適用** — `may_use_governance_paths_without_proposal` は `land` では無効 | `main` へのマージ |

CI は通常 `propose` を検査し、`main` への push では `land` (`--stage land`) を検査する。`bootstrap` が `land` で無承認の governance 変更を着地させることは `check_governance_path` が拒否する (G1)。

---

## 5. よくある質問: モデルが毎回変わることは分離に使えるか

**結論: 部分的に yes。ただし「自然に分離される」とは言えない。**

| 効果 | 評価 |
| :--- | :--- |
| **コンテキストの独立** | ✅ **強い**。別チャットは提案者の推論履歴を持たない。リポジトリの状態から再導出するしかない。これは GitSwarm の Stateless 原則そのもので、提案者の暗黙の前提を落とす。 |
| **サンプリングの独立** | ✅ 期待できる。同じモデルでも別セッションなら別の生成。ただし相関は残る。 |
| **モデル系列の多様性** | ⚠️ **保証されない**。毎回同じ系列の可能性があり、自己申告も検証できない。 |
| **共通モード障害の除去** | ⚠️ **不十分**。全モデルが同じ論文を同じように読み違える可能性は残る。 |
| **同一性の証明** | ❌ **不可**。git author は全セッション共通。暗号学的な署名もない。 |

したがってハーネスは「モデルが違うこと」に頼らず、**記録とブランチで分離を強制する**。
モデルの多様性は「分離の品質を上げる追加要因」であって、分離の根拠ではない。

### 実際に防げるもの / 防げないもの

| 事象 | 防げるか |
| :--- | :--- |
| 同じチャットで提案・検証・承認を完結させる | ✅ R3 が拒否 |
| 提案者が自分の提案をレビューする | ✅ R3 |
| 検証者が validator / tests を書き換えて通す | ✅ R2 |
| ベンチマーク成果物を手書きして「実行した」と主張する | ⚠️ 実行ログと `--check` で検出。完全な防止は不可 |
| 別セッションを名乗る | ⚠️ R5 + ブランチ一意性で検出。ただし履歴改変までは防げない |
| 全モデル共通の誤読 | ❌ 外部の人間レビューが必要 |

**最終ゲートは `main` への人間のマージ**である。ハーネスは「気づける形にする」ものであって、
「悪意ある改変を暗号学的に防ぐ」ものではない。

---

## 6. 並行線路の照合手順（PRP-002 C6/A5）

並行する独立セッション線路 (例: `arena/eb670d1f` と `arena/f63b6887` が同一親から分岐し独自の REV-001/RQ-001/PRP-002 を発行) は `next_id` の衝突等で union マージ時に validator エラー (duplicate revision, supersedes mismatch) になるが `check-all` は `ok=true` のままである。照合は手動で行う:

```bash
# 線路B (例: arena/f63b6887) を線路A (arena/5491cb12) に照合
git fetch origin arena/f63b6887-researchos
git checkout arena/5491cb12-researchos
git merge --no-ff --no-commit origin/arena/f63b6887-researchos
python3 scripts/validate_researchos.py  # 失敗すれば
# 競合した ID は新しい revision で supersedes を正しい前行ハッシュに付け替え
# 両方の行を保持しつつ、重複 ID は手動で新 ID に採番し直す
git status  # state/*.jsonl の競合を手動解消
python3 scripts/validate_researchos.py --quiet && python3 scripts/researchos_guard.py check-all --stage propose
git commit -m "reconcile: merge parallel line B into A" # + Session-Id/Role trailers
```

* `next_id` は線路間で衝突する。ガバナンス ID (PRP-*, REV-*, APR-*, RQ-*) は並行線路では手動で一意な suffix を付与するか、将来の PRP-003 の UUID 方式を待つこと。
* 現行 `policy/state_baseline.json` の `files` 接頭辞検査は将来 PRP-003 で撤廃し、ハッシュ鎖のみに移行する。現時点では両方を検査する。

## 7. 運用手順（手動起動を前提）

### 6.1 セッションを終えるとき

```bash
python3 scripts/researchos_next.py --write
# → state/NEXT_SESSION.md に次セッション用プロンプトが生成される
git add state/NEXT_SESSION.md && git commit
```

### 6.2 次のチャットを開く（人間）

1. Arena.ai で新しいチャットを開始する。
2. `state/NEXT_SESSION.md` の内容をそのまま貼り付ける。
3. セッションは推奨ロールを claim し、キューを処理する。

### 6.3 3 セッションで 1 サイクル

```
[proposer]  提案 PRP-xxx + キュー RQ-xxx
    ↓
[verifier]  claim → researchos_verify.py → REV-xxx → complete
    ↓
[approver]  REV を読み APR-xxx を追記（提案者・検証者と別セッション）
    ↓
[人間]      main へマージ（land ゲート）
```

### 6.4 コマンド一覧

```bash
# セッション
python3 scripts/researchos_session.py claim --role verifier
python3 scripts/researchos_session.py list
python3 scripts/researchos_session.py close --session SES-xxxx

# キュー
python3 scripts/researchos_queue.py add --proposal PRP-xxx --session SES-xxxx
python3 scripts/researchos_queue.py list --status open
python3 scripts/researchos_queue.py claim --queue RQ-xxx --session SES-xxxx
python3 scripts/researchos_queue.py complete --queue RQ-xxx --review REV-xxx --session SES-xxxx

# 検証
python3 scripts/researchos_verify.py --proposal PRP-xxx --session SES-xxxx --write

# 監査
python3 scripts/researchos_guard.py check-all
python3 scripts/researchos_guard.py status
python3 scripts/validate_researchos.py

# 引き継ぎ
python3 scripts/researchos_next.py --write
```

---

## 7. 失敗時のリカバリ

| 症状 | 原因 | 対処 |
| :--- | :--- | :--- |
| `check-append-only` が失敗 | 過去の行を編集した | `git checkout` で戻し、訂正行を追記する |
| `check-authorship` が失敗 | レコードとコミットのセッションが不一致 | 正しいセッションで claim し直し、そのセッション名義でコミットする |
| `self-review` エラー | 提案者とレビュアーが同一 | 別チャットを開き、verifier を claim する |
| `governance path ... without a Governance-Proposal` | 提案なしでガバナンスを変更 | まず `PRP-*` を提案し、`Governance-Proposal` トレーラーを付ける |
| `cannot land your own proposal` | 提案者が着地しようとした | 承認者セッションに着地させる |
| キューの claim が通らない | セッションが verifier を持たない | `claim --role verifier` |

### ロールバック

`state/*.jsonl` は追記専用なので、**削除によるロールバックはしない**。
誤ったレコードは `revision` を上げて `status: rejected` や `deleted: true` を追記する。
コードのロールバックは通常の `git revert` を使い、そのコミットにも
`Session-Id` / `Session-Role` を付ける。

---

## 8. 残存リスク（正直な記載）

1. **ガードはリポジトリ内のコードである。** 書き込み権限を持つセッションはガード自体を弱められる。
   対策は「ガバナンスパスの変更に承認を要求する」ことと「main への人間のマージ」の 2 つだけ。
2. **同一性は暗号学的ではない。** 署名付きコミットや外部 ID プロバイダがないため、
   なりすましは「監査可能」だが「不可能」ではない。
3. **モデルの同一性は不明。** `declared_model` は自己申告。
4. **共通モード障害。** 異なるモデルでも同じ誤読をする可能性は残る。
   一次資料の逐語引用と再実行でしか対抗できない。
5. **起動は手動。** セッションが誰にも開かれなければ、キューは滞留する。
   `state/NEXT_SESSION.md` と CI のサマリが唯一の通知手段。

---

## 9. 設計判断の記録

| 判断 | 理由 |
| :--- | :--- |
| ブランチを同一性のアンカーにする | git author が全セッション共通で使えないため |
| `declared_model` を判定に使わない | 検証不能な自己申告をコンプライアンスに使わない |
| 訂正を追記で表現する | 監査時に「何がいつ変わったか」を消さないため |
| 承認を別レコードにする | 承認者が提案を書き換えると分離が崩れるため |
| `propose` / `land` を分ける | 機能ブランチでの試行を許しつつ、main では承認を必須にするため |
| bootstrap を 1 セッションに限定する | インストール時の抜け道を恒久化しないため |
| 起動だけ自動化しない | Arena.ai のチャットは人間が開く。そこを偽装すると監査不能になる |

---

*Policy version 1 — 2026-10-19。変更には `PRP-*` と別セッションのレビュー・承認が必要。*
