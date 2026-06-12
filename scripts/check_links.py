#!/usr/bin/env python3
"""Check that every [[wiki link]] resolves.

Targets may be frontmatter ids (npc-harald), repo paths without extension
(meta/canon, world/regions/_index), or session ids (2026-06-11-01).
Unresolved links in meta/seeds.md are warnings; everywhere else, errors.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.wiki import build_id_map, error, extract_links, warning  # noqa: E402

SEARCH_DIRS = ("world", "meta", "plot", "character", "sessions")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", type=Path)
    args = ap.parse_args()
    root = args.root.resolve()

    ids = set(build_id_map(root))
    paths = {
        p.relative_to(root).as_posix().removesuffix(".md")
        for p in root.rglob("*.md")
        if not p.relative_to(root).as_posix().startswith((".github/", "scripts/", "tests/", "demo/"))
    }
    session_ids = {p.stem for p in (root / "sessions").glob("*.md")} if (root / "sessions").is_dir() else set()

    problems, warnings = [], []
    files = [root / "index.md"] if (root / "index.md").exists() else []
    for d in SEARCH_DIRS:
        files.extend(sorted((root / d).rglob("*.md")) if (root / d).is_dir() else [])

    for path in files:
        rel = path.relative_to(root).as_posix()
        for target in extract_links(path.read_text(encoding="utf-8")):
            if target in ids or target in paths or target in session_ids:
                continue
            if target.startswith("<") or "session-id" in target or target in ("id", "id1", "id2"):
                continue  # schema placeholders in templates
            msg = f"unresolved link [[{target}]]"
            (warnings if rel == "meta/seeds.md" else problems).append(
                (warning if rel == "meta/seeds.md" else error)(rel, msg)
            )

    out = problems + warnings
    print("\n".join(out) if out else "links: all wiki links resolve")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
