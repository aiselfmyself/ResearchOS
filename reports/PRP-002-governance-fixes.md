# PRP-002 ガバナンス・ハーネス強化 — F1〜F4・A1〜A8・G1〜G4・V1〜V13 の是正

- 作成日: 2026-10-19
- 作成セッション: `SES-5491cb12` / proposer / `arena/5491cb12-researchos`
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

## 2. C2/A1 — 追記専用のローリングハッシュ鎖

### 現象
`check_append_only` は `base_commit` 時点の行数を数え、前方一致だけを見る。`state/reviews.jsonl` は base 後に作成されたため baseline に含まれず、追記行は無保護。REV-001 の `summary` 書き換えが `ok=true`。

### 原因
- `policy/state_baseline.json` の `files` は base 時点の 5 ファイルのみ
- `_historical_text` が file creation commit との比較にフォールバックするが、creation 後の追記は prefix に含まれない
- `resolve_effective` のハッシュ鎖検証は `validate_researchos.py` だけで、guard の append_only は呼ばない

### 修正
1. `scripts/researchos_guard.py::check_append_only` に **ローリング検証** を追加:
   - 各 `state/*.jsonl` について `resolve_effective` 相当の revision/supersedes 検証を実行
   - prefix 検査は維持 (後方互換) しつつ、ハッシュ鎖エラーがあれば追加エラーとして報告
   - 新 helper `check_hash_chain(path)` を `researchos_common.py` に追加し、guard と validator で共有
2. `scripts/researchos_common.py`: `legacy_hashes` 判定を維持しつつ、新レコードは必ず `supersedes == line_hash(prev)` を満たすことを文書化
3. `docs/GOVERNANCE.md` R4 を「接頭辞 + ハッシュ鎖」に更新
4. テスト: `tests/test_governance.py` に `test_append_only_hash_chain_is_enforced` 追加 — REV-001 行の1文字書き換えが `check_append_only` で FAIL することを検証 (throwaway clone 相当を unit test で再現)

### 受入条件
- `python3 scripts/researchos_guard.py check-append-only` がハッシュ鎖不正で exit 1
- REV-001 行を改変した一時ファイルで `check_hash_chain` がエラーを返す
- 既存の 49 tests は PASS (baseline 前の行は legacy 免除)

---

## 3. C3/A2 — 承認とレビュー内容の束縛

### 現象
`schemas/approval.json` は `review_ids` のみ。承認後にレビュー行を書き換えても `check-all ok=true`。
`APR-001` は自主的に `review_line_sha256` を記録したが、スキーマ・検証器は関知しない。

### 修正
1. `schemas/approval.json` に `review_line_sha256` (object, key: review_id, value: sha256 hex) を**推奨必須**フィールドとして追加 (追加プロパティ許可なので既存 APR-001 は互換、PRP-002 以降は必須化を validator で強制)
2. `scripts/validate_researchos.py::validate_governance` で:
   - `approval` が `approved` のとき、参照する各 `review` の正規化行ハッシュを計算し、`review_line_sha256[review_id]` と一致することを検証
   - 不一致は error、欠落は PRP-002 以降は error (baseline 前の APR-001 は warning に留めるか、revision 2 で追補可能)
3. `scripts/researchos_guard.py::check_record_authorship` は既存の通り `git blame` で authorship を束縛 — レビュー書き換えにはレビュー者ロールのコミットが必要になり、A4 (F1×A1 合成) も合わせて塞ぐ

### 受入条件
- `validate_researchos.py` が `review_line_sha256` 不一致の approval で exit 1
- APR-001 のハッシュ `d1bf998f...` が validator で検証される (本セッションの `validate_researchos.py --quiet` が PASS)

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

### 受入条件
- `python3 scripts/researchos_guard.py check-commits --stage land` が exit 2 ではなく 0 or 1
- `researchos_session.py close --session SES-5491cb12` 直後の `check-commits` が PASS

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

