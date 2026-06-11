"""Tests for check_style.py: controlled_tags and the style audit logic."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from check_style import controlled_tags  # noqa: E402


# ---------------------------------------------------------------------------
# controlled_tags
# ---------------------------------------------------------------------------

SAMPLE_CONVENTIONS = """\
# Conventions

## NPC Tags

**Disposition:** `friendly`, `neutral`, `wary`, `hostile`
**Role:** `political`, `mystical`, `memory`
"""


class TestControlledTags(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.meta = self.tmp / "meta"
        self.meta.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_parses_tags_from_conventions(self):
        (self.meta / "conventions.md").write_text(SAMPLE_CONVENTIONS)
        tags = controlled_tags(self.tmp)
        self.assertIsNotNone(tags)
        self.assertIn("friendly", tags)
        self.assertIn("neutral", tags)
        self.assertIn("wary", tags)
        self.assertIn("hostile", tags)
        self.assertIn("political", tags)
        self.assertIn("mystical", tags)
        self.assertIn("memory", tags)

    def test_returns_none_when_no_conventions_file(self):
        result = controlled_tags(self.tmp)
        self.assertIsNone(result)

    def test_returns_none_when_no_tagged_lines(self):
        (self.meta / "conventions.md").write_text("# No tags defined here\n\nJust prose.\n")
        result = controlled_tags(self.tmp)
        self.assertIsNone(result)

    def test_multiple_categories_collected(self):
        conv = "**A:** `alpha`, `beta`\n**B:** `gamma`\n"
        (self.meta / "conventions.md").write_text(conv)
        tags = controlled_tags(self.tmp)
        self.assertEqual(tags, {"alpha", "beta", "gamma"})

    def test_does_not_include_non_backtick_words(self):
        (self.meta / "conventions.md").write_text("**Category:** `valid` and not-this-one\n")
        tags = controlled_tags(self.tmp)
        self.assertIn("valid", tags)
        self.assertNotIn("not-this-one", tags)
        self.assertNotIn("and", tags)


# ---------------------------------------------------------------------------
# check_style.py via subprocess
# ---------------------------------------------------------------------------

def _make_valid_npc(path: Path, npc_id: str = "npc-test", link_from: Path | None = None) -> None:
    """Write a valid NPC article. If link_from is given, write a file that links to it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nid: {npc_id}\ntitle: Test NPC\ntype: npc\ntags: []\nstatus: alive\n"
        f"importance: minor\nfirst_seen: session-zero\nlast_seen: session-zero\n"
        f"related: []\nsummary: A test NPC\n---\n\n## Quick Reference\n\nA brief reference.\n\n## Details\nDetails.\n"
    )
    if link_from is not None:
        link_from.write_text(f"# Index\n\n- [[{npc_id}]] — A test NPC\n")


