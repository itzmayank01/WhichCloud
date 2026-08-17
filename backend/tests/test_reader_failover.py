"""Walking the provider chain when one runs out."""

import pytest

from whichcloud.architecture import readers


@pytest.fixture(autouse=True)
def _no_ambient_keys(monkeypatch):
    """Start every test from an empty environment.

    Without this the developer's own keys leak in: a machine with four Gemini
    keys configured makes a test that sets two see six, and the failure looks
    like a bug in the code rather than in the test.
    """
    for _, variable in readers.CHAIN:
        for name in (variable, *(f"{variable}_{n}" for n in range(2, 10))):
            monkeypatch.delenv(name, raising=False)


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


@pytest.mark.parametrize(
    "message",
    [
        "404 NOT_FOUND models/gemini-2.5-flash is no longer available to new users",
        "The model does not exist",
        "model not available for this key",
        "unsupported model",
    ],
)
def test_a_key_without_access_to_the_model_hands_on(message):
    """Keys issued at different times have different model access. A key that
    cannot call the model is a fact about that key, not about the description,
    so it must not stop the chain -- this exact 404 blocked all ten keys."""
    assert readers.is_exhausted(Exception(message))


def test_every_key_is_tried_whatever_the_failure(monkeypatch):
    """The chain must not depend on recognising an error.

    Three separate failures each stopped all ten keys before this: a quota
    429, a 404 for a model the key could not call, and a 503 for a busy
    model. Each was fixed by adding a phrase and waiting to be surprised
    again, so the rule is now that anything moves on.
    """
    from whichcloud.architecture import extract as ex

    monkeypatch.setenv("GEMINI_API_KEY", "a,b,c")
    monkeypatch.setenv("GROQ_API_KEY", "d")

    from whichcloud.architecture.schema import Architecture, Service

    answer = Architecture(
        services=[Service(name="S3", tier="data", flow="sync")]
    )
    tried: list[str] = []

    def failing(description, client=None, key=None):
        tried.append(key)
        raise RuntimeError("something nobody predicted")

    def working(description, client=None, key=None):
        tried.append(key)
        return answer

    monkeypatch.setitem(ex._EXTRACTORS, "gemini", failing)
    monkeypatch.setitem(ex._EXTRACTORS, "groq", working)

    assert ex._read_with_failover("a shop", None) is answer
    assert tried == ["a", "b", "c", "d"]


def test_when_all_are_out_of_capacity_it_says_so(monkeypatch):
    from whichcloud.architecture import extract as ex
    from whichcloud.intake import IntakeError

    monkeypatch.setenv("GEMINI_API_KEY", "a,b")

    def exhausted(description, client=None, key=None):
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    monkeypatch.setitem(ex._EXTRACTORS, "gemini", exhausted)

    with pytest.raises(IntakeError, match="out of capacity"):
        ex._read_with_failover("a shop", None)


def test_a_real_error_is_surfaced_over_a_quota_one(monkeypatch):
    """When some keys are merely spent and one hit a genuine fault, the fault
    is the useful thing to report."""
    from whichcloud.architecture import extract as ex
    from whichcloud.intake import IntakeError

    monkeypatch.setenv("GEMINI_API_KEY", "spent,broken")
    calls = {"n": 0}

    def mixed(description, client=None, key=None):
        calls["n"] += 1
        raise RuntimeError(
            "429 quota" if calls["n"] == 1 else "schema validation blew up"
        )

    monkeypatch.setitem(ex._EXTRACTORS, "gemini", mixed)

    with pytest.raises(IntakeError, match="schema validation blew up"):
        ex._read_with_failover("a shop", None)


def test_an_empty_architecture_is_treated_as_a_failure(monkeypatch):
    """Some models answer a long description with an empty object rather than
    an error. It validates, so it was returned and then cached -- and since
    the first answer for a key is kept, a blank diagram became the permanent
    answer for a twenty six service description."""
    from whichcloud.architecture import extract as ex
    from whichcloud.architecture.schema import Architecture, Service

    monkeypatch.setenv("GEMINI_API_KEY", "empty")
    monkeypatch.setenv("GROQ_API_KEY", "good")

    real = Architecture(services=[Service(name="S3", tier="data", flow="sync")])

    monkeypatch.setitem(
        ex._EXTRACTORS, "gemini", lambda d, c=None, key=None: Architecture()
    )
    monkeypatch.setitem(ex._EXTRACTORS, "groq", lambda d, c=None, key=None: real)

    assert ex._read_with_failover("a shop", None) is real
