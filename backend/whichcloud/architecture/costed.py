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
    # The engine's default compute is priced as raw instances (BASE_SIZING
    # picks an EC2 instance type, not a task definition), so that is what
    # gets drawn. "compute_fargate" below is the container-orchestrated
    # alternative, priced and drawn separately -- collapsing both onto one
    # "Amazon ECS" label meant an EC2-only architecture was mislabeled as
    # running containers it never provisioned.
    "compute": ("Amazon EC2 Auto Scaling", "compute", "Application servers, sized to the traffic described", "private"),
    "compute_fargate": ("AWS Fargate (ECS)", "compute", "Serverless application containers", "private"),
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
    # Previously unmapped in topology.py -- these line items existed and
    # were priced, but silently added their cost onto the compute node and
    # never appeared as their own service.
    "email": ("Amazon SES", "async", "Sends transactional email", "private"),
    "queue": ("Amazon SQS", "async", "Decouples requests from the work that processes them", "private"),
    "notification": ("Amazon SNS", "async", "Push notifications and fan-out", "private"),
    # Serverless. No VPC placement -- Lambda, API Gateway and DynamoDB are
    # regional managed services, not boxes inside a subnet, which is exactly
    # why a serverless architecture has no NAT gateway or private subnet to
    # draw. "edge" keeps them out of the VPC container the server shapes use.
    "apigateway": ("Amazon API Gateway", "api", "Managed HTTP front for the functions", "edge"),
    "lambda": ("AWS Lambda", "compute", "Runs application code per request, scales to zero", "edge"),
    "dynamodb": ("Amazon DynamoDB", "data", "Serverless key-value and document store", "edge"),
    # Placed at "edge", not "private": Secrets Manager is a regional managed
    # service reached over the network, and pinning it inside a subnet was
    # forcing a VPC around a serverless architecture that has none.
    "secrets": ("AWS Secrets Manager", "security", "Stores database and API credentials", "edge"),
    # Managed AI. Regional services called over the network -- no VPC, placed
    # "edge" like the other managed services, tier "ml".
    "rekognition": ("Amazon Rekognition", "ml", "Image recognition and moderation", "edge"),
    "comprehend": ("Amazon Comprehend", "ml", "Sentiment and language analysis", "edge"),
    # Event-driven / IoT. Managed regional services, placed "edge" (no VPC):
    # devices publish to IoT Core, events flow through a stream, and land in a
    # purpose-built time-series store queried by the analytics services.
    "iot": ("AWS IoT Core", "edge", "Device connectivity and messaging", "edge"),
    "firehose": ("Kinesis Data Firehose", "async", "Managed delivery of the stream to storage", "edge"),
    "timestream": ("Amazon Timestream", "data", "Purpose-built time-series store", "edge"),
    "athena": ("Amazon Athena", "analytics", "Serverless SQL over the data lake", "edge"),
    "glue": ("AWS Glue", "analytics", "Managed ETL and data catalog", "edge"),
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
    ("kms", "database"),
    # Outbound, not inbound: private compute reaches the internet through
    # the gateway, which is the opposite direction to every edge above.
    ("compute", "nat"),
    ("dns", "waf"),
    ("dns", "network"),
    ("dns", "loadbalancer"),
    ("compute", "auth"),
    ("compute", "email"),
    ("compute", "queue"),
    ("compute", "notification"),
    ("storage", "backup"),
    # ── serverless request path ──
    # The edge tier reaches API Gateway, which invokes Lambda, which reads
    # and writes DynamoDB and serves assets from S3. Only drawn where both
    # ends exist, so a server shape (no apigateway/lambda) shows none of them.
    ("network", "apigateway"),
    ("dns", "apigateway"),
    ("apigateway", "lambda"),
    ("lambda", "dynamodb"),
    # The function calls the managed AI service, then stores the result.
    ("lambda", "rekognition"),
    ("lambda", "comprehend"),
    ("lambda", "storage"),
    ("lambda", "auth"),
    ("lambda", "queue"),
    ("lambda", "notification"),
    # The async buffer: compute publishes events, the stores consume them.
    ("compute", "streaming"),
    ("compute", "kafka"),
    ("streaming", "database"),
    ("kafka", "database"),
    ("streaming", "search"),
    ("streaming", "warehouse"),
    ("kafka", "search"),
    ("kafka", "warehouse"),
    # ── event-driven / IoT pipeline ──
    # Devices publish to IoT Core, which feeds the stream; processors consume
    # it and write to the time-series store; analytics query that store and
    # the data lake. Only drawn where both ends exist per tier, so each tier's
    # own graph shows exactly the services it selected.
    ("iot", "streaming"),
    ("iot", "kafka"),
    ("streaming", "compute"),
    ("streaming", "compute_fargate"),
    ("streaming", "lambda"),
    ("streaming", "firehose"),
    ("kafka", "compute"),
    ("kafka", "compute_fargate"),
    ("kafka", "firehose"),
    ("firehose", "storage"),
    ("compute", "timestream"),
    ("compute_fargate", "timestream"),
    ("lambda", "timestream"),
    ("streaming", "timestream"),
    ("kafka", "timestream"),
    ("timestream", "athena"),
    ("timestream", "search"),
    ("timestream", "warehouse"),
    ("storage", "athena"),
    ("storage", "glue"),
    ("glue", "warehouse"),
)