## 13. 変更対象一覧 (承認後に実装するファイル — 本提案では proposer が propose ステージで実装)

| ファイル | 対応ID | 変更内容 |
|---|---|---|
| `scripts/researchos_common.py` | C4/F1, G2, G4, A1 | `is_ancestor` helper, `commit_parents` helper, `check_hash_chain` doc, `COLLECTION_ID_KEYS` 強調, `next_id` 衝突警告コメント |
| `scripts/researchos_guard.py` | C2/A1, C4/F1+F2, G1, F3, F4, C6 | `check_governance_path` bootstrap 例外の land 除外, `check_commits` merge 監査・branch束縛是正・close例外, `check_append_only` にハッシュ鎖追加, `check_record_authorship` 維持, CLI `--stage` 追加 |
| `scripts/validate_researchos.py` | G3, C3/A2, C6 | `validate_governance` に集約整合性・required_checks・review_line_sha256 検証追加 |
| `scripts/researchos_queue.py` | G4 | `_load` を `load_effective` に統一 |
| `scripts/researchos_verify.py` | G4, V10 | `resolve_effective` に id_key 明示, `build_checks` に 4 プローブ統合 (12 checks) |
| `scripts/researchos_session.py` | F4, G4 | `effective_sessions` の `resolve_effective` 修正, close 例外のドキュメント |
| `scripts/researchos_next.py` | V11, G4 | `_effective` を `load_effective` に, `decide_role` に fail→proposer ロジック |
| `policy/roles.json` | G1 | bootstrap 説明に land 承認必須を追記 |
| `schemas/approval.json` | C3/A2 | `review_line_sha256` 追加 (optional, pattern hex) |
| `tests/test_governance.py` | A7, G1, G3, G4, A1 | `test_bootstrap_is_exempt` 改名・land 追加, 新テスト 4件, `test_bootstrap_proposal_cannot_be_self_closed` 修正 |
| `.github/workflows/verify-github-actions.yml` | F3, A8 | `--stage land` 対応, job 分割で短絡防止 |
| `docs/GOVERNANCE.md` | C2, C4, C6, G1 | R4 ハッシュ鎖, R6 bootstrap 例外, 並行線路照合手順, A3 注記 |
| `reports/PRP-002-governance-fixes.md` | — | 本ドキュメント |
| `state/proposals.jsonl` | — | PRP-002 追加 |
| `state/review_queue.jsonl` | — | RQ-002 追加 |
| `state/plan.md` | — | 本提案ラウンドの記録 |
| `state/NEXT_SESSION.md` | — | 自動生成 |

**非対象 (本提案では変更しない):** `state/sources/evidence/claims/verifications/hypotheses.jsonl` (追記専用), `gitswarm/**`, `contributions/**`, `policy/state_baseline.json` (baseline は維持、次回 PRP-003 で段階移行)

---

## 14. 受入不変条件 (Definition of Done — V12 対応)

以下の不変条件が**いかなる状態推移においても**成立すること:

1. **G1-G4 プローブ完全通過:**
   ```bash
   python3 verifications/prp001_governance_probes.py  # exit 0, 全4項目 enforced=true
   ```
2. **設計整合プローブ完全通過 (本提案で新設):**
   ```bash
   python3 verifications/prp002_design_probes.py  # exit 0, 全12項目 ok=true (V10 で researchos_verify.py に統合後はそちらで代替)
   ```
3. **CLI land ステージ正常動作:**
   ```bash
   python3 scripts/researchos_guard.py check-commits --stage propose --json  # exit 0
   python3 scripts/researchos_guard.py check-commits --stage land --json    # 未承認時は exit 1、承認後は exit 0 (exit 2 不可)
   python3 scripts/researchos_guard.py check-all --stage land --json
   ```
4. **決定論的静的検証完全通過:**
   ```bash
   python3 scripts/validate_researchos.py --quiet  # exit 0
   ```
