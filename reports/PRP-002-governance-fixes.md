# PRP-002 ガバナンス・ハーネス強化 — F1〜F4・A1〜A8・G1〜G4・V1〜V13 の是正

- 作成日: 2026-10-19
- 作成セッション: `SES-5491cb12` / proposer / `arena/5491cb12-researchos`（revision 1・2）
- **rework: `SES-86da9dab` / proposer / `arena/86da9dab-researchos`（revision 3 = revision 2 の rework、2026-10-19）**
- rework の根拠: `REV-003`（fail、`SES-f99f5b7f`、`verifications/prp002_verifier_f99f5b7f.md`）の §9 推奨 2・3・4・5・6・7
- rework のスコープ: ①ファイル全体の append-only アンカー（C2/A1）②実改竄テスト ③`review_line_sha256` の必須化（C3/A2）④§14 コマンドの整合
- 対象: PRP-001 承認レビュー `REV-001` (SES-eb670d1f, pass条件付き) および承認ラウンド `APR-001` (SES-955f8586, 条件付き承認 C1〜C6) で指摘された全ギャップ
- 提案ID: `PRP-002`（未使用、連番）
- ベース: `policy/state_baseline.json` base_commit `066b937454263aa6685f2bf7869124698829d3f9`、直前コミット `6b22092` (SES-5491cb12 claim)
- 先行系統: `arena/c4426c6b → eb670d1f → 955f8586` (線路A) と `arena/e7ac466a → 47c55a23 → e09f19e4 → f63b6887` (線路B) の設計文書を統合し、実装を伴った改訂として再提案する

> **本ドキュメントは提案の根拠であり、保護対象 (scripts/, schemas/, policy/, tests/, .github/) の実装変更は本提案に紐づくコミットで提供する。** Proposer は `Governance-Proposal: PRP-002` トレーラー付きで `propose` ステージの変更が許可され、承認後に `land` ゲートを通過する。

---

## 0. 要約 — なぜ PRP-001 のまま main に land できないか

PRP-001 の標準8検査は PASS だが、否定ケースは未検査だった：

| 原因 | 結果 | 影響 |
|---|---|---|
| F1: Session-Id は自己申告、ブランチ束縛は HEAD のみ | 他人セッション詐称コミット + guard 自身の無効化が `check-all ok=true` | R2/R6 迂回 |
| F2: merge コミットは `is_merge` で skip、`--first-parent` で side-branch 不可視 | トレーラー無しで `.github/workflows` 改変を `--no-ff` で着地 → `ok=true` | R2/R6 迂回 |
| F3: CI の land ゲート `check-commits --stage land` が CLI 引数として存在せず exit 2 | 初の main push で CI が赤、かつ一度も実行されていない (gh run list --branch main 空) | R6 が未テスト |
| F4: `researchos_session.py close` が自セッションで `session is closed` エラー | ドキュメント記載の終了コマンドが自らを壊す | 運用不能 |
| A1: `state_baseline.json` 前方一致のみで `reviews.jsonl` 等の追記行は無保護 | REV-001 summary 書き換えが `ok=true` / validator exit 0 | R4 形骸化 |
| A2: 承認が `review_ids` のみ参照、内容を束縛しない | レビュー事後差し替えが全緑のまま | R3 形骸化 |
| A3: HEAD 限定が正規継承で偽陽性 (`git merge` 直後1コミット前で `check-all` FAIL) | 手順通りに進めると赤になる | 運用摩擦 |
| A5: 並行線路の照合不能 (eb670d1f + f63b6887 union で validator 7エラー / guard ok=true) | 別線路の PRP-002/Revs が衝突 (`next_id` 衝突) | 分岐運用不能 |
| A7: `test_bootstrap_proposal_cannot_be_self_closed` が「承認が無い」ことを検査 | APR-001 (別セッション承認) で恒久的に赤 | CI が手続き通り承認を記録した瞬間に赤 |
| A8: 1件の赤テストで job 全体が短絡 → benchmark/guard/land が未実行 | 欠陥があっても land ゲートがスキップされる | CI 構造欠陥 |
| G1-G4: e7ac466a 線路の否定プローブ 4件全 fail (bootstrap land迂回, merge未監査, 承認整合性欠落, ID衝突) | 同上 | 実害あり |

本提案はこれらを**1つの実装ラウンド**で閉じ、設計整合プローブ V1-V13 も同時に解消する。

---

## 1. 設計方針 — 「信用せず、回してから直す」

- 各欠陥は**使い捨てクローンでの再現**を前提に設計した (前セッションの監査手法を踏襲)
- 修正は「HEAD だけを見る」→「ブランチで導入したコミット範囲を見る」に転換
- 静的 baseline 接頭辞 → **行ごとのローリングハッシュ鎖** (各 revision の `supersedes` が前行の canonical hash)
- 承認は ID ではなく**内容ハッシュ**を束縛
- CI は `propose` と `land` を分離し、赤テストが land ゲートを潰さない

---

## 2. C2/A1 — 追記専用: ファイル全体のアンカー（revision 3 で作り直し）

### revision 2 までの設計が失敗した理由（REV-003 §3 で実証された）

revision 1・2 は「`revision` と `supersedes` によるローリングハッシュ鎖」を追記専用の強化とした。
実装もそのとおりだったが、**鎖が同一 ID の revision 間しか繋がっていない**ため、次の 3 つが
すべて `check-append-only` exit 0 / `check-all --json` `ok=true` になった:

1. `state/reviews.jsonl` の `REV-001` の `summary` をその場で書き換え（未コミット）
2. `REV-001` の行を削除（未コミット）
3. 追記して**コミットした** `REV-9001` 行を書き換え

根因は 2 つ。(a) 最新行（revision 1 の行、まだ supersede されていない行）を固定する仕組みが無い。
(b) `state/reviews.jsonl` は `e236b57` で**空ファイル**として作られたため、接頭辞検査の基準が空で、
全行が無保護だった。加えて rev2 で追加した `test_append_only_hash_chain_is_enforced` は
改竄を一切行わず、きれいなファイルを `resolve_effective` に通すだけだったので改竄済みツリーでも PASS した
（REV-003 §3.4）。

### revision 3 の設計 — 4 層

`check-append-only` は次の 4 層を検査する。いずれも「行の追記だけ」なら緑を保ち、
**既存行の書き換え・削除**だけを拒否する。

| 層 | 実装 | 捕まえるもの |
| :--- | :--- | :--- |
| 1. baseline 接頭辞 | `prefix_violations(rel, historical, current)`（既存、後方互換のため維持） | baseline 以前からある行 |
| 2. **HEAD 接頭辞** | `check_working_tree_against_head()` — 作業ツリー vs `HEAD` | **未コミット**の書き換え・削除（攻撃 1・2） |
| 3. **コミット単位監査** | `check_state_history()` — `base..HEAD` の各コミット（side branch 込み）で既存行が不変か。1 回の `git cat-file --batch` で全 blob を読む。merge は `subsequence_violations()`（各親の行が全て・同じ順序で残ること）を要求 | **コミット済み**の書き換え・削除（攻撃 3）。どのコミットが行ったか short SHA 付きで報告 |
| 4. **ファイル全体アンカー** | `state/anchors.jsonl` + `researchos_common.anchor_errors()` | アンカー済み行（**最新行を含む**）の書き換え・削除。履歴を辿れない場合でも検出 |

