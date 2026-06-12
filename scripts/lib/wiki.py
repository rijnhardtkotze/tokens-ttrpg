"""Shared wiki primitives: frontmatter, [[links]], id maps.

Everything that reads or writes the campaign wiki goes through here so the
validators and the GM driver agree on what an article is.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")

WORLD_DIR_FOR_TYPE = {
    "npc": "npcs",
    "location": "regions",
    "item": "items",
    "faction": "factions",
    "lore": "lore",
    "creature": "bestiary",
}

ID_PREFIX_FOR_TYPE = {
    "npc": "npc",
    "location": "loc",
    "item": "item",
    "faction": "faction",
    "lore": "lore",
    "creature": "creature",
    "quest": "quest",
}


def parse_frontmatter(text: str) -> tuple[dict | None, str]:
    """Return (frontmatter dict or None, body). Raises yaml.YAMLError on bad YAML."""
    if text.startswith("---\r\n"):
        hdr = 5
    elif text.startswith("---\n"):
        hdr = 4
    else:
        return None, text
    for nl in ("\r\n---", "\n---"):
        end = text.find(nl, hdr)
        if end != -1:
            raw = text[hdr:end]
            body = text[end + len(nl) :].lstrip("\r\n")
            break
    else:
        return None, text
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        return None, text
    return data, body


def serialize_frontmatter(data: dict, body: str) -> str:
    raw = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=None)
    return f"---\n{raw}---\n\n{body.lstrip(chr(10))}"


def extract_links(text: str) -> list[str]:
    """All [[target]] / [[target|alias]] targets, code blocks excluded."""
    no_code = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    no_code = re.sub(r"`[^`\n]*`", "", no_code)
    return [m.group(1).strip() for m in LINK_RE.finditer(no_code)]


def iter_world_articles(root: Path):
    """Yield (relpath, Path) for every world article (excluding _index.md)."""
    for path in sorted((root / "world").rglob("*.md")):
        if path.name == "_index.md":
            continue
        yield path.relative_to(root).as_posix(), path


def iter_session_logs(root: Path):
    sessions = root / "sessions"
    if not sessions.is_dir():
        return
    for path in sorted(sessions.glob("*.md")):
        yield path.relative_to(root).as_posix(), path


def build_id_map(root: Path) -> dict[str, list[str]]:
    """Map frontmatter id -> [relpaths] across the whole wiki (lists expose duplicates)."""
    ids: dict[str, list[str]] = {}
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        # demo/ is staging material for the demo-campaign branch, not live wiki
        if rel.startswith((".github/", "scripts/", "tests/", "demo/")):
            continue
        try:
            fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if fm and isinstance(fm.get("id"), str):
            ids.setdefault(fm["id"], []).append(rel)
    return ids


def quick_reference(body: str) -> str | None:
    """The text of an article's '## Quick Reference' section, if present."""
    m = re.search(r"^## Quick Reference\s*\n(.*?)(?=^## |\Z)", body, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else None


def _escape_command_data(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_command_prop(value: str) -> str:
    return _escape_command_data(value).replace(":", "%3A").replace(",", "%2C")


def error(path: str, msg: str) -> str:
    """A GitHub Actions error annotation line."""
    return f"::error file={_escape_command_prop(path)}::{_escape_command_data(msg)}"


def warning(path: str, msg: str) -> str:
    return f"::warning file={_escape_command_prop(path)}::{_escape_command_data(msg)}"
