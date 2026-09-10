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
    # Azure's firewall line is "Web application firewall" -- Application
    # Gateway WAF v2 -- and matched none of the prefixes here, so $367.92 of
    # an Azure estimate was billed with no box on the diagram to show it.
    # Every priced line is meant to be a box and every box a line; a table
    # keyed on one provider's product wording breaks that silently for the
    # other two.
    "Web application firewall": "waf",
    "Cloud Armor": "waf",
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
    # Azure's pool is a warehouse, not a compute tier. Without this it fell
    # through to `compute` and the diagram drew a $4,934/month data warehouse
    # as an application server.
    "Synapse dedicated SQL": "warehouse",
    "BigQuery serverless": "warehouse",
    "Threat detection": "threat",
    "Security posture": "posture",
    "Distributed tracing": "tracing",
    "Telemetry ingestion": "tracing",
    "Security posture checks": "posture",
    "VPC flow logs": "flowlogs",
    "Fargate vCPU": "compute_fargate",
    "Fargate memory": "compute_fargate",
    "Container Instances vCPU": "compute_fargate",
    "Container Instances memory": "compute_fargate",
    "Cloud Run vCPU": "compute_fargate",
    "Cloud Run memory": "compute_fargate",
    "Database storage": "database",
    "Load balancer LCUs": "loadbalancer",
    "Object storage write requests": "storage",
    "Object storage read requests": "storage",
    # Previously unmapped -- fell through to "compute" by default (see
    # _kind_for below), which folded their cost into the compute box and
    # meant these services never appeared on the diagram at all.
    # A CDN IS NOT AN EGRESS METER. These shared the "network" kind with
    # plain egress, so an architecture WITH an edge cache and one without
    # drew the identical box -- and on GCP and Azure that box is already
    # named "Cloud CDN" and "Azure Front Door", which put a CDN on the
    # picture for workloads that had none. Separate kinds, because they are
    # separate architectural decisions.
    "CDN data transfer": "cdn",
    "CDN requests": "cdn",
    "Transactional email": "email",
    "Queue requests": "queue",
    "Notifications": "notification",
    # Serverless. "API Gateway" must be checked before the plain prefixes it
    # would otherwise fall through on, and each DynamoDB/Lambda line folds
    # onto one box per service via the summing in build() below.
    "Lambda requests": "lambda",
    "Lambda vCPU time": "lambda",
    "Lambda duration": "lambda",
    "API Gateway requests": "apigateway",
    "DynamoDB reads": "dynamodb",
    "DynamoDB writes": "dynamodb",
    "DynamoDB storage": "dynamodb",
    # Same node kind, the other clouds' product names for it.
    "Cosmos DB reads": "dynamodb",
    "Cosmos DB writes": "dynamodb",
    "Cosmos DB storage": "dynamodb",
    "Firestore reads": "dynamodb",
    "Firestore writes": "dynamodb",
    "Firestore storage": "dynamodb",
    "Rekognition images": "rekognition",
    "Comprehend sentiment": "comprehend",
    "IoT Core messages": "iot",
    "Timestream writes": "timestream",
    "Timestream storage": "timestream",
    "Firehose delivery": "firehose",
    "Athena data scanned": "athena",
    "Synapse serverless SQL data scanned": "athena",
    "BigQuery data scanned": "athena",
    "Glue ETL": "glue",
    "Data Factory": "glue",
    "Dataflow": "glue",
    # Was falling through to the "compute" default -- harmless-looking on a
    # server diagram (its $0.40 quietly summed onto the compute box) but on a
    # serverless one it MANUFACTURED an EC2 box, and an EC2 box in a subnet
    # dragged a whole VPC in with it. Secrets Manager is a real service; it
    # gets its own node.
    "Secrets": "secrets",
    # Five more that were falling through to "compute", found by diffing
    # fingerprints across tier levels. Every one is a distinct
    # ARCHITECTURAL decision, and folding them into the compute box made
    # the fingerprint blind to exactly the differences a tier is supposed
    # to be made of: turning on immutable backups and a cross-region copy
    # did not move the fingerprint at all, so tiers could differ in
    # substance and still read as one design.
    #
    # Object Lock is WORM retention -- the control that makes a backup
    # survive an attacker holding valid credentials. It is not storage.
    "Object Lock": "object_lock",
    # A copy in another region is disaster recovery, not more backup.
    # Both meters -- the resting copy and the transfer that fills it --
    # belong to one decision, so they share one node.
    "Cross-region backup copy": "backup_dr",
    "Cross-region backup transfer": "backup_dr",
    # A cold tier is a different storage class with different retrieval
    # behaviour and a different failure mode, not a bigger bucket.
    "Archived retention": "archive",
    # An organisation-level SCP is a governance control, not a server.
    "Region-deny guardrail": "guardrail",
    # VPC endpoints are private routes into AWS services -- the reason a
    # NAT gateway is not processing that traffic. They were reading as
    # compute, which put their cost on the application box and hid the
    # decision that removed it from NAT. Gateway (free) and interface
    # (hourly + per-GB) endpoints are one architectural choice, so they
    # share a node.
    "Gateway endpoints": "vpc_endpoints",
    "Interface endpoints": "vpc_endpoints",
    "Interface endpoint data processing": "vpc_endpoints",
    # The four billing dimensions that did not exist before. Each is its
    # own node, because each is its own decision: an event bus is not a
    # queue, a connection held open is not a request, and a model endpoint
    # is not an application server.
    "Event bus": "eventbus",
    "Connection minutes": "connections",
    "Connection messages": "connections",
    "Model endpoint": "inference",
    # A disk attached to an instance is not the same node as an
    # object store, and a rehosted estate is mostly disk.
    "Block storage": "block_storage",
}


