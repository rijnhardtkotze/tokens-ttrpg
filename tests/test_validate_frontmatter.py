"""Tests for validate_frontmatter.py: check_article and check_session at unit level."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from validate_frontmatter import (  # noqa: E402
    IMPORTANCE,
    REQUIRED,
    STATUSES,
    TYPES,
    check_article,
    check_session,
)


def _valid_npc_text(overrides: dict | None = None) -> str:
    fields = {
        "id": "npc-test",
        "title": "Test NPC",
        "type": "npc",
        "tags": "[]",
        "status": "alive",
        "importance": "minor",
        "first_seen": "session-zero",
        "last_seen": "session-zero",
        "related": "[]",
        "summary": "A test NPC for unit tests",
    }
    if overrides:
        fields.update(overrides)
    lines = ["---"]
    for k, v in fields.items():
        lines.append(f"{k}: {v}")
    lines += ["---", "", "# Test NPC", ""]
    return "\n".join(lines)


class TestCheckArticle(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.world_npcs = self.tmp / "world" / "npcs"
        self.world_npcs.mkdir(parents=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, text: str, filename: str = "npc-test.md") -> list[str]:
        path = self.world_npcs / filename
        path.write_text(text)
        rel = path.relative_to(self.tmp).as_posix()
        problems: list[str] = []
        check_article(rel, path, problems)
        return problems

    def test_valid_npc_no_problems(self):
        problems = self._run(_valid_npc_text())
        self.assertEqual(problems, [])

    def test_missing_frontmatter(self):
        problems = self._run("# No frontmatter here\n")
        self.assertTrue(any("missing frontmatter" in p for p in problems))

    def test_missing_required_key_id(self):
        text = _valid_npc_text({"id": None})
        # Remove the id line entirely
        lines = [l for l in text.splitlines() if not l.startswith("id:")]
        problems = self._run("\n".join(lines))
        self.assertTrue(any("id" in p and "missing" in p for p in problems))

    def test_missing_required_key_summary(self):
        lines = [l for l in _valid_npc_text().splitlines() if not l.startswith("summary:")]
        problems = self._run("\n".join(lines))
        self.assertTrue(any("summary" in p for p in problems))

    def test_all_required_keys_checked(self):
        # Each required key produces an error when missing
        for key in REQUIRED:
            lines = [l for l in _valid_npc_text().splitlines() if not l.startswith(f"{key}:")]
            problems = self._run("\n".join(lines))
            self.assertTrue(
                any(key in p for p in problems),
                f"Expected error about missing key '{key}', got: {problems}"
            )

    def test_invalid_type(self):
        problems = self._run(_valid_npc_text({"type": "dragon", "id": "dragon-bob"}))
        self.assertTrue(any("type" in p for p in problems))

    def test_valid_types_accepted(self):
        for t in TYPES:
            # Build a matching id prefix
            from lib.wiki import ID_PREFIX_FOR_TYPE, WORLD_DIR_FOR_TYPE
            prefix = ID_PREFIX_FOR_TYPE.get(t, t)
            subdir = WORLD_DIR_FOR_TYPE.get(t, f"{t}s")
            d = self.tmp / "world" / subdir
            d.mkdir(parents=True, exist_ok=True)
            fname = f"{prefix}-validtest.md"
            path = d / fname
            rel = path.relative_to(self.tmp).as_posix()
            path.write_text(_valid_npc_text({"id": f"{prefix}-validtest", "type": t}))
            problems: list[str] = []
            check_article(rel, path, problems)
            type_errors = [p for p in problems if "type" in p and "not one of" in p]
            self.assertEqual(type_errors, [], f"Type '{t}' should be valid, got: {type_errors}")

    def test_invalid_status(self):
        problems = self._run(_valid_npc_text({"status": "undead"}))
        self.assertTrue(any("status" in p for p in problems))

    def test_valid_statuses_accepted(self):
        for s in STATUSES:
            problems = self._run(_valid_npc_text({"status": s}))
            status_errors = [p for p in problems if "status" in p and "not one of" in p]
            self.assertEqual(status_errors, [], f"Status '{s}' should be valid")

    def test_invalid_importance(self):
        problems = self._run(_valid_npc_text({"importance": "legendary"}))
        self.assertTrue(any("importance" in p for p in problems))

    def test_valid_importances_accepted(self):
        for imp in IMPORTANCE:
            problems = self._run(_valid_npc_text({"importance": imp}))
            imp_errors = [p for p in problems if "importance" in p and "not one of" in p]
            self.assertEqual(imp_errors, [], f"Importance '{imp}' should be valid")

    def test_tags_must_be_list(self):
        problems = self._run(_valid_npc_text({"tags": "friendly"}))
        self.assertTrue(any("tags" in p for p in problems))

    def test_related_must_be_list(self):
        problems = self._run(_valid_npc_text({"related": "npc-other"}))
        self.assertTrue(any("related" in p for p in problems))

    def test_empty_summary_rejected(self):
        lines = _valid_npc_text().splitlines()
        # Replace summary with empty
        lines = [("summary: " if l.startswith("summary:") else l) for l in lines]
        problems = self._run("\n".join(lines))
        self.assertTrue(any("summary" in p for p in problems))

    def test_id_pattern_must_match(self):
        # id with uppercase should fail
        problems = self._run(_valid_npc_text({"id": "NPC-Test"}))
        self.assertTrue(any("does not match" in p or "id" in p for p in problems))

    def test_id_prefix_mismatch_for_type(self):
        # NPC id should start with npc-
        problems = self._run(_valid_npc_text({"id": "loc-test"}))
        self.assertTrue(any("should start with" in p or "does not match" in p for p in problems))

    def test_npc_must_be_in_world_npcs(self):
        # Put an NPC in wrong directory
        wrong_dir = self.tmp / "world" / "regions"
        wrong_dir.mkdir(parents=True, exist_ok=True)
        path = wrong_dir / "npc-test.md"
        path.write_text(_valid_npc_text())
        rel = path.relative_to(self.tmp).as_posix()
        problems: list[str] = []
        check_article(rel, path, problems)
        self.assertTrue(any("belongs under" in p for p in problems))

    def test_id_must_be_string_not_integer(self):
        problems = self._run(_valid_npc_text({"id": "123"}))
        # 123 doesn't match <type>-<slug> pattern
        self.assertTrue(any("does not match" in p or "id" in p for p in problems))


# ---------------------------------------------------------------------------
# check_session
# ---------------------------------------------------------------------------

class TestCheckSession(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.sessions = self.tmp / "sessions"
        self.sessions.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, text: str, filename: str = "2026-06-11-01.md") -> list[str]:
        path = self.sessions / filename
        path.write_text(text)
        rel = path.relative_to(self.tmp).as_posix()
        problems: list[str] = []
        check_session(rel, path, problems)
        return problems

    def test_valid_session_no_problems(self):
        text = "---\ndate: 2026-06-11\nsummary: Eska investigates the lantern.\n---\n\n# Session\n"
        self.assertEqual(self._run(text), [])

    def test_missing_frontmatter(self):
        problems = self._run("# No frontmatter\n")
        self.assertTrue(any("missing frontmatter" in p or "frontmatter" in p for p in problems))

    def test_missing_date(self):
        text = "---\nsummary: Something happened.\n---\n\n# Session\n"
        problems = self._run(text)
        self.assertTrue(any("date" in p for p in problems))

    def test_missing_summary(self):
        text = "---\ndate: 2026-06-11\n---\n\n# Session\n"
        problems = self._run(text)
        self.assertTrue(any("summary" in p for p in problems))

    def test_both_fields_required(self):
        # Both date and summary missing
        text = "---\nother: value\n---\n\n# Session\n"
        problems = self._run(text)
        keys_found = set()
        for p in problems:
            if "date" in p:
                keys_found.add("date")
            if "summary" in p:
                keys_found.add("summary")
        self.assertIn("date", keys_found)
        self.assertIn("summary", keys_found)

    def test_invalid_yaml_reported(self):
        text = "---\nkey: [\ninvalid yaml\n---\n\n# Session\n"
        problems = self._run(text)
        self.assertTrue(any("YAML" in p or "frontmatter" in p or "invalid" in p for p in problems))


# ---------------------------------------------------------------------------
# Full validator integration (duplicate id detection)
# ---------------------------------------------------------------------------

class TestDuplicateIdDetection(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_duplicate_id_reported(self):
        import subprocess
        d = self.tmp / "world" / "npcs"
        d.mkdir(parents=True)
        for fname in ("npc-dup-a.md", "npc-dup-b.md"):
            (d / fname).write_text(_valid_npc_text({"id": "npc-duplicate"}))
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate_frontmatter.py"), "--root", str(self.tmp)],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("duplicate id", proc.stdout)


if __name__ == "__main__":
    unittest.main()
