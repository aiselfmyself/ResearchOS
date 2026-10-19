# PRP-002 独立検証レポート（REV-003）

- 検証セッション: `SES-f99f5b7f`（`arena/f99f5b7f-researchos`、**verifier のみ**。proposer ではない）
- 提案: `PRP-002`（proposer `SES-5491cb12` / `arena/5491cb12-researchos`）
- キュー: `RQ-002` を claim し、`REV-003` で complete
- 対象: `a997498`（proposer tip）を `git merge --ff-only origin/arena/5491cb12-researchos` で取り込み、verifier コミットを追加
  - `b4e775c` session claim / `e669f41` RQ-002 claim / `7b17c8e` REV-003 / `9ff1525` RQ-002 complete
- 環境: Python 3.11.2 / git 2.39.5 / Linux
- レビュー行ハッシュ: `502b4e439664c21d7832752f03ebbcb880db932fe8e536b2e2d3aa06a4be4745`

## 1. 結論

**RQ-002 の 13 required_checks は 13/13 pass。しかし PRP-002 全体の判定は fail。**

理由は、提案自身が §2 の受入条件として掲げた **C2/A1（追記専用のローリングハッシュ鎖）が実際には機能していない**ことです。独立に再現した攻撃では、次がすべて **guard を通過**しました。

1. `state/reviews.jsonl` の `REV-001` の `summary` をその場で書き換え → `check-append-only` は exit 0
2. `REV-001` の行を**削除** → `check-append-only` は exit 0、`check-all --json` は `ok=true`
3. 新規に追加して**コミット済み**の `REV-9001` 行を書き換え → `check-all --json` は `ok=true`
4. 上記 1〜3 の状態でも、PRP-002 が追加した `test_append_only_hash_chain_is_enforced` は **PASS**（テストが改竄を行わず、きれいなファイルが読めることだけを確認しているため）

したがって「13 の自動検査は通るが、DoD の不変条件は成立しない」という結果です。承認・land は行わず、PRP-002 revision 2 で C2/A1 を実装し直すべきです。

第二の所見として、**C3/A2 の `review_line_sha256` は必須化されていません**。提案 §3 は「PRP-002 以降は必須化を validator で強制」と書きますが、実装は「存在する場合だけ照合」です。ハッシュのない承認 `APR-910` を fixture で追加したところ、`validate_researchos.py --quiet` は exit 0 でした。A1 が未修正であることと組み合わさると、承認後のレビュー差し替えを防ぐ実効的な錠がありません（本リポジトリの `APR-001` だけは自主的に `review_line_sha256` を持っているため、REV-001 の改竄は validator が検出します。ただしそれは当該 1 件限りです）。

## 2. 13 検査の実行結果（13/13 pass）

実行コマンド:

```bash
python3 scripts/researchos_verify.py --proposal PRP-002 --session SES-f99f5b7f
# exit 0 / result pass / 13 checks（--write は使わず、記録は REV-003 として別途追記）
```

| # | check | result | 主な根拠 |
| ---: | :--- | :--- | :--- |
| 1 | `policy` | pass | `check-policy` PASS |
| 2 | `schema_and_integrity` | pass | `validate_researchos.py --quiet` exit 0 |
| 3 | `regression_tests` | pass | `Ran 57 tests ... OK`（§14 の記載は 52 件。下記 §5） |
| 4 | `benchmark_reproducible` | pass | `benchmark.py --check` PASS |
| 5 | `readout_snapshot` | pass | 5 キーすべて committed snapshot と一致 |
| 6 | `append_only` | pass | クリーンな状態で `check-append-only` PASS |
| 7 | `role_guard` | pass | `check-commits --stage propose` exit 0 |
| 8 | `bootstrap_land_requires_approval` | pass | probe `enforced=true` |
| 9 | `merge_commits_are_audited` | pass | probe `enforced=true` |
| 10 | `approval_consistency` | pass | probe `enforced=true` |
| 11 | `distinct_reviews` | pass | probe `enforced=true` |
| 12 | `governance_review` | pass | 4 probes 集約 |
| 13 | `role_separation` | pass | reviewer `SES-f99f5b7f` ≠ proposer `SES-5491cb12` |

`verifications/prp001_governance_probes.py` も単独で exit 0、4/4 `enforced=true` です。

**重要:** 6 番の `append_only` は「クリーンな状態で PASS」しただけです。以下 §3 の改竄状態でも PASS します。13/13 は「改竄されていない現在の木」に対する結果であり、追記専用性の証明ではありません。

