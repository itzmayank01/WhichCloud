"""The output contract: description in, three compliant tiers out.

This is where the four reasoning modules meet the price catalog. The order
is deliberate and is the whole design:

    extract  ->  derive the rate  ->  filter  ->  price

Filtering BEFORE pricing is the behaviour change. The old flow priced a
cheapest option and then noticed it failed a stated requirement, which
produces a cheap number attached to a design the user already ruled out --
and a cheap number wins arguments. Nothing that fails the filter is ever
given a price here; it is shown separately, with its violations, if at all.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from whichcloud.constraint_filter import Architecture, check
from whichcloud.constraints import Constraints, extract
from whichcloud.estimator import ArchitectureSpec, Estimate, estimate
from whichcloud.load_model import Load, build_load
from whichcloud.objectives import compliance_notes, objectives
from whichcloud.planner import RPS_PER_VCPU, in_country_regions

#: Neutral region keys per country, in the order a plan should prefer them.
COUNTRY_REGIONS: dict[str, tuple[str, ...]] = {
    "IN": ("india", "india-south"),
    "SG": ("singapore",),
    "US": ("us-east",),
    "IE": ("eu-west",),
    "DE": ("eu-west",),
    "FR": ("eu-west",),
    "GB": ("eu-west",),
}

#: Storage assumed when the description gives none. Flagged, never hidden:
#: it drives the largest single line on a records-heavy workload, so an
#: unexamined default here quietly sets the total.
DEFAULT_STORAGE_GB = 500.0
DEFAULT_EGRESS_GB = 100.0


@dataclass
class Tier:
    name: str
    label: str
    spec: ArchitectureSpec
    estimate: Estimate
    rto: str = ""
    rpo: str = ""
    region_rto: str = ""
    region_rpo: str = ""
    gives_up: list[str] = field(default_factory=list)
    justifications: dict[str, str] = field(default_factory=dict)

    @property
    def monthly_total(self) -> float:
        return float(self.estimate.total_monthly)

    def within_budget(self, budget: float) -> bool:
        return not budget or self.monthly_total <= budget


@dataclass
class Plan:
    constraints: Constraints
    load: Load
    tiers: list[Tier] = field(default_factory=list)
    below_requirements: dict | None = None
    compliance: list[dict] = field(default_factory=list)
    over_budget_note: str = ""
    unspent_budget: dict | None = None


def _vcpu_for(peak_rps: float) -> int:
    """vCPU per instance, from the rate. Two is the floor, not a default."""
    import math

    return max(2, 2 * math.ceil(peak_rps / (RPS_PER_VCPU * 2)))


def _instances_for(peak_rps: float, *, high_availability: bool) -> int:
    import math

    needed = max(1, math.ceil(peak_rps / RPS_PER_VCPU))
    return max(needed, 2) if high_availability else needed


def _spec_for(
    *,
    name: str,
    constraints: Constraints,
    load: Load,
    region: str,
    instances: int,
    tier_level: int,
) -> ArchitectureSpec:
    """One tier's spec. Every optional component traces to a filter or a gate."""
    high_availability = constraints.availability == "high"
    durable = constraints.durability == "high"
    storage = constraints.storage_gb or DEFAULT_STORAGE_GB
    egress = constraints.egress_gb or DEFAULT_EGRESS_GB
    vcpu = _vcpu_for(load.peak_rps)

    return ArchitectureSpec(
        name=name,
        region=region,
        # Sized from the peak rate. Not from 450 staff, and not from $900.
        compute_count=instances,
        compute_vcpu=vcpu,
        compute_memory_gb=float(vcpu) * 2,
        arch="arm64" if constraints.sector != "other" else None,
        database_vcpu=2,
        database_memory_gb=8.0,
        # Required by availability=high; not a tier upsell.
        database_multi_az=high_availability,
        database_arch="arm64",
        database_read_replicas=1 if "database_replica" in load.included else 0,
        storage_gb=storage,
        egress_gb=egress,
        load_balancer=high_availability,
        serves_requests=True,
        # Gated on the derived rate, not on the tier's position in the list.
        cache_vcpu=2 if "cache" in load.included else None,
        cache_memory_gb=4.0 if "cache" in load.included else None,
        monitored_metrics=30,
        waf_rule_count=3 if "waf" in load.included else None,
        # Required by durability=high.
        backup_gb=storage if durable else 0.0,
        backup_copy_gb=storage if durable else 0.0,
        object_lock=durable,
        lifecycle_gb=storage * 0.4 if durable else 0.0,
        region_deny_guardrail=bool(constraints.country),
        # Always: these exist to keep S3 and ECR traffic off the NAT gateway,
        # where the same bytes cost four times as much.
        vpc_endpoints=2,
        vpc_endpoint_gb=egress * 0.5,
        nat_gateway_count=2 if high_availability else 1,
        audit_logging=True,
        tls_certificate=True,
        dns_hosted_zones=1,
        kms_key_count=1,
        flowlog_gb=egress * 0.5,
        # tier 2 and 3 additions
        secret_count=1 if tier_level >= 2 else 0,
        tracing_monthly_traces=1_000_000 if tier_level >= 2 else 0,
        threat_detection=tier_level >= 2,
    )


