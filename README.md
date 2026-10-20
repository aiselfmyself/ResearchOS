# ResearchOS

研究オペレーティングシステムの最小コア。研究の状態・証拠・実行・検証・履歴をモデルの外側で管理するための、小さく再実行可能な起点である。

> **状態（2026-10-20）**：2026-10-19 の実装線路はガバナンス機構の自己言及ループに陥り、`main` へのマージが0件のまま停滞した。経緯と分析は `docs/stagnation-analysis-2026-10-20.md`、最小コアへの立て直し方針は `docs/minimal-core-and-ci.md` を参照。本ブランチは「再実行できるものだけを `main` に載せる」ための最小抽出である。
>
> **同日の追加**：未完了要素の棚卸し（`docs/incomplete-work-audit-2026-10-20.md`）の指摘に基づき、統合レポート（`contributions/2026-10-20_integrated_survey_report.md`）、共通モード障害の決定論的測定（`gitswarm/readout_sim.py`）、反証の紐付け、既知の誤記2件の訂正、出典7件の台帳登録を行った。台帳は sources=11 / evidence=19 / claims=11 / verifications=32 / hypotheses=3。

## 構成

```text
task/                  研究課題定義（Long-Horizon Agent Architectures 文献調査）
schemas/               研究オブジェクトのスキーマ（source/evidence/claim/verification/hypothesis）
state/                 研究台帳（JSONL。監査訂正済みデータ）
scripts/
  validate_state.py    研究台帳の決定論的検証器（標準ライブラリのみ）
  new_id.py            非連番レコードIDの採番器（並行作業のID衝突対策）
  check_citations.py   書誌のarXiv照合（オフラインfixture、--liveは手動専用）
  check_memo_citations.py 調査メモ内引用のarXiv照合（オフラインfixture、--liveは手動専用）
  check_ownership.py   並行作業の所有マップによるパス分類（助言専用・CI非接続）
gitswarm/
  problem.py solvers/  30都市TSPの決定論的ソルバ群（greedy/random/two_opt/SA）
  benchmarks/          複数シード実行＋成果物照合（--write/--check）
  readout.py           GitSwarm readout解析器（履歴が貯まれば使う道具）
  readout_sim.py       同質ワーカーの多数決＝共通モード障害の決定論的測定（--write/--check）
  artifacts/           実行で再生成できる成果物（ベンチマーク行列・投票スイープ行列）
tests/
  fixtures/            arXiv書誌スナップショット（オフライン照合用・2026-10-20取得）
  test_minimal_core.py    履歴非依存の回帰テスト（34件）
  test_check_citations.py 書誌照合テスト（17件・ネットワーク非依存）
  test_check_memo_citations.py メモ引用照合テスト（33件・ネットワーク非依存）
  test_ownership.py       所有マップ分類テスト（16件・ネットワーク非依存）
  test_readout_sim.py     投票スイープの回帰・閾値予測テスト（20件・ネットワーク非依存）
contributions/         研究ノート（統合レポート・調査メモ・全文読解レポート・共通モード測定）
docs/                  分析レポートと設計記録（並行作業の所有マップは docs/parallel-work-ownership.md。強制力なし）
.github/workflows/
  core-check.yml       最小CI（テスト＋ベンチマーク再現性＋投票シミュレーション再現性＋台帳検証＋書誌照合）
```

## 使い方

```sh
# 1. テスト（約5秒・110件）
python3 -m unittest discover -s tests -v

# 2. ベンチマークの再現性確認（fresh実行と成果物の照合）
python3 gitswarm/benchmarks/benchmark.py --check

# 3. 共通モード障害の測定の再現性確認（fresh実行と成果物の照合）
python3 gitswarm/readout_sim.py --check

# 4. 研究台帳の検証
python3 scripts/validate_state.py

# 5. 書誌のarXiv照合（オフラインfixtureのみ。ネットワーク不要）
python3 scripts/check_citations.py

# 6. 調査メモ内引用のarXiv照合（オフラインfixtureのみ。CIゲート対象）
python3 scripts/check_memo_citations.py

# 成果物の再生成（実行できることの証明。数値は不変のはず）
python3 gitswarm/benchmarks/benchmark.py --write
python3 gitswarm/readout_sim.py --write
```

CI（`core-check.yml`）は上記1〜6をゲートする。Python 3.12固定。

## 意図的に含まれないもの（ガバナンス凍結）

役割分離・追記専用台帳・レビューキュー・コミットtrailer検査・landゲートは含まない。これらは形式的完全性を追求する過程で進捗を止めたため、凍結中である（記録は `arena/*` ブランチに残る）。凍結の解除には「DoDを3行以内で先に書く」ことが条件。詳細は `docs/minimal-core-and-ci.md` §1.2。

## 次の段階（設計思想レポートのPhase順序に従う）

1. 単一Workerのベースライン：`task/TASK.md` の文献調査を人間が読める短いレポートとして完成させる ✅ 完了（2026-10-20：`contributions/2026-10-20_integrated_survey_report.md`。`task/TASK.md` §4 の Integrator 統合レポート。§2 の目的1〜3を証拠の強弱4段階で論証）
2. 捏造対策は1点に絞る：arXiv APIによる引用の機械照合 ✅ 完了（2026-10-20：`scripts/check_citations.py`。オフラインfixture照合をCIでゲート、実API照合 `--live` は手動専用）
3. 共通モード障害の直接測定 ✅ 一部完了（2026-10-20：`gitswarm/readout_sim.py`。決定論的投票モデルで増幅の条件を測定。**ただしワーカーはモデル上の標本であり、実 LLM ワーカー群の追従率 `rho` と共有見解の正しさ `c` は未測定**。測定の限界は `contributions/2026-10-20_common_mode_measurement.md` §6）
4. その後、必要性が実証されたときに複数Worker・Supervisor・検証の拡張を検討する（Phase 4は最後）
