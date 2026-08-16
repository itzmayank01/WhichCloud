"""Turning a description into an Architecture, with a model doing the reading.

The model's whole job is recognition: which services were named, how they were
said to connect. It never decides that a system *should* have a cache, and it
never sets a price -- the same rule intake follows, for the same reason. A
diagram of what someone described is checkable against their words; a diagram
of what a model thought they meant is not.
"""

import hashlib
import os

from whichcloud.architecture.readers import candidates, configured, is_exhausted
from whichcloud.architecture.schema import Architecture
from whichcloud.intake import IntakeError, Provider
from whichcloud.pricing import store

#: Bumped whenever the schema changes shape. It is part of the cache key, so
#: an old extraction made under different rules is never served as if it were
#: made under the current ones.
SCHEMA_VERSION = "3"   # 3: functional components

#: The rolling alias, not a pinned version. A pinned one ages out: keys made
#: today cannot call gemini-2.5-flash at all -- Google returns "no longer
#: available to new users" -- so a version that works for the oldest key in
#: the chain 404s for the newest. The alias is whatever is current for each
#: key, which is the only thing true of all of them.
_MODEL = "gemini-flash-latest"
GROQ_MODEL = "llama-3.3-70b-versatile"
OPENAI_MODEL = "gpt-4.1-mini"
ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"

_INSTRUCTION = """\
Extract the architecture described below.

Rules:
- Include EVERY cloud service the text names. Do not add services it does not
  name, however obviously they might belong.
- Connect them. Every service should name what it talks to in `connects_to`,
  following the request and data flow these services have when used together,
  even where the text lists them without saying how they join up. A named
  service that connects to nothing is almost always wrong -- an architecture
  is its connections, and a page of unlinked boxes is an inventory.
  Adding a service that was not named changes what someone described; drawing
  the relationship between two they did name does not.
- Put VPCs, subnets, regions and availability zones in `boundaries`, not in
  `services`. They contain services; they are not services.
- Group services into functional `component`s, the way AWS's own reference
  architectures do: "Web UI", "Data", "Search", "Cost reporting", "Image
  deployment". Services that cooperate to do one job share a component. Aim
  for three to seven components, each holding two to six services; a component
  per service is not a grouping, and one component holding everything is not
  either.
- Put non-cloud tools such as GitHub Actions or third-party gateways in
  `external`.
- `regions` and `azs_per_region` are numbers. "three regions" is 3.
- `flow` must be exactly one of: sync, async, replication, control.
- `connects_to` must use names exactly as they appear in `name`.

Description:
"""


def _gemini(description: str, client=None, key: str | None = None) -> Architecture:
    from google import genai

    if client is None:
        key = key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise IntakeError("GEMINI_API_KEY is not set.")
        client = genai.Client(api_key=key)

    result = client.models.generate_content(
        model=_MODEL,
        contents=_INSTRUCTION + description,
        config={
            "response_mime_type": "application/json",
            "response_schema": Architecture,
            # Sampling is the difference between a tool and a slot machine.
            # Measured over three runs of one description: at the default
            # temperature the service list came back as 22, then 21, then 23,
            # agreeing on only 20 of the 24 names ever mentioned. At zero it
            # returned the same 22 services, 13 boundaries and 3 regions every
            # time. A user who re-reads their own architecture must not be
            # shown a different system.
            "temperature": 0.0,
        },
    )
    return Architecture.model_validate_json(result.text)


def _openai_compatible(
    description: str, key: str, base_url: str | None, model: str
) -> Architecture:
    """Groq and OpenAI both speak this, so one function serves both.

    Structured output is requested two ways because providers differ on which
    they implement, and the difference is not discoverable in advance: Groq's
    Llama models reject `json_schema` outright and want `json_object` with the
    shape described in the prompt instead. Rather than hardcode which provider
    gets which -- a table that goes stale every time a model is added -- the
    stricter form is tried first and the looser one used if it is refused.
    """
    import json

    from openai import OpenAI

    client = OpenAI(api_key=key, base_url=base_url)
    schema = Architecture.model_json_schema()
    prompt = _INSTRUCTION + description

    try:
        result = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "architecture",
                    "schema": schema,
                    "strict": False,
                },
            },
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        if "json_schema" not in str(exc):
            raise
        result = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"{prompt}\n\nReturn JSON matching this schema "
                        f"exactly:\n{json.dumps(schema)}"
                    ),
                }
            ],
        )

    return Architecture.model_validate_json(result.choices[0].message.content or "{}")


def _groq(description: str, client=None, key: str | None = None) -> Architecture:
    key = key or os.getenv("GROQ_API_KEY", "")
    if not key:
        raise IntakeError("GROQ_API_KEY is not set.")
    return _openai_compatible(
        description, key, "https://api.groq.com/openai/v1", GROQ_MODEL
    )


