#!/usr/bin/env python3
"""Safe, read-only Gemini key authentication test. Never print or store the key.

Run: GEMINI_API_KEY=<set-in-your-shell> python -m scripts.check_gemini_key
Or run interactively and enter the key at the hidden prompt.
This queries Google's official models.list endpoint; it does not generate content.
"""
from __future__ import annotations

import getpass
import json
import os
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=100"

def main() -> int:
    key = os.getenv("GEMINI_API_KEY") or getpass.getpass("Gemini API key (hidden): ").strip()
    if not key:
        print("No key supplied.")
        return 2
    request = Request(
        ENDPOINT,
        headers={"x-goog-api-key": key, "User-Agent": "RfactoryKeyCheck/1.0"},
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read(1024 * 1024).decode("utf-8"))
    except HTTPError as exc:
        description = {400: "Invalid key/request", 401: "Authentication rejected",
                       403: "Permission/restriction denied", 429: "Rate limit exceeded"}
        print(f"Gemini key NOT verified: HTTP {exc.code}: {description.get(exc.code, 'API error')}")
        return 1
    except (URLError, TimeoutError):
        print("Google API unreachable from this network; cannot determine key validity.")
        return 3

    models = {item.get("name", "").removeprefix("models/") for item in payload.get("models", [])}
    print(f"Authentication succeeded. {len(models)} models visible.")
    for model in ("gemini-3.5-flash-lite", "gemini-3.8-flash-lite-tts",
                  "gemini-3.1-flash-lite-image", "gemini-nano-banana-2.1"):
        print(f"- {model}: {'listed' if model in models else 'not listed'}")
    print("Note: visibility does NOT guarantee free image generation or available quota.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
