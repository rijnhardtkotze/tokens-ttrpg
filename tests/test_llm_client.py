"""Tests for llm_client.py: _config, LLMError, and chat response parsing."""

from __future__ import annotations

import io
import json
import os
import sys
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import llm_client  # noqa: E402
from llm_client import LLMError, _config  # noqa: E402


def _set_env(**kwargs):
    """Context manager: set env vars for the test, clean up after."""
    return unittest.mock.patch.dict(os.environ, kwargs)


class TestLLMError(unittest.TestCase):

    def test_is_runtime_error(self):
        err = LLMError("something went wrong")
        self.assertIsInstance(err, RuntimeError)

    def test_message_preserved(self):
        err = LLMError("test message")
        self.assertIn("test message", str(err))


class TestConfig(unittest.TestCase):

    def test_anthropic_defaults(self):
        with _set_env(GM_PROVIDER="anthropic", GM_MODEL="claude-3", GM_API_KEY="sk-test"):
            os.environ.pop("GM_BASE_URL", None)
            provider, model, api_key, base = _config()
        self.assertEqual(provider, "anthropic")
        self.assertEqual(model, "claude-3")
        self.assertEqual(api_key, "sk-test")
        self.assertIn("anthropic.com", base)

    def test_openai_defaults(self):
        with _set_env(GM_PROVIDER="openai", GM_MODEL="gpt-4", GM_API_KEY="sk-openai"):
            os.environ.pop("GM_BASE_URL", None)
            provider, model, api_key, base = _config()
        self.assertEqual(provider, "openai")
        self.assertIn("openai.com", base)

    def test_provider_case_normalized_to_lower(self):
        with _set_env(GM_PROVIDER="Anthropic", GM_MODEL="claude-3", GM_API_KEY="key"):
            os.environ.pop("GM_BASE_URL", None)
            provider, _, _, _ = _config()
        self.assertEqual(provider, "anthropic")

    def test_missing_api_key_raises(self):
        env = {"GM_PROVIDER": "anthropic", "GM_MODEL": "claude-3"}
        with unittest.mock.patch.dict(os.environ, env):
            os.environ.pop("GM_API_KEY", None)
            with self.assertRaises(LLMError):
                _config()

    def test_missing_model_raises(self):
        env = {"GM_PROVIDER": "anthropic", "GM_API_KEY": "key"}
        with unittest.mock.patch.dict(os.environ, env):
            os.environ.pop("GM_MODEL", None)
            with self.assertRaises(LLMError):
                _config()

    def test_invalid_provider_raises(self):
        with _set_env(GM_PROVIDER="groq", GM_MODEL="llama", GM_API_KEY="key"):
            os.environ.pop("GM_BASE_URL", None)
            with self.assertRaises(LLMError) as ctx:
                _config()
        self.assertIn("groq", str(ctx.exception))

    def test_custom_base_url_used(self):
        with _set_env(GM_PROVIDER="openai", GM_MODEL="local", GM_API_KEY="key",
                      GM_BASE_URL="http://localhost:11434/v1"):
            _, _, _, base = _config()
        self.assertEqual(base, "http://localhost:11434/v1")

    def test_base_url_trailing_slash_stripped(self):
        with _set_env(GM_PROVIDER="anthropic", GM_MODEL="claude-3", GM_API_KEY="key",
                      GM_BASE_URL="https://api.anthropic.com/"):
            _, _, _, base = _config()
        self.assertFalse(base.endswith("/"))

    def test_default_provider_is_anthropic(self):
        env = {"GM_MODEL": "claude-3", "GM_API_KEY": "key"}
        with unittest.mock.patch.dict(os.environ, env):
            os.environ.pop("GM_PROVIDER", None)
            os.environ.pop("GM_BASE_URL", None)
            provider, _, _, _ = _config()
        self.assertEqual(provider, "anthropic")