## 3. 反証テスト（blocking finding: C2/A1）

すべて `/tmp` の使い捨てコピーで実行し、本リポジトリの保護対象ファイルは変更していません。

### 3.1 REV-001 の summary をその場で書き換え

```bash
cp -a /home/user/ResearchOS /tmp/final-tamper && cd /tmp/final-tamper
python3 - <<'PY'
import json
from pathlib import Path
p = Path('state/reviews.jsonl'); lines = p.read_text().splitlines()
r = json.loads(lines[0]); r['summary'] = 'TAMPERED at final HEAD'
lines[0] = json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
p.write_text('\n'.join(lines) + '\n')
PY
python3 scripts/researchos_guard.py check-append-only
# => PASS: append_only / exit 0

python3 - <<'PY'
import sys; sys.path.insert(0, 'scripts')
import researchos_guard as g
print(g._check_hash_chain_for_file('state/reviews.jsonl'))
PY
# => []
```

- PRP-002 §2 の受入条件「`check-append-only` がハッシュ鎖不正で exit 1」「REV-001 行を改変した一時ファイルでエラー」に **反します**。
- `validate_researchos.py --quiet` は `APR-001.review_line_sha256` の不一致で exit 1 になります。これは A2 の部分的成功ですが、**guard の C2/A1 は失敗**です。

### 3.2 REV-001 行の削除

```bash
# 直前の /tmp/final-tamper で REV-001 行を削除
python3 scripts/researchos_guard.py check-append-only
# => PASS: append_only / exit 0

python3 scripts/researchos_guard.py check-all --json
# => {"ok": true, "results": {"policy": [], "append_only": [], "commits": [], "authorship": []}} / exit 0
```

- `validate_researchos.py` は `APR-001` が `REV-001` を参照できないため exit 1 になりますが、**guard の `check-all` は ok=true** です。§14 item 6 の「台帳追記専用性・真正性維持（check-all ok=true）」は、この状態推移で成立しません。

### 3.3 新規追加・コミット済み行の書き換え（A1 の一般形）

```bash
cp -a /home/user/ResearchOS /tmp/actual-tamper2 && cd /tmp/actual-tamper2
# REV-9001 を追記し、verifier 名義でコミット
# その後 REV-9001 の summary だけを書き換え
python3 scripts/researchos_guard.py check-append-only   # PASS / exit 0
python3 scripts/researchos_guard.py check-all --json    # ok=true / exit 0
```

- `state/reviews.jsonl` は `e236b57` で **空ファイル**として作られ、その後の行はすべて「追記」です。`_historical_text` は作成コミット（空）を基準にするため、前方一致検査の対象行が存在しません。
- `resolve_effective` のハッシュ鎖は **同一 ID の revision 間**の `supersedes` だけを検査します。最新行（revision 1 の行や、まだ supersede されていない最新 revision）はどこからもハッシュで固定されていません。したがって「追加済みの最新行を書き換える」攻撃は検出できません。
- これは PRP-002 §2 が約束した「各ファイルの全行をローリングハッシュ鎖で検証」「単なる前方一致では保護されない追記行の書き換え (A1) はハッシュ鎖で検出」と一致しません。

### 3.4 追加されたテストは改竄を検査していない

`tests/test_governance.py::RepositoryStateTest::test_append_only_hash_chain_is_enforced` は、改竄をシミュレートせず、**きれいな `state/reviews.jsonl` を `resolve_effective` に通してエラーがないこと**だけを確認しています。改竄済みの木でも PASS します。

```bash
# /tmp/actual-tamper2（REV-9001 を書き換え済み）で
python3 -m unittest tests.test_governance.RepositoryStateTest.test_append_only_hash_chain_is_enforced
# => Ran 1 test ... OK
```

PRP-002 §2 は「REV-001 行の 1 文字書き換えが check_append_only で FAIL することを検証」と明記していますが、テストはそれをしていません。

### 3.5 根因と修正方向

- 現行の「ハッシュ鎖」は **ID ごとの revision 鎖**であり、ファイル全体の鎖ではありません。最新行のハッシュを次の行（またはファイル末尾のアンカー）が含む構造になっていません。
- `state/reviews.jsonl` / `state/approvals.jsonl` の作成時点は空ファイルです。`check_append_only` は作成コミットとの前方一致しか見ないため、空の baseline では全行が無保護です。
- 修正案:
  1. **HEAD との比較**を append-only の基本にする（未コミットの改竄は HEAD との差分で必ず検出できる）。コミット済みの改竄は、各コミットで既存行が変わっていないことを `git log -p` / `git diff <parent> <commit>` で検査する。
  2. もしくは、各行に直前行のハッシュ（`prev_line_sha256`）を持たせ、**ファイル末尾の head ハッシュ**をコミットトレーラーや承認記録などの外部アンカーに固定する。最新行を含む全行が鎖に入る。
  3. `test_append_only_hash_chain_is_enforced` を、一時ファイルを実際に 1 文字改変して `check_append_only(...) != []` を assert するテストに置き換える（現行テストは無意味）。

