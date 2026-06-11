#!/usr/bin/env python3
"""Check _index.md membership and drift.

Every world article must have a one-liner in its category's _index.md; every
[[id]] in an index must exist; the one-liner must still contain the article's
frontmatter summary (index drift).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.wiki import build_id_map, error, extract_links, iter_world_articles, parse_frontmatter  # noqa: E402


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().rstrip(".").lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", type=Path)
    args = ap.parse_args()
    root = args.root.resolve()

    id_map = build_id_map(root)
    problems: list[str] = []

    for rel, path in iter_world_articles(root):
        try:
            fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue  # validate_frontmatter reports this
        if not fm or "id" not in fm:
            continue
        index_path = path.parent / "_index.md"
        index_rel = index_path.relative_to(root).as_posix()
        index_text = index_path.read_text(encoding="utf-8") if index_path.exists() else ""
        line = next((ln for ln in index_text.splitlines() if f"[[{fm['id']}]]" in ln or f"[[{fm['id']}|" in ln), None)
        if line is None:
            problems.append(error(index_rel, f"article '{fm['id']}' ({rel}) missing from index"))
        elif isinstance(fm.get("summary"), str) and normalize(fm["summary"]) not in normalize(line):
            problems.append(error(index_rel, f"index drift: one-liner for '{fm['id']}' no longer matches its summary"))

    for index_path in sorted((root / "world").rglob("_index.md")):
        rel = index_path.relative_to(root).as_posix()
        for target in extract_links(index_path.read_text(encoding="utf-8")):
            if "/" in target or target in ("id",):
                continue
            if target not in id_map:
                problems.append(error(rel, f"index references [[{target}]] but no article carries that id"))

    print("\n".join(problems) if problems else "indexes: membership and summaries in sync")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
