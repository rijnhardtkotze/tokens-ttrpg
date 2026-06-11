#!/usr/bin/env python3
"""Assemble the GM's prompt context: the lazy-loading protocol, mechanized.

Always loaded: boot files, the rulebook, the merged PR (title/body/diff),
dice results, cost. Then entity resolution: [[ids]] in the PR body/diff and
touched articles -> Tier-3 full text; their categories' _index.md -> Tier-1;
one hop of related: ids -> Tier-2 Quick Reference only. ~40k-token budget,
Tier-2 dropped first, boot files never.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.wiki import build_id_map, extract_links, parse_frontmatter, quick_reference  # noqa: E402

BOOT_FILES = [
    "index.md",
    "meta/canon.md",
    "meta/conventions.md",
    "meta/git-protocol.md",
    "character/sheet.md",
    "plot/state.md",
]
TOKEN_BUDGET = 40_000


def _read(root: Path, rel: str) -> str | None:
    p = root / rel
    return p.read_text(encoding="utf-8") if p.exists() else None


def _section(title: str, body: str) -> str:
    return f"\n\n===== {title} =====\n{body.strip()}\n"


def latest_session(root: Path) -> tuple[str, str] | None:
    sessions = sorted((root / "sessions").glob("*.md")) if (root / "sessions").is_dir() else []
    if not sessions:
        return None
    p = sessions[-1]
    return p.relative_to(root).as_posix(), p.read_text(encoding="utf-8")


def assemble(root: Path, pr_title: str, pr_body: str, pr_diff: str,
             dice_results: list[dict], cost_report: str) -> str:
    id_map = {k: v[0] for k, v in build_id_map(root).items()}

    parts: list[str] = []
    for rel in BOOT_FILES:
        text = _read(root, rel)
        if text is not None:
            parts.append(_section(rel, text))
    last = latest_session(root)
    if last:
        parts.append(_section(f"{last[0]} (latest session log)", last[1]))

    turn = _section("THE MERGED PLAYER ACTION (PR)", f"Title: {pr_title}\n\n{pr_body or '(no body)'}")
    turn += _section("ACTION DIFF", pr_diff[:30_000])
    if dice_results:
        rolled = "\n".join(
            f"- {r['action_id']}: {r['expr']} -> dice {r['dice']} = **{r['total']}**" for r in dice_results
        )
        turn += _section("FATE — RESOLVED ROLLS (already final, narrate around these)", rolled)
    turn += _section("WEAVE COST (already deducted by the driver)", cost_report)

    # Entity resolution
    mentioned: list[str] = []
    for target in extract_links(pr_body or "") + extract_links(pr_diff or ""):
        if target in id_map and target not in mentioned:
            mentioned.append(target)

    tier3, tier1_dirs, related_ids = [], [], []
    for aid in mentioned:
        rel = id_map[aid]
        text = _read(root, rel)
        if text is None:
            continue
        tier3.append(_section(f"{rel} (full article)", text))
        parent = str(Path(rel).parent)
        if parent not in tier1_dirs:
            tier1_dirs.append(parent)
        try:
            fm, _ = parse_frontmatter(text)
        except yaml.YAMLError:
            fm = None
        for rid in (fm or {}).get("related") or []:
            if rid in id_map and rid not in mentioned and rid not in related_ids:
                related_ids.append(rid)

    tier1 = []
    for d in tier1_dirs:
        text = _read(root, f"{d}/_index.md")
        if text:
            tier1.append(_section(f"{d}/_index.md", text))

    tier2 = []
    for rid in related_ids:
        text = _read(root, id_map[rid])
        if text is None:
            continue
        _, body = parse_frontmatter(text)
        qr = quick_reference(body)
        if qr:
            tier2.append(_section(f"{id_map[rid]} (Quick Reference of related [[{rid}]])", qr))

    # Budget: boot + turn are untouchable; shed Tier-2 first, then truncate Tier-3.
    def chars(blocks: list[str]) -> int:
        return sum(len(b) for b in blocks)

    budget_chars = TOKEN_BUDGET * 4
    while tier2 and chars(parts) + len(turn) + chars(tier3 + tier1 + tier2) > budget_chars:
        tier2.pop()
    while tier3 and chars(parts) + len(turn) + chars(tier3 + tier1) > budget_chars:
        tier3[-1] = tier3[-1][: max(len(tier3[-1]) // 2, 2000)] + "\n[truncated]\n"
        if len(tier3[-1]) <= 2100:
            tier3.pop()

    return "".join(parts) + "".join(tier3) + "".join(tier1) + "".join(tier2) + turn


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Print the assembled context for inspection.")
    ap.add_argument("--root", default=".", type=Path)
    ap.add_argument("--pr-title", default="(dry run)")
    ap.add_argument("--pr-body", default="")
    ap.add_argument("--pr-diff", default="")
    args = ap.parse_args()
    print(assemble(args.root.resolve(), args.pr_title, args.pr_body, args.pr_diff, [], "(none)"))
