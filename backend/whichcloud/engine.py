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

SEARCH_NODES: dict[str, int] = {"low": 2, "medium": 2, "high": 3}
WAREHOUSE_NODES: dict[str, int] = {"low": 2, "medium": 2, "high": 4}

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

    label: str  # "Cheapest" | "Balanced" | "Most reliable"
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


def size_for(requirement: Requirement) -> tuple[int, int, float]:
    """Instance count and size for a workload. HEURISTIC."""
    count, vcpu, memory = BASE_SIZING[requirement.traffic_scale]

    if requirement.traffic_pattern == "spiky":
        count = max(count, round(count * SPIKE_INSTANCE_MULTIPLIER))

    # Batch work runs on a schedule; a single worker pool is the usual shape.
    if requirement.is_batch:
        count = max(1, count // 2)

    return count, vcpu, memory


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


def base_spec(requirement: Requirement, label: str) -> ArchitectureSpec:
    """The untuned shape for this workload, before any technique applies."""
    count, vcpu, memory = size_for(requirement)
    db_vcpu, db_memory = DB_SIZING[requirement.traffic_scale]

    return ArchitectureSpec(
        name=label,
        region=requirement.region,
        compute_count=count,
        compute_vcpu=vcpu,
        compute_memory_gb=memory,
        database_vcpu=db_vcpu if requirement.needs_database else None,
        database_memory_gb=db_memory if requirement.needs_database else None,
        database_multi_az=False,
        storage_gb=requirement.storage_gb,
        egress_gb=requirement.egress_gb,
        load_balancer=requirement.needs_database and count > 1,
        # A read-heavy app in front of a database wants a cache, and anything
        # in production is monitored. Both are heuristic, like the sizing.
        cache_vcpu=2 if requirement.needs_database else None,
        cache_memory_gb=2.0 if requirement.needs_database else None,
        monitored_metrics=30 if requirement.needs_database else 10,
        waf_rule_count=WAF_RULE_COUNT if requirement.needs_waf else None,
        waf_monthly_requests=(
            WAF_MONTHLY_REQUESTS[requirement.traffic_scale]
            if requirement.needs_waf
            else 0.0
        ),
        # Standard hygiene for anything running in production, not a
        # reliability or scale feature -- every tier gets it, the same way
        # every tier already gets monitoring.
        audit_logging=True,
        kms_key_count=1 if requirement.needs_database else None,
        tls_certificate=True,
        # One NAT gateway per zone the workload spans, so a zone failure
        # does not strand the other zone's outbound traffic. The per-tier
        # count is set in _shape_variants; two is the production default.
        # Data volume is approximated by egress -- HEURISTIC, and the one
        # part of this line that is an estimate rather than a rate.
        nat_gateway_count=2,
        nat_gb_processed=requirement.egress_gb,
        # One zone for the application. Query volume scales with traffic
        # tier; both are HEURISTIC, like the sizing above them.
        dns_hosted_zones=1,
        dns_monthly_queries=DNS_MONTHLY_QUERIES[requirement.traffic_scale],
        # Sign-in only exists where there are users to sign in. Batch and
        # ML workloads have none, so they get no auth line at all.
        auth_monthly_active_users=(
            AUTH_MONTHLY_ACTIVE_USERS[requirement.traffic_scale]
            if requirement.needs_database
            else 0.0
        ),
        # Backing up the object store. RDS automated backups are free
        # within retention and are deliberately not double-counted here --
        # see load_backup_prices.
        backup_gb=requirement.storage_gb,
        # ── data pipeline & analytics ──
        # Kafka only where volume genuinely justifies it; Kinesis otherwise.
        # Both are gated on the requirement first, so no CRUD app acquires a
        # streaming tier it never asked for.
        stream_shards=(0 if _wants_kafka(requirement) else stream_shards_for(requirement)),
        stream_put_units=(
            (requirement.daily_transactions or 0) * 30
            if requirement.needs_event_streaming and not _wants_kafka(requirement)
            else 0.0
        ),
        kafka_broker_count=KAFKA_MIN_BROKERS if _wants_kafka(requirement) else 0,
        kafka_broker_vcpu=2 if _wants_kafka(requirement) else None,
        kafka_broker_memory_gb=8.0 if _wants_kafka(requirement) else None,
        search_node_count=(
            SEARCH_NODES[requirement.traffic_scale] if requirement.needs_search else 0
        ),
        search_node_vcpu=2 if requirement.needs_search else None,
        search_node_memory_gb=8.0 if requirement.needs_search else None,
        search_storage_gb=requirement.storage_gb if requirement.needs_search else 0.0,
        warehouse_node_count=(
            WAREHOUSE_NODES[requirement.traffic_scale] if requirement.needs_analytics else 0
        ),
        warehouse_node_vcpu=2 if requirement.needs_analytics else None,
        warehouse_node_memory_gb=16.0 if requirement.needs_analytics else None,
        # ── threat detection & observability ──
        # On for every tier. GuardDuty prices from the compute and database
        # vCPUs actually present, so this scales with the architecture
        # rather than being a flat add-on.
        # Fargate is opt-in, not the default compute tier. Setting it here
        # while `compute_count` still holds EC2 instances billed BOTH --
        # about $42/mo of compute nobody asked for -- so a caller choosing
        # Fargate must zero compute_count. `fargate_tasks_for` derives the
        # base and peak counts; see scripts/ for the selecting call.
        secret_count=BASE_SECRET_COUNT if requirement.needs_database else 0,
        threat_detection=True,
        tracing_monthly_traces=TRACING_MONTHLY_TRACES[requirement.traffic_scale],
        posture_monthly_checks=POSTURE_MONTHLY_CHECKS[requirement.traffic_scale],
        flowlog_gb=requirement.egress_gb * FLOWLOG_GB_PER_EGRESS_GB,
    )


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
    replicas = (
        DB_READ_REPLICAS[requirement.traffic_scale] if requirement.needs_database else 0
    )
    reliable_delta: dict = {"database_multi_az": True, "load_balancer": True}
    reliable_rationale = (
        "Survives an availability-zone failure: extra capacity and a "
        "standby database."
    )
    reliable_tradeoffs = [
        "The standby database roughly doubles the largest line on the bill",
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

    return [
        (
            "Cheapest",
            "Smallest footprint that still runs the workload. Accepts a single "
            "instance and no standby database.",
            {
                "compute_count": 1,
                "database_multi_az": False,
                "load_balancer": False,
                # One zone, so one gateway -- paying for a second in a zone
                # nothing runs in would be waste, not resilience.
                "nat_gateway_count": 1,
            },
            (
                "Single instance — a restart or crash is downtime",
                "No load balancer, so no room to scale out under load",
                "Single-zone database — a zone failure takes you offline",
                "One NAT gateway — losing its zone cuts outbound traffic",
            ),
        ),
        (
            "Balanced",
            "Handles the expected peak without cold starts, and fits a normal "
            "budget.",
            {},
            (
                "Database has no standby — a zone failure means recovery, not failover",
                "Sized for the expected peak, not an unexpected one",
            ),
        ),
        (
            "Most reliable",
            reliable_rationale,
            reliable_delta,
            tuple(reliable_tradeoffs),
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


def recommend(
    requirement: Requirement,
    provider: str = "aws",
    techniques: list[Technique] | None = None,
    dsn: str | None = None,
) -> list[Option]:
    """Produce three priced, explained architectures for one provider."""
    catalog = techniques if techniques is not None else load_techniques()
    options: list[Option] = []

    for label, rationale, delta, tradeoffs in _shape_variants(requirement):
        spec = base_spec(requirement, label)
        if delta:
            spec = replace(spec, **delta)
        if label == "Most reliable":
            spec = replace(spec, compute_count=max(2, spec.compute_count))

        baseline = estimate(spec, provider, dsn=dsn)

        matched = match_all(
            requirement,
            catalog,
            provider=provider,
            estimated_spend=float(baseline.total_monthly) or None,
        )
        advisory = [m for m in matched if not m.technique.is_priceable]

        current, applied = _apply_techniques(spec, matched, provider, dsn)

        final = estimate(current, provider, dsn=dsn) if applied else baseline

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
