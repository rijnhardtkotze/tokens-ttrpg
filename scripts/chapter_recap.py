#!/usr/bin/env python3
"""Chapter close: milestone -> LLM recap -> recap file via GM PR + tag + Release."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gm_turn import parse_envelope  # noqa: E402
from llm_client import chat  # noqa: E402

PROMPTS = Path(__file__).resolve().parent / "prompts"


def sh(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--milestone", required=True, help="milestone title, e.g. 'Chapter 1'")
    ap.add_argument("--number", required=True, type=int, help="chapter number for the tag")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    ap.add_argument("--root", default=".", type=Path)
    args = ap.parse_args()
    root = args.root.resolve()
    os.chdir(root)

    issues = json.loads(sh("gh", "issue", "list", "--repo", args.repo, "--state", "all",
                           "--milestone", args.milestone, "--json", "number,title,body,labels,state"))
    parts = ["===== QUEST ISSUES OF THE CHAPTER ====="]
    for i in issues:
        labels = ",".join(lab["name"] for lab in i.get("labels", []))
        parts.append(f"#{i['number']} [{i['state']}] ({labels}) {i['title']}\n{i.get('body') or ''}")
    for p in sorted((root / "sessions").glob("*.md")):
        parts.append(f"===== {p.name} =====\n{p.read_text(encoding='utf-8')}")

    system = (PROMPTS / "chapter_recap_system.md").read_text(encoding="utf-8")
    env = parse_envelope(chat(system, [{"role": "user", "content": "\n\n".join(parts)}]))
    title, recap = env.get("title", args.milestone), env.get("recap", "")
    if not recap:
        print("::error::model returned no recap")
        return 1

    recap_path = root / "sessions" / f"chapter-{args.number}-recap.md"
    recap_path.write_text(f"# Chapter {args.number}: {title}\n\n{recap.strip()}\n", encoding="utf-8")

    branch = f"gm/chapter-{args.number}-recap"
    sh("git", "checkout", "-b", branch)
    sh("git", "add", str(recap_path))
    sh("git", "commit", "-m", f"Chapter {args.number} recap: {title}")
    sh("git", "push", "-u", "origin", branch, "--force")
    sh("gh", "pr", "create", "--repo", args.repo, "--base", "main", "--head", branch,
       "--title", f"Chapter {args.number} closes: {title}", "--body", recap, "--label", "gm-turn")

    sh("gh", "release", "create", f"chapter-{args.number}", "--repo", args.repo,
       "--title", f"Chapter {args.number}: {title}", "--notes", recap)
    return 0


if __name__ == "__main__":
    sys.exit(main())
