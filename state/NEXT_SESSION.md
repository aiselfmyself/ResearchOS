# ResearchOS 次セッションへの引き継ぎ

生成日時: 2026-10-19T12:32:45+00:00
引き継ぎ元ブランチ: `arena/955f8586-researchos`
推奨ロール: **proposer**

## あなた（次のセッション）が最初にやること

```bash
git fetch origin
git merge origin/arena/955f8586-researchos -m "merge: ResearchOS の研究状態を引き継ぎ"
# ブランチ名からセッションIDを自動導出してロールを宣言する
python3 scripts/researchos_session.py claim --role proposer
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
| - | PRP-001 | pending_review | - |

## 承認待ち（レビュー済み）

なし。

## 手順

```bash
# 新しい提案を作る
python3 scripts/researchos_queue.py list
# state/proposals.jsonl に PRP-YYYY を追記し、レビューキューに登録する
python3 scripts/researchos_queue.py add --proposal PRP-YYYY --session <YOUR_SESSION_ID>
```

## 現在のセッション一覧

- `SES-c4426c6b` active bootstrap+proposer — arena/c4426c6b-researchos
- `SES-eb670d1f` active verifier — arena/eb670d1f-researchos
- `SES-955f8586` active approver — arena/955f8586-researchos

> このファイルは `scripts/researchos_next.py` が生成します。手動で編集しないでください。
