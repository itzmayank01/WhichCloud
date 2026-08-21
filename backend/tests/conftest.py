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


@pytest.fixture
def llm(monkeypatch):
    """Opt back in, for a test that is actually about extraction."""
    monkeypatch.delenv("WHICHCLOUD_DISABLE_LLM", raising=False)
    if not os.getenv("WHICHCLOUD_EXTRACT_PROVIDER"):
        monkeypatch.setenv("WHICHCLOUD_EXTRACT_PROVIDER", "groq")
