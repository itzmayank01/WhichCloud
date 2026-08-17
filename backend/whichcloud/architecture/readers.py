"""Which model reads a description, and what happens when one runs out.

A free tier is twenty requests a day. That is enough to build with and not
enough to demonstrate anything, and when it runs out the failure arrives in
the middle of somebody typing rather than at a convenient moment. So there is
a chain rather than a provider: several keys for the same service, then other
services entirely, tried in order until one answers.

Only quota and rate-limit failures move to the next candidate. A malformed
description or a bug in this code fails the same way on every provider, and
retrying it four times turns one clear error into four slow ones.

Adding a key is an environment variable and nothing else:

    GEMINI_API_KEY          the first one tried
    GEMINI_API_KEY_2 .. _9  more of the same, used in order
    GROQ_API_KEY            and GROQ_API_KEY_2 .. _9
    ANTHROPIC_API_KEY       billed, so last
    OPENAI_API_KEY

Comma-separated values work too, so GEMINI_API_KEY="a,b,c" is three keys.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

#: Free tiers first, billed last, so an exhausted free key costs the next
#: request a retry rather than costing money.
CHAIN: tuple[tuple[str, str], ...] = (
    ("gemini", "GEMINI_API_KEY"),
    ("groq", "GROQ_API_KEY"),
    ("anthropic", "ANTHROPIC_API_KEY"),
    ("openai", "OPENAI_API_KEY"),
)

#: What a provider says when it is out. Checked as substrings of the error
#: text because each SDK raises its own exception type and none of them share
#: a base class worth catching.
EXHAUSTED = (
    "resource_exhausted",
    "rate limit",
    "rate_limit",
    "quota",
    "429",
    "too many requests",
    "insufficient_quota",
    "overloaded",
    # An empty balance is the same situation as an empty quota: this provider
    # cannot answer now, another one might. Anthropic reports it as a 400,
    # which without this reads as a bad request and stops the chain.
    "credit balance",
    "billing",
    "payment",
    # A key that cannot call the model is a fact about that key, not about the
    # description. Keys issued at different times have different model access,
    # so one refusing must hand on to the next rather than stopping the chain.
    "not found",
    "not available",
    "does not exist",
    "404",
    "unsupported",
    # Transient capacity. Every one of these was discovered by being stopped
    # by it, which is why the chain no longer depends on this list being
    # complete -- it now decides the wording, not whether to continue.
    "unavailable",
    "503",
    "high demand",
    "try again later",
    "temporarily",
    "permission_denied",
    "permission denied",
    "denied access",
    "403",
    "forbidden",
    "unauthorized",
    "invalid_api_key",
    "401",
)


@dataclass(frozen=True)
class Candidate:
    provider: str
    key: str
    #: Which key this was, for reporting. Never the key itself.
    label: str


def _keys_for(variable: str) -> list[str]:
    """Every key configured under this name, in the order they are tried."""
    found: list[str] = []
    for name in (variable, *(f"{variable}_{n}" for n in range(2, 10))):
        raw = os.getenv(name, "")
        for part in raw.split(","):
            key = part.strip()
            if key and key not in found:
                found.append(key)
    return found


def candidates(preferred: str | None = None) -> list[Candidate]:
    """The chain to try, in order.

    A named provider goes first with the rest kept as fallbacks, rather than
    used alone -- asking for Gemini and getting nothing because its quota is
    gone is worse than getting an answer from Groq and being told so.
    """
    order = list(CHAIN)
    if preferred:
        order.sort(key=lambda entry: entry[0] != preferred)

    out: list[Candidate] = []
    for provider, variable in order:
        for index, key in enumerate(_keys_for(variable), start=1):
            out.append(
                Candidate(
                    provider=provider,
                    key=key,
                    label=f"{provider}#{index}" if index > 1 else provider,
                )
            )
    return out


def is_exhausted(error: Exception) -> bool:
    """Is this the provider saying "not now" rather than "never"?

    Only these are worth trying elsewhere. A description the model cannot
    parse fails identically on every provider in the chain, and walking all of
    them turns one clear error into four slow ones.
    """
    text = str(error).lower()
    return any(marker in text for marker in EXHAUSTED)


def configured() -> dict[str, int]:
    """How many keys each provider has, for /health to report.

    Counts only. A key must never reach a log, a response or a screen.
    """
    return {
        provider: len(_keys_for(variable))
        for provider, variable in CHAIN
        if _keys_for(variable)
    }
