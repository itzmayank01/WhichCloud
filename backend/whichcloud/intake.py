"""Plain English in, a validated Requirement out.

This is the thin adapter the engine was built for. A language model reads a
free-form description and fills the same `Requirement` object a person would
fill by hand; nothing downstream knows or cares which one happened.

Two providers are supported and produce identical results:

  gemini     Google Gemini — has a genuinely free tier, so this is the default
             when GEMINI_API_KEY is set. See the privacy note below.
  anthropic  Claude — better on ambiguous descriptions, but pay-as-you-go.

Three design decisions carry most of the weight:

**The model reports what it had to guess.** A description rarely mentions
every field, so the draft carries an `assumed` list and one `clarifying_
question`. That turns "the model invented a budget" into "the engine knows the
budget was assumed and can ask about it" — the difference between a system
that hides its uncertainty and one that surfaces it.

**Validation happens on our side, not the model's.** Structured outputs
guarantee the shape; `Requirement` rejects the values. A hallucinated
`workload_type` fails loudly at the boundary rather than producing a
confidently wrong architecture three steps later.

**The provider is swappable because the contract is the object, not the API.**
Both providers fill `RequirementDraft`; only the transport differs.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from .pricing.models import REGIONS
from .requirements import Requirement

Provider = Literal["gemini", "groq", "anthropic", "openai"]

# Free tier, fast, and comfortably capable of structured extraction.
#: The rolling alias, not a pinned version. Keys issued today cannot call
#: gemini-2.5-flash at all -- Google answers "no longer available to new
#: users" -- so a version that works for the oldest key in the chain 404s for
#: the newest. The architecture reader was fixed for this and this was missed,
#: which left /describe broken while /architecture worked.
GEMINI_MODEL = "gemini-flash-latest"

# Extraction is a short, scoped task — the model is reading a paragraph and
# filling a struct, not designing anything.
ANTHROPIC_MODEL = "claude-opus-5"
OPENAI_MODEL = "gpt-4.1-mini"

#: Checked against the account's own model list rather than documentation --
#: llama-3.3-70b-versatile was gone, and a pinned name that no longer exists
#: fails identically to a bad key.
GROQ_MODEL = "openai/gpt-oss-120b"
ANTHROPIC_EFFORT = "low"

SYSTEM = f"""\
You turn a plain-English description of an application into a structured \
requirement for a cloud architecture tool.

Extract only what the description supports. When the description does not \
mention a field, choose the most reasonable default for the kind of \
application described AND add that field's name to `assumed`. Never present \
a guess as though the user stated it.

Region must be one of: {', '.join(sorted(REGIONS))}. Pick the one nearest the \
audience the description implies; if none is implied, use "india" and mark it \
assumed.

Guidance on the fields that are easy to get wrong:
- traffic_pattern is "spiky" only if the description implies bursts (sales, \
launches, batch windows, weekend peaks). Steady background load is "steady".
- interruptible is true only when the work can be restarted without harm — \
batch jobs, ML training, queue workers. Anything serving live user requests \
is false.
- high_availability is true only if the description mentions uptime, \
redundancy, or the cost of downtime.
- arm_compatible is true unless the description names an x86-only dependency.
- Scale: "low" is a few thousand users or an internal tool, "medium" is tens \
of thousands, "high" is hundreds of thousands or more.
- needs_waf is true only if the description mentions attacks, fraud on \
incoming traffic, bots, DDoS, or explicitly asks to be protected — not for \
ordinary auth or encryption.
- needs_event_streaming is true only if something must react to events as \
they happen — real-time fraud detection on a payment stream, live telemetry, \
clickstream processing. Batch/nightly processing of the same data is false.
- needs_analytics is true if the description asks for dashboards, \
reporting, or aggregation across the data (OLAP) — and also when it asks \
for a central view over many locations or units, however plainly it is \
put. "Head office can see live numbers", "see sales across all branches" \
and "one dashboard for every site" are all aggregation across the estate \
and count. It is false for looking up a single record, which the database \
already serves.
- needs_search is true only if the description asks to search or filter \
across records by content — a product catalogue search, a log search. Not \
for fetching one record by id.
- daily_transactions: the stated number of orders/transactions/payments per \
day. Convert other periods (per month / 30, per year / 365). Use 0 when the \
description gives no number — never estimate one from company size.
- latency_target_ms: a number only if the description states or clearly \
implies a response-time bound ("sub-second", "real-time", "under 200ms"). \
"Sub-second" means 1000. Use 0 if nothing implies a bound.