## 4. C3/A2: `review_line_sha256` は必須化されていない

提案 §3 は「`review_line_sha256` を推奨必須フィールドとして追加 ... PRP-002 以降は必須化を validator で強制」としています。しかし:

- `schemas/approval.json` の `required` に `review_line_sha256` はありません（`properties` のみ）。
- `validate_governance` は `expected_hashes = approval.get(...)` が truthy のときだけ照合します。欠落は検査しません。

検証（`/tmp/t9`、本リポジトリのコピー）:

```text
REV-910（13 checks all pass）を追記
APR-910（approved、review_ids=[REV-910]、review_line_sha256 なし）を追記
python3 scripts/validate_researchos.py --quiet
=> exit 0
```

つまり、承認者がハッシュを省略すれば、承認とレビュー内容の束縛は成立しません。A1 が未修正の現状では、これは実効的な防御になりません。少なくとも PRP-002 以降の承認では `review_line_sha256` を必須にし、欠落を error にすべきです（`APR-001` は祖父条項で warning 可）。

## 5. §14 DoD の文字どおりの受入コマンド

| §14 | コマンド / 条件 | 結果 |
| :--- | :--- | :--- |
| 1 | `python3 verifications/prp001_governance_probes.py` | **pass**（exit 0、4/4 enforced=true） |
| 2 | `python3 verifications/prp002_design_probes.py` | **fail**（ファイルが存在しない）。`researchos_verify.py` は 4 つの G-probe を統合していますが、V1-V13 の 12 項目を実行する probe ではありません |
| 3 | `check-commits --stage propose --json` | **fail**（exit 2。`check-commits` に `--json` 引数がない。DoD は exit 2 を明示的に禁止） |
| 3 | `check-commits --stage land --json` | **fail**（同上、exit 2） |
| 3 | `check-all --stage land --json` | 動作する（未承認のため exit 1。承認後の exit 0 は未検証） |
| 4 | `validate_researchos.py --quiet` | **pass**（exit 0） |
| 5 | `unittest discover -s tests` | **pass**（57 tests OK。ただし §14 の記載は 52 件） |
| 5 | `benchmark.py --check` | **pass** |
| 5 | `readout.py --quiet --format json` | **pass**（snapshot 一致） |
| 6 | `check-all --json` / `check-authorship` | クリーンな状態では **pass**（ok=true / PASS）。ただし §3 の改竄状態でも ok=true になり、不変条件は失敗 |
| 7 | docs / roles / approval schema | **pass**（R4 ハッシュ鎖、R6 land 例外、照合手順、bootstrap 説明、`review_line_sha256` の存在を確認） |

補足:

- `check-commits --stage propose`（`--json` なし）は exit 0、`--stage land` は未承認のため exit 1 で、**stage 機能自体は動いています**。欠けているのは `--json` だけです。CI も `--json` なしで呼んでいるため、CI の land ゲートは機能的には動きます。
- テスト件数 57 は 52 より多い（追加テスト自体は PASS）。数字の更新漏れであり、機能的な失敗ではありません。
- `verifications/prp002_design_probes.py` の欠落は、V1-V13 の実行可能な受入証跡がないことを意味します。V1/V4/V9/V13 の一部は 13 checks とコードで間接的に確認できますが、V7（synthetic SHA）、V8（fixture）、V11（next.py）、V12（DoD）を独立に再実行する probe はありません。

## 6. 独立に確認できた修正（positive）

以下は `/tmp` のコピーで実際の Git 操作を行い、修正が効いていることを確認しました。

