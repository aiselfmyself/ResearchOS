# ResearchOS

**GitSwarm 型の自律研究オペレーティングシステム（プロトタイプ）**

ResearchOS は、研究状態を会話履歴から分離し、Git リポジトリを「不変の構造化共有メモリ」として使う研究ワークフローです。Supervisor / Worker / Critic / Verifier / Integrator の役割を `Informed-By` の意味的依存で連鎖させ、アトミックコミットとして推論の途中成果を蓄積します。

- **研究課題:** 自律型 AI エージェントにおける長期推論・分散協調アーキテクチャ（Stateless vs GitSwarm）
- **実行環境:** Arena.ai Agent Mode × GitHub
- **前セッション:** `arena/01673a58-researchos`（`8763d08`）
- **本ブランチ:** `arena/c4426c6b-researchos`（独立検証 `Auditor-01`）

> **重要:** `gitswarm/` は **プロトコルレベルのシミュレーション** です。単一プロセスがワーカー役を逐次演じるものであり、非同期・独立コンテキストのマルチエージェント実行環境ではありません。詳細は [`reports/independent-verification-report.md`](reports/independent-verification-report.md) を参照してください。

---

## クイックスタート

```bash
# 1. 決定論的検証（スキーマ・ID 一意性・参照整合性・Informed-By の祖先関係）
python3 scripts/validate_researchos.py

# 2. 回帰テスト（監査 Findings の固定）
python3 -m unittest discover -s tests -v

# 3. GitSwarm ベンチマークの再現性チェック
python3 gitswarm/benchmarks/benchmark.py --check

# 4. GitSwarm readout（既定は gitswarm/ にスコープ）
python3 gitswarm/readout.py

# 5. プロトコル・シミュレーション（既定はドライラン推奨）
python3 gitswarm/run_simulation.py --dry-run
```

### ベンチマーク成果物の再生成

```bash
python3 gitswarm/benchmarks/benchmark.py --write
```

`gitswarm/artifacts/benchmark_matrix.json` には `_meta`（seeds / random_iterations / SA パラメータ / Python / platform / solver SHA-256 / git HEAD）と `per_seed` が含まれます。

---

## ディレクトリ構成

| パス | 役割 |
| :--- | :--- |
| `task/TASK.md` | 研究課題・Ground Truth 要件・検証プロトコル |
| `state/` | 研究状態（sources / evidence / claims / verifications / hypotheses / plan） |
| `schemas/` | JSON Schema（source / evidence / claim / verification / hypothesis） |
| `scripts/validate_researchos.py` | 決定論的検証器（依存ライブラリなし） |
| `gitswarm/problem.py` | 30都市 Euclidean TSP |
| `gitswarm/solvers/` | greedy / random search / 2-opt / simulated annealing |
| `gitswarm/benchmarks/benchmark.py` | 5シード・ベンチマーク（`--write` / `--check`） |
| `gitswarm/readout.py` | 推薦集計と Compounding 指標（パス・スコープ対応） |
| `gitswarm/run_simulation.py` | 7ワーカーエピソードのプロトコル・シミュレーション |
| `tests/` | 監査 Findings を固定する回帰テスト |
| `reports/` | 研究統合・GitSwarm 検証・独立監査レポート |
| `contributions/` | 各ワーカーの調査ノート |
| `verifications/` | 反証レポート・監査ログ |
| `.github/workflows/` | CI（validator / tests / benchmark drift check） |

---

## 研究状態のモデル

```
Source ──< Evidence ──< Claim ──< Verification
                         │
                         └──< Hypothesis
```

- **Source**: arXiv 等の一次資料（DOI / 著者 / 年 / URL）
- **Evidence**: 逐語引用・測定値・メタデータ照合（`quote_type` 必須）
- **Claim**: 証拠に紐づく主張（`candidate` / `supported` / `disputed` / `rejected`）
- **Verification**: 主張・出典・証拠に対する検証（`pass` / `fail` / `warn` / `falsified`）
- **Hypothesis**: 検証可能な仮説（`proposed` / `testing` / `supported` / `falsified` / `inconclusive`）

`Informed-By:` コミットトレーラは、物理的な親とは別に**意味的な依存**を記録します。検証器は、引用先が実在するだけでなく、**引用元の祖先である**ことも確認します。

---

## 現在の検証状況（2026-10-19）

| チェック | 結果 |
| :--- | :--- |
| `scripts/validate_researchos.py` | PASS（4 Sources / 14 Evidence / 7 Claims / 21 Verifications / 3 Hypotheses） |
| `python3 -m unittest discover -s tests -v` | 15 tests OK |
| `benchmark.py --check` | PASS |
| `readout.py`（`gitswarm/` スコープ） | 7 worker commits / 5 candidates / reuse 100% / negative 100% / ancestry 80% |

### 独立監査で判明した主な訂正

1. `benchmark_matrix.json` は実行値ではなく手書き値だった。再実行値は SA 4410.25 → **4731.96**、two_opt 4792.40 → **4739.72**。SA の優位性は **0.16%**。
2. `SRC-001` / `SRC-003` の著者名が誤っていた（正: **Qizheng Zhang** / **Shubham Agarwal**）。
3. `EVD-001` / `EVD-004` の逐語引用は原文に存在しなかった。
4. `readout.py` は履歴全体を走査し、指標がスコープ依存だった。
5. 旧検証器は型・enum・ID 重複・`Informed-By` の祖先関係を検査していなかった。

詳細: [`reports/independent-verification-report.md`](reports/independent-verification-report.md)

---

## 既知の限界

- 非同期・独立ワーカーの実運用は未検証（本リポジトリは逐次シミュレーション）。
- ベンチマークは 30都市 TSP・5シードの toy 規模。
- `CLM-003`（多数決の危険性）は `candidate`。均質投票の誤り増幅を直接測った実験はない。
- arXiv メタデータは 2026-10-19 時点の照合結果。

---

## ライセンス

このリポジトリは研究プロトタイプです。引用文献の著作権は各原著者に帰属します。
