# 最小コアと最小CIの設計（ガバナンス凍結の実施記録）

- 作成日：2026-10-20
- 背景：`docs/stagnation-analysis-2026-10-20.md` の処方箋1・2の実施
- 方針：**「再実行できるものだけを `main` に載せる」**。形式的完全性の追求は凍結する。

---

## 1. 最小コアの選定基準

`arena/955f8586-researchos`（PR #9）の内容を次の基準でふるいにかけた：

- ✅ 含める：標準ライブラリのみで動き、**このリポジトリ自身のgit履歴に依存せず**、再実行で検証できるもの
- ❌ 除く：ガバナンス機構（役割・台帳・キュー・ゲート）、履歴依存のテスト、単一プロセスのロールプレイ

### 1.1 含めたもの（と理由）

| 部品 | 出典 | 含めた理由 |
|---|---|---|
| `gitswarm/problem.py`、`solvers/` 4種 | PR #9そのまま | 決定論的TSPソルバ。履歴非依存 |
| `gitswarm/benchmarks/benchmark.py` | PR #9そのまま | `--write`/`--check` で再実行検証できる。監査で「手書きベンチマークを再現不能にした」と確認済みの、実際に効いた対策 |
| `gitswarm/artifacts/benchmark_matrix.json` | 再生成（数値は旧版と完全一致を確認） | 実行で作り直せること自体が検証 |
| `gitswarm/readout.py` | PR #9そのまま | GitSwarm readout解析器。履歴が貯まれば使う道具 |
| `schemas/` 研究5種、`state/` 研究5台帳 | PR #9そのまま（訂正済みデータ） | 監査の訂正（著者名・引用種別・CLM-003格下げ）を活かす |
| `task/TASK.md` | PR #9（§4の検証器参照のみ更新） | 本来の研究課題定義 |
| `contributions/` 2件 | PR #9そのまま | 研究ノート（小規模・無害） |
| `scripts/validate_state.py` | **新規**（約200行） | 研究5台帳専用の小さな検証器。旧 `validate_researchos.py`（858行）はガバナンス台帳・役割分離・trailer検査と結合していたため不採用 |
| `tests/test_minimal_core.py` | **新規**（18テスト） | 履歴非依存テスト。旧 `test_integrity.py` はコミット数・SHA・ガバナンス台帳に結合していたため不採用（詳細は §3） |
| `.gitignore` | PR #9そのまま | — |

### 1.2 除いたもの（と理由）

| 部品 | 除いた理由 |
|---|---|
| `scripts/researchos_{guard,session,queue,verify,next,common}.py`、`scripts/build_state_baseline.py` | ガバナンス・ハーネス本体。F1/A1で迂回可能性が実証済み。凍結 |
| `scripts/validate_researchos.py`、`scripts/run_researchos_pilot.py` | 前者はガバナンス結合、後者は単一プロセスで役割コミットを自動生成する（監査が批判したロールプレイの自動化）。不採用 |
| `gitswarm/run_simulation.py`、`artifacts/worker*.json`、`artifacts/readout_snapshot.json` | 偽装ワーカー名義のコミットを量産するシミュレーションとその生成物。スナップショットは旧履歴のSHAを含むため新履歴では無意味 |
| `tests/test_governance.py`、`tests/test_integrity.py` | 前者はガバナンス、後者は旧履歴（コミット数7・候補5・SHA）にハードコード依存 |
| `schemas/` ガバナンス5種、`state/` ガバナンス5台帳＋`plan.md`＋`NEXT_SESSION.md` | 提案・レビュー・承認・キュー・セッション台帳。凍結。引き継ぎは人間の判断に戻す |
| `policy/`、`docs/GOVERNANCE.md` | ガバナンス定義。凍結（`arena/*` ブランチに記録として残る） |
| `reports/`、`verifications/`、`docs/GOVERNANCE.md` | 旧線路の監査・検証ログ。履歴資料として旧ブランチに残し、`main` には載せない |
| `.github/workflows/verify-github-actions.yml`、`negative-test.yml` | ガバナンス検査・landゲート（故障中）・動作確認用。最小CIに置換 |

---

## 2. 最小CIの設計（`.github/workflows/core-check.yml`）

ゲートするのは決定論的・再実行可能な3検査のみ：

1. `python3 -m unittest discover -s tests -v` — 18テスト（約2秒）
2. `python3 gitswarm/benchmarks/benchmark.py --check` — 成果物と fresh run の照合（許容誤差0.01）
3. `python3 scripts/validate_state.py` — 研究台帳のスキーマ・ID一意・参照整合性

設計上の決定：

- **shallow checkoutでよい**：テストは合成リポジトリでreadoutを検証し、本リポジトリの履歴を読まない
- **Python 3.12に固定**（`setup-python`）：ベンチマーク数値の決定性を環境変動から守る。TOLERANCE=0.01と `round()` があるため3.11でも同一値を確認済みだが、CIは固定する
- **readout CLIはゲートしない**：履歴にworkerコミットがない間は exit 1 が正常であり、freshな `main` を赤くする理由にならない（A7の教訓：正常状態を失敗として検出するゲートを作らない）
- **何を足さないか**：trailer検査、役割検査、append-only検査、landゲート、成果物アップロード、動作確認用の計算テスト。これらは凍結であり、欠落ではない

---

## 3. なぜ旧テストをそのまま持ってこなかったか

旧 `tests/test_integrity.py` の結合先：

- `readout` の期待値が旧履歴に固定（worker commit 7件・候補5件・指標100/100/80・`winning_candidate_sha`）
- `vr.run_all_checks()` がガバナンス5台帳＋10スキーマを必須とする
- → 新しい `main` の履歴（数コミット）では必ず失敗する。**「正しいコードが赤くなるテスト」はA7そのもの**であり、持ち込みは停滞の再発である

新 `tests/test_minimal_core.py` は監査の教訓だけを移植した：

- ベンチマーク再実行一致（＋solverハッシュ束縛で強化）
- readoutのパススコープ（合成リポジトリで再現）
- 著者名訂正・引用種別・CLM-003格下げ（訂正済みデータの固定）
- 否定テスト（不正enum・型・必須欠落・ダングリング参照・ID重複）

---

## 4. このPRのDoD（Definition of Done）

> 1. 最小CI（3検査）がこのブランチで緑であること
> 2. 人間が `main` へのマージを承認すること
> 3. マージ後に `main` のCIが緑であること

以上。ガバナンス台帳・レビューキュー・複数役割の承認はDoDに含めない（凍結中のため）。