Set `clarifying_question` to the single most useful question to ask next — \
the one whose answer would most change the recommendation. Ask about one \
thing only, in plain language, no jargon. If the description is complete \
enough that no question would materially change the result, leave it empty.

For `budget_monthly_usd`, use -1 when the description gives no budget.
"""


class RequirementDraft(BaseModel):
    """What the model returns.

    Every field is required and non-nullable. That is deliberate: schema
    support for nullable unions varies between providers, and a sentinel we
    control (-1, "") behaves the same everywhere. `budget_monthly_usd` of -1
    and an empty `clarifying_question` both mean "not present".
    """

    goal: str = Field(description="One-line restatement of what they're building")
    workload_type: Literal["web", "api", "batch", "ml", "storage", "mixed"]
    traffic_pattern: Literal["steady", "spiky", "unknown"]
    traffic_scale: Literal["low", "medium", "high"]
    region: str = Field(description=f"One of: {', '.join(sorted(REGIONS))}")

    budget_monthly_usd: float = Field(
        description="Monthly budget in USD, or -1 if the description gives none"
    )
    storage_gb: float = Field(description="Object storage in GB")
    egress_gb: float = Field(description="Outbound traffic per month in GB")

    interruptible: bool = Field(description="Can the work be restarted safely?")
    high_availability: bool = Field(description="Must it survive a zone failure?")
    arm_compatible: bool = Field(description="No x86-only dependencies?")

    needs_waf: bool = Field(description="Protection against attacks/DDoS/bots on incoming traffic?")
    needs_event_streaming: bool = Field(description="Must react to events as they happen, not on a batch schedule?")
    needs_analytics: bool = Field(description="Dashboards/reporting/aggregation over the data, not just record lookups?")
    needs_search: bool = Field(description="Full-text or faceted search over the data?")
    daily_transactions: int = Field(description="Transactions/orders per day if stated, else 0")
    latency_target_ms: int = Field(
        description="Stated or implied response-time bound in ms; 0 if none implied"
    )

    provider_preference: Literal["aws", "azure", "gcp", "none"] = Field(
        description="'none' unless they named a cloud"
    )
    compliance: list[str] = Field(description="e.g. GDPR, HIPAA; empty if none")

    assumed: list[str] = Field(
        description="Field names you defaulted rather than read from the description"
    )
    clarifying_question: str = Field(
        description="The single most useful next question, or empty string"
    )

    @property
    def budget(self) -> float | None:
        """-1 is the wire representation of 'not mentioned'."""
        return None if self.budget_monthly_usd < 0 else self.budget_monthly_usd

    @property
    def question(self) -> str | None:
        return self.clarifying_question.strip() or None

    def to_requirement(self) -> Requirement:
        """Convert to the engine's contract, validating on the way through."""
        return Requirement(
            goal=self.goal,
            workload_type=self.workload_type,
            traffic_pattern=self.traffic_pattern,
            traffic_scale=self.traffic_scale,
            region=self.region,
            budget_monthly_usd=self.budget,
            storage_gb=self.storage_gb,
            egress_gb=self.egress_gb,
            interruptible=self.interruptible,
            high_availability=self.high_availability,
            arm_compatible=self.arm_compatible,
            needs_waf=self.needs_waf,
            needs_event_streaming=self.needs_event_streaming,
            needs_analytics=self.needs_analytics,
            needs_search=self.needs_search,
            daily_transactions=self.daily_transactions or None,
            latency_target_ms=self.latency_target_ms or None,
            provider_preference=(
                None if self.provider_preference == "none" else self.provider_preference
            ),
            compliance=tuple(self.compliance),
        )


@dataclass(frozen=True, slots=True)
class Intake:
    """A parsed description: the requirement, plus what we're unsure about."""

    requirement: Requirement
    assumed: tuple[str, ...]
    clarifying_question: str | None
    provider: Provider
    raw: RequirementDraft

    @property
    def is_confident(self) -> bool:
        """Did the description actually say most of this?"""
        return len(self.assumed) <= 2


class IntakeError(RuntimeError):
    """Raised when the description cannot be turned into a requirement."""


# ── provider selection ──────────────────────────────────────────────────


def available_providers() -> list[Provider]:
    """Which providers have credentials present, cheapest first."""
    found: list[Provider] = []
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        found.append("gemini")
    # Before the billed ones: Groq's free tier is measured per minute rather
    # than per day, so it is the one still answering when the day's Gemini
    # quota is gone.
    if os.getenv("GROQ_API_KEY"):
        found.append("groq")
    if os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"):
        found.append("anthropic")
    if os.getenv("OPENAI_API_KEY"):
        found.append("openai")
    return found


