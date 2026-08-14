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

import os
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from .pricing.models import REGIONS
from .requirements import Requirement

Provider = Literal["gemini", "anthropic"]

# Free tier, fast, and comfortably capable of structured extraction.
GEMINI_MODEL = "gemini-2.5-flash"

# Extraction is a short, scoped task — the model is reading a paragraph and
# filling a struct, not designing anything.
ANTHROPIC_MODEL = "claude-opus-5"
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
    if os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"):
        found.append("anthropic")
    return found


def _detect_provider() -> Provider:
    found = available_providers()
    if not found:
        raise IntakeError(
            "No language-model credentials found. Set GEMINI_API_KEY (free tier: "
            "aistudio.google.com/apikey) or ANTHROPIC_API_KEY (pay-as-you-go). "
            "Only plain-English intake needs this — the rest of WhichCloud, "
            "including all pricing and recommendations, runs without it."
        )
    return found[0]


# ── providers ───────────────────────────────────────────────────────────


def _extract_gemini(description: str, client=None) -> RequirementDraft:
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
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
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


def _extract_anthropic(description: str, client=None) -> RequirementDraft:
    """Claude via structured output."""
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise IntakeError("anthropic is not installed: pip install anthropic") from exc

    client = client or anthropic.Anthropic()

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


_EXTRACTORS = {"gemini": _extract_gemini, "anthropic": _extract_anthropic}


# ── public entry point ──────────────────────────────────────────────────


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

    draft = _EXTRACTORS[provider](description, client)

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
