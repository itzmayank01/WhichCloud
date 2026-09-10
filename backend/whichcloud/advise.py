"""Ask a question about an architecture the engine has already priced.

The rule this module exists to enforce: **the model never states a price.**

Everywhere else in WhichCloud a number comes from the catalog, and the whole
argument for the product is that competitors' figures are a language model
guessing. An advisor that answered "switching to Graviton saves you about
$40" would put exactly that guess back in, in the one place a reader is most
inclined to trust it -- next to real numbers.

So the split is: the model reads the priced architecture and proposes
CHANGES, in the engine's own vocabulary. The engine prices the change. If a
suggestion cannot be expressed as something the engine can re-price, it is
returned as advice with no figure attached and labelled as such -- the same
treatment `engine.py` already gives techniques it cannot model.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
from pydantic import BaseModel, Field, field_validator

from whichcloud.intake import (
    ANTHROPIC_MODEL,
    EXTRACT_TIMEOUT_S,
    GEMINI_MODEL,
    GROQ_MODEL,
    OPENAI_MODEL,
    IntakeError,
)

#: Levers the engine can actually re-price. A suggestion naming one of these
#: can be costed and shown as a real difference; anything else is advice.
#: Kept as a closed set deliberately -- an open string would let the model
#: invent a knob, and the failure would surface as a silently ignored
#: suggestion rather than an error.
LEVERS: frozenset[str] = frozenset({
    "compute_count",
    "compute_vcpu",
    "compute_memory_gb",
    "compute_arch",
    "database_vcpu",
    "database_memory_gb",
    "database_read_replicas",
    "database_multi_az",
    "cache_vcpu",
    "cache_memory_gb",
    "nat_gateway_count",
    "cdn",
    "spot",
    "commitment",
    # Observability and security. These were missing from the first version
    # and it showed immediately: asked why a reliable tier cost what it did,
    # every model reached for GuardDuty, X-Ray, detailed monitoring and
    # backup retention -- correctly, they are real lines on the bill -- and
    # every one of those suggestions came back lever "none" and therefore
    # unpriceable. The vocabulary has to cover what the estimator actually
    # meters, not just the compute shape.
    "threat_detection",
    "tracing_monthly_traces",
    "posture_monthly_checks",
    "flowlog_gb",
    "backup_gb",
    "waf_rule_count",
    "none",
})

DIRECTIONS: frozenset[str] = frozenset(
    {"increase", "decrease", "enable", "disable", "unchanged"}
)


class Suggestion(BaseModel):
    """One thing that could be done differently, and why."""

    title: str = Field(description="Short imperative, e.g. 'Drop the second NAT gateway'")
    rationale: str = Field(
        description=(
            "Why this applies to THIS architecture, citing what you were shown. "
            "Never state or estimate a cost."
        )
    )
    #: The vocabulary is spelled out in the description rather than carried by
    #: the type. Dropping the Literal stopped one bad value from voiding a
    #: whole review (see the validators below), but it also emptied the enum
    #: out of the JSON schema Gemini is handed -- so the model that DOES read
    #: a schema stopped being told what the levers were, and mapped almost
    #: everything to "none". Listing them here reaches every provider: the
    #: schema readers via the description, the others via _shape_hint().
    lever: str = Field(
        default="none",
        description=(
            "The engine knob this maps to. MUST be exactly one of: "
            + ", ".join(sorted(LEVERS))
            + ". Use 'none' only when the idea is real but maps to none of them."
        ),
    )
    direction: str = Field(
        default="unchanged",
        description=(
            "Which way to move the lever. One of: increase, decrease, enable, "
            "disable, unchanged."
        ),
    )
    trade_off: str = Field(
        default="",
        description="What is given up. Every saving costs something; name it.",
    )

    # Coerced rather than rejected, both of them.
    #
    # These started as Literals and a model that answered well but named a
    # lever outside the set -- "instance_type", "storage_class" -- failed
    # validation, which threw away the entire review over one field of one
    # suggestion. That is the wrong trade: an unmappable suggestion is exactly
    # the case this module already has a plan for, which is to show it as
    # advice with no figure attached. Unknown now means "none", so the idea
    # survives and simply arrives unpriceable.
    @field_validator("lever")
    @classmethod
    def _known_lever(cls, value: str) -> str:
        return value if value in LEVERS else "none"

    @field_validator("direction")
    @classmethod
    def _known_direction(cls, value: str) -> str:
        return value if value in DIRECTIONS else "unchanged"


class Advice(BaseModel):
    """The answer, plus what could be done about it."""

    answer: str = Field(
        description=(
            "A direct answer to the question in plain English, 2-4 sentences. "
            "Never state or estimate a cost -- refer to figures already shown."
        )
    )
    suggestions: list[Suggestion] = Field(
        default_factory=list, description="At most four, most impactful first."
    )
    verdict: str = Field(
        default="not_applicable",
        description=(
            "When the question asks whether the architecture (or an edit to it) "
            "is correct, the judgement: sound | has_risks | not_recommended | "
            "not_applicable. 'not_applicable' when it does not."
        ),
    )

    @field_validator("verdict")
    @classmethod
    def _known_verdict(cls, value: str) -> str:
        allowed = {"sound", "has_risks", "not_recommended", "not_applicable"}
        return value if value in allowed else "not_applicable"


SYSTEM = """\
You are a cloud architecture reviewer inside a pricing tool.