class TestChatResponseParsing(unittest.TestCase):
    """Test the chat() function's response parsing with mocked HTTP."""

    def _make_anthropic_response(self, text: str) -> bytes:
        return json.dumps({
            "content": [{"type": "text", "text": text}]
        }).encode()

    def _make_openai_response(self, text: str) -> bytes:
        return json.dumps({
            "choices": [{"message": {"content": text}}]
        }).encode()

    def _mock_urlopen(self, response_bytes: bytes):
        """Return a context manager mock for urllib.request.urlopen."""
        mock_resp = unittest.mock.MagicMock()
        mock_resp.read.return_value = response_bytes
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = unittest.mock.MagicMock(return_value=False)
        return unittest.mock.patch("urllib.request.urlopen", return_value=mock_resp)

    def test_anthropic_response_parsed(self):
        with _set_env(GM_PROVIDER="anthropic", GM_MODEL="claude-3", GM_API_KEY="key"):
            os.environ.pop("GM_BASE_URL", None)
            with self._mock_urlopen(self._make_anthropic_response("Hello world")):
                result = llm_client.chat("system", [{"role": "user", "content": "hi"}])
        self.assertEqual(result, "Hello world")

    def test_openai_response_parsed(self):
        with _set_env(GM_PROVIDER="openai", GM_MODEL="gpt-4", GM_API_KEY="key"):
            os.environ.pop("GM_BASE_URL", None)
            with self._mock_urlopen(self._make_openai_response("Hello from openai")):
                result = llm_client.chat("system", [{"role": "user", "content": "hi"}])
        self.assertEqual(result, "Hello from openai")

    def test_anthropic_multiple_content_blocks(self):
        response = json.dumps({
            "content": [
                {"type": "text", "text": "Part one. "},
                {"type": "text", "text": "Part two."},
            ]
        }).encode()
        with _set_env(GM_PROVIDER="anthropic", GM_MODEL="claude-3", GM_API_KEY="key"):
            os.environ.pop("GM_BASE_URL", None)
            with self._mock_urlopen(response):
                result = llm_client.chat("system", [{"role": "user", "content": "hi"}])
        self.assertEqual(result, "Part one. Part two.")

    def test_retriable_status_retries(self):
        """A 429 should trigger a retry (up to 3 attempts), then raise."""
        import urllib.error
        http_err = urllib.error.HTTPError(url="http://x", code=429, msg="Too Many Requests",
                                          hdrs={}, fp=io.BytesIO(b"rate limited"))
        with _set_env(GM_PROVIDER="anthropic", GM_MODEL="claude-3", GM_API_KEY="key"):
            os.environ.pop("GM_BASE_URL", None)
            with unittest.mock.patch("urllib.request.urlopen", side_effect=http_err), \
                 unittest.mock.patch("time.sleep"):  # don't actually sleep in tests
                with self.assertRaises(LLMError):
                    llm_client.chat("system", [{"role": "user", "content": "hi"}])

    def test_non_retriable_status_raises_immediately(self):
        """A 401 should raise immediately without retry."""
        import urllib.error
        http_err = urllib.error.HTTPError(url="http://x", code=401, msg="Unauthorized",
                                          hdrs={}, fp=io.BytesIO(b"unauthorized"))
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise http_err

        with _set_env(GM_PROVIDER="anthropic", GM_MODEL="claude-3", GM_API_KEY="key"):
            os.environ.pop("GM_BASE_URL", None)
            with unittest.mock.patch("urllib.request.urlopen", side_effect=side_effect):
                with self.assertRaises(LLMError):
                    llm_client.chat("system", [{"role": "user", "content": "hi"}])
        self.assertEqual(call_count, 1)  # no retries for 401

    def test_retriable_codes_set(self):
        self.assertIn(429, llm_client.RETRIABLE)
        self.assertIn(500, llm_client.RETRIABLE)
        self.assertIn(503, llm_client.RETRIABLE)
        self.assertNotIn(401, llm_client.RETRIABLE)
        self.assertNotIn(404, llm_client.RETRIABLE)

    def test_anthropic_system_message_in_payload(self):
        """Verify Anthropic sends system as top-level field (not in messages)."""
        captured_payload = {}

        def mock_urlopen(req, timeout=None):
            captured_payload.update(json.loads(req.data))
            mock_resp = unittest.mock.MagicMock()
            mock_resp.read.return_value = json.dumps(
                {"content": [{"type": "text", "text": "ok"}]}
            ).encode()
            mock_resp.__enter__ = lambda s: mock_resp
            mock_resp.__exit__ = unittest.mock.MagicMock(return_value=False)
            return mock_resp

        with _set_env(GM_PROVIDER="anthropic", GM_MODEL="claude-3", GM_API_KEY="key"):
            os.environ.pop("GM_BASE_URL", None)
            with unittest.mock.patch("urllib.request.urlopen", side_effect=mock_urlopen):
                llm_client.chat("be helpful", [{"role": "user", "content": "hi"}])

        self.assertEqual(captured_payload.get("system"), "be helpful")
        # System should NOT appear inside messages for Anthropic
        for msg in captured_payload.get("messages", []):
            self.assertNotEqual(msg.get("role"), "system")

    def test_openai_system_in_messages(self):
        """Verify OpenAI prepends system as a message with role=system."""
        captured_payload = {}

        def mock_urlopen(req, timeout=None):
            captured_payload.update(json.loads(req.data))
            mock_resp = unittest.mock.MagicMock()
            mock_resp.read.return_value = json.dumps(
                {"choices": [{"message": {"content": "ok"}}]}
            ).encode()
            mock_resp.__enter__ = lambda s: mock_resp
            mock_resp.__exit__ = unittest.mock.MagicMock(return_value=False)
            return mock_resp

        with _set_env(GM_PROVIDER="openai", GM_MODEL="gpt-4", GM_API_KEY="key"):
            os.environ.pop("GM_BASE_URL", None)
            with unittest.mock.patch("urllib.request.urlopen", side_effect=mock_urlopen):
                llm_client.chat("be helpful", [{"role": "user", "content": "hi"}])

        messages = captured_payload.get("messages", [])
        self.assertTrue(any(m.get("role") == "system" for m in messages))
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[0]["content"], "be helpful")


if __name__ == "__main__":
    unittest.main()