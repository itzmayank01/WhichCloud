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
    "waf": ("AWS WAF", "edge", "Filters malicious requests before they reach the app", "edge"),
    "network": ("Amazon CloudFront", "edge", "Content delivery", "edge"),
    "loadbalancer": ("Elastic Load Balancing", "api", "Traffic distribution", "public"),
    "compute": ("Amazon ECS", "compute", "Application containers", "private"),
    "cache": ("Amazon ElastiCache", "data", "In-memory cache", "private"),
    "database": ("Amazon RDS", "data", "Relational database", "private"),
    # A distinct name, not another "Amazon RDS" -- two services would collide
    # on the same key in the `built` name->Service map below and one would
    # silently vanish from the diagram while still being paid for.
    "database_replica": (
        "Amazon RDS Read Replica", "data", "Read replica for reporting and reads", "private",
    ),
    "storage": ("Amazon S3", "data", "Object storage", "edge"),
    "monitoring": ("Amazon CloudWatch", "observability", "Metrics and logs", "edge"),
    "audit": ("AWS CloudTrail", "observability", "Records who did what, for audit and compliance", "edge"),
    "kms": ("AWS KMS", "security", "Encrypts data at rest", "private"),
    "nat": ("NAT Gateway", "api", "Outbound internet for private subnets", "public"),
    "dns": ("Amazon Route 53", "edge", "DNS resolution and health checks", "edge"),
    "auth": ("Amazon Cognito", "security", "Staff sign-in, MFA and tokens", "edge"),
    "backup": ("AWS Backup", "data", "Scheduled backups and retention", "private"),
    "streaming": ("Amazon Kinesis Data Streams", "async", "Buffers transactions for real-time processing", "private"),
    "kafka": ("Amazon MSK", "async", "Managed Kafka for high-volume event streaming", "private"),
    "search": ("Amazon OpenSearch", "analytics", "Full-text search and live dashboards", "private"),
    "warehouse": ("Amazon Redshift", "analytics", "Data warehouse for sales analytics", "private"),
    "threat": ("Amazon GuardDuty", "security", "Continuous threat detection across compute and data", "edge"),
    "tracing": ("AWS X-Ray", "observability", "Distributed tracing across the request path", "edge"),
    "posture": ("AWS Security Hub", "security", "Continuous compliance and posture checks", "edge"),
    "flowlogs": ("VPC Flow Logs", "observability", "Records network traffic crossing the VPC", "edge"),
    "tls": ("AWS Certificate Manager", "security", "TLS certificates for the load balancer and CDN", "edge"),
}

#: The request path, in order. Only pairs where both ends exist are drawn, so
#: a tier without a load balancer connects the CDN straight to compute rather
#: than to a box that is not there.
FLOW_ORDER: tuple[tuple[str, str], ...] = (
    ("waf", "network"),
    ("waf", "loadbalancer"),
    ("waf", "compute"),
    ("network", "loadbalancer"),
    ("network", "compute"),
    ("loadbalancer", "compute"),
    ("compute", "cache"),
    ("compute", "database"),
    ("compute", "storage"),
    ("database", "database_replica"),
    ("compute", "audit"),
    ("kms", "database"),
    # Outbound, not inbound: private compute reaches the internet through
    # the gateway, which is the opposite direction to every edge above.
    ("compute", "nat"),
    ("tls", "loadbalancer"),
    ("dns", "waf"),
    ("dns", "network"),
    ("dns", "loadbalancer"),
    ("compute", "auth"),
    ("storage", "backup"),
    ("threat", "compute"),
    ("tracing", "compute"),
    ("posture", "compute"),
    ("flowlogs", "compute"),
    # The async buffer: compute publishes events, the stores consume them.
    ("compute", "streaming"),
    ("compute", "kafka"),
    ("streaming", "database"),
    ("kafka", "database"),
    ("streaming", "search"),
    ("streaming", "warehouse"),
    ("kafka", "search"),
    ("kafka", "warehouse"),
)


@dataclass
class PricedNode:
    """One node of a priced option, as the engine describes it."""

    kind: str
    label: str
    monthly_usd: float | None
    sku: str | None


def architecture_from(
    nodes: list[PricedNode], high_availability: bool, zones: int | None = None
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
            # WAF sits in front of whichever single box the request actually
            # meets first -- the CDN if there is one, else the load balancer,
            # else compute directly -- not all three at once.
            if source_kind == "waf" and target_kind == "loadbalancer" and "network" in by_kind:
                continue
            if source_kind == "waf" and target_kind == "compute" and (
                "network" in by_kind or "loadbalancer" in by_kind
            ):
                continue
            # Same rule for DNS, which resolves to one entry point: the WAF
            # if traffic is filtered, else the CDN, else the load balancer.
            if source_kind == "dns" and target_kind == "network" and "waf" in by_kind:
                continue
            if source_kind == "dns" and target_kind == "loadbalancer" and (
                "waf" in by_kind or "network" in by_kind
            ):
                continue
            # One async buffer, not two: where MSK is present it is the
            # stream, and Kinesis is not also drawn feeding the same sinks.
            if source_kind == "streaming" and "kafka" in by_kind:
                continue
            # Compute writes to the database THROUGH the buffer when there
            # is one, so the direct edge would contradict the topology.
            if (
                source_kind == "compute"
                and target_kind == "database"
                and ("kafka" in by_kind or "streaming" in by_kind)
            ):
                continue
            built[by_kind[source_kind]].connects_to.append(by_kind[target_kind])

    if "monitoring" in by_kind and "compute" in by_kind:
        built[by_kind["monitoring"]].connects_to.append(by_kind["compute"])

    # ── the network the price was worked out for ──
    # Drawn from what was actually PAID for, not inferred from a flag. The
    # top tier bills three NAT gateways and ran three instances while this
    # still drew two zones, so the picture contradicted the bill beside it
    # -- the one thing this project treats as unforgivable.
    if zones is None:
        zones = 2 if high_availability else 1
    zones = max(1, zones)

    # ONE zone is drawn, labelled with how many there are.
    #
    # Drawing a box per zone put the same service names in every one, and a
    # service can only be placed once -- so the last zone took them all and
    # the earlier boxes rendered empty, leaving a three-zone architecture
    # showing a single frame confusingly numbered "3".
    #
    # Repeating the services instead would triple every box on the canvas
    # to say something the labels already say. It also matches how the rest
    # of the diagram reads: the NAT node carries the cost of all three
    # gateways, not one, and nobody expects three NAT icons.
    suffix = f" × {zones}" if zones > 1 else ""
    public = f"Public subnet{suffix}"
    private = f"Private subnet{suffix}"
    zone = f"Availability Zone{suffix}"

    boundaries: list[Boundary] = []
    zone_names: list[str] = []

    boundaries.append(
        Boundary(kind="subnet", name=public, contains=list(placement["public"]))
    )
    boundaries.append(
        Boundary(kind="subnet", name=private, contains=list(placement["private"]))
    )
    boundaries.append(Boundary(kind="az", name=zone, contains=[public, private]))
    zone_names.append(zone)

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
