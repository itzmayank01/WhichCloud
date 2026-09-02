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

import concurrent.futures
import json
import os
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from .pricing.models import REGIONS
from .requirements import Requirement

#: Wall-clock budget per provider call. A provider slow to respond is one the
#: chain should give up on and try the next of, not wait on indefinitely: a
#: hung Gemini call with no timeout blocked the whole of /describe for
#: minutes while healthy keys sat unused behind it. Generous enough that a
#: merely-slow provider still answers; short enough that a hung one fails
#: over while the user is still watching.
EXTRACT_TIMEOUT_S = 25.0

Provider = Literal["gemini", "groq", "anthropic", "openai"]

# Free tier, fast, and comfortably capable of structured extraction.
#: The rolling alias, not a pinned version. Keys issued today cannot call
#: gemini-2.5-flash at all -- Google answers "no longer available to new
#: users" -- so a version that works for the oldest key in the chain 404s for
#: the newest. The architecture reader was fixed for this and this was missed,
#: which left /describe broken while /architecture worked.
#: Flash, not pro -- measured, not assumed.
#:
#: Pro reads a description better, and it was tried. On the free tier its
#: quota is a fraction of flash's and it returned 429 RESOURCE_EXHAUSTED on
#: the second call of a three-case test, while flash kept answering. A
#: better reader that is out of quota reads nothing at all.
#:
#: Set WHICHCLOUD_GEMINI_MODEL=gemini-pro-latest on a paid Google account.
GEMINI_MODEL = os.getenv("WHICHCLOUD_GEMINI_MODEL", "gemini-flash-latest")

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
- needs_email is true only if the description mentions sending email — \
confirmations, receipts, invoices, alerts — to users or staff.
- needs_queue is true only if the description mentions background jobs, \
async processing, or work that happens after the request returns rather \
than during it (report generation, video encoding, batch invoicing).
- needs_notifications is true only if the description mentions push \
notifications, SMS, or in-app/mobile alerts — not email, which needs_email \
already covers.
- serverless is true ONLY when the workload is a genuine fit for a \
pay-per-use, scale-to-zero design: spiky or unpredictable or bursty traffic, \
event-driven or API backends, low or idle baseline, "only pay when used", or \
an explicit ask for Lambda/serverless. It is FALSE for a steady always-on \
application, anything that states it needs a relational/SQL database, or a \
system that must not go down during business hours (that implies always-on \
servers). Be conservative — when unsure, false.
- ai is true when the app's CORE value is a machine-learning capability — \
image recognition, object/face detection, content moderation, sentiment or \
NLP analysis. It is FALSE for an ordinary app that merely stores data or \
serves pages. Then set the specific capability: ai_vision for anything about \
images or video (recognition, detection, moderation, faces, "analyse \
photos/uploads"); ai_language for anything about text (sentiment, NLP, \
entities, key phrases, "analyse reviews/comments"). Set both if both are \
described. When ai is false, both ai_vision and ai_language are false.
- event_driven is true when the system's job is to INGEST AND PROCESS A \
STREAM of events or telemetry rather than to serve user requests: streaming \
ingest, continuous or real-time event processing, sensor/IoT data, \
clickstream, a metrics or logs pipeline, "events a day streaming in", \
"processed as they arrive". A request-serving web app with a database is \
NOT event_driven even if it emits some events. Set telemetry when that \
stream is time-series, append-only or sensor data (IoT readings, metrics, \
device events) — the signal that the data must NOT go in a relational \
database. When event_driven is false, telemetry is false.
- The four derivation axes describe the workload's shape and DRIVE the \
architecture. Answer each from the text, defaulting to the web-app answer \
only when nothing indicates otherwise:
  ingress_shape — what enters: "requests" (users calling an API/site), \
"events" (webhooks, messages, discrete signals), "files" (uploads, media), \
"batches" (scheduled bulk loads), "connections" (persistent sockets, live \
chat), "streams" (continuous high-rate telemetry/clickstream).
  processing_mode — "synchronous" (answered in the request), \
"near-real-time" (processed as it arrives, seconds of latency), "batch" \
(accumulated into scheduled runs), "offline" (deferred, no latency need).
  data_shape — what the data IS: "relational" (records with relationships), \
"time-series" (telemetry, metrics, append-only by time), "key-value", \
"document", "object" (media/blobs), "search" (full-text), "warehouse" \
(analytics/OLAP), "mixed" (genuinely several). Sensor/IoT/metrics data is \
time-series, NOT relational.
  egress_shape — what leaves: "api", "media" (video/large files to users), \
