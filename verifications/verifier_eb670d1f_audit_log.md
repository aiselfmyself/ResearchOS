# 独立検証ログ — PRP-001 ガバナンス・ハーネス

- **セッション**: `SES-eb670d1f`（branch `arena/eb670d1f-researchos`）
- **ロール**: `verifier`（提案者 `SES-c4426c6b` とは別セッション。承認は行わない）
- **日時**: 2026-10-19 (UTC)
- **環境**: Python 3.11.2 on linux
- **引き継ぎ**: `origin/arena/c4426c6b-researchos` (`8a09e28`) を fast-forward で継承
- **対象提案**: `PRP-001` — *Adopt the ResearchOS governance harness (roles, append-only state, review queue)*
- **結果**: `REV-001` / `result: pass`（8 検査すべて pass）＋ 6 件の発見（うち High 2 件）

---

## 1. 方針: 「PASS した」を信用しない

前々セッションの失敗は、**検証スイートが PASS したのに中身が偽だった**ことだった
（ベンチマークは未実行、著者名が誤り）。したがって本セッションでは

1. 標準スイートを再実行する（これは当然やる）が、
2. **それを「効いている」と証明するために、違反を起こして検出されるかを確かめる**。

ガバナンス・ハーネスの価値は「ルールを書いたこと」ではなく「ルールが破られたときに
失敗すること」にある。ので、使い捨てクローン（`git clone` した別ディレクトリ）で
13 のシナリオを実行した。本ブランチの履歴は一切汚していない。

---

## 2. 標準スイート（8 検査）— 生の結果

```
python3 scripts/researchos_verify.py --proposal PRP-001 --session SES-eb670d1f --write
（全作業完了後にもう一度実行し、同じく 8/8 pass であることを確認した）

policy                   pass   PASS: policy
schema_and_integrity     pass
regression_tests         pass   Ran 49 tests in 1.306s OK
benchmark_reproducible   pass   PASS: benchmark artifact matches a fresh execution
readout_snapshot         pass   readout matches the committed snapshot
append_only              pass   PASS: append_only
role_guard               pass   PASS: commits
role_separation          pass   reviewer differs from proposer
```

### 2.1 ベンチマークは本当に「再実行」されているか

`benchmark.py --check` は `run_benchmarks()` を毎回走らせ、コミット済み成果物と比較する。
実測値（本セッションの再実行）:

| Solver | mean | min | max | runs |
| :--- | ---: | ---: | ---: | ---: |
| greedy | 5521.41 | 5039.797 | 6296.501 | 5 |
| random | 12279.86 | 11581.285 | 13337.465 | 5 |
| two_opt | 4739.72 | 4401.48 | 5264.448 | 5 |
| simulated_annealing | 4731.96 | 4396.027 | 5264.448 | 5 |

Auditor-01 の再実行値と**一致**。SA の two_opt に対する優位は 0.16%（7.76 / 4739.72）。

改ざんが検出されるかも確かめた（**最初の試行は私のミスで無効**だった。成果物に
`summary` というキーは無く、トップレベルはソルバ名なので編集箇所を外していた）:

```
greedy.mean_distance を 1.0 に改ざん
  → FAIL: greedy.mean_distance: committed=1.0 actual=5521.41 (delta=+5520.410)   exit=1
per_seed[42].greedy を 1.0 に改ざん
  → FAIL: per_seed[42].greedy: committed=1.0 actual=5057.938 (delta=+5056.938)   exit=1
```

**「ベンチマークが手書きだった」という 2026-10-19 の失敗は、再現不能になっている。**

### 2.2 著者名の訂正を一次資料に照合したか

Auditor-01 の訂正を、このセッションで独立に引き直した。