#: Kinds that genuinely run inside a subnet, and therefore require a VPC to be
#: drawn around them. A managed service like KMS or Secrets Manager may be
#: PLACED "private" for tidiness, but it does not itself justify a VPC -- a
#: serverless architecture reaches all of them over the network and has no VPC
#: at all, which is precisely why it pays for no NAT gateway.
_VPC_RESIDENT_KINDS = frozenset({
    "compute", "compute_fargate", "cache", "database", "database_replica",
    "nat", "loadbalancer", "streaming", "kafka", "search", "warehouse",
})


@dataclass
class PricedNode:
    """One node of a priced option, as the engine describes it."""

    kind: str
    label: str
    monthly_usd: float | None
    sku: str | None


def architecture_from(
    nodes: list[PricedNode],
    high_availability: bool,
    zones: int | None = None,
    serves_requests: bool = True,
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

    # Egress is drawn as a CDN only where something is being served. A
    # nightly batch job moves data out too, but calling that CloudFront put
    # a content delivery network in front of a pipeline nobody calls.
    #
    # Passed in rather than inferred: "has a load balancer" looked like a
    # reasonable proxy and is not, because a small web app on one instance
    # legitimately has a CDN in front of compute with no balancer at all.

    #: The name each kind ended up with, since some are renamed below and
    #: the edges have to resolve against what was actually built.
    named: dict[str, str] = {}

    for kind, node in present.items():
        name, tier, purpose, where = AWS_SERVICE[kind]
        if kind == "network" and not serves_requests:
            name, purpose = "AWS Data Transfer", "Data leaving the region"
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
        named[kind] = name
        if node.monthly_usd is not None:
            prices[name] = (node.monthly_usd, node.sku or "")

    by_kind = dict(named)
    # Names may have gained a suffix above, so resolve against what was built.
    built = {s.name: s for s in services}
    for kind, base in list(by_kind.items()):
        if base not in built:
            match = next((n for n in built if n.startswith(base)), None)
            if match:
                by_kind[kind] = match

    # A Fargate compute node plays the same role in the request path as EC2
    # compute -- everything FLOW_ORDER says about "compute" (what reaches it,
    # what it reaches) applies unchanged. Aliasing here means the routing
    # table below never needs a parallel "compute_fargate" entry for every
    # edge compute already has.
    if "compute_fargate" in by_kind and "compute" not in by_kind:
        by_kind["compute"] = by_kind["compute_fargate"]

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

    # CloudWatch gets no arrow either, for the reason above: it collects from
    # every service in the picture, so a line to compute alone is a claim
    # about where metrics come from that is not true.

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

    # A VPC only where something actually RUNS in a subnet. A managed service
    # placed "private" for tidiness (KMS, Secrets Manager) does not justify a
    # VPC on its own -- a serverless architecture reaches all of them over the
    # network and has none. The absence of the VPC is itself true information:
    # it is *why* the serverless option pays for no NAT gateway. Managed
    # services that were placed inside the (now absent) subnets fall back to
    # sitting directly in the cloud boundary.
    needs_vpc = any(kind in _VPC_RESIDENT_KINDS for kind in present)
    if not needs_vpc:
        placement["edge"].extend(placement["public"])
        placement["edge"].extend(placement["private"])
        placement["public"].clear()
        placement["private"].clear()
    if needs_vpc:
        boundaries.append(
            Boundary(kind="subnet", name=public, contains=list(placement["public"]))
        )
        boundaries.append(
            Boundary(kind="subnet", name=private, contains=list(placement["private"]))
        )
        boundaries.append(Boundary(kind="az", name=zone, contains=[public, private]))
        boundaries.insert(0, Boundary(kind="vpc", name="VPC", contains=[zone]))

    return (
        Architecture(
            services=services,
            boundaries=boundaries,
            regions=1,
            azs_per_region=zones,
        ),
        prices,
    )
