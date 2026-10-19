# ResearchOS

**GitSwarm 型の自律研究オペレーティングシステム（プロトタイプ）**

ResearchOS は、研究状態を会話履歴から分離し、Git リポジトリを「不変の構造化共有メモリ」として使う研究ワークフローです。Supervisor / Worker / Critic / Verifier / Integrator の役割を `Informed-By` の意味的依存で連鎖させ、アトミックコミットとして推論の途中成果を蓄積します。

- **研究課題:** 自律型 AI エージェントにおける長期推論・分散協調アーキテクチャ（Stateless vs GitSwarm）
- **実行環境:** Arena.ai Agent Mode × GitHub
- **前セッション:** `arena/01673a58-researchos`（`8763d08`）
- **現行ブランチ:** `arena/c4426c6b-researchos`（独立監査 + ガバナンス・ハーネス）

> **重要:** `gitswarm/` は **プロトコルレベルのシミュレーション** です。単一プロセスがワーカー役を逐次演じるものであり、非同期・独立コンテキストのマルチエージェント実行環境ではありません。詳細は [`reports/independent-verification-report.md`](reports/independent-verification-report.md) を参照してください。

---

## クイックスタート

```bash
# 1. 決定論的検証（スキーマ・参照整合性・分離・Informed-By の祖先関係）
python3 scripts/validate_researchos.py

# 2. ガバナンス検査（ロール権限・追記専用・authorship）
python3 scripts/researchos_guard.py check-all

# 3. 回帰テスト
python3 -m unittest discover -s tests -v

# 4. GitSwarm ベンチマークの再現性チェック
python3 gitswarm/benchmarks/benchmark.py --check

# 5. GitSwarm readout（既定は gitswarm/ にスコープ）
python3 gitswarm/readout.py

# 6. 次セッション用の引き継ぎプロンプトを生成
python3 scripts/researchos_next.py --write
```

### セッションとして参加する

```bash
# ブランチ名からセッションIDを自動導出してロールを宣言
python3 scripts/researchos_session.py claim --role verifier

# レビューキューを確認して着手
python3 scripts/researchos_queue.py list --status open
python3 scripts/researchos_queue.py claim --queue RQ-001 --session SES-xxxx

# 標準検証スイート（合否は実行結果のみ）
python3 scripts/researchos_verify.py --proposal PRP-001 --session SES-xxxx --write

# 完了を記録
python3 scripts/researchos_queue.py complete --queue RQ-001 --review REV-001 --session SES-xxxx
```

---

## ガバナンス（提案者・検証者・承認者の分離）

2026-10-19 の監査で、**自己検証が PASS したのに内容が誤っていた**ことが判明しました。これを構造的に防ぐため、セッション単位の分離を導入しています。

```
1 チャット = 1 セッション = 1 ブランチ
proposer ──> PRP-xxx + RQ-xxx
verifier ──> REV-xxx（別セッション、検証器・テストは編集不可）
approver ──> APR-xxx（さらに別セッション）
human    ──> main へマージ（land ゲート）
```

| ルール | 仕組み |
| :--- | :--- |
| 役割の分離 | 提案・レビュー・承認の `session_id` がすべて異なることを検証器が強制 |
| パス権限 | verifier は `scripts/`, `schemas/`, `policy/`, `tests/`, `.github/` を変更できない |
| 追記専用 | 訂正は `revision` + `supersedes` の新しい行。既存行の編集・削除は拒否 |
| authorship | `git blame` で導入コミットを特定し、`Session-Id` とレコードのセッションを照合 |
| ガバナンス変更 | `propose`（提案あり）と `land`（別セッションの承認済み）の 2 段階 |
| 起動 | **手動のまま**（Arena.ai のチャットは人間が開く）。`state/NEXT_SESSION.md` が引き継ぎを担う |

詳細: [`docs/GOVERNANCE.md`](docs/GOVERNANCE.md)
実装レポート: [`reports/governance-implementation-report.md`](reports/governance-implementation-report.md)

