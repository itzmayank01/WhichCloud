"""The architecture planner: constraints in, a machine-readable spec out.

This module answers "what should be built", never "what does it cost". The
catalog prices whatever it emits, which is why the one inviolable rule here
is that every component named must exist in the catalog. A planner that
invents a component produces a spec nothing can price, and an unpriceable
spec is worse than a missing one: it looks complete.

The separation matters for a second reason. Sizing derived from a budget
converges on spending the budget. Sizing derived from a request rate
converges on what the traffic needs, and leaving money unspent becomes a
correct answer rather than an oversight.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

from whichcloud.requirements import Requirement

Provenance = Literal["stated", "assumed"]
PeakShape = Literal["flat", "morning", "evening", "spiky"]
Sector = Literal["healthcare", "fintech", "ecommerce", "internal", "other"]

#: How much busier the peak is than the daily mean, per shape.
#:
#: "morning = 10x average over a 2-hour window" is given. The rest follow
#: the same reasoning: a day's traffic compressed into a narrower window is
#: a taller peak. Flat is not 1.0 because no real traffic is flat -- it is
#: the mildest shape, not the absence of one.
#:
#: HEURISTIC, and the one number here that is. The arithmetic around it is
#: not: average is division, and peak is average times this.
PEAK_MULTIPLIER: dict[str, float] = {
    "flat": 2.0,
    "morning": 10.0,
    "evening": 10.0,
    "spiky": 20.0,
}

#: Below this, a CDN, a cache, a read replica and a queue each add cost and
#: operational surface without changing the outcome. They are added only
#: when something stated forces them, never because the tier is the
#: expensive one.
SCALE_FLOOR_RPS = 50.0

#: Requests one vCPU serves at peak before latency degrades. HEURISTIC.
RPS_PER_VCPU = 40.0

#: Regions available per country, from the catalog. A region_lock is only
#: satisfiable within this set.
IN_COUNTRY: dict[str, tuple[str, ...]] = {
    # Mumbai and Hyderabad. Both, because a data-residency requirement and
    # a cross-region copy are only in conflict if the country has one
    # region -- and India does not. An earlier version of this map listed
    # only Mumbai and reported the two requirements as unsatisfiable, which
    # was a statement about our catalog coverage dressed up as geography.
    "india": ("ap-south-1", "ap-south-2"),
    "singapore": ("ap-southeast-1",),
    "ireland": ("eu-west-1",),
    "united states": ("us-east-1",),
}


@dataclass
class Constraint:
    """One extracted field and whether it was read or inferred."""

    value: object
    provenance: Provenance
    question: str = ""

    @property
    def stated(self) -> bool:
        return self.provenance == "stated"


@dataclass
class Rates:
    """Step 2. The derived figures everything downstream is sized from."""

    requests_per_day: int
    average_rps: float
    peak_rps: float
    peak_shape: PeakShape
    multiplier: float

    @property
    def below_scale_floor(self) -> bool:
        return self.peak_rps < SCALE_FLOOR_RPS

    def as_text(self) -> str:
        return (
            f"{self.requests_per_day:,} requests/day = "
            f"{self.average_rps:.2f} req/sec average; "
            f"{self.peak_shape} shape x{self.multiplier:g} = "
            f"{self.peak_rps:.2f} req/sec peak. "
            "Compute and database sized from the peak."
        )


@dataclass
class Tier:
    """Step 6. One costable design."""

    name: str
    components: list[dict] = field(default_factory=list)
    rto: str = ""
    rpo: str = ""
    gives_up: list[str] = field(default_factory=list)
    justifications: dict[str, str] = field(default_factory=dict)
    over_budget: bool = False


@dataclass
class Plan:
    """Step 7. Emitted once for the whole answer."""

    tiers: list[Tier] = field(default_factory=list)
    assumed_fields: dict[str, str] = field(default_factory=dict)
    compliance_notes: list[str] = field(default_factory=list)
    sizing_basis: str = ""
    unsatisfiable: list[str] = field(default_factory=list)
    budget_note: str = ""


def derive_rates(requests_per_day: int, peak_shape: PeakShape) -> Rates:
    """Step 2. Average and peak request rate, from volume alone.

    Not from the user count, which says nothing about how often each user
    acts, and not from the budget, which says nothing about anything.
    """
    multiplier = PEAK_MULTIPLIER[peak_shape]
    average = requests_per_day / 86_400
    return Rates(
        requests_per_day=requests_per_day,
        average_rps=average,
        peak_rps=average * multiplier,
        peak_shape=peak_shape,
        multiplier=multiplier,
    )


def instances_for(peak_rps: float, *, high_availability: bool) -> int:
    """How many compute instances the peak needs, floored by availability.

    The floor is the point of the availability filter: two instances across
    two zones is not a sizing outcome, it is a hard requirement that sizing
    may exceed but never undercut.
    """
    needed = max(1, math.ceil(peak_rps / RPS_PER_VCPU))
    return max(needed, 2) if high_availability else needed


def in_country_regions(region_lock: str) -> tuple[str, ...]:
    """Regions inside the locked country, from the catalog's coverage."""
    return IN_COUNTRY.get(region_lock.strip().lower(), ())


