#!/usr/bin/env python3
"""Generate ``policy/state_baseline.json``.

The baseline freezes the state files *as they were* when the governance harness
was introduced.  Everything in the baseline is grandfathered (legacy); every
line appended afterwards must follow the revision / session rules.

Run once during bootstrap:

    python3 scripts/build_state_baseline.py --base <parent-commit>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from researchos_common import (  # noqa: E402
    LEGACY_STATE_FILES,
    ROOT,
    STATE_BASELINE,
    git_show,
    line_hash,
    read_jsonl_text,
    sha256_text,
)


def build(base_commit: str) -> dict:
    files = {}
    legacy = {}
    for relative in LEGACY_STATE_FILES:
        text = git_show(base_commit, relative)
        if text is None:
            raise SystemExit(
                f"{relative} does not exist at {base_commit}; refusing to baseline"
            )
        records = read_jsonl_text(text)
        files[relative] = {
            "sha256": sha256_text(text),
            "bytes": len(text.encode("utf-8")),
            "lines": len(records),
        }
        legacy[relative] = [line_hash(record) for record in records]
    return {
        "policy_version": 1,
        "base_commit": base_commit,
        "description": (
            "Append-only baseline. Records whose canonical line hash appears in "
            "legacy_line_sha256 are grandfathered; all later lines must carry a "
            "revision, a session, and (for supported claims) independent backing."
        ),
        "files": files,
        "legacy_line_sha256": legacy,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="build policy/state_baseline.json")
    parser.add_argument("--base", required=True, help="commit to freeze")
    parser.add_argument(
        "--write", action="store_true", help="write the file (default: print)"
    )
    args = parser.parse_args(argv)

    payload = build(args.base)
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.write:
        STATE_BASELINE.parent.mkdir(parents=True, exist_ok=True)
        # This file is policy input, not append-only state.
        STATE_BASELINE.write_text(text, encoding="utf-8")
        print(f"wrote {STATE_BASELINE.relative_to(ROOT)}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