def _detect_provider() -> Provider:
    found = available_providers()
    if not found:
        raise IntakeError(
            "No language-model credentials found. Set GEMINI_API_KEY (free tier: "
            "aistudio.google.com/apikey), ANTHROPIC_API_KEY or OPENAI_API_KEY "
            "(both pay-as-you-go). "
            "Only plain-English intake needs this — the rest of WhichCloud, "
            "including all pricing and recommendations, runs without it."
        )
    return found[0]


# ── providers ───────────────────────────────────────────────────────────


def _extract_gemini(description: str, client=None, key: str | None = None) -> RequirementDraft:
    """Google Gemini via structured output.

    Privacy note worth knowing: on the free tier Google may use prompts and
    responses to improve its products. These descriptions are architecture
    summaries rather than user data, but do not paste anything confidential
    into a free-tier request.
    """
    try:
        from google import genai
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise IntakeError("google-genai is not installed: pip install google-genai") from exc

    if client is None:
        key = key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise IntakeError("GEMINI_API_KEY is not set.")
        client = genai.Client(api_key=key)

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=description.strip(),
            config={
                "system_instruction": SYSTEM,
                "response_mime_type": "application/json",
                "response_schema": RequirementDraft,
            },
        )
    except Exception as exc:
        raise IntakeError(f"Could not reach Gemini: {exc}") from exc

    draft = getattr(response, "parsed", None)
    if draft is None:
        raise IntakeError("Gemini returned no structured output for that description.")
    return draft


def _extract_anthropic(description: str, client=None, key: str | None = None) -> RequirementDraft:
    """Claude via structured output."""
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise IntakeError("anthropic is not installed: pip install anthropic") from exc

    # The chain hands us a specific key; without one the SDK reads the
    # environment, which is what a single-key setup expects.
    client = client or (
        anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
    )

    try:
        response = client.messages.parse(
            model=ANTHROPIC_MODEL,
            max_tokens=4096,
            system=SYSTEM,
            output_format=RequirementDraft,
            output_config={"effort": ANTHROPIC_EFFORT},
            messages=[{"role": "user", "content": description.strip()}],
        )
    except Exception as exc:
        raise IntakeError(f"Could not reach Claude: {exc}") from exc

    if getattr(response, "stop_reason", None) == "refusal":
        raise IntakeError(
            "Claude declined to process that description. Rephrase and retry."
        )

    draft = response.parsed_output
    if draft is None:
        raise IntakeError("Claude returned no structured output for that description.")
    return draft


def _extract_openai(description: str, client=None, key: str | None = None) -> RequirementDraft:
    """GPT via structured output.

    Same contract as the other two: the model fills in RequirementDraft and
    nothing else. It never sees a price and never returns one -- every figure
    on the site comes from the provider catalogs, and the reader's only job is
    turning a sentence into fields the engine can price.
    """
    try:
        import openai
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise IntakeError("openai is not installed: pip install openai") from exc

    client = client or (openai.OpenAI(api_key=key) if key else openai.OpenAI())

    try:
        response = client.responses.parse(
            model=OPENAI_MODEL,
            instructions=SYSTEM,
            input=description.strip(),
            text_format=RequirementDraft,
        )
    except Exception as exc:
        raise IntakeError(f"Could not reach OpenAI: {exc}") from exc

    draft = getattr(response, "output_parsed", None)
    if draft is None:
        raise IntakeError("OpenAI returned no structured output for that description.")
    return draft


#: A filled example, not the schema. Handed the schema's `properties`, Groq
#: returned it back with the field descriptions still in place -- {"goal":
#: {"description": ..., "type": "string"}} -- because a shape full of "type"
#: and "title" keys reads as the thing to reproduce. An example of the answer
#: leaves nothing to mirror.
_GROQ_SHAPE = """Reply with JSON in exactly this form, filled in from the text:
{"goal":"Online stock and billing system for a retail chain",
"workload_type":"web","traffic_pattern":"steady","traffic_scale":"medium",
"region":"india","budget_monthly_usd":500,"storage_gb":100,"egress_gb":50,
"interruptible":false,"high_availability":true,"arm_compatible":true,
"needs_waf":false,"needs_event_streaming":false,"needs_analytics":false,
"needs_search":false,"daily_transactions":8000,"latency_target_ms":0,
"provider_preference":"none","compliance":[],
"assumed":["storage_gb"],"clarifying_question":"How much data do you store?"}

workload_type: web, api, batch, ml, storage, mixed
traffic_pattern: steady, spiky, unknown
traffic_scale: low, medium, high
provider_preference: aws, azure, gcp, none
budget_monthly_usd: -1 when the text gives no budget.
needs_waf: attacks/DDoS/bots/fraud on incoming traffic, not ordinary auth.
needs_event_streaming: must react as events happen, not on a batch schedule.
needs_analytics: dashboards/reporting/aggregation, not single-record lookups.
needs_search: searching/filtering across records by content.
daily_transactions: stated transactions per day; 0 if not stated.
latency_target_ms: a stated or implied response-time bound; 0 if none.
assumed: names of fields you had to guess. clarifying_question: "" if none."""


