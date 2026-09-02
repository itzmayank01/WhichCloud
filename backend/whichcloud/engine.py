"""The engine: requirements in, priced architectures out.

    Requirement -> sizing -> three shapes -> techniques applied -> priced

Two things are worth understanding before reading further.

**The sizing rules below are engineering judgement, not measured data.** Every
price in this project is fetched from a provider and validated against a second
source. The heuristics here are not: they are conventional starting points, and
they are collected in one table so they can be argued with, tuned, and replaced
by real load data later. They are labelled as heuristics everywhere they
surface. Do not let them borrow the credibility of the pricing layer.

**Savings are measured, never claimed.** A technique changes the architecture;
the estimator prices both versions against real catalogs; the difference is the
saving. Nothing sums the `typical_pct` values from the knowledge base, because
those are neither independent nor additive.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from decimal import Decimal

from .estimator import ArchitectureSpec, Estimate, LineItem, estimate
from .knowledge import Match, Technique, load_techniques, match_all, rejected
from .requirements import Requirement

# ── sizing heuristics ───────────────────────────────────────────────────
#
# HEURISTIC, NOT MEASURED. Conventional starting points for a workload of each
# size. Replace with observed utilisation as soon as real data exists.

# traffic_scale -> (instances, vCPU each, GB each)
BASE_SIZING: dict[str, tuple[int, int, float]] = {
    "low": (1, 2, 4.0),
    "medium": (2, 2, 8.0),
    "high": (4, 4, 16.0),
}

# Spiky traffic needs headroom for the peak, since scaling is not instant.
SPIKE_INSTANCE_MULTIPLIER = 1.5

# ── volume-derived sizing ───────────────────────────────────────────────
#
# BASE_SIZING is a floor, not the answer. Read alone it put 50 million
# transactions a day on the same four instances as 500,000, because
# traffic_scale has three buckets and everything above "hundreds of
# thousands" lands in the top one. Where a description states a volume,
# the shape is computed from it and the table only sets the minimum.
#
# The rates below are judgement. The arithmetic built on them is not, and
# that is the point: doubling the stated load doubles the capacity.

#: Requests one application vCPU serves per second. Conservative for a
#: CRUD/billing workload doing real database work per request. HEURISTIC.
RPS_PER_VCPU = 50.0

#: Transactions one database vCPU sustains, counting the reads a typical
#: request does around each write. HEURISTIC.
TPS_PER_DB_VCPU = 25.0

#: Real instance sizes, so a computed requirement snaps to something a
#: provider actually sells rather than to "7 vCPU".
VCPU_STEPS = (2, 4, 8, 16, 32, 48, 64, 96)

#: Past this many instances, scale up rather than out: a hundred small
#: machines cost more to run and to reason about than a dozen large ones.
MAX_INSTANCES = 12


def _snap_vcpu(needed: float) -> int:
    """The smallest real instance size that covers `needed`."""
    for step in VCPU_STEPS:
        if step >= needed:
            return step
    return VCPU_STEPS[-1]


def peak_rps_for(requirement: Requirement) -> float:
    """Peak requests per second implied by the stated daily volume.

    Zero when the description gives no number -- the caller then keeps the
    tier's floor rather than sizing from an invented figure.
    """
    daily = requirement.daily_transactions or 0
    if not daily:
        return 0.0
    return (daily / 86_400) * PEAK_MULTIPLIER

# Databases are sized below the app tier for typical CRUD workloads.
DB_SIZING: dict[str, tuple[int, float]] = {
    "low": (2, 4.0),
    "medium": (2, 8.0),
    "high": (4, 16.0),
}

# Read replicas ease read-heavy pressure -- dashboards, reporting, live
# inventory lookups -- without adding write capacity the primary does not
# need. Offered only on "Most reliable": a replica is a reliability/scale
# feature, the same tier Multi-AZ already belongs to, not a default every
# tier pays for. HEURISTIC, like the rest of this table.
DB_READ_REPLICAS: dict[str, int] = {"low": 0, "medium": 0, "high": 2}

# WAF is a security control, not a reliability tier -- a workload that named
# an attack surface needs protecting on Cheapest as much as on Most reliable,
# so unlike read replicas this applies to the base shape every tier inherits.
# A starter rule set (managed groups plus a handful of custom rules) and
# request volume scaled like everything else in this table. HEURISTIC.
WAF_RULE_COUNT = 10
WAF_MONTHLY_REQUESTS: dict[str, float] = {
    "low": 1_000_000.0,
    "medium": 10_000_000.0,
    "high": 100_000_000.0,
}

# DNS lookups and sign-ins per traffic tier. Both feed graduated rates, so
# these decide whether a workload sits inside a free allowance or past it --
# which is the difference between $0 and a real line for authentication.
# HEURISTIC, like everything else in this section.
DNS_MONTHLY_QUERIES: dict[str, float] = {
    "low": 1_000_000.0,
    "medium": 10_000_000.0,
    "high": 100_000_000.0,
}
AUTH_MONTHLY_ACTIVE_USERS: dict[str, float] = {
    "low": 1_000.0,
    "medium": 25_000.0,
    "high": 250_000.0,
}

# ── data pipeline & analytics sizing ──
#
# A Kinesis shard takes 1 MB/s or 1,000 records/s inbound. Sizing from the
# stated transaction rate is therefore arithmetic rather than a guess: the
# shard count is ceil(peak records per second / 1000), with a floor of one
# and headroom for the peak because retail traffic is not flat across the
# day. What remains heuristic is the peak multiplier, not the shard maths.
STREAM_RECORDS_PER_SHARD = 1_000
STREAM_PEAK_MULTIPLIER = 4.0  # daily peak vs. daily mean. HEURISTIC.

#: Above this daily transaction count a queue stops being optional: the
#: database can no longer absorb write bursts directly without either
#: dropping traffic or blocking checkout. Below it, a stream is complexity
#: nobody needs. HEURISTIC.
STREAMING_MIN_DAILY_TRANSACTIONS = 10_000

#: Managed Kafka is preferred over Kinesis only at genuinely large volumes,
#: where its throughput and replay guarantees earn a three-broker minimum.
#: Below this, Kinesis costs a fraction of the same capability. HEURISTIC.
KAFKA_MIN_DAILY_TRANSACTIONS = 1_000_000
KAFKA_MIN_BROKERS = 3

#: Search and warehouse node counts per traffic tier. Two nodes minimum for
#: anything production, because a single search node is a single point of
#: failure holding the index. HEURISTIC.
#: Requests a single Fargate task serves per second before it needs help.
#: Conservative for a CRUD/billing workload on 1 vCPU. HEURISTIC -- the
#: task count derived from it is arithmetic, this number is judgement.
FARGATE_RPS_PER_TASK = 25.0
#: Two minimum, always: one task is a single point of failure, and a
#: service that must survive a zone failure cannot run in one zone.
FARGATE_MIN_TASKS = 2
#: How much of the day sits at peak, and how much busier the peak is than
#: the daily mean. Retail concentrates sharply into evening trading.
PEAK_HOURS_PER_DAY = 4.0
PEAK_MULTIPLIER = 4.0
#: One secret for the database credential; more when there is a stream or
#: warehouse holding its own connection details.
BASE_SECRET_COUNT = 1

# ── metered costs that are never optional ───────────────────────────────
#
# Adapters existed for these and nothing set a quantity, so every estimate
# omitted them. They are not extras: an RDS instance always has provisioned
# storage, an ALB always bills capacity units on top of its hour, and a
# bucket always serves requests. Leaving them at zero understated every
# bill this engine has produced.

#: Provisioned database storage. A transactional store holds far more than
#: the object storage a description usually quotes, so this has its own
#: floor and grows with the transaction rate. HEURISTIC.
DB_STORAGE_FLOOR_GB = 100.0
DB_STORAGE_GB_PER_DAILY_TXN = 0.002

#: One ALB capacity unit covers roughly 25 new connections per second.
#: HEURISTIC in the ratio, arithmetic in what is built on it.
RPS_PER_LCU = 25.0

#: Writes track transactions; reads run well ahead of them, because a page
#: view fetches many more assets than a checkout writes rows. HEURISTIC.
S3_GETS_PER_PUT = 10.0

SEARCH_NODES: dict[str, int] = {"low": 2, "medium": 2, "high": 3}
WAREHOUSE_NODES: dict[str, int] = {"low": 2, "medium": 2, "high": 4}

# ── async messaging volumes ──
#
# One email/notification per transaction is the simplest honest reading of
# "send a confirmation" -- not a guess at open rates or retries. A workload
# that asked for one of these but stated no transaction volume still gets a
# floor rather than a silent zero, the same reasoning stream_shards_for uses
# below: the requirement decided there IS one, volume only decides how big.
EMAILS_PER_TRANSACTION = 1.0
QUEUE_JOBS_PER_TRANSACTION = 1.0
NOTIFICATIONS_PER_TRANSACTION = 1.0
EMAIL_MONTHLY_FLOOR = 500.0
QUEUE_MONTHLY_FLOOR = 1_000.0
NOTIFICATION_MONTHLY_FLOOR = 500.0

# ── threat detection & observability volumes ──
#
# These are production hygiene, on by default like audit logging, not a
# budget-triggered upgrade: a system nobody is watching for intrusions is
# not production-ready however much or little was budgeted. The volumes
# below are HEURISTIC; the rates they multiply are fetched.
TRACING_MONTHLY_TRACES: dict[str, float] = {
    "low": 100_000.0,      # inside X-Ray's free allowance
    "medium": 2_000_000.0,
    "high": 20_000_000.0,
}
#: Security Hub evaluates each enabled control against each resource,
#: continuously. Scales with estate size rather than with traffic.
POSTURE_MONTHLY_CHECKS: dict[str, float] = {
    "low": 50_000.0,
    "medium": 150_000.0,
    "high": 500_000.0,
}
#: Flow log volume tracks the traffic crossing the VPC, so it is derived
#: from egress rather than from a tier lookup.
FLOWLOG_GB_PER_EGRESS_GB = 0.10

SIZING_BASIS = (
    "Sizing is heuristic: conventional starting points per traffic tier, not "
    "measured from your workload. Validate under load before committing."
)


@dataclass(frozen=True, slots=True)
class AppliedTechnique:
    """A technique folded into a spec, with its saving measured.

    `saved` is the difference between pricing the architecture with this
    technique and pricing it with the technique's declared counterfactual —
    what the team would plausibly have chosen otherwise. It is never taken
    from the knowledge base's `typical_pct`.
    """

    match: Match
    saved: Decimal
    counterfactual_sku: str

    @property
    def technique(self) -> Technique:
        return self.match.technique


@dataclass(frozen=True, slots=True)
class Option:
    """One recommended architecture, priced, with its reasoning."""

    label: str  # "Cheapest" | "Most reliable" | "Most optimized"
    rationale: str
    spec: ArchitectureSpec
    estimate: Estimate
    applied: tuple[AppliedTechnique, ...]  # folded in, with measured savings
    advisory: tuple[Match, ...]  # techniques we cannot price but should mention
    baseline_monthly: Decimal  # same shape with no techniques applied

    # What this shape gives up. A cheap option that does not state its cost in
    # reliability is how people get burned.
    tradeoffs: tuple[str, ...] = ()

    @property
    def monthly(self) -> Decimal:
        return self.estimate.total_monthly

    @property
    def measured_saving(self) -> Decimal:
        """Sum of each technique's measured saving against its counterfactual.

        Applied sequentially by the estimator, so these do not double-count:
        each is the difference the technique actually made to this shape.
        """
        return sum((a.saved for a in self.applied), Decimal(0))

    @property
    def saving_pct(self) -> float:
        reference = self.monthly + self.measured_saving
        if not reference:
            return 0.0
        return float(self.measured_saving / reference * 100)

    @property
    def within_budget(self) -> bool | None:
        budget = self.spec_budget
        return None if budget is None else self.monthly <= Decimal(str(budget))

    spec_budget: float | None = None
    #: For spiky workloads, the monthly cost of the SAME architecture with the
    #: spike-headroom compute removed -- i.e. steady-state traffic. The headline
    #: `monthly` provisions the peak (conservative); this is the floor the
    #: autoscaler drops to between spikes. None when traffic is not spiky.
    steady_monthly: "Decimal | None" = None
    #: True when the workload hit its capacity caps before consuming its share
    #: of the budget -- extra budget buys nothing more. Lets the interface say
    #: "sized to your workload; more budget adds no useful capacity" instead of
    #: leaving an unchanged number looking like a bug.
    budget_saturated: bool = False


def size_for(requirement: Requirement) -> tuple[int, int, float]:
    """Instance count and size for a workload.

    The tier table is the floor. When the description states a transaction
    volume the shape is computed from it, so ten times the load really does
    get more capacity instead of the same four machines.
    """
    count, vcpu, memory = BASE_SIZING[requirement.traffic_scale]

    peak = peak_rps_for(requirement)
    if peak:
        total_vcpu = peak / RPS_PER_VCPU
        # Scale out first, then up: past MAX_INSTANCES a bigger machine is
        # cheaper to run and easier to reason about than more of them.
        needed = max(count, math.ceil(total_vcpu / vcpu))
        while needed > MAX_INSTANCES and vcpu < VCPU_STEPS[-1]:
            vcpu = _snap_vcpu(vcpu + 1)
            needed = max(2, math.ceil(total_vcpu / vcpu))
        count = max(count, needed)
        # Memory tracks cores at the usual ratio for an application tier.
        memory = max(memory, float(vcpu) * 2.0)

    if requirement.traffic_pattern == "spiky":
        count = max(count, round(count * SPIKE_INSTANCE_MULTIPLIER))

    # Batch work runs on a schedule; a single worker pool is the usual shape.
    if requirement.is_batch:
        count = max(1, count // 2)

    return count, vcpu, memory


def _spike_headroom_instances(requirement: Requirement) -> int:
    """How many compute instances exist ONLY to absorb the traffic spike.

    The difference between this workload sized as spiky and the same workload
    sized as steady -- exactly the instances SPIKE_INSTANCE_MULTIPLIER added.
    Zero when the workload is not spiky (nothing to show a band for).
    """
    if requirement.traffic_pattern != "spiky":
        return 0
    spiky = size_for(requirement)[0]
    steady = size_for(replace(requirement, traffic_pattern="steady"))[0]
    return max(0, spiky - steady)


def db_size_for(requirement: Requirement) -> tuple[int, float]:
    """Database vCPU and memory for a workload.

    Same rule as the application tier: the table sets a floor, a stated
    volume sets the answer. A database is sized up rather than out, since
    the primary takes every write however many replicas exist.
    """
    vcpu, memory = DB_SIZING[requirement.traffic_scale]

    peak = peak_rps_for(requirement)
    if peak:
        vcpu = max(vcpu, _snap_vcpu(peak / TPS_PER_DB_VCPU))
        # Databases want more memory per core than an app tier: the working
        # set living in RAM is most of what makes them fast.
        memory = max(memory, float(vcpu) * 4.0)

    return vcpu, memory


def fargate_tasks_for(requirement: Requirement) -> tuple[int, int]:
    """Base and peak task counts for the stated transaction volume.

    Arithmetic where the description gives a number: a stated daily
    transaction count becomes a mean rate, a peak multiple of that rate,
    and the task count needed to serve it. Two is the floor regardless,
    because one task cannot survive losing its zone -- which is a
    requirement the description states, not a budget the engine is
    spending.

    Returns (base, peak). They are equal when nothing implies a peak.
    """
    daily = requirement.daily_transactions or 0
    if not daily:
        base = max(FARGATE_MIN_TASKS, BASE_SIZING[requirement.traffic_scale][0])
        return base, base

    mean_rps = daily / 86_400
    peak_rps = mean_rps * PEAK_MULTIPLIER
    needed = math.ceil(peak_rps / FARGATE_RPS_PER_TASK)

    base = max(FARGATE_MIN_TASKS, math.ceil(mean_rps / FARGATE_RPS_PER_TASK))
    peak = max(base, needed)
    return base, peak


def _streaming_ingestion(requirement: Requirement) -> dict:
    """The stream that ingests events -- Kinesis, or Kafka at volume.

    This is the FRONT DOOR for an event-driven workload, not an optimization:
    when a system's reason for existing is to ingest a real-time stream (IoT
    telemetry, clickstream, a payments feed), the stream is how the data
    arrives. Withholding it from the cheaper tiers -- as this once did,
    placing it on the top option only -- left them describing an architecture
    that physically could not do the job the description stated. So it lives
    in the base shape, present on every tier, whenever event streaming is
    required. The dedicated ANALYTICS store behind it is the genuine tier
    upgrade and stays in `_pipeline_delta`.
    """
    if not requirement.needs_event_streaming:
        return {}
    if _wants_kafka(requirement):
        return {
            "kafka_broker_count": KAFKA_MIN_BROKERS,
            "kafka_broker_vcpu": 2,
            "kafka_broker_memory_gb": 8.0,
        }
    return {
        "stream_shards": stream_shards_for(requirement),
        "stream_put_units": float((requirement.daily_transactions or 0) * 30),
    }


def _pipeline_delta(requirement: Requirement) -> dict:
    """The dedicated analytics store, for the top option only.

    The stream that ingests events is in the base shape now (every tier needs
    the front door). What the top tier adds is a store built for aggregation
    -- a warehouse, a search cluster -- behind that stream, so reporting is
    decoupled from the transactional path and keeps working when neither the
    query volume nor the row count would fit on a database read replica. It is
    a different architecture, not a bigger one, which is the distinction the
    tiers are supposed to draw.
    """
    delta: dict = {}

    if requirement.needs_search:
        delta["search_node_count"] = SEARCH_NODES[requirement.traffic_scale]
        delta["search_node_vcpu"] = 2
        delta["search_node_memory_gb"] = 8.0
        delta["search_storage_gb"] = requirement.storage_gb

    if requirement.needs_analytics:
        delta["warehouse_node_count"] = WAREHOUSE_NODES[requirement.traffic_scale]
        delta["warehouse_node_vcpu"] = 2
        delta["warehouse_node_memory_gb"] = 16.0

    return delta


def _wants_kafka(requirement: Requirement) -> bool:
    """Kafka, or Kinesis? Volume decides, and only above a real threshold.

    MSK's smallest sensible production cluster is three brokers -- roughly
    $107/mo at kafka.t3.small -- against a single Kinesis shard at about
    $13. That premium buys replay, ordering and ecosystem compatibility
    that only start to matter at volume, so below the threshold Kinesis is
    the honest default rather than the cheap one.
    """
    return (
        requirement.needs_event_streaming
        and (requirement.daily_transactions or 0) >= KAFKA_MIN_DAILY_TRANSACTIONS
    )


def stream_shards_for(requirement: Requirement) -> int:
    """Shards needed for the stated transaction rate, or 0 if not streaming.

    Derived, not guessed: a shard ingests 1,000 records/second, so the count
    follows from the transaction volume the description actually gave. A
    workload that never asked for streaming gets none regardless of size --
    volume decides how big the stream is, the requirement decides whether
    there is one at all.
    """
    if not requirement.needs_event_streaming:
        return 0
    daily = requirement.daily_transactions or 0
    if daily < STREAMING_MIN_DAILY_TRANSACTIONS:
        return 1  # asked for, but small: the minimum viable stream
    mean_per_second = daily / 86_400
    peak = mean_per_second * STREAM_PEAK_MULTIPLIER
    return max(1, math.ceil(peak / STREAM_RECORDS_PER_SHARD))


#: Above this monthly egress, a workload that serves requests is delivering
#: real content -- media, downloads, a busy site -- and belongs behind a CDN.
#: A video platform pushing hundreds of TB direct from EC2, with no
#: CloudFront in the picture, is not an architecture anyone ships; the whole
#: point of a CDN is to be the thing that serves that traffic.
CDN_EGRESS_THRESHOLD_GB = 1000.0


def _delivery(requirement: Requirement) -> tuple[float, float, float]:
    """Split egress between a CDN and the origin, for content-heavy sites.

    Returns (cdn_gb, origin_egress_gb, cdn_requests). Below the threshold, or
    for a workload that serves nothing, delivery stays direct and no CDN is
    added. Above it, the bytes are attributed to CloudFront -- which is where
    they are actually served -- and origin egress drops to zero: AWS does not
    charge for the origin-to-edge fetch, so inventing a separate origin-egress
    line would overstate the bill for the exact optimization a CDN represents.
    CloudFront's per-GB rate is within a rounding error of direct egress here,
    so this corrects the ARCHITECTURE without inventing a saving the catalog
    cannot substantiate.
    """
    egress = requirement.egress_gb
    # A media/object workload is served THROUGH CloudFront by definition --
    # that is what an object primary means -- so it goes behind a CDN whatever
    # the byte count. Other shapes only earn a CDN once egress is large enough
    # to be real content delivery rather than API responses.
    is_media = requirement.serves_requests and requirement.data_shape == "object"
    if not requirement.serves_requests or (egress < CDN_EGRESS_THRESHOLD_GB and not is_media):
        return 0.0, egress, 0.0
    # One HTTPS request per ~2 MB object delivered -- a coarse, stated
    # approximation, like every volume heuristic here.
    requests = egress / 0.002
    return egress, 0.0, requests


@dataclass(frozen=True, slots=True)
class _PrimaryStore:
    """The store a serving workload keeps its own data in, DERIVED from
    `data_shape` rather than defaulted to a relational database.

    This is the heart of "derived, not templated": a media platform and a
    relational shop are the same `web` workload_type, so the old shape gave
    both an RDS instance and they came out as the same architecture. The data
    they hold is not the same, so the store they need is not the same.

      has_rds   a managed SQL primary the tier ladder acts on (Multi-AZ, read
                replicas, an ElastiCache in front). Only relational stores get
                those levers; a key-value or object store scales differently.
      stateful  there is application data at rest here that must be encrypted,
                have its secrets held and its users authenticated. A pure
                media/CDN origin is not stateful in this sense -- it serves
                bytes from S3 and holds no relational session state.
    """

    kind: str
    fields: dict
    has_rds: bool
    stateful: bool
    reason: str


def _store_for(requirement: Requirement) -> _PrimaryStore:
    """Route the primary store from `data_shape`. Never relational by default.

    A workload that serves no requests (batch, ML, bulk storage) keeps no
    serving store at all -- the same rule `needs_database` encoded before,
    preserved here so those shapes are unchanged.
    """
    if not requirement.needs_database:
        return _PrimaryStore(
            "none", {}, has_rds=False, stateful=False,
            reason="a batch/storage workload serves no requests and keeps no online database",
        )

    shape = requirement.data_shape
    daily = requirement.daily_transactions or 0

    if shape in ("relational", "mixed"):
        db_vcpu, db_memory = db_size_for(requirement)
        return _PrimaryStore(
            "relational",
            {"database_vcpu": db_vcpu, "database_memory_gb": db_memory},
            has_rds=True, stateful=True,
            reason="records with relationships and joins — a managed SQL database (RDS)",
        )

    if shape in ("key-value", "document"):
        # DynamoDB stands in for both: the catalog prices it, and it is the
        # honest key-value/document primary. (DocumentDB is not in the
        # catalog; the plan says fall back to DynamoDB rather than invent a
        # rate.) Sized from the stated volume, floored so a real table costs
        # something before traffic.
        return _PrimaryStore(
            "key-value",
            {
                "dynamodb_read_units_per_month": max(
                    LAMBDA_INVOCATIONS_FLOOR, daily * 30 * DYNAMO_READS_PER_TXN
                ),
                "dynamodb_write_units_per_month": max(
                    DYNAMO_STORAGE_FLOOR_GB * 1000, daily * 30 * DYNAMO_WRITES_PER_TXN
                ),
                "dynamodb_storage_gb": max(DYNAMO_STORAGE_FLOOR_GB, requirement.storage_gb),
            },
            has_rds=False, stateful=True,
            reason=(
                "single-key lookups at scale — a DynamoDB table, not a SQL "
                "database it would only bottleneck on"
            ),
        )

    if shape == "object":
        # Media/blobs. S3 IS the primary store (already in the base shape as
        # object storage), served through CloudFront. No relational database
        # exists in this architecture at all -- which is exactly what makes a
        # media platform diverge from a shop.
        return _PrimaryStore(
            "object", {}, has_rds=False, stateful=False,
            reason="media and large objects — served from S3 behind CloudFront, no relational database",
        )

    if shape == "search":
        return _PrimaryStore(
            "search",
            {
                "search_node_count": SEARCH_NODES[requirement.traffic_scale],
                "search_node_vcpu": 2,
                "search_node_memory_gb": 8.0,
                "search_storage_gb": requirement.storage_gb,
            },
            has_rds=False, stateful=True,
            reason="full-text and faceted access is the primary read path — an OpenSearch cluster",
        )

    if shape == "warehouse":
        return _PrimaryStore(
            "warehouse",
            {
                "warehouse_node_count": WAREHOUSE_NODES[requirement.traffic_scale],
                "warehouse_node_vcpu": 2,
                "warehouse_node_memory_gb": 16.0,
            },
            has_rds=False, stateful=True,
            reason="analytics/OLAP over columns, not row-at-a-time OLTP — a Redshift warehouse",
        )

    if shape == "time-series":
        # A serving workload whose data is genuinely time-series (metrics UI,
        # a status board over live readings) routes to Timestream, NEVER a
        # relational store -- the standing rule the extraction prompt states.
        return _PrimaryStore(
            "time-series",
            {
                "timestream_write_gb": max(1.0, requirement.storage_gb * 0.1),
                "timestream_storage_gb": requirement.storage_gb,
            },
            has_rds=False, stateful=True,
            reason="append-only readings by time — Timestream, never a relational store",
        )

    # Unreached: data_shape is a closed Literal. Relational is the honest
    # fallback if a new member is ever added without routing.
    db_vcpu, db_memory = db_size_for(requirement)
    return _PrimaryStore(
        "relational",
        {"database_vcpu": db_vcpu, "database_memory_gb": db_memory},
        has_rds=True, stateful=True,
        reason="relational default",
    )


def base_spec(requirement: Requirement, label: str) -> ArchitectureSpec:
    """The untuned shape for this workload, before any technique applies.

    The primary store is DERIVED from `data_shape` (see `_store_for`), so two
    `web` workloads holding different data no longer collapse to the same
    RDS-backed architecture. Everything that used to gate on `needs_database`
    now gates on what the store actually is: `has_rds` for the SQL-specific
    levers (cache, read replicas, DB storage), `stateful` for the data-at-rest
    concerns (encryption keys, secrets, sign-in).
    """
    count, vcpu, memory = size_for(requirement)
    store = _store_for(requirement)
    has_rds = store.has_rds
    stateful = store.stateful
    cdn_gb, origin_egress_gb, cdn_requests = _delivery(requirement)

    spec = ArchitectureSpec(
        name=label,
        region=requirement.region,
        compute_count=count,
        compute_vcpu=vcpu,
        compute_memory_gb=memory,
        # The primary store is filled from `store.fields` below, derived from
        # data_shape rather than hardcoded to a relational database here.
        database_vcpu=None,
        database_memory_gb=None,
        database_multi_az=False,
        storage_gb=requirement.storage_gb,
        egress_gb=origin_egress_gb,
        cdn_gb=cdn_gb,
        cdn_monthly_requests=cdn_requests,
        serves_requests=requirement.serves_requests,
        # A balancer sits in front of an app tier that serves requests and has
        # more than one instance to balance -- independent of whether that app
        # talks to a SQL database or an object store behind it.
        load_balancer=requirement.serves_requests and count > 1,
        # A read-heavy app in front of a database wants a cache, and anything
        # in production is monitored. Both are heuristic, like the sizing.
        # A cache only where there is enough traffic for one to pay for
        # itself. Low traffic against a small database gets nothing: the
        # smallest node was billing $37.96/mo to memoise queries a site
        # serving 200 visitors a day does not repeat often enough to matter.
        # A cache fronts a RELATIONAL primary under load -- a DynamoDB or
        # OpenSearch store scales on its own and does not take an ElastiCache
        # in front. Held out of the Cheapest tier (see _shape_variants), which
        # accepts hitting the database directly to save the node.
        cache_vcpu=(
            2 if has_rds and requirement.traffic_scale != "low" else None
        ),
        cache_memory_gb=(
            2.0 if has_rds and requirement.traffic_scale != "low" else None
        ),
        monitored_metrics=30 if stateful else 10,
        waf_rule_count=(
            WAF_RULE_COUNT if requirement.needs_waf and requirement.serves_requests else None
        ),
        waf_monthly_requests=(
            WAF_MONTHLY_REQUESTS[requirement.traffic_scale]
            if requirement.needs_waf
            else 0.0
        ),
        # Standard hygiene for anything running in production, not a
        # reliability or scale feature -- every tier gets it, the same way
        # every tier already gets monitoring.
        audit_logging=True,
        kms_key_count=1 if stateful else None,
        # A certificate terminates inbound TLS; a batch job has none.
        tls_certificate=requirement.serves_requests,
        # One NAT gateway per zone the workload spans, so a zone failure
        # does not strand the other zone's outbound traffic. The per-tier
        # count is set in _shape_variants; two is the production default.
        # Data volume is approximated by egress -- HEURISTIC, and the one
        # part of this line that is an estimate rather than a rate.
        nat_gateway_count=2,
        nat_gb_processed=requirement.egress_gb,
        # One zone for the application. Query volume scales with traffic
        # tier; both are HEURISTIC, like the sizing above them.
        # No inbound callers, no public name to resolve.
        dns_hosted_zones=1 if requirement.serves_requests else 0,
        dns_monthly_queries=(
            DNS_MONTHLY_QUERIES[requirement.traffic_scale]
            if requirement.serves_requests
            else 0.0
        ),
        # Sign-in only exists where there are users to sign in. Batch and
        # ML workloads have none, so they get no auth line at all.
        auth_monthly_active_users=(
            AUTH_MONTHLY_ACTIVE_USERS[requirement.traffic_scale]
            if stateful
            else 0.0
        ),
        # Backing up the object store. RDS automated backups are free
        # within retention and are deliberately not double-counted here --
        # see load_backup_prices.
        backup_gb=requirement.storage_gb,
        # Always-on metered costs, sized from the workload.
        db_storage_gb=(
            max(
                DB_STORAGE_FLOOR_GB,
                (requirement.daily_transactions or 0) * DB_STORAGE_GB_PER_DAILY_TXN,
            )
            if has_rds
            else 0.0
        ),
        alb_lcu=(
            max(1.0, peak_rps_for(requirement) / RPS_PER_LCU)
            if requirement.serves_requests
            else 0.0
        ),
        s3_put_requests=float((requirement.daily_transactions or 0) * 30),
        s3_get_requests=float((requirement.daily_transactions or 0) * 30 * S3_GETS_PER_PUT),
        # ── async messaging ──
        # Gated on the requirement first, same as WAF/search/analytics above:
        # a CRUD app that never mentioned email acquires no SES line, however
        # many transactions it does.
        emails_per_month=(
            max(
                EMAIL_MONTHLY_FLOOR,
                (requirement.daily_transactions or 0) * 30 * EMAILS_PER_TRANSACTION,
            )
            if requirement.needs_email
            else 0.0
        ),
        queue_requests_per_month=(
            max(
                QUEUE_MONTHLY_FLOOR,
                (requirement.daily_transactions or 0) * 30 * QUEUE_JOBS_PER_TRANSACTION,
            )
            if requirement.needs_queue
            else 0.0
        ),
        notifications_per_month=(
            max(
                NOTIFICATION_MONTHLY_FLOOR,
                (requirement.daily_transactions or 0) * 30 * NOTIFICATIONS_PER_TRANSACTION,
            )
            if requirement.needs_notifications
            else 0.0
        ),
        # ── data pipeline & analytics ──
        # Kafka only where volume genuinely justifies it; Kinesis otherwise.
        # Both are gated on the requirement first, so no CRUD app acquires a
        # streaming tier it never asked for.
        # The event and analytics pipeline is NOT in the base shape. A
        # requirement like "head office sees live numbers" can be served
        # three different ways, and which one you pick is the architectural
        # decision the tiers exist to express -- see _pipeline_delta.
        # ── threat detection & observability ──
        # On for every tier. GuardDuty prices from the compute and database
        # vCPUs actually present, so this scales with the architecture
        # rather than being a flat add-on.
        # Fargate is opt-in, not the default compute tier. Setting it here
        # while `compute_count` still holds EC2 instances billed BOTH --
        # about $42/mo of compute nobody asked for -- so a caller choosing
        # Fargate must zero compute_count. `fargate_tasks_for` derives the
        # base and peak counts; see scripts/ for the selecting call.
        secret_count=BASE_SECRET_COUNT if stateful else 0,
        threat_detection=True,
        tracing_monthly_traces=TRACING_MONTHLY_TRACES[requirement.traffic_scale],
        # Security Hub is a compliance product, and it was being billed on
        # every architecture regardless. On a bakery's marketing site with
        # no compliance requirement it was $50/mo -- the largest line after
        # the database, for a control nobody asked for and no auditor will
        # ever read. It now needs a stated regime, or enough traffic that
        # continuous posture checking is a real operational need.
        posture_monthly_checks=(
            POSTURE_MONTHLY_CHECKS[requirement.traffic_scale]
            if requirement.compliance or requirement.traffic_scale in ("high", "very_high")
            else 0.0
        ),
        flowlog_gb=requirement.egress_gb * FLOWLOG_GB_PER_EGRESS_GB,
    )
    # The primary store, derived from data_shape (RDS / DynamoDB / OpenSearch
    # / Redshift / Timestream / none), plus the ingestion stream where the
    # workload is event-driven. Both are part of the base shape -- present on
    # every tier, not a top-tier add-on.
    overrides = {**store.fields, **_streaming_ingestion(requirement)}
    return replace(spec, **overrides) if overrides else spec


# ── serverless sizing ──
# HEURISTIC, like every sizing rule here. A request runs a function that does
# a little database work; the rates below turn a stated transaction volume
# into invocations, request-units and stored bytes. The arithmetic on top of
# them is exact -- double the load, double the numbers.

#: One invocation per stated transaction. The honest floor when a workload
#: asked for serverless but stated no volume -- the requirement decided there
#: IS a function, the volume only decides how busy it is.
LAMBDA_INVOCATIONS_FLOOR = 1_000_000.0
#: A function that does real work but is not a heavy compute job. 150ms at
#: 512MB is a conventional CRUD/API handler.
LAMBDA_AVG_MS = 150.0
LAMBDA_MEMORY_MB = 512.0
#: Reads run ahead of writes -- a request reads several items and writes one,
#: the same asymmetry the S3 GET/PUT ratio already encodes.
DYNAMO_READS_PER_TXN = 3.0
DYNAMO_WRITES_PER_TXN = 1.0
#: Stored data floor, GB. A real table holds something even before traffic.
DYNAMO_STORAGE_FLOOR_GB = 25.0
#: Warm environments the reliability tier keeps ready, to remove cold-start
#: latency from the critical path.
PROVISIONED_CONCURRENCY = 5


def _monthly_invocations(requirement: Requirement) -> float:
    daily = requirement.daily_transactions or 0
    if not daily:
        return LAMBDA_INVOCATIONS_FLOOR
    return max(LAMBDA_INVOCATIONS_FLOOR, float(daily) * 30.0)


def serverless_spec(requirement: Requirement, label: str) -> ArchitectureSpec:
    """The serverless shape: Lambda + API Gateway + DynamoDB, no servers.

    Deliberately NOT `base_spec` with compute zeroed. A serverless
    architecture is a different system, not a smaller one -- there is no
    VPC, no NAT gateway, no load balancer, no standby database, because none
    of those exist in it. Everything it does keep is billed by use, so an
    idle month genuinely costs almost nothing, which is the property the
    shape exists to express.
    """
    invocations = _monthly_invocations(requirement)
    serves = requirement.serves_requests

    return ArchitectureSpec(
        name=label,
        region=requirement.region,
        # No always-on compute or relational database -- the whole point.
        compute_count=0,
        database_vcpu=None,
        # ── the serverless core ──
        lambda_invocations_per_month=invocations,
        lambda_avg_ms=LAMBDA_AVG_MS,
        lambda_memory_mb=LAMBDA_MEMORY_MB,
        apigateway_requests_per_month=invocations if serves else 0.0,
        dynamodb_read_units_per_month=invocations * DYNAMO_READS_PER_TXN,
        dynamodb_write_units_per_month=invocations * DYNAMO_WRITES_PER_TXN,
        dynamodb_storage_gb=max(DYNAMO_STORAGE_FLOOR_GB, requirement.storage_gb),
        # Assets and their egress still live on S3/CloudFront.
        storage_gb=requirement.storage_gb,
        egress_gb=requirement.egress_gb,
        serves_requests=serves,
        # Edge and identity, where the workload faces users.
        dns_hosted_zones=1 if serves else 0,
        dns_monthly_queries=DNS_MONTHLY_QUERIES[requirement.traffic_scale] if serves else 0.0,
        auth_monthly_active_users=(
            AUTH_MONTHLY_ACTIVE_USERS[requirement.traffic_scale] if serves else 0.0
        ),
        tls_certificate=serves,
        waf_rule_count=(
            WAF_RULE_COUNT if requirement.needs_waf and serves else None
        ),
        waf_monthly_requests=(
            WAF_MONTHLY_REQUESTS[requirement.traffic_scale] if requirement.needs_waf else 0.0
        ),
        # Production hygiene that is not server-specific: metrics, tracing,
        # audit, a key, secrets. Priced the same way every tier prices them.
        monitored_metrics=20,
        tracing_monthly_traces=TRACING_MONTHLY_TRACES[requirement.traffic_scale],
        audit_logging=True,
        kms_key_count=1,
        secret_count=BASE_SECRET_COUNT,
        # S3 request volume tracks the same transaction count.
        s3_put_requests=float((requirement.daily_transactions or 0) * 30),
        s3_get_requests=float((requirement.daily_transactions or 0) * 30 * S3_GETS_PER_PUT),
        emails_per_month=(
            max(500.0, invocations * 0.0) if requirement.needs_email else 0.0
        ),
        queue_requests_per_month=(
            invocations if requirement.needs_queue else 0.0
        ),
        notifications_per_month=(
            500.0 if requirement.needs_notifications else 0.0
        ),
    )


def _serverless_variants(
    requirement: Requirement,
) -> list[tuple[str, str, dict, tuple[str, ...]]]:
    """The three serverless options, as deltas from `serverless_spec`.

    The tiers differ BY SERVICE, not only by a warm-capacity number: a
    reliable serverless design adds durable async (SQS) and fan-out/alerting
    (SNS) so a failed or bursty invocation is retried rather than dropped, and
    the optimized one adds edge protection and serverless analytics (Athena +
    Glue) over the data the functions write. Every added service is serverless
    too -- no VPC, no NAT, no server appears -- so the shape stays what it is.
    """
    invocations = _monthly_invocations(requirement)

    # Most reliable: warm capacity, plus a durable async path. SQS absorbs
    # bursts and retries failures; SNS fans out and carries the dead-letter
    # alert. These are the serverless reliability primitives -- the equivalent
    # of the server shape's standby and load balancer.
    reliable: dict = {
        "lambda_provisioned_concurrency": PROVISIONED_CONCURRENCY,
        "queue_requests_per_month": invocations,
        "notifications_per_month": max(500.0, invocations * 0.001),
    }

    # Most optimized: everything reliable buys, plus edge protection and a
    # serverless analytics path (Athena querying S3, Glue cataloguing it) so
    # reporting runs off the data lake instead of scanning DynamoDB. Still no
    # server -- Athena and Glue are serverless, so no VPC is dragged in.
    optimized = dict(reliable)
    optimized["lambda_memory_mb"] = 1024.0
    optimized["athena_tb_scanned_per_month"] = 2.0
    optimized["glue_dpu_hours_per_month"] = 50.0
    if requirement.serves_requests:
        optimized["waf_rule_count"] = WAF_RULE_COUNT
        optimized["waf_monthly_requests"] = WAF_MONTHLY_REQUESTS[requirement.traffic_scale]

    return [
        (
            "Cheapest",
            "Pure pay-per-use: functions scale to zero between requests, so an "
            "idle month costs almost nothing.",
            {},
            (
                "Cold starts add latency to the first request after idle",
                "No provisioned capacity, so a sudden burst warms up as it arrives",
                "No durable queue — a failed invocation is not retried for you",
            ),
        ),
        (
            "Most reliable",
            f"Keeps {PROVISIONED_CONCURRENCY} functions warm and adds a durable "
            "async path — SQS absorbs bursts and retries failures, SNS fans out "
            "and carries the dead-letter alert.",
            reliable,
            (
                f"{PROVISIONED_CONCURRENCY} warmed environments bill around the "
                "clock whether or not traffic needs them — the one always-on "
                "cost in an otherwise pay-per-use design",
                "A queue and topic add moving parts to operate and monitor",
            ),
        ),
        (
            "Most optimized",
            "More memory per function (faster, so less billed duration), warm "
            "capacity, a durable async path, protection at the edge, and "
            "serverless analytics (Athena + Glue) over the data lake.",
            optimized,
            (
                "Higher memory costs more per GB-second but finishes sooner; the "
                "net depends on the workload",
                "A Web ACL and its rules bill whether or not anything is blocked",
                "Athena scans data per query, so reporting cost tracks how much "
                "history each question reads",
            ),
        ),
    ]


# ── managed-AI sizing ──
# HEURISTIC. Each stated prediction is one inference call. A text prediction
# analyses a short document -- 5 Comprehend units (500 characters) is a
# conventional social-post / review length; a real workload restates it.
AI_UNITS_PER_TEXT_PREDICTION = 5.0


def ai_spec(requirement: Requirement, label: str) -> ArchitectureSpec:
    """An AI app: the serverless backend, plus the managed AI services it calls.

    Built ON the serverless core -- an AI feature is reached through an API,
    orchestrated by a function, and its results are stored -- with the
    inference volume priced against the real Rekognition / Comprehend meters.
    The AI call, not a server, is where an AI app's money goes, which is the
    whole reason the generic-compute shape was the wrong answer for it.
    """
    spec = serverless_spec(requirement, label)
    calls = _monthly_invocations(requirement)  # one inference per request

    return replace(
        spec,
        rekognition_images_per_month=calls if requirement.ai_vision else 0.0,
        comprehend_units_per_month=(
            calls * AI_UNITS_PER_TEXT_PREDICTION if requirement.ai_language else 0.0
        ),
    )


def _ai_variants(
    requirement: Requirement,
) -> list[tuple[str, str, dict, tuple[str, ...]]]:
    """The three AI options. Same serverless levers -- the managed AI services
    are pay-per-call and identical across tiers, so what varies is the backend
    that fronts them (warm capacity, protection), exactly as for serverless."""
    variants = _serverless_variants(requirement)
    # Reword the headline so it reads as an AI architecture, keeping the same
    # deltas (the backend is what the tiers tune; the AI calls are fixed).
    caps = []
    if requirement.ai_vision:
        caps.append("image recognition")
    if requirement.ai_language:
        caps.append("sentiment analysis")
    what = " and ".join(caps) or "AI inference"
    relabelled = []
    for label, rationale, delta, tradeoffs in variants:
        if label == "Cheapest":
            rationale = (
                f"Managed AI for {what}, pay-per-call, on a serverless backend "
                "that scales to zero between requests."
            )
        relabelled.append((label, rationale, delta, tradeoffs))
    return relabelled


# ── event-driven / IoT sizing ──
# HEURISTIC. A stated events/day becomes events/month, and the per-event
# sizing turns that into stream shards, function invocations, and bytes
# written to the time-series store. Every figure is an assumption; the
# arithmetic on top of them is not.
EVENT_SIZE_KB = 1.0            # a sensor reading / event payload
TELEMETRY_RETENTION_MONTHS = 12   # how long the append-only history is kept
ATHENA_TB_PER_MONTH = 5.0     # analytics queries scanning the data lake
GLUE_DPU_HOURS = 200.0        # managed ETL cataloguing the stream
EVENT_FLOOR_PER_DAY = 100_000


def _event_volume(requirement: Requirement) -> float:
    daily = requirement.daily_transactions or EVENT_FLOOR_PER_DAY
    return float(daily) * 30.0


def event_driven_spec(requirement: Requirement, label: str) -> ArchitectureSpec:
    """The event pipeline for one tier. A stream processor, NOT a web app.

    The tiers differ BY SERVICE, so this builds each tier's own graph rather
    than one graph at three sizes:

      cheapest   Kinesis -> Lambda (+ Spot workers if the work is restartable)
                 -> Timestream, queried with Athena. Serverless and pay-per-
                 use; Spot where the description says jobs can be rerun.
      balanced   adds Firehose for managed delivery and swaps Lambda for
                 Fargate and adds Glue -- managed where it removes real ops
                 risk, each swap answering a phrase in the description.
      optimized  MSK and IoT Core for device-scale ingest, OpenSearch and
                 Redshift for purpose-built analytics -- the architecture the
                 platform grows into, every choice still right at 10x load.

    Telemetry NEVER lands in a relational database: `telemetry` routes the
    primary store to Timestream, otherwise DynamoDB. RDS is never set.
    """
    events = _event_volume(requirement)
    write_gb = events * EVENT_SIZE_KB / 1_000_000.0
    telemetry = requirement.telemetry

    # The primary store: a purpose-built time-series store for telemetry, a
    # key-value store otherwise. Never RDS.
    store: dict = {}
    if telemetry:
        store["timestream_write_gb"] = write_gb
        store["timestream_storage_gb"] = write_gb * TELEMETRY_RETENTION_MONTHS
    else:
        store["dynamodb_write_units_per_month"] = events
        store["dynamodb_read_units_per_month"] = events * 2
        store["dynamodb_storage_gb"] = max(25.0, write_gb)

    common = dict(
        name=label,
        region=requirement.region,
        compute_count=0,
        database_vcpu=None,          # never a relational primary store
        storage_gb=max(requirement.storage_gb, write_gb),  # the S3 data lake
        egress_gb=requirement.egress_gb,
        serves_requests=requirement.serves_requests,
        # An event pipeline is fronted by an API for control/queries.
        apigateway_requests_per_month=events if requirement.serves_requests else 0.0,
        monitored_metrics=30,
        tracing_monthly_traces=TRACING_MONTHLY_TRACES[requirement.traffic_scale],
        audit_logging=True,
        kms_key_count=1,
        s3_put_requests=events,
        s3_get_requests=events * S3_GETS_PER_PUT,
        **store,
    )

    if label == "Cheapest":
        spec = ArchitectureSpec(
            **common,
            stream_shards=stream_shards_for(requirement) or 1,
            stream_put_units=events,
            athena_tb_scanned_per_month=ATHENA_TB_PER_MONTH,
        )
        # The stream processor. Where the work is restartable the cheapest
        # tier runs it on Spot -- the discount the stated retry tolerance
        # unlocks -- INSTEAD of on-demand Lambda, not on top of it. Otherwise
        # it is serverless Lambda, which scales to zero between bursts.
        if requirement.interruptible:
            count, vcpu, memory = size_for(requirement)
            return replace(
                spec, compute_count=max(1, count // 2),
                compute_vcpu=vcpu, compute_memory_gb=memory, use_spot=True,
            )
        return replace(
            spec,
            lambda_invocations_per_month=events,
            lambda_avg_ms=LAMBDA_AVG_MS,
            lambda_memory_mb=LAMBDA_MEMORY_MB,
        )

    if label == "Most reliable":
        base, _peak = fargate_tasks_for(requirement)
        return ArchitectureSpec(
            **common,
            stream_shards=stream_shards_for(requirement) or 1,
            stream_put_units=events,
            firehose_gb_per_month=write_gb,          # managed delivery to S3
            fargate_task_count=max(2, base),         # managed containers
            fargate_task_vcpu=1.0, fargate_task_memory_gb=2.0,
            athena_tb_scanned_per_month=ATHENA_TB_PER_MONTH,
            glue_dpu_hours_per_month=GLUE_DPU_HOURS,  # managed ETL/catalog
            threat_detection=True,
        )

    # Most optimized
    base, _peak = fargate_tasks_for(requirement)
    return ArchitectureSpec(
        **common,
        kafka_broker_count=KAFKA_MIN_BROKERS,        # managed high-throughput
        kafka_broker_vcpu=2, kafka_broker_memory_gb=8.0,
        iot_messages_per_month=events if telemetry else 0.0,  # device fleet
        fargate_task_count=max(3, base),
        fargate_task_vcpu=1.0, fargate_task_memory_gb=2.0,
        glue_dpu_hours_per_month=GLUE_DPU_HOURS,
        search_node_count=SEARCH_NODES[requirement.traffic_scale],  # dashboards
        search_node_vcpu=2, search_node_memory_gb=8.0,
        search_storage_gb=max(requirement.storage_gb, write_gb),
        warehouse_node_count=WAREHOUSE_NODES[requirement.traffic_scale],  # OLAP
        warehouse_node_vcpu=2, warehouse_node_memory_gb=16.0,
        threat_detection=True,
        posture_monthly_checks=POSTURE_MONTHLY_CHECKS[requirement.traffic_scale],
    )


def _event_driven_variants(
    requirement: Requirement,
) -> list[tuple[str, str, dict, tuple[str, ...]]]:
    """Three event-pipeline options that differ BY SERVICE. The deltas are
    empty: `event_driven_spec` builds each tier's own graph, because a tier
    that swaps Kinesis for MSK is a different architecture, not a bigger one."""
    spot_note = (
        "Restartable workers run on Spot — reclaimable at two minutes' "
        "notice, which the stated retry tolerance accepts"
        if requirement.interruptible else
        "Serverless processing scales to zero between event bursts"
    )
    return [
        (
            "Cheapest",
            "Serverless, pay-per-use pipeline: Kinesis into Lambda into a "
            "time-series store, queried on demand with Athena.",
            {},
            (
                spot_note,
                "Athena scans the raw data lake, so query cost tracks how "
                "much history each question reads",
            ),
        ),
        (
            "Most reliable",
            "Managed where it removes operational risk: Firehose delivers the "
            "stream, Fargate runs the processors, Glue catalogues the data.",
            {},
            (
                "Managed services cost more per unit than self-run, buying back "
                "the operational time self-managing them would take",
            ),
        ),
        (
            "Most optimized",
            "The platform it grows into: MSK and IoT Core for device-scale "
            "ingest, OpenSearch and Redshift for purpose-built analytics.",
            {},
            (
                "MSK and a warehouse run continuously — sized for 10x the "
                "stated load, so they carry cost before that growth arrives",
            ),
        ),
    ]


#: A batch/ETL run scans the raw lake; the warehouse tier loads curated
#: tables instead. Both HEURISTIC, restated by a real workload.
BATCH_ATHENA_TB_PER_MONTH = 5.0
BATCH_GLUE_DPU_HOURS = 150.0


def batch_etl_spec(requirement: Requirement, label: str) -> ArchitectureSpec:
    """A batch/ETL pipeline for one tier — NOT a web app with the database off.

    A nightly ETL job reads from an object lake, transforms on compute that can
    be reclaimed and restarted (that is what makes the work interruptible), and
    lands results a query engine reads. It has no load balancer, no relational
    OLTP database, no cache and no CDN, because nothing calls it over the
    network and nothing serves a user in the request path.

    The tiers differ BY SERVICE, the same way the event-driven shape does:

      cheapest   S3 lake -> Spot EC2 workers -> Athena over the raw files.
                 Reclaimable capacity and pay-per-query; the cheapest way to
                 run work that can simply be rerun.
      balanced   swaps self-run Spot for managed Fargate and adds Glue to
                 catalogue and transform — managed where it removes real ops
                 risk, still querying with Athena.
      optimized  loads a Redshift warehouse for fast repeated analytics
                 instead of re-scanning the lake each time, on managed Fargate
                 with Glue — the shape a data platform grows into.
    """
    daily = requirement.daily_transactions or 0
    # Rows processed per month, floored so an unquantified pipeline still has a
    # real object-request volume rather than zero.
    rows = max(1_000_000.0, daily * 30.0)

    common = dict(
        name=label,
        region=requirement.region,
        database_vcpu=None,          # never a relational primary
        serves_requests=False,       # nothing calls it; no edge, no LB, no CDN
        storage_gb=requirement.storage_gb,   # the S3 data lake
        egress_gb=requirement.egress_gb,
        monitored_metrics=20,
        tracing_monthly_traces=TRACING_MONTHLY_TRACES[requirement.traffic_scale],
        audit_logging=True,
        kms_key_count=1,
        s3_put_requests=rows,
        s3_get_requests=rows * S3_GETS_PER_PUT,
        flowlog_gb=requirement.egress_gb * FLOWLOG_GB_PER_EGRESS_GB,
    )

    if label == "Cheapest":
        # Self-run workers on Spot — the discount interruptible work unlocks —
        # scanning the lake with Athena. Where the work is NOT restartable,
        # on-demand EC2 (Spot is withheld by the technique layer regardless).
        count, vcpu, memory = size_for(requirement)
        return ArchitectureSpec(
            **common,
            compute_count=max(1, count),
            compute_vcpu=vcpu,
            compute_memory_gb=memory,
            use_spot=requirement.interruptible,
            athena_tb_scanned_per_month=BATCH_ATHENA_TB_PER_MONTH,
        )

    if label == "Most reliable":
        base, _peak = fargate_tasks_for(requirement)
        return ArchitectureSpec(
            **common,
            compute_count=0,                   # no EC2; the work runs on Fargate
            fargate_task_count=max(2, base),   # managed containers
            fargate_task_vcpu=1.0, fargate_task_memory_gb=2.0,
            glue_dpu_hours_per_month=BATCH_GLUE_DPU_HOURS,   # managed ETL/catalog
            athena_tb_scanned_per_month=BATCH_ATHENA_TB_PER_MONTH,
            threat_detection=True,
        )

    # Most optimized — Redshift replaces re-scanning the lake with Athena.
    base, _peak = fargate_tasks_for(requirement)
    return ArchitectureSpec(
        **common,
        compute_count=0,                   # no EC2; the work runs on Fargate
        fargate_task_count=max(3, base),
        fargate_task_vcpu=1.0, fargate_task_memory_gb=2.0,
        glue_dpu_hours_per_month=BATCH_GLUE_DPU_HOURS,
        warehouse_node_count=WAREHOUSE_NODES[requirement.traffic_scale],
        warehouse_node_vcpu=2, warehouse_node_memory_gb=16.0,
        threat_detection=True,
        posture_monthly_checks=POSTURE_MONTHLY_CHECKS[requirement.traffic_scale],
    )


def _batch_etl_variants(
    requirement: Requirement,
) -> list[tuple[str, str, dict, tuple[str, ...]]]:
    """Three batch/ETL options that differ BY SERVICE — `batch_etl_spec` builds
    each tier's own graph, so the deltas are empty."""
    spot_note = (
        "Workers run on Spot — reclaimable at two minutes' notice, which a "
        "rerunnable batch job accepts for the discount"
        if requirement.interruptible else
        "Self-run workers on on-demand capacity; the job is not marked "
        "restartable, so reclaimable Spot is withheld"
    )
    return [
        (
            "Cheapest",
            "Self-run workers over an S3 data lake, queried on demand with "
            "Athena. The cheapest way to run work that can simply be rerun.",
            {},
            (
                spot_note,
                "Athena scans the raw lake, so query cost tracks how much data "
                "each run reads",
            ),
        ),
        (
            "Most reliable",
            "Managed where it removes operational risk: Fargate runs the "
            "transforms, Glue catalogues and cleans the data.",
            {},
            (
                "Managed containers and Glue cost more per unit than self-run "
                "Spot, buying back the operational time of running them",
            ),
        ),
        (
            "Most optimized",
            "Loads a Redshift warehouse for fast repeated analytics instead of "
            "re-scanning the lake every run, on managed Fargate with Glue.",
            {},
            (
                "A warehouse runs continuously — sized for 10x the stated load, "
                "so it carries cost before that growth arrives",
            ),
        ),
    ]