**rolling head**（`researchos_common.rolling_head` / `prefix_heads`）は生の各行を順に SHA-256 で
連結した 1 個のハッシュで、ファイル全体の内容と順序に束縛される。空は `GENESIS_HASH = 0×64`。
アンカー 1 エントリは「この台帳の先頭 N 行の head はこれ」という**事実**であり、
`prev_head_sha256` / `prev_lines` で同じ台帳のアンカー鎖を、
`prev_anchor_head_sha256` / `prev_anchor_lines` で**アンカー台帳自身の自己鎖**を作る。

検証は 3 性質:

1. **self-chain** — エントリ *i* は *i-1* までのアンカー台帳を固定する。過去のアンカー行を
   書き換えると以降のエントリが不一致になる。
2. **prefix pin** — 全エントリについて「現在のファイルの先頭 `lines` 行の rolling head == `head_sha256`」。
   アンカー済みの行を 1 行でも書き換えると、それ以降の**すべての**エントリが不一致になる。
3. **tip pin** — 台帳ごとの最新エントリが現在の行数・head と一致すること（= 最新行が固定される）。
   不一致は「`researchos_anchor.py update` を実行してコミットせよ」というエラーになる。

**改竄後にアンカーを更新しても隠せない。** 新エントリは通っても、古いエントリが元の接頭辞を
固定し続けるため層 4 の性質 2 が失敗し続ける（テスト
`test_re_anchoring_does_not_hide_a_rewrite` / probe `R1.3`）。

`append_jsonl()` は被アンカー台帳への追記時に **pin を自動更新**するので、
`researchos_session.py` / `researchos_queue.py` / `researchos_verify.py` の通常フローで
アンカーが古くなることはない。手書きの追記だけが `update` を必要とする。

### なぜ `prev_line_sha256` を各行に持たせないのか

REV-003 §3.5 の修正案 2 は「各行に直前行ハッシュを持たせ、末尾 head を外部アンカーに固定する」だった。
rev3 は**同じ保証をファイル単位の rolling head で実現**する。各行へのフィールド追加は
10 台帳すべてのスキーマと既存行（ grandfathered ）の書き換えを要求し、fixture も壊す。
rolling head なら 1 個のハッシュが全行を固定でき、既存行は無変更で済む。
代わりにアンカー台帳 `state/anchors.jsonl` を**外部アンカー**として使い、
そこへの書き込みを R2（パス権限）・R4（追記専用）・R5（authorship）の対象にする。

### 受入条件（rev3）

* `python3 scripts/researchos_guard.py check-append-only` が上記 3 攻撃のそれぞれで **exit 1**
* `python3 scripts/researchos_guard.py check-all --json` が **`ok=false`**
* `python3 scripts/researchos_anchor.py verify` が改竄ツリーで **exit 1**、クリーンツリーで **exit 0**
* 正当な追記（`append_jsonl` → 自動 pin → コミット）は **exit 0** のまま
* 実行可能な証跡: `tests/test_append_only_tamper.py`（20 tests）と
  `verifications/prp002_rev2_acceptance_probes.py --only R1`

---

## 3. C3/A2 — 承認とレビュー内容の束縛（revision 3 で必須化）

### 現象

`schemas/approval.json` は `review_ids` のみ必須で、`validate_governance` は
`expected_hashes = approval.get(...)` が truthy のときだけ照合していた。つまり**省略すれば検査されない**。
REV-003 §4 は fixture `APR-910`（`review_line_sha256` なし）で `validate_researchos.py --quiet` が
exit 0 になることを実測した。A1（§2）が未修正だったため、承認後のレビュー差し替えを防ぐ錠が
実質的に存在しなかった。

### revision 3 の修正（必須化）

1. `schemas/approval.json` の **`required` に `review_line_sha256` を追加**（`review_id → sha256` の map）。
2. `validate_governance`:
   * `decision == "approved"` で束縛が**無い** → error
   * map に**参照レビューのエントリが無い** → error
   * `review_sha256`（単一文字列）で 2 件以上のレビューを参照 → error（map を要求）
   * ハッシュ**不一致** → 常に error
   * `decision == "rejected"` は束縛を要求しない
3. **祖父条項はデータとして置く**: `policy/roles.json` の
   `enforcement.approval_review_binding.grandfathered_approvals = ["APR-001"]`。
   列挙された承認だけは「束縛が無い」場合 error ではなく warning に降格する
   （スキーマ `required` のエラーも同様に降格）。**ハッシュが存在すれば不一致は常に error**。
   免除を広げるには `policy/roles.json` の変更 = ガバナンス変更（承認が必要）になる。
4. `APR-001` は既に `review_line_sha256 = {"REV-001": "d1bf998f..."}` を持つため、
   実データはそのまま緑（`validate_researchos.py --quiet` exit 0）。

### 受入条件（rev3）

* 束縛の無い `approved` を追加した一時リポジトリで `validate_researchos.py --quiet` が **exit 1**
* 正しい束縛を付けた同一 fixture が **exit 0**（= 検証器が「常に赤」で合格しないことの対照）
* `schemas/approval.json` の `required` に `review_line_sha256` が入っている
* 実行可能な証跡: `researchos_verify.check_approval_binding()`（15 checks の 1 つ）、
  `tests/test_governance.py::ApprovalBindingTest`（9 tests）、probe `--only R3`

---

## 4. C4/F1・F2/A3 — セッション束縛と merge 監査

### 4.1 F1/A3: Session-Id 詐称と HEAD 限定の是正

**現状:**
```python
if sha == head and session.get("branch") != branch:
    errors.append(...)
```
HEAD のみ検査 → 非HEAD で他人名義のコミットを埋め込める (guard 自身を無効化して `ok=true` を実証)。逆に正規の `git merge --ff` 直後は HEAD が他人のコミットになり偽陽性。

**修正:**
- `check_commits` のブランチ束縛を **「このブランチで導入したコミット範囲」** に変更
- 実装: 現在セッションの `first_commit` を取得し、`git merge-base --is-ancestor ancestor descendant` で判定
  - `sha` が `first_commit` の祖先 → 継承された履歴 (他ブランチ由来) → branch 不一致を許容
  - `sha` が `first_commit` の子孫 → 本ブランチで新規に導入 → `session.branch == current_branch` を必須
- 祖先判定が例外 (synthetic sha) の場合は保守的にエラー (enforced=true 側に倒す)

```python
current_session = find_session(sessions, current_session_id) # claim 直後の effective から
first_commit = current_session.get("first_commit")
for sha in commits_including_merges:
    session = _find_session(sessions_at(sha), session_id)
    if session.branch != branch:
        if first_commit and is_ancestor(first_commit, sha):
            continue # inherited, ok
        if not is_ancestor(sha, first_commit): # new commit on this branch
            errors.append(f"{short}: forged session ...")
```

- `researchos_common.py` に `is_ancestor(ancestor, descendant)` helper を追加 (git merge-base --is-ancestor, 例外は RuntimeError → None)

### 4.2 F2/G2: merge コミットの監査

**現状:**
```python
if is_merge(sha):
    continue
commits = commits_in_range(base, first_parent=True)
```
`--first-parent` で side-branch 不可視 + merge 自体のトレーラー/path 未検査。

