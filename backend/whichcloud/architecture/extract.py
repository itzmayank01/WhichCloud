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
SCHEMA_VERSION = "1"

_MODEL = "gemini-2.5-flash"
GROQ_MODEL = "llama-3.3-70b-versatile"
OPENAI_MODEL = "gpt-4.1-mini"
ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"

_INSTRUCTION = """\
Extract the architecture described below.

Rules:
- Include EVERY cloud service the text names. Do not add services it does not
  name, however obviously they might belong.
- Put VPCs, subnets, regions and availability zones in `boundaries`, not in
  `services`. They contain services; they are not services.
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

    Chat completions with a JSON schema rather than the newer parse helper,
    because Groq implements the older surface and this has to work on each.
    """
    from openai import OpenAI

    client = OpenAI(api_key=key, base_url=base_url)
    result = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "architecture",
                "schema": Architecture.model_json_schema(),
                "strict": False,
            },
        },
        messages=[{"role": "user", "content": _INSTRUCTION + description}],
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
    """Walk the chain until one provider answers.

    Only quota and rate-limit failures move on. Anything else -- a
    description the model cannot parse, a bug here -- fails the same way
    everywhere, and trying all four turns one clear error into four slow ones.
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

    exhausted: list[str] = []
    for candidate in chain:
        extractor = _EXTRACTORS.get(candidate.provider)
        if extractor is None:
            continue
        try:
            return extractor(description, None, candidate.key)
        except Exception as exc:
            if is_exhausted(exc):
                exhausted.append(candidate.label)
                continue
            raise IntakeError(
                f"{candidate.label} could not read that: {str(exc)[:200]}"
            ) from exc

    raise IntakeError(
        "Every configured model is out of quota right now ("
        + ", ".join(exhausted)
        + "). Descriptions read earlier still open instantly from the cache. "
        "Add another key as GEMINI_API_KEY_2 or GROQ_API_KEY to keep going."
    )


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
