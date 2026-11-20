"""Turn a repository scan into a Requirement the pricing engine accepts.

The scan says what services a repository needs. The engine needs that plus
the things no repository can state: how much traffic, how much data, which
region, what budget. This module joins the two, and is built so the join
cannot be made without the second half.

`build_requirement` takes those as required keyword arguments. Not as
optional ones with sensible defaults -- a default here would be a number
nobody chose, flowing into a bill presented as though it had been derived
from the code. Making them required moves "a repository cannot tell you
your traffic" out of the documentation and into the signature, where it
cannot be forgotten.

What the scan does supply is reported back as evidence, so the interface
can show which dependency produced each decision, and `assumed` lists what
had to be defaulted anyway -- the same contract /describe already uses for
the fields its extractor could not read.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..requirements import Requirement
from .repo_scan import Detection, RepoScan, workload_type_hint

__all__ = ["RepoRequirement", "build_requirement", "SIGNAL_TO_FIELD"]


#: scan signal -> the Requirement flag it sets.
#:
#: Only flags, never sizes. A signal says "this workload needs a queue",
#: which is a yes or no the code can answer; it never says how big the
#: queue is, which it cannot.
SIGNAL_TO_FIELD: dict[str, str] = {
    "queue": "needs_queue",
    "search": "needs_search",
    "analytics": "needs_analytics",
    "email": "needs_email",
    "notifications": "needs_notifications",
    "event_streaming": "needs_event_streaming",
    "ai_vision": "ai_vision",
    "ai_language": "ai_language",
    "serverless": "serverless",
}


@dataclass
class RepoRequirement:
    """A Requirement, plus how much of it the repository actually justified."""

    requirement: Requirement
    #: The detections that set a flag, so the interface can say which
    #: dependency is responsible for each service in the architecture.
    evidence: list[Detection]
    #: Fields nothing in the repository spoke to, so they were defaulted or
    #: supplied by the caller. Named so the interface can mark them as
    #: assumptions rather than findings.
    assumed: list[str]


def build_requirement(
    scan: RepoScan,
    *,
    goal: str,
    traffic_scale: str,
    region: str,
    budget_monthly_usd: float | None,
    storage_gb: float,
    egress_gb: float,
    traffic_pattern: str = "unknown",
    high_availability: bool = False,
) -> RepoRequirement:
    """Join a scan with the answers only a person can give.

    Every keyword here before the defaults is something no repository
    states. They are required on purpose: see the module docstring.
    """
    flags: dict[str, bool] = {}
    evidence: list[Detection] = []
    signals = scan.signals()

    for detection in scan.detections:
        field = SIGNAL_TO_FIELD.get(detection.signal)
        if field is not None:
            flags[field] = True
            evidence.append(detection)

    # `ai` is the umbrella the engine prices against; the two specific
    # flags are what the dependency actually proved. Either implies it.
    if signals & {"ai", "ai_vision", "ai_language"}:
        flags["ai"] = True
        evidence.extend(d for d in scan.detections if d.signal == "ai")

    hint = workload_type_hint(scan)
    assumed: list[str] = []
    if hint is None:
        # "mixed" is the engine's own term for "more than one shape, or we
        # could not tell", so it is the honest default -- but it is still
        # recorded as an assumption rather than passed off as a reading.
        assumed.append("workload_type")

    # Everything the caller supplied is an answer, not a finding. The
    # repository had no say in any of it, and the interface should not
    # imply otherwise.
    assumed.extend(
        ["traffic_scale", "region", "storage_gb", "egress_gb", "traffic_pattern"]
    )
    if budget_monthly_usd is None:
        assumed.append("budget_monthly_usd")
    if not scan.datastores:
        # No datastore found is a real reading, but a workload with none is
        # unusual enough that the interface should say so rather than
        # quietly price a stateless design.
        assumed.append("no_datastore_detected")

    requirement = Requirement(
        goal=goal,
        workload_type=hint or "mixed",  # type: ignore[arg-type]
        traffic_pattern=traffic_pattern,  # type: ignore[arg-type]
        traffic_scale=traffic_scale,  # type: ignore[arg-type]
        region=region,
        budget_monthly_usd=budget_monthly_usd,
        storage_gb=storage_gb,
        egress_gb=egress_gb,
        high_availability=high_availability,
        **flags,  # type: ignore[arg-type]
    )
    return RepoRequirement(
        requirement=requirement,
        evidence=sorted(evidence, key=lambda d: (d.signal, d.evidence)),
        assumed=sorted(set(assumed)),
    )
