"""Tests for gm_context.py: latest_session, assemble, _section."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from gm_context import TOKEN_BUDGET, _section, assemble, latest_session  # noqa: E402


# ---------------------------------------------------------------------------
# _section helper
# ---------------------------------------------------------------------------

class TestSection(unittest.TestCase):

    def test_format(self):
        result = _section("my-title", "body text")
        self.assertIn("===== my-title =====", result)
        self.assertIn("body text", result)

    def test_body_is_stripped(self):
        result = _section("title", "  body  \n\n")
        self.assertIn("body", result)
        # Should not have trailing whitespace in body
        self.assertNotIn("  body  ", result)

    def test_empty_body(self):
        result = _section("title", "")
        self.assertIn("===== title =====", result)


# ---------------------------------------------------------------------------
# latest_session
# ---------------------------------------------------------------------------

class TestLatestSession(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_sessions_dir_returns_none(self):
        self.assertIsNone(latest_session(self.tmp))

    def test_empty_sessions_dir_returns_none(self):
        (self.tmp / "sessions").mkdir()
        self.assertIsNone(latest_session(self.tmp))

    def test_single_session_returned(self):
        sessions = self.tmp / "sessions"
        sessions.mkdir()
        log = sessions / "2026-06-11-01.md"
        log.write_text("# Session log\n")
        result = latest_session(self.tmp)
        self.assertIsNotNone(result)
        rel, text = result
        self.assertEqual(rel, "sessions/2026-06-11-01.md")
        self.assertIn("Session log", text)

    def test_latest_session_by_sort_order(self):
        sessions = self.tmp / "sessions"
        sessions.mkdir()
        (sessions / "2026-06-10-01.md").write_text("earlier")
        (sessions / "2026-06-11-01.md").write_text("later")
        (sessions / "2026-06-11-02.md").write_text("latest")
        rel, text = latest_session(self.tmp)
        self.assertEqual(rel, "sessions/2026-06-11-02.md")
        self.assertEqual(text, "latest")

    def test_returns_relpath_as_posix(self):
        sessions = self.tmp / "sessions"
        sessions.mkdir()
        (sessions / "2026-01-01-01.md").write_text("content")
        rel, _ = latest_session(self.tmp)
        self.assertIn("/", rel)
        self.assertFalse(rel.startswith("/"))


# ---------------------------------------------------------------------------
# assemble
# ---------------------------------------------------------------------------

class TestAssemble(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, rel: str, content: str) -> Path:
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return p

    def test_minimal_assemble_contains_pr_section(self):
        result = assemble(self.tmp, "My Action", "body text", "diff", [], "cost: 0")
        self.assertIn("THE MERGED PLAYER ACTION (PR)", result)
        self.assertIn("My Action", result)
        self.assertIn("body text", result)

    def test_assemble_contains_diff_section(self):
        result = assemble(self.tmp, "Title", "body", "--- a/file\n+++ b/file", [], "cost: 0")
        self.assertIn("ACTION DIFF", result)
        self.assertIn("--- a/file", result)

    def test_assemble_contains_weave_cost_section(self):
        result = assemble(self.tmp, "Title", "body", "diff", [], "Weave cost: 3")
        self.assertIn("WEAVE COST", result)
        self.assertIn("Weave cost: 3", result)

    def test_boot_files_included_when_present(self):
        self._write("index.md", "# Index\nNavigation here.\n")
        result = assemble(self.tmp, "Title", "body", "diff", [], "cost: 0")
        self.assertIn("index.md", result)
        self.assertIn("Navigation here.", result)

    def test_missing_boot_files_skipped(self):
        # No files at all — should not raise
        result = assemble(self.tmp, "Title", "", "", [], "")
        self.assertIn("THE MERGED PLAYER ACTION (PR)", result)

    def test_latest_session_included(self):
        sessions = self.tmp / "sessions"
        sessions.mkdir()
        (sessions / "2026-06-11-01.md").write_text("The hero walked into the fog.")
        result = assemble(self.tmp, "Title", "body", "diff", [], "cost: 0")
        self.assertIn("The hero walked into the fog.", result)
        self.assertIn("latest session log", result)

    def test_dice_results_section_included_when_rolls_present(self):
        rolls = [{"action_id": "spot-guard", "expr": "1d20", "dice": [14], "total": 14}]
        result = assemble(self.tmp, "Title", "body", "diff", rolls, "cost: 0")
        self.assertIn("FATE", result)
        self.assertIn("spot-guard", result)
        self.assertIn("1d20", result)
        self.assertIn("14", result)

    def test_no_dice_results_section_excluded(self):
        result = assemble(self.tmp, "Title", "body", "diff", [], "cost: 0")
        self.assertNotIn("FATE", result)

    def test_entity_resolution_includes_mentioned_article(self):
        # Create an article with a known id
        self._write("world/npcs/npc-eska.md",
                    "---\nid: npc-eska\ntitle: Eska\ntype: npc\ntags: []\nstatus: alive\n"
                    "importance: major\nfirst_seen: s0\nlast_seen: s0\nrelated: []\n"
                    "summary: The diver\n---\n\n## Quick Reference\nDiver.\n\n## Details\nFull text.\n")
        # Body mentions [[npc-eska]]
        result = assemble(self.tmp, "Title", "She spoke to [[npc-eska]].", "diff", [], "cost: 0")
        self.assertIn("npc-eska", result)
        self.assertIn("Full text.", result)

    def test_entity_resolution_loads_category_index(self):
        # Article exists with an id, and its category _index exists
        self._write("world/npcs/npc-eska.md",
                    "---\nid: npc-eska\ntitle: Eska\ntype: npc\ntags: []\nstatus: alive\n"
                    "importance: major\nfirst_seen: s0\nlast_seen: s0\nrelated: []\n"
                    "summary: The diver\n---\n\n## Quick Reference\nDiver.\n")
        self._write("world/npcs/_index.md", "# NPCs\n\n- [[npc-eska]] — The diver\n")
        result = assemble(self.tmp, "Title", "[[npc-eska]] went diving.", "diff", [], "cost: 0")
        self.assertIn("_index.md", result)

    def test_no_entity_resolution_for_unrecognized_ids(self):
        # A link to a non-existent article id should not crash
        result = assemble(self.tmp, "Title", "[[nonexistent-id]] appeared.", "diff", [], "cost: 0")
        self.assertIn("THE MERGED PLAYER ACTION (PR)", result)

    def test_diff_truncated_at_30000_chars(self):
        long_diff = "+" + "x" * 40_000
        result = assemble(self.tmp, "Title", "body", long_diff, [], "cost: 0")
        # The diff in the output should not contain more than 30000 chars of the long diff
        self.assertNotIn("x" * 35_000, result)

    def test_related_articles_in_tier2(self):
        # npc-eska has related: [npc-maren]; npc-maren has Quick Reference
        self._write("world/npcs/npc-eska.md",
                    "---\nid: npc-eska\ntitle: Eska\ntype: npc\ntags: []\nstatus: alive\n"
                    "importance: major\nfirst_seen: s0\nlast_seen: s0\nrelated: [npc-maren]\n"
                    "summary: The diver\n---\n\n## Quick Reference\nDiver.\n")
        self._write("world/npcs/npc-maren.md",
                    "---\nid: npc-maren\ntitle: Maren\ntype: npc\ntags: []\nstatus: alive\n"
                    "importance: major\nfirst_seen: s0\nlast_seen: s0\nrelated: []\n"
                    "summary: Keeper\n---\n\n## Quick Reference\nLantern keeper.\n\n## Details\nFull.\n")
        result = assemble(self.tmp, "Title", "[[npc-eska]] met someone.", "diff", [], "cost: 0")
        # Maren's Quick Reference should appear (Tier-2)
        self.assertIn("Lantern keeper.", result)
        # But Maren's full details should NOT appear (only QR in Tier-2)
        self.assertNotIn("Full.", result)

    def test_return_type_is_string(self):
        result = assemble(self.tmp, "T", "b", "d", [], "c")
        self.assertIsInstance(result, str)

    def test_token_budget_constant(self):
        self.assertEqual(TOKEN_BUDGET, 40_000)


if __name__ == "__main__":
    unittest.main()