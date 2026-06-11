#!/usr/bin/env python3
"""Validate article frontmatter against the schema in CLAUDE.md.

World articles need the full schema; session logs need date + summary.
Exit 1 on any error; emits GitHub Actions annotations.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.wiki import (  # noqa: E402
    ID_PREFIX_FOR_TYPE,
    WORLD_DIR_FOR_TYPE,
    build_id_map,
    error,
    iter_session_logs,
    iter_world_articles,
    parse_frontmatter,
)

REQUIRED = ["id", "title", "type", "tags", "status", "importance", "first_seen", "last_seen", "related", "summary"]
TYPES = set(ID_PREFIX_FOR_TYPE)
STATUSES = {"alive", "dead", "unknown", "missing", "active", "resolved", "dormant"}
IMPORTANCE = {"major", "minor", "seed"}
ID_RE = re.compile(r"^[a-z]+-[a-z0-9][a-z0-9-]*$")


def check_article(rel: str, path: Path, problems: list[str]) -> None:
    try:
        fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        problems.append(error(rel, f"invalid YAML frontmatter: {exc}"))
        return
    if fm is None:
        problems.append(error(rel, "missing frontmatter block"))
        return

    for key in REQUIRED:
        if key not in fm:
            problems.append(error(rel, f"frontmatter missing required key '{key}'"))
    aid, atype = fm.get("id"), fm.get("type")
    if atype is not None and atype not in TYPES:
        problems.append(error(rel, f"type '{atype}' not one of {sorted(TYPES)}"))
    if fm.get("status") is not None and fm["status"] not in STATUSES:
        problems.append(error(rel, f"status '{fm['status']}' not one of {sorted(STATUSES)}"))
    if fm.get("importance") is not None and fm["importance"] not in IMPORTANCE:
        problems.append(error(rel, f"importance '{fm['importance']}' not one of {sorted(IMPORTANCE)}"))
    if not isinstance(fm.get("tags"), list):
        problems.append(error(rel, "tags must be a list"))
    if not isinstance(fm.get("related"), list):
        problems.append(error(rel, "related must be a list"))
    if not (isinstance(fm.get("summary"), str) and fm["summary"].strip()):
        problems.append(error(rel, "summary must be a non-empty one-liner"))

    if isinstance(aid, str):
        if not ID_RE.match(aid):
            problems.append(error(rel, f"id '{aid}' does not match <type>-<slug>"))
        prefix = ID_PREFIX_FOR_TYPE.get(atype)
        if prefix and not aid.startswith(prefix + "-"):
            problems.append(error(rel, f"id '{aid}' should start with '{prefix}-' for type '{atype}'"))
    elif "id" in fm:
        problems.append(error(rel, "id must be a string"))

    expected_dir = WORLD_DIR_FOR_TYPE.get(atype)
    if expected_dir and not rel.startswith(f"world/{expected_dir}/"):
        problems.append(error(rel, f"type '{atype}' belongs under world/{expected_dir}/"))


def check_session(rel: str, path: Path, problems: list[str]) -> None:
    try:
        fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        problems.append(error(rel, f"invalid YAML frontmatter: {exc}"))
        return
    if fm is None:
        problems.append(error(rel, "session log missing frontmatter (needs date, summary)"))
        return
    for key in ("date", "summary"):
        if key not in fm:
            problems.append(error(rel, f"session log frontmatter missing '{key}'"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", type=Path)
    args = ap.parse_args()
    root = args.root.resolve()

    problems: list[str] = []
    for rel, path in iter_world_articles(root):
        check_article(rel, path, problems)
    for rel, path in iter_session_logs(root):
        if re.match(r"^sessions/chapter-\d+-recap\.md$", rel):
            continue
        check_session(rel, path, problems)
    for aid, paths in build_id_map(root).items():
        if len(paths) > 1:
            problems.append(error(paths[1], f"duplicate id '{aid}' (also in {paths[0]})"))

    print("\n".join(problems) if problems else "frontmatter: all articles valid")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
