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
| `state/anchors.jsonl`（追記専用アンカー） | ✅ | ✅ | ✅ | ✅ |
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
| 承認の内容束縛 | **`review_line_sha256` が必須**（PRP-002 rev3 / C3・A2）。`approved` は参照する各レビューの正規化行ハッシュを `review_id → sha256` の map で持つ。欠落・一部欠落は error、不一致は常に error |
| 承認の効果 | **approval レジャーが正**。提案の `status` は書き換え不要 |

`review_line_sha256` を省略できた頃は、承認後にレビュー行を差し替えても束縛が残らなかった
（REV-003 §4 が fixture `APR-910` で再現）。規則自体は `schemas/approval.json` の `required` と
`validate_governance` の両方で強制し、**適用前の `APR-001` だけの免除を
`policy/roles.json` の `enforcement.approval_review_binding.grandfathered_approvals` に
データとして置く**（免除を広げるのもガバナンス変更）。免除された承認でも、ハッシュが存在すれば照合される。

### R4. 追記専用（PRP-002 rev3 で強化: ファイル全体のアンカー）

`state/*.jsonl` は行の追加のみ。既存行の編集・削除・並べ替えは `check-append-only` が拒否する。
訂正は同じ ID で新しい行を追記する:

```json
{"claim_id":"CLM-003", "...":"...", "revision":2, "supersedes":"<前の行の正規化JSONのsha256>"}
```

基準点は `policy/state_baseline.json`（`base_commit: 066b937`）。
それ以前の行は**祖父条項**で免除され、行ハッシュで識別される。

**なぜ rev2 の「ハッシュ鎖」では足りなかったか。** `supersedes` の鎖は *同一 ID の revision 間*
だけを繋ぐので、**最新行**（revision 1 の行、まだ supersede されていない行）はどこからも固定されない。
さらに `state/reviews.jsonl` は baseline 後に**空ファイル**として作られたため、接頭辞検査の対象行が
1 行も存在しなかった。結果として REV-003 §3 の 3 つの攻撃（REV-001 の書き換え・削除・追記済み行の
書き換え）がすべて `check-append-only` と `check-all --json` を通過した。

**rev3 は 4 層で検査する。** どの層も「行を追記するだけ」なら緑のまま、既存行の書き換え・削除だけを選ぶ。

| 層 | 検査 | 捕まえる改竄 |
| :--- | :--- | :--- |
| 1. baseline 接頭辞 | `base_commit`（無ければ作成コミット）時点の行が残っているか | baseline 以前からある行の書き換え |
| 2. **HEAD 接頭辞** | 作業ツリーが HEAD の行を全てそのまま保持しているか | **未コミット**の書き換え・削除 |
| 3. **コミット単位監査** | `base..HEAD` の各コミット（side branch 込み）が既存行を変更していないか。merge は「各親の行が全てそのまま・同じ順序で残る」ことを要求 | **コミット済み**の書き換え・削除（どのコミットが行ったかまで特定） |
| 4. **ファイル全体アンカー** | `state/anchors.jsonl` の各エントリが「先頭 N 行の rolling head」を固定し、それが現在のファイルと一致するか | アンカー済み行（**最新行を含む**）の書き換え・削除。履歴を辿れない場合でも検出 |

**rolling head** は生の各行を順番に SHA-256 で連結して得る 1 個のハッシュで、ファイル全体の
内容と順序に束縛される（`researchos_common.rolling_head` / `prefix_heads`）。空ファイルは
`GENESIS_HASH = 0×64`。アンカー 1 エントリ = 「このファイルの先頭 N 行の head はこれ」という事実で、
次のフィールドを持つ:

```json
{"anchor_id":"ANC-<16hex>","file":"state/reviews.jsonl","lines":2,
 "head_sha256":"<先頭2行のrolling head>","prev_head_sha256":"<直前アンカーのhead>",
 "prev_lines":1,"prev_anchor_head_sha256":"<この行より前の anchors.jsonl 全体のhead>",
 "prev_anchor_lines":7,"session_id":"SES-xxxx","created_at":"..."}
```

* `head_sha256` / `lines` — 台帳の接頭辞の固定（**全エントリを現在のファイルと照合**するので、
  古いエントリほど強い制約になる）。
* `prev_head_sha256` / `prev_lines` — 同じ台帳のアンカー鎖。
* `prev_anchor_head_sha256` / `prev_anchor_lines` — **アンカー台帳自身の自己鎖**。
  過去のアンカー行を 1 行書き換えると、それ以降のエントリがこの値で不一致になる。
