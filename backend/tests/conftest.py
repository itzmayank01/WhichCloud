"""Test-suite defaults.

The unit suite must not call a language model. Two reasons, and the
second is the one that matters:

  1. Speed. A model call per `build()` turns a two-minute suite into a
     twenty-minute one.
  2. Honesty about what is being tested. A test that asserts on
     components while silently depending on an extraction is really
     testing two things and reporting one, and it fails for whichever
     reason is least visible. The decision layer is deterministic and is
     tested as such; extraction is measured separately, on purpose, in
     tests/probes/.

So the LLM is off by default here and the phrase-table fallback answers
instead. Tests that specifically exercise extraction opt back in with
the `llm` fixture.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _no_model_calls(monkeypatch):
    monkeypatch.setenv("WHICHCLOUD_DISABLE_LLM", "1")


#: Failures that are facts about the day rather than about this code.
#: A free-tier budget resetting is not a regression, and a suite that
#: goes red on it teaches people to ignore the suite.
_CAPACITY_SIGNS = (
    "429", "quota", "rate limit", "rate_limit", "resource_exhausted",
    "too many requests", "insufficient_quota", "credit balance", "billing",
    "payment", "overloaded", "out of capacity", "high demand", "503",
    "timeout", "timed out", "connection", "unavailable",
)


def _is_capacity_failure(exc: Exception) -> bool:
    return any(sign in str(exc).lower() for sign in _CAPACITY_SIGNS)


@pytest.fixture
def llm(monkeypatch):
    """Opt back in, for a test that is actually about extraction.

    SKIPS on capacity (quota, rate limit, no credit, timeout) and FAILS
    on anything else. The distinction matters: a blanket skip would hide
    a schema-validation failure, a malformed response, or a parser that
    can no longer map the model's answer to Constraints -- exactly the
    regressions these tests exist to catch -- behind a message that reads
    like "we ran out of tokens again".
    """
    monkeypatch.delenv("WHICHCLOUD_DISABLE_LLM", raising=False)
    monkeypatch.delenv("WHICHCLOUD_OFFLINE", raising=False)

    from whichcloud import llm_extract

    try:
        llm_extract._call_with_failover("A booking system for 200 staff.")
    except Exception as exc:  # noqa: BLE001
        if _is_capacity_failure(exc):
            pytest.skip(f"no capacity: {str(exc)[:110]}")
        raise AssertionError(
            f"extractor is reachable but failed on a probe call, which is a "
            f"regression rather than a capacity problem: {type(exc).__name__}: {exc}"
        ) from exc
