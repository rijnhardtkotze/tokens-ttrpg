#!/usr/bin/env python3
"""/resolve-paradox — resolve a conflicted timeline merge in fiction.

Run on a checkout of the timeline-merge PR's head branch. Attempts the merge
locally, hands the conflict regions to the LLM, writes its resolutions, logs
the paradox to meta/contradictions.md, commits and pushes to the PR branch.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gm_context import BOOT_FILES  # noqa: E402
from gm_turn import parse_envelope  # noqa: E402  (same JSON tolerance)
from llm_client import chat  # noqa: E402

PROMPTS = Path(__file__).resolve().parent / "prompts"
MARKER_RE = re.compile(r"^(<{7}|={7}|>{7})", re.MULTILINE)


def sh(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=check, capture_output=True, text=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pr", required=True, type=int)
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--root", default=".", type=Path)
    args = ap.parse_args()
    root = args.root.resolve()
    os.chdir(root)

    # Merge base INTO the timeline branch so conflicts surface here; "ours" is
    # the timeline, "theirs" is canonical main.
    merge = sh("git", "merge", "--no-commit", "--no-ff", args.base, check=False)
    conflicted = sh("git", "diff", "--name-only", "--diff-filter=U").stdout.split()
    if merge.returncode == 0 and not conflicted:
        sh("git", "merge", "--abort", check=False)
        print("No paradox: the timeline merges cleanly.")
        return 0

    parts = []
    for rel in BOOT_FILES:
        p = root / rel
        if p.exists():
            parts.append(f"\n===== {rel} =====\n{p.read_text(encoding='utf-8')}")
    for rel in conflicted:
        parts.append(f"\n===== CONFLICTED: {rel} =====\n{(root / rel).read_text(encoding='utf-8')}")

    system = (PROMPTS / "gm_paradox_system.md").read_text(encoding="utf-8")
    env = parse_envelope(chat(system, [{"role": "user", "content": "".join(parts)}]))

    resolved = {r["path"]: r["content"] for r in env.get("resolutions", [])}
    missing = [rel for rel in conflicted if rel not in resolved]
    if missing:
        print(f"::error::model left conflicts unresolved: {missing}")
        sh("git", "merge", "--abort", check=False)
        return 1
    for rel, content in resolved.items():
        if MARKER_RE.search(content):
            print(f"::error::resolution for {rel} still contains conflict markers")
            sh("git", "merge", "--abort", check=False)
            return 1
        (root / rel).write_text(content.rstrip("\n") + "\n", encoding="utf-8")

    today = datetime.date.today().isoformat()
    with (root / "meta" / "contradictions.md").open("a", encoding="utf-8") as fh:
        fh.write(f"\n## {today}: Paradox resolved (timeline merge PR #{args.pr})\n\n"
                 f"{env.get('paradox_log', '').strip()}\n")

    sh("git", "add", "-A")
    sh("git", "commit", "-m", f"Resolve timeline paradox for PR #{args.pr}")
    sh("git", "push")
    if env.get("comment"):
        sh("gh", "pr", "comment", str(args.pr), "--repo", args.repo,
           "--body", f"🌀 **The paradox settles.**\n\n{env['comment'].strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
