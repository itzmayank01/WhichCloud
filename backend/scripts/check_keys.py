#!/usr/bin/env python3
"""Which configured model keys actually work.

Ten keys in an environment is ten things that can be wrong quietly. A key can
be malformed, revoked, out of quota, or issued against a project with no
access to the model -- and every one of those surfaces as the same thing when
a description fails to read. This asks each key directly and says which.

Never prints a key. Length and prefix only, which is enough to spot a
truncated paste or a value that is not a key at all.

    python3 scripts/check_keys.py
"""

import json
import sys
import urllib.error
import urllib.request

from whichcloud.architecture.readers import candidates

TIMEOUT = 30


def probe(provider: str, key: str) -> tuple[bool, str]:
    """One cheap call. Listing models is free and needs the same credential.

    Groq and OpenAI go through their SDK rather than a hand-rolled request.
    Groq sits behind Cloudflare, which answers a bare urllib call with 403
    error 1010 -- a bot check, not an authentication failure. Probing that way
    reported four perfectly good keys as dead.
    """
    if provider in ("groq", "openai"):
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=key,
                base_url="https://api.groq.com/openai/v1" if provider == "groq" else None,
            )
            models = client.models.list()
            return True, f"ok, {len(models.data)} models"
        except Exception as exc:
            return False, str(exc)[:120].replace("\n", " ")

    urls = {
        "gemini": "https://generativelanguage.googleapis.com/v1beta/models",
        "groq": "https://api.groq.com/openai/v1/models",
        "openai": "https://api.openai.com/v1/models",
        "anthropic": "https://api.anthropic.com/v1/models",
    }
    headers = {
        "gemini": {"x-goog-api-key": key},
        "groq": {"Authorization": f"Bearer {key}"},
        "openai": {"Authorization": f"Bearer {key}"},
        "anthropic": {"x-api-key": key, "anthropic-version": "2023-06-01"},
    }
    url = urls.get(provider)
    if not url:
        return False, "unknown provider"

    try:
        request = urllib.request.Request(url, headers=headers[provider])
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body = json.load(response)
        count = len(body.get("models", body.get("data", [])))
        return True, f"ok, {count} models"
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()[:120].replace("\n", " ")
        return False, f"HTTP {exc.code} {detail}"
    except Exception as exc:  # network, DNS, timeout
        return False, str(exc)[:120]


def main() -> int:
    chain = candidates()
    if not chain:
        print("  no keys configured")
        return 1

    working = 0
    for candidate in chain:
        ok, detail = probe(candidate.provider, candidate.key)
        mark = "ok  " if ok else "FAIL"
        working += ok
        print(
            f"  {mark} {candidate.label:12} "
            f"len={len(candidate.key):<4} {candidate.key[:4]}…  {detail}"
        )

    print(f"\n  {working} of {len(chain)} keys usable")
    return 0 if working else 1


if __name__ == "__main__":
    sys.exit(main())