def _extract_groq(
    description: str, client=None, key: str | None = None
) -> RequirementDraft:
    """Groq, which speaks OpenAI's protocol.

    Worth having here because its free tier is measured per minute rather than
    per day: when four Gemini keys are spent for the day, this still answers.
    A requirement is a short object, so the token limit that stops Groq
    reading a twenty five service architecture does not apply.

    json_object rather than json_schema. Groq's models reject the strict form,
    and the shape is small enough to state in the prompt.
    """
    try:
        import openai
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise IntakeError("openai is not installed: pip install openai") from exc

    key = key or os.getenv("GROQ_API_KEY")
    if not key:
        raise IntakeError("GROQ_API_KEY is not set.")

    client = client or openai.OpenAI(
        api_key=key, base_url="https://api.groq.com/openai/v1"
    )

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0,
            max_tokens=1500,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"{description}\n\n{_GROQ_SHAPE}"},
            ],
        )
    except Exception as exc:
        raise IntakeError(f"Could not reach Groq: {exc}") from exc

    return RequirementDraft.model_validate_json(
        response.choices[0].message.content or "{}"
    )


_EXTRACTORS = {
    "gemini": _extract_gemini,
    "groq": _extract_groq,
    "anthropic": _extract_anthropic,
    "openai": _extract_openai,
}


# ── public entry point ──────────────────────────────────────────────────


def _draft_with_failover(description: str, provider: Provider, client=None):
    """Try every configured key, not just the first.

    This module called one provider and gave up, so a spent Gemini quota broke
    /describe outright while /architecture -- which walks the chain -- carried
    on through the other nine keys. The same failure, fixed in one place and
    missed in the other.

    Only the chain differs; each provider's extractor is unchanged.
    """
    from whichcloud.architecture.readers import candidates, is_exhausted

    if client is not None:               # an injected client is the test's
        return _EXTRACTORS[provider](description, client)

    chain = [c for c in candidates(provider) if c.provider in _EXTRACTORS]
    if not chain:
        return _EXTRACTORS[provider](description, client)

    failures: list[tuple[str, Exception]] = []
    for candidate in chain:
        try:
            return _EXTRACTORS[candidate.provider](description, None, candidate.key)
        except Exception as exc:
            failures.append((candidate.label, exc))

    if all(is_exhausted(exc) for _, exc in failures):
        raise IntakeError(
            "Every configured model is out of capacity right now ("
            + ", ".join(label for label, _ in failures)
            + "). Add another key as GEMINI_API_KEY_2 or GROQ_API_KEY."
        )
    label, exc = next((f for f in failures if not is_exhausted(f[1])), failures[0])
    raise IntakeError(f"{label} could not read that: {str(exc)[:200]}") from exc


def parse_description(
    description: str,
    provider: Provider | None = None,
    client=None,
) -> Intake:
    """Turn a plain-English description into a validated Requirement.

    `provider` defaults to whichever credentials are present, preferring the
    free one. Pass `client` to inject a stub in tests; that implies
    `anthropic` unless a provider is named.

    Raises IntakeError if the description is empty, no provider is reachable,
    or the extraction fails our own validation.
    """
    if not description or not description.strip():
        raise IntakeError("Describe what you're building — the input was empty.")

    if provider is None:
        provider = "anthropic" if client is not None else _detect_provider()
    if provider not in _EXTRACTORS:
        raise IntakeError(
            f"Unknown provider {provider!r}. Choose one of: {', '.join(_EXTRACTORS)}"
        )

    draft = _draft_with_failover(description, provider, client)

    try:
        requirement = draft.to_requirement()
    except ValueError as exc:
        raise IntakeError(f"Extracted requirement failed validation: {exc}") from exc

    return Intake(
        requirement=requirement,
        assumed=tuple(draft.assumed),
        clarifying_question=draft.question,
        provider=provider,
        raw=draft,
    )
