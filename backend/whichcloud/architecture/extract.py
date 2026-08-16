"""Turning a description into an Architecture, with a model doing the reading.

The model's whole job is recognition: which services were named, how they were
said to connect. It never decides that a system *should* have a cache, and it
never sets a price -- the same rule intake follows, for the same reason. A
diagram of what someone described is checkable against their words; a diagram
of what a model thought they meant is not.
"""

import os

from whichcloud.architecture.schema import Architecture
from whichcloud.intake import IntakeError, Provider

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
        model="gemini-2.5-flash",
        contents=_INSTRUCTION + description,
        config={
            "response_mime_type": "application/json",
            "response_schema": Architecture,
        },
    )
    return Architecture.model_validate_json(result.text)


_EXTRACTORS = {"gemini": _gemini}


def extract_architecture(
    description: str,
    reader: Provider = "gemini",
    client=None,
) -> Architecture:
    """Read the architecture a description sets out."""
    if reader not in _EXTRACTORS:
        raise IntakeError(f"no architecture reader for {reader!r}")
    return _EXTRACTORS[reader](description, client)