#: Every category the catalog can price. A component outside this set
#: cannot be emitted, however sensible it would be to build.
CATALOG = {
    "compute", "database", "db_storage", "storage", "storage_lifecycle",
    "loadbalancer", "lcu", "nat", "endpoint", "network", "cache",
    "backup", "backup_copy", "governance", "monitoring", "audit", "tracing",
    "flowlogs", "kms", "secrets", "tls", "dns", "auth", "threat", "posture",
    "waf", "streaming", "kafka", "search", "search_storage", "warehouse",
    "fargate",
}


def _c(category: str, quantity: float = 1, size: str = "", note: str = "") -> dict:
    """One catalog component. Refuses anything the catalog cannot price."""
    if category not in CATALOG:
        raise ValueError(
            f"{category!r} is not in the catalog; the planner may not emit it"
        )
    entry = {"category": category, "quantity": quantity}
    if size:
        entry["size"] = size
    if note:
        entry["note"] = note
    return entry


def _baseline(rates: Rates, instances: int, *, high_availability: bool) -> list[dict]:
    """What every tier carries, sized from the peak rate.

    The observability and key-management components are here rather than in
    a higher tier because they are how an incident is diagnosed at all --
    and because they are cheap enough that omitting them saves little and
    costs the ability to answer "what happened".
    """
    # Spot capacity is DISQUALIFIED by availability=high, not merely
    # discouraged. Cheapest-first pricing picks t4g.nano:spot for a
    # workload like this -- $1.61/month against $16.35 on-demand -- and
    # spot is reclaimed on two minutes' notice. For a system whose
    # downtime during clinic hours is unacceptable, the cheaper number is
    # the wrong answer, not a trade-off worth surfacing.
    purchase = "on-demand" if high_availability else "any"

    components = [
        _c("compute", instances,
           note=f"sized for {rates.peak_rps:.2f} req/sec peak; {purchase}"),
        _c("database", 1),
        _c("db_storage", 1),
        _c("storage", 1),
        _c("monitoring", 1),
        _c("audit", 1),
        _c("kms", 1),
        _c("tls", 1),
        _c("dns", 1),
        _c("flowlogs", 1),
    ]

    # Step 5: one NAT unless availability requires egress per zone. A
    # zone-redundant design whose only NAT sits in the failed zone has not
    # survived the failure -- the instances are up and cannot reach out.
    components.append(
        _c("nat", 2 if high_availability else 1,
           note="per-AZ so egress survives a zone loss" if high_availability
                else "single gateway, shared")
    )

    # Step 5: endpoints always. Object storage and the container registry
    # are the two paths a private subnet uses constantly, and routing them
    # through NAT bills the same bytes at four times the rate.
    components.append(
        _c("endpoint", 2, note="S3 and ECR, to keep those bytes off the NAT gateway")
    )
    return components


