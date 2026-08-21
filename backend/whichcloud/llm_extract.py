"""Extraction, by language model. Raw prompt in, Constraints out.

Why this replaced the phrase tables: they refused 85% of real phrasings
(tests/probes/classifier_accuracy.md). Twenty prompts written to defeat
them produced twenty different near-misses with almost no overlap -- the
tail is unbounded, not long, and reading open-ended English is what a
language model is actually for.

What this module is NOT allowed to do is the whole design:

  * It returns CONSTRAINTS ONLY. Never a regulation name, never a price,
    never a service or component. Compliance stays a (country, sector)
    table lookup and pricing stays a catalog lookup, because those are
    checkable facts and a model that invents one is the failure mode this
    project exists to avoid -- citing HIPAA at an Indian hospital is
    exactly the error the compliance table was built to make impossible.
  * It does not touch the decision layer. Constraints in, components out
    stays 100% deterministic, and is separately asserted.

Determinism is preserved rather than abandoned, by splitting the claim:

    decision + pricing : fully deterministic, asserted at 100 iterations
    extraction         : reproducible via cache, agreement rate measured

The cache is keyed on sha256(prompt|model|schema) and the first answer
wins, so a user who re-reads their own plan sees the plan they saw.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

from whichcloud.archetype import ARCHETYPES, UNKNOWN
from whichcloud.architecture.readers import candidates, is_exhausted
from whichcloud.constraints import REQUIRED, Constraints
from whichcloud.constraints import extract as phrase_extract
from whichcloud.pricing import store

#: Bumped whenever the prompt or schema below changes meaning, so a cached
#: answer produced under different rules is never served as a current one.
SCHEMA_VERSION = "constraints-v1"

#: THE PINNED PRIMARY. One provider and one model, named, because
#: different models return different Constraints from the same prompt --
#: so "98.5% field agreement" is a statement about THIS pair, and a plan
#: read by anything else is not strictly comparable to it. Failover still
#: happens (a demo with no reachable model is worse than one read by a
#: second choice), but it is marked rather than silent.
PRIMARY_PROVIDER = "groq"
PRIMARY_MODEL = "openai/gpt-oss-120b"

#: Per-provider model names. Gemini's `gemini-2.5-flash` -- what the older
#: architecture reader still names -- is no longer served to new keys and
#: 404s, hence `-latest`.
_MODELS: dict[str, str] = {
    "groq": PRIMARY_MODEL,
    "gemini": "gemini-flash-latest",
    "anthropic": "claude-sonnet-4-5",
}

#: Part of the cache key, so a change of primary produces new extractions
#: rather than silently serving ones made by a different model.
_MODEL = PRIMARY_MODEL

#: The minimum-evidence bar, as confidence BANDS rather than a flat
#: two-span requirement.
#:
#: The flat rule measured the wrong thing. It rejected eight correct
#: classifications that came back at 0.90 confidence, purely because the
#: model quoted one long span ("Consultants need to log candidates,
#: attach CVs, and track where each one is in the process") instead of
#: fragmenting it into two short ones. Worse, span COUNT is not stable
#: between calls on identical input -- the same prompt returned 1 span
#: then 2 -- so it was injecting variance rather than filtering it.
#:
#: What the bar is actually for is stopping a guess: one incidental
#: keyword, unopposed, must not classify. Confidence is the stable
#: signal for that, and span count only earns a vote in the middle band
#: where confidence alone is not decisive.
HIGH_CONFIDENCE = 0.85       # one substantive span is enough
MIN_ARCHETYPE_CONFIDENCE = 0.60  # below this, nothing classifies
MID_BAND_MIN_SPANS = 2       # between the two, corroboration is required

#: A span has to describe behaviour, not just contain a noun. "Postgres"
#: is a keyword; "drivers log what they picked up and dropped off" is a
#: workload. Four words is a coarse proxy for that difference, and coarse
#: is appropriate -- the alternative is another table of what counts.
MIN_SUBSTANTIVE_SPAN_WORDS = 4


def _substantive(span: str) -> bool:
    return len(span.split()) >= MIN_SUBSTANTIVE_SPAN_WORDS


def passes_evidence_bar(confidence: float, spans: list[str]) -> tuple[bool, str]:
    """Whether this classification has earned the right to be believed.

    Returns (ok, why) so the reason survives into the output -- a refusal
    that cannot say what it wanted is not much better than a guess.
    """
    substantive = [s for s in spans if _substantive(s)]
    if confidence >= HIGH_CONFIDENCE:
        if substantive:
            return True, f"confidence {confidence:.2f} with a substantive span"
        return False, (
            f"confidence {confidence:.2f} but no span describing the workload "
            "-- a high score resting on an incidental keyword is still a guess"
        )
    if confidence >= MIN_ARCHETYPE_CONFIDENCE:
        if len(spans) >= MID_BAND_MIN_SPANS:
            return True, f"confidence {confidence:.2f} corroborated by {len(spans)} spans"
        return False, (
            f"confidence {confidence:.2f} is mid-band and only {len(spans)} "
            "span(s) support it"
        )
    return False, f"confidence {confidence:.2f} is below {MIN_ARCHETYPE_CONFIDENCE}"


class ExtractionError(RuntimeError):
    """No model could read the description."""


# ── the wire schema ──────────────────────────────────────────────────
# Deliberately a mirror of Constraints, not a superset. Every field the
# model may return is one the decision layer already knows how to
# consume; there is nowhere for it to put a service name even if it
# wanted to.

Source = Literal["stated", "assumed"]


class Field_(BaseModel):
    """One extracted value, with where it came from."""

    value: str = Field(description="The value. Numbers as digits, booleans as true/false.")
    source: Source = Field(description="'stated' if the text says it, else 'assumed'")
    span: str = Field(
        default="",
        description="The exact substring of the input this was drawn from. "
                    "Empty when source is 'assumed'.",
    )


class ArchetypeCall(BaseModel):
    archetype: str = Field(description=f"One of: {', '.join(ARCHETYPES)}, or unknown")
    confidence: float = Field(description="0.0 to 1.0")
    spans: list[str] = Field(
        default_factory=list,
        description="Distinct substrings of the input supporting this archetype.",
    )


class Extraction(BaseModel):
    country: Field_
    sector: Field_
    availability: Field_
    durability: Field_
    users: Field_
    requests_per_day: Field_
    peak_shape: Field_
    budget_monthly_usd: Field_
    storage_gb: Field_
    egress_gb: Field_
    public_facing: Field_
    country_lock: Field_
    archetype: ArchetypeCall


_INSTRUCTION = f"""You read a description of a software workload and return
structured constraints. You do not design architectures, name cloud services,
name regulations, or estimate prices — another system does all of that from
what you return. Return only what the text supports.