"notifications", "dashboards" (reporting views), "exports" (bulk data out), \
"none" (internal pipeline, nothing served).
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
    needs_email: bool = Field(description="Sends transactional email — confirmations, receipts, alerts?")
    needs_queue: bool = Field(description="Background jobs or async work decoupled from the request path?")
    needs_notifications: bool = Field(description="Push notifications or SMS alerts, separate from email?")
    serverless: bool = Field(description="Genuine serverless fit — spiky/event-driven/scale-to-zero, no always-on servers or relational DB needed?")
    ai: bool = Field(description="Is the app's core value a managed AI/ML capability (image recognition, NLP/sentiment)?")
    ai_vision: bool = Field(description="Analyses images/video — recognition, detection, moderation, faces?")
    ai_language: bool = Field(description="Analyses text — sentiment, NLP, entities, key phrases?")
    event_driven: bool = Field(description="A stream/event processor — continuous ingestion of events or telemetry processed as they arrive, not a request-serving app?")
    telemetry: bool = Field(description="Time-series, append-only or sensor telemetry data (IoT, metrics, clickstream)?")
    ingress_shape: Literal["requests", "events", "files", "batches", "connections", "streams"] = Field(
        description="What ENTERS the system: user requests, discrete events, uploaded files, scheduled batches, persistent connections, or continuous streams"
    )
    processing_mode: Literal["synchronous", "near-real-time", "batch", "offline"] = Field(
        description="What must HAPPEN to the input: answered in the request (synchronous), processed as it arrives (near-real-time), accumulated into runs (batch), or deferred (offline)"
    )
    data_shape: Literal["relational", "time-series", "key-value", "document", "object", "search", "warehouse", "mixed"] = Field(
        description="What the data IS at rest: relational records, time-series/telemetry, key-value, documents, large objects/media, full-text search, analytics warehouse, or mixed"
    )
    egress_shape: Literal["api", "media", "notifications", "dashboards", "exports", "none"] = Field(
        description="What LEAVES, to whom: API responses, media/files, notifications, dashboards/reports, bulk exports, or nothing (internal pipeline)"
    )
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
            needs_email=self.needs_email,
            needs_queue=self.needs_queue,
            needs_notifications=self.needs_notifications,
            serverless=self.serverless,
            ai=self.ai,
            ai_vision=self.ai_vision,
            ai_language=self.ai_language,
            event_driven=self.event_driven,
            telemetry=self.telemetry,
            ingress_shape=self.ingress_shape,
            processing_mode=self.processing_mode,
            data_shape=self.data_shape,
            egress_shape=self.egress_shape,
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


#: Preference order, most accurate first. Reading a description is the one
#: step nothing downstream can repair: the engine sizes and prices from the
#: extracted fields, so a reader that misses "head office sees live numbers"
#: produces a correct price for the wrong architecture.
#:
#: Set WHICHCLOUD_READER_ORDER to a comma-separated list to override --
#: "gemini,groq,anthropic" restores the cheapest-first order this used to
#: have, which matters if the Anthropic bill does.
#: Order matters less than reaching a reader that answers. Claude Opus is
#: the most accurate of these and is NOT first, for one measured reason:
#: the configured Anthropic keys return "Your credit balance is too low to
#: access the Anthropic API" on every call. A first-choice reader that
#: always 400s costs a round-trip per request and reads nothing.
#:
#: Add API credit, then put it first with one line and nothing else:
#:     WHICHCLOUD_READER_ORDER=anthropic,gemini,groq
#:
#: (An Anthropic *subscription* does not grant API credit -- they are
#: separate products, which is the trap this comment exists to record.)
DEFAULT_READER_ORDER: tuple[Provider, ...] = (
    "gemini",
    "groq",
    "anthropic",  # claude-opus-5 -- preferred once it has credit
    "openai",
)

#: What each provider needs before it can be tried.
_CREDENTIALS: dict[Provider, tuple[str, ...]] = {
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "groq": ("GROQ_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"),
    "openai": ("OPENAI_API_KEY",),
}