def build_plan(
    *,
    rates: Rates,
    availability: str,
    durability: str,
    region_lock: str,
    sector: str,
    storage_gb: float,
    budget_monthly_usd: float | None,
    assumed: dict[str, str] | None = None,
) -> Plan:
    """Steps 3 to 7: filters, three tiers, and the notes emitted once."""
    plan = Plan(assumed_fields=dict(assumed or {}))
    high_availability = availability == "high"
    durable = durability == "high"

    plan.sizing_basis = rates.as_text()

    # ── Step 3: region lock ──
    regions = in_country_regions(region_lock)
    if region_lock and not regions:
        plan.unsatisfiable.append(
            f"No catalog region inside {region_lock}. Nothing can be placed "
            "there, so no design below satisfies the residency requirement."
        )
    elif len(regions) == 1 and durable:
        # The conflict this planner exists to surface rather than paper over.
        plan.unsatisfiable.append(
            f"{region_lock} has exactly one region in the catalog "
            f"({regions[0]}), so a cross-region copy cannot stay in the "
            "country. durability=high and this region_lock cannot both be "
            "satisfied. The copy is omitted rather than sent offshore; "
            "choosing to send it abroad is a decision for whoever owns the "
            "data, not a default."
        )

    # ── Step 4: cheapest compliant ──
    instances = instances_for(rates.peak_rps, high_availability=high_availability)
    cheapest = Tier(name="cheapest_compliant")
    cheapest.components = _baseline(
        rates, instances, high_availability=high_availability
    )

    if high_availability:
        cheapest.components.append(
            _c("loadbalancer", 1, note="required by availability=high")
        )
        cheapest.components.append(_c("lcu", 1))
        cheapest.components.append(
            _c("database", 1, size="multi-az",
               note="required by availability=high; replaces single-AZ")
        )
        # The multi-AZ database replaces the single-AZ one above.
        cheapest.components = [
            comp for comp in cheapest.components
            if not (comp["category"] == "database" and comp.get("size") != "multi-az")
        ]

    if durable:
        cheapest.components.append(_c("backup", 1))
        cheapest.components.append(
            _c("governance", 1, size="object-lock",
               note="write-once retention; a backup an attacker can delete "
                    "is not a backup")
        )
        if len(regions) > 1:
            cheapest.components.append(
                _c("backup_copy", 1, note=f"second region inside {region_lock}")
            )
        # Step 5: lifecycle-tier write-once data by default.
        cheapest.components.append(
            _c("storage_lifecycle", 1,
               note="reports and logs are written once and rarely read; "
                    "Standard forever overstates retention cost roughly six-fold")
        )

    if region_lock and regions:
        cheapest.components.append(
            _c("governance", 1, size="region-deny-scp",
               note=f"denies every region outside {region_lock}; intent is "
                    "not a control")
        )

    cheapest.rto = "minutes — a zone loss fails over" if high_availability else (
        "hours — a single instance must be rebuilt"
    )
    cheapest.rpo = "minutes — Multi-AZ replication is synchronous" if high_availability else (
        "up to one backup interval"
    )
    cheapest.gives_up = _gives_up(
        high_availability=high_availability, durable=durable,
        regions=regions, rates=rates,
    )

    # ── Step 4: recommended ──
    recommended = Tier(
        name="recommended",
        components=list(cheapest.components),
        rto=cheapest.rto,
        rpo=cheapest.rpo,
    )
    _add_recommended(recommended, rates=rates, sector=sector, durable=durable)
    recommended.gives_up = _gives_up(
        high_availability=high_availability, durable=durable,
        regions=regions, rates=rates, recommended=True,
    )

    # ── Step 4: headroom ──
    headroom_rates = derive_rates(rates.requests_per_day * 3, rates.peak_shape)
    headroom_instances = instances_for(
        headroom_rates.peak_rps, high_availability=high_availability
    )
    headroom = Tier(
        name="headroom",
        components=[
            dict(comp, quantity=headroom_instances)
            if comp["category"] == "compute" else dict(comp)
            for comp in recommended.components
        ],
        rto=recommended.rto,
        rpo=recommended.rpo,
    )
    if headroom_instances == instances:
        # Honest rather than padded. At a low enough rate, three times the
        # traffic still fits the availability floor, so this tier is the
        # recommended one and buying more would be buying nothing.
        headroom.justifications = {
            "compute": (
                f"unchanged at {instances} instances: 3x the stated traffic is "
                f"{headroom_rates.peak_rps:.2f} req/sec peak, which the two "
                "instances required by availability=high already carry. There "
                "is no capacity to add that the traffic would use."
            )
        }
        headroom.gives_up = list(recommended.gives_up) + [
            "Nothing beyond the recommended tier — at this rate a headroom "
            "tier is the same design, and paying more would not change it."
        ]
    else:
        headroom.justifications = {
            "compute": (
                f"{headroom_instances} instances carry 3x the stated traffic "
                f"({headroom_rates.peak_rps:.2f} req/sec peak) without re-architecting"
            )
        }
    plan.tiers = [cheapest, recommended, headroom]
    plan.compliance_notes = _compliance(sector, region_lock)

    if budget_monthly_usd:
        plan.budget_note = (
            "Budget is not an input to sizing. Every tier above is sized from "
            f"{rates.peak_rps:.2f} req/sec peak; if that costs less than "
            f"${budget_monthly_usd:,.0f}, the remainder is unspent and that is "
            "the correct result, not an opportunity."
        )
    return plan