* 最新エントリは台帳の現在の行数・head と一致しなければならない（**tip pin**）。
  追記したらアンカーも更新する、が規則。

**改竄後にアンカーを更新しても隠せない。** 追記された新エントリは検査を通っても、
古いエントリが「先頭 N 行の head」を固定し続けているため、書き換えた行がその N 行に含まれる限り
不一致が残る（`tests/test_append_only_tamper.py::test_re_anchoring_does_not_hide_a_rewrite`）。

運用:

```bash
python3 scripts/researchos_anchor.py verify    # 全台帳が pin されているか（exit 1 = 未 pin / 破損）
python3 scripts/researchos_anchor.py update    # 追記した台帳の tip を pin（追記のみ、幂等）
python3 scripts/researchos_anchor.py list
python3 scripts/researchos_guard.py check-anchors --json
```

`append_jsonl()` は対象が本リポジトリの被アンカー台帳なら**自動的に pin を更新する**ので、
`researchos_session.py` / `researchos_queue.py` / `researchos_verify.py` 経由の追記で
アンカーが古くなることはない。手で追記した場合だけ `update` が必要で、忘れると
`check-append-only` がコマンド名つきのエラーで止まる。

**アンカーの authorship:** `state/anchors.jsonl` の各行も R5 の対象なので、pin の書き換えには
そのセッションを名乗るコミットが必要になる。

静的 baseline（層 1）は後方互換のために残す。段階的な撤廃は PRP-003 の検討事項。

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

# 追記専用アンカー（PRP-002 rev3）
python3 scripts/researchos_anchor.py verify
python3 scripts/researchos_anchor.py update   # 手で state/*.jsonl に追記したあと
python3 scripts/researchos_anchor.py list

# 監査
python3 scripts/researchos_guard.py check-all --json
python3 scripts/researchos_guard.py check-append-only --json
python3 scripts/researchos_guard.py check-anchors --json
python3 scripts/researchos_guard.py status
python3 scripts/validate_researchos.py

# 引き継ぎ
python3 scripts/researchos_next.py --write
```

---

## 7. 失敗時のリカバリ

| 症状 | 原因 | 対処 |
| :--- | :--- | :--- |
| `check-append-only` が失敗（`against HEAD` / `was modified`） | 過去の行を編集・削除した | `git checkout` で戻し、訂正行を追記する |
| `anchor is stale` / `not anchored` | 追記後にアンカーを更新していない | `python3 scripts/researchos_anchor.py update` を実行してコミットする |
| `anchor ... pins N lines ... but they now roll up to ...` | アンカー済みの行が書き換わっている | 書き換えを取り消し、訂正は新しい行として追記する（アンカー更新では隠せない） |
| `prev_anchor_head_sha256 does not match` | `state/anchors.jsonl` の過去の行が書き換わっている | 同上。アンカー台帳も追記専用 |
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
6. **アンカーの根は Git 履歴にある。** `state/anchors.jsonl` の**最終行**だけは、それ以降の
   エントリが存在しないため自己鎖で固定できない。層 2（HEAD 接頭辞）と層 3（コミット単位監査）が
   その書き換えを捕まえるが、**履歴そのものを書き換える**攻撃（`git filter-branch` 等）は
   リポジトリ内のコードでは防げない。最終ゲートが `main` への人間のマージである理由はこれである。
   署名付きコミットや外部アンカー（例: 承認記録への head 固定）は PRP-003 以降の検討事項。
7. **アンカーは「追記専用であること」を証明するが、「内容が正しいこと」は証明しない。**
   誤った内容の行を追記し、そのまま pin することはできる。内容の妥当性は独立レビューの役割。

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
| 追記専用を 4 層（baseline / HEAD / コミット単位 / ファイル全体アンカー）で検査する | どの 1 層にも単独では抜け道があった（REV-003 §3）。層を増やすほど「緑の意味」が強くなる |
| アンカーを `policy/` ではなく `state/anchors.jsonl` に置く | pin は追記ごとに更新される事実であり、全ロールが追記でき、かつ追記専用と authorship (R5) の対象になる必要がある。`policy/**` だと verifier が pin を更新できない |
| アンカー ID を内容から導出する | 並行線路が同じ tip を pin しても union マージで衝突しない（A5 の緩和） |

---

*Policy version 1 — 2026-10-19。変更には `PRP-*` と別セッションのレビュー・承認が必要。*
