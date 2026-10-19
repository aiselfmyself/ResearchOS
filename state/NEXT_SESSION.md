# ResearchOS 次セッションへの引き継ぎ

生成日時: 2026-10-19T09:23:04+00:00
引き継ぎ元ブランチ: `arena/c4426c6b-researchos`
推奨ロール: **verifier**

## あなた（次のセッション）が最初にやること

```bash
git fetch origin
git merge origin/arena/c4426c6b-researchos -m "merge: ResearchOS の研究状態を引き継ぎ"
# ブランチ名からセッションIDを自動導出してロールを宣言する
python3 scripts/researchos_session.py claim --role verifier
python3 scripts/researchos_guard.py status
```

## このセッションで守るルール（ハーネスが検査します）

1. **自分の提案を自分でレビュー・承認してはいけない。**
   提案・レビュー・承認は、それぞれ別のセッション（＝別のチャット／別のブランチ）が行います。
2. **`scripts/`, `schemas/`, `policy/`, `tests/`, `.github/` は勝手に編集してはいけない。**
   変更には承認済みの `PRP-*`（governance proposal）と `Governance-Proposal:` トレーラーが必要です。
3. **`state/*.jsonl` は追記のみ。** 既存行の編集・削除は `check-append-only` が拒否します。
   訂正は同じ ID で `revision` を上げた新しい行を追記してください。
4. **すべてのコミットに `Session-Id:` と `Session-Role:` を付ける。**
   付け忘れると CI の `check-commits` が失敗します。

## 現在のレビュー待ち

| Queue | Proposal | Status | 必要な検査 |
| :--- | :--- | :--- | :--- |
| RQ-001 | PRP-001 | open | `governance_review, schema_and_integrity, regression_tests, benchmark_reproducible, readout_snapshot, append_only, role_guard, role_separation` |

## 承認待ち（レビュー済み）

なし。

## 手順

```bash
# 1. キューを確認して着手を記録
python3 scripts/researchos_queue.py list --status open
python3 scripts/researchos_queue.py claim --queue RQ-001 --session <YOUR_SESSION_ID>
# 2. 標準検証スイートを実行（合否はあなたの判断ではなく実行結果）
python3 scripts/researchos_verify.py --proposal PRP-001 --session <YOUR_SESSION_ID> --write
# 3. 完了を記録
python3 scripts/researchos_queue.py complete --queue RQ-001 --review REV-001 --session <YOUR_SESSION_ID>
```

## 現在のセッション一覧

- `SES-c4426c6b` active bootstrap+proposer — arena/c4426c6b-researchos

> このファイルは `scripts/researchos_next.py` が生成します。手動で編集しないでください。
