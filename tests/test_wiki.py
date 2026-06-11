import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from lib.wiki import extract_links, parse_frontmatter, quick_reference, serialize_frontmatter  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class TestWiki(unittest.TestCase):
    def test_frontmatter_roundtrip(self):
        text = "---\nid: npc-harald\ntags: [friendly]\nweave: 3\n---\n\n## Quick Reference\nAn innkeeper.\n"
        fm, body = parse_frontmatter(text)
        self.assertEqual(fm["id"], "npc-harald")
        out = serialize_frontmatter(fm, body)
        fm2, body2 = parse_frontmatter(out)
        self.assertEqual(fm, fm2)
        self.assertEqual(body.strip(), body2.strip())

    def test_no_frontmatter(self):
        self.assertEqual(parse_frontmatter("# Heading\n"), (None, "# Heading\n"))

    def test_extract_links_skips_code(self):
        text = "See [[npc-harald|Harald]] and [[loc-oakford]].\n```\n[[not-a-link]]\n```\n`[[also-not]]`"
        self.assertEqual(extract_links(text), ["npc-harald", "loc-oakford"])

    def test_quick_reference(self):
        body = "## Quick Reference\nLine one.\nLine two.\n\n## Details\nLong.\n"
        self.assertEqual(quick_reference(body), "Line one.\nLine two.")
        self.assertIsNone(quick_reference("## Details\nonly\n"))


class TestValidatorsOnFixtures(unittest.TestCase):
    """The broken fixture wiki must trip every validator; the real repo must pass."""

    def run_validator(self, script: str, root: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), "--root", str(root)],
            capture_output=True, text=True,
        )

    def test_clean_repo_passes(self):
        for script in ("validate_frontmatter.py", "check_links.py", "check_indexes.py"):
            proc = self.run_validator(script, ROOT)
            self.assertEqual(proc.returncode, 0, f"{script} failed on clean repo:\n{proc.stdout}")

    def test_broken_fixture_fails(self):
        broken = FIXTURES / "broken-wiki"
        frontmatter = self.run_validator("validate_frontmatter.py", broken)
        self.assertEqual(frontmatter.returncode, 1)
        self.assertIn("missing required key", frontmatter.stdout)
        self.assertIn("does not match <type>-<slug>", frontmatter.stdout)

        links = self.run_validator("check_links.py", broken)
        self.assertEqual(links.returncode, 1)
        self.assertIn("unresolved link", links.stdout)

        indexes = self.run_validator("check_indexes.py", broken)
        self.assertEqual(indexes.returncode, 1)
        self.assertIn("missing from index", indexes.stdout)


if __name__ == "__main__":
    unittest.main()
