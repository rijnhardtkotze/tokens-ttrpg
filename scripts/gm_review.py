#!/usr/bin/env python3
"""/gm — out-of-band dialogue with the GM in a PR or issue comment thread.

Loads the boot files plus the thread so far, asks the LLM for a table-talk
reply, and posts it as a comment. Changes no world state.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gm_context import BOOT_FILES, latest_session  # noqa: E402
from llm_client import chat  # noqa: E402

PROMPTS = Path(__file__).resolve().parent / "prompts"


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--number", required=True, type=int, help="PR or issue number")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    ap.add_argument("--message", required=True, help="the player's /gm message")
    ap.add_argument("--root", default=".", type=Path)
    args = ap.parse_args()
    root = args.root.resolve()

    parts = []
    for rel in BOOT_FILES:
        p = root / rel
        if p.exists():
            parts.append(f"\n===== {rel} =====\n{p.read_text(encoding='utf-8')}")
    last = latest_session(root)
    if last:
        parts.append(f"\n===== {last[0]} (latest session log) =====\n{last[1]}")

    issue = json.loads(gh("issue", "view", str(args.number), "--repo", args.repo,
                          "--json", "title,body,comments"))
    thread = [f"[opening post] {issue['title']}\n{issue.get('body') or ''}"]
    for c in issue.get("comments", [])[-15:]:
        author = (c.get("author") or {}).get("login", "?")
        thread.append(f"[{author}] {c.get('body', '')}")
    parts.append("\n===== THE THREAD =====\n" + "\n\n".join(thread))
    parts.append(f"\n===== THE PLAYER ASKS =====\n{args.message}")

    system = (PROMPTS / "gm_review_system.md").read_text(encoding="utf-8")
    reply = chat(system, [{"role": "user", "content": "".join(parts)}], max_tokens=2000)
    gh("issue", "comment", str(args.number), "--repo", args.repo, "--body", f"🧙 {reply.strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