def _openai(description: str, client=None, key: str | None = None) -> Architecture:
    key = key or os.getenv("OPENAI_API_KEY", "")
    if not key:
        raise IntakeError("OPENAI_API_KEY is not set.")
    return _openai_compatible(description, key, None, OPENAI_MODEL)


def _anthropic(description: str, client=None, key: str | None = None) -> Architecture:
    import anthropic

    key = key or os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        raise IntakeError("ANTHROPIC_API_KEY is not set.")

    result = anthropic.Anthropic(api_key=key).messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=8192,
        temperature=0,
        tools=[
            {
                "name": "architecture",
                "description": "The architecture the description sets out",
                "input_schema": Architecture.model_json_schema(),
            }
        ],
        tool_choice={"type": "tool", "name": "architecture"},
        messages=[{"role": "user", "content": _INSTRUCTION + description}],
    )
    for block in result.content:
        if block.type == "tool_use":
            return Architecture.model_validate(block.input)
    raise IntakeError("the model returned no architecture")


_EXTRACTORS = {
    "gemini": _gemini,
    "groq": _groq,
    "openai": _openai,
    "anthropic": _anthropic,
}


def _read_with_failover(description: str, reader: Provider | None, client=None):
    """Try every configured key until one answers.

    An earlier version only moved on for failures matching a list of known
    phrases -- quota, rate limit, credit balance. That list was wrong three
    times running: a key that could not call the model returned 404 "no longer
    available to new users", and a busy model returned 503 "experiencing high
    demand". Each time one key stopped all ten, and each time the fix was to
    add another phrase and wait to be surprised again.

    So the rule is inverted. Any failure moves to the next candidate, because
    a second key costs a second or two and the alternative is telling someone
    their description failed when a working key was sitting unused. Errors are
    still classified, but only to write a useful message once everything has
    been tried.
    """
    if client is not None:                       # an injected client is the test's
        return _EXTRACTORS[reader or "gemini"](description, client)

    chain = candidates(reader)
    if not chain:
        raise IntakeError(
            "No model credentials found. Set GEMINI_API_KEY or GROQ_API_KEY "
            "in the environment; extra keys can be added as GEMINI_API_KEY_2 "
            "and so on, and are used when the first is exhausted."
        )

    failures: list[tuple[str, Exception]] = []
    for candidate in chain:
        extractor = _EXTRACTORS.get(candidate.provider)
        if extractor is None:
            continue
        try:
            return extractor(description, None, candidate.key)
        except Exception as exc:
            failures.append((candidate.label, exc))

    # Everything failed. If it was all capacity, say so plainly -- that is a
    # wait, not a bug. Otherwise surface the first real error, which is the
    # one most likely to describe the actual problem.
    if all(is_exhausted(exc) for _, exc in failures):
        raise IntakeError(
            "Every configured model is out of capacity right now ("
            + ", ".join(label for label, _ in failures)
            + "). Descriptions read earlier still open instantly from the "
            "cache. Add another key as GEMINI_API_KEY_2 or GROQ_API_KEY."
        )

    label, exc = next((f for f in failures if not is_exhausted(f[1])), failures[0])
    raise IntakeError(
        f"No configured model could read that. {label} said: {str(exc)[:250]}"
    ) from exc


def cache_key(description: str, reader: str) -> str:
    """What makes two requests the same request."""
    parts = "|".join([description.strip(), reader, _MODEL, SCHEMA_VERSION])
    return hashlib.sha256(parts.encode()).hexdigest()


def extract_architecture(
    description: str,
    reader: Provider = "gemini",
    client=None,
    *,
    use_cache: bool = True,
    refresh: bool = False,
) -> Architecture:
    """Read the architecture a description sets out.

    The first answer for a description is kept and reused. Not for speed --
    though it is faster and cheaper -- but because a model asked the same
    question twice does not reliably answer the same way. Measured over three
    runs of one description at temperature 0, this returned 23, 22 and 23
    nodes with 48, 32 and 48 edges. Greedy decoding is not reproducible
    serving, and no provider promises otherwise.

    A user reopening their own saved architecture has to see the system they
    saw before, or nothing built on top of it can be trusted to mean anything.

    Pass refresh=True to deliberately re-read; use_cache=False for tests that
    must not touch the database.
    """
    if reader not in _EXTRACTORS:
        raise IntakeError(f"no architecture reader for {reader!r}")

    key = cache_key(description, reader)

    if use_cache and not refresh:
        try:
            stored = store.cached_architecture(key)
        except Exception:
            stored = None  # a cold cache must never block an extraction
        if stored:
            return Architecture.model_validate_json(stored)

    arch = _read_with_failover(description, reader, client)

    if use_cache:
        try:
            store.cache_architecture(
                key, description, reader, _MODEL, SCHEMA_VERSION,
                arch.model_dump_json(),
            )
        except Exception:
            pass  # failing to cache is not failing to answer

    return arch
