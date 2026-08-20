"""The reader set the API advertises and the one it can actually run.

The landing page shows a chip per reader. These tests exist so that list
cannot drift from what the backend supports -- a chip for a provider with no
extractor behind it is an integration claimed and not built.
"""

import os
from unittest.mock import patch

from whichcloud.intake import _EXTRACTORS, available_providers, parse_description


def test_every_advertised_reader_has_an_extractor():
    """The Provider type is what the API accepts; the registry is what can
    actually run. A name in one and not the other is a 500 waiting for whoever
    passes it -- which is exactly what adding Groq to the registry and not to
    the API's literal produced."""
    from typing import get_args

    from whichcloud.intake import Provider

    assert set(_EXTRACTORS) == set(get_args(Provider))


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

    def test_a_reader_that_answers_leads_when_several_are_set(self):
        # Claude Opus reads best but its keys have no credit balance, so
        # it sits behind the readers that actually answer.
        # WHICHCLOUD_READER_ORDER promotes it once the account is funded.
        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "x", "ANTHROPIC_API_KEY": "y", "OPENAI_API_KEY": "z"},
            clear=True,
        ):
            assert available_providers()[0] == "gemini"

    def test_every_configured_provider_is_reported(self):
        with patch.dict(
            os.environ,
            {
                "GEMINI_API_KEY": "x",
                "GROQ_API_KEY": "g",
                "ANTHROPIC_API_KEY": "y",
                "OPENAI_API_KEY": "z",
            },
            clear=True,
        ):
            assert set(available_providers()) == {
                "gemini",
                "groq",
                "anthropic",
                "openai",
            }


def test_unknown_reader_is_refused_by_name():
    try:
        parse_description("an online shop", provider="chatgpt")  # type: ignore[arg-type]
    except Exception as exc:
        assert "chatgpt" in str(exc)
        assert "openai" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("an unknown provider should not be accepted")
