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
| `scripts/new_id.py`、`docs/record-id-scheme.md` | **新規**（2026-10-20） | 非連番IDの採番器と規約。並行ブランチが同じ連番を採番して衝突する問題（A5と同型）を、ID側で原理的に解消する。役割・パス制限は導入しない |
| `scripts/check_citations.py`、`tests/fixtures/arxiv_metadata_snapshot.json`、`tests/test_check_citations.py` | **新規**（2026-10-20） | README「次の段階」2の最小実装。台帳書誌とarXivスナップショット（2026-10-20取得）の照合は標準ライブラリのみ・ネットワーク不要。実API照合（`--live`）は手動専用でCIゲートにしない |
| `scripts/check_memo_citations.py`、`tests/test_check_memo_citations.py`、fixture追記7件 | **新規**（2026-10-20） | 調査メモ（`contributions/*.md`）の参考文献・本文中arXiv引用と同梱スナップショットの照合。標準ライブラリのみ・ネットワーク不要、`--live` は手動専用。**CIゲート（core-check の6番目）に 2026-10-20 追加済み**（監査 ID 8）。同時に、arXiv ID もURLも持たない参照を黙って SKIP せず MALFORMED として失敗させるよう変更した（折り返し行の未検証を防ぐため） |
| `scripts/check_memo_ledger_refs.py`、`tests/test_check_memo_ledger_refs.py` | **新規**（2026-10-21、12テスト） | 調査メモ内の台帳ID参照（`SRC-`/`EVD-`/`CLM-`/`VER-`/`HYP-`）とリポジトリパス参照の存在検査。トークンパターンは `validate_state.py` から import しており、台帳側とメモ側の規則がずれることはない。**CIゲート（core-check の7番目）に 2026-10-21 追加済み**。動機と限界（意味的誤りは検出できない）は §2.1。アーカイブ済みIDは ARCHIVED として報告し失敗にしない。`--coverage`（未参照レコードの報告）はゲートにしない |
| `tests/test_minimal_core.py` | **新規**（28テスト） | 履歴非依存テスト。旧 `test_integrity.py` はコミット数・SHA・ガバナンス台帳に結合していたため不採用（詳細は §3） |
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

ゲートするのは決定論的・再実行可能な**7検査**（2026-10-21 時点。初版は4検査で、2026-10-20 に 5・6 を、2026-10-21 に 7 を追加した）：

1. `python3 -m unittest discover -s tests -v` — **184テスト**（約3〜5秒）
2. `python3 gitswarm/benchmarks/benchmark.py --check` — 成果物と fresh run の照合（許容誤差0.01）
3. `python3 gitswarm/readout_sim.py --check` — 投票シミュレーション成果物と fresh run の照合
4. `python3 scripts/validate_state.py` — 研究台帳のスキーマ・ID一意・参照整合性（**台帳内の** ID・パス参照の存在検査を含む）
5. `python3 scripts/check_citations.py` — 台帳書誌と同梱arXivスナップショットの照合（**オフライン・ネットワーク不要**。実API照合の `--live` は手動専用でゲートしない）
6. `python3 scripts/check_memo_citations.py` — 調査メモ（`contributions/*.md`）の参考文献・本文中arXiv引用と同梱スナップショットの照合（オフライン）
7. `python3 scripts/check_memo_ledger_refs.py` — 調査メモ内の**台帳ID参照とリポジトリパス参照の存在検査**（オフライン。2026-10-21 追加。後述 §2.1）

設計上の決定：

- **shallow checkoutでよい**：テストは合成リポジトリでreadoutを検証し、本リポジトリの履歴を読まない
- **Python 3.12に固定**（`setup-python`）：ベンチマーク数値の決定性を環境変動から守る。TOLERANCE=0.01と `round()` があるため3.11でも同一値を確認済みだが、CIは固定する
- **readout CLIはゲートしない**：履歴にworkerコミットがない間は exit 1 が正常であり、freshな `main` を赤くする理由にならない（A7の教訓：正常状態を失敗として検出するゲートを作らない）
- **arXiv APIへの実ネットワーク照合はゲートしない**：CIはネットワークなしだけで再実行できる同梱fixture照合（検査4）のみ。`--live` はarXivのレート制限も含め手動実行専用
- **何を足さないか**：trailer検査、役割検査、append-only検査、landゲート、成果物アップロード、動作確認用の計算テスト。これらは凍結であり、欠落ではない

## 2.1 検査7（メモ内の台帳ID・パス参照）を足した理由と限界

**動機**：`contributions/2026-10-20_integrated_survey_report.md` §3.4 が記録した
「理解と生成の非対称」——現在のモデルは複雑な文脈の**理解**には熟達するが、同等に洗練された
**長文の生成**には限界を示す——は、本リポジトリに直接当てはまる。本リポジトリは長文の執筆
（調査メモ・監査文書・統合レポート・PR本文）をエージェントに委任している。

実際に 2026-10-21 までに、エージェントが書いた長文から**機械検査でしか検出できない問題**が
3 件出ている。

| # | 内容 | 検出したもの |
|---|---|---|
| a | 文献メモが arXiv:2605.23950 を「実験を持たない」と記述（実際は自前の 3×3 実験を持つ） | 並列照合セッションの逐語照合 |
| b | context engineering の 3 構成要素を「階層」と記述（原典は平坦な列挙） | 同上 |
| c | メモに記載されたコマンドが存在しないファイル名（日付テンプレート `2026-10-2X`）を指す | **検査7**（本検査） |

**検査7は (a)(b) を検出できない。** これらは意味的な誤りであり、原典と突き合わせなければ
分からない。検査7が検出できるのは**参照が解決しない**こと——存在しない台帳IDの引用
（誤記または幻覚）、存在しないパスの参照——だけである。
**何を検出しないかを明示したうえで置く。** 検出範囲を過大に宣言しない。

**アーカイブ済みIDの扱い**：2026-10-20 に台帳から除いたレコード（CLM-004/005/007 ほか）は
`docs/archived-ledger-records-2026-10-20.md` に原文が残る。統合レポートはこれらを
「除外した」旨の記述で正当に参照しているため、**失敗ではなく ARCHIVED として報告**する。

**`--coverage` はゲートにしない**：どのメモからも参照されていない台帳レコードを報告する機能だが、
新規に起こした EVD は報告へ反映されるまで一時的に未参照になる。
**正常な状態を失敗として検出するゲートは作らない**（A7 の教訓）。

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

> 1. 最小CI（`core-check.yml` の**全ゲート**——2026-10-21 時点で **7 つ**）がこのブランチで緑であること
> 2. `main` へのマージ承認——**2026-10-21 の自律マージ方針により、統合役は CI 緑を確認して自律的にマージしてよい**（`docs/autonomous-merge-policy-2026-10-21.md` §2 の4条件を満たす場合）
> 3. マージ後に `main` のCIが緑であること

以上。ガバナンス台帳・レビューキュー・複数役割の承認はDoDに含めない（凍結中のため）。

**〔2026-10-21 訂正・統合役〕** 第1項は当初「3検査」と記していたが、CI は検査の追加に伴い
4 → 6 → 7 と増えた。**数値をハードコードすると必ず陳腐化する**ため、ゲート数の記述をやめ
「全ゲート」を条件とし、現在値を日付付きの参考として残す。第2項も、制定当時は人間の承認を
要したところ自律マージ方針の制定により変わったため、実態に合わせた。
（監査 ID 14 の解消。`docs/incomplete-work-audit-2026-10-20.md` §14 参照。）
