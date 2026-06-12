#!/usr/bin/env python3
"""Provider-agnostic LLM chat client. No SDKs, stdlib only.

Env:
    GM_PROVIDER   anthropic | openai          (openai covers OpenRouter, vLLM,
                                               Ollama, llama.cpp, any compatible API)
    GM_MODEL      model id
    GM_API_KEY    bearer / x-api-key value
    GM_BASE_URL   optional override (defaults per provider)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

DEFAULT_BASE = {
    "anthropic": "https://api.anthropic.com",
    "openai": "https://api.openai.com/v1",
}
RETRIABLE = {429, 500, 502, 503, 504, 529}


class LLMError(RuntimeError):
    pass


def extract_json(raw: str) -> dict:
    """Pull the single JSON object out of a model reply (tolerates one fenced block).

    Schema validation is the caller's job — each driver has its own contract.
    """
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found in model output")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("model output is not a JSON object")
    return data


def log_raw(label: str, text: str) -> None:
    """Print untrusted model output to a CI log without letting it issue
    workflow commands (::error::, ::add-mask::, ...)."""
    # Pick a token that does not appear in the text, otherwise the model could
    # emit our own ::{token}:: end-marker and re-enable workflow commands early.
    token = uuid.uuid4().hex
    while token in text:
        token = uuid.uuid4().hex
    print(f"::stop-commands::{token}")
    print(f"{label}\n{text}")
    print(f"::{token}::")


def _config() -> tuple[str, str, str, str]:
    provider = os.environ.get("GM_PROVIDER", "anthropic").lower()
    if provider not in DEFAULT_BASE:
        raise LLMError(f"GM_PROVIDER must be one of {sorted(DEFAULT_BASE)}, got '{provider}'")
    model = os.environ.get("GM_MODEL")
    api_key = os.environ.get("GM_API_KEY")
    if not model or not api_key:
        raise LLMError("GM_MODEL and GM_API_KEY must be set")
    base = (os.environ.get("GM_BASE_URL") or DEFAULT_BASE[provider]).rstrip("/")
    if urllib.parse.urlparse(base).scheme not in {"http", "https"}:
        raise LLMError(f"GM_BASE_URL must start with http:// or https://, got '{base}'")
    return provider, model, api_key, base


def chat(system: str, messages: list[dict], max_tokens: int = 8000, timeout: int = 300) -> str:
    """messages: [{"role": "user"|"assistant", "content": str}, ...] -> assistant text."""
    provider, model, api_key, base = _config()

    if provider == "anthropic":
        url = f"{base}/v1/messages"
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        payload = {"model": model, "max_tokens": max_tokens, "system": system, "messages": messages}
    else:
        url = f"{base}/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}"}
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, *messages],
        }
    headers["content-type"] = "application/json"

    last_err: Exception | None = None
    for attempt in range(3):
        if attempt:
            time.sleep(2 ** (attempt + 1))
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
            if provider == "anthropic":
                return "".join(b.get("text", "") for b in data.get("content", []))
            return data["choices"][0]["message"]["content"] or ""
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:500]
            last_err = LLMError(f"HTTP {exc.code} from {url}: {detail}")
            if exc.code not in RETRIABLE:
                raise last_err from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            last_err = LLMError(f"request to {url} failed: {exc}")
    raise last_err  # type: ignore[misc]


def main() -> int:
    ap = argparse.ArgumentParser(description="Sanity-check the GM LLM configuration.")
    ap.add_argument("--ping", action="store_true", help="send a tiny request and report success")
    args = ap.parse_args()
    if args.ping:
        try:
            chat("Reply with the single word: ready", [{"role": "user", "content": "Status?"}], max_tokens=16)
        except LLMError as exc:
            print(f"GM LLM configuration check FAILED: {exc}", file=sys.stderr)
            return 1
        provider, model, _, base = _config()
        print(f"GM LLM ready: provider={provider} model={model} base={base}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