def apply_effects(spec: ArchitectureSpec, matched: list[Match]) -> ArchitectureSpec:
    """Fold every priceable technique into the architecture."""
    updates: dict[str, object] = {}
    for match in matched:
        for key, value in match.technique.effect.items():
            updates[key] = value
    return replace(spec, **updates) if updates else spec


def _shape_variants(
    requirement: Requirement,
) -> list[tuple[str, str, dict, tuple[str, ...]]]:
    """The three options, as deltas from the base shape.

    Three, never one: a single "best" is always wrong for someone, and the
    first time it is wrong the user stops trusting the tool.
    """
    # Read replicas, Multi-AZ standby and a fronting cache are RELATIONAL
    # levers -- they act on an RDS primary. A DynamoDB, OpenSearch or object
    # store scales by its own units, so a shape derived to one of those must
    # not acquire a phantom replica or ElastiCache here. `has_rds` gates them;
    # `serves_requests` still gates the balancer, which fronts any app tier.
    has_rds = _store_for(requirement).has_rds
    replicas = DB_READ_REPLICAS[requirement.traffic_scale] if has_rds else 0
    # A balancer only where something is being balanced. The base shape
    # already gates this on the workload serving requests; setting it True
    # here regardless put an Elastic Load Balancing box in front of a
    # nightly batch job that nothing calls.
    reliable_delta: dict = {}
    if has_rds:
        reliable_delta["database_multi_az"] = True
    if requirement.serves_requests:
        reliable_delta["load_balancer"] = True
    if has_rds:
        reliable_rationale = (
            "Survives an availability-zone failure: extra capacity and a "
            "standby database."
        )
        reliable_tradeoffs = [
            "The standby database roughly doubles the largest line on the bill",
            "Still one region — a regional outage is not covered",
        ]
    else:
        # No RDS to stand by: the reliability the tier buys is a balancer and
        # a multi-instance app tier in front of a store (DynamoDB, OpenSearch,
        # S3/CloudFront) that is already multi-AZ by design.
        reliable_rationale = (
            "Survives an availability-zone failure: a load-balanced, "
            "multi-instance app tier in front of a store that is already "
            "replicated across zones."
        )
        reliable_tradeoffs = [
            "More running instances than the cheapest tier",
            "Still one region — a regional outage is not covered",
        ]
    if replicas:
        reliable_delta["database_read_replicas"] = replicas
        reliable_rationale += (
            f" Adds {replicas} read replicas so dashboards and reporting "
            "queries stop competing with checkout writes on the primary."
        )
        reliable_tradeoffs.append(
            f"{replicas} read replicas run around the clock whether or not "
            "reporting traffic is using them"
        )

    # ── Most optimized ──
    #
    # The top tier turns ON every capability the catalog can price that a
    # well-resourced team would actually run -- it does not inflate
    # quantities to reach a number. Read replicas whatever the scale,
    # because the reporting queries that justify them exist at any size;
    # protection at the edge; a cache with room to hold a real working set.
    #
    # What it deliberately does NOT do is spend to a budget. A tier that
    # grew until it consumed a percentage of whatever figure was typed
    # would recommend the same architecture to a blog and to a bank, which
    # is the opposite of optimized.
    optimized_delta: dict = dict(reliable_delta)
    optimized_tradeoffs = list(reliable_tradeoffs)

    if has_rds:
        optimized_delta["database_read_replicas"] = max(2, replicas)
        # The cache tracks the database it fronts rather than jumping to a
        # flat size. Pinned at 4 vCPU it cost $179/mo on a workload doing
        # 0.09 transactions a second -- three times the database it was
        # meant to protect, for capacity nothing would touch. Half the
        # primary's cores, floored at the smallest useful node.
        db_vcpu, _ = db_size_for(requirement)
        # Half the database, but never larger than the traffic warrants --
        # a cache sized purely off the database put a cache.m5.large in
        # front of a site with no load to cache.
        cache_vcpu = max(2, db_vcpu // 2)
        if requirement.traffic_scale in ("low", "medium"):
            cache_vcpu = 2
        optimized_delta["cache_vcpu"] = cache_vcpu
        optimized_delta["cache_memory_gb"] = float(cache_vcpu) * 2.0
        optimized_tradeoffs.append(
            "Read replicas run whether or not the reporting load that "
            "justifies them has arrived yet"
        )

    # Protection at the edge. Priced here even where the description named
    # no attack surface, because this is the tier that assumes one exists.
    if requirement.serves_requests:
        optimized_delta["waf_rule_count"] = WAF_RULE_COUNT
        optimized_delta["waf_monthly_requests"] = WAF_MONTHLY_REQUESTS[
            requirement.traffic_scale
        ]
        optimized_tradeoffs.append(
            "A Web ACL and its rules bill whether or not anything is blocked"
        )

    # A third availability zone. Two survives losing one; three survives
    # losing one while another is being patched, which is the difference
    # between surviving a failure and surviving a failure on a bad day.
    optimized_delta["nat_gateway_count"] = 3
    optimized_tradeoffs.append(
        "A third zone means a third NAT gateway running continuously"
    )

    # The dedicated pipeline, where the description asked for one. This is
    # what makes the top tier a different architecture rather than the same
    # one with bigger machines.
    pipeline = _pipeline_delta(requirement)
    if pipeline:
        optimized_delta.update(pipeline)
        optimized_tradeoffs.append(
            "Reporting runs on its own stream and store rather than on the "
            "database, which is more moving parts to operate"
        )

    return [
        (
            "Cheapest",
            "Smallest footprint that still runs the workload. One instance, no "
            "cache, no standby database — it talks to the primary store "
            "directly and accepts a single point of failure to skip the spend.",
            {
                "compute_count": 1,
                "database_multi_az": False,
                "load_balancer": False,
                # No cache: the cheapest tier hits the primary store directly.
                # The managed cache is a Most-reliable/Most-optimized service,
                # not a smaller version of one -- holding it out here is part
                # of what makes the tiers three different shapes, not three
                # sizes. Harmless where the store never had a cache anyway
                # (DynamoDB/OpenSearch/object), a real saving where it did.
                "cache_vcpu": None,
                "cache_memory_gb": None,
                # One zone, so one gateway -- paying for a second in a zone
                # nothing runs in would be waste, not resilience.
                "nat_gateway_count": 1,
            },
            (
                "Single instance — a restart or crash is downtime",
                "No load balancer, so no room to scale out under load",
                "No cache — every read hits the primary store",
                "Single-zone database — a zone failure takes you offline",
                "One NAT gateway — losing its zone cuts outbound traffic",
            ),
        ),
        (
            "Most reliable",
            reliable_rationale,
            reliable_delta,
            tuple(reliable_tradeoffs),
        ),
        (
            "Most optimized",
            "Everything this workload can actually use: reporting reads taken "
            "off the primary, protection at the edge, and a cache large "
            "enough to keep the database quiet under load.",
            optimized_delta,
            tuple(optimized_tradeoffs),
        ),
    ]


def _what_changed(with_it: Estimate, without_it: Estimate) -> str:
    """Name the SKU this technique replaced.

    Comparing whole estimates and reporting items[0] would credit a database
    technique with beating a compute instance. Find the line that actually
    differs instead.
    """
    chosen = {i.label: i.sku for i in with_it.items}
    for item in without_it.items:
        if chosen.get(item.label) != item.sku:
            return item.sku

    # Same SKUs, different quantities — a duty-cycle change, not a swap.
    for item in without_it.items:
        match = next((i for i in with_it.items if i.label == item.label), None)
        if match and match.quantity != item.quantity:
            return f"{item.sku} at full duty"
    return without_it.items[0].sku if without_it.items else ""


def _apply_techniques(
    spec: ArchitectureSpec,
    matched: list[Match],
    provider: str,
    dsn: str | None,
) -> tuple[ArchitectureSpec, list[AppliedTechnique]]:
    """Fold every priceable technique in, measuring what each one saved.

    Applied one at a time and priced against that technique's own
    counterfactual, so a later technique measures on top of the earlier
    ones and the savings add without double-counting. A technique that
    cannot be priced on both sides, or that turns out to cost more, is
    dropped rather than claimed.
    """
    current = spec
    applied: list[AppliedTechnique] = []

    for match in (m for m in matched if m.technique.is_priceable):
        with_it = replace(current, **match.technique.effect)
        without_it = replace(current, **match.technique.counterfactual)

        priced_with = estimate(with_it, provider, dsn=dsn)
        priced_without = estimate(without_it, provider, dsn=dsn)

        if not priced_with.items or not priced_without.items:
            continue  # cannot measure it, so do not claim it

        saved = priced_without.total_monthly - priced_with.total_monthly
        if saved <= 0:
            continue  # an "optimization" that costs more is not one

        current = with_it
        applied.append(
            AppliedTechnique(
                match=match,
                saved=saved,
                counterfactual_sku=_what_changed(priced_with, priced_without),
            )
        )

    return current, applied


#: Effect keys that buy a lower bill at the cost of availability -- spot
#: capacity that can be reclaimed, and scaling to zero that adds cold-start
#: latency and cannot absorb a sudden spike. A technique touching either is
#: appropriate for the Cheapest tier and wrong for the ones whose whole
#: point is guaranteed capacity.
_AVAILABILITY_TRADING_EFFECTS = frozenset({"use_spot", "compute_duty_cycle"})


def _trades_availability(technique: Technique) -> bool:
    return bool(_AVAILABILITY_TRADING_EFFECTS & set(technique.effect))


# ── budget-driven headroom ───────────────────────────────────────────────
#
# By default the engine sizes from the WORKLOAD and treats budget as a
# pass/fail check (see the "does NOT spend to a budget" note in
# _shape_variants). That is the honest default, but it makes the budget
# field feel inert: raising it changes nothing a user can see.
#
# This function makes budget an active lever, on an explicit request, WITHOUT
# padding into absurdity. The rules that keep it honest:
#
#   * The WORKLOAD sets the floor. Nothing here shrinks a tier below what the
#     traffic needs to run, and Cheapest is left at that floor untouched --
#     it stays the honest minimum, so a tight budget still has a real answer.
#   * Budget only ever buys capacity a well-funded team would actually run:
#     more app instances (burst + resilience), read replicas (read scaling
#     and failover), a larger cache (lower latency), a bigger primary. Never
#     idle quantity for its own sake.
#   * HARD CAPS bound every knob, so a $50k budget on a small workload plateaus
#     at that workload's useful maximum instead of inventing a grotesque
#     fleet. Past the plateau, extra budget correctly changes nothing -- and
#     Option carries `budget_saturated` so the interface can say why.
#   * It never exceeds the budget: each upgrade is priced and kept only if the
#     new total still fits the tier's target share of the budget.
#
# Server web shapes only. Serverless, AI, event-driven and batch shapes scale
# by their own units (concurrency, shards, workers) and are left alone.

#: The share of the stated budget each tier may grow into. Cheapest is absent
#: -- it is never scaled. The upper tiers leave headroom below the budget so
#: the result "fits with room to spare" rather than sitting exactly on it.
_BUDGET_TARGET_FILL: dict[str, float] = {
    "Most reliable": 0.45,
    "Most optimized": 0.85,
}

#: Absolute ceilings on what budget can buy, per knob, PER TIER. These are
#: what stop a large budget on a small workload from ballooning: once every
#: knob is capped the tier is saturated and further budget is inert. The caps
#: are lower for Most reliable than Most optimized so the two tiers stay
#: distinct postures even at a budget large enough to saturate both -- without
#: this they converge on the same maxed-out stack and the tier choice becomes
#: meaningless.
#: The budget-driven total is also capped at a MULTIPLE of the tier's own
#: natural (workload-sized) cost. This is what keeps the plateau defensible:
#: a $50k budget on a workload that naturally costs $1k lands near 2-2.5x
#: that, not at some fixed five-figure ceiling that happens to be where the
#: capacity caps bite. Anchored on the observation that no architect -- human
#: or LLM -- sizes a 50k-user store past a few thousand dollars a month. The
#: fixed capacity caps below still apply as a secondary backstop for genuinely
#: large workloads, where even 2.5x the floor is a lot of money.
_BUDGET_CEILING_MULTIPLE: dict[str, float] = {
    "Most reliable": 1.8,
    "Most optimized": 2.5,
}

_BUDGET_CAPS: dict[str, dict[str, int]] = {
    # Reliability is about surviving a zone failure, not peak throughput:
    # a couple of standbys and a modest cache, not a maxed-out fleet.
    "Most reliable": {"compute": 6, "replicas": 2, "cache_vcpu": 8, "db_vcpu": 16},
    # The top tier is "everything this workload can use": the real ceilings.
    "Most optimized": {"compute": 12, "replicas": 5, "cache_vcpu": 16, "db_vcpu": 32},
}


def _scale_to_budget(
    spec: "ArchitectureSpec",
    requirement: Requirement,
    label: str,
    provider: str,
    dsn: str | None,
) -> tuple["ArchitectureSpec", bool]:
    """Grow an upper-tier spec into its share of the stated budget.

    Returns (spec, saturated). `saturated` is True when every knob hit its
    cap before the budget target was reached -- i.e. the workload cannot
    usefully absorb the money on offer, which is a fact worth surfacing
    rather than hiding behind an unchanged number.
    """
    budget = requirement.budget_monthly_usd
    fill = _BUDGET_TARGET_FILL.get(label)
    if not budget or budget <= 0 or fill is None:
        return spec, False

    budget_target = Decimal(str(budget)) * Decimal(str(fill))
    has_rds = _store_for(requirement).has_rds
    caps = _BUDGET_CAPS[label]

    def priced(candidate: "ArchitectureSpec") -> Decimal:
        return estimate(candidate, provider, dsn=dsn).total_monthly

    # The effective target is the SMALLER of the budget's share and a multiple
    # of the workload's own natural cost. The cost ceiling is what makes the
    # plateau scale with the workload instead of ballooning to wherever the
    # fixed capacity caps happen to sit.
    floor_cost = priced(spec)
    ceiling = floor_cost * Decimal(str(_BUDGET_CEILING_MULTIPLE[label]))
    target = min(budget_target, ceiling)
    # Budget wants to pay for more than this workload can usefully absorb: the
    # ceiling (or caps) will bind, so a higher budget changes nothing -- which
    # is what `saturated` tells the interface to say.
    budget_exceeds_ceiling = budget_target > ceiling

    # Already at or above the effective target: nothing to grow.
    if floor_cost >= target:
        return spec, budget_exceeds_ceiling

    def upgrades(sp: "ArchitectureSpec"):
        """The next capacity buy for each knob, cheapest-value first, or None
        when that knob is capped. A round-robin over these gives balanced
        growth rather than pouring the whole budget into one dimension."""
        moves = []
        if sp.compute_count < caps["compute"]:
            moves.append(replace(sp, compute_count=sp.compute_count + 1))
        if has_rds and sp.database_read_replicas < caps["replicas"]:
            moves.append(
                replace(sp, database_read_replicas=sp.database_read_replicas + 1)
            )
        if has_rds and (sp.cache_vcpu or 0) < caps["cache_vcpu"]:
            nxt = min(caps["cache_vcpu"], _snap_vcpu((sp.cache_vcpu or 2) + 1))
            moves.append(replace(sp, cache_vcpu=nxt, cache_memory_gb=float(nxt) * 2.0))
        if has_rds and (sp.database_vcpu or 0) < caps["db_vcpu"]:
            nxt = min(caps["db_vcpu"], _snap_vcpu((sp.database_vcpu or 2) + 1))
            moves.append(
                replace(sp, database_vcpu=nxt, database_memory_gb=float(nxt) * 4.0)
            )
        return moves

    # Greedy round-robin: at each step take the cheapest upgrade that still
    # fits under target. Stop when nothing fits (budget bound) or nothing is
    # left to buy (capacity bound -> saturated). Bounded step count so a
    # pathological budget cannot spin the pricing loop indefinitely.
    for _ in range(64):
        moves = upgrades(spec)
        if not moves:
            return spec, True  # every knob capped: workload is saturated
        affordable = [(priced(m), m) for m in moves]
        affordable = [(c, m) for c, m in affordable if c <= target]
        if not affordable:
            # Nothing more fits under the effective target. If the budget
            # itself was the binding constraint, that's not saturation -- a
            # bigger budget WOULD buy more. If the workload's cost ceiling
            # bound us first, it is: extra budget is inert.
            return spec, budget_exceeds_ceiling
        affordable.sort(key=lambda cm: cm[0])
        spec = affordable[0][1]
    return spec, budget_exceeds_ceiling


def recommend(
    requirement: Requirement,
    provider: str = "aws",
    techniques: list[Technique] | None = None,
    dsn: str | None = None,
) -> list[Option]:
    """Produce three priced, explained architectures for one provider."""
    catalog = techniques if techniques is not None else load_techniques()
    options: list[Option] = []

    # A serverless workload is a different architecture, not a smaller server
    # one, so it is built from its own spec and its own three variants. The
    # instance-count floors below are meaningless here (there are no
    # instances) and are skipped.
    # An AI app is a serverless backend plus the managed AI services it calls,
    # so it takes priority over the plain serverless shape when both are set.
    ai = getattr(requirement, "ai", False) and (
        requirement.ai_vision or requirement.ai_language
    )
    event_driven = getattr(requirement, "event_driven", False)
    serverless = getattr(requirement, "serverless", False)
    # A batch/ETL run is its own shape too: an object lake, reclaimable
    # workers and a query engine, with no edge, LB, cache or relational OLTP.
    # Lower priority than event_driven (a streaming pipeline that also happens
    # to be labelled batch is still event-driven), higher than the web shape.
    batch = (not event_driven) and requirement.workload_type == "batch"
    if event_driven:
        variants = _event_driven_variants(requirement)
    elif ai:
        variants = _ai_variants(requirement)
    elif serverless:
        variants = _serverless_variants(requirement)
    elif batch:
        variants = _batch_etl_variants(requirement)
    else:
        variants = _shape_variants(requirement)

    # Scaled specs kept by label so a dearer tier can be floored at the cheaper
    # one's capacity -- the budget scaler optimises each tier independently and
    # could otherwise hand "Most optimized" a smaller database than "Most
    # reliable" (cheapest-upgrade-first spent its budget elsewhere), inverting
    # the price order the labels promise.
    _scaled_by_label: dict[str, ArchitectureSpec] = {}

    for label, rationale, delta, tradeoffs in variants:
        if event_driven:
            spec = event_driven_spec(requirement, label)
        elif ai:
            spec = ai_spec(requirement, label)
        elif serverless:
            spec = serverless_spec(requirement, label)
        elif batch:
            spec = batch_etl_spec(requirement, label)
        else:
            spec = base_spec(requirement, label)
        if delta:
            spec = replace(spec, **delta)
        # A tier cannot be less available than the one below it. This floor
        # was applied to "Most reliable" alone, so on a small workload the
        # top tier came out with ONE instance where the middle tier had two
        # -- spanning three availability zones with nothing in two of them.
        # Server shapes only: serverless, AI and event-driven shapes have no
        # fixed instance count to floor, and forcing one would manufacture a
        # phantom EC2 fleet (or, for event_driven, override its Spot workers).
        server_shape = not serverless and not ai and not event_driven and not batch
        if server_shape and label == "Most reliable":
            spec = replace(spec, compute_count=max(2, spec.compute_count))
        elif server_shape and label == "Most optimized":
            # One per zone, since this tier pays for three of them.
            spec = replace(spec, compute_count=max(3, spec.compute_count))

        # Cross-AZ data transfer exists only once the deployment spans more
        # than one zone -- a Multi-AZ database or a load-balanced multi-instance
        # app tier. Single-AZ tiers (Cheapest) cross no boundary and stay at
        # zero. Volume is proxied on egress; see the spec field's note.
        if server_shape and (spec.database_multi_az or spec.compute_count > 1):
            spec = replace(spec, inter_az_gb=requirement.egress_gb)

        # Budget as an active lever: grow the upper tiers into the stated
        # budget, bounded by hard caps so it never pads into absurdity. The
        # workload floor above still binds; Cheapest is deliberately excluded
        # so it stays the honest minimum. No-op when no budget was stated.
        budget_saturated = False
        if server_shape:
            spec, budget_saturated = _scale_to_budget(
                spec, requirement, label, provider, dsn
            )
            # A tier is never smaller than the one below it. Floor each scalable
            # knob at the cheaper tier's value so "Most optimized" is always >=
            # "Most reliable" componentwise, and therefore in price -- the
            # monotonicity the three labels assert.
            floor_from = _scaled_by_label.get("Most reliable")
            if label == "Most optimized" and floor_from is not None:
                spec = replace(
                    spec,
                    compute_count=max(spec.compute_count, floor_from.compute_count),
                    database_vcpu=(max(spec.database_vcpu or 0, floor_from.database_vcpu or 0) or None),
                    database_memory_gb=(max(spec.database_memory_gb or 0, floor_from.database_memory_gb or 0) or None),
                    database_read_replicas=max(spec.database_read_replicas, floor_from.database_read_replicas),
                    cache_vcpu=(max(spec.cache_vcpu or 0, floor_from.cache_vcpu or 0) or None),
                    cache_memory_gb=(max(spec.cache_memory_gb or 0, floor_from.cache_memory_gb or 0) or None),
                )
            _scaled_by_label[label] = spec

        baseline = estimate(spec, provider, dsn=dsn)

        matched = match_all(
            requirement,
            catalog,
            provider=provider,
            estimated_spend=float(baseline.total_monthly) or None,
        )
        # Availability-trading techniques belong to the Cheapest tier ONLY.
        # Spot capacity can be reclaimed and scale-to-zero adds cold-start
        # latency; applying them to every tier made "Most reliable" run on
        # exactly the reclaimable, cold-starting infrastructure its name
        # promises to avoid -- and, for a compute-only workload with no
        # database or load balancer to vary, left all three tiers identical
        # but for their instance count. Withholding them here is what makes
        # the tiers three distinct postures: Cheapest trades reliability for
        # cost; the dearer tiers pay for guaranteed, always-on capacity.
        usable = matched if label == "Cheapest" else [
            m for m in matched if not _trades_availability(m.technique)
        ]
        advisory = [m for m in usable if not m.technique.is_priceable]

        current, applied = _apply_techniques(spec, usable, provider, dsn)

        final = estimate(current, provider, dsn=dsn) if applied else baseline

        # Steady/peak band for spiky traffic. The compute count already carries
        # the spike headroom (SPIKE_INSTANCE_MULTIPLIER, applied in size_for);
        # the "steady" figure prices the identical architecture with exactly
        # those extra instances removed, so a reader can see the peak they
        # provision for versus the floor they sit at the rest of the time.
        steady_monthly = None
        if server_shape and _spike_headroom_instances(requirement) > 0:
            final_spec = current if applied else spec
            floor = {"Cheapest": 1, "Most reliable": 2, "Most optimized": 3}.get(label, 1)
            steady_count = max(floor, final_spec.compute_count - _spike_headroom_instances(requirement))
            if steady_count < final_spec.compute_count:
                steady_monthly = estimate(
                    replace(final_spec, compute_count=steady_count), provider, dsn=dsn
                ).total_monthly

        # Named needs with no adapter yet. Never invented, never silently
        # dropped either -- reported the same way an unpriceable compute
        # shape is: as a real gap in `missing`, which is what makes the
        # estimate `incomplete` and keeps it from winning a comparison it
        # cannot actually deliver on. See estimator.py's own rule.

        options.append(
            Option(
                label=label,
                rationale=rationale,
                spec=current if applied else spec,
                estimate=final,
                applied=tuple(applied),
                advisory=tuple(advisory),
                baseline_monthly=baseline.total_monthly,
                tradeoffs=tradeoffs,
                spec_budget=requirement.budget_monthly_usd,
                steady_monthly=steady_monthly,
                budget_saturated=budget_saturated,
            )
        )

    return options


@dataclass(frozen=True, slots=True)
class LineChange:
    """One line item's fate between two options."""

    label: str
    before: LineItem | None
    after: LineItem | None

    @property
    def delta(self) -> Decimal:
        a = self.after.monthly_usd if self.after else Decimal(0)
        b = self.before.monthly_usd if self.before else Decimal(0)
        return a - b

    @property
    def kind(self) -> str:
        if self.before is None:
            return "added"
        if self.after is None:
            return "removed"
        return "changed" if self.delta else "unchanged"


@dataclass(slots=True)
class OptionDiff:
    """What actually differs between two options.

    A price comparison tells you one option costs more. This tells you what
    the extra money buys — which is the question a user is really asking when
    they click between them.
    """

    from_label: str
    to_label: str
    changes: list[LineChange] = field(default_factory=list)

    @property
    def added(self) -> list[LineChange]:
        return [c for c in self.changes if c.kind == "added"]

    @property
    def removed(self) -> list[LineChange]:
        return [c for c in self.changes if c.kind == "removed"]

    @property
    def changed(self) -> list[LineChange]:
        return [c for c in self.changes if c.kind == "changed"]

    @property
    def unchanged(self) -> list[LineChange]:
        return [c for c in self.changes if c.kind == "unchanged"]

    @property
    def delta_monthly(self) -> Decimal:
        return sum((c.delta for c in self.changes), Decimal(0))


def _line_key(label: str) -> str:
    """Match line items across options by what they ARE, not what they cost.

    "Database" and "Database (Multi-AZ)" are the same line at different
    service levels; "Compute × 1" and "Compute × 3" are the same tier at
    different sizes. Matching on the raw label would report each as a removal
    plus an addition, which hides the very thing the user is trying to see.
    """
    return label.split(" ×")[0].split(" (")[0].strip()


def diff_options(before: Option, after: Option) -> OptionDiff:
    """Compare two priced options line by line."""
    result = OptionDiff(from_label=before.label, to_label=after.label)

    lhs = {_line_key(i.label): i for i in before.estimate.items}
    rhs = {_line_key(i.label): i for i in after.estimate.items}

    for key in list(lhs) + [k for k in rhs if k not in lhs]:
        result.changes.append(
            LineChange(label=key, before=lhs.get(key), after=rhs.get(key))
        )

    return result


def recommend_across_clouds(
    requirement: Requirement,
    providers: tuple[str, ...] = ("aws", "azure", "gcp"),
    dsn: str | None = None,
) -> dict[str, list[Option]]:
    """Run the engine on every provider the user is open to."""
    if requirement.provider_preference:
        providers = (requirement.provider_preference,)

    catalog = load_techniques()
    return {p: recommend(requirement, p, catalog, dsn=dsn) for p in providers}


def why_not(requirement: Requirement, provider: str = "aws") -> list[tuple[Technique, str]]:
    """Techniques that did not apply, and why. Explainability, not filler."""
    return rejected(requirement, provider=provider)
