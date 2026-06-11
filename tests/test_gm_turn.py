"""Tests for gm_turn.py: parse_envelope, check_paths, session_file, apply_envelope."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from gm_turn import (  # noqa: E402
    WEAVE_REGEN,
    apply_envelope,
    check_paths,
    parse_envelope,
    session_file,
)


# ---------------------------------------------------------------------------
# parse_envelope
# ---------------------------------------------------------------------------

class TestParseEnvelope(unittest.TestCase):

    def _valid(self, extra: str = "") -> str:
        return f'{{"narration": "The fog thickens.", "pr_title": "A dark night"{extra}}}'

    def test_plain_json(self):
        env = parse_envelope(self._valid())
        self.assertEqual(env["narration"], "The fog thickens.")
        self.assertEqual(env["pr_title"], "A dark night")

    def test_json_inside_markdown_fence(self):
        raw = f"Some preamble\n```json\n{self._valid()}\n```\nTrailing text"
        env = parse_envelope(raw)
        self.assertEqual(env["pr_title"], "A dark night")

    def test_json_inside_unlabeled_fence(self):
        raw = f"```\n{self._valid()}\n```"
        env = parse_envelope(raw)
        self.assertEqual(env["narration"], "The fog thickens.")

    def test_surrounding_prose_with_braces(self):
        # JSON extraction looks for first { and last }, so prose around it is tolerated
        raw = "Here is the output: " + self._valid() + " done."
        env = parse_envelope(raw)
        self.assertEqual(env["pr_title"], "A dark night")

    def test_extra_fields_are_preserved(self):
        raw = self._valid(', "files": [], "quests": []')
        env = parse_envelope(raw)
        self.assertEqual(env["files"], [])

    def test_missing_narration_raises(self):
        with self.assertRaises(ValueError):
            parse_envelope('{"pr_title": "title"}')

    def test_missing_pr_title_raises(self):
        with self.assertRaises(ValueError):
            parse_envelope('{"narration": "something"}')

    def test_empty_narration_raises(self):
        with self.assertRaises(ValueError):
            parse_envelope('{"narration": "", "pr_title": "title"}')

    def test_no_json_raises(self):
        with self.assertRaises(ValueError):
            parse_envelope("No JSON here at all.")

    def test_invalid_json_raises(self):
        with self.assertRaises((ValueError, Exception)):
            parse_envelope("{bad json}")

    def test_non_dict_json_raises(self):
        with self.assertRaises(ValueError):
            parse_envelope('["narration", "pr_title"]')


# ---------------------------------------------------------------------------
# check_paths
# ---------------------------------------------------------------------------

class TestCheckPaths(unittest.TestCase):

    def _file(self, path: str, op: str = "replace", content: str = "x") -> dict:
        return {"path": path, "op": op, "content": content}

    def test_allowed_world_path(self):
        check_paths({"files": [self._file("world/npcs/npc-test.md")]})  # should not raise

    def test_allowed_plot_path(self):
        check_paths({"files": [self._file("plot/state.md")]})

    def test_allowed_sessions_path(self):
        check_paths({"files": [self._file("sessions/2026-06-11-01.md")]})

    def test_allowed_character_journal(self):
        check_paths({"files": [self._file("character/journal.md")]})

    def test_allowed_character_sheet(self):
        check_paths({"files": [self._file("character/sheet.md")]})

    def test_forbidden_meta_canon(self):
        with self.assertRaises(ValueError):
            check_paths({"files": [self._file("meta/canon.md")]})

    def test_forbidden_meta_rolls(self):
        with self.assertRaises(ValueError):
            check_paths({"files": [self._file("meta/rolls.md")]})

    def test_forbidden_github_dir(self):
        with self.assertRaises(ValueError):
            check_paths({"files": [self._file(".github/workflows/gm-turn.yml")]})

    def test_forbidden_scripts_dir(self):
        with self.assertRaises(ValueError):
            check_paths({"files": [self._file("scripts/dice.py")]})

    def test_forbidden_tests_dir(self):
        with self.assertRaises(ValueError):
            check_paths({"files": [self._file("tests/test_dice.py")]})

    def test_path_outside_allowlist(self):
        with self.assertRaises(ValueError):
            check_paths({"files": [self._file("README.md")]})

    def test_path_outside_allowlist_meta_non_forbidden(self):
        # meta/ is not in ALLOWED_PREFIXES; only specific forbidden paths trigger that check
        with self.assertRaises(ValueError):
            check_paths({"files": [self._file("meta/seeds.md")]})

    def test_bad_op_raises(self):
        with self.assertRaises(ValueError):
            check_paths({"files": [{"path": "world/npcs/x.md", "op": "delete", "content": "x"}]})

    def test_missing_content_raises(self):
        with self.assertRaises(ValueError):
            check_paths({"files": [{"path": "world/npcs/x.md", "op": "replace"}]})

    def test_content_none_raises(self):
        with self.assertRaises(ValueError):
            check_paths({"files": [{"path": "world/npcs/x.md", "op": "replace", "content": None}]})

    def test_all_three_ops_allowed(self):
        for op in ("create", "replace", "append"):
            check_paths({"files": [self._file("world/items/sword.md", op=op)]})

    def test_no_files_no_error(self):
        check_paths({"narration": "ok", "pr_title": "ok"})

    def test_empty_files_list(self):
        check_paths({"files": []})

    def test_valid_index_update(self):
        check_paths({"index_updates": [{"index": "world/npcs/_index.md", "id": "npc-test", "line": "- [[npc-test]] — A test NPC"}]})

    def test_invalid_index_update_not_world(self):
        with self.assertRaises(ValueError):
            check_paths({"index_updates": [{"index": "meta/seeds.md", "id": "x", "line": "- [[x]]"}]})

    def test_invalid_index_update_not_index(self):
        with self.assertRaises(ValueError):
            check_paths({"index_updates": [{"index": "world/npcs/npc-test.md", "id": "npc-test", "line": "x"}]})


# ---------------------------------------------------------------------------
# session_file
# ---------------------------------------------------------------------------

class TestSessionFile(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_creates_sessions_dir_and_file(self):
        today = "2026-06-11"
        path = session_file(self.tmp, today, "Test Action")
        self.assertTrue(path.exists())
        self.assertEqual(path.name, f"{today}-01.md")
        content = path.read_text()
        self.assertIn("date: 2026-06-11", content)
        self.assertIn("Test Action", content)

    def test_returns_existing_session(self):
        today = "2026-06-11"
        sessions = self.tmp / "sessions"
        sessions.mkdir()
        existing = sessions / f"{today}-01.md"
        existing.write_text("---\ndate: 2026-06-11\nsummary: Prior\n---\n\n# Existing\n")
        path = session_file(self.tmp, today, "New Action")
        self.assertEqual(path, existing)

    def test_returns_last_session_when_multiple_exist(self):
        today = "2026-06-11"
        sessions = self.tmp / "sessions"
        sessions.mkdir()
        (sessions / f"{today}-01.md").write_text("first")
        (sessions / f"{today}-02.md").write_text("second")
        path = session_file(self.tmp, today, "Third Action")
        self.assertEqual(path.name, f"{today}-02.md")

    def test_new_file_has_correct_frontmatter(self):
        today = "2026-06-15"
        path = session_file(self.tmp, today, "Investigate the lantern")
        content = path.read_text()
        self.assertIn("date:", content)
        self.assertIn("summary: Investigate the lantern", content)


# ---------------------------------------------------------------------------
# apply_envelope
# ---------------------------------------------------------------------------

class TestApplyEnvelope(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        # Create required directories and files
        (self.tmp / "sessions").mkdir()
        (self.tmp / "character").mkdir()
        (self.tmp / "meta").mkdir()
        (self.tmp / "plot").mkdir()
        # Character sheet with weave
        sheet = self.tmp / "character" / "sheet.md"
        sheet.write_text("---\nid: character-sheet\nweave: 8\nweave_max: 10\n---\n\n# Sheet\n")
        # Plot state
        state = self.tmp / "plot" / "state.md"
        state.write_text("---\nturn: 0\n---\n\n# State\n")
        # Rolls ledger
        rolls_md = self.tmp / "meta" / "rolls.md"
        rolls_md.write_text("# Rolls Ledger\n\n| Turn | PR | Action id | Expr | Dice | Total | Entropy SHA |\n|---|---|---|---|---|---|---|\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _basic_env(self, extra: dict | None = None) -> dict:
        env = {"narration": "The fog rolls in.", "pr_title": "Inspect the lantern"}
        if extra:
            env.update(extra)
        return env

    def test_narration_appended_to_session_log(self):
        env = self._basic_env()
        apply_envelope(self.tmp, env, 1, 42, "Inspect the lantern", [], "abc123", 0)
        logs = list((self.tmp / "sessions").glob("*.md"))
        self.assertEqual(len(logs), 1)
        content = logs[0].read_text()
        self.assertIn("The fog rolls in.", content)
        self.assertIn("Turn 1", content)
        self.assertIn("PR #42", content)

    def test_file_create(self):
        env = self._basic_env({
            "files": [{"path": "world/npcs/npc-eska.md", "op": "create", "content": "# Eska\n"}]
        })
        apply_envelope(self.tmp, env, 1, 42, "Eska appears", [], "abc123", 0)
        created = self.tmp / "world" / "npcs" / "npc-eska.md"
        self.assertTrue(created.exists())
        self.assertIn("# Eska", created.read_text())

    def test_file_replace(self):
        target = self.tmp / "world" / "npcs"
        target.mkdir(parents=True)
        (target / "npc-test.md").write_text("old content")
        env = self._basic_env({
            "files": [{"path": "world/npcs/npc-test.md", "op": "replace", "content": "new content"}]
        })
        apply_envelope(self.tmp, env, 1, 42, "Test replace", [], "abc123", 0)
        self.assertEqual((target / "npc-test.md").read_text().strip(), "new content")

    def test_file_append(self):
        target = self.tmp / "world" / "npcs"
        target.mkdir(parents=True)
        existing = target / "npc-test.md"
        existing.write_text("existing content")
        env = self._basic_env({
            "files": [{"path": "world/npcs/npc-test.md", "op": "append", "content": "appended content"}]
        })
        apply_envelope(self.tmp, env, 1, 42, "Test append", [], "abc123", 0)
        text = existing.read_text()
        self.assertIn("existing content", text)
        self.assertIn("appended content", text)

    def test_weave_deducted_and_regen_applied(self):
        # Initial weave: 8, cost: 3, regen: 2 -> expected: min(max(8-3+2,0),10) = 7
        env = self._basic_env()
        apply_envelope(self.tmp, env, 1, 42, "Test weave", [], "abc123", 3)
        from lib.wiki import parse_frontmatter
        fm, _ = parse_frontmatter((self.tmp / "character" / "sheet.md").read_text())
        self.assertEqual(fm["weave"], 7)

    def test_weave_clamped_to_max(self):
        # weave: 9, cost: 0, regen: 2 -> expected: min(max(9-0+2,0),10) = 10
        sheet = self.tmp / "character" / "sheet.md"
        sheet.write_text("---\nid: character-sheet\nweave: 9\nweave_max: 10\n---\n\n# Sheet\n")
        env = self._basic_env()
        apply_envelope(self.tmp, env, 1, 42, "Test weave max", [], "abc123", 0)
        from lib.wiki import parse_frontmatter
        fm, _ = parse_frontmatter(sheet.read_text())
        self.assertEqual(fm["weave"], 10)

    def test_weave_clamped_to_zero(self):
        # weave: 1, cost: 5, regen: 2 -> expected: min(max(1-5+2,0),10) = 0
        sheet = self.tmp / "character" / "sheet.md"
        sheet.write_text("---\nid: character-sheet\nweave: 1\nweave_max: 10\n---\n\n# Sheet\n")
        env = self._basic_env()
        apply_envelope(self.tmp, env, 1, 42, "Test weave zero", [], "abc123", 5)
        from lib.wiki import parse_frontmatter
        fm, _ = parse_frontmatter(sheet.read_text())
        self.assertEqual(fm["weave"], 0)

    def test_weave_not_touched_when_no_weave_field(self):
        sheet = self.tmp / "character" / "sheet.md"
        sheet.write_text("---\nid: character-sheet\n---\n\n# Sheet\n")
        original = sheet.read_text()
        env = self._basic_env()
        apply_envelope(self.tmp, env, 1, 42, "No weave", [], "abc123", 2)
        # sheet should not have weave added automatically (no weave field in original)
        from lib.wiki import parse_frontmatter
        fm, _ = parse_frontmatter(sheet.read_text())
        self.assertNotIn("weave", fm or {})

    def test_plot_state_updated(self):
        env = self._basic_env({"plot_state": "# State\n\nNew state text."})
        apply_envelope(self.tmp, env, 3, 42, "Update state", [], "abc123", 0)
        from lib.wiki import parse_frontmatter
        fm, body = parse_frontmatter((self.tmp / "plot" / "state.md").read_text())
        self.assertEqual(fm["turn"], 3)
        self.assertIn("New state text.", body)

    def test_plot_state_turn_always_updated(self):
        env = self._basic_env()  # no plot_state in env
        apply_envelope(self.tmp, env, 5, 42, "Turn counter", [], "abc123", 0)
        from lib.wiki import parse_frontmatter
        fm, _ = parse_frontmatter((self.tmp / "plot" / "state.md").read_text())
        self.assertEqual(fm["turn"], 5)

    def test_rolls_appended_to_ledger(self):
        rolls = [{"action_id": "pick-lock", "expr": "1d20+2", "dice": [15], "total": 17}]
        env = self._basic_env()
        apply_envelope(self.tmp, env, 2, 42, "Pick the lock", rolls, "deadbeef", 0)
        ledger = (self.tmp / "meta" / "rolls.md").read_text()
        self.assertIn("pick-lock", ledger)
        self.assertIn("1d20+2", ledger)
        self.assertIn("17", ledger)
        self.assertIn("deadbeef", ledger)

    def test_no_rolls_ledger_unchanged(self):
        rolls_md = self.tmp / "meta" / "rolls.md"
        original = rolls_md.read_text()
        env = self._basic_env()
        apply_envelope(self.tmp, env, 1, 42, "No dice", [], "abc123", 0)
        self.assertEqual(rolls_md.read_text(), original)

    def test_journal_appended_when_suggestion_provided(self):
        journal = self.tmp / "character" / "journal.md"
        journal.write_text("# Journal\n")
        env = self._basic_env({"journal_suggestion": "Eska felt the cold of the fog."})
        apply_envelope(self.tmp, env, 1, 42, "Test journal", [], "abc123", 0)
        text = journal.read_text()
        self.assertIn("Eska felt the cold of the fog.", text)

    def test_journal_created_if_missing(self):
        env = self._basic_env({"journal_suggestion": "First entry."})
        apply_envelope(self.tmp, env, 1, 42, "Create journal", [], "abc123", 0)
        journal = self.tmp / "character" / "journal.md"
        self.assertTrue(journal.exists())
        self.assertIn("First entry.", journal.read_text())

    def test_contradictions_appended(self):
        contradictions = self.tmp / "meta" / "contradictions.md"
        contradictions.write_text("# Contradictions\n")
        env = self._basic_env({
            "contradictions": [{"summary": "Lantern paradox", "detail": "The lantern cannot be both lit and dark."}]
        })
        apply_envelope(self.tmp, env, 1, 42, "Paradox", [], "abc123", 0)
        text = contradictions.read_text()
        self.assertIn("Lantern paradox", text)
        self.assertIn("The lantern cannot be both lit and dark.", text)

    def test_index_update_appends_new_entry(self):
        idx = self.tmp / "world" / "npcs" / "_index.md"
        idx.parent.mkdir(parents=True)
        idx.write_text("# NPCs\n\n")
        env = self._basic_env({
            "index_updates": [{"index": "world/npcs/_index.md", "id": "npc-eska", "line": "- [[npc-eska]] — Salvage diver"}]
        })
        apply_envelope(self.tmp, env, 1, 42, "Index update", [], "abc123", 0)
        text = idx.read_text()
        self.assertIn("[[npc-eska]]", text)
        self.assertIn("Salvage diver", text)

    def test_index_update_replaces_existing_entry(self):
        idx = self.tmp / "world" / "npcs" / "_index.md"
        idx.parent.mkdir(parents=True)
        idx.write_text("# NPCs\n\n- [[npc-eska]] — Old description\n")
        env = self._basic_env({
            "index_updates": [{"index": "world/npcs/_index.md", "id": "npc-eska", "line": "- [[npc-eska]] — Updated description"}]
        })
        apply_envelope(self.tmp, env, 1, 42, "Index replace", [], "abc123", 0)
        text = idx.read_text()
        self.assertNotIn("Old description", text)
        self.assertIn("Updated description", text)

    def test_index_update_creates_index_if_missing(self):
        idx = self.tmp / "world" / "factions" / "_index.md"
        idx.parent.mkdir(parents=True)
        env = self._basic_env({
            "index_updates": [{"index": "world/factions/_index.md", "id": "faction-drowned", "line": "- [[faction-drowned]] — The drowned"}]
        })
        apply_envelope(self.tmp, env, 1, 42, "Create index", [], "abc123", 0)
        self.assertTrue(idx.exists())
        self.assertIn("[[faction-drowned]]", idx.read_text())

    def test_files_content_trailing_newline_normalized(self):
        env = self._basic_env({
            "files": [{"path": "world/npcs/npc-new.md", "op": "create", "content": "# New\n\nContent\n\n\n"}]
        })
        apply_envelope(self.tmp, env, 1, 42, "Newlines", [], "abc123", 0)
        content = (self.tmp / "world" / "npcs" / "npc-new.md").read_text()
        self.assertTrue(content.endswith("\n"))
        self.assertFalse(content.endswith("\n\n"))

    def test_weave_regen_constant_is_two(self):
        self.assertEqual(WEAVE_REGEN, 2)


if __name__ == "__main__":
    unittest.main()