"""Tests for the plain-English intake adapter.

None of these call the Anthropic API. The model's *judgement* is measured by
scripts/eval_intake.py; what is tested here is everything around it — the
mapping, the validation boundary, and the failure paths — because those are
what turn a plausible-looking extraction into a wrong architecture if they
break.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from tests.fixtures.intake_examples import EXAMPLES, example
from whichcloud.intake import (
    GEMINI_MODEL,
    Intake,
    IntakeError,
    RequirementDraft,
    parse_description,
)
from whichcloud.pricing.models import REGIONS
from whichcloud.requirements import Requirement


def draft(**overrides) -> RequirementDraft:
    base = dict(
        goal="an online shop",
        workload_type="web",
        traffic_pattern="spiky",
        traffic_scale="medium",
        region="india",
        budget_monthly_usd=400.0,
        storage_gb=200.0,
        egress_gb=500.0,
        interruptible=False,
        high_availability=False,
        arm_compatible=True,
        needs_waf=False,
        needs_event_streaming=False,
        needs_analytics=False,
        needs_search=False,
        daily_transactions=0,
        latency_target_ms=0,
        provider_preference="none",
        compliance=[],
        assumed=[],
        clarifying_question="",
    )
    base.update(overrides)
    return RequirementDraft(**base)


@dataclass
class FakeResponse:
    parsed_output: object
    stop_reason: str = "end_turn"


class FakeClient:
    """Stands in for anthropic.Anthropic — records the call, returns a draft."""

    def __init__(self, response):
        self._response = response
        self.calls: list[dict] = []
        self.messages = self

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


# ── draft → requirement ─────────────────────────────────────────────────


def test_draft_converts_to_requirement():
    req = draft().to_requirement()
    assert isinstance(req, Requirement)
    assert req.workload_type == "web"
    assert req.budget_monthly_usd == 400.0


def test_provider_preference_none_becomes_null():
    """'none' is a string on the wire because enums can't hold null cleanly.

    If it survived as the literal string 'none', the engine would try to price
    a cloud called "none" instead of comparing all three.
    """
    assert draft(provider_preference="none").to_requirement().provider_preference is None
    assert draft(provider_preference="aws").to_requirement().provider_preference == "aws"


def test_compliance_list_becomes_tuple():
    req = draft(compliance=["HIPAA", "GDPR"]).to_requirement()
    assert req.compliance == ("HIPAA", "GDPR")


def test_sentinel_budget_means_not_mentioned():
    """-1 crosses the wire because nullable-union schema support varies by
    provider; a sentinel we control behaves identically everywhere."""
    assert draft(budget_monthly_usd=-1).to_requirement().budget_monthly_usd is None
    assert draft(budget_monthly_usd=400).to_requirement().budget_monthly_usd == 400


def test_empty_question_means_no_question():
    assert draft(clarifying_question="").question is None
    assert draft(clarifying_question="   ").question is None
    assert draft(clarifying_question="How spiky?").question == "How spiky?"


# ── validation boundary ─────────────────────────────────────────────────


def test_bad_region_is_rejected_downstream():
    """The schema can't enumerate regions, so a wrong one must fail later.

    Structured outputs guarantee `region` is a string, not that it is a region
    we price. This is exactly the class of error that would otherwise surface
    as a confusing pricing miss.
    """
    from whichcloud.pricing.models import provider_region

    req = draft(region="atlantis").to_requirement()
    with pytest.raises(ValueError, match="atlantis"):
        provider_region(req.region, "aws")


def test_negative_volume_fails_validation():
    with pytest.raises(ValueError, match="negative"):
        draft(egress_gb=-1).to_requirement()


def test_negative_budget_reads_as_absent_not_invalid():
    """Any negative is the sentinel — it must never reach Requirement as a
    negative number, which would fail validation for the wrong reason."""
    assert draft(budget_monthly_usd=-100).to_requirement().budget_monthly_usd is None


# ── parse_description ───────────────────────────────────────────────────


def test_empty_description_is_rejected_without_calling_the_api():
    client = FakeClient(FakeResponse(draft()))
    with pytest.raises(IntakeError, match="empty"):
        parse_description("   ", client=client)
    assert client.calls == [], "should not spend an API call on empty input"


def test_parse_returns_intake_with_metadata():
    client = FakeClient(
        FakeResponse(
            draft(assumed=["region", "storage_gb"], clarifying_question="How spiky?")
        )
    )
    intake = parse_description("a shop", client=client)

    assert isinstance(intake, Intake)
    assert intake.requirement.workload_type == "web"
    assert intake.assumed == ("region", "storage_gb")
    assert intake.clarifying_question == "How spiky?"
    assert intake.provider == "anthropic"


def test_confidence_reflects_how_much_was_guessed():
    few = parse_description("x", client=FakeClient(FakeResponse(draft(assumed=["region"]))))
    many = parse_description(
        "x",
        client=FakeClient(
            FakeResponse(draft(assumed=["region", "storage_gb", "egress_gb", "budget"]))
        ),
    )
    assert few.is_confident
    assert not many.is_confident


def test_refusal_is_surfaced_not_swallowed():
    client = FakeClient(FakeResponse(draft(), stop_reason="refusal"))
    with pytest.raises(IntakeError, match="declined"):
        parse_description("something", client=client)


def test_missing_structured_output_is_an_error():
    client = FakeClient(FakeResponse(None))
    with pytest.raises(IntakeError, match="no structured output"):
        parse_description("something", client=client)


def test_api_failure_becomes_intake_error():
    client = FakeClient(RuntimeError("connection reset"))
    with pytest.raises(IntakeError, match="Could not reach Claude"):
        parse_description("something", client=client)


def test_invalid_extraction_fails_loudly():
    """A hallucinated value must not become a silently wrong architecture."""
    client = FakeClient(FakeResponse(draft(egress_gb=-5)))
    with pytest.raises(IntakeError, match="failed validation"):
        parse_description("something", client=client)


def test_request_uses_the_documented_model_and_schema():
    client = FakeClient(FakeResponse(draft()))
    parse_description("a shop", client=client)

    call = client.calls[0]
    assert call["model"] == "claude-opus-5"
    assert call["output_format"] is RequirementDraft
    assert call["messages"][0]["content"] == "a shop"


# ── evaluation fixtures ─────────────────────────────────────────────────


def test_every_example_has_a_unique_id():
    ids = [e["id"] for e in EXAMPLES]
    assert len(ids) == len(set(ids))


def test_examples_only_expect_real_requirement_fields():
    """A typo'd fixture field would silently never be scored."""
    valid = set(Requirement.__slots__) | {"provider_preference"}
    for case in EXAMPLES:
        unknown = set(case["expected"]) - valid
        assert not unknown, f"{case['id']} expects unknown fields: {unknown}"


def test_examples_only_use_regions_we_price():
    for case in EXAMPLES:
        region = case["expected"].get("region")
        if region is not None:
            assert region in REGIONS, f"{case['id']} uses unpriced region {region!r}"


def test_examples_cover_the_workload_types_the_engine_branches_on():
    """Batch and web take different paths through sizing and technique matching."""
    covered = {c["expected"].get("workload_type") for c in EXAMPLES}
    assert {"web", "api", "batch", "ml", "storage"} <= covered


def test_examples_cover_both_interruptible_states():
    """Spot is gated on interruptible, so both sides need a fixture."""
    values = {
        c["expected"]["interruptible"]
        for c in EXAMPLES
        if "interruptible" in c["expected"]
    }
    assert values == {True, False}


def test_example_lookup_by_id():
    assert example("ecommerce-spiky")["expected"]["traffic_pattern"] == "spiky"
    with pytest.raises(KeyError):
        example("does-not-exist")


# ── provider selection ──────────────────────────────────────────────────


def test_a_reader_that_answers_is_preferred_to_a_better_one_that_cannot(monkeypatch):
    """Claude Opus reads these descriptions best and is deliberately not
    first: the configured Anthropic keys have no credit balance, so every
    call 400s. A first-choice reader that always fails costs a round-trip
    per request and extracts nothing. The order is one env var away once
    the account is funded -- see the override test below.
    """
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "y")
    monkeypatch.delenv("WHICHCLOUD_READER_ORDER", raising=False)
    from whichcloud.intake import available_providers

    assert available_providers()[0] == "gemini"


def test_the_order_can_be_changed_without_touching_the_code(monkeypatch):
    """Whoever pays the bill decides which reader leads."""
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "y")
    monkeypatch.setenv("WHICHCLOUD_READER_ORDER", "anthropic,gemini")
    from whichcloud.intake import available_providers

    assert available_providers() == ["anthropic", "gemini"]


def test_a_nonsense_order_falls_back_rather_than_reading_nothing(monkeypatch):
    """A typo in the env var must not leave the app with no reader at all."""
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "y")
    monkeypatch.setenv("WHICHCLOUD_READER_ORDER", "gemeni, gpt4")
    from whichcloud.intake import available_providers

    # Neither name is a provider, so the whole override is ignored and the
    # default order stands -- rather than an empty list and no reader.
    assert available_providers() == ["anthropic"]


def test_google_api_key_also_counts(monkeypatch):
    """Clearing the two providers that existed when this was written leaves
    whatever else the developer has configured to leak in, and the assertion
    then fails on a key that has nothing to do with what is being tested."""
    for var in (
        "GEMINI_API_KEY", "GROQ_API_KEY",
        "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "x")
    from whichcloud.intake import available_providers

    assert available_providers() == ["gemini"]


def test_no_credentials_names_both_options(monkeypatch):
    """Every provider has to be cleared, not the two that existed when this
    was written -- a key left in the environment means the call succeeds and
    the test reports that no error was raised."""
    for var in (
        "GEMINI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY",
        "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(IntakeError, match="GEMINI_API_KEY"):
        parse_description("a shop")


def test_unknown_provider_is_rejected():
    # "openai" used to stand in for an unknown provider here. It is a real
    # reader now, so the example has to be something that genuinely is not.
    with pytest.raises(IntakeError, match="Unknown provider"):
        parse_description("a shop", provider="llama")


# ── gemini transport ────────────────────────────────────────────────────


class FakeGeminiResponse:
    def __init__(self, parsed):
        self.parsed = parsed


class FakeGeminiClient:
    """Stands in for genai.Client — mirrors client.models.generate_content."""

    def __init__(self, response):
        self._response = response
        self.calls: list[dict] = []
        self.models = self

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def test_gemini_path_produces_the_same_intake():
    """Both providers fill the same object — the engine cannot tell them
    apart, which is the entire point of the Requirement contract."""
    client = FakeGeminiClient(FakeGeminiResponse(draft(assumed=["region"])))
    intake = parse_description("a shop", provider="gemini", client=client)

    assert intake.provider == "gemini"
    assert intake.requirement.workload_type == "web"
    assert intake.assumed == ("region",)


def test_gemini_request_uses_structured_output():
    client = FakeGeminiClient(FakeGeminiResponse(draft()))
    parse_description("a shop", provider="gemini", client=client)

    call = client.calls[0]
    # Against the constant, not a literal. Pinning the name here meant this
    # broke the day the model was unpinned, which is a test of the constant
    # rather than of the behaviour it was written for.
    assert call["model"] == GEMINI_MODEL
    assert call["contents"] == "a shop"
    assert call["config"]["response_schema"] is RequirementDraft
    assert call["config"]["response_mime_type"] == "application/json"


def test_gemini_failure_becomes_intake_error():
    client = FakeGeminiClient(RuntimeError("quota exceeded"))
    with pytest.raises(IntakeError, match="Could not reach Gemini"):
        parse_description("a shop", provider="gemini", client=client)


def test_gemini_missing_structured_output_is_an_error():
    client = FakeGeminiClient(FakeGeminiResponse(None))
    with pytest.raises(IntakeError, match="no structured output"):
        parse_description("a shop", provider="gemini", client=client)


def test_draft_schema_has_no_nullable_fields():
    """Nullable-union support varies between providers. Every field is
    required with a sentinel so one schema works on both."""
    schema = RequirementDraft.model_json_schema()
    for name, spec in schema["properties"].items():
        assert "anyOf" not in spec, f"{name} is a nullable union"
    assert set(schema["required"]) == set(schema["properties"])