For every field return: value, source, and span.
  source = "stated"  the text says it, directly or by clear implication
  source = "assumed" the text does not say it; you are returning a default
  span   = the exact substring you drew it from, or "" when assumed

Fields:
  country            ISO-2 code inferred from any place named (Pune -> IN).
                     "" if no place is named.
  sector             one of: healthcare, fintech, ecommerce, education,
                     internal_tools, public_web, other
  availability       "high" if being offline would be a serious problem
                     (uptime promises, "cannot go down", named business hours
                     that must hold). "low" if the text says downtime is
                     tolerable. Assume "low" only when the text is silent.
                     Beware: "busiest during business hours" describes TRAFFIC
                     TIMING, not an uptime requirement.
  durability         "high" if losing the data would be serious or it is
                     regulated. "ephemeral" ONLY if the text explicitly says
                     the data is disposable or can be regenerated. Otherwise
                     "normal". Note: tolerance for DOWNTIME says nothing about
                     tolerance for DATA LOSS — do not infer one from the other.
  users              integer count of people using it. 0 if not stated.
                     Interpret "12-person team" as 12, "100,000 users" as 100000.
  requests_per_day   integer. Convert whatever unit the text uses into requests
                     per DAY: "2 million requests a day" -> 2000000,
                     "80,000 applications a month" -> 2667,
                     "50 predictions a second" -> 4320000,
                     "30,000 visitors a month" -> 1000.
                     0 only if the text gives no volume at all.
  peak_shape         one of: flat, morning, evening, spiky
  budget_monthly_usd number, monthly. 0 if not stated.
  storage_gb         number. 0 if not stated.
  egress_gb          number. 0 if not stated.
  public_facing      true if end consumers/the public use it directly over the
                     internet; false if only staff on known sites do. A system
                     that HOLDS data about the public is not necessarily USED
                     by them.
  country_lock       true only if the text requires data to stay in a country
                     (a residency phrase, or a named national regulator).
                     Merely naming a city is NOT a country lock.

