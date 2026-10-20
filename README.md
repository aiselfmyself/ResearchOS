# ResearchOS

研究オペレーティングシステムの最小コア。研究の状態・証拠・実行・検証・履歴をモデルの外側で管理するための、小さく再実行可能な起点である。

> **状態（2026-10-20）**：2026-10-19 の実装線路はガバナンス機構の自己言及ループに陥り、`main` へのマージが0件のまま停滞した。経緯と分析は `docs/stagnation-analysis-2026-10-20.md`、最小コアへの立て直し方針は `docs/minimal-core-and-ci.md` を参照。本ブランチは「再実行できるものだけを `main` に載せる」ための最小抽出である。

## 構成

```text
task/                  研究課題定義（Long-Horizon Agent Architectures 文献調査）
schemas/               研究オブジェクトのスキーマ（source/evidence/claim/verification/hypothesis）
state/                 研究台帳（JSONL。監査訂正済みデータ）
scripts/
  validate_state.py    研究台帳の決定論的検証器（標準ライブラリのみ）
  new_id.py            非連番レコードIDの採番器（並行作業のID衝突対策）
gitswarm/
  problem.py solvers/  30都市TSPの決定論的ソルバ群（greedy/random/two_opt/SA）
  benchmarks/          複数シード実行＋成果物照合（--write/--check）
  readout.py           GitSwarm readout解析器（履歴が貯まれば使う道具）
  artifacts/           実行で再生成できるベンチマーク行列
tests/
  test_minimal_core.py 履歴非依存の回帰テスト（28件）
contributions/         研究ノート
docs/                  分析レポートと設計記録
.github/workflows/
  core-check.yml       最小CI（テスト＋ベンチマーク再現性＋台帳検証）
```

## 使い方

```sh
# 1. テスト（約2秒）
python3 -m unittest discover -s tests -v

# 2. ベンチマークの再現性確認（fresh実行と成果物の照合）
python3 gitswarm/benchmarks/benchmark.py --check

# 3. 研究台帳の検証
python3 scripts/validate_state.py

# 成果物の再生成（実行できることの証明。数値は不変のはず）
python3 gitswarm/benchmarks/benchmark.py --write
```

CI（`core-check.yml`）は上記1〜3だけをゲートする。Python 3.12固定。

## 意図的に含まれないもの（ガバナンス凍結）

役割分離・追記専用台帳・レビューキュー・コミットtrailer検査・landゲートは含まない。これらは形式的完全性を追求する過程で進捗を止めたため、凍結中である（記録は `arena/*` ブランチに残る）。凍結の解除には「DoDを3行以内で先に書く」ことが条件。詳細は `docs/minimal-core-and-ci.md` §1.2。

## 次の段階（設計思想レポートのPhase順序に従う）

1. 単一Workerのベースライン：`task/TASK.md` の文献調査を人間が読める短いレポートとして完成させる
2. 捏造対策は1点に絞る：arXiv APIによる引用の機械照合
3. その後、必要性が実証されたときに複数Worker・Supervisor・検証の拡張を検討する（Phase 4は最後）