5. **テスト・ベンチマーク完全通過:**
   ```bash
   python3 -m unittest discover -s tests -v  # 全 tests PASS (52件)
   python3 gitswarm/benchmarks/benchmark.py --check  # PASS
   python3 gitswarm/readout.py --quiet --format json # readout_snapshot 一致
   ```
6. **台帳追記専用性・真正性維持:**
   ```bash
   python3 scripts/researchos_guard.py check-all --json  # ok=true
   python3 scripts/researchos_guard.py check-authorship   # PASS
   ```
7. **文書整合性:**
   - `docs/GOVERNANCE.md` に R4 ハッシュ鎖・R6 land 例外・照合手順が記載
   - `policy/roles.json` の bootstrap 説明が更新
   - `schemas/approval.json` に `review_line_sha256` が存在

**本セッション (proposer) は上記 1-6 を空の一時リポジトリと本リポジトリの両方で検証し、ログを `verifications/verifier_eb670d1f_audit_log.md` 相当の `state/plan.md` に残す。次の verifier セッションが独立に再実行し、approver が承認する。**

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

## 16. リスクと残留課題 (正直な記載)

1. **ガードはリポジトリ内コード:** 書き込み権限を持つセッションはガードを弱められる。対策は `main` の人間ゲートと本ハーネスの `land` 検査のみ。PRP-002 の land 時は `scripts/` 変更も承認必須で再発防止。
2. **Merge 監査の完全性:** `git rev-list other ^first_parent` による列挙は octopus merge や履歴改変では限界がある。完全な保証は `main` の人間レビュー。
3. **既存 RQ-001/Apr-001:** 本提案で変更しない。`validate_researchos.py` は APR-001 の `review_line_sha256` を検証するが、APR-001 が旧スキーマでも warning に留めるか、revision 2 で追補する運用とする (本実装では warning)。
4. **並行線路の完全解消は PRP-003:** `next_id` の衝突回避を UUID に変える等の根本対策は別提案。本提案は衝突しない新規 ID (RQ-002) と照合手順の文書化に留める。
5. **Identity の暗号学的保証なし:** git author は全セッション共通、model は自己申告。ブランチ一意性と `git blame` のみが根拠。本提案はその限界を明記しつつ、ハーネス自身の防御を最大化する。

---

## 17. 証跡

| 種別 | 参照 |
|---|---|
| セッション | `state/sessions.jsonl` の `SES-5491cb12` (proposer, branch `arena/5491cb12-researchos`, first_commit `ae108a1...`) |
| コミット | `6b22092` session claim / (次) PRP-002 提案・キュー追加 / (次) ガバナンス実装 (全て `SES-5491cb12` / proposer, `Governance-Proposal: PRP-002` トレーラー付き) |
| CI | `6b22092` の push に対して `verify` job が propose ゲートを通過、`land` ゲートは `main` 以外でスキップ (V1 修正後は `stage` 引数が有効) |
| レビュー | 次セッションの verifier が `REV-002` (12 checks) を `state/reviews.jsonl` に記録予定 |
| キュー | `state/review_queue.jsonl` の `RQ-002` (open, required_checks 12項目) |
| プローブ | `verifications/prp001_governance_probes.py` (新設、G1-G4 を検証) |
| 提案 | `state/proposals.jsonl` の `PRP-002` (本コミットで追加) |
| 承認 | まだ無し (次の approver セッションが `APR-002` を記録) |

全コミットに `Session-Id: SES-5491cb12` / `Session-Role: proposer` / `Policy-Version: 1` / `Informed-By: <完全SHA祖先>` / `Governance-Proposal: PRP-002` (保護対象変更時のみ) を付与。

---

*本提案は `arena/955f8586` 承認ラウンドの条件付き承認 (C1-C6) を満たすための実装提案であり、PRP-001 を main に land する前の必須ゲートである。*
