"""Module 3. A stated requirement is a filter, not a preference.

The behaviour change this module exists for: there is no unconstrained
cheapest tier. A design that fails a stated requirement is not a cheaper
version of the same thing -- it is a different thing, and offering it
beside two compliant options invites picking it on price. It can still be
shown, in its own panel, labelled with what it violates.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Architecture:
    """A candidate, in the terms the filter checks."""

    compute_instance_count: int = 1
    availability_zones: int = 1
    load_balancer: bool = False
    database_multi_az: bool = False
    automated_backups: bool = False
    cross_region_copy_region: str = ""
    object_lock: bool = False
    regions: tuple[str, ...] = ()
    region_deny_guardrail: bool = False

    #: True when availability comes from the SERVICE rather than from
    #: instances you arranged.
    #:
    #: The four availability checks below are written in instance terms --
    #: count them, spread them across zones, put a balancer in front,
    #: replicate the database. Every one of those is the right question
    #: for EC2 and a meaningless one for Lambda, API Gateway, SQS, S3 and
    #: DynamoDB, which are regional services already replicated across
    #: availability zones. Demanding "two instances and a load balancer"
    #: of a Lambda function asks for something that does not exist, and
    #: failing the design for not having it would push it towards an
    #: always-on fleet that is genuinely LESS available.
    #:
    #: Deliberately scoped to availability only. Every durability check
    #: still applies in full: serverless says nothing about whether your
    #: backups survive losing a region, and this flag must never become a
    #: way to skip one.
    serverless: bool = False


@dataclass
class FilterResult:
    valid: bool
    violations: list[str] = field(default_factory=list)


def check(
    architecture: Architecture,
    *,
    availability: str,
    durability: str,
    country: str = "",
    country_regions: tuple[str, ...] = (),
) -> FilterResult:
    """Every violation, named in the user's terms rather than the system's."""
    violations: list[str] = []

    # A regional managed service is already spread across zones, so the
    # instance-shaped questions below have no answer for it. See
    # Architecture.serverless.
    if availability == "high" and not architecture.serverless:
        if architecture.compute_instance_count < 2:
            violations.append(
                "runs a single instance, so any restart is an outage — you "
                "said downtime is unacceptable"
            )
        if architecture.availability_zones < 2:
            violations.append(
                "sits in one availability zone, so a zone failure takes it down"
            )
        if not architecture.load_balancer:
            violations.append(
                "has no load balancer, so there is nothing to fail traffic over to"
            )
        if not architecture.database_multi_az:
            violations.append(
                "runs a single-AZ database, which is the one component whose "
                "loss cannot be worked around"
            )

    if durability == "high":
        if not architecture.automated_backups:
            violations.append("takes no automated backups")
        if not architecture.cross_region_copy_region:
            violations.append(
                "keeps every copy in one region, so losing the region loses "
                "the data — you said it cannot be lost"
            )
        elif country_regions and architecture.cross_region_copy_region not in country_regions:
            violations.append(
                f"copies backups to {architecture.cross_region_copy_region}, "
                f"which is outside {country}"
            )
        if not architecture.object_lock:
            violations.append(
                "stores documents without immutability, so a backup an "
                "attacker reaches can be deleted"
            )

    if country_regions:
        outside = [r for r in architecture.regions if r not in country_regions]
        if outside:
            violations.append(
                f"places {', '.join(outside)} outside {country}"
            )
        if not architecture.region_deny_guardrail:
            violations.append(
                f"has no guardrail denying regions outside {country}; "
                "intent is not a control"
            )

    return FilterResult(valid=not violations, violations=violations)