**修正:**
1. `is_merge` 判定を外し、**merge コミット自体のトレーラー・パス・承認を検査**:
   ```python
   trailers = commit_trailers(sha)
   paths = commit_paths(sha) # merge commit 自体の差分 (first-parent との差分が governance なら検出)
   # synthetic sha では git が例外 → enforced 扱いで error
   ```
2. **second-parent 側のコミット列挙**:
   ```python
   parents = git("rev-list", "--parents", "-n", "1", sha).split()
   # parents[0]=sha, parents[1]=first_parent, parents[2:]=other_parents
   for other in parents[2:]:
       try:
           side_commits = git("rev-list", "--reverse", f"{base}..{other}", f"^{parents[1]}")
           for side_sha in side_commits:
               # side_sha についても trailers/paths/governance 検査
       except RuntimeError:
           errors.append(f"{short}: cannot enumerate side branch of merge")
   ```
3. `researchos_common.py` に `commit_parents(sha)` helper を追加、例外時は `None`
4. `check_governance_path` は merge 経由でも `stage` に応じて承認を要求

**合成 SHA 耐性 (V6/V7):** モックや合成 SHA では `git` が exit 1 → `RuntimeError` → `enforced=false` ではなく error として報告 (fail-open しない)。

### 受入条件
- `verifications/prp001_governance_probes.py` の `merge_commits_are_audited` が `enforced=true` (`trailers_inspected` と `paths_inspected` 共に true)
- 実リポジトリでの再現: `.github/workflows` を side branch でトレーラー無し改変 → `--no-ff` merge → `check-commits` が FAIL
- 正規の fast-forward 継承 (`git merge origin/eb670d1f`) は `check-all` PASS (A3 解消)

---

## 5. G1 — bootstrap land 時の迂回防止

### 現象
```python
if spec.get("may_use_governance_paths_without_proposal"):
    return []
```
`stage` を見ずに早期 return → `land` でも `proposal=None` + `approved_ids={}` で PASS。

### 修正
```python
if spec.get("may_use_governance_paths_without_proposal"):
    if stage == "land":
        pass # land では例外を適用しない — 下の承認検査に落とす
    else:
        return []
```
- `policy/roles.json` の `bootstrap` 説明に「land 時は独立承認必須」を追記
- `docs/GOVERNANCE.md` R6 の bootstrap 行を「インストール時1回のみ、かつ land 時は承認必須」に更新
- `tests/test_governance.py` の `test_bootstrap_is_exempt` を `test_bootstrap_may_propose_without_proposal` に改名し、 `land` では FAIL を期待する `test_bootstrap_land_requires_approval` を追加

### 受入条件
- `check_governance_path("bootstrap", ..., None, ..., "land")` が非空エラー
- `check_governance_path("bootstrap", ..., approved_proposal, other_session, "land")` が PASS
- プローブ `bootstrap_land_requires_independent_approval` が `enforced=true`

---

## 6. G3 — 承認整合性と required_checks

### 現象
`validate_governance` が `review.result == "pass"` のみを見て `checks` の個別 fail や `required_checks` の欠落を無視。`required_checks` 自体も参照しない。

### 修正
`scripts/validate_researchos.py::validate_governance` に追加:
1. **集約整合性:** `review.result == "pass"` なら `checks` に `fail` があってはならない。あれば error。`checks` が空も error。`result == "partial"` は `skip`/`warn` が1件以上かつ `fail` 無しのみ許容 (V13)。
2. **required_checks 束縛:** queue の `required_checks` (authority) が `review.checks[].name` の pass 集合に含まれない場合は error。`governance_review` を含む 12 項目を正規名称とする (V9)。
3. **承認の前提:** `approval.decision == "approved"` は上記を満たす passing review を最低1件参照しなければ error。
4. 空 `checks` と `partial` の規則を明示 (V13)。

### 受入条件
- プローブ `approval_rejects_failed_or_missing_required_checks` が `enforced=true`
- 新テスト `test_pass_review_with_failing_check_is_rejected` / `test_missing_required_check_is_rejected` が PASS
- 矛盾する review/approval を含む一時リポジトリで `validate_researchos.py` が exit 1

---

## 7. G4 — 複数レビューの distinct 保持

### 現象
`researchos_queue.py:_load` と `researchos_verify.py:_sessions/_proposal/existing` が `resolve_effective(... )` に `id_key` を渡さず、`ID_KEYS` 順序で `session_id` が勝つ。同一 verifier の REV-001/002 が `duplicate revision 1` 誤判定 → `queue complete` CLI が失敗。

### 修正
- `scripts/researchos_queue.py::_load` を `load_effective(name)` に統一 (`COLLECTION_ID_KEYS` 自動適用)
- `scripts/researchos_verify.py` の `_sessions()`, `_proposal()`, `existing` の `resolve_effective` 呼び出しに `COLLECTION_ID_KEYS["sessions"]` / `["proposals"]` / `["reviews"]` を明示
- `scripts/researchos_session.py::effective_sessions()` も `resolve_effective(records, "session_id")`
- `scripts/researchos_next.py::_effective` も `load_effective` に統一
- `researchos_common.py` の docstring で `COLLECTION_ID_KEYS` 利用を強調、必要に応じ `merge_diff_paths` helper を追加 (V6 補助)

### 受入条件
- プローブ `multiple_reviews_from_one_session_remain_distinct` が `enforced=true` (untyped_errors 空)
- 実 CLI: 同一 verifier で REV-001/002 を追記後に `researchos_queue.py complete --queue RQ-001 --review REV-002` が成功
- 新テスト `test_multiple_reviews_from_one_session_remain_distinct` が PASS

---

## 8. C6/A5 — 並行線路の照合手順

### 現象
`eb670d1f` と `f63b6887` の union merge で validator 7エラー (duplicate revision, supersedes mismatch) だが `check-all ok=true`。`next_id` が線路間で衝突。

### 設計 (本提案は「手順」を定義し、完全な自動解消は PRP-003 以降に委譲)
1. **ID の衝突回避:** `next_id` は線路間で衝突する。暫定策として `PRP-002` 以降の新規 ID は `SES-xxx` 接尾辞を推奨するか、UUID を検討。少なくとも `researchos_common.py::next_id` のコメントに「並行線路では手動で ID を採番し `duplicate revision` を避けること」を明記。本セッションは `RQ-002` を新規発行し、既存 `RQ-001` (completed) とは別 ID で衝突しない。
2. **照合手順 (docs/GOVERNANCE.md §7 に追記):**
   ```bash
   # 線路Bを線路Aに照合する (例: f63b6887 → 5491cb12)
   git fetch origin arena/f63b6887-researchos
   git checkout arena/5491cb12-researchos
   git merge --no-ff --no-commit origin/arena/f63b6887-researchos
   python3 scripts/validate_researchos.py  # 失敗すれば手動で supersedes を再計算
   # 競合した ID は新しい revision で supersedes を正しい前行ハッシュに付け替え
   git checkout --ours ... # ではなく、両方の行を保持しつつ revision を上げ直す
   ```
