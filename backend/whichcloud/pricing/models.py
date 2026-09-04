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
class PriceTier:
    """One band of a graduated rate: `price_usd` applies from `begin` to `end`.

    Providers publish these as beginRange/endRange on a price dimension.
    `end` of None is the unbounded final band ("Inf" in AWS's feed).

    Graduated, not cliff-edged: a workload past the boundary pays the lower
    rate on the units below it and the higher rate only on the excess, which
    is how AWS actually bills. Treating the top band as applying to every
    unit is the classic way to overstate a bill several-fold.
    """

    begin: Decimal
    end: Decimal | None
    price_usd: Decimal

    def as_dict(self) -> dict:
        return {
            "begin": str(self.begin),
            "end": None if self.end is None else str(self.end),
            "price_usd": str(self.price_usd),
        }

    @classmethod
    def from_dict(cls, data: dict) -> PriceTier:
        end = data.get("end")
        return cls(
            begin=Decimal(str(data["begin"])),
            end=None if end in (None, "", "Inf") else Decimal(str(end)),
            price_usd=Decimal(str(data["price_usd"])),
        )


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

    #: Graduated bands, when the provider publishes them. Empty means the
    #: single flat `price_usd` applies to every unit. `price_usd` always
    #: mirrors the first band's rate, so anything that ignores tiers still
    #: gets the entry rate rather than nothing.
    tiers: tuple[PriceTier, ...] = ()

    @property
    def monthly_usd(self) -> Decimal:
        """Cost of running this continuously for a month."""
        if self.unit == "hour":
            return self.price_usd * HOURS_PER_MONTH
        return self.price_usd

    def cost_for(self, quantity: Decimal | float | int) -> Decimal:
        """What `quantity` units actually cost, honouring graduated bands.

        With no tiers this is the flat rate times the quantity. With tiers
        each band charges only the units that fall inside it, so a free
        allowance (a $0 first band, which is how Cognito's 50,000 MAUs and
        SNS's first million requests are published) is genuinely free and
        only the excess is billed.
        """
        amount = Decimal(str(quantity))
        if not self.tiers:
            return self.price_usd * amount

        total = Decimal(0)
        for tier in sorted(self.tiers, key=lambda t: t.begin):
            if tier.end is not None and amount <= tier.begin:
                break
            upper = amount if tier.end is None else min(amount, tier.end)
            billable = upper - tier.begin
            if billable > 0:
                total += billable * tier.price_usd
        return total

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
    #: Refuse credit-limited ("burstable") families. Set when the projected
    #: sustained load would run the machine above its baseline, and on the
    #: tier whose premise is headroom for an unstated peak -- which is exactly
    #: what CPU credits do not provide. Provider-neutral on purpose: the same
    #: question is asked of all three, answered against each one's own
    #: published baseline, so the comparison never turns on one provider
    #: being quietly given a throttled machine and another a sustained one.
    exclude_burstable: bool = False

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
#
# The other India regions were measured too, and deliberately not added:
#
#   AWS   ap-south-2  Hyderabad   +0.0% vs Mumbai, 490 types against 807
#   GCP   asia-south2 Delhi       +0.0% vs Mumbai, 425 types against 470
#
# Both price every India region identically, so a second one buys no insight
# and costs machine types -- adding them would put choices in the interface
# that cannot change an answer. Azure is the exception, varying up to 37%
# across its three, which is exactly why which Azure region we use is a
# decision worth recording and the others are not.
REGIONS: dict[str, dict[str, str]] = {
    "india": {"aws": "ap-south-1", "azure": "centralindia", "gcp": "asia-south1"},
    # Hyderabad. Carried as its own key so a data-residency requirement can
    # be satisfied WITHOUT leaving India: a cross-region copy needs a second
    # region in the same country, and with only Mumbai ingested the honest
    # answer was that no such copy existed. AWS has published ap-south-2
    # since 2022; the gap was ours, not the country's.
    "india-south": {"aws": "ap-south-2", "azure": "centralindia", "gcp": "asia-south2"},
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


#: CPU baseline for credit-limited ("burstable") instance families, as a
#: fraction of one vCPU sustained. A burstable machine earns credits while it
#: runs below this line and spends them above it; run above it for long enough
#: and it throttles TO the baseline. That makes the family correct for a
#: workload whose sustained demand sits well under the line and wrong for one
#: that does not, which is a question about load, not about price.
#:
#: These come from provider documentation, because no pricing API publishes
#: them -- the rate feeds price a machine, they do not describe how it behaves.
#: They live here, once, so the adapters record them as catalog attributes and
#: the engine reads them as data rather than carrying a table of its own.
_AWS_T_BASELINE = {
    "nano": 0.05, "micro": 0.10, "small": 0.20, "medium": 0.20,
    "large": 0.30, "xlarge": 0.40, "2xlarge": 0.40,
}
#: Azure publishes a baseline per B-series size rather than per suffix.
_AZURE_B_BASELINE = {
    "b1s": 0.10, "b1ms": 0.20, "b2s": 0.40, "b2ms": 0.30, "b4ms": 0.225,
    "b8ms": 0.17, "b12ms": 0.17, "b16ms": 0.17, "b20ms": 0.17,
    "b2ts_v2": 0.20, "b2ls_v2": 0.30, "b2s_v2": 0.40,
    "b4ls_v2": 0.30, "b4s_v2": 0.40, "b8ls_v2": 0.30, "b8s_v2": 0.40,
    "b16ls_v2": 0.30, "b16s_v2": 0.40, "b32ls_v2": 0.30, "b32s_v2": 0.40,
    "b2pts_v2": 0.20, "b2pls_v2": 0.30, "b2ps_v2": 0.40,
    "b4pls_v2": 0.30, "b4ps_v2": 0.40, "b8pls_v2": 0.30, "b8ps_v2": 0.40,
    "b16pls_v2": 0.30, "b16ps_v2": 0.40,
}
#: Google's shared-core machines are the burstable ones; N2, N2D, C2 and the
#: rest deliver their full vCPU continuously and carry no baseline at all.
_GCP_SHARED_CORE_BASELINE = {
    "e2-micro": 0.25, "e2-small": 0.50, "e2-medium": 0.50,
    "f1-micro": 0.20, "g1-small": 0.50,
}


def burstable_baseline(provider: str, sku: str) -> float | None:
    """The sustained CPU fraction this machine is entitled to, or None if it
    is not credit-limited. None means "runs at full vCPU indefinitely"."""
    low = sku.lower().split(":")[0]
    if provider == "aws":
        if not low.startswith(("t2.", "t3.", "t3a.", "t4g.")):
            return None
        return _AWS_T_BASELINE.get(low.split(".", 1)[1] if "." in low else "")
    if provider == "azure":
        return _AZURE_B_BASELINE.get(low.replace("standard_", ""))
    if provider == "gcp":
        return _GCP_SHARED_CORE_BASELINE.get(low)
    return None
