"""Module 2. Turn a stated volume into a request rate, and gate on it.

Everything expensive hangs off this object. The point is not the
arithmetic -- dividing by 86,400 is not the hard part -- it is that the
gates below read from a derived rate instead of from a budget or a user
count. 450 staff sounds like a lot and 6,000 lookups a day is 0.07
requests a second; only one of those two numbers can size a machine.

What is deliberately kept is the record of what was NOT added. An
architecture that quietly omits a CDN looks identical to one that never
considered it, and the omission is the judgement worth showing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from whichcloud.constraints import Constraints

Tier = Literal["trivial", "small", "medium", "large"]

#: How much busier the peak is than the daily mean, per shape.
MULTIPLIER: dict[str, float] = {
    "flat": 2.0,
    "morning": 10.0,
    "evening": 10.0,
    "spiky": 25.0,
}

#: Rate bands. The names matter more than the numbers: they are what the
#: gates below are written against, so a threshold can move without every
#: caller having to know it did.
BANDS: tuple[tuple[float, Tier], ...] = (
    (10.0, "trivial"),
    (50.0, "small"),
    (500.0, "medium"),
)

_ORDER: dict[Tier, int] = {"trivial": 0, "small": 1, "medium": 2, "large": 3}

_ASYNC_HINTS = (
    "async", "asynchronous", "batch", "queue", "background job", "long job",
    "long-running", "overnight", "scheduled job", "worker", "defer",
)
_READ_HEAVY_HINTS = (
    "lookup", "search", "browse", "report", "dashboard", "read-heavy",
    "mostly read", "catalogue", "catalog", "view", "marketplace",
    "storefront", "product listing", "product page",
)
_STATIC_ASSET_HINTS = (
    "video", "image", "photo", "media", "download", "static asset",
    "scan", "large file", "attachment", "pdf",
)
#: Multi-word on purpose: a bare "report" matches "lab report", which is a
#: noun in the data, not a workload description -- the phrase that earns a
#: replica below medium tier has to name the workload, not the data.
_REPORTING_HINTS = (
    "reporting workload", "reporting system", "analytics dashboard",
    "business intelligence", "bi tool", "bi dashboard", "data warehouse",
)
_INTERNATIONAL_HINTS = (
    "international users", "global users", "customers abroad",
    "users overseas", "multiple countries", "worldwide", "across regions",
    "users outside the country", "users in other countries",
)


@dataclass
class Load:
    """The derived rate, and what it justified adding or leaving out."""

    avg_rps: float
    peak_rps: float
    tier: Tier
    peak_shape: str
    multiplier: float
    included: list[str] = field(default_factory=list)
    excluded_with_reason: list[str] = field(default_factory=list)

    def at_least(self, tier: Tier) -> bool:
        return _ORDER[self.tier] >= _ORDER[tier]

    def sizing_basis(self) -> dict:
        return {
            "avg_rps": round(self.avg_rps, 4),
            "peak_rps": round(self.peak_rps, 4),
            "tier": self.tier,
            "load_tier": self.tier,
            "sized_from": (
                f"{self.peak_rps:.2f} req/sec peak "
                f"({self.peak_shape} shape, x{self.multiplier:g} the "
                f"{self.avg_rps:.2f} req/sec average). Compute and database "
                "are sized from this figure; neither the user count nor the "
                "budget is an input to sizing."
            ),
        }


def _band(peak_rps: float) -> Tier:
    for ceiling, name in BANDS:
        if peak_rps < ceiling:
            return name
    return "large"


def build_load(constraints: Constraints, description: str = "") -> Load:
    """Derive the rate, then decide what the rate does and does not justify."""
    text = description.lower()
    avg = constraints.requests_per_day / 86_400 if constraints.requests_per_day else 0.0
    multiplier = MULTIPLIER[constraints.peak_shape]
    peak = avg * multiplier
    load = Load(
        avg_rps=avg,
        peak_rps=peak,
        tier=_band(peak),
        peak_shape=constraints.peak_shape,
        multiplier=multiplier,
    )

    rate = f"{peak:.2f} peak req/sec"
    audience = "public-facing" if constraints.public_facing else "staff-only access"
    # DEFECT 1. Read the extracted CONSTRAINT, not the raw text. The
    # phrase table is kept as a fallback for the degraded path only:
    # under LLM extraction `static_assets` is a real field, and matching
    # "video" in prose was both redundant and, on any prompt the table
    # missed, silently wrong.
    heavy_assets = constraints.static_assets in ("light", "heavy") or (
        constraints.static_assets == "none"
        and any(h in text for h in _STATIC_ASSET_HINTS)
    )
    international = any(h in text for h in _INTERNATIONAL_HINTS)
    read_heavy = any(h in text for h in _READ_HEAVY_HINTS)
    reporting = any(h in text for h in _REPORTING_HINTS)
    # Same reasoning as static assets: the extracted field first, the
    # phrase table only where extraction said nothing.
    asynchronous = constraints.async_processing or any(
        h in text for h in _ASYNC_HINTS
    )

    # ── CDN ──
    if constraints.public_facing and (heavy_assets or international):
        load.included.append("network")
    else:
        why = []
        if not constraints.public_facing:
            why.append(audience)
        if not heavy_assets and not international:
            why.append("no large static assets and no users outside the "
                        "home country described")
        load.excluded_with_reason.append(
            f"CloudFront (CDN): not added, {rate} and {', '.join(why)}"
        )

    # ── WAF ──
    if constraints.public_facing:
        load.included.append("waf")
    else:
        load.excluded_with_reason.append(
            f"AWS WAF: not added, {audience} — reachable only from known "
            "networks, so security groups plus an IP allowlist are the "
            "control that fits; a firewall in front of an internal system "
            "filters traffic that never arrives"
        )

    # ── cache ──
    if load.at_least("medium") and read_heavy:
        load.included.append("cache")
    else:
        why = (
            f"{rate} does not repeat reads often enough to pay for itself"
            if not load.at_least("medium")
            else "workload is not described as read-heavy"
        )
        load.excluded_with_reason.append(f"ElastiCache: not added, {why}")

    # ── read replica ──
    # Reporting/BI/analytics is a distinct, multi-word signal -- a bare
    # "report" matches "lab report" (a noun in the data), which is exactly
    # the false positive that would have added a replica to a hospital
    # records lookup that never asked for one.
    if load.at_least("medium") or reporting:
        load.included.append("database_replica")
    else:
        load.excluded_with_reason.append(
            f"Read replica: not added, {rate} is served by the primary; a "
            "replica adds cost and a second thing to fail over"
        )

    # ── queue ──
    if asynchronous:
        load.included.append("streaming")
    else:
        load.excluded_with_reason.append(
            "Message queue: not added, nothing in the description is "
            "asynchronous, batched or long-running"
        )

    return load
