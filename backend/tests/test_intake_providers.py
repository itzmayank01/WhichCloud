"""The reader set the API advertises and the one it can actually run.

The landing page shows a chip per reader. These tests exist so that list
cannot drift from what the backend supports -- a chip for a provider with no
extractor behind it is an integration claimed and not built.
"""

import os
from unittest.mock import patch

from whichcloud.intake import _EXTRACTORS, available_providers, parse_description


def test_every_advertised_reader_has_an_extractor():
    assert set(_EXTRACTORS) == {"gemini", "anthropic", "openai"}


def test_each_extractor_is_callable():
    for name, fn in _EXTRACTORS.items():
        assert callable(fn), name


class TestAvailability:
    def test_none_without_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            assert available_providers() == []

    def test_openai_is_found_by_its_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "x"}, clear=True):
            assert available_providers() == ["openai"]

    def test_gemini_leads_when_several_are_set(self):
        # The free tier should be picked before anything billable.
        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "x", "ANTHROPIC_API_KEY": "y", "OPENAI_API_KEY": "z"},
            clear=True,
        ):
            assert available_providers()[0] == "gemini"

    def test_all_three_are_reported(self):
        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "x", "ANTHROPIC_API_KEY": "y", "OPENAI_API_KEY": "z"},
            clear=True,
        ):
            assert set(available_providers()) == {"gemini", "anthropic", "openai"}


def test_unknown_reader_is_refused_by_name():
    try:
        parse_description("an online shop", provider="chatgpt")  # type: ignore[arg-type]
    except Exception as exc:
        assert "chatgpt" in str(exc)
        assert "openai" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("an unknown provider should not be accepted")