#: Roles present on every design by POLICY rather than because the workload
#: asked for them. They are exempt from justifying themselves individually --
#: the policy IS the reason, and repeating it on eleven nodes would drown the
#: ones that carry real derivation.
#:
#: Kept SHORT and explicit. The longer this list, the less the `because`
#: requirement proves: anything on it is a default that has been blessed
#: rather than earned.
#: THE THREE PLANES. Fixing the graph model, before any layout.
#:
#: DATA    things a request actually flows through. Directed edges, and
#:         the only plane worth animating -- a request path is a sequence,
#:         and animating a security control alongside it implies the
#:         request passes through GuardDuty, which it does not.
#: CONTROL services BOUND to a specific data-plane node: the key that
#:         encrypts that database, the certificate that terminates on
#:         that load balancer. Attachment lines, not arrows.
#: ACCOUNT services that watch or govern the whole account and belong to
#:         no node in particular. CloudTrail does not attach to the
#:         database; it records every API call in the account. Drawn as a
#:         labelled band with NO EDGES AT ALL, because any edge drawn
#:         from them would be an invented relationship.
#:
#: The old graph had one plane, so the second and third had nowhere to go
#: and were rendered as unconnected boxes -- which reads as "we forgot to
#: join these up" rather than "these do not join up".
DATA_PLANE = "data"
CONTROL_PLANE = "control"
ACCOUNT_PLANE = "account"

PLANES = (DATA_PLANE, CONTROL_PLANE, ACCOUNT_PLANE)

#: Node kind -> plane. Anything absent is DATA, because a service that
#: carries a request is the default and the exceptions are enumerable.
_PLANE_BY_KIND: dict[str, str] = {
    # ── control: attached to one specific node ──
    "kms": CONTROL_PLANE,
    "secrets": CONTROL_PLANE,
    "tls": CONTROL_PLANE,
    "auth": CONTROL_PLANE,
    "backup": CONTROL_PLANE,
    "backup_dr": CONTROL_PLANE,
    "object_lock": CONTROL_PLANE,
    "archive": CONTROL_PLANE,
    "vpc_endpoints": CONTROL_PLANE,
    # ── account: watches everything, attaches to nothing ──
    "audit": ACCOUNT_PLANE,
    "threat": ACCOUNT_PLANE,
    "posture": ACCOUNT_PLANE,
    "flowlogs": ACCOUNT_PLANE,
    "monitoring": ACCOUNT_PLANE,
    "tracing": ACCOUNT_PLANE,
    "guardrail": ACCOUNT_PLANE,
}

#: Which data-plane node a control-plane service attaches to, in order of
#: preference. The first one PRESENT wins; a control service whose subject
#: is absent is attached to nothing rather than to something arbitrary.
_CONTROL_ATTACHES_TO: dict[str, tuple[str, ...]] = {
    # A key encrypts stored data, so it binds to the store -- not to the
    # compute that happens to call it.
    "kms": ("database", "dynamodb", "storage", "search", "block_storage"),
    # Secrets are read by whatever runs the application.
    "secrets": ("compute", "compute_fargate", "lambda", "inference"),
    # A certificate terminates on whatever faces the internet.
    "tls": ("cdn", "loadbalancer", "apigateway", "connections", "storage"),
    # Identity sits in front of the thing users reach.
    "auth": ("apigateway", "loadbalancer", "cdn", "compute", "connections"),
    # Backups are OF a store.
    "backup": ("database", "storage", "dynamodb", "block_storage"),
    "backup_dr": ("backup", "database", "storage", "dynamodb"),
    "object_lock": ("backup", "storage"),
    "archive": ("storage",),
    # Endpoints are the private route OUT of the compute that uses them.
    "vpc_endpoints": ("compute", "compute_fargate"),
}


#: How a standby region's line items are marked when merged into a
#: tier's bill. Mirrors plan._merge_standby and fingerprint._STANDBY_MARKER
#: -- three places that must agree on one string, so it is written once
#: in each and asserted equal by a test.
_STANDBY_MARKER = "(standby"


def plane_for(kind: str) -> str:
    """Which plane a node kind belongs to. Data is the default.

    A standby node sits in the same plane as the primary it mirrors: a
    standby database is still a database.
    """
    base = kind.split("@", 1)[0]
    return _PLANE_BY_KIND.get(base, DATA_PLANE)


BASELINE_KINDS = frozenset(
    {
        "client", "dns", "tls", "auth", "kms", "secrets",
        "monitoring", "tracing", "audit", "threat", "posture",
        "flowlogs", "backup",
    }
)


def _because(kind: str, spec: "ArchitectureSpec", requirement=None) -> str:
    """Why this role is in the architecture, in terms of what was described.

    Traced to the SPEC rather than to the tier, because the spec is what the
    requirement produced. A reason that said "the top tier adds this" would
    describe the code rather than the workload, and is exactly the kind of
    non-answer that let defaults through.
    """
    reasons: dict[str, str] = {
        "compute": (
            f"{spec.compute_count} instance(s) sized to the stated load; "
            "something has to serve the requests"
        ),
        "compute_fargate": (
            f"{spec.fargate_task_count} container task(s): work that runs and "
            "finishes, so nothing is kept warm between runs"
        ),
        "lambda": "event-driven work that scales to zero between invocations",
        "apigateway": "the front door for a serverless backend with no load balancer",
        "loadbalancer": "more than one instance to distribute across, and a health check to fail out of",
        "cdn": "public readers of the same content, cached at the edge rather than fetched from the origin each time",
        "waf": "a public attack surface named in the requirement",
        "database": "relational records the workload reads and writes transactionally",
        "database_replica": (
            f"{spec.database_read_replicas} read replica(s) to take reporting "
            "load off the primary"
        ),
        "dynamodb": "key-value access, so a relational engine would be paid for and not used",
        "timestream": "append-only time-series data, which does not belong in a relational store",
        "cache": "repeated reads that would otherwise hit the primary every time",
        "storage": f"{spec.storage_gb:g} GB of objects to keep",
        "warehouse": "analytics queried repeatedly, rather than re-scanned from the lake each run",
        "athena": "ad-hoc queries over the lake, billed per scan rather than by a running cluster",
        "glue": "the transform step between the raw data and what analysts query",
        "search": "full-text or faceted search, which a relational LIKE cannot serve at this size",
        "queue": "bursty arrivals buffered so the processor is not sized for the peak",
        "streaming": "a continuous event feed rather than discrete requests",
        "kafka": "a continuous event feed rather than discrete requests",
        "firehose": "events delivered to storage without a consumer to run",
        "iot": "devices connecting directly, which need a broker rather than a load balancer",
        "email": "transactional mail the workload sends",
        "notification": "the requirement names notifying someone when work completes",
        "nat": "private instances that still need outbound access",
        # Egress is a meter rather than a component, but it is on the diagram
        # and on the bill, so it explains itself like everything else. Making
        # it baseline would have been the easier answer and the wrong one:
        # every exemption is a role that stops having to justify its cost.
        "network": (
            f"{spec.egress_gb:g} GB leaving the cloud each month, billed per GB "
            "and not cached at an edge"
        ),
        "rekognition": "image analysis named in the requirement",
        "comprehend": "text analysis named in the requirement",
    }
    return reasons.get(kind, "")


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
    #: WHY this node is in the architecture, traced to what the requirement
    #: said. Empty only for baseline roles, which are present by policy.
    #:
    #: A role that cannot say why it is here is indistinguishable from a
    #: default that leaked in -- which is how an HR tool for eighty people
    #: acquired a web firewall. The audit scores an unexplained role as a
    #: defect for exactly that reason, so this is not documentation, it is
    #: the thing that makes the derivation checkable.
    because: str = ""
    #: True for roles present by POLICY on every design -- identity, keys,
    #: observability, audit. They are not derived and are not asked to
    #: justify themselves individually.
    baseline: bool = False
    #: WHICH PLANE THIS BELONGS TO. See PLANES below.
    #:
    #: The single most load-bearing field on a diagram, and it did not
    #: exist: every node was drawn as though it sat in the request path,
    #: so eleven of nineteen on a hospital tier-2 had no edge at all and
    #: fell into a disconnected row at the bottom. That row was not a
    #: layout bug. It was three different kinds of thing being drawn as
    #: one kind.
    plane: str = "data"

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
    #: `flow` for a request travelling through, `attaches` for a control
    #: plane service bound to the node it serves.
    #:
    #: They are drawn differently because they mean different things: a
    #: request FLOWS from a load balancer to compute, and KMS does not
    #: flow anywhere -- it is ATTACHED to the database whose volumes it
    #: encrypts. Drawing the second as an arrow implies a request path
    #: that does not exist, and is why the previous graph left them
    #: unconnected rather than connect them wrongly.
    kind: str = "flow"


@dataclass(slots=True)
class Topology:
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    @property
    def total_monthly(self) -> Decimal:
        return sum((n.monthly_usd for n in self.nodes), Decimal(0))

    def node(self, node_id: str) -> Node | None:
        return next((n for n in self.nodes if n.id == node_id), None)


#: Labels that legitimately reach the `compute` default -- the actual
#: compute meters, which have no prefix entry because compute IS the
#: default. Everything else arriving here is an unmapped service, and
#: `unmapped_labels` below exists so a test can say so rather than
#: leaving it to be noticed years later on a diagram.
_LEGITIMATE_COMPUTE = ("Compute", "Instance", "vCPU", "Memory", "Spot")


def _kind_for(item: LineItem) -> str:
    for prefix, kind in _KIND_BY_PREFIX.items():
        if item.label.startswith(prefix):
            return kind
    return "compute"


def unmapped_labels(items) -> list[str]:
    """Line items falling through to the `compute` default that are not
    compute.

    The default is a trap and has been sprung repeatedly: Secrets Manager
    manufactured an EC2 box on a serverless diagram, a Synapse pool drew
    a $4,934/month warehouse as an application server, and Object Lock,
    the cross-region backup copy, the archive tier and the region-deny
    guardrail all summed silently onto the compute node -- which made the
    architecture fingerprint blind to them, so a tier could turn on
    immutable backups and DR and still fingerprint identically to one
    that had neither.

    Returning the offenders rather than raising keeps this a reporting
    tool: a new meter should fail a test, not a user's request.
    """
    out = []
    for item in items:
        if _kind_for(item) != "compute":
            continue
        if any(item.label.startswith(p) for p in _LEGITIMATE_COMPUTE):
            continue
        out.append(item.label)
    return out


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
    if kind in ("storage", "network", "cdn"):
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
    "cdn": "CDN",
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
    # Provider-neutral. This read ("aws waf", "waf") and matched on a label
    # only AWS produces, so Azure's "Web application firewall" line -- $367.92
    # of an Azure estimate -- was billed with no node on the diagram to show
    # it. Every priced line is supposed to be a box and every box a line; a
    # matcher keyed on one provider's product name breaks that for the other
    # two silently.
    ("aws waf", "waf"),
    ("web application firewall", "waf"),
    ("cloud armor", "waf"),
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
    archetype: str = "",
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
        # THE SECOND REGION IS A SECOND SET OF BOXES.
        #
        # A warm standby was being priced -- real instances, a real
        # database, in another geography -- and folded onto the primary's
        # nodes, so tier 3 drew IDENTICALLY to tier 2 on every fixture
        # that had one. The diagram was telling the reader the upgrade
        # bought nothing, while the bill said $144 more.
        #
        # The fingerprint already counts these separately (Part 6);
        # this is the same fix one layer down, so the picture and the
        # fingerprint agree about what the architecture is.
        # ...but NOT for account-plane services. An audit trail in a
        # second region is still one account-wide control, and a second
        # CloudTrail box is noise rather than information -- its cost
        # folds onto the primary, where a reader expects to find it.
        if _STANDBY_MARKER in item.label and plane_for(kind) != ACCOUNT_PLANE:
            kind = f"{kind}@standby"
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
            because=_because(kind, spec),
            baseline=kind in BASELINE_KINDS,
            plane=plane_for(kind),
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
                because=_because(kind, spec),
                baseline=kind in BASELINE_KINDS,
            )

    # The client is always present and always free — it anchors the flow.
    topology.nodes.append(
        Node(
            id="users", label="Users", kind="client", monthly_usd=Decimal(0),
            baseline=True,
        )
    )
    # The draw order, roughly edge -> compute -> data -> async -> ops. A kind
    # absent from this list is built above but never shown, which is how the
    # serverless and messaging services silently vanished from the diagram
    # while still appearing on the bill -- so every kind the estimator can
    # produce a line for must have an entry here.
    # ORDER, NOT MEMBERSHIP. The tuple below decides what is drawn FIRST;
    # everything else follows in a stable order after it.
    #
    # This used to decide membership too, and that made it a
    # hand-maintained list of every kind that exists -- so the nine kinds
    # added since (block storage, the event bus, connection metering, a
    # model endpoint, object lock, the DR copy, the archive tier, VPC
    # endpoints, the region guardrail) were priced, were in `by_kind`,
    # and were NEVER DRAWN. They appeared on the bill and not on the
    # picture, which is the exact failure the comment above this warns
    # about, reintroduced by the mechanism meant to prevent it.
    #
    # Same class of bug as _kind_for's `compute` fallback: a list that
    # must be updated by hand is a list that will not be.
    _DRAW_FIRST = (
        "waf", "cdn", "network", "apigateway", "connections",
        "loadbalancer", "compute", "compute_fargate", "lambda", "inference",
        "cache", "iot", "firehose",
        "database", "database_replica", "dynamodb", "timestream",
        "block_storage", "rekognition", "comprehend", "athena", "glue",
        "storage", "eventbus", "queue", "notification", "email",
        "streaming", "kafka", "search", "warehouse",
        "monitoring", "audit", "kms", "secrets", "nat", "vpc_endpoints",
        "tls", "dns", "auth", "backup", "backup_dr", "object_lock",
        "archive", "guardrail", "threat", "tracing", "posture", "flowlogs",
    )
    ordered = [k for k in _DRAW_FIRST if k in by_kind]
    ordered += sorted(k for k in by_kind if k not in _DRAW_FIRST)
    for kind in ordered:
        topology.nodes.append(by_kind[kind])

    # ── edges: the data plane ──
    present = set(by_kind)

    # AN ARCHETYPE THAT DECLARES ITS OWN REQUEST PATH USES IT.
    #
    # Everything below this branch is web_app's path -- users -> DNS ->
    # WAF -> load balancer -> compute -> database -- and running the
    # other six shapes through it left their real services unconnected.
    # An event pipeline's API Gateway, queue, consumers and email all
    # floated with no edges, because none of them is a load balancer or
    # an EC2 instance. The archetype is the only thing that knows how a
    # request travels through its own shape.
    declared = _declared_flow(archetype)
    if declared:
        # `users` is a synthetic node, not a priced kind, so it is never
        # in `present` -- and requiring it there left it orphaned on
        # every archetype that does have a requester.
        reachable = present | {"users"}
        for source, target, label in declared:
            if source in reachable and target in reachable:
                topology.edges.append(Edge(source, target, label))

        # A SHAPE WITH NO REQUESTER GETS NO REQUESTER BOX.
        #
        # A nightly batch job has no user in its request path -- a
        # schedule starts it. Drawing a "Users" box anyway and leaving it
        # unconnected says the diagram is unfinished; removing it says
        # the truth, which is that nobody is waiting on this one.
        if not any(src == "users" for src, _t, _l in declared):
            topology.nodes = [n for n in topology.nodes if n.id != "users"]

        _attach_control_plane(topology, present)
        _link_standby(topology)
        return topology

    entry = _first_present(
        present, "dns", "waf", "cdn", "network", "loadbalancer", "compute"
    )
    if entry:
        topology.edges.append(Edge("users", entry))

    if "waf" in present:
        nxt = _first_present(present, "cdn", "network", "loadbalancer", "compute")
        if nxt:
            topology.edges.append(Edge("waf", nxt))

    # The CDN sits in front, and serves static assets itself -- that is what
    # it is for. Plain egress is a meter on the way out, not a hop.
    upstream = _first_present(present, "cdn", "network")
    if upstream:
        nxt = "loadbalancer" if "loadbalancer" in present else "compute"
        if nxt in present:
            topology.edges.append(Edge(upstream, nxt))
        if "storage" in present:
            topology.edges.append(Edge(upstream, "storage", "assets"))
    elif "storage" in present and "compute" in present:
        topology.edges.append(Edge("compute", "storage", "assets"))

    if "loadbalancer" in present and "compute" in present:
        topology.edges.append(Edge("loadbalancer", "compute"))

    # Same defect as the NAT edge: keying on "compute" alone orphaned the
    # cache and the database on every Fargate or serverless tier.
    app = next(
        (k for k in ("compute", "compute_fargate", "lambda") if k in present),
        None,
    )
    if app and "cache" in present:
        topology.edges.append(Edge(app, "cache"))
    if app and "database" in present:
        topology.edges.append(Edge(app, "database"))
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
    # web_app's OWN unconnected services. These were priced, drawn, and
    # joined to nothing -- the same disconnected-row symptom, in the one
    # shape that already had a request path.
    if app:
        for sink, label in (
            ("queue", "async work"),
            ("email", "sends"),
            ("notification", "notifies"),
        ):
            if sink in present:
                topology.edges.append(Edge(app, sink, label))
    # Egress is what LEAVES, so it hangs off whatever last touches the
    # user's bytes rather than floating on its own.
    egress_source = _first_present(
        present, "cdn", "loadbalancer", "apigateway", "storage",
    ) or app
    if "network" in present and egress_source:
        topology.edges.append(Edge(egress_source, "network", "egress"))

    # NAT is reached by whatever runs in the private subnet, which is not
    # always `compute`: a Fargate tier has no EC2 node, so keying this on
    # "compute" alone left the NAT gateway as the last orphaned
    # data-plane node on every managed tier.
    outbound_source = next(
        (k for k in ("compute", "compute_fargate", "lambda") if k in present),
        None,
    )
    if outbound_source and "nat" in present:
        topology.edges.append(Edge(outbound_source, "nat", "outbound"))

    _attach_control_plane(topology, present)
    _link_standby(topology)

    return topology


def _declared_flow(archetype: str) -> tuple:
    """The archetype's own request path, if it declared one."""
    if not archetype:
        return ()
    from whichcloud.archetypes import graph_for

    graph = graph_for(archetype)
    return tuple(graph.flow) if graph else ()


def _link_standby(topology: "Topology") -> None:
    """Join each standby component to the primary it mirrors.

    The relationship is REPLICATION, and saying so is the point: a
    standby database is not a second database somebody also runs, it is
    a copy of the first one kept warm in another region. Drawn as its own
    edge kind so the request-path animation skips it -- a request does
    not travel to the standby, which is exactly why it is a standby.
    """
    ids = {n.id for n in topology.nodes}
    for node in list(topology.nodes):
        if "@standby" not in node.id:
            continue
        primary = node.id.split("@", 1)[0]
        if primary in ids:
            topology.edges.append(
                Edge(primary, node.id, "replicates", kind="replicates")
            )


def _attach_control_plane(topology: "Topology", present: set) -> None:
    # ── CONTROL PLANE: attach, do not route ──
    #
    # The account-plane reasoning above is right and was already here.
    # What was missing is the middle case: services that DO belong to one
    # specific node. KMS is not watching the account, it is encrypting
    # THAT database. A certificate terminates on THAT load balancer.
    # Those are real relationships, and leaving them unconnected said
    # "we forgot" when the truth was "this is not a request path".
    #
    # `kind="attaches"` so the renderer can draw them as bindings rather
    # than arrows, and so the request-path animation can skip them: a
    # request does not travel through a key.
    for control_kind, subjects in _CONTROL_ATTACHES_TO.items():
        if control_kind not in present:
            continue
        subject = next((s for s in subjects if s in present), None)
        if subject is None:
            # Its subject is absent, so there is nothing true to attach
            # it to. Better unattached than attached to whatever happens
            # to be on the canvas.
            continue
        topology.edges.append(
            Edge(control_kind, subject, _ATTACHMENT_LABEL.get(control_kind, ""),
                 kind="attaches")
        )


#: What a control-plane service DOES to the node it attaches to. The verb
#: is the point: "encrypts" and "backs up" are different relationships,
#: and an unlabelled binding is just a line.
_ATTACHMENT_LABEL: dict[str, str] = {
    "kms": "encrypts",
    "secrets": "supplies credentials",
    "tls": "terminates TLS",
    "auth": "authenticates",
    "backup": "backs up",
    "backup_dr": "copies off-region",
    "object_lock": "makes immutable",
    "archive": "tiers to archive",
    "vpc_endpoints": "private route out",
}