def _architecture_from(spec: ArchitectureSpec, region_code: str) -> Architecture:
    """The spec, in the terms the filter checks."""
    return Architecture(
        compute_instance_count=spec.compute_count,
        availability_zones=spec.nat_gateway_count or 1,
        load_balancer=spec.load_balancer,
        database_multi_az=spec.database_multi_az,
        automated_backups=bool(spec.backup_gb),
        cross_region_copy_region=(
            "ap-south-2" if spec.backup_copy_gb and region_code == "ap-south-1" else ""
        ),
        object_lock=spec.object_lock,
        regions=(region_code,) + (("ap-south-2",) if spec.backup_copy_gb else ()),
        region_deny_guardrail=spec.region_deny_guardrail,
    )


def build(description: str, provider: str = "aws", dsn: str | None = None) -> Plan:
    """The whole contract, in the order the modules are meant to run."""
    constraints = extract(description)
    load = build_load(constraints, description)

    regions = COUNTRY_REGIONS.get(constraints.country, ("india",))
    region = regions[0]
    in_country = in_country_regions(_country_name(constraints.country))

    high_availability = constraints.availability == "high"
    instances = _instances_for(load.peak_rps, high_availability=high_availability)

    plan = Plan(constraints=constraints, load=load)

    specs = [
        ("tier_1", "Cheapest compliant", 1, instances),
        ("tier_2", "Recommended", 2, instances),
        ("tier_3", "Headroom for 3x", 3, max(instances, _instances_for(
            load.peak_rps * 3, high_availability=high_availability))),
    ]

    for name, label, level, count in specs:
        spec = _spec_for(
            name=name, constraints=constraints, load=load, region=region,
            instances=count, tier_level=level,
        )
        # FILTER BEFORE PRICE. A spec that fails here is never given a
        # number, because a cheap number attached to a rejected design is
        # the thing this module exists to stop producing.
        verdict = check(
            _architecture_from(spec, _aws_region(region)),
            availability=constraints.availability,
            durability=constraints.durability,
            country=_country_name(constraints.country),
            country_regions=_aws_regions(in_country),
        )
        if not verdict.valid:
            raise AssertionError(
                f"{name} was generated non-compliant: {verdict.violations}"
            )

        est = estimate(spec, provider, dsn=dsn)
        obj = objectives(
            multi_instance=spec.compute_count >= 2,
            multi_az_database=spec.database_multi_az,
            cross_region_copy=bool(spec.backup_copy_gb),
        )
        tier = Tier(
            name=name, label=label, spec=spec, estimate=est,
            rto=obj["rto"], rpo=obj["rpo"],
            region_rto=obj["region_rto"], region_rpo=obj["region_rpo"],
        )
        tier.gives_up = _gives_up(spec, load)
        if level >= 2:
            tier.justifications.update(_tier_two_justifications(constraints))
        if level >= 3:
            tier.justifications["compute"] = (
                f"{count} instances carry 3x the stated volume "
                f"({load.peak_rps * 3:.2f} req/sec peak)"
                if count > instances
                else f"unchanged at {instances}: 3x the stated volume is still "
                     f"{load.peak_rps * 3:.2f} req/sec, which the instances "
                     "required by availability=high already carry"
            )
        plan.tiers.append(tier)

    plan.below_requirements = _below_panel(constraints, load, region, dsn, provider)
    plan.compliance = compliance_notes(constraints.country, constraints.sector)

    budget = constraints.budget_monthly_usd
    cheapest = plan.tiers[0]
    if budget and cheapest.monthly_total > budget:
        plan.over_budget_note = (
            "Your requirements set a floor above your budget. Cheapest "
            "compliant design shown."
        )
    elif budget:
        spare = budget - plan.tiers[1].monthly_total
        if spare > 0:
            plan.unspent_budget = {
                "amount_usd": round(spare, 2),
                "note": (
                    f"${spare:,.2f} of your ${budget:,.0f} is unspent. That is a "
                    "correct result, not an error: every tier is sized from "
                    f"{load.peak_rps:.2f} req/sec peak, and spending the "
                    "remainder would buy capacity this workload would not use."
                ),
            }
    return plan


