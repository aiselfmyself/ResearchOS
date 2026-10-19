#!/usr/bin/env python3
"""Generate the hand-off prompt for the next Arena.ai chat.

Arena.ai sessions are started manually, so the harness cannot launch the next
worker.  Instead it produces a paste-ready prompt that tells the next chat which
role it must claim, which queue item to work on, and what it must not do.

Examples:
    python3 scripts/researchos_next.py
    python3 scripts/researchos_next.py --write   # also updates state/NEXT_SESSION.md
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from researchos_common import (  # noqa: E402
    ROOT,
    current_branch,
    load_effective,
    now_utc,
    read_jsonl,
    resolve_effective,
    STATE_FILES,
)

NEXT_PATH = ROOT / "state" / "NEXT_SESSION.md"


def _effective(name: str):
    try:
        records, errors, _warnings = resolve_effective(read_jsonl(ROOT / STATE_FILES[name]))
    except (OSError, ValueError):
        return []
    return records if not errors else records


def decide_role(queue: List[dict], proposals: List[dict], reviews: List[dict], approvals: List[dict]) -> str:
    approved_ids = {
        approval.get("proposal_id")
        for approval in approvals
        if approval.get("decision") == "approved"
    }
    reviewed = {
        review.get("proposal_id")
        for review in reviews
        if review.get("result") in ("pass", "partial")
    }
    if any(item.get("status") == "open" for item in queue):
        return "verifier"
    if any(
        proposal.get("status") == "pending_review"
        for proposal in proposals
        if proposal.get("proposal_id") not in reviewed
    ):
        return "verifier"
    if any(
        proposal.get("proposal_id") in reviewed
        and proposal.get("proposal_id") not in approved_ids
        and proposal.get("status") == "pending_review"
        for proposal in proposals
    ):
        return "approver"
    return "proposer"


def build_prompt(role: str, branch: str) -> str:
    queue = _effective("review_queue")
    proposals = _effective("proposals")
    reviews = _effective("reviews")
    approvals = _effective("approvals")
    sessions = _effective("sessions")

    open_items = [item for item in queue if item.get("status") in ("open", "claimed")]
    pending = [item for item in proposals if item.get("status") == "pending_review"]
    passing = {r.get("proposal_id") for r in reviews if r.get("result") in ("pass", "partial")}
    approved = {a.get("proposal_id") for a in approvals if a.get("decision") == "approved"}

    lines: List[str] = []
    lines.append("# ResearchOS 次セッションへの引き継ぎ")
    lines.append("")
    lines.append(f"生成日時: {now_utc()}")
    lines.append(f"引き継ぎ元ブランチ: `{branch}`")
    lines.append(f"推奨ロール: **{role}**")
    lines.append("")
    lines.append("## あなた（次のセッション）が最初にやること")
    lines.append("")
    lines.append("```bash")
    lines.append("git fetch origin")
    lines.append(f"git merge origin/{branch} -m \"merge: ResearchOS の研究状態を引き継ぎ\"")
    lines.append("# ブランチ名からセッションIDを自動導出してロールを宣言する")
    lines.append(f"python3 scripts/researchos_session.py claim --role {role}")
    lines.append("python3 scripts/researchos_guard.py status")
    lines.append("```")
    lines.append("")
    lines.append("## このセッションで守るルール（ハーネスが検査します）")
    lines.append("")
    lines.append("1. **自分の提案を自分でレビュー・承認してはいけない。**")
    lines.append("   提案・レビュー・承認は、それぞれ別のセッション（＝別のチャット／別のブランチ）が行います。")
    lines.append("2. **`scripts/`, `schemas/`, `policy/`, `tests/`, `.github/` は勝手に編集してはいけない。**")
    lines.append("   変更には承認済みの `PRP-*`（governance proposal）と `Governance-Proposal:` トレーラーが必要です。")
    lines.append("3. **`state/*.jsonl` は追記のみ。** 既存行の編集・削除は `check-append-only` が拒否します。")
    lines.append("   訂正は同じ ID で `revision` を上げた新しい行を追記してください。")
    lines.append("4. **すべてのコミットに `Session-Id:` と `Session-Role:` を付ける。**")
    lines.append("   付け忘れると CI の `check-commits` が失敗します。")
    lines.append("")
    lines.append("## 現在のレビュー待ち")
    lines.append("")
    if not open_items and not pending:
        lines.append("なし。新しい提案（`PRP-*`）から始めてください。")
    else:
        lines.append("| Queue | Proposal | Status | 必要な検査 |")
        lines.append("| :--- | :--- | :--- | :--- |")
        for item in open_items:
            lines.append(
                f"| {item.get('queue_id')} | {item.get('proposal_id')} | "
                f"{item.get('status')} | `{', '.join(item.get('required_checks', []))}` |"
            )
        for proposal in pending:
            if proposal.get("proposal_id") not in {i.get("proposal_id") for i in open_items}:
                lines.append(
                    f"| - | {proposal.get('proposal_id')} | pending_review | - |"
                )
    lines.append("")
    lines.append("## 承認待ち（レビュー済み）")
    lines.append("")
    waiting = [
        proposal
        for proposal in proposals
        if proposal.get("proposal_id") in passing
        and proposal.get("proposal_id") not in approved
        and proposal.get("status") == "pending_review"
    ]
    if waiting:
        for proposal in waiting:
            lines.append(
                f"- `{proposal.get('proposal_id')}` {proposal.get('title')} "
                f"(提案: {proposal.get('session_id')})"
            )
    else:
        lines.append("なし。")
    lines.append("")
    lines.append("## 手順")
    lines.append("")
    if role == "verifier":
        lines.append("```bash")
        lines.append("# 1. キューを確認して着手を記録")
        lines.append("python3 scripts/researchos_queue.py list --status open")
        lines.append("python3 scripts/researchos_queue.py claim --queue RQ-001 --session <YOUR_SESSION_ID>")
        lines.append("# 2. 標準検証スイートを実行（合否はあなたの判断ではなく実行結果）")
        lines.append("python3 scripts/researchos_verify.py --proposal PRP-001 --session <YOUR_SESSION_ID> --write")
        lines.append("# 3. 完了を記録")
        lines.append("python3 scripts/researchos_queue.py complete --queue RQ-001 --review REV-001 --session <YOUR_SESSION_ID>")
        lines.append("```")
    elif role == "approver":
        lines.append("```bash")
        lines.append("# レビューを読み、承認記録を追記する（自分でレビューした提案は承認できません）")
        lines.append("python3 scripts/researchos_guard.py status")
        lines.append("python3 - <<'PY'")
        lines.append("from pathlib import Path")
        lines.append("import sys; sys.path.insert(0, 'scripts')")
        lines.append("from researchos_common import append_jsonl, now_utc")
        lines.append("append_jsonl(Path('state/approvals.jsonl'), {")
        lines.append("    'approval_id': 'APR-001',")
        lines.append("    'proposal_id': 'PRP-001',")
        lines.append("    'session_id': '<YOUR_SESSION_ID>',")
        lines.append("    'review_ids': ['REV-001'],")
        lines.append("    'decision': 'approved',")
        lines.append("    'rationale': '...',")
        lines.append("    'created_at': now_utc(),")
        lines.append("})")
        lines.append("PY")
        lines.append("```")
    else:
        lines.append("```bash")
        lines.append("# 新しい提案を作る")
        lines.append("python3 scripts/researchos_queue.py list")
        lines.append("# state/proposals.jsonl に PRP-YYYY を追記し、レビューキューに登録する")
        lines.append("python3 scripts/researchos_queue.py add --proposal PRP-YYYY --session <YOUR_SESSION_ID>")
        lines.append("```")
    lines.append("")
    lines.append("## 現在のセッション一覧")
    lines.append("")
    for session in sessions:
        lines.append(
            f"- `{session.get('session_id')}` {session.get('status', 'active')} "
            f"{'+'.join(session.get('roles', []))} — {session.get('branch')}"
        )
    lines.append("")
    lines.append("> このファイルは `scripts/researchos_next.py` が生成します。手動で編集しないでください。")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="next-session hand-off prompt")
    parser.add_argument("--write", action="store_true", help="update state/NEXT_SESSION.md")
    parser.add_argument("--role", default=None, choices=["verifier", "approver", "proposer", "integrator"])
    args = parser.parse_args(argv)

    branch = current_branch()
    role = args.role or decide_role(
        _effective("review_queue"),
        _effective("proposals"),
        _effective("reviews"),
        _effective("approvals"),
    )
    prompt = build_prompt(role, branch)
    print(prompt)
    if args.write:
        NEXT_PATH.write_text(prompt, encoding="utf-8")
        print(f"\nwrote {NEXT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