3. **静的 baseline の廃止方向:** 将来の PRP-003 で `policy/state_baseline.json` の `files` 接頭辞検査を撤廃し、ハッシュ鎖のみに移行 (本 PRP-002 では guard にハッシュ鎖を追加するが baseline は維持して段階移行)。

### 受入条件
- `docs/GOVERNANCE.md` に照合手順が記載される
- `state/review_queue.jsonl` に `RQ-002` (open) が存在し、`RQ-001` と衝突しない
- `validate_researchos.py` が現行線路で PASS (線路Bとの union は別途検証、今回はスコープ外だが手順は文書化)

---

## 9. F3/F4 — CLI と close の修正

### F3: `--stage` CLI 引数が存在しない
- `scripts/researchos_guard.py` の `check-commits` と `check-all` パーサーに `--stage` (choices: propose, land, default: propose) を追加
- `main()` で `getattr(args, "stage", "propose")` を確実に渡す
- `.github/workflows/verify-github-actions.yml` の land ゲートを:
  ```yaml
  - name: ガバナンス着地ゲート（main のみ）
    if: github.ref_name == 'main'
    run: |
      python3 scripts/researchos_guard.py check-commits --branch main --stage land --json
      python3 scripts/researchos_guard.py check-all --branch main --stage land --json
  ```
  に修正し、`set -euo pipefail` 下で exit 2 にならないことを確認
- `check-commits --stage land` が存在しない引数で exit 2 になる問題を解消

### F4: `close` が自らを壊す
- `check_commits` で `session.status == "closed"` のとき、親コミットの session 状態を参照:
  ```python
  if session.get("status") == "closed":
      parent = git("rev-parse", f"{sha}^", check=False)
      if parent:
          parent_sessions, _ = _sessions_at(parent)
          parent_session = _find_session(parent_sessions, session_id)
          if parent_session and parent_session.get("status") != "closed":
              continue # this commit is the close commit itself, allow
      errors.append(...)
  ```
- `researchos_session.py` のドキュメントに「close コミットは例外的に許容される」を追記

### rev3 追記: `--json` を全サブコマンドへ

REV-003 §5 は `check-commits --stage propose --json` が **exit 2**（argparse に `--json` が無い）で、
§14 が exit 2 を明示的に禁止している以上 DoD 不成立だと指摘した。rev3 では
`check-policy` / `check-append-only` / `check-commits` / `check-authorship` / `check-all` の
**すべて**が `--json` を受け、`check-anchors` を新設した。exit code は 0 = pass / 1 = fail のみで、
文書化されたコマンドが 2 を返すことはない。

### 受入条件
- `python3 scripts/researchos_guard.py check-commits --stage land --json` が exit 2 ではなく 0 or 1
- 全サブコマンドで `--json` が通り、JSON に `ok` と `results` が入る
- `researchos_session.py close --session <self>` 直後の `check-commits` が PASS

---

## 10. A7 — テストの不変条件修正

**旧:** `assertFalse(any(a[proposal_id]==PRP-001))` — 「承認が存在してはいけない」
**新:** 「提案者による承認が無い」かつ「第3セッションによる承認は成功」を検査:
```python
def test_bootstrap_proposal_cannot_be_self_closed(self):
    proposals = {p[proposal_id]: p for p in proposals}
    assert proposals["PRP-001"][session_id] == "SES-c4426c6b"
    approvals = load_jsonl(approvals)
    self.assertFalse(any(a[proposal_id]==PRP-001 and a[session_id]==SES-c4426c6b for a in approvals),
        "proposer must not self-approve")
    # 新: レビュアーによる承認も拒否
    self.assertTrue(any(a[proposal_id]==PRP-001 for a in approvals),
        "a third session should have approved PRP-001") # APR-001 exists
    # 対偶テストを別メソッドで追加
def test_reviewer_cannot_approve(self): ...
def test_third_session_can_approve(self): ...
```

本 PRP-002 では既存テストを上記に書き換え、APR-001 が存在しても PASS するようにする。
CI の `unittest discover` が 49→52 tests で全 PASS になることを確認 (新テスト 3件追加)。

---

## 11. A8 — CI の短絡防止

**旧:** `verify` job の `ResearchOS 回帰テスト` が失敗すると `set -euo pipefail` で job 全体が short-circuit し、 benchmark/guard/land がスキップされる (A8: 4 steps skipped, 1 failed)。

**修正:** `verify-github-actions.yml` の `verify` job を 2 jobs に分割するか、`continue-on-error` + 集約 verdict を使う:
```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python3 scripts/validate_researchos.py
      - run: python3 -m unittest discover -s tests -v
      - run: python3 gitswarm/benchmarks/benchmark.py --check
  guard:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: {fetch-depth: 0}
      - run: python3 scripts/researchos_guard.py check-all --stage propose --json
      - if: github.ref_name == 'main'
        run: python3 scripts/researchos_guard.py check-all --stage land --json
```

少なくとも「land ゲートは test 失敗時でも実行される」構造にする。`negative-test.yml` は分離済みなので維持。

### 受入条件
- CI の `guard` job が `test` job の失敗後も実行される (または fail-fast しない)
- `main` への push で land ゲートが実行されることを手動で `gh run list --branch main` が空でないことで将来検証 (今回は設計のみ)

---

## 12. V1-V13 — 設計整合プローブの対応

`arena/f63b6887` 線路の `reports/verification-PRP-002.md` で指摘された 13 件を本実装で解消:

| V | 内容 | 対応 |
|---|---|---|
| V1 | `--stage` CLI 欠落 | F3 で解消 |
| V2 | G4 受入条件の二重基準 (probe vs 実 CLI) | G4 で一本化: `load_effective` 統一で両方 PASS |
| V3 | approval vs queue completed の規則混同 | G3 で分離: approval は review の `result/checks` を見、queue は `required_checks` を見る。`completed` は review_id の存在のみを要求 (G3 前半と後半を分離) |
| V4 | typed resolution の徹底 | G4 で解消: 全 collection で `COLLECTION_ID_KEYS` 明示 |
| V5 | スコープ整合 (changes パス一覧) | 本提案の `changes` に `scripts/researchos_session.py`, `scripts/researchos_next.py` を含める (V5) |
| V6 | merge 監査の制御フロー (early continue で path 未検査) | F2 で解消: merge でも `trailers_inspected` と `paths_inspected` を両方実行し、結果を累積 |
| V7 | synthetic sha 例外耐性 | F2 で解消: `git` 例外を `RuntimeError` で捕捉し error として報告 (クラッシュしない) |
| V8 | テスト fixture と実ポリシー不一致 (`may_write_governance_with_proposal` 欠落) | `tests/test_governance.py` の `spec_bootstrap` に実ポリシー通りのフラグを付与 |
| V9 | required_checks 名の表記揺れ | 12 項目に統一: `governance_review`, `schema_and_integrity`, `regression_tests`, `benchmark_reproducible`, `readout_snapshot`, `append_only`, `role_guard`, `role_separation`, `bootstrap_land_requires_approval`, `merge_commits_are_audited`, `approval_consistency`, `distinct_reviews` |
| V10 | `researchos_verify.py` へのガバナンスプローブ統合 | `build_checks` に 4 プローブを統合: `bootstrap_land_requires_approval` etc. を自動 check として追加 (12 checks になる) |
| V11 | `researchos_next.py` の動的導出と rework 対応 | `decide_role` に「最新レビューが fail なら proposer を推奨」ロジック追加、ID ハードコード撤廃 |
| V12 | DoD の時点独立化 | §13 の不変条件として再定義 (特定の RQ-xxx open に依存しない) |
| V13 | 空 checks / partial 規則の明確化 | G3 で解消: `checks` 空は error, `partial` は `fail` 無しかつ `skip`/`warn` 有りのみ許容 |

