"""A priced option, turned into a real AWS architecture.

The engine prices categories -- compute, database, cache -- because that is
what a price catalog can be indexed by. A reader wants services: not
"Database, db.t4g.large, $121.91" but Amazon RDS, in a private subnet, in the
zone that survives the other one failing.

This is the join. Each priced category becomes the AWS service that category
means, placed where AWS's own reference architectures place it, carrying the
price the engine worked out. Nothing here invents a figure: every node's cost
comes from the catalog, and a category the engine could not price is drawn
unpriced rather than left out.

The network structure is not guessed either. A tier the engine marked
high-availability gets two availability zones because that is what it was
priced for -- the standby database in "Most reliable" is the second zone, and
drawing one zone would contradict the number.
"""

from __future__ import annotations

from dataclasses import dataclass

from whichcloud.architecture.schema import Architecture, Boundary, Service

#: What each priced category is, as an AWS service. One row per category the
#: catalog covers, which is why this table is short and complete rather than
#: long and partial.
#:
#: (service name, tier, what it does, where it sits)
AWS_SERVICE: dict[str, tuple[str, str, str, str]] = {
    "network": ("Amazon CloudFront", "edge", "Content delivery", "edge"),
    "loadbalancer": ("Elastic Load Balancing", "api", "Traffic distribution", "public"),
    "compute": ("Amazon ECS", "compute", "Application containers", "private"),
    "cache": ("Amazon ElastiCache", "data", "In-memory cache", "private"),
    "database": ("Amazon RDS", "data", "Relational database", "private"),
    "storage": ("Amazon S3", "data", "Object storage", "edge"),
    "monitoring": ("Amazon CloudWatch", "observability", "Metrics and logs", "edge"),
}

#: The request path, in order. Only pairs where both ends exist are drawn, so
#: a tier without a load balancer connects the CDN straight to compute rather
#: than to a box that is not there.
FLOW_ORDER: tuple[tuple[str, str], ...] = (
    ("network", "loadbalancer"),
    ("network", "compute"),
    ("loadbalancer", "compute"),
    ("compute", "cache"),
    ("compute", "database"),
    ("compute", "storage"),
)


@dataclass
class PricedNode:
    """One node of a priced option, as the engine describes it."""

    kind: str
    label: str
    monthly_usd: float | None
    sku: str | None


def architecture_from(
    nodes: list[PricedNode], high_availability: bool
) -> tuple[Architecture, dict[str, tuple[float, str]]]:
    """The architecture for a priced option, and what each node costs.

    Returns the drawable architecture and a map from node id to (price, sku),
    which the layout attaches afterwards. Keeping the price out of the
    Architecture is deliberate: that type describes what a system *is*, and it
    is also produced by reading a description, where no price exists.
    """
    present = {n.kind: n for n in nodes if n.kind in AWS_SERVICE}

    services: list[Service] = []
    prices: dict[str, tuple[float, str]] = {}
    placement: dict[str, list[str]] = {"public": [], "private": [], "edge": []}

    for kind, node in present.items():
        name, tier, purpose, where = AWS_SERVICE[kind]
        # The engine's own label carries detail the category name does not --
        # "Database (Multi-AZ)" says something the word "database" cannot.
        detail = node.label
        if "(" in detail:
            name = f"{name} {detail[detail.index('(') :]}"

        connects: list[str] = []
        services.append(
            Service(
                name=name,
                tier=tier,  # type: ignore[arg-type]
                component="",
                connects_to=connects,
                flow="control" if kind == "monitoring" else "sync",
                purpose=purpose,
            )
        )
        placement[where].append(name)
        if node.monthly_usd is not None:
            prices[name] = (node.monthly_usd, node.sku or "")

    by_kind = {
        kind: AWS_SERVICE[kind][0]
        for kind in present
    }
    # Names may have gained a suffix above, so resolve against what was built.
    built = {s.name: s for s in services}
    for kind, base in list(by_kind.items()):
        if base not in built:
            match = next((n for n in built if n.startswith(base)), None)
            if match:
                by_kind[kind] = match

    for source_kind, target_kind in FLOW_ORDER:
        if source_kind in by_kind and target_kind in by_kind:
            # A CDN that reaches a load balancer must not also reach compute
            # directly; the request goes through one path, not both.
            if (
                source_kind == "network"
                and target_kind == "compute"
                and "loadbalancer" in by_kind
            ):
                continue
            built[by_kind[source_kind]].connects_to.append(by_kind[target_kind])

    if "monitoring" in by_kind and "compute" in by_kind:
        built[by_kind["monitoring"]].connects_to.append(by_kind["compute"])

    # ── the network the price was worked out for ──
    zones = 2 if high_availability else 1
    boundaries: list[Boundary] = []
    zone_names: list[str] = []

    for index in range(1, zones + 1):
        public = f"Public subnet {index}" if zones > 1 else "Public subnet"
        private = f"Private subnet {index}" if zones > 1 else "Private subnet"
        zone = f"Availability Zone {index}" if zones > 1 else "Availability Zone"
        zone_names.append(zone)

        # Every zone holds the same services. That is what paying for
        # high availability buys, and drawing one copy would show a system
        # that cannot survive the failure the price covers.
        boundaries.append(Boundary(kind="subnet", name=public, contains=list(placement["public"])))
        boundaries.append(
            Boundary(kind="subnet", name=private, contains=list(placement["private"]))
        )
        boundaries.append(Boundary(kind="az", name=zone, contains=[public, private]))

    boundaries.insert(0, Boundary(kind="vpc", name="VPC", contains=zone_names))

    return (
        Architecture(
            services=services,
            boundaries=boundaries,
            regions=1,
            azs_per_region=zones,
        ),
        prices,
    )