def _below_panel(constraints, load, region, dsn, provider) -> dict | None:
    """The design that fails the filter, shown apart and never priced as a tier."""
    if constraints.availability != "high" and constraints.durability != "high":
        return None

    naive = Architecture(
        compute_instance_count=1, availability_zones=1, load_balancer=False,
        database_multi_az=False, automated_backups=False, object_lock=False,
        regions=(_aws_region(region),), region_deny_guardrail=False,
    )
    verdict = check(
        naive,
        availability=constraints.availability,
        durability=constraints.durability,
        country=_country_name(constraints.country),
        country_regions=_aws_regions(in_country_regions(_country_name(constraints.country))),
    )
    return {
        "label": "Below your stated requirements",
        "violations": verdict.violations,
        "note": (
            "Shown for comparison only. It is cheaper because it does less, "
            "not because it is better value, and it is not one of the three "
            "options above."
        ),
    }


def _gives_up(spec: ArchitectureSpec, load: Load) -> list[str]:
    gaps = []
    if not spec.backup_copy_gb:
        gaps.append("Losing the region loses the data — no copy leaves it.")
    if spec.database_read_replicas == 0:
        gaps.append(
            f"Reads and writes share one database; at {load.peak_rps:.2f} "
            "req/sec that is ample, but a reporting workload would contend."
        )
    gaps.append(
        "Nothing here protects against a bad deployment — that needs a "
        "release process, not infrastructure."
    )
    return gaps


def _tier_two_justifications(constraints: Constraints) -> dict[str, str]:
    out = {
        "secrets": (
            "credentials in environment variables leak through logs; you said "
            "the data is regulated"
        ),
        "tracing": "a slow lookup is otherwise diagnosed by guesswork",
    }
    if constraints.sector in ("healthcare", "fintech"):
        out["threat"] = (
            f"a {constraints.sector} record store is a target; detection bills "
            "per vCPU so it scales with the footprint"
        )
    return out


def _country_name(code: str) -> str:
    return {"IN": "India", "SG": "Singapore", "US": "United States",
            "IE": "Ireland", "GB": "United Kingdom"}.get(code, "")


def _aws_region(neutral: str) -> str:
    from whichcloud.pricing.models import provider_region

    return provider_region(neutral, "aws")


def _aws_regions(neutral_keys: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(neutral_keys)
