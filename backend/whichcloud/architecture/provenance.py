"""Did the model TRANSCRIBE an architecture, or DESIGN one?

The distinction decides whether a diagram may be drawn at all, so it is
computed here from the text rather than asked of the model -- a reader
that invented an architecture is exactly the reader least able to report
that it did.

Why it matters. `/architecture` has always had two modes. Transcription
("draw the MSK/Aurora/Lambda stack I just described") is a reading task:
the output is checkable, word by word, against the input. Design ("I have
a marketing site, draw me something") is a *service selection*, and a
service selection made by a language model at request time is the one
thing this engine is built not to do -- it is unpriced, unvalidated,
different on every call, and indistinguishable in the interface from the
deterministic engine's output.

So: transcription stays. Design is refused, and the caller is pointed at
the deterministic planner, which either prices the shape or says why it
cannot.

The test is deliberately generous to transcription. A single service
traceable to the description is enough to call it a reading, because the
failure being guarded is the model inventing an ENTIRE architecture from
a prompt that named nothing -- not a model adding one obvious neighbour
to a stack the user spelled out.
"""

from __future__ import annotations

import re

#: Words that appear in service names without identifying anything. A
#: description saying "storage" must not make "S3 Bucket" look transcribed
#: -- "bucket" and "storage" are what every object store is called, and
#: matching on them would mark every designed architecture as read.
_GENERIC = frozenset({
    "amazon", "aws", "google", "cloud", "azure", "microsoft",
    "service", "services", "instance", "instances", "bucket", "buckets",
    "distribution", "zone", "zones", "hosted", "managed", "gateway",
    "database", "databases", "storage", "server", "servers", "cluster",
    "table", "tables", "function", "functions", "queue", "queues",
    "api", "web", "app", "application", "data", "network", "compute",
    "for", "and", "the", "of", "with", "elastic", "simple", "virtual",
    "private", "public", "standard", "general", "purpose", "engine",
    "windows", "linux",
})

_WORD = re.compile(r"[a-z0-9]+")


def _tokens(name: str) -> set[str]:
    """Identifying words in a service name -- generic ones removed.

    Short tokens are kept when they are alphanumeric mixes ("s3", "ec2",
    "rds"), which are the most identifying names AWS has, and dropped
    when they are bare words ("of", "in") that carry nothing.
    """
    out = set()
    for word in _WORD.findall(name.lower()):
        if word in _GENERIC:
            continue
        if len(word) < 3 and not any(ch.isdigit() for ch in word):
            continue
        out.add(word)
    return out


def traceable_services(architecture, description: str) -> list[str]:
    """The services whose names actually appear in the description."""
    text = description.lower()
    found = []
    for service in architecture.services:
        tokens = _tokens(service.name)
        if tokens and any(re.search(rf"\b{re.escape(t)}", text) for t in tokens):
            found.append(service.name)
    return found


def was_designed(architecture, description: str) -> tuple[bool, str]:
    """True when the model chose the services rather than reading them.

    Returns (designed, evidence) so a refusal can quote its own basis --
    "none of the six services you were shown appear in what you wrote" is
    checkable; "this looks designed" is not.
    """
    services = list(architecture.services)
    if not services:
        return False, "no services returned"

    traced = traceable_services(architecture, description)
    if traced:
        return False, (
            f"{len(traced)} of {len(services)} service(s) named in the "
            f"description ({', '.join(traced[:3])})"
        )
    return True, (
        f"none of the {len(services)} service(s) returned "
        f"({', '.join(s.name for s in services[:3])}) appear in the "
        "description — the model selected them rather than reading them"
    )
