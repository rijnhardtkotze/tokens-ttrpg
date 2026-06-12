import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from chapter_recap import parse_recap_envelope  # noqa: E402
from gm_paradox import parse_paradox_envelope  # noqa: E402
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


class TestParadoxEnvelope(unittest.TestCase):
    """parse_paradox_envelope enforces the gm_paradox_system.md contract."""

    def _valid(self) -> dict:
        return {"resolutions": [{"path": "world/npcs/x.md", "content": "settled"}],
                "paradox_log": "what collided and how reality settled",
                "comment": "the dust clears"}

    def test_accepts_the_prompt_contract(self):
        env = parse_paradox_envelope(json.dumps(self._valid()))
        self.assertEqual(env["resolutions"][0]["path"], "world/npcs/x.md")

    def test_log_and_comment_are_optional(self):
        env = parse_paradox_envelope(json.dumps({"resolutions": self._valid()["resolutions"]}))
        self.assertNotIn("comment", env)

    def test_rejects_gm_turn_shape(self):
        # The original bug, inverted: a gm-turn envelope is not a paradox reply.
        with self.assertRaises(ValueError):
            parse_paradox_envelope(json.dumps({"narration": "x", "pr_title": "t"}))

    def test_rejects_malformed_resolutions(self):
        for payload in ({},
                        {"resolutions": "not a list"},
                        {"resolutions": []},
                        {"resolutions": ["not a dict"]},
                        {"resolutions": [{"content": "no path"}]},
                        {"resolutions": [{"path": "no-content.md"}]},
                        {"resolutions": [{"path": "", "content": "empty path"}]},
                        {"resolutions": [{"path": 3, "content": "bad path"}]},
                        {"resolutions": [{"path": "x.md", "content": 3}]}):
            with self.assertRaises(ValueError, msg=repr(payload)):
                parse_paradox_envelope(json.dumps(payload))

    def test_rejects_duplicate_paths(self):
        payload = {"resolutions": [{"path": "world/npcs/x.md", "content": "a"},
                                   {"path": "world/npcs/x.md", "content": "b"}]}
        with self.assertRaises(ValueError):
            parse_paradox_envelope(json.dumps(payload))

    def test_rejects_forbidden_paths(self):
        for forbidden in ("meta/canon.md", "meta/rolls.md",
                          ".github/workflows/gm-turn.yml", "scripts/gm_turn.py",
                          "tests/test_envelope.py"):
            payload = {"resolutions": [{"path": forbidden, "content": "hijack"}]}
            with self.assertRaises(ValueError, msg=forbidden):
                parse_paradox_envelope(json.dumps(payload))

    def test_rejects_non_string_log_and_comment(self):
        for key in ("paradox_log", "comment"):
            payload = self._valid()
            payload[key] = ["not", "a", "string"]
            with self.assertRaises(ValueError, msg=key):
                parse_paradox_envelope(json.dumps(payload))


class TestRecapEnvelope(unittest.TestCase):
    """parse_recap_envelope enforces the chapter_recap_system.md contract."""

    def test_accepts_the_prompt_contract(self):
        env = parse_recap_envelope(json.dumps({"title": "The Salt Bell", "recap": "It began."}))
        self.assertEqual(env["title"], "The Salt Bell")
        self.assertEqual(env["recap"], "It began.")

    def test_title_is_optional(self):
        env = parse_recap_envelope(json.dumps({"recap": "It began."}))
        self.assertEqual(env["recap"], "It began.")

    def test_rejects_gm_turn_shape(self):
        # The original bug, inverted: a gm-turn envelope is not a recap reply.
        with self.assertRaises(ValueError):
            parse_recap_envelope(json.dumps({"narration": "x", "pr_title": "t"}))

    def test_rejects_missing_blank_or_non_string_recap(self):
        for payload in ({}, {"title": "t"}, {"recap": ""}, {"recap": "  \n "}, {"recap": ["x"]}):
            with self.assertRaises(ValueError, msg=repr(payload)):
                parse_recap_envelope(json.dumps(payload))

    def test_rejects_non_string_title(self):
        with self.assertRaises(ValueError):
            parse_recap_envelope(json.dumps({"title": 7, "recap": "fine"}))


if __name__ == "__main__":
    unittest.main()