| Source | レコードの筆頭著者 | arXiv の筆頭著者 | 著者数 | 判定 |
| :--- | :--- | :--- | ---: | :--- |
| SRC-001 (arXiv:2610.07625) | Qizheng Zhang | Qizheng Zhang [1](https://arxiv.org/abs/2610.07625) | 18 / 18 | 一致 |
| SRC-002 (arXiv:2610.04862) | Vedant Shah | Vedant Shah [2](https://arxiv.org/abs/2610.04862) | 14 / 14 | 一致 |
| SRC-003 (arXiv:2610.17184) | Shubham Agarwal | Shubham Agarwal [3](https://arxiv.org/abs/2610.17184) | 23 / 23 | 一致 |

3 件すべて一次資料と一致。Auditor-01 の「Verifier の authors confirmed は不成立」という
指摘と、その後の是正は正しかった。

### 2.3 スイートは自分のミスも検出した（生の証拠）

本セッションのコミット `aa5dd53` で `Informed-By: HEAD` と書いてしまい（sha ではないので
規約違反）、その直後の実行で

```
FAIL: test_repository_passes_all_checks
  AssertionError: ["Commit aa5dd53 has malformed Informed-By reference 'HEAD'"] != []
FAIL: test_repository_state_passes_all_checks  （同じく 1 件）
Ran 49 tests — FAILED (failures=2)
```

が出た。`--amend` で `Informed-By` を実 sha に直したところ 49 tests OK に戻った。
**スイートは「通すための飾り」ではなく実際に違反を落とす**（少なくとも状態レイヤと
成果物については）。この点は §4 の git レイヤの抜け道と切り分けて評価する必要がある。

---

## 3. 負のテスト: ふつうの違反は検出されるか（7/7 検出）

すべて使い捨てクローンで実行。`python3 scripts/researchos_guard.py check-all`。

| # | シナリオ | 期待 | 実際 |
| :--- | :--- | :--- | :--- |
| N1 | verifier が `scripts/researchos_guard.py` を編集 | FAIL | ✅ `role 'verifier' may not modify governance path 'scripts/researchos_guard.py'` |
| N2 | verifier が `state/claims.jsonl` に追記 | FAIL | ✅ `role 'verifier' is not allowed to write 'state/claims.jsonl'` |
| N3 | トレーラ無しコミット | FAIL | ✅ `missing Session-Id / Session-Role trailers` |
| N4 | 存在しないセッションを名乗る | FAIL | ✅ `session 'SES-fake' is not in state/sessions.jsonl` |
| N5 | 未所持ロール（`bootstrap`）を名乗る | FAIL | ✅ `session 'SES-eb670d1f' does not hold role 'bootstrap'` |
| N6 | 既存行を書き換え（追記でなく） | FAIL | ✅ `state/claims.jsonl: line 1 was modified or reordered` |
| N7 | state ファイルを削除 | FAIL | ✅ `state/hypotheses.jsonl: file existed at 066b937 but is now missing` |

R4（追記専用）と R2（パス権限）は**単体では効いている**。

### 3.1 R5（authorship 束縛）も効いている

verifier が「提案者セッション名義のレビュー」を追記するシナリオ（N12）:

```
check-authorship FAIL
  state/reviews.jsonl:1: record claims session 'SES-c4426c6b' but was introduced by
  commit 8f83816 authored by 'SES-eb670d1f'
validate_researchos.py: Review 'REV-900' is a self-review: session SES-c4426c6b
  both proposed and reviewed PRP-001
validate_researchos.py (warning): Review 'REV-900' was written by a session
  without the verifier role
```

別セッションを名乗るレコードは、**両方の検査器**で落ちる。

---

## 4. 発見: 検出されなかった抜け道（6 件）

### F1 (High) — `Session-Id` は自己申告で、ブランチ束縛は HEAD しか見ない

`researchos_guard.py: check_commits()` は各コミットについて「セッションが存在するか」
「ロールを持つか」「パスが許可されるか」を検査するが、**セッションのブランチが
現在のブランチと一致するかは HEAD コミットでしか検査しない**（`if sha == head and ...`）。

したがって「他人のセッション ID を名乗るコミット」は HEAD 以外なら通る。
最も権限の大きい `bootstrap`（`may_write: ["**"]`、提案不要）を名乗れば、
検証器自身を無効化できる。実証（使い捨てクローン）:

```python
# scripts/researchos_guard.py の check_commits() の先頭に return [] を差し込む
git commit -m "... 
  Session-Id: SES-c4426c6b      ← 提案者セッションを名乗る
  Session-Role: bootstrap"
# その上に自分の正当な verifier コミットを 1 つ積む（HEAD のブランチ検査を通すため）
git commit -m "...
  Session-Id: SES-eb670d1f
  Session-Role: verifier"
```

```
$ python3 scripts/researchos_guard.py check-all --json
{"ok": true, "results": {"policy": [], "append_only": [], "commits": [], "authorship": []}}
```

**ガードを無効化した状態で `ok: true`。** R5 の authorship 束縛も、blame が
「そのコミット自身」を返すため整合して見える。

GOVERNANCE.md §8.2 は「同一性は暗号学的ではない」と正直に書いているが、
§4 の R2/R5 は「強制される」と書かれている。**ドキュメントと実装の差**がここにある。

### F2 (High) — マージコミットは丸ごと検査対象外（`--first-parent` の副作用）

`commits_in_range()` は `--first-parent` を使い、`is_merge()` のコミットは `continue` で
読み飛ばす。したがって:

- マージコミット自体が持つ差分（`git show --name-only` が返す、第1親との差分）は検査されない
- `--no-ff` でマージされた側ブランチのコミットは、first-parent 系列にいないので検査されない

実証: トレーラを一切持たないコミットで `scripts/researchos_guard.py` と
`.github/workflows/evil.yml` を変更した side branch を `--no-ff` マージ。

```
$ python3 scripts/researchos_guard.py check-all --json
{"ok": true, ... "commits": [] ...}
```

**verifier は「触れない」とされているガバナンスパスを、マージで着地できる。**
これは R2 と R6 の両方を迂回する。

### F3 (Medium) — `land` ゲートは CLI に繋がっていない

`.github/workflows/verify-github-actions.yml` の「ガバナンス着地ゲート（main のみ）」は

```yaml
python3 scripts/researchos_guard.py check-commits --branch main --stage land
```

を実行するが、`check-commits` サブパーサに `--stage` は定義されていない
（`--base` と `--branch` のみ）。したがって

```
researchos_guard.py: error: unrecognized arguments: --stage land   (exit 2)
```

**このステップは main で必ず落ちる。しかも「ガバナンス違反」ではなく
「CLI の使い方エラー」として落ちる。** さらに `check_all` / `check-commits` の
呼び出し側は `getattr(args, "stage", "propose")` なので、仮に引数が渡っても
常に `propose` として扱われる。

プログラムから直接 `check_commits(stage="land")` を呼んだ場合の挙動も確認した
（`main` にマージする 2 通りをシミュレート）:

| main へのマージ形式 | 検査対象コミット | land の判定 |
| :--- | :--- | :--- |
| **Squash merge** | PR 全体が 1 コミットに潰れ、verifier の `Session-Id` が付く | 59 件のエラー（ガバナンスパス 26 ＋ 通常パス 32 ＋ ブランチ不一致 1）。**bootstrap が作ったファイルまで verifier の責任にされる** |
| **Create a merge commit** | マージコミット 1 件のみ（しかも `is_merge` で読み飛ばし） | **`PASS (no errors)` — 何も検査していない** |

つまり **R6 は、GitHub のどちらのマージ形式でも main で実効性を持たない**
（squash なら誤った理由で失敗、merge commit なら空振り）。

### F4 (Medium) — 自分のセッションを `close` すると CI が壊れる

`researchos_session.py close --session <自分>` は `status: closed` の改訂行を追記するが、
`check_commits()` は各コミット時点のセッション台帳を見て

```
bc87dc3: session 'SES-eb670d1f' is closed
```

を出す。**close したコミット自身が常に HEAD になる**ため、ドキュメントにある
`close` は「実行した瞬間にガード違反」になる（GOVERNANCE.md §6.4 は close を
コマンド一覧に載せているが、§6.1 の終了手順には含めていない。実装は §6.4 側）。

### F5 (Low) — キューの `required_checks` は誰も突き合わせていない

RQ-001 は `governance_review, schema_and_integrity, regression_tests,
benchmark_reproducible, readout_snapshot, append_only, role_guard, role_separation`
を要求するが、`researchos_verify.py` が生成するのは `policy, schema_and_integrity, ...`
の 8 つで、**`governance_review` という名前の検査は存在しない**（相当するのは `policy`）。
`required_checks` は `researchos_queue.py`（書く）と `researchos_next.py`（表示する）しか
参照しておらず、レビュー結果との突き合わせはどこにも無い。

名称が 1 つずれているので、将来レビューを機械的に突き合わせようとすると
「要求検査が未実施」と誤判定する。

### F6 (Low・残存リスク) — readout snapshot は verifier が書き換えられる

`policy/roles.json` は verifier に `gitswarm/artifacts/readout_snapshot.json` への
書き込みを許している（意図的: 検証者が再ベースラインするため）。したがって
`readout_snapshot` 検査が証明するのは「**最後に verifier が再ベースラインして以降、
ドリフトしていない**」であって「ドリフトしたことがない」ではない。
`gitswarm/readout.py` のスコープを変えてから verifier が snapshot を再生成する
シナリオ（N14）では、ガードは `gitswarm/readout.py` の変更を正しく検出したが
（`role 'verifier' is not allowed to write 'gitswarm/readout.py'`）、
snapshot 側の更新だけなら検査は通る。

---

## 5. 判定

| 項目 | 結果 |
| :--- | :--- |
| 標準 8 検査 | **pass**（8/8） |
| 負のテスト（通常違反） | **7/7 検出** |
| R3 / R4 / R5（状態レイヤ） | いずれも拒否を確認 |
| ベンチマーク改ざん検出 | **検出**（`--check` は実再実行） |
| 著者名の一次資料照合 | 3 件すべて一致 |
| git レイヤの強制 | **F1 / F2 により迂回可能**（実証済み） |
| main への着地ゲート | **F3 により実効性なし** |
| 付随する運用上の地雷 | F4 / F5 / F6 |

**REV-001 は `pass`。** ただしここでの pass は「要求された 8 検査が通った」という意味で、
「ハーネスが完全である」という意味では**無い**。F1・F2 は「気づける形にする」という
ハーネス自称の目的は満たす（どちらも git の履歴に痕跡が残る）が、
「防ぐ」ものではない。

したがって本レビューは **条件付き pass**:

1. PRP-001 の採用は支持する。何も無い状態（bootstrap の例外が唯一のルール）より
   厳密に良い。
2. **F1〜F4 は別提案（PRP-002）で閉じるべき**。私は verifier なので
   `scripts/` に触れられないし、触れるべきでもない（R2）。
3. PRP-002 が承認されるまで、**main へのマージは人間が中身を見るゲートであり続ける**。
   F3 のとおり、現状の land ステップは何も守っていない。

---

## 6. この検証で出来なかったこと（限界）

- **セッション同一性の証明**: git author は全セッション共通で、署名も無い。
  「別セッションである」ことはブランチ名とレコードでしか担保されない（F1 の根本原因）。
- **モデル多様性の検証**: `declared_model` は自己申告。本セッションも
  `arena-agent (self-declared, unverified)` と記録した。**検証していない。**
- **ハーネスのテスト自身は提案者が書いた**: `tests/test_governance.py` の 34 テストは
  PRP-001 と同じセッションの成果物。私は実行結果と、その外側のシナリオしか見ていない。
- **一次資料の逐語引用**: EVD-001 / EVD-004 の逐語抜粋が原文に存在するかは
  本セッションでは引き直していない（Auditor-01 の是正を検証していない）。
  著者名と書誌事項のみ照合した。
- **実運用でのテスト**: 非同期・独立コンテキストのワーカー群は未検証のまま。

---

## 7. 再現方法

```bash
git clone -b arena/eb670d1f-researchos <repo> w && cd w
# 標準スイート
python3 scripts/researchos_verify.py --proposal PRP-001 --session SES-eb670d1f
# F1: 他人の bootstrap セッションを名乗ってガードを無効化し、上に自分のコミットを積む
# F2: side branch で scripts/ を変更し --no-ff でマージ
# F3: python3 scripts/researchos_guard.py check-commits --branch main --stage land
# F4: python3 scripts/researchos_session.py close --session SES-eb670d1f
```

各シナリオの実行結果は本ファイル §3・§4 に抜粋した。スクリプト本体は
ブランチ外の一時クローンで実行したため、リポジトリには残していない
（残すと「攻撃のレシピを配布する」ことになるが、必要なら別途提案する）。

---

*記録: `REV-001`（`state/reviews.jsonl`）/ セッション `SES-eb670d1f` (verifier)*
