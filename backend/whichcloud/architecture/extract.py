"""Turning a description into an Architecture, with a model doing the reading.

The model's whole job is recognition: which services were named, how they were
said to connect. It never decides that a system *should* have a cache, and it
never sets a price -- the same rule intake follows, for the same reason. A
diagram of what someone described is checkable against their words; a diagram
of what a model thought they meant is not.
"""

import hashlib
import os

from whichcloud.architecture.schema import Architecture
from whichcloud.intake import IntakeError, Provider
from whichcloud.pricing import store

#: Bumped whenever the schema changes shape. It is part of the cache key, so
#: an old extraction made under different rules is never served as if it were
#: made under the current ones.
SCHEMA_VERSION = "1"

_MODEL = "gemini-2.5-flash"

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


def _gemini(description: str, client=None) -> Architecture:
    from google import genai

    if client is None:
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
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


_EXTRACTORS = {"gemini": _gemini}


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

    try:
        arch = _EXTRACTORS[reader](description, client)
    except IntakeError:
        raise
    except Exception as exc:
        # The provider's own errors arrive as library exceptions. Left
        # unhandled they become a 500 with no CORS headers, which a browser
        # reports as "Failed to fetch" -- a network problem, which it is not.
        # A daily quota running out is an ordinary thing that should say so.
        detail = str(exc)
        if "RESOURCE_EXHAUSTED" in detail or "429" in detail:
            raise IntakeError(
                "The model's daily free-tier quota is used up (20 requests a "
                "day). Descriptions read earlier still open instantly from the "
                "cache; new ones need the quota to reset or a billed key."
            ) from exc
        raise IntakeError(f"the reader could not parse that: {detail[:200]}") from exc

    if use_cache:
        try:
            store.cache_architecture(
                key, description, reader, _MODEL, SCHEMA_VERSION,
                arch.model_dump_json(),
            )
        except Exception:
            pass  # failing to cache is not failing to answer

    return arch