**現在の状態:** `PRP-001`（ガバナンス・ハーネス採用）が `pending_review`、`RQ-001` が `open`。
このセッションは自分の提案をレビュー・承認できません。次のセッション（verifier）を待っています。

### モデルが毎回変わることについて

Arena.ai はチャットごとにモデルが変わり得ますが、**分離はモデルの違いに依存しません**。

- ✅ 別チャットは提案者の推論履歴を持たないため、リポジトリから再導出する（コンテキスト独立）。
- ⚠️ モデル系列の多様性は保証されず、自己申告も検証できない。
- ❌ 同一性は暗号学的に証明できない（git author は全セッション共通）。

そのため、セッション ID・ブランチ・レコード・`git blame` で分離を強制しています。

---

## ディレクトリ構成

| パス | 役割 |
| :--- | :--- |
| `task/TASK.md` | 研究課題・Ground Truth 要件・検証プロトコル |
| `state/` | 研究状態（sources / evidence / claims / verifications / hypotheses / sessions / proposals / reviews / approvals / review_queue） |
| `schemas/` | JSON Schema（研究レコード + ガバナンスレコード） |
| `policy/` | ロールポリシーと追記専用の基準点 |
| `scripts/validate_researchos.py` | 決定論的検証器（依存ライブラリなし） |
| `scripts/researchos_guard.py` | ロール権限・追記専用・authorship の検査 |
| `scripts/researchos_session.py` | セッション台帳の操作 |
| `scripts/researchos_queue.py` | レビューキュー |
| `scripts/researchos_verify.py` | 標準検証スイート |
| `scripts/researchos_next.py` | 次セッション用プロンプト生成 |
| `gitswarm/` | 30都市TSP のベンチマークと readout |
| `tests/` | 監査 Findings とガバナンス規則の回帰テスト（49 件） |
| `reports/` | 研究統合・GitSwarm 検証・独立監査・ガバナンス実装 |
| `docs/GOVERNANCE.md` | ガバナンス・プロトコル |
| `.github/workflows/` | CI（validator / tests / benchmark / governance） |

---

## 研究状態のモデル

```
Source ──< Evidence ──< Claim ──< Verification
                         │
                         └──< Hypothesis

Session ──< Proposal ──< Review ──< Approval
              │
              └──< QueueItem ──< Review
```

- **Source**: arXiv 等の一次資料（DOI / 著者 / 年 / URL）
- **Evidence**: 逐語引用・測定値・メタデータ照合（`quote_type` 必須）
- **Claim**: 証拠に紐づく主張（`candidate` / `supported` / `disputed` / `rejected`）
- **Verification**: 検証結果（`pass` / `fail` / `warn` / `falsified`）
- **Hypothesis**: 検証可能な仮説
- **Session / Proposal / Review / Approval**: 役割分離の台帳

`Informed-By:` コミットトレーラは、物理的な親とは別に**意味的な依存**を記録します。検証器は、引用先が実在するだけでなく、**引用元の祖先である**ことも確認します。

---

## 現在の検証状況（2026-10-19）

| チェック | 結果 |
| :--- | :--- |
| `scripts/validate_researchos.py` | PASS（4 Sources / 14 Evidence / 7 Claims / 21 Verifications / 3 Hypotheses / 1 Session / 1 Proposal / 1 Queue） |
| `scripts/researchos_guard.py check-all` | PASS（policy / append_only / commits / authorship） |
| `python3 -m unittest discover -s tests -v` | 49 tests OK |
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
- ガードはリポジトリ内のコードであり、書き込み権限があれば弱められる。最終ゲートは人間のマージ。
- セッションの同一性は暗号学的に証明されない。
- セッションの起動は手動（Arena.ai のチャットは人間が開く）。

---

## ライセンス

このリポジトリは研究プロトタイプです。引用文献の著作権は各原著者に帰属します。