class TestCheckStyleSubprocess(unittest.TestCase):

    def run_style(self, root: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "check_style.py"), "--root", str(root)],
            capture_output=True, text=True,
        )

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_always_exits_zero(self):
        # check_style.py is warn-only and must always exit 0
        proc = self.run_style(self.tmp)
        self.assertEqual(proc.returncode, 0)

    def test_nothing_to_flag_on_empty_world(self):
        proc = self.run_style(self.tmp)
        self.assertIn("nothing to flag", proc.stdout)

    def test_orphan_detected_with_no_incoming_links(self):
        world = self.tmp / "world" / "npcs"
        world.mkdir(parents=True)
        _make_valid_npc(world / "npc-lone.md", npc_id="npc-lone")
        proc = self.run_style(self.tmp)
        self.assertEqual(proc.returncode, 0)  # warn-only
        self.assertIn("orphan", proc.stdout)
        self.assertIn("npc-lone", proc.stdout)

    def test_no_orphan_when_linked(self):
        world = self.tmp / "world" / "npcs"
        world.mkdir(parents=True)
        idx = world / "_index.md"
        _make_valid_npc(world / "npc-linked.md", npc_id="npc-linked", link_from=idx)
        proc = self.run_style(self.tmp)
        self.assertNotIn("orphan", proc.stdout)

    def test_quick_reference_bloat_detected(self):
        world = self.tmp / "world" / "npcs"
        world.mkdir(parents=True)
        idx = world / "_index.md"
        idx.write_text("# NPCs\n\n- [[npc-bloat]] — Bloated NPC\n")
        # QR with 11 non-blank lines
        qr_lines = "\n".join(f"- Line {i}" for i in range(11))
        (world / "npc-bloat.md").write_text(
            f"---\nid: npc-bloat\ntitle: Bloat\ntype: npc\ntags: []\nstatus: alive\n"
            f"importance: minor\nfirst_seen: s0\nlast_seen: s0\nrelated: []\nsummary: Bloated\n---\n\n"
            f"## Quick Reference\n\n{qr_lines}\n\n## Details\nFull.\n"
        )
        proc = self.run_style(self.tmp)
        self.assertEqual(proc.returncode, 0)  # warn-only
        self.assertIn("Quick Reference exceeds 10 lines", proc.stdout)

    def test_quick_reference_exactly_10_lines_ok(self):
        world = self.tmp / "world" / "npcs"
        world.mkdir(parents=True)
        idx = world / "_index.md"
        idx.write_text("# NPCs\n\n- [[npc-ok]] — OK NPC\n")
        qr_lines = "\n".join(f"- Line {i}" for i in range(10))
        (world / "npc-ok.md").write_text(
            f"---\nid: npc-ok\ntitle: OK\ntype: npc\ntags: []\nstatus: alive\n"
            f"importance: minor\nfirst_seen: s0\nlast_seen: s0\nrelated: []\nsummary: OK NPC\n---\n\n"
            f"## Quick Reference\n\n{qr_lines}\n\n## Details\nFull.\n"
        )
        proc = self.run_style(self.tmp)
        self.assertNotIn("Quick Reference exceeds 10 lines", proc.stdout)

    def test_uncontrolled_tag_detected_when_conventions_defined(self):
        meta = self.tmp / "meta"
        meta.mkdir()
        (meta / "conventions.md").write_text("**Disposition:** `friendly`, `neutral`\n")
        world = self.tmp / "world" / "npcs"
        world.mkdir(parents=True)
        idx = world / "_index.md"
        idx.write_text("# NPCs\n\n- [[npc-tagged]] — Tagged NPC\n")
        (world / "npc-tagged.md").write_text(
            "---\nid: npc-tagged\ntitle: Tagged\ntype: npc\ntags: [unknown-tag]\nstatus: alive\n"
            "importance: minor\nfirst_seen: s0\nlast_seen: s0\nrelated: []\nsummary: Tagged\n---\n\n"
            "## Quick Reference\nA reference.\n"
        )
        proc = self.run_style(self.tmp)
        self.assertEqual(proc.returncode, 0)  # warn-only
        self.assertIn("unknown-tag", proc.stdout)
        self.assertIn("not in the controlled list", proc.stdout)

    def test_controlled_tag_no_warning(self):
        meta = self.tmp / "meta"
        meta.mkdir()
        (meta / "conventions.md").write_text("**Disposition:** `friendly`, `neutral`\n")
        world = self.tmp / "world" / "npcs"
        world.mkdir(parents=True)
        idx = world / "_index.md"
        idx.write_text("# NPCs\n\n- [[npc-good]] — Good NPC\n")
        (world / "npc-good.md").write_text(
            "---\nid: npc-good\ntitle: Good\ntype: npc\ntags: [friendly]\nstatus: alive\n"
            "importance: minor\nfirst_seen: s0\nlast_seen: s0\nrelated: []\nsummary: Good NPC\n---\n\n"
            "## Quick Reference\nA reference.\n"
        )
        proc = self.run_style(self.tmp)
        self.assertNotIn("not in the controlled list", proc.stdout)


if __name__ == "__main__":
    unittest.main()