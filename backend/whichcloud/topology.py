"""Turn a priced architecture into a diagram.

The interface needs to draw boxes and arrows, and every box needs to carry its
own cost. That is the thing neither a diagram tool nor a cost tool does — one
draws without prices, the other prices without drawing.

The topology is derived from the **priced estimate**, never from the request.
If a component could not be priced it does not appear as a confident node; it
appears as an unpriced one. A diagram that shows a database we failed to price
would be lying in the most convincing possible format.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal

from .estimator import ArchitectureSpec, Estimate, LineItem

# Which line-item labels map to which node. Labels come from the estimator, so
# this is the one place the two modules agree on vocabulary. "Database read
# replica" must be checked before the plain "Database" prefix it also starts
# with, or every replica line would collapse onto the primary's node.
_KIND_BY_PREFIX = {
    "Compute": "compute",
    "Database read replica": "database_replica",
    "Database": "database",
    "Object storage": "storage",
    "Egress": "network",
    "Load balancer": "loadbalancer",
    "Cache": "cache",
    "Monitoring": "monitoring",
    "WAF": "waf",
    "Audit logging": "audit",
    "KMS keys": "kms",
    "Key management operations": "kms",
    "NAT gateway": "nat",
    "NAT data processing": "nat",
    "TLS certificate": "tls",
    "DNS hosted zone": "dns",
    "DNS queries": "dns",
    "Authentication": "auth",
    "Backup storage": "backup",
    "Event stream shards": "streaming",
    "Event stream PUT units": "streaming",
    "Kafka brokers": "kafka",
    "Search nodes": "search",
    "Search storage": "search",
    "Warehouse nodes": "warehouse",
    "Threat detection": "threat",
    "Security posture": "posture",
    "Distributed tracing": "tracing",
    "Telemetry ingestion": "tracing",
    "Security posture checks": "posture",
    "VPC flow logs": "flowlogs",
    "Fargate vCPU": "compute_fargate",
    "Fargate memory": "compute_fargate",
    "Database storage": "database",
    "Load balancer LCUs": "loadbalancer",
    "S3 write requests": "storage",
    "S3 read requests": "storage",
    # Previously unmapped -- fell through to "compute" by default (see
    # _kind_for below), which folded their cost into the compute box and
    # meant these services never appeared on the diagram at all.
    "CDN data transfer": "network",
    "CDN requests": "network",
    "Transactional email": "email",
    "Queue requests": "queue",
    "Notifications": "notification",
    # Serverless. "API Gateway" must be checked before the plain prefixes it
    # would otherwise fall through on, and each DynamoDB/Lambda line folds
    # onto one box per service via the summing in build() below.
    "Lambda requests": "lambda",
    "Lambda duration": "lambda",
    "API Gateway requests": "apigateway",
    "DynamoDB reads": "dynamodb",
    "DynamoDB writes": "dynamodb",
    "DynamoDB storage": "dynamodb",
    "Rekognition images": "rekognition",
    "Comprehend sentiment": "comprehend",
    "IoT Core messages": "iot",
    "Timestream writes": "timestream",
    "Timestream storage": "timestream",
    "Firehose delivery": "firehose",
    "Athena data scanned": "athena",
    "Glue ETL": "glue",
    # Was falling through to the "compute" default -- harmless-looking on a
    # server diagram (its $0.40 quietly summed onto the compute box) but on a
    # serverless one it MANUFACTURED an EC2 box, and an EC2 box in a subnet
    # dragged a whole VPC in with it. Secrets Manager is a real service; it
    # gets its own node.
    "Secrets": "secrets",
}


@dataclass(frozen=True, slots=True)
class Node:
    id: str
    label: str
    kind: str  # client | network | loadbalancer | compute | database | storage
    monthly_usd: Decimal
    sku: str = ""
    detail: str = ""  # "t4g.large × 3"
    priced: bool = True
    optimized_by: tuple[str, ...] = ()  # technique ids that touched this node

    def share_of(self, total: Decimal) -> float:
        """Fraction of the bill. Drives border weight in the diagram —
        the expensive node should look expensive."""
        if not total:
            return 0.0
        return float(self.monthly_usd / total)


@dataclass(frozen=True, slots=True)
class Edge:
    source: str
    target: str
    label: str = ""


@dataclass(slots=True)
class Topology:
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    @property
    def total_monthly(self) -> Decimal:
        return sum((n.monthly_usd for n in self.nodes), Decimal(0))

    def node(self, node_id: str) -> Node | None:
        return next((n for n in self.nodes if n.id == node_id), None)


def _kind_for(item: LineItem) -> str:
    for prefix, kind in _KIND_BY_PREFIX.items():
        if item.label.startswith(prefix):
            return kind
    return "compute"


def _detail_for(item: LineItem, spec: ArchitectureSpec, kind: str) -> str:
    if kind == "compute":
        parts = [item.sku, f"× {spec.compute_count}"]
        if spec.compute_duty_cycle < 1.0:
            parts.append(f"@ {spec.compute_duty_cycle:.0%}")
        return " ".join(parts)
    if kind == "compute_fargate":
        return (
            f"{spec.fargate_task_count} task(s), "
            f"{spec.fargate_task_vcpu:g} vCPU / {spec.fargate_task_memory_gb:g} GB"
        )
    if kind in ("database", "database_replica"):
        return item.sku
    if kind in ("storage", "network"):
        return f"{item.quantity:g} GB"
    if kind == "waf":
        return f"{spec.waf_rule_count} rules, {spec.waf_monthly_requests:,.0f} req/mo"
    return item.sku


# Effect keys, mapped to the node they alter. Lets the diagram mark which boxes
# a technique actually touched, rather than listing techniques separately.
_EFFECT_TARGETS = {
    "arch": "compute",
    "use_spot": "compute",
    "compute_duty_cycle": "compute",
    "database_arch": "database",
    "database_multi_az": "database",
}


# What the estimator calls a gap, and which node it belongs to.
#
# These strings come from Estimate.missing, which is written for a human to
# read -- "load balancer" with a space, "egress" rather than "network". A
# node kind cannot be recovered by looking for the kind's own name inside
# them, so the phrases are matched explicitly. Getting this wrong does not
# raise; it silently drops the component from the diagram, which is how a
# provider that prices one service out of seven ended up looking like a
# three-box architecture.
_LABELS = {
    "loadbalancer": "Load balancer",
    "storage": "Object storage",
    "network": "Egress",
    "cache": "Cache",
    "monitoring": "Monitoring",
    "database": "Database",
    "database_replica": "Database read replica",
    "compute": "Compute",
    "compute_fargate": "Fargate compute",
    "email": "Transactional email",
    "queue": "Queue",
    "notification": "Notifications",
    "lambda": "AWS Lambda",
    "apigateway": "API Gateway",
    "dynamodb": "DynamoDB",
    "secrets": "Secrets Manager",
    "rekognition": "Amazon Rekognition",
    "comprehend": "Amazon Comprehend",
    "iot": "AWS IoT Core",
    "timestream": "Amazon Timestream",
    "firehose": "Kinesis Data Firehose",
    "athena": "Amazon Athena",
    "glue": "AWS Glue",
    "waf": "AWS WAF",
    "audit": "Audit logging",
    "kms": "KMS keys",
    "nat": "NAT gateway",
    "tls": "TLS certificate",
    "dns": "DNS",
    "auth": "Authentication",
    "backup": "Backup storage",
    "streaming": "Event stream",
    "kafka": "Managed Kafka",
    "search": "Search cluster",
    "warehouse": "Data warehouse",
    "threat": "Threat detection",
    "tracing": "Distributed tracing",
    "posture": "Security posture",
    "flowlogs": "VPC flow logs",
}

_MISSING_PHRASES: tuple[tuple[str, str], ...] = (
    ("load balancer", "loadbalancer"),
    ("object storage", "storage"),
    ("monitoring", "monitoring"),
    ("database read replica", "database_replica"),
    ("database", "database"),
    ("compute", "compute"),
    ("storage", "storage"),
    ("egress", "network"),
    ("cache", "cache"),
    ("aws waf", "waf"),
    ("audit logging", "audit"),
    ("kms", "kms"),
    ("nat gateway", "nat"),
    ("tls certificate", "tls"),
    ("dns hosted zone", "dns"),
    ("authentication", "auth"),
    ("backup storage", "backup"),
    ("event streaming", "streaming"),
    ("managed kafka", "kafka"),
    ("search node", "search"),
    ("search storage", "search"),
    ("data warehouse", "warehouse"),
    ("threat detection", "threat"),
    ("distributed tracing", "tracing"),
    ("security posture", "posture"),
    ("vpc flow logs", "flowlogs"),
    ("transactional email", "email"),
    ("queue", "queue"),
    ("notification", "notification"),
    ("api gateway", "apigateway"),
    ("lambda", "lambda"),
    ("dynamodb", "dynamodb"),
    ("rekognition", "rekognition"),
    ("comprehend", "comprehend"),
    ("iot core", "iot"),
    ("timestream", "timestream"),
    ("firehose", "firehose"),
    ("athena", "athena"),
    ("glue", "glue"),
)


def _first_present(present: set[str], *candidates: str) -> str | None:
    """The first of `candidates` that exists in the diagram, or None.

    The request path is a chain of optional hops: traffic meets DNS, then a
    WAF, then a CDN, then a load balancer, then compute -- but any of them
    may be absent, and each hop connects to the next one that IS there.
    Written inline that was a chain of ternaries per hop, repeated four
    times, which is exactly as hard to read as it sounds.
    """
    return next((kind for kind in candidates if kind in present), None)


def _kind_for_missing(missing: str) -> str | None:
    text = missing.lower()
    for phrase, kind in _MISSING_PHRASES:
        if phrase in text:
            return kind
    return None


def build(
    spec: ArchitectureSpec,
    estimate: Estimate,
    applied: tuple = (),
) -> Topology:
    """Nodes and edges for one priced option.

    `applied` is the option's AppliedTechnique tuple; each one is attributed to
    the node its effect changed, so the interface can put a mark on the box
    rather than only in a list underneath.
    """
    topology = Topology()

    # Which node did each technique change?
    touched: dict[str, list[str]] = {}
    for entry in applied:
        for key in entry.technique.effect:
            kind = _EFFECT_TARGETS.get(key)
            if kind:
                touched.setdefault(kind, []).append(entry.technique.id)

    # Everything that was actually priced becomes a node. Most categories
    # produce exactly one line item, but WAF prices a Web ACL, its rules and
    # its request volume as three separate items that are still one box on
    # the diagram -- so a kind seen again is summed onto its existing node
    # rather than overwriting it, which would have kept only the last of the
    # three prices and silently dropped the other two from the total.
    by_kind: dict[str, Node] = {}
    for item in estimate.items:
        kind = _kind_for(item)
        if kind in by_kind:
            existing = by_kind[kind]
            by_kind[kind] = replace(
                existing, monthly_usd=existing.monthly_usd + item.monthly_usd
            )
            continue
        node = Node(
            id=kind,
            label=item.label.split(" ×")[0].split(" (")[0],
            kind=kind,
            monthly_usd=item.monthly_usd,
            sku=item.sku,
            detail=_detail_for(item, spec, kind),
            priced=True,
            # _EFFECT_TARGETS points ARM/spot techniques at "compute" -- a
            # Fargate box is compute too, and would otherwise show no badge
            # for the same optimization an EC2 box gets credited for.
            optimized_by=tuple(dict.fromkeys(
                touched.get(kind, [])
                if kind != "compute_fargate"
                else touched.get("compute_fargate", []) + touched.get("compute", [])
            )),
        )
        by_kind[kind] = node

    # Anything the estimator could not price still belongs on the diagram —
    # drawn as unpriced, never silently omitted.
    for missing in estimate.missing:
        kind = _kind_for_missing(missing)
        if kind and kind not in by_kind:
            by_kind[kind] = Node(
                id=kind,
                label=_LABELS.get(kind, kind.title()),
                kind=kind,
                monthly_usd=Decimal(0),
                detail=missing,
                priced=False,
            )

    # The client is always present and always free — it anchors the flow.
    topology.nodes.append(
        Node(id="users", label="Users", kind="client", monthly_usd=Decimal(0))
    )
    # The draw order, roughly edge -> compute -> data -> async -> ops. A kind
    # absent from this list is built above but never shown, which is how the
    # serverless and messaging services silently vanished from the diagram
    # while still appearing on the bill -- so every kind the estimator can
    # produce a line for must have an entry here.
    for kind in ("waf", "network", "apigateway", "loadbalancer",
                 "compute", "compute_fargate", "lambda", "cache",
                 "iot", "firehose",
                 "database", "database_replica", "dynamodb", "timestream",
                 "rekognition", "comprehend", "athena", "glue", "storage",
                 "monitoring", "audit", "kms", "secrets", "nat", "tls", "dns", "auth",
                 "backup", "email", "queue", "notification",
                 "streaming", "kafka", "search", "warehouse",
                 "threat", "tracing", "posture", "flowlogs"):
        if kind in by_kind:
            topology.nodes.append(by_kind[kind])

    # ── edges: request path, then data path ──
    present = set(by_kind)
    entry = _first_present(
        present, "dns", "waf", "network", "loadbalancer", "compute"
    )
    if entry:
        topology.edges.append(Edge("users", entry))

    if "waf" in present:
        nxt = _first_present(present, "network", "loadbalancer", "compute")
        if nxt:
            topology.edges.append(Edge("waf", nxt))

    if "network" in present:
        nxt = "loadbalancer" if "loadbalancer" in present else "compute"
        if nxt in present:
            topology.edges.append(Edge("network", nxt))
        if "storage" in present:
            topology.edges.append(Edge("network", "storage", "assets"))
    elif "storage" in present and "compute" in present:
        topology.edges.append(Edge("compute", "storage", "assets"))

    if "loadbalancer" in present and "compute" in present:
        topology.edges.append(Edge("loadbalancer", "compute"))

    if "compute" in present and "cache" in present:
        topology.edges.append(Edge("compute", "cache"))
    if "compute" in present and "database" in present:
        topology.edges.append(Edge("compute", "database"))
    if "database" in present and "database_replica" in present:
        topology.edges.append(Edge("database", "database_replica", "replicates"))
    if "database" in present and "kms" in present:
        topology.edges.append(Edge("kms", "database", "encrypts"))
    if "dns" in present:
        nxt = _first_present(present, "waf", "network", "loadbalancer")
        if nxt:
            topology.edges.append(Edge("dns", nxt, "resolves"))
    if "compute" in present and "auth" in present:
        topology.edges.append(Edge("compute", "auth", "sign-in"))
    if "storage" in present and "backup" in present:
        topology.edges.append(Edge("storage", "backup", "backs up"))
    # The async buffer sits between compute and the data stores it feeds.
    buffer_kind = _first_present(present, "kafka", "streaming")
    if buffer_kind and "compute" in present:
        topology.edges.append(Edge("compute", buffer_kind, "events"))
        if "database" in present:
            topology.edges.append(Edge(buffer_kind, "database", "writes"))
    for sink in ("search", "warehouse"):
        if sink in present:
            source = buffer_kind or ("compute" if "compute" in present else None)
            if source:
                topology.edges.append(Edge(source, sink, "indexes" if sink == "search" else "loads"))
    # Governance services get NO arrow, deliberately.
    #
    # Threat detection, tracing, posture and flow logs sit below the network
    # and watch everything in it, so an arrow to compute is both arbitrary
    # -- they watch the database too -- and enormous: these were the five
    # longest edges on the canvas, up to 606px each, crossing every row
    # between. AWS's own reference diagrams draw Shield and GuardDuty
    # standing alone for the same reason. Their band says what they do.
    if "compute" in present and "nat" in present:
        topology.edges.append(Edge("compute", "nat", "outbound"))

    return topology
