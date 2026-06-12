#!/usr/bin/env python3
"""Warn-only style audit (the mechanical slice of meta/lint-protocol.md).

Checks: Quick Reference bloat (>10 lines), tags outside the controlled lists in
meta/conventions.md, and orphan articles with no incoming links. Always exits 0;
the report is posted to the PR by CI.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.wiki import extract_links, iter_world_articles, parse_frontmatter, quick_reference, warning  # noqa: E402


def controlled_tags(root: Path) -> set[str] | None:
    """Parse the `**Category:** \\`a\\`, \\`b\\`` lines from meta/conventions.md."""
    conv = root / "meta" / "conventions.md"
    if not conv.exists():
        return None
    tags = set()
    for line in conv.read_text(encoding="utf-8").splitlines():
        if re.match(r"^\*\*[^*]+:\*\*", line):
            tags.update(re.findall(r"`([^`]+)`", line))
    return tags or None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", type=Path)
    args = ap.parse_args()
    root = args.root.resolve()

    allowed = controlled_tags(root)
    warnings: list[str] = []

    articles = []
    for rel, path in iter_world_articles(root):
        try:
            fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        articles.append((rel, fm or {}, body))

    incoming: set[tuple[str, str]] = set()
    scan_dirs = ["world", "plot", "character", "sessions", "meta"]
    for d in scan_dirs:
        if not (root / d).is_dir():
            continue
        for p in (root / d).rglob("*.md"):
            src_rel = p.relative_to(root).as_posix()
            for target in extract_links(p.read_text(encoding="utf-8")):
                incoming.add((src_rel, target))

    for rel, fm, body in articles:
        qr = quick_reference(body)
        if qr and len([ln for ln in qr.splitlines() if ln.strip()]) > 10:
            warnings.append(warning(rel, "Quick Reference exceeds 10 lines — condense (Tier-2 bloat)"))
        if allowed:
            for tag in fm.get("tags") or []:
                if isinstance(tag, str) and tag not in allowed:
                    warnings.append(warning(rel, f"tag '{tag}' is not in the controlled list in meta/conventions.md"))
        aid = fm.get("id")
        if aid and not any(t == aid and src != rel for src, t in incoming):
            warnings.append(warning(rel, f"orphan: no other file links to [[{aid}]]"))

    print("\n".join(warnings) if warnings else "style: nothing to flag")
    return 0


if __name__ == "__main__":
    sys.exit(main())