---

## 13. 変更対象一覧（propose ステージで実装済み — revision 3 の差分は **太字**）

| ファイル | 対応ID | 変更内容 |
|---|---|---|
| `scripts/researchos_common.py` | C4/F1, G2, G4, **C2/A1** | `is_ancestor` / `commit_parents` helper, `COLLECTION_ID_KEYS` 強調, `next_id` 衝突警告。**(rev3)** `rolling_head` / `prefix_heads` / `head_at` / `ledger_lines` / `file_head`, アンカー台帳 (`anchored_ledgers`, `build_anchor_updates`, `record_anchor`, `anchor_errors`), `git_show_many`（`git cat-file --batch`）, `append_jsonl` の自動 pin（著者は record の `session_id` → `created_by_session` → `claimed_by_session` → ブランチ名の順で解決。`state/review_queue.jsonl` の行は `session_id` を持たないため、これが無いと `unknown` で pin されて `check-authorship` が赤になる）, `session_from_branch` / `record_session_hint`（自動 pin の著者帰属。`state/review_queue.jsonl` の行は `session_id` を持たない）, `current_branch` の unborn-branch フォールバック（`git symbolic-ref --short HEAD`）, `resolve_effective(..., allow_identical_duplicates=)`, `STATE_FILES`/`COLLECTION_ID_KEYS` に `anchors` 追加 |
| `scripts/researchos_guard.py` | C2/A1, C4/F1+F2, G1, F3, F4, C6, **§14** | bootstrap land 例外の除去, merge 監査, branch 束縛是正, close 例外, `--stage`。**(rev3)** `check_working_tree_against_head`（層2）, `check_state_history` + `_state_commit_log` + `subsequence_violations`（層3）, `check_append_only` への `anchor_errors` 統合（層4）, `check-anchors` サブコマンド, **全サブコマンドへの `--json`**, `RECORD_FILES` に `state/anchors.jsonl` |
| **`scripts/researchos_anchor.py`（新規）** | **C2/A1** | **`update` / `list` / `verify`。tip pin の生成と検証。ブランチ名から session を導出** |
| `scripts/validate_researchos.py` | G3, C3/A2, C6 | 集約整合性・required_checks・`review_line_sha256` 照合。**(rev3)** 束縛の**必須化**（欠落/一部欠落/単一文字列 = error、不一致 = 常に error）、`grandfathered_approvals()`、`anchor_errors()` の統合、`anchors` のスキーマ/一意性配線（同一行の重複は幂等） |
| `scripts/researchos_queue.py` | G4 | `_load` を `load_effective` に統一 |
| `scripts/researchos_verify.py` | G4, V10, **C2/A1・C3/A2** | id_key 明示, 4 ガバナンスプローブ統合。**(rev3)** 敵対的チェック 2 つを追加 → **15 checks**: `append_only_adversarial`（使い捨てコピーで 3 攻撃 + 対照）, `approval_binding`（束縛なし = exit 1 / 束縛あり = exit 0） |
| `scripts/researchos_session.py` | F4, G4 | `resolve_effective` 修正, close 例外 |
| `scripts/researchos_next.py` | V11, G4, **§14・C3/A2** | `load_effective`, fail→proposer 推奨。**(rev3)** 引き継ぎルール5（手動追記後の `researchos_anchor.py update`）とルール6（`review_line_sha256` 必須）を追加。approver テンプレートを「参照レビューから束縛を計算する」形に修正（rev3 以前は束縛なしの承認例を示しており、そのとおりに書くと validator error になる）。手順の `RQ-001`/`PRP-001` ハードコードを撤廃し、実際に open なキュー項目から `queue_id`/`proposal_id`/passing review を導出（V11 の意図） |
| `policy/roles.json` | G1, **C2/A1・C3/A2** | bootstrap land 承認必須。**(rev3)** 全ロールの `may_write` に `state/anchors.jsonl`, `enforcement.whole_file_append_only_anchors`, `enforcement.approval_review_binding`（祖父条項をデータ化） |
| `schemas/approval.json` | C3/A2 | `review_line_sha256` 追加。**(rev3)** `required` に昇格 |
| **`schemas/anchor.json`（新規）** | **C2/A1** | **アンカーエントリのスキーマ（`ANC-[0-9a-f]{16}`, 64hex, 行数, 自己鎖フィールド）** |
| `tests/test_governance.py` | A7, G1, G3, G4, **A1・C3/A2** | 既存の修正。**(rev3)** `test_append_only_hash_chain_is_enforced` を**実際に改竄する**テストに置換, `ApprovalBindingTest`（9 tests）, `bind()` fixture, `approval()` fixture に束縛引数 |
| **`tests/test_append_only_tamper.py`（新規）** | **C2/A1** | **実改竄テスト 20 件: rolling head / アンカー台帳（改竄・削除・再アンカー隠蔽・自己鎖）/ 使い捨てコピーでの 3 攻撃 + 履歴層単独 + 対照 / アンカー行の著者帰属（`unknown` 退行の防止）** |
| `.github/workflows/verify-github-actions.yml` | F3, A8, **§14** | job 分割。**(rev3)** `check-append-only --json` / `check-anchors` / rev3 受入プローブを CI に追加 |
| `docs/GOVERNANCE.md` | C2, C4, C6, G1, **C3/A2** | R6, 並行線路照合。**(rev3)** R4 を 4 層 + アンカー台帳に全面改写, R3 に承認束縛の必須化, ロール表に `state/anchors.jsonl`, コマンド一覧, リカバリ表, 残存リスク 6・7, 設計判断 |
| **`verifications/prp002_rev2_acceptance_probes.py`（新規）** | **§14** | **DoD ランナ。R1-R4 の 26 プローブを実行し、§14 のコマンドと期待 exit を突き合わせる。R2.3 はガードを意図的に弱体化させたコピーで改竄テストが赤になることを要求する（mutation control）** |
| `reports/PRP-002-governance-fixes.md` | — | 本ドキュメント（rev3 rework） |
| `state/proposals.jsonl` | — | PRP-002（**rev3 を追記**） |
| `state/review_queue.jsonl` | — | RQ-002（completed）。**RQ-003 を新規追加（rev3 のレビューラウンド、required_checks 15 項目）** |
| **`state/anchors.jsonl`（新規）** | **C2/A1** | **全 10 台帳の genesis pin（rev3 採用時点の tip）** |
| `state/plan.md` | — | 本ラウンドの記録 |
| `state/NEXT_SESSION.md` | — | 自動生成 |

**非対象（本提案では変更しない）:** `state/sources/evidence/claims/verifications/hypotheses.jsonl` の既存行,
`gitswarm/**`, `contributions/**`, `policy/state_baseline.json`（層1 は維持。撤廃は PRP-003）。
`state/anchors.jsonl` への genesis 追記は既存行の変更ではなく**追記**であり、R4 に従う。