archetype: classify the SHAPE of the workload.
  web_app       request-serving application with a database behind it
  static_site   files served to visitors, no app server, no database
  batch_etl     scheduled work, idle between runs
  event_driven  reacting to external events (webhooks, queues, uploads)
  ml_inference  serving predictions from a trained model
  realtime      persistent connections (chat, live feeds)
  migration     moving EXISTING servers/VMs to the cloud as they are
  unknown       genuinely underdetermined

  Return confidence 0.0-1.0 and the distinct substrings supporting it.
  Return "unknown" with low confidence when the description does not say
  enough to tell these apart. A vague request to "move to the cloud" with no
  statement of WHAT is being moved is unknown, not migration.

Description:
"""


# ── result ───────────────────────────────────────────────────────────


@dataclass
class ExtractionMeta:
    """How the Constraints were obtained, so the output can say so."""

    reader: str = ""
    model: str = ""
    #: True when the phrase-table fallback produced this, because no model
    #: could be reached or none returned a valid response.
    degraded: bool = False
    degraded_reason: str = ""
    cached: bool = False
    archetype: str = UNKNOWN
    archetype_confidence: float = 0.0
    archetype_spans: list[str] = field(default_factory=list)
    #: Why the classification was believed or refused, in words.
    evidence_verdict: str = ""
    #: True when a provider OTHER than the pinned primary answered.
    #: Different models produce different Constraints, so a plan read by
    #: a failover provider is not strictly comparable to one read by the
    #: primary -- and the agreement figures quoted in the report are
    #: primary-to-primary. Surfaced for the same reason DEGRADED is.
    failover: bool = False
    failover_note: str = ""
    #: field name -> the input substring it was read from.
    spans: dict[str, str] = field(default_factory=dict)


def cache_key(description: str) -> str:
    parts = "|".join([description.strip(), _MODEL, SCHEMA_VERSION])
    return hashlib.sha256(parts.encode()).hexdigest()


# ── coercion ─────────────────────────────────────────────────────────
# The model returns strings; Constraints wants typed values. Every
# conversion here fails soft to the field's default rather than raising:
# one unparseable field must not discard an otherwise good extraction.


def _as_int(raw: str) -> int:
    try:
        return int(float(str(raw).replace(",", "").strip() or 0))
    except (TypeError, ValueError):
        return 0


def _as_float(raw: str) -> float:
    try:
        return float(str(raw).replace(",", "").replace("$", "").strip() or 0)
    except (TypeError, ValueError):
        return 0.0


def _as_bool(raw: str) -> bool:
    return str(raw).strip().lower() in ("true", "yes", "1")


_ENUMS: dict[str, tuple[str, ...]] = {
    "sector": ("healthcare", "fintech", "ecommerce", "education",
               "internal_tools", "public_web", "other"),
    "availability": ("low", "high"),
    "durability": ("normal", "high", "ephemeral"),
    "peak_shape": ("flat", "morning", "evening", "spiky"),
}


def _to_constraints(payload: Extraction) -> tuple[Constraints, ExtractionMeta]:
    """The wire shape, validated into the object the decision layer takes.

    Validation is OURS, not the model's: structured output guarantees the
    shape, this guarantees the values. A hallucinated sector fails here
    and falls back to its default rather than reaching the engine.
    """
    c = Constraints()
    meta = ExtractionMeta()

    for name in REQUIRED + ("country_lock",):
        entry: Field_ = getattr(payload, name)
        raw = entry.value

        if name in _ENUMS:
            value = str(raw).strip().lower()
            if value not in _ENUMS[name]:
                continue  # keep the dataclass default, and leave it 'assumed'
        elif name in ("users", "requests_per_day"):
            value = _as_int(raw)
        elif name in ("budget_monthly_usd", "storage_gb", "egress_gb"):
            value = _as_float(raw)
        elif name in ("public_facing", "country_lock"):
            value = _as_bool(raw)
        else:  # country
            value = str(raw).strip().upper()[:2]

        setattr(c, name, value)
        if entry.source == "stated":
            c.stated.add(name)
            c.evidence[name] = entry.span or "(stated, no span given)"
            if entry.span:
                meta.spans[name] = entry.span

    # country_lock is not a REQUIRED field -- it has no stated/assumed
    # accounting of its own -- so drop it back out of the stated set.
    c.stated.discard("country_lock")

    call = payload.archetype
    name = (call.archetype or "").strip().lower()
    distinct_spans = [s for s in dict.fromkeys(call.spans) if s.strip()]
    confidence = float(call.confidence or 0.0)

    if name not in ARCHETYPES:
        meta.archetype = UNKNOWN
        meta.evidence_verdict = f"{name!r} is not an archetype this engine knows"
    else:
        ok, why = passes_evidence_bar(confidence, distinct_spans)
        meta.archetype = name if ok else UNKNOWN
        meta.evidence_verdict = why

    meta.archetype_confidence = confidence
    meta.archetype_spans = distinct_spans

    return c, meta


# ── the call ─────────────────────────────────────────────────────────


def _gemini(description: str, key: str) -> Extraction:
    from google import genai

    client = genai.Client(api_key=key)
    result = client.models.generate_content(
        model=_MODELS["gemini"],
        contents=_INSTRUCTION + description,
        config={
            "response_mime_type": "application/json",
            "response_schema": Extraction,
            # Sampling is the difference between a tool and a slot machine.
            "temperature": 0.0,
        },
    )
    return Extraction.model_validate_json(result.text)


def _anthropic(description: str, key: str) -> Extraction:
    import anthropic

    client = anthropic.Anthropic(api_key=key)
    schema = Extraction.model_json_schema()
    message = client.messages.create(
        model=_MODELS["anthropic"],
        max_tokens=2048,
        temperature=0,
        tools=[{
            "name": "return_constraints",
            "description": "Return the extracted constraints.",
            "input_schema": schema,
        }],
        tool_choice={"type": "tool", "name": "return_constraints"},
        messages=[{"role": "user", "content": _INSTRUCTION + description}],
    )
    for block in message.content:
        if block.type == "tool_use":
            return Extraction.model_validate(block.input)
    raise ExtractionError("anthropic returned no tool_use block")


#: Groq serves an OpenAI-compatible API, so one function covers it. Kept
#: in the chain because it is the only free tier here with quota left --
#: the Gemini keys are exhausted and the Anthropic ones are out of
#: credit, and an extractor with no reachable model is an extractor that
#: silently degrades to the phrase tables it was built to replace.
def _groq(description: str, key: str) -> Extraction:
    from openai import OpenAI

    client = OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")
    completion = client.chat.completions.create(
        model=_MODELS["groq"],
        temperature=0,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "extraction",
                "schema": Extraction.model_json_schema(),
                "strict": False,
            },
        },
        messages=[{"role": "user", "content": _INSTRUCTION + description}],
    )
    return Extraction.model_validate_json(completion.choices[0].message.content)


_READERS = {"gemini": _gemini, "groq": _groq, "anthropic": _anthropic}


def _call_with_failover(description: str) -> tuple[Extraction, str]:
    """Try every configured key until one answers.

    WHICHCLOUD_EXTRACT_PROVIDER moves one provider to the front. Worth
    having because the chain's default order is by cost, not by
    availability: when the free Gemini keys are quota-exhausted every
    call still pays ~25s discovering that before reaching a key that
    works, which turns a 125-call measurement into an hour of timeouts.
    """
    preferred = os.getenv("WHICHCLOUD_EXTRACT_PROVIDER") or PRIMARY_PROVIDER
    chain = [c for c in candidates(preferred) if c.provider in _READERS]
    if not chain:
        raise ExtractionError("no model credentials configured")

    failures: list[tuple[str, Exception]] = []
    for candidate in chain:
        try:
            return _READERS[candidate.provider](description, candidate.key), candidate.label
        except Exception as exc:  # noqa: BLE001 -- any failure tries the next key
            failures.append((candidate.label, exc))

    if failures and all(is_exhausted(exc) for _, exc in failures):
        raise ExtractionError(
            "every configured model is out of capacity: "
            + ", ".join(label for label, _ in failures)
        )
    label, exc = failures[0]
    raise ExtractionError(f"{label}: {str(exc)[:200]}") from exc


class NotInCacheError(RuntimeError):
    """Offline mode, and this prompt has never been extracted."""


def extract(
    description: str,
    *,
    use_cache: bool = True,
    allow_fallback: bool = True,
    dsn: str | None = None,
) -> tuple[Constraints, ExtractionMeta]:
    """Read a description into Constraints, with the phrase tables as a net.

    Never raises for a model failure when allow_fallback is on: a degraded
    answer that says it is degraded beats no answer, and the phrase tables
    still handle the phrasings they always did.

    WHICHCLOUD_OFFLINE serves cache only and raises NotInCacheError for
    anything missing. That is deliberately NOT the phrase-table fallback:
    for a live demonstration, a clear "this prompt was not warmed" is a
    recoverable mistake, whereas a silent 85%-miss reader producing a
    confident-looking wrong answer on stage is not.
    """
    offline = bool(os.getenv("WHICHCLOUD_OFFLINE"))

    if os.getenv("WHICHCLOUD_DISABLE_LLM") and not offline:
        return _fallback(description, "LLM extraction disabled by environment")

    key = cache_key(description)
    if use_cache or offline:
        try:
            stored = store.cached_constraints(key, dsn)
        except Exception:
            stored = None  # a cold cache must never block an extraction
        if stored:
            try:
                payload = Extraction.model_validate_json(stored)
                constraints, meta = _to_constraints(payload)
                meta.cached = True
                meta.model = _MODEL
                meta.reader = f"{PRIMARY_PROVIDER} (cached)"
                return constraints, meta
            except Exception:
                pass  # a stale-shaped row is re-read, not fatal

    if offline:
        raise NotInCacheError(
            "Offline mode: this description has not been extracted before, "
            "so there is no cached reading of it. Run "
            "`python scripts/warm_cache.py --prompt ...` while a model is "
            "reachable, or unset WHICHCLOUD_OFFLINE. Pricing is not "
            "attempted from an unread prompt."
        )

    try:
        payload, label = _call_with_failover(description)
    except Exception as exc:  # noqa: BLE001
        if not allow_fallback:
            raise
        return _fallback(description, str(exc)[:200])

    constraints, meta = _to_constraints(payload)
    meta.reader, meta.model = label, _MODEL
    # `label` is "groq", "groq#2", "gemini"... -- the provider is the part
    # before the '#', since a second key for the primary is still primary.
    provider = label.split("#", 1)[0]
    if provider != PRIMARY_PROVIDER:
        meta.failover = True
        meta.model = _MODELS.get(provider, provider)
        meta.failover_note = (
            f"Extracted by failover provider {provider!r} "
            f"({meta.model}), not the pinned primary "
            f"{PRIMARY_PROVIDER!r} ({PRIMARY_MODEL}). Different models read "
            "the same prompt differently, so this plan is not strictly "
            "comparable to one read by the primary, and the published "
            "agreement figures do not cover it."
        )

    if use_cache:
        try:
            store.cache_constraints(
                key, description, label, _MODEL, SCHEMA_VERSION,
                payload.model_dump_json(), dsn,
            )
        except Exception:
            pass  # failing to cache is not failing to extract

    return constraints, meta


def _fallback(description: str, reason: str) -> tuple[Constraints, ExtractionMeta]:
    """The phrase tables, kept precisely for this. Marked DEGRADED so a
    plan built on the weaker reader never passes for a full one -- it
    misses 85% of phrasings, and hiding that would be worse than the
    refusal it produces."""
    from whichcloud.archetype import classify as phrase_classify

    constraints = phrase_extract(description)
    detected, _ = phrase_classify(description)
    return constraints, ExtractionMeta(
        reader="phrase-tables",
        model="none",
        degraded=True,
        degraded_reason=(
            f"Language-model extraction was unavailable ({reason}). Fell back "
            "to phrase matching, which reads far fewer phrasings — treat a "
            "missing constraint here as unread rather than absent."
        ),
        archetype=detected,
        archetype_confidence=0.0,
        spans=dict(constraints.evidence),
    )
