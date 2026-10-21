# ResearchOS

研究オペレーティングシステムの最小コア。研究の状態・証拠・実行・検証・履歴をモデルの外側で管理するための、小さく再実行可能な起点である。

> **状態（2026-10-20）**：2026-10-19 の実装線路はガバナンス機構の自己言及ループに陥り、`main` へのマージが0件のまま停滞した。経緯と分析は `docs/stagnation-analysis-2026-10-20.md`、最小コアへの立て直し方針は `docs/minimal-core-and-ci.md` を参照。本ブランチは「再実行できるものだけを `main` に載せる」ための最小抽出である。
>
> **同日の追加**：未完了要素の棚卸し（`docs/incomplete-work-audit-2026-10-20.md`）の指摘に基づき、統合レポート（`contributions/2026-10-20_integrated_survey_report.md`）、共通モード障害の決定論的測定（`gitswarm/readout_sim.py`）、反証の紐付け、既知の誤記2件の訂正、出典7件の台帳登録を行った。
>
> **2026-10-21 の進展（証拠の充実と誤りの訂正）**：3 セッションの並列照合（S1/S2/S3）が 6 論文 48 claim を原典と突き合わせ、統合役が裁定して **EVD 33 件を追加**した（evidence 14 → **47**）。**11 ソースすべてが 1 件以上の EVD を持つ**状態になった（照合開始前は 4/11）。照合の過程で**文献メモの誤り 2 件**を捕捉し、人間の承認を得て訂正した。
>
> - (a) arXiv:2605.23950 を「実験を持たない position paper」としていた誤り。原典 §4.2 は **3 モデル × 3 ハーネスの計画格子実験**を実施しており、**ハーネス分散はモデル分散の 7.80 倍**、**9 組中 6 組で順位逆転**を報告している。本リポジトリの問い（性能差はモデルか harness か）に対する最も直接的な先行測定だった。
> - (b) context engineering の 3 構成要素（Retrieval and Generation / Processing / Management）を「階層」としていた誤り。原典は**平坦な列挙**である。
>
> 統合レポートを**第2版**に改訂した（Agora 本文読解 §4.4・§5.6、自律研究の現在地 §5.7 を新設、[8] の自前実験を §3.3 に反映、各所の計数を更新）。監査 ID 15（SRC-004 への VER が 0 件）を解消し VER 2 件を追加した。**台帳は sources=11 / evidence=47 / claims=8 / verifications=27 / hypotheses=2。**
>
> **同日の整理**：監査 ID 11（旧ブランチのアーカイブ）を完了した。人間の承認を得て `arena/*` のリモートブランチ **36 本すべてを削除**し、**リモートのブランチは `main` のみ**になった。あわせて ID 12（記録数値のドリフト是正）を人間の判断で撤回した。これで `docs/incomplete-work-audit-2026-10-20.md` の**未対応項目はゼロ**になった。
>
> **証拠の紐付け完了**：`scripts/check_memo_ledger_refs.py` の新設に伴い調べたところ、
> **47 件中 18 件の EVD がどのメモからも参照されていなかった**（`task/TASK.md` §3 は
> 「主張には必ず証拠と出典を紐付けること」を要求する）。全件を紐付け、**未参照 EVD は 0** になった。
>
> **マージ方針（2026-10-21 以降）**：**CI が緑の PR は、人間の承認を待たずに各セッションが `main` へマージしてよい。** 取り消しが安価なためである。破壊的操作（リモートブランチの削除、`--force` を伴う push、台帳レコードの削除、リポジトリ設定の変更）は**引き続き人間の明示的な承認を要する**。根拠・境界・前提は `docs/autonomous-merge-policy-2026-10-21.md`。

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
  check_memo_ledger_refs.py メモ内の台帳ID・パス参照の存在検査（CI7番目のゲート）
gitswarm/
  problem.py solvers/  30都市TSPの決定論的ソルバ群（greedy/random/two_opt/SA）
  benchmarks/          複数シード実行＋成果物照合（--write/--check）
  readout.py           GitSwarm readout解析器（履歴が貯まれば使う道具）
  readout_sim.py       同質ワーカーの多数決＝共通モード障害の決定論的測定（--write/--check）
  artifacts/           実行で再生成できる成果物（ベンチマーク行列・投票スイープ行列）
tests/
  fixtures/            arXiv書誌スナップショット（オフライン照合用・2026-10-20取得）
  test_minimal_core.py         履歴非依存の回帰テスト（34件）
  test_check_citations.py      書誌照合テスト（17件・ネットワーク非依存）
  test_check_memo_citations.py 調査メモ内引用の照合テスト（33件）
  test_measure_agreement.py    並列セッション間一致度の測定テスト（25件）
  test_ownership.py            所有マップによるパス分類テスト（16件）
  test_readout_sim.py          共通モード障害シミュレータの回帰テスト（20件）
  test_check_memo_ledger_refs.py メモ内ID・パス参照の検査テスト（12件）
                               ── 合計 157件
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