---

## 14. 受入不変条件（Definition of Done — revision 3 でコマンドを実在のものに整合）

REV-003 §5 は「§14 のコマンドが実在しない／文書どおりに動かない」ことを 3 件指摘した
（存在しない probe ファイル、exit 2 の `check-commits --json`、52 件という古いテスト数）。
rev3 の §14 は **`verifications/prp002_rev2_acceptance_probes.py` がそのまま実行する表**である。
各行の probe ID はそのスクリプトの出力と一致し、期待 exit は実測で固定した。

```bash
python3 verifications/prp002_rev2_acceptance_probes.py --json   # 26/26 ok, exit 0
```

| # | 不変条件 | コマンド | 期待 | probe |
| :-- | :--- | :--- | :--- | :--- |
| 1 | G1-G4 プローブ | `python3 verifications/prp001_governance_probes.py` | exit 0（4/4 `enforced=true`） | R4.1 |
| 2 | **rev3 受入プローブ（本提案で新設、実在する）** | `python3 verifications/prp002_rev2_acceptance_probes.py` | exit 0（26/26 ok） | — 自身 |
| 3 | CLI land ステージ | `python3 scripts/researchos_guard.py check-commits --stage propose --json` | exit 0 | R4.2 |
| 3 | 同上 | `python3 scripts/researchos_guard.py check-commits --stage land --json` | PRP-002 未承認の間は exit 1、別セッション承認後は exit 0。**いずれの状態でも exit 2 は失敗** | R4.3 |
| 3 | 同上 | `python3 scripts/researchos_guard.py check-all --stage land --json` | 未承認の間は exit 1（`ok=false`） | R4.4 |
| 4 | 決定論的静的検証 | `python3 scripts/validate_researchos.py --quiet` | exit 0 | R4.8 |
| 5 | 回帰テスト | `python3 -m unittest discover -s tests` | exit 0 / `OK`。**件数はハードコードしない**（実測は出力の `Ran N tests`。rev3 rework 時点の実測値は §18） | R4.9, R4.13 |
| 5 | ベンチマーク | `python3 gitswarm/benchmarks/benchmark.py --check` | exit 0 | R4.10 |
| 5 | readout | `python3 gitswarm/readout.py --quiet --format json` | exit 0（snapshot 一致） | R4.11 |
| 6 | 台帳の追記専用性 | `python3 scripts/researchos_guard.py check-all --json` | exit 0 かつ `ok=true` | R4.12 |
| 6 | **改竄時の追記専用性（rev3 で新設）** | `check-append-only --json` を、①行の書き換え ②行の削除 ③追記・コミット済み行の書き換え、の各使い捨てコピーで実行 | **3 つとも exit 1 / `ok=false`**。クリーンなコピーは exit 0（対照） | R1.3 |
| 6 | **アンカー** | `python3 scripts/researchos_anchor.py verify` | exit 0（全台帳 pin 済み）。改竄コピーでは exit 1 | R1.1 |
| 6 | **実改竄テスト** | `python3 -m unittest tests.test_append_only_tamper` | exit 0（20 tests）。**かつ**ガードを弱体化させたコピーでは exit ≠ 0 | R2.1, R2.3 |
| 6 | authorship | `python3 scripts/researchos_guard.py check-authorship --json` | exit 0 | R4.6 |
| 7 | **承認束縛の必須化** | `researchos_verify.check_approval_binding()`（= 15 checks の 1 つ） | 束縛なし `approved` → validator exit 1、束縛あり → exit 0 | R3.3 |
| 7 | 文書整合性 | `docs/GOVERNANCE.md` に R4 の 4 層・アンカー台帳・承認束縛、`policy/roles.json` に `approval_review_binding` と `state/anchors.jsonl`、`schemas/approval.json` の `required` に `review_line_sha256`、`schemas/anchor.json` の存在 | すべて真 | R3.1, R3.2, R4.15 |
| 7 | **§14 の自己整合** | 本表が参照する `verifications/*.py` がすべて実在し、テスト件数をハードコードしていないこと | 真 | R4.13, R4.14 |

**15 checks（`researchos_verify.py`）:** rev2 の 13 項目（`policy`, `schema_and_integrity`,
`regression_tests`, `benchmark_reproducible`, `readout_snapshot`, `append_only`, `role_guard`,
`role_separation`, `bootstrap_land_requires_approval`, `merge_commits_are_audited`,
`approval_consistency`, `distinct_reviews`, `governance_review`）に
**`append_only_adversarial`** と **`approval_binding`** を加えた。
これで「クリーンな木では 13/13 pass するが DoD の不変条件は成立しない」という
REV-003 §2 の状態は構造的に起きない（敵対的チェックが改竄を自分で実行するため）。

**この §14 を実行するのが proposer の義務であり、結果は `state/plan.md` と §18 に記録する。
次の verifier セッションが独立に再実行し（`RQ-003`）、approver が承認する。**

---

## 15. 実装手順 (本提案が承認された後 — 人間が main に land するまで)

1. **Proposer (本セッション、または別セッションでも可、approval 後なら可):**
   ```bash
   git checkout -b arena/<new>-researchos
   python3 scripts/researchos_session.py claim --role proposer --first-commit <HEAD>
   # Governance-Proposal: PRP-002 トレーラー付きで保護対象を編集
   git commit -m "fix: governance G1-G4 ..." # + Session-Id/Role/Proposal/Informed-By/Web trailers
   ```
2. **Verifier (別セッション):**
   ```bash
   python3 scripts/researchos_session.py claim --role verifier
   python3 scripts/researchos_queue.py claim --queue RQ-002 --session <id>
   python3 scripts/researchos_verify.py --proposal PRP-002 --session <id> --write
   python3 scripts/researchos_queue.py complete --queue RQ-002 --review REV-002 --session <id>
   ```
3. **Approver (proposer/verifier と別):**
   ```bash
   python3 scripts/researchos_session.py claim --role approver
   # REV-002 を読む (governance_review が pass であること、12 checks 全 pass)
   python3 - <<'PY'
   from pathlib import Path; import sys; sys.path.insert(0,'scripts')
   from researchos_common import append_jsonl, now_utc, line_hash, read_jsonl
   # review_line_hash を計算して束縛
   PY
   ```
4. **Land (人間):** `main` への merge 前に `check-commits --stage land` と `validate_researchos.py` が PASS することを CI で確認。`main` の初 push で `gh run list --branch main` が空でなくなることを確認。

---

## 16. リスクと残留課題（正直な記載 — rev3 で更新）