def available_providers() -> list[Provider]:
    """Which providers have credentials present, most accurate first.

    The fallback chain still runs top to bottom, so a provider that is out
    of quota or returns malformed JSON hands off to the next one -- the
    accuracy preference costs nothing when the preferred reader is down.
    """
    raw = os.getenv("WHICHCLOUD_READER_ORDER", "")
    order: tuple[Provider, ...] = DEFAULT_READER_ORDER
    if raw.strip():
        wanted = [p.strip().lower() for p in raw.split(",") if p.strip()]
        chosen = [p for p in wanted if p in _CREDENTIALS]
        if chosen:
            order = tuple(chosen)  # type: ignore[assignment]

    return [
        provider
        for provider in order
        if any(os.getenv(name) for name in _CREDENTIALS[provider])
    ]


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
"needs_search":false,"needs_email":false,"needs_queue":false,
"needs_notifications":false,"serverless":false,"ai":false,"ai_vision":false,
"ai_language":false,"event_driven":false,"telemetry":false,
"ingress_shape":"requests","processing_mode":"synchronous",
"data_shape":"relational","egress_shape":"api",
"daily_transactions":8000,
"latency_target_ms":0,"provider_preference":"none","compliance":[],
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
needs_email: sends confirmations, receipts, invoices or alerts by email.
needs_queue: background jobs or async work off the request path.
needs_notifications: push/SMS/app alerts, not email.
serverless: spiky/event-driven/scale-to-zero, pay-per-use, no always-on \
servers or SQL database. False for steady always-on apps. Be conservative.
ai: core value is an ML capability (image recognition, sentiment/NLP). \
ai_vision: images/video. ai_language: text/sentiment. All false if ai false.
event_driven: ingests/processes a STREAM of events or telemetry, not a \
request-serving app. telemetry: time-series/append-only/sensor data (IoT, \
metrics). Both false for an ordinary web app.
ingress_shape: requests|events|files|batches|connections|streams — what enters.
processing_mode: synchronous|near-real-time|batch|offline — what happens to it.
data_shape: relational|time-series|key-value|document|object|search|warehouse\
|mixed — what the data is. Sensor/IoT/metrics = time-series, not relational.
egress_shape: api|media|notifications|dashboards|exports|none — what leaves.
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
            # gpt-oss is a reasoning model. At the default effort it spends
            # the whole 1500-token budget thinking, returns empty content,
            # and Groq rejects that with a 400 whose `failed_generation` is
            # an empty string -- which reads like a schema problem and is
            # not one. llm_extract._groq already learned this; intake did
            # not, so every Groq key in the failover chain failed the same
            # way and /describe 400'd whenever Gemini was overloaded.
            reasoning_effort="low",
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
    # One executor for the whole chain. Each call runs on a worker thread so a
    # hung provider can be ABANDONED after EXTRACT_TIMEOUT_S -- the SDKs differ
    # in how (and whether) they honour a timeout argument, so a wall-clock budget
    # around the call is the one mechanism that works for all of them. A
    # leaked worker on a genuinely hung call is acceptable: the process
    # carries on and the next provider answers.
    stalled: set[str] = set()  # providers whose endpoint is hung, not a key
    # One worker per candidate, and NOT a `with` block: a genuinely hung call
    # leaves its thread running, and `with`-exit (shutdown(wait=True)) would
    # block the whole request on that leaked thread -- reintroducing the hang
    # this timeout exists to remove. shutdown(wait=False) at the end lets the
    # request return while the orphan finishes and is discarded.
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(chain)))
    try:
        for candidate in chain:
            # A timeout is an endpoint problem, not a key one: the other keys
            # of a stalled provider hit the same slow endpoint, so trying them
            # only burns another EXTRACT_TIMEOUT_S each. Skip straight to the
            # next provider. (A quota error, by contrast, IS key-specific --
            # those still walk every key.)
            if candidate.provider in stalled:
                continue
            future = pool.submit(
                _EXTRACTORS[candidate.provider], description, None, candidate.key
            )
            try:
                return future.result(timeout=EXTRACT_TIMEOUT_S)
            except concurrent.futures.TimeoutError:
                future.cancel()
                stalled.add(candidate.provider)
                failures.append((
                    candidate.label,
                    TimeoutError(f"no response in {EXTRACT_TIMEOUT_S:.0f}s (overloaded)"),
                ))
            except Exception as exc:
                failures.append((candidate.label, exc))
    finally:
        pool.shutdown(wait=False)

    if all(is_exhausted(exc) for _, exc in failures):
        raise IntakeError(
            "Every configured model is out of capacity or too slow right now ("
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
