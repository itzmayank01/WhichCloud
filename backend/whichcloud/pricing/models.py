"""Normalized price model shared by every provider adapter.

Each provider publishes prices in its own shape. Everything upstream of this
module — the optimization engine, the cost estimator, the comparison view —
only ever sees a PricePoint, so adding a provider never touches the engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

# Cloud providers bill per hour; every published "monthly" figure in the
# industry uses 730 hours (365 * 24 / 12). Keep one definition.
HOURS_PER_MONTH = Decimal(730)


@dataclass(frozen=True, slots=True)
class PricePoint:
    """One priced thing, in one region, from one provider."""

    provider: str  # aws | azure | gcp
    category: str  # compute | database | storage | network
    sku: str  # provider's own identifier, e.g. "t4g.medium"
    name: str  # human-facing label
    region: str  # provider's own region code
    unit: str  # "hour" | "GB-month" | "request"
    price_usd: Decimal

    # Compute-only specs. None for storage/network line items.
    vcpu: int | None = None
    memory_gb: float | None = None
    arch: str | None = None  # "x86_64" | "arm64"

    attributes: dict[str, str] = field(default_factory=dict)

    @property
    def monthly_usd(self) -> Decimal:
        """Cost of running this continuously for a month."""
        if self.unit == "hour":
            return self.price_usd * HOURS_PER_MONTH
        return self.price_usd

    @property
    def is_arm(self) -> bool:
        return self.arch == "arm64"

    def __str__(self) -> str:
        return f"{self.provider}:{self.sku} @ ${self.price_usd}/{self.unit}"


@dataclass(frozen=True, slots=True)
class ComputeQuery:
    """What the engine asks for when it needs a machine.

    Deliberately provider-neutral: the caller says "2 vCPU, 4 GB, in India",
    not "t4g.medium". Translating that into each provider's catalog is the
    adapter's job.
    """

    min_vcpu: int
    min_memory_gb: float
    region: str  # our own region key, e.g. "india"
    arch: str | None = None  # None = any; "arm64" to force ARM

    def matches(self, p: PricePoint) -> bool:
        if p.vcpu is None or p.memory_gb is None:
            return False
        if p.vcpu < self.min_vcpu or p.memory_gb < self.min_memory_gb:
            return False
        if self.arch and p.arch != self.arch:
            return False
        return True


# Our region keys mapped to each provider's code. The engine speaks in these
# neutral keys so a cross-cloud comparison is always apples-to-apples.
# A market, and the region each provider is represented by inside it. These
# are not always the same city, and that is deliberate: the question a reader
# is asking is "what does this cost in India", not "what does this cost in
# Mumbai specifically".
#
# Azure India measured, lowest on-demand meter per SKU:
#
#   centralindia  Pune      1,328 SKUs   cheapest
#   southindia    Chennai   1,014 SKUs   +36.6%
#   westindia     Mumbai      770 SKUs   +23.8%
#
# So Pune is both the cheapest and the best covered, and matching AWS's and
# GCP's Mumbai by moving Azure to westindia would have cost the reader 24% on
# price and 42% of the machine types to make two city names agree. The
# interface names the region each figure comes from instead.
REGIONS: dict[str, dict[str, str]] = {
    "india": {"aws": "ap-south-1", "azure": "centralindia", "gcp": "asia-south1"},
    "us-east": {"aws": "us-east-1", "azure": "eastus", "gcp": "us-east1"},
    "eu-west": {"aws": "eu-west-1", "azure": "westeurope", "gcp": "europe-west1"},
    "singapore": {"aws": "ap-southeast-1", "azure": "southeastasia", "gcp": "asia-southeast1"},
}


def provider_region(region_key: str, provider: str) -> str:
    try:
        return REGIONS[region_key][provider]
    except KeyError:
        raise ValueError(
            f"No {provider} region mapped for '{region_key}'. "
            f"Known regions: {', '.join(sorted(REGIONS))}"
        ) from None