1. **ガードはリポジトリ内コード:** 書き込み権限を持つセッションはガードを弱められる。対策は `main` の人間ゲートと `land` 検査のみ。rev3 ではこれに加えて **mutation control**（probe R2.3）を入れ、「ガードを弱めたら改竄テストが赤になる」ことを機械的に要求した。ガードを弱めてテストも弱めることは可能だが、その変更自体が `scripts/` と `tests/` の diff としてレビューに曝される。
2. **Merge 監査の完全性:** side branch 列挙は octopus merge や履歴改変で限界がある。rev3 の層3は merge 結果に「各親の行が全て・同じ順序で残る」ことを要求するので、union マージは通り、行を落とす/書き換えるマージは通らない。
3. **アンカーの根は Git 履歴:** `state/anchors.jsonl` の**最終行**はそれ以降のエントリが無いので自己鎖で固定できない。層2（HEAD）と層3（コミット単位）がその書き換えを捕まえるが、**履歴そのものの書き換え**（`filter-branch` / force push）はリポジトリ内コードでは防げない。署名付きコミットや承認記録への head 固定は PRP-003 以降。
4. **アンカーは追記専用性を証明するが正しさを証明しない:** 誤った内容を行として追記し、そのまま pin することはできる。内容の妥当性は独立レビューの役割。
5. **既存 APR-001:** rev3 で `review_line_sha256` を必須化した。`APR-001` は実際に束縛を持つので緑のまま。免除は `policy/roles.json` の `enforcement.approval_review_binding.grandfathered_approvals` に**データとして**置き、広げるにはガバナンス変更（別セッションの承認）を要求する。
6. **並行線路の完全解消は PRP-003:** `next_id` の衝突は残る。rev3 では (a) アンカー ID を内容から導出して衝突を回避、(b) 同一行の重複追記を幂等として扱い union マージの `duplicate revision` を減らした。`RQ-003` は並行線路 `arena/f63b6887` の `RQ-003` と衝突する可能性があり、union 時は `docs/GOVERNANCE.md` §6 の手順で照合する（REV-003 §8 が指摘したとおり）。
7. **Identity の暗号学的保証なし:** git author は全セッション共通、model は自己申告。ブランチ一意性と `git blame`（R5）が根拠。
8. **アンカー運用の摩擦:** 手で `state/*.jsonl` に追記したセッションは `researchos_anchor.py update` を忘れると `check-append-only` が赤になる。`append_jsonl()` 経由の追記は自動で pin されるので、標準ツールを使う限り摩擦は無い。エラーメッセージに実行すべきコマンドを含めてある。

---

## 17. 証跡

### revision 1・2（`SES-5491cb12` / `arena/5491cb12-researchos`）

| 種別 | 参照 |
|---|---|
| セッション | `state/sessions.jsonl` の `SES-5491cb12` (proposer, branch `arena/5491cb12-researchos`, first_commit `ae108a1...`) |
| コミット | `6b22092` claim / `9f737a9` 提案 / `00cee15` 実装 / `43bc5d1` 提案 rev2 / `eb4cee3` hand-off / `a997498` `--scan-all` |
| レビュー | `REV-003`（fail、`SES-f99f5b7f`）。並行線路に `REV-002`（fail、`arena/363c9e54`） |
| キュー | `RQ-002`（rev4 = completed with REV-003） |
| プローブ | `verifications/prp001_governance_probes.py`（G1-G4） |
| 承認 | PRP-002 については**まだ無し**（REV-003 が「承認しない」を推奨） |

### revision 3 = revision 2 の rework（`SES-86da9dab` / `arena/86da9dab-researchos`）

| 種別 | 参照 |
|---|---|
| セッション | `state/sessions.jsonl` の `SES-86da9dab`（proposer, branch `arena/86da9dab-researchos`, first_commit `e45cdd8...` = REV-003 の hand-off tip） |
| 入力 | `verifications/prp002_verifier_f99f5b7f.md`（REV-003）§3・§4・§5・§9 |
| 実装 | `scripts/researchos_common.py`, `scripts/researchos_guard.py`, **`scripts/researchos_anchor.py`**, `scripts/validate_researchos.py`, `scripts/researchos_verify.py`, `policy/roles.json`, `schemas/approval.json`, **`schemas/anchor.json`**, `.github/workflows/verify-github-actions.yml` |
| テスト | **`tests/test_append_only_tamper.py`（新規 20 件）**, `tests/test_governance.py`（`ApprovalBindingTest` 9 件 + 改竄テストへの置換） |
| プローブ | **`verifications/prp002_rev2_acceptance_probes.py`（新規、26 プローブ = §14 ランナ）** |
| アンカー | **`state/anchors.jsonl`（genesis pin 10 件）** |
| 提案 | `state/proposals.jsonl` の `PRP-002` **revision 3**（rev2 行の `supersedes` 付き追記） |
| キュー | `state/review_queue.jsonl` の **`RQ-003`**（open, required_checks **15** 項目） |
| 記録 | `state/plan.md` の「PRP-002 rev3 Rework Round」, §18 の実測表 |

全コミットに `Session-Id` / `Session-Role` / `Policy-Version: 1` / `Informed-By: <完全SHA祖先>`、
保護対象（`scripts/`, `schemas/`, `policy/`, `tests/`, `.github/`）を含むコミットには
`Governance-Proposal: PRP-002` を付与する。

---

## 18. revision 3 rework — REV-003 指摘との対応と実測

### 18.1 指摘 → 変更 → 証跡

| REV-003 | 指摘 | rev3 の変更 | 実行可能な証跡 |
| :--- | :--- | :--- | :--- |
| §3.1 / §9-2 | `REV-001` の `summary` 書き換えが `check-append-only` exit 0 | 層2（HEAD 接頭辞）+ 層4（アンカー prefix pin） | probe `R1.3` attack `rewrite_committed_line_in_place` → exit 1 / test `test_attack1_*` |
| §3.2 / §9-2 | `REV-001` 行の削除が `check-all --json` `ok=true` | 層2 + 層3 + 層4（`lines` 超過を検出） | probe `R1.3` attack `delete_committed_line` → `ok=false` / test `test_attack2_*` |
| §3.3 / §9-2 | **追記してコミットした行**の書き換えが `ok=true`（A1 の一般形） | 層3（コミット単位監査）+ 層4（tip pin）+ `append_jsonl` の自動 pin | probe `R1.3` attack `rewrite_freshly_appended_committed_line`（append 0 → clean 0 → rewrite 1 → committed rewrite 1）/ test `test_attack3_*`, `test_history_layer_*` |
| §3.4 / §9-6 | `test_append_only_hash_chain_is_enforced` が改竄しておらず無意味 | 実際に 1 行を書き換えて `anchor_errors() != []` を assert するテストに置換。さらに end-to-end の敵対的スイートを新設 | probe `R2.1`-`R2.4`（**R2.3 = mutation control**: ガードを弱体化させたコピーでスイートが赤になることを要求） |
| §3.5 | 根因: ID ごとの revision 鎖でありファイル全体の鎖ではない／作成時が空 | ファイル全体の rolling head + `state/anchors.jsonl`（自己鎖つき）を新設。§2 に設計と代替案の比較を記載 | probe `R1.1`, `R1.2` / `scripts/researchos_anchor.py verify` |
| §4 / §9-3 | `review_line_sha256` が必須化されておらず、fixture `APR-910` が exit 0 | スキーマ `required` + validator の必須化（欠落/一部欠落/単一文字列 = error、不一致 = 常に error）。祖父条項は `policy/roles.json` のデータ | probe `R3.1`-`R3.4` / `researchos_verify.check_approval_binding()` / `ApprovalBindingTest` 9 件 |
| §5 item2 / §9-5 | `verifications/prp002_design_probes.py` が存在しない | 実在する DoD ランナ `verifications/prp002_rev2_acceptance_probes.py` を新設し、§14 をその出力と 1:1 に対応させた。（同名の verifier 成果物は並行線路 `arena/e09f19e4` にのみ存在し、本線路の DoD からは参照しない） | probe `R4.14`（§14 が参照する probe が全て実在することを検査） |
| §5 item3 / §9-4 | `check-commits --json` が exit 2 | 全サブコマンドに `--json` を実装、`check-anchors` を新設。§14 の表を実測 exit で固定 | probe `R4.2`-`R4.7` |
| §5 補足 / §9-7 | テスト件数の記載 52 が実測 57 と食い違う | §14 から**件数のハードコードを削除**し、実測コマンドを記載。probe が「ハードコードが無いこと」を検査 | probe `R4.13` |
| §2 | 「13/13 pass だが DoD 不成立」 | 15 checks に拡張し、`append_only_adversarial` と `approval_binding` が**自分で改竄を実行して**判定する | `python3 scripts/researchos_verify.py --proposal PRP-002 --session <verifier>` |
| §8 | 並行線路の ID 衝突（`RQ-002` rev3 が両線路で衝突） | アンカー ID を内容から導出、同一行の重複追記を幂等化して union 時の衝突面を縮小。`RQ-003` は衝突しうるため §6 の照合手順を維持 | `docs/GOVERNANCE.md` §6, §16-6 |

