import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from weave_cost import file_cost, read_weave, total_cost  # noqa: E402


class TestWeaveCost(unittest.TestCase):
    def test_free_paths(self):
        for path in ("sessions/2026-06-11-01.md", "character/journal.md", "world/npcs/_index.md",
                     "meta/seeds.md", "meta/contradictions.md"):
            self.assertEqual(file_cost(path, 100, False)[0], 0, path)

    def test_engine_paths_are_outside_the_fiction(self):
        self.assertEqual(file_cost(".github/workflows/validate.yml", 500, True), (0, "outside the fiction"))
        self.assertEqual(file_cost("scripts/dice.py", 50, False)[0], 0)

    def test_world_costs(self):
        self.assertEqual(file_cost("world/npcs/harald.md", 10, False)[0], 2)   # ceil(10/5)
        self.assertEqual(file_cost("world/npcs/harald.md", 11, False)[0], 3)
        self.assertEqual(file_cost("world/npcs/harald.md", 10, True)[0], 4)    # +2 summon

    def test_plot_and_sheet(self):
        self.assertEqual(file_cost("plot/state.md", 25, False)[0], 3)          # ceil(25/10)
        self.assertEqual(file_cost("character/sheet.md", 5, False)[0], 1)

    def test_canon_triple(self):
        self.assertEqual(file_cost("meta/canon.md", 10, False)[0], 6)          # ceil(10/5)*3

    def test_total_minimum_one(self):
        rows = [{"cost": 0}, {"cost": 0}]
        self.assertEqual(total_cost(rows), 1)
        self.assertEqual(total_cost([]), 0)

    def test_read_weave(self):
        sheet = "---\nid: character-sheet\nweave: 7\nweave_max: 10\n---\n\nbody\n"
        self.assertEqual(read_weave(sheet), (7, 10))
        self.assertEqual(read_weave("# no frontmatter\n"), (None, None))


if __name__ == "__main__":
    unittest.main()
