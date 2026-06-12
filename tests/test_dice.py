import collections
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from dice import DiceError, parse_expr, parse_rolls_block, roll, roll_die  # noqa: E402

SHA = "47a1cb2e9d3f5a1b8c6d4e2f0a9b8c7d6e5f4a3b"


class TestDice(unittest.TestCase):
    def test_deterministic(self):
        a = roll(SHA, 12, "pick-the-lock", "3d6+2")
        b = roll(SHA, 12, "pick-the-lock", "3d6+2")
        self.assertEqual(a, b)
        self.assertEqual(a["total"], sum(a["dice"]) + 2)

    def test_inputs_change_outcome(self):
        base = roll(SHA, 12, "pick-the-lock", "1d20")["dice"]
        self.assertNotEqual(base, roll(SHA, 13, "pick-the-lock", "1d20")["dice"])
        self.assertNotEqual(base, roll(SHA, 12, "pick-the-locks", "1d20")["dice"])
        self.assertNotEqual(base, roll(SHA.replace("4", "5"), 12, "pick-the-lock", "1d20")["dice"])

    def test_entropy_case_insensitive(self):
        self.assertEqual(roll(SHA.upper(), 1, "a", "1d20"), roll(SHA, 1, "a", "1d20"))

    def test_range_and_rough_uniformity(self):
        counts = collections.Counter(roll_die(SHA, pr, "u", i, 20) for pr in range(50) for i in range(200))
        self.assertEqual(set(counts), set(range(1, 21)))
        for face, n in counts.items():
            self.assertGreater(n, 350, f"face {face} suspiciously rare")  # 10000/20 = 500 expected

    def test_expr_validation(self):
        for bad in ("0d6", "21d6", "1d7", "1d20+100", "d20", "1d20-x"):
            with self.assertRaises(DiceError, msg=bad):
                parse_expr(bad)
        self.assertEqual(parse_expr("2d10-3"), (2, 10, -3))

    def test_rolls_block_parsing(self):
        body = "Intent\n```rolls\npick-the-lock: 1d20+2   # Dexterity\nspot: 1d20\n```\ntail"
        self.assertEqual(
            parse_rolls_block(body),
            [("pick-the-lock", "1d20+2", "Dexterity"), ("spot", "1d20", "")],
        )
        self.assertEqual(parse_rolls_block("no block here"), [])
        with self.assertRaises(DiceError):
            parse_rolls_block("```rolls\na: 1d20\na: 1d6\n```")
        with self.assertRaises(DiceError):
            parse_rolls_block("```rolls\nBad_Id: 1d20\n```")


if __name__ == "__main__":
    unittest.main()