### 18.2 実測（proposer セッション `SES-86da9dab`、Python 3.11 / git 2.39 / Linux）

| 測定 | 結果 |
| :--- | :--- |
| `python3 verifications/prp002_rev2_acceptance_probes.py --json` | 26/26 ok, exit 0 |
| `python3 -m unittest discover -s tests` | `Ran 86 tests ... OK`（rev2 時点は 57 件。内訳: `test_append_only_tamper` 20 件 + `ApprovalBindingTest` 9 件 = 29 件増） |
| `python3 scripts/researchos_guard.py check-all --json` | `ok=true`（`policy`, `append_only`, `commits`, `authorship`, `anchors` の 5 キーすべてエラー 0） |
| `python3 scripts/validate_researchos.py --quiet` | exit 0 |
| `python3 scripts/researchos_anchor.py verify` | `ok=true`（10 台帳すべて pin 済み） |
| 攻撃 1（REV-001 の `summary` 書き換え、未コミット） | `check-append-only` **exit 1**（層2 `against HEAD` + 層4 `an anchored line was modified`） |
| 攻撃 1b（書き換えた上で `researchos_anchor.py update`） | **exit 1**（古いエントリの prefix pin が残るため隠せない） |
| 攻撃 2（REV-001 行の削除） | **exit 1** / `check-all --json` `ok=false` |
| 攻撃 3（REV-9001 を追記→コミット→書き換え→再アンカー→コミット） | 追記直後は **exit 0**、書き換え（未コミット）**exit 1**、コミット後も **exit 1**（層3 が `5092212: ... against c69f9ca` とコミット単位で特定） |
| `researchos_verify.check_append_only_adversarial()` | 4/4 rejected（対照含む） |
| `researchos_verify.check_approval_binding()` | unbound → exit 1（`review_line_sha256` エラー 2 件）、bound → exit 0 |

### 18.3 rev3 で**やらなかった**こと（正直な記載）

* `policy/state_baseline.json`（層1）の撤廃 — 後方互換のため維持。撤廃は PRP-003。
* 署名付きコミット／リポジトリ外アンカー — 履歴書き換えへの対抗は PRP-003 以降。
* `next_id` の UUID 化 — 並行線路の ID 衝突の根本対策は PRP-003。
* REV-003 が positive と確認した F1/F2/F4/G1/G3/G4 の実装は**変更していない**（壊れていないものを触らない）。rev3 の差分は §2・§3・§9(rev3 追記)・§13・§14 と新規ファイルに限る。
* 並行線路 `arena/f63b6887`（design-only の PRP-002 rev2）と `arena/363c9e54`（REV-002）は merge していない。REV-003 と同じく proposer tip から独立に rework した。

### 18.4 rev3 の実装中に**自分で見つけた**副作用（verifier への申し送り）

rev3 の変更が既存の検査・文書と衝突した3件。いずれも push 前に検出して修正済みで、
「新しい層を足すと別の検査が赤くなる」ことの実例として記録する。

| 見つけた経緯 | 症状 | 修正 | 退行防止 |
| :--- | :--- | :--- | :--- |
| `check-all --branch arena/86da9dab-researchos --stage propose --json`（コミット後、push 前） | `state/anchors.jsonl:12: record claims session 'unknown' but was introduced by commit fbe0f71 authored by 'SES-86da9dab'` → `ok=false`、exit 1。`append_jsonl` の自動 pin が record の `session_id` しか見ておらず、`state/review_queue.jsonl` の行は `created_by_session` / `claimed_by_session` しか持たないため `unknown` で pin されていた | `record_session_hint()`（`session_id` → `created_by_session` → `claimed_by_session`）を追加し、それでも無ければ `session_from_branch(root=root)` にフォールバック。`check-authorship` は弱めていない | `AnchorAuthorshipTest` 4 件（`test_record_session_hint_*`, `test_session_from_branch_*`, `test_auto_pin_falls_back_to_the_branch_session`, `test_repository_anchor_lines_name_a_real_session`）。`tests/test_append_only_tamper.py` は 16 → **20 件** |
| 同上のテスト作成中 | 未 commit のリポジトリ（unborn branch）では `git rev-parse --abbrev-ref HEAD` が `HEAD` を返し、ブランチ名から session を導出できない | `current_branch()` に `git symbolic-ref --short HEAD` のフォールバックを追加（detached HEAD では従来どおり `HEAD`） | `test_auto_pin_falls_back_to_the_branch_session`（`git init -b arena/deadbeef-researchos` の空リポジトリで `SES-deadbeef` になることを確認） |
| `researchos_next.py --write` の出力を目視 | rev3 で `review_line_sha256` を必須化したのに、引き継ぎの approver テンプレートが**束縛なしの承認例**を示していた。次のセッションがそのとおりに書くと validator が error になる | テンプレートを「参照レビューから `line_hash` を計算して束縛する」形に書き換え、`assert set(binding) == set(REVIEWS)` を追加。あわせて手順の `RQ-001`/`PRP-001` ハードコードを撤廃し、open なキュー項目から導出（V11 の意図）。ルール5（手動追記後の `anchor.py update`）・ルール6（束縛必須）を追加 | `state/NEXT_SESSION.md` の生成物を本セッションで確認（RQ-003 / PRP-002 / 15 checks が正しく出る） |

* アンカー台帳は追記専用なので、`unknown` で pin された行は「訂正行の追記」では直せない
  （`check-authorship` は行単位で見る）。該当行を含むコミットは **push 前**だったため、
  コミットを作り直して正しい著者で pin し直した。push 後に同じことが起きた場合は、
  正しい session で `researchos_anchor.py update` を実行して新しい行を追記し、
  古い行は履歴に残したまま verifier に申し送ること（`docs/GOVERNANCE.md` §8-6）。

---

*本提案は `arena/955f8586` 承認ラウンドの条件付き承認 (C1-C6) を満たすための実装提案であり、PRP-001 を main に land する前の必須ゲートである。revision 3 は `REV-003`（fail）に対する rework であり、`RQ-003` として別セッションの verifier に引き継ぐ。*