| 欠陥 | 検証 | 結果 |
| :--- | :--- | :--- |
| **F1** 非 HEAD のセッション詐称 | verifier ブランチで `Session-Id: SES-5491cb12` のコミットを作成 → `check-commits` | **FAIL 検出**（`session ... belongs to branch arena/5491cb12-researchos, not arena/f99f5b7f-researchos`） |
| **F2** merge 監査 | トレーラーなしの side commit を `--no-ff` merge → `check-commits` | **FAIL 検出**（side commit の trailers 欠落 + governance path） |
| **F2** merge 自体の監査 | トレーラーなしの merge commit → `check-commits` | **FAIL 検出**（merge commit の trailers 欠落） |
| **F4** close 例外 | `researchos_session.py close` のコミット → `check-commits` / その後のコミット | close コミットは **PASS**、post-close は **FAIL**（`session is closed`） |
| **G1** bootstrap land | probe | `enforced=true` |
| **G3** 承認整合性 | probe + `validate_governance` | `enforced=true` |
| **G4** 同一セッションの複数レビュー | REV-8101/REV-8102 を同一セッションで追記 → `queue complete --review REV-8101` | **成功**（exit 0） |
| **A2** ハッシュ不一致（存在する場合） | REV-001 改竄 → validator | **exit 1**（`review_line_sha256 mismatch`） |

F1/F2/F4/G4 の修正は、少なくとも今回の再現方法に対しては有効です。C2/A1 だけが設計と実装が一致していません。

## 7. 再現手順（要約）

```bash
# 1. 13 checks
python3 scripts/researchos_verify.py --proposal PRP-002 --session SES-f99f5b7f

# 2. §14 probes
python3 verifications/prp001_governance_probes.py

# 3. 反証（使い捨てコピーで）
cp -a /home/user/ResearchOS /tmp/final-tamper
cd /tmp/final-tamper
# REV-001 の summary を書き換える
python3 scripts/researchos_guard.py check-append-only          # exit 0 (expected 1)
python3 -c "import sys;sys.path.insert(0,'scripts');import researchos_guard as g;print(g._check_hash_chain_for_file('state/reviews.jsonl'))"
# => []
# REV-001 行を削除する
python3 scripts/researchos_guard.py check-all --json            # ok=true (expected false)

# 4. コミット済みの追記行を書き換える
#    (REV-9001 を追記・コミット → summary を書き換え)
python3 scripts/researchos_guard.py check-all --json            # ok=true
```

## 8. 並行線路と ID の扱い

- `arena/363c9e54-researchos` には、同じ PRP-002 に対する **REV-002（fail、`check-commits --json` の exit 2 を根拠）** と、RQ-002 の claim（revision 3）が既にあります。本セッションはこのブランチを merge せず、proposer tip `a997498` から独立に検証しました。
- レビュー ID は **REV-003** を使用しました。REV-002 は並行線路で使用済みのため、union 時の duplicate revision を避けるための意図的な採番です（`docs/GOVERNANCE.md` §6 の「並行線路では手動で一意な suffix」に相当）。
- ただし **RQ-002 の revision 3 は両線路で衝突**します（本線: claim → complete の rev3/rev4、並行線: claim の rev3）。union する場合は §6 の手順で `supersedes` を付け替え、必要なら queue の履歴を手動照合してください。これは PRP-002 の既知の残存リスク（A5/PRP-003）です。

## 9. 推奨

1. **PRP-002 を承認しない。** A1/C2 は提案の中心的な受入条件であり、現状は §2 の受入テストに失敗します。
2. PRP-002 revision 2 で、append-only を「HEAD との比較」または「ファイル全体の head アンカー付きハッシュ鎖」に作り直す。最新行を固定する仕組みを必須にする。
3. `review_line_sha256` を PRP-002 以降の承認で必須化する（欠落 = error、APR-001 のみ warning）。
4. `check-commits --json` を実装するか、§14 のコマンドを `check-all --json` に修正する。
5. `prp002_design_probes.py` を追加するか、V1-V13 の検証方法を §14 に明記する。
6. `test_append_only_hash_chain_is_enforced` を実際の改竄テストに置き換える（現在は無意味）。
7. テスト件数の記載を 57 に更新する。

## 10. 限界（正直な記載）

- 本検証はリポジトリ内のコードと Git 履歴に基づきます。ガード自身を書き換える権限を持つセッションに対する暗号学的保証はありません（GOVERNANCE.md §5/§8 の既知の限界）。
- 反証テストは `/tmp` のコピーで行い、本リポジトリの `scripts/`, `schemas/`, `policy/`, `tests/`, `.github/` は変更していません。本セッションの書き込みは `state/sessions.jsonl`, `state/review_queue.jsonl`, `state/reviews.jsonl`, `verifications/**` に限られます。
- 13 checks の pass は、改竄されていない現在の木に対する実行結果です。§3 のとおり、改竄状態でも同じ 13 checks のうち `append_only` は pass します。

---

*Verifier: SES-f99f5b7f — 2026-10-19。REV-003 / RQ-002 completed。*
