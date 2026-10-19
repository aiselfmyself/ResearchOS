# ResearchOS 次セッションへの引き継ぎ

生成日時: 2026-10-19T12:16:21+00:00
引き継ぎ元ブランチ: `arena/eb670d1f-researchos`
推奨ロール: **approver**

## あなた（次のセッション）が最初にやること

```bash
git fetch origin
git merge origin/arena/eb670d1f-researchos -m "merge: ResearchOS の研究状態を引き継ぎ"
# ブランチ名からセッションIDを自動導出してロールを宣言する
python3 scripts/researchos_session.py claim --role approver
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

- `PRP-001` Adopt the ResearchOS governance harness (roles, append-only state, review queue) (提案: SES-c4426c6b)

## 手順

```bash
# レビューを読み、承認記録を追記する（自分でレビューした提案は承認できません）
python3 scripts/researchos_guard.py status
python3 - <<'PY'
from pathlib import Path
import sys; sys.path.insert(0, 'scripts')
from researchos_common import append_jsonl, now_utc
append_jsonl(Path('state/approvals.jsonl'), {
    'approval_id': 'APR-001',
    'proposal_id': 'PRP-001',
    'session_id': '<YOUR_SESSION_ID>',
    'review_ids': ['REV-001'],
    'decision': 'approved',
    'rationale': '...',
    'created_at': now_utc(),
})
PY
```

## 現在のセッション一覧

- `SES-c4426c6b` active bootstrap+proposer — arena/c4426c6b-researchos
- `SES-eb670d1f` active verifier — arena/eb670d1f-researchos

> このファイルは `scripts/researchos_next.py` が生成します。手動で編集しないでください。
