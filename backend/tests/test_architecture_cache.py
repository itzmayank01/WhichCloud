"""The same description must answer the same way, run to run."""

import hashlib

from whichcloud.architecture import extract
from whichcloud.architecture.extract import cache_key


def test_the_same_description_and_reader_key_alike():
    assert cache_key("a web app", "gemini") == cache_key("a web app", "gemini")


def test_surrounding_whitespace_is_not_a_different_question():
    assert cache_key("  a web app\n", "gemini") == cache_key("a web app", "gemini")


def test_a_different_description_keys_differently():
    assert cache_key("a web app", "gemini") != cache_key("a mobile app", "gemini")


def test_a_different_reader_keys_differently():
    """Two models read the same text differently, so an answer cached from one
    must not be served as though it came from the other."""
    assert cache_key("a web app", "gemini") != cache_key("a web app", "anthropic")


def _key_under(model: str, version: str) -> str:
    parts = "|".join(["a web app", "gemini", model, version])
    return hashlib.sha256(parts.encode()).hexdigest()


def test_the_schema_version_takes_part_in_the_key():
    """An extraction made under an older schema has a different shape.
    Serving it as current is how a cache silently corrupts what reads it."""
    current = cache_key("a web app", "gemini")

    assert current == _key_under(extract._MODEL, extract.SCHEMA_VERSION)
    assert current != _key_under(extract._MODEL, extract.SCHEMA_VERSION + "-next")


def test_the_model_takes_part_in_the_key():
    """Changing model changes the answer, so it has to change the key."""
    assert cache_key("a web app", "gemini") != _key_under(
        "some-other-model", extract.SCHEMA_VERSION
    )
