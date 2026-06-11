#!/usr/bin/env python3
"""Weave: the diff-cost of changing reality.

Cost per file from `git diff --numstat base...head` (changed = added + deleted):

    sessions/, character/journal.md                       0   narrating yourself is free
    plot/, character/sheet.md                  ceil(n/10)     nudging your own thread
    world/** (existing article)                ceil(n/5)      reshaping reality
    world/** (new article)                     ceil(n/5)+2    summoning into existence
    meta/canon.md                              ceil(n/5)*3    rewriting the laws
    indexes, meta/seeds.md, meta/contradictions.md        0   bookkeeping

Total = max(sum, 1). Exits 3 when --budget is given and exceeded.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

FREE_PREFIXES = ("sessions/",)
FREE_FILES = {"character/journal.md", "meta/seeds.md", "meta/contradictions.md", "meta/rolls.md"}
ENGINE_PREFIXES = (".github/", "scripts/", "tests/")  # not part of the fiction


def file_cost(path: str, lines: int, is_new: bool) -> tuple[int, str]:
    if path.startswith(ENGINE_PREFIXES) or not path.endswith(".md"):
        return 0, "outside the fiction"
    if path.endswith("_index.md") or path in FREE_FILES or path.startswith(FREE_PREFIXES):
        return 0, "free"
    if path == "meta/canon.md":
        return math.ceil(lines / 5) * 3, "rewriting the laws of the world"
    if path.startswith("world/"):
        base = math.ceil(lines / 5)
        return (base + 2, "summoning into existence") if is_new else (base, "reshaping reality")
    if path.startswith("plot/") or path == "character/sheet.md":
        return math.ceil(lines / 10), "nudging your own thread"
    return 0, "free"


def diff_costs(base: str, head: str, repo: Path) -> list[dict]:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout

    new_files = set(git("diff", "--name-only", "--diff-filter=A", f"{base}...{head}").split())
    rows = []
    for line in git("diff", "--numstat", f"{base}...{head}").splitlines():
        added, deleted, path = line.split("\t", 2)
        lines = (0 if added == "-" else int(added)) + (0 if deleted == "-" else int(deleted))
        cost, why = file_cost(path, lines, path in new_files)
        rows.append({"path": path, "lines": lines, "cost": cost, "why": why})
    return rows


def total_cost(rows: list[dict]) -> int:
    return max(sum(r["cost"] for r in rows), 1) if rows else 0


def read_weave(sheet_text: str) -> tuple[int | None, int | None]:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from lib.wiki import parse_frontmatter

    fm, _ = parse_frontmatter(sheet_text)
    if not fm:
        return None, None
    w, wm = fm.get("weave"), fm.get("weave_max")
    return (w if isinstance(w, int) else None), (wm if isinstance(wm, int) else None)


def markdown_report(rows: list[dict], total: int, budget: int | None) -> str:
    lines = ["### 🕸️ Weave cost", "", "| File | Lines | Cost | |", "|---|---:|---:|---|"]
    for r in rows:
        if r["why"] == "outside the fiction":
            continue
        lines.append(f"| `{r['path']}` | {r['lines']} | {r['cost']} | {r['why']} |")
    lines.append(f"\n**Total: {total}**")
    if budget is not None:
        verdict = "✅ within your Weave" if total <= budget else "❌ **exceeds your Weave — reality resists**"
        lines.append(f" against current Weave **{budget}** — {verdict}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--repo", default=".", type=Path)
    ap.add_argument("--budget", type=int, default=None, help="current weave; exit 3 if exceeded")
    ap.add_argument("--format", choices=["json", "markdown"], default="json")
    args = ap.parse_args()

    rows = diff_costs(args.base, args.head, args.repo)
    total = total_cost(rows)
    if args.format == "markdown":
        print(markdown_report(rows, total, args.budget))
    else:
        print(json.dumps({"files": rows, "total": total, "budget": args.budget}))
    return 3 if args.budget is not None and total > args.budget else 0


if __name__ == "__main__":
    sys.exit(main())
