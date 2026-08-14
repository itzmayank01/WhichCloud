"""Plain English in, a validated Requirement out.

This is the thin adapter the engine was built for. Claude reads a free-form
description and fills the same `Requirement` object a person would fill by
hand; nothing downstream knows or cares which one happened.

Two design decisions carry most of the weight:

**The model reports what it had to guess.** A description rarely mentions
every field, so the draft carries an `assumed` list and one `clarifying_
question`. That turns "the LLM invented a budget" into "the engine knows the
budget was assumed and can ask about it" — the difference between a system
that hides its uncertainty and one that surfaces it.

**Validation happens on our side, not the model's.** The draft is converted
through `Requirement`, which rejects unknown fields and impossible values. A
hallucinated `workload_type` fails loudly here rather than producing a
confidently wrong architecture three steps later.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from .pricing.models import REGIONS
from .requirements import Requirement

MODEL = "claude-opus-5"

# Extraction is a short, scoped task — the model is reading a paragraph and
# filling a struct, not designing anything. Low effort keeps it quick without
# touching the model choice.
EFFORT = "low"

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
enough that no question would materially change the result, leave it null.
"""


class RequirementDraft(BaseModel):
    """What Claude returns. Deliberately close to `Requirement`, plus metadata.

    Structured outputs guarantee this shape; they do not guarantee the values
    are sensible. `to_requirement()` is where sense is enforced.
    """

    goal: str = Field(description="One-line restatement of what they're building")
    workload_type: Literal["web", "api", "batch", "ml", "storage", "mixed"]
    traffic_pattern: Literal["steady", "spiky", "unknown"]
    traffic_scale: Literal["low", "medium", "high"]
    region: str = Field(description=f"One of: {', '.join(sorted(REGIONS))}")

    budget_monthly_usd: float | None = Field(
        description="Monthly budget in USD, or null if not mentioned"
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
    clarifying_question: str | None = Field(
        description="The single most useful next question, or null"
    )

    def to_requirement(self) -> Requirement:
        """Convert to the engine's contract, validating on the way through."""
        return Requirement(
            goal=self.goal,
            workload_type=self.workload_type,
            traffic_pattern=self.traffic_pattern,
            traffic_scale=self.traffic_scale,
            region=self.region,
            budget_monthly_usd=self.budget_monthly_usd,
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
    raw: RequirementDraft

    @property
    def is_confident(self) -> bool:
        """Did the description actually say most of this?"""
        return len(self.assumed) <= 2


class IntakeError(RuntimeError):
    """Raised when the description cannot be turned into a requirement."""


def _client():
    import anthropic

    if not (
        os.getenv("ANTHROPIC_API_KEY")
        or os.getenv("ANTHROPIC_AUTH_TOKEN")
        or os.path.isdir(os.path.expanduser("~/.config/anthropic"))
    ):
        raise IntakeError(
            "No Anthropic credentials found. Either export ANTHROPIC_API_KEY, "
            "or run `ant auth login` to store a profile. The rest of "
            "WhichCloud works without this — only plain-English intake needs it."
        )
    return anthropic.Anthropic()


def parse_description(description: str, client=None) -> Intake:
    """Turn a plain-English description into a validated Requirement.

    Raises IntakeError if the description is empty, the API is unreachable, or
    the model returns something that fails our own validation.
    """
    if not description or not description.strip():
        raise IntakeError("Describe what you're building — the input was empty.")

    client = client or _client()

    try:
        response = client.messages.parse(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM,
            output_format=RequirementDraft,
            output_config={"effort": EFFORT},
            messages=[{"role": "user", "content": description.strip()}],
        )
    except Exception as exc:  # network, auth, rate limit — all unusable here
        raise IntakeError(f"Could not reach Claude: {exc}") from exc

    if response.stop_reason == "refusal":
        raise IntakeError(
            "Claude declined to process that description. Rephrase and retry."
        )

    draft = response.parsed_output
    if draft is None:
        raise IntakeError("Claude returned no structured output for that description.")

    try:
        requirement = draft.to_requirement()
    except ValueError as exc:
        # Structured outputs guarantee the shape; our own rules catch the rest.
        raise IntakeError(f"Extracted requirement failed validation: {exc}") from exc

    return Intake(
        requirement=requirement,
        assumed=tuple(draft.assumed),
        clarifying_question=draft.clarifying_question,
        raw=draft,
    )
