"""Walking the provider chain when one runs out."""

import pytest

from whichcloud.architecture import readers


def test_extra_keys_are_picked_up_in_order(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "first")
    monkeypatch.setenv("GEMINI_API_KEY_2", "second")
    monkeypatch.setenv("GEMINI_API_KEY_3", "third")

    labels = [c.label for c in readers.candidates() if c.provider == "gemini"]
    assert labels == ["gemini", "gemini#2", "gemini#3"]


def test_one_variable_can_hold_several_keys(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "a, b ,c")
    keys = [c.key for c in readers.candidates() if c.provider == "gemini"]
    assert keys == ["a", "b", "c"]


def test_a_repeated_key_is_not_tried_twice(monkeypatch):
    """Two names holding the same key is one candidate, not two attempts at
    the same exhausted quota."""
    monkeypatch.setenv("GEMINI_API_KEY", "same")
    monkeypatch.setenv("GEMINI_API_KEY_2", "same")
    assert len([c for c in readers.candidates() if c.provider == "gemini"]) == 1


def test_free_providers_come_before_billed_ones(monkeypatch):
    for name in ("GEMINI_API_KEY", "GROQ_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.setenv(name, "k")
    order = [c.provider for c in readers.candidates()]
    assert order.index("gemini") < order.index("anthropic")
    assert order.index("groq") < order.index("anthropic")


def test_a_named_provider_leads_but_the_rest_remain(monkeypatch):
    """Asking for Groq and getting nothing because its quota is gone is worse
    than getting an answer from Gemini and being told which answered."""
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("GROQ_API_KEY", "k2")

    chain = [c.provider for c in readers.candidates("groq")]
    assert chain[0] == "groq"
    assert "gemini" in chain


@pytest.mark.parametrize(
    "message",
    [
        "429 RESOURCE_EXHAUSTED",
        "Rate limit reached for model",
        "You exceeded your current quota",
        "Your credit balance is too low",
        "Error code: 429 - too many requests",
        "insufficient_quota",
    ],
)
def test_provider_out_of_capacity_moves_to_the_next(message):
    assert readers.is_exhausted(Exception(message))


@pytest.mark.parametrize(
    "message",
    [
        "invalid API key",
        "context length exceeded",
        "could not parse the response",
        "connection refused",
    ],
)
def test_other_failures_do_not_walk_the_chain(message):
    """These fail identically on every provider. Retrying all four turns one
    clear error into four slow ones."""
    assert not readers.is_exhausted(Exception(message))


def test_configured_reports_counts_never_keys(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "secret-value")
    counts = readers.configured()
    assert counts["gemini"] == 1
    assert "secret-value" not in str(counts)