def _add_recommended(tier: Tier, *, rates: Rates, sector: str, durable: bool) -> None:
    """Step 4. The smallest set of additions that reduce operational risk.

    Each must trace to something stated. None may be justified by leftover
    budget, which is why the scale floor is checked before anything that
    only pays off under load.
    """
    tier.components.append(_c("secrets", 1))
    tier.justifications["secrets"] = (
        "credentials in environment variables leak through logs and process "
        "listings; rotation is impossible without a store"
    )

    tier.components.append(_c("tracing", 1))
    tier.justifications["tracing"] = (
        "a slow request is otherwise diagnosed by guesswork across instances"
    )

    if sector in ("healthcare", "fintech"):
        tier.components.append(_c("threat", 1))
        tier.justifications["threat"] = (
            f"a {sector} workload is a target; detection scales per-vCPU with "
            "the footprint rather than as a flat fee"
        )

    # Step 2's floor, enforced. These are the components that only earn
    # their cost under load.
    if not rates.below_scale_floor:
        tier.components.append(_c("cache", 1))
        tier.justifications["cache"] = (
            f"{rates.peak_rps:.0f} req/sec repeats reads often enough for a "
            "cache to reduce database size"
        )


def _gives_up(
    *, high_availability: bool, durable: bool,
    regions: tuple[str, ...], rates: Rates, recommended: bool = False,
) -> list[str]:
    """Step 6. What this design does not protect against, in plain words."""
    gaps: list[str] = []
    if not high_availability:
        gaps.append(
            "A zone failure takes the service down until an instance is "
            "rebuilt — there is no second instance to take over."
        )
    if not durable:
        gaps.append(
            "Data lost between backups is not recoverable, and a backup an "
            "attacker can reach can be deleted."
        )
    if len(regions) <= 1:
        gaps.append(
            "Losing the whole region loses the service and, if no copy left "
            "the country, the data with it."
        )
    if rates.below_scale_floor and not recommended:
        gaps.append(
            f"No caching layer — at {rates.peak_rps:.2f} req/sec one would "
            "cost more than it saves, but a sudden traffic change would need "
            "one adding."
        )
    gaps.append(
        "Nothing here protects against a bad deployment; that needs a "
        "release process, not infrastructure."
    )
    return gaps


def _compliance(sector: str, region_lock: str) -> list[str]:
    """Step 7. Only obligations the architecture can actually satisfy.

    Named regimes only where both sector and region are known. An invented
    regulation name is worse than none: it is checkable, and wrong.
    """
    if not sector or not region_lock:
        return []

    country = region_lock.strip().lower()
    notes: list[str] = []

    if sector == "healthcare" and country == "india":
        notes.append(
            "Digital Personal Data Protection Act 2023 — health data is "
            "sensitive personal data: encryption at rest (kms), access "
            "logging (audit), and breach-notification evidence (flowlogs)."
        )
    elif sector == "fintech" and country == "india":
        notes.append(
            "RBI storage-of-payment-system-data direction — payment data "
            "must stay in India: enforced by the region-deny policy "
            "(governance), not by configuration convention."
        )
        notes.append(
            "The same direction is what makes a cross-region copy outside "
            "India non-compliant rather than merely undesirable."
        )
    elif sector == "healthcare" and country == "united states":
        notes.append(
            "HIPAA Security Rule — encryption at rest (kms), audit controls "
            "(audit), and retention of access records (storage_lifecycle)."
        )

    if not notes:
        notes.append(
            f"No regime named for sector={sector} in {region_lock}. Stating "
            "one would be inventing it."
        )
    return notes
