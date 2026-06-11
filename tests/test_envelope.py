import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from gm_turn import check_paths, parse_envelope  # noqa: E402
from llm_client import extract_json  # noqa: E402


class TestExtractJson(unittest.TestCase):
    """extract_json is schema-agnostic: every driver's contract must parse with it."""

    def test_raw_and_fenced(self):
        obj = {"title": "Ch 1", "recap": "It began."}
        self.assertEqual(extract_json(json.dumps(obj)), obj)
        self.assertEqual(extract_json(f"```json\n{json.dumps(obj)}\n```"), obj)
        self.assertEqual(extract_json(f"noise before\n{json.dumps(obj)}\nafter"), obj)

    def test_paradox_and_recap_shapes_parse(self):
        # Regression: these contracts have no narration/pr_title and must not be
        # forced through the gm-turn envelope validation.
        paradox = {"resolutions": [{"path": "world/npcs/x.md", "content": "..."}],
                   "paradox_log": "log", "comment": "c"}
        self.assertEqual(extract_json(json.dumps(paradox)), paradox)

    def test_rejects_non_objects(self):
        for bad in ("no json here", "[1, 2]", '"just a string"'):
            with self.assertRaises(ValueError, msg=bad):
                extract_json(bad)


class TestGmTurnEnvelope(unittest.TestCase):
    def test_requires_narration_and_pr_title(self):
        with self.assertRaises(ValueError):
            parse_envelope(json.dumps({"narration": "x"}))
        env = parse_envelope(json.dumps({"narration": "x", "pr_title": "GM Turn 1"}))
        self.assertEqual(env["pr_title"], "GM Turn 1")

    def test_path_allowlist(self):
        def env_for(path):
            return {"narration": "x", "pr_title": "t",
                    "files": [{"path": path, "op": "create", "content": "c"}]}

        for ok in ("world/npcs/x.md", "plot/state.md", "sessions/2026-01-01-01.md",
                   "character/journal.md", "character/sheet.md"):
            check_paths(env_for(ok))
        for forbidden in ("meta/canon.md", "meta/rolls.md", ".github/workflows/x.yml",
                          "scripts/dice.py", "secrets.txt"):
            with self.assertRaises(ValueError, msg=forbidden):
                check_paths(env_for(forbidden))


if __name__ == "__main__":
    unittest.main()
