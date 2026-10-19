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
    # PRP-002 G4 + V11: use load_effective with COLLECTION_ID_KEYS
    try:
        effective, errors, _warnings = load_effective(name)
    except (OSError, ValueError):
        return []
    return effective if not errors else effective


def scan_all_branches_for_open_queues() -> List[Dict]:
    """Scan all remote arena/* branches for open review queues.

    Returns list of dicts with branch, queue_id, proposal_id, created_at.
    Best-effort: ignores branches where file missing or unreadable.
    Resolves per-branch effective status (like load_effective) so that
    claimed/completed revisions hide their earlier open line.
    """
    import subprocess
    import json

    result: List[Dict] = []
    try:
        branches = subprocess.check_output(
            ["git", "for-each-ref", "--format=%(refname:strip=3)", "refs/remotes/origin/arena/*"],
            text=True,
        ).splitlines()
    except Exception:
        return result

    for branch_ref in branches:
        remote_ref = f"origin/{branch_ref}"
        try:
            content = subprocess.check_output(
                ["git", "show", f"{remote_ref}:state/review_queue.jsonl"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            continue
        records = []
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            records.append(rec)
        if not records:
            continue
        # Resolve effective per queue_id (same logic as load_effective)
        # Group by queue_id and pick latest revision
        from collections import defaultdict
        grouped: Dict[str, List[Dict]] = defaultdict(list)
        for rec in records:
            qid = rec.get("queue_id")
            if qid:
                grouped[qid].append(rec)
        for qid, recs in grouped.items():
            # Pick effective: max revision, or last if no revision field
            # Use resolve logic: sort by revision then supersedes chain is validated elsewhere,
            # but for scan we just pick highest revision number.
            recs_sorted = sorted(recs, key=lambda r: r.get("revision", 1))
            latest = recs_sorted[-1]
            if latest.get("status") == "open":
                result.append({
                    "branch": branch_ref,
                    "queue_id": latest.get("queue_id"),
                    "proposal_id": latest.get("proposal_id"),
                    "created_at": latest.get("created_at", ""),
                    "required_checks": latest.get("required_checks", []),
                })
    result.sort(key=lambda x: x.get("created_at", ""))
    return result


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
    # V11: if latest review for a pending proposal is fail, recommend proposer rework
    # Find proposals where latest review is fail
    failed_proposals = {
        review.get("proposal_id")
        for review in reviews
        if review.get("result") == "fail"
    }
    # If any open queue, verifier needed
    if any(item.get("status") == "open" for item in queue):
        return "verifier"
    # If any pending proposal hasn't been reviewed (no pass/partial), verifier
    if any(
        proposal.get("status") == "pending_review"
        for proposal in proposals
        if proposal.get("proposal_id") not in reviewed
    ):
        # But if its latest review is fail, it needs proposer rework, not another verifier loop
        # Check if any unreviewed proposal has a fail review (rework needed)
        for prop in proposals:
            if prop.get("proposal_id") not in reviewed and prop.get("proposal_id") in failed_proposals:
                return "proposer"
        return "verifier"
    if any(
        proposal.get("proposal_id") in reviewed
        and proposal.get("proposal_id") not in approved_ids
        and proposal.get("status") == "pending_review"
        for proposal in proposals
    ):
        return "approver"
    # V11: if all reviewed are fail, proposer should rework
    if any(p.get("proposal_id") in failed_proposals for p in proposals if p.get("status") == "pending_review"):
        return "proposer"
    return "proposer"


def build_prompt(role: str, branch: str, scan_all: bool = False, global_open: Optional[List[Dict]] = None) -> str:
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
    lines.append("5. **手で `state/*.jsonl` に追記したら、アンカーも更新する（PRP-002 rev3 / R4）。**")
    lines.append("   `python3 scripts/researchos_anchor.py update` を実行してコミットしてください。")
    lines.append("   `append_jsonl()`（＝ `researchos_session.py` / `researchos_queue.py` / `researchos_verify.py`）")
    lines.append("   経由の追記は自動的に pin されるので、この手順が要るのは手書きの追記だけです。")
    lines.append("   既存行を書き換えてから `update` しても隠せません（古いアンカーが元の接頭辞を固定し続けます）。")
    lines.append("6. **承認には `review_line_sha256` が必須（PRP-002 rev3 / R3）。**")
    lines.append("   `approved` を記録するとき、参照する各レビューの正規化行ハッシュを")
    lines.append("   `{\"review_id\": \"<sha256>\"}` の形で付けてください。欠落・一部欠落は validator が error にします。")
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
    # PRP-002 rev3 (§14/V11): the hand-off must name the queue item that is
    # actually open, not a hard-coded RQ-001/PRP-001 from the install round.
    first_open = open_items[0] if open_items else {}
    open_queue = first_open.get("queue_id", "RQ-XXX")
    open_proposal = first_open.get("proposal_id", "PRP-XXX")
    awaiting = [
        proposal.get("proposal_id")
        for proposal in proposals
        if proposal.get("proposal_id") in passing
        and proposal.get("proposal_id") not in approved
        and proposal.get("status") == "pending_review"
    ]
    approval_target = awaiting[0] if awaiting else "PRP-XXX"
    approval_reviews = sorted(
        {
            review.get("review_id")
            for review in reviews
            if review.get("proposal_id") == approval_target
            and review.get("result") in ("pass", "partial")
        }
    )
    if role == "verifier":
        lines.append("```bash")
        lines.append("# 1. キューを確認して着手を記録")
        lines.append("python3 scripts/researchos_queue.py list --status open")
        lines.append(f"python3 scripts/researchos_queue.py claim --queue {open_queue} --session <YOUR_SESSION_ID>")
        lines.append("# 2. 標準検証スイートを実行（合否はあなたの判断ではなく実行結果）")
        lines.append(f"#    {open_queue} の required_checks は {len(first_open.get('required_checks', []))} 項目。REV-* は --write が自動採番します。")
        lines.append(f"python3 scripts/researchos_verify.py --proposal {open_proposal} --session <YOUR_SESSION_ID> --write")
        lines.append("# 3. 完了を記録")
        lines.append(f"python3 scripts/researchos_queue.py complete --queue {open_queue} --review <REV-XXXX> --session <YOUR_SESSION_ID>")
        lines.append("# 4. 追記専用の確認（PRP-002 rev3）。クリーンな木で緑になること、そして")
        lines.append("#    改竄した使い捨てコピーで赤になることを自分の目で確かめてください。")
        lines.append("python3 scripts/researchos_guard.py check-append-only --json")
        lines.append("python3 scripts/researchos_anchor.py verify")
        lines.append("```")
    elif role == "approver":
        lines.append("```bash")
        lines.append("# レビューを読み、承認記録を追記する（自分でレビューした提案は承認できません）")
        lines.append("python3 scripts/researchos_guard.py status")
        lines.append("python3 - <<'PY'")
        lines.append("from pathlib import Path")
        lines.append("import sys; sys.path.insert(0, 'scripts')")
        lines.append("from researchos_common import append_jsonl, line_hash, now_utc, read_jsonl")
        lines.append("")
        lines.append("# PRP-002 rev3 (R3/C3・A2): review_line_sha256 は **必須**。")
        lines.append("# 参照するレビューの正規化行ハッシュを束縛しないと validator が error になります。")
        review_list = ", ".join(f"'{item}'" for item in approval_reviews) or "'REV-XXXX'"
        lines.append(f"REVIEWS = [{review_list}]   # {approval_target} の passing review（result: pass が最低1件）")
        lines.append("reviews = {r['review_id']: r for r in read_jsonl(Path('state/reviews.jsonl'))}")
        lines.append("binding = {rid: line_hash(reviews[rid]) for rid in REVIEWS if rid in reviews}")
        lines.append("assert set(binding) == set(REVIEWS), f'unknown review: {set(REVIEWS) - set(binding)}'")
        lines.append("")
        lines.append("append_jsonl(Path('state/approvals.jsonl'), {")
        lines.append("    'approval_id': 'APR-XXX',")
        lines.append(f"    'proposal_id': '{approval_target}',")
        lines.append("    'session_id': '<YOUR_SESSION_ID>',")
        lines.append("    'review_ids': REVIEWS,")
        lines.append("    'review_line_sha256': binding,")
        lines.append("    'decision': 'approved',")
        lines.append("    'rationale': '...',")
        lines.append("    'created_at': now_utc(),")
        lines.append("})")
        lines.append("PY")
        lines.append("# append_jsonl はアンカーも自動更新します。手で追記した場合は次を実行:")
        lines.append("python3 scripts/researchos_anchor.py verify")
        lines.append("```")
    else:
        lines.append("```bash")
        lines.append("# 新しい提案を作る")
        lines.append("python3 scripts/researchos_queue.py list")
        lines.append("# state/proposals.jsonl に PRP-YYYY を追記し、レビューキューに登録する")
        lines.append("# （append_jsonl を使えばアンカーは自動更新されます）")
        lines.append("python3 scripts/researchos_queue.py add --proposal PRP-YYYY --session <YOUR_SESSION_ID>")
        lines.append("# 手で state/*.jsonl に追記した場合のみ必要（PRP-002 rev3 / R4）")
        lines.append("python3 scripts/researchos_anchor.py update")
        lines.append("```")
    lines.append("")
    lines.append("## 現在のセッション一覧")
    lines.append("")
    for session in sessions:
        lines.append(
            f"- `{session.get('session_id')}` {session.get('status', 'active')} "
            f"{'+'.join(session.get('roles', []))} — {session.get('branch')}"
        )
    # Global verifier prioritization hint
    if scan_all and global_open is not None:
        lines.append("")
        lines.append("## 他ブランチで Verifier を待っているキュー（優先度順）")
        lines.append("")
        if not global_open:
            lines.append("なし。現ブランチのキューを優先してください。")
        else:
            lines.append("| Branch | Queue | Proposal | Created |")
            lines.append("| :--- | :--- | :--- | :--- |")
            for item in global_open:
                lines.append(
                    f"| `{item['branch']}` | {item['queue_id']} | {item['proposal_id']} | {item['created_at']} |"
                )
            # Highlight oldest
            oldest = global_open[0]
            if oldest["branch"] != branch:
                lines.append("")
                lines.append(f"> **優先推奨:** 最古の open キューは `{oldest['branch']}` の `{oldest['queue_id']}` ({oldest['proposal_id']}) です。")
                lines.append(f"> 現ブランチ `{branch}` より優先度が高い可能性があります。`git fetch` 後に `git show origin/{oldest['branch']}:state/proposals.jsonl` で内容を確認し、必要ならそちらを Verifier として claim してください。")
                lines.append("> ただし merge は人間の判断で — 同一ブランチで Verifier を完結させる場合は現ブランチを優先して構いません。")
            lines.append("")
            lines.append("ヒント: `python3 scripts/researchos_next.py --scan-all` で再取得できます。")
    lines.append("")
    lines.append("> このファイルは `scripts/researchos_next.py` が生成します。手動で編集しないでください。")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="next-session hand-off prompt")
    parser.add_argument("--write", action="store_true", help="update state/NEXT_SESSION.md")
    parser.add_argument("--role", default=None, choices=["verifier", "approver", "proposer", "integrator"])
    parser.add_argument("--scan-all", action="store_true", help="scan all remote arena/* branches for open queues and prioritize verifier")
    args = parser.parse_args(argv)

    branch = current_branch()
    role = args.role or decide_role(
        _effective("review_queue"),
        _effective("proposals"),
        _effective("reviews"),
        _effective("approvals"),
    )
    scan_all = args.scan_all
    global_open = None
    if scan_all:
        global_open = scan_all_branches_for_open_queues()
        # If global oldest is older than current branch's oldest open, suggest switching
        # But role decision remains local unless --role explicitly overrides
        if global_open:
            # If global oldest is not current branch, hint verifier to prioritize it
            # Don't auto-change role; just add hint section via build_prompt
            pass
    prompt = build_prompt(role, branch, scan_all=scan_all, global_open=global_open)
    print(prompt)
    if args.write:
        NEXT_PATH.write_text(prompt, encoding="utf-8")
        print(f"\nwrote {NEXT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