You will be shown a REAL architecture that a pricing engine has already
costed against live provider rate cards, and a question about it.

Absolute rules:

1. NEVER invent, estimate, project, or calculate a cost. Not "roughly $40",
   not "about 30% less", not "that would save a third". The engine prices
   every change you propose; a number from you would be a guess sitting next
   to measured figures.

   You MAY quote a line item's own figure exactly as it appears in the list
   below, to say what is driving the bill. You may NOT do arithmetic on those
   figures -- no adding two lines together, no subtracting to show a saving,
   no percentages. Quoting is citation; arithmetic is a new number, and a new
   number from you is the thing this rule exists to prevent. Prefer naming
   the line ("the database is the largest item") over quoting it.
2. Ground every claim in what you were shown. If the architecture has no
   cache, do not discuss its cache.
3. Respect what the workload requires. If the requirement says it must not go
   down during business hours, do not propose removing redundancy to save
   money -- that is not a cheaper answer, it is the wrong one.
4. Name the trade-off for every suggestion. Something is always given up.
5. If the question cannot be answered from what you were shown, say so
   plainly rather than inventing context.

Map each suggestion to a lever the engine can re-price where one fits. Use
lever "none" when the idea is sound but is not one of the listed knobs -- it
will be shown as advice without a figure, which is honest, rather than
dropped."""


def _facts(option: dict, requirement: dict | None) -> str:
    """The architecture, written out as the model's only source of truth.

    Deliberately verbose about gaps. An advisor that is not told which
    components went unpriced will confidently reason about a total that is
    missing its database, and the reader has no way to see that it did.
    """
    lines: list[str] = []

    lines.append(f"TIER: {option.get('label')}")
    lines.append(f"PROVIDER: {option.get('provider')}  REGION: {option.get('region')}")
    lines.append(f"SHAPE: {option.get('shape')}")
    total = option.get("ondemand_monthly_usd") or option.get("monthly_usd")
    lines.append(f"TOTAL SHOWN TO THE USER: ${total} per month")
    lines.append("")

    lines.append("LINE ITEMS (label, sku, monthly USD) -- these are measured:")
    for item in option.get("items", []):
        lines.append(
            f"  - {item.get('label')} | {item.get('sku')} | ${item.get('monthly_usd')}"
        )

    applied = option.get("applied") or []
    if applied:
        lines.append("")
        lines.append("OPTIMISATIONS ALREADY APPLIED (do not re-propose these):")
        for technique in applied:
            lines.append(f"  - {technique.get('name')}")

    advisory = option.get("advisory") or []
    if advisory:
        lines.append("")
        lines.append("ALREADY SURFACED AS UNPRICEABLE ADVICE (do not re-propose):")
        for technique in advisory:
            lines.append(f"  - {technique.get('name')}")

    missing = option.get("missing") or []
    if missing:
        lines.append("")
        lines.append(
            "COMPONENTS THE CATALOG COULD NOT PRICE -- the total above EXCLUDES "
            "these, so it is a floor rather than an answer:"
        )
        for gap in missing:
            lines.append(f"  - {gap}")

    unmet = option.get("unmet") or []
    if unmet:
        lines.append("")
        lines.append("REQUIREMENTS THIS TIER DOES NOT MEET:")
        for gap in unmet:
            lines.append(f"  - {gap}")

    if requirement:
        lines.append("")
        lines.append("WHAT THE USER ASKED FOR:")
        lines.append(json.dumps(requirement, indent=2, default=str)[:1500])

    return "\n".join(lines)


# ── model plumbing ──────────────────────────────────────────────────────
#
# Same failover shape as intake._draft_with_failover: walk every configured
# key, abandon a provider whose endpoint hangs, and report which one answered.
# Not shared with it because the two want different outputs -- that one wants
# a Requirement, this one wants an Advice -- and threading a schema through
# would have made the extractor signature worse for its only other caller.


def _ask_gemini(prompt: str, key: str) -> Advice:
    from google import genai

    client = genai.Client(api_key=key)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config={
            "system_instruction": SYSTEM,
            "response_mime_type": "application/json",
            "response_schema": Advice,
            # Zero, like intake. A review that changes its mind between two
            # identical questions reads as unreliable even when both answers
            # are reasonable.
            "temperature": 0,
        },
    )
    parsed = getattr(response, "parsed", None)
    if parsed is None:
        raise IntakeError("Gemini returned no structured advice.")
    return parsed


def _ask_openai_compatible(prompt: str, key: str, *, base_url: str | None, model: str) -> Advice:
    import openai

    client = openai.OpenAI(api_key=key, base_url=base_url) if base_url else openai.OpenAI(api_key=key)
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        max_tokens=2000,
        # json_object, not json_schema: Groq's models reject the strict form,
        # which intake.py records learning the hard way. The shape is stated
        # in the prompt instead.
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM + "\n\n" + _shape_hint()},
            {"role": "user", "content": prompt},
        ],
    )
    content = response.choices[0].message.content or ""
    if not content.strip():
        raise IntakeError("Model returned empty advice.")
    return Advice.model_validate_json(content)


def _ask_anthropic(prompt: str, key: str) -> Advice:
    import anthropic

    client = anthropic.Anthropic(api_key=key)
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2000,
        system=SYSTEM + "\n\n" + _shape_hint(),
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise IntakeError("Claude returned no JSON advice.")
    return Advice.model_validate_json(text[start : end + 1])


def _shape_hint() -> str:
    """The schema, for providers that will not take one as a parameter.

    This has to spell the lever vocabulary out. Gemini receives the Pydantic
    model and honours it; Groq and Claude get only this string, and the first
    version described `lever` as "str" -- so they filled it with sensible
    prose the validator then coerced to "none", and EVERY suggestion came
    back unpriceable. The enum was never reaching the models that needed it
    written down.
    """
    return (
        "Reply with JSON only, no prose around it, in exactly this shape:\n"
        '{"answer": str, "verdict": '
        '"sound"|"has_risks"|"not_recommended"|"not_applicable", '
        '"suggestions": [{"title": str, "rationale": str, "lever": str, '
        '"direction": "increase"|"decrease"|"enable"|"disable"|"unchanged", '
        '"trade_off": str}]}\n\n'
        '"lever" MUST be exactly one of these strings:\n'
        + ", ".join(sorted(LEVERS))
        + '\nUse "none" only when the suggestion genuinely maps to none of them.'
    )


def _call(candidate, prompt: str) -> Advice:
    if candidate.provider == "gemini":
        return _ask_gemini(prompt, candidate.key)
    if candidate.provider == "groq":
        return _ask_openai_compatible(
            prompt, candidate.key,
            base_url="https://api.groq.com/openai/v1", model=GROQ_MODEL,
        )
    if candidate.provider == "anthropic":
        return _ask_anthropic(prompt, candidate.key)
    if candidate.provider == "openai":
        return _ask_openai_compatible(
            prompt, candidate.key, base_url=None, model=OPENAI_MODEL
        )
    raise IntakeError(f"No advisor for provider {candidate.provider}.")


def advise(
    question: str,
    option: dict,
    requirement: dict | None = None,
    *,
    reader: str | None = None,
) -> tuple[Advice, str]:
    """Answer `question` about `option`. Returns the advice and who wrote it.

    The reader label is returned rather than logged because the interface
    shows it: an answer from a model is a different kind of claim from a
    number out of the catalog, and the person reading it should be able to
    tell which they are looking at without checking the docs.
    """
    from whichcloud.architecture.readers import candidates, is_exhausted

    chain = candidates(reader)
    if not chain:
        raise IntakeError(
            "No language-model credentials found. Set GEMINI_API_KEY (free tier: "
            "aistudio.google.com/apikey). Pricing and recommendations run without "
            "one; only this advisor needs it."
        )

    prompt = (
        f"{_facts(option, requirement)}\n\n"
        f"QUESTION FROM THE USER:\n{question.strip()}\n"
    )

    failures: list[tuple[str, Exception]] = []
    stalled: set[str] = set()
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(chain)))
    try:
        for candidate in chain:
            if candidate.provider in stalled:
                continue
            future = pool.submit(_call, candidate, prompt)
            try:
                return future.result(timeout=EXTRACT_TIMEOUT_S), candidate.label
            except concurrent.futures.TimeoutError:
                future.cancel()
                stalled.add(candidate.provider)
                failures.append((candidate.label, TimeoutError("no response in time")))
            except Exception as exc:
                failures.append((candidate.label, exc))
    finally:
        pool.shutdown(wait=False)

    if failures and all(is_exhausted(exc) for _, exc in failures):
        raise IntakeError(
            "Every configured model is out of capacity right now ("
            + ", ".join(label for label, _ in failures)
            + "). Add another key as GEMINI_API_KEY_2 or GROQ_API_KEY."
        )
    label, exc = next(
        (f for f in failures if not is_exhausted(f[1])), failures[0]
    ) if failures else ("no reader", IntakeError("no candidates"))
    raise IntakeError(f"{label} could not answer that: {str(exc)[:200]}") from exc
