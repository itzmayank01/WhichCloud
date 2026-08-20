"""Turn an architecture into a monthly bill.

This is what separates WhichCloud from a diagram tool. The engine describes a
shape — three app servers, a Postgres, 200 GB of assets, 500 GB of egress — and
this module prices every line from the catalog and adds it up.

Rules it follows:
  * Never invent a price. If a component cannot be priced, it is reported in
    `missing`, not silently dropped or guessed.
  * Every line shows its unit price and quantity, so a user can check the maths.
  * Totals are labelled estimates, because list pricing ignores committed-use
    discounts and real traffic never matches a projection exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from .pricing.models import HOURS_PER_MONTH, ComputeQuery, PricePoint, provider_region
from .pricing import store


@dataclass(frozen=True, slots=True)
class ArchitectureSpec:
    """A provider-neutral description of what needs to run."""

    name: str
    region: str  # our neutral key, e.g. "india"

    compute_count: int = 1
    compute_vcpu: int = 2
    compute_memory_gb: float = 4.0
    arch: str | None = None  # "arm64" to force ARM

    database_vcpu: int | None = None
    database_memory_gb: float | None = None
    database_multi_az: bool = False
    database_arch: str | None = None  # "arm64" to force ARM database instances
    # Read replicas of the primary, for read-heavy load at scale. Not a
    # separate meter on any provider -- a replica is billed as one more
    # instance of the primary's class, which is exactly how it is priced.
    database_read_replicas: int = 0

    storage_gb: float = 0.0
    egress_gb: float = 0.0
    load_balancer: bool = False
    #: Does anything outside call this over the network? Carried so the
    #: drawing can tell a CDN from plain data transfer without guessing
    #: from which components happen to be present.
    serves_requests: bool = True

    # A cache in front of the database, and metrics for the whole thing.
    cache_vcpu: int | None = None
    cache_memory_gb: float | None = None
    monitored_metrics: int = 0

    # WAF: None means "not requested" -- a workload that never asked for
    # protection gets no line, same as every other optional component here.
    # Set to a rule count (0 is valid: a Web ACL with only AWS managed rule
    # groups) to price it.
    waf_rule_count: int | None = None
    waf_monthly_requests: float = 0.0

    # Standard production hygiene: audit logging and an encryption key.
    # Priced for real (CloudTrail's one free trail is a genuine $0, KMS a
    # real $1/mo/key), not assumed free by omission.
    audit_logging: bool = False
    kms_key_count: int | None = None
    #: Key operations per month. Providers price key management two
    #: incompatible ways -- AWS per key held, Azure per operation performed
    #: -- so the spec carries both and each adapter uses the one it bills.
    kms_monthly_operations: float = 200_000.0

    # Private subnets need a NAT gateway per zone to reach the internet.
    # One of the largest line items people forget: two gateways is ~$82/mo
    # before a single byte is processed.
    nat_gateway_count: int = 0
    nat_gb_processed: float = 0.0
    tls_certificate: bool = False

    # DNS, sign-in and backup. Each is graduated, so the quantity matters
    # rather than just the presence of the component -- 300 staff sit
    # inside Cognito's free allowance, 300,000 users do not.
    dns_hosted_zones: int = 0
    dns_monthly_queries: float = 0.0
    auth_monthly_active_users: float = 0.0
    backup_gb: float = 0.0

    # ── data pipeline & analytics ──
    # Each is None/0 unless the workload actually asked for it: a CRUD app
    # with no streaming requirement must not acquire a Kafka cluster.
    stream_shards: int = 0
    stream_put_units: float = 0.0
    kafka_broker_count: int = 0
    kafka_broker_vcpu: int | None = None
    kafka_broker_memory_gb: float | None = None
    search_node_count: int = 0
    search_node_vcpu: int | None = None
    search_node_memory_gb: float | None = None
    search_storage_gb: float = 0.0
    warehouse_node_count: int = 0
    warehouse_node_vcpu: int | None = None
    warehouse_node_memory_gb: float | None = None

    # ── threat detection & observability ──
    # Production hygiene, like audit logging: a system nobody is watching
    # for intrusions is not production-ready, whatever the budget.
    threat_detection: bool = False
    tracing_monthly_traces: float = 0.0
    posture_monthly_checks: float = 0.0
    flowlog_gb: float = 0.0

    # ── metered detail the hourly rates alone leave out ──
    # Fargate replaces the EC2 compute line when set: a task buys vCPU and
    # memory separately, so it cannot be looked up as an instance type.
    fargate_task_count: int = 0
    fargate_task_vcpu: float = 0.0
    fargate_task_memory_gb: float = 0.0
    fargate_arm: bool = True
    #: Peak task count. Billing follows actual running time, so a service
    #: that scales to `fargate_peak_tasks` for part of the day costs the
    #: base count plus the extra tasks for the hours they actually run --
    #: not the peak around the clock.
    fargate_peak_tasks: int = 0
    fargate_peak_hours_per_day: float = 0.0
    #: Secrets held in Secrets Manager, billed per secret per month.
    secret_count: int = 0
    #: Provisioned database storage, billed apart from the instance hour.
    db_storage_gb: float = 0.0
    #: ALB capacity units -- the usage half of a balancer's bill.
    alb_lcu: float = 0.0
    s3_put_requests: float = 0.0
    s3_get_requests: float = 0.0

    # Spot capacity can be reclaimed at short notice, so it is opt-in and only
    # ever appropriate for interruptible work.
    use_spot: bool = False

    # Fraction of the month compute actually runs. 1.0 = always on. Scale-to-
    # zero lowers this. The hourly RATE stays real; only the hours change.
    compute_duty_cycle: float = 1.0


@dataclass(frozen=True, slots=True)
class LineItem:
    label: str
    sku: str
    unit: str
    unit_price: Decimal
    quantity: Decimal
    monthly_usd: Decimal

    @property
    def detail(self) -> str:
        return f"{self.quantity:g} × ${self.unit_price:.4f}/{self.unit}"


@dataclass(slots=True)
class Estimate:
    provider: str
    region: str
    spec: ArchitectureSpec
    items: list[LineItem] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def total_monthly(self) -> Decimal:
        return sum((i.monthly_usd for i in self.items), Decimal(0))

    @property
    def is_complete(self) -> bool:
        return not self.missing


# For metered categories, "cheapest in category" is the wrong default: S3
# archive tiers undercut Standard by 5x but are not where a web app's assets
# live. Naming the sensible default keeps estimates honest, and we fall back to
# cheapest only when the preferred SKU is absent.
DEFAULT_SKUS: dict[tuple[str, str], str] = {
    ("aws", "storage"): "s3:general-purpose",
    ("azure", "storage"): "blob:hot-lrs",
    ("aws", "loadbalancer"): "alb",
    ("azure", "loadbalancer"): "lb:standard",
    ("aws", "network"): "egress:internet",
    ("azure", "network"): "egress:internet",
}


#: The SKU each provider uses for a category, by role. Without this the
#: estimator asked every provider for AWS's own SKU names -- so Azure could
#: publish a DNS zone price and still be reported as missing DNS, because
#: nothing ever looked up `dns:hosted-zone`. A category absent for a
#: provider simply has no row and is reported missing, as before.
PROVIDER_SKUS: dict[tuple[str, str, str], str] = {
    ("aws", "dns", "zone"): "route53:hosted-zone",
    ("aws", "dns", "queries"): "route53:dns-queries",
    ("azure", "dns", "zone"): "dns:hosted-zone",
    ("azure", "dns", "queries"): "dns:queries",
    ("aws", "kms", "key"): "kms:key",
    ("azure", "kms", "key"): "keyvault:operations",
    ("aws", "backup", "storage"): "backup:warm-storage",
    ("azure", "backup", "storage"): "backup:vault-lrs",
    ("aws", "flowlogs", "ingest"): "vpc:flow-logs",
    ("azure", "flowlogs", "ingest"): "networkwatcher:flow-logs",
    ("aws", "threat", "compute"): "guardduty:ec2-vcpu",
    ("aws", "threat", "database"): "guardduty:rds-vcpu",
    ("aws", "threat", "fargate"): "guardduty:fargate-vcpu",
    ("azure", "threat", "compute"): "defender:server-node",
    ("aws", "posture", "checks"): "securityhub:compliance-check",
    ("azure", "posture", "checks"): "defender:cspm-node",
    ("aws", "auth", "mau"): "cognito:user-pool-mau",
    ("azure", "auth", "mau"): "entra:external-id-mau",
    ("aws", "audit", "trail"): "cloudtrail:management-events",
    ("azure", "audit", "trail"): "activitylog:events",
    ("aws", "tls", "certificate"): "acm:public-certificate",
    ("azure", "tls", "certificate"): "appservice:managed-certificate",
    ("aws", "tracing", "traces"): "xray:traces-recorded",
    ("azure", "tracing", "ingest"): "appinsights:ingestion",
    ("aws", "secrets", "secret"): "secretsmanager:secret",
    # Azure holds secrets in Key Vault and bills the same per-operation
    # meter as keys, so there is no separate secrets line to price.
    ("azure", "secrets", "secret"): None,
    ("gcp", "dns", "zone"): "clouddns:managed-zone",
    ("gcp", "dns", "queries"): "clouddns:queries",
    ("gcp", "kms", "key"): "cloudkms:key-version",
    ("gcp", "secrets", "secret"): "secretmanager:version",
    ("gcp", "tracing", "traces"): "cloudtrace:spans",
    ("gcp", "nat", "gateway"): "cloudnat:gateway-hour",
    ("gcp", "nat", "data"): "cloudnat:gb-processed",
    ("aws", "nat", "gateway"): "nat:gateway-hour",
    ("aws", "nat", "data"): "nat:gb-processed",
    ("azure", "nat", "gateway"): "nat:gateway-hour",
    ("azure", "nat", "data"): "nat:gb-processed",
    ("gcp", "tls", "certificate"): "certmanager:certificate",
    ("gcp", "auth", "mau"): "identityplatform:mau",
    ("gcp", "audit", "trail"): "cloudlogging:storage",
    ("gcp", "flowlogs", "ingest"): "cloudlogging:vended-logs",
    ("gcp", "backup", "storage"): "backupdr:gce-vm",
    ("gcp", "threat", "compute"): "scc:compute-core",
    # One SCC subscription covers threat detection AND posture, so the
    # posture line would charge the same subscription a second time.
    ("gcp", "posture", "checks"): None,
}


def _sku(provider: str, category: str, role: str) -> str | None:
    return PROVIDER_SKUS.get((provider, category, role))


def _models(provider: str, category: str) -> bool:
    """Does this provider bill this category at all, on any role?

    A category with an explicit None is one the provider folds into
    another charge -- Azure keeps secrets in Key Vault and bills them on
    the key-operation meter. Reporting that as a missing component would
    mark the estimate incomplete for a cost that is already on the bill.
    """
    return any(k[0] == provider and k[1] == category for k in PROVIDER_SKUS)


def _by_role(
    provider: str, region: str, category: str, role: str, dsn: str | None
) -> PricePoint | None:
    """The price point this provider uses for a category's role, if any."""
    sku = _sku(provider, category, role)
    return store.get_price(provider, region, category, sku, dsn=dsn) if sku else None


def _preferred(
    provider: str, region: str, category: str, dsn: str | None
) -> PricePoint | None:
    sku = DEFAULT_SKUS.get((provider, category))
    if sku:
        point = store.get_price(provider, region, category, sku, dsn=dsn)
        if point:
            return point
    return store.cheapest_in_category(provider, region, category, dsn=dsn)


def _hourly_line(
    label: str, point: PricePoint, count: int, duty_cycle: float = 1.0
) -> LineItem:
    quantity = Decimal(count) * HOURS_PER_MONTH * Decimal(str(duty_cycle))
    return LineItem(
        label=label,
        sku=point.sku,
        unit=point.unit,
        unit_price=point.price_usd,
        quantity=quantity,
        monthly_usd=point.price_usd * quantity,
    )


def _metered_line(label: str, point: PricePoint, amount: float) -> LineItem:
    quantity = Decimal(str(amount))
    return LineItem(
        label=label,
        sku=point.sku,
        unit=point.unit,
        unit_price=point.price_usd,
        quantity=quantity,
        monthly_usd=point.price_usd * quantity,
    )


def _tiered_line(label: str, point: PricePoint, amount: float) -> LineItem:
    """A metered line whose rate is graduated rather than flat.

    `unit_price` shows the rate actually paid on average rather than the
    entry band's rate, so the line's own arithmetic still reconciles:
    quantity x unit_price equals the total charged. Showing the first
    band's rate next to a tier-aware total would look like a mistake.
    """
    quantity = Decimal(str(amount))
    total = point.cost_for(quantity)
    effective = (total / quantity) if quantity else Decimal(0)
    return LineItem(
        label=label,
        sku=point.sku,
        unit=point.unit,
        unit_price=effective,
        quantity=quantity,
        monthly_usd=total,
    )


def estimate(spec: ArchitectureSpec, provider: str, dsn: str | None = None) -> Estimate:
    """Price one architecture on one provider."""
    region = provider_region(spec.region, provider)
    result = Estimate(provider=provider, region=region, spec=spec)

    # ---- compute ----
    if spec.compute_count > 0:
        query = ComputeQuery(
            min_vcpu=spec.compute_vcpu,
            min_memory_gb=spec.compute_memory_gb,
            region=spec.region,
            arch=spec.arch,
        )
        purchase = "spot" if spec.use_spot else "ondemand"
        point = store.cheapest_compute(
            query, provider=provider, purchase=purchase, dsn=dsn
        )
        if point:
            label = f"Compute × {spec.compute_count}"
            if spec.use_spot:
                label += " (spot)"
            result.items.append(
                _hourly_line(
                    label, point, spec.compute_count, spec.compute_duty_cycle
                )
            )
        else:
            result.missing.append(
                f"{purchase} compute {spec.compute_vcpu}vCPU/"
                f"{spec.compute_memory_gb:g}GB"
                + (f" {spec.arch}" if spec.arch else "")
            )

    # ---- database ----
    if spec.database_vcpu:
        point = store.cheapest_database(
            provider=provider,
            region=region,
            min_vcpu=spec.database_vcpu,
            min_memory_gb=spec.database_memory_gb or 0.0,
            multi_az=spec.database_multi_az,
            arch=spec.database_arch,
            dsn=dsn,
        )
        if point:
            label = "Database" + (" (Multi-AZ)" if spec.database_multi_az else "")
            result.items.append(_hourly_line(label, point, 1))
        else:
            result.missing.append(
                f"database {spec.database_vcpu}vCPU/"
                f"{(spec.database_memory_gb or 0):g}GB"
                + (f" {spec.database_arch}" if spec.database_arch else "")
                + (" multi-az" if spec.database_multi_az else "")
            )

        # ---- read replicas ----
        # Reuses the primary's price point when it is already the right one
        # (single-AZ) rather than a second catalog round trip. A replica is
        # never assumed to inherit a standby it does not have, so when the
        # primary is Multi-AZ this looks up the plain single-AZ point instead
        # of pricing the replica as if it were also Multi-AZ.
        if spec.database_read_replicas > 0:
            replica_point = (
                point
                if point and not spec.database_multi_az
                else store.cheapest_database(
                    provider=provider,
                    region=region,
                    min_vcpu=spec.database_vcpu,
                    min_memory_gb=spec.database_memory_gb or 0.0,
                    multi_az=False,
                    arch=spec.database_arch,
                    dsn=dsn,
                )
            )
            if replica_point:
                label = f"Database read replica × {spec.database_read_replicas}"
                result.items.append(
                    _hourly_line(label, replica_point, spec.database_read_replicas)
                )
            else:
                result.missing.append(
                    f"database read replica {spec.database_vcpu}vCPU/"
                    f"{(spec.database_memory_gb or 0):g}GB"
                )

    # ---- storage ----
    if spec.storage_gb > 0:
        point = _preferred(provider, region, "storage", dsn)
        if point:
            result.items.append(_metered_line("Object storage", point, spec.storage_gb))
        else:
            result.missing.append("object storage")

    # ---- egress ----
    if spec.egress_gb > 0:
        point = _preferred(provider, region, "network", dsn)
        if point:
            result.items.append(_metered_line("Egress", point, spec.egress_gb))
        else:
            result.missing.append("egress")

    # ---- cache ----
    if spec.cache_vcpu:
        point = store.cheapest_compute_like(
            provider=provider,
            region=region,
            category="cache",
            min_vcpu=spec.cache_vcpu,
            min_memory_gb=spec.cache_memory_gb or 0.0,
            dsn=dsn,
        )
        if point:
            result.items.append(_hourly_line("Cache", point, 1))
        else:
            result.missing.append(
                f"cache {spec.cache_vcpu}vCPU/{(spec.cache_memory_gb or 0):g}GB"
            )

    # ---- monitoring ----
    if spec.monitored_metrics:
        point = store.cheapest_in_category(provider, region, "monitoring", dsn=dsn)
        if point:
            result.items.append(
                _metered_line("Monitoring", point, spec.monitored_metrics)
            )
        else:
            result.missing.append("monitoring")

    # ---- load balancer ----
    if spec.load_balancer:
        point = _preferred(provider, region, "loadbalancer", dsn)
        if point:
            result.items.append(_hourly_line("Load balancer", point, 1))
        else:
            result.missing.append("load balancer")

    # ---- WAF ----
    # Three real SKUs, not a bundled guess: a Web ACL is a flat fee, rules
    # are a flat fee each, and inspected requests are metered. All three
    # or none -- a Web ACL priced without its rules would understate what
    # protection actually costs.
    if spec.waf_rule_count is not None:
        webacl = store.get_price(provider, region, "waf", "waf:webacl", dsn=dsn)
        rule = store.get_price(provider, region, "waf", "waf:rule", dsn=dsn)
        request = store.get_price(provider, region, "waf", "waf:request", dsn=dsn)
        if webacl and rule and request:
            result.items.append(_metered_line("WAF Web ACL", webacl, 1))
            if spec.waf_rule_count:
                result.items.append(
                    _metered_line(
                        f"WAF rules × {spec.waf_rule_count}", rule, spec.waf_rule_count
                    )
                )
            if spec.waf_monthly_requests:
                result.items.append(
                    _metered_line(
                        "WAF request inspection", request, spec.waf_monthly_requests
                    )
                )
        else:
            # The category, not the AWS product name. This list is shown to
            # the reader beside an Azure or GCP total, where "AWS WAF" reads
            # as though the estimate is missing a competitor's service.
            result.missing.append("web application firewall")

    # ---- audit logging ----
    if spec.audit_logging:
        point = _by_role(provider, region, "audit", "trail", dsn)
        if point:
            result.items.append(_metered_line("Audit logging", point, 1))
        else:
            result.missing.append("audit logging")

    # ---- NAT gateways ----
    if spec.nat_gateway_count:
        hourly = _by_role(provider, region, "nat", "gateway", dsn)
        per_gb = _by_role(provider, region, "nat", "data", dsn)
        if hourly:
            result.items.append(
                _hourly_line(
                    f"NAT gateway × {spec.nat_gateway_count}",
                    hourly,
                    spec.nat_gateway_count,
                )
            )
            if per_gb and spec.nat_gb_processed:
                result.items.append(
                    _metered_line(
                        "NAT data processing", per_gb, spec.nat_gb_processed
                    )
                )
        else:
            result.missing.append("NAT gateway")

    # ---- TLS ----
    if spec.tls_certificate:
        point = _by_role(provider, region, "tls", "certificate", dsn)
        if point:
            result.items.append(_metered_line("TLS certificate", point, 1))
        else:
            result.missing.append("TLS certificate")

    # ---- DNS ----
    if spec.dns_hosted_zones:
        zone = _by_role(provider, region, "dns", "zone", dsn)
        queries = _by_role(provider, region, "dns", "queries", dsn)
        if zone:
            result.items.append(
                _tiered_line(
                    f"DNS hosted zone × {spec.dns_hosted_zones}",
                    zone,
                    spec.dns_hosted_zones,
                )
            )
            if queries and spec.dns_monthly_queries:
                result.items.append(
                    _tiered_line("DNS queries", queries, spec.dns_monthly_queries)
                )
        else:
            result.missing.append("DNS hosted zone")

    # ---- authentication ----
    if spec.auth_monthly_active_users:
        point = _by_role(provider, region, "auth", "mau", dsn)
        if point:
            result.items.append(
                _tiered_line(
                    "Authentication (MAU)", point, spec.auth_monthly_active_users
                )
            )
        else:
            result.missing.append("authentication")

    # ---- backup ----
    if spec.backup_gb:
        point = _by_role(provider, region, "backup", "storage", dsn)
        if point:
            result.items.append(_metered_line("Backup storage", point, spec.backup_gb))
        else:
            result.missing.append("backup storage")

    # ---- event streaming (Kinesis) ----
    if spec.stream_shards:
        shard = store.get_price(provider, region, "streaming", "kinesis:shard-hour", dsn=dsn)
        puts = store.get_price(
            provider, region, "streaming", "kinesis:put-payload-units", dsn=dsn
        )
        if shard:
            result.items.append(
                _hourly_line(f"Event stream shards \u00d7 {spec.stream_shards}", shard, spec.stream_shards)
            )
            if puts and spec.stream_put_units:
                result.items.append(
                    _metered_line("Event stream PUT units", puts, spec.stream_put_units)
                )
        else:
            result.missing.append("event streaming")

    # ---- managed Kafka (MSK) ----
    if spec.kafka_broker_count:
        point = store.cheapest_compute_like(
            provider=provider,
            region=region,
            category="kafka",
            min_vcpu=spec.kafka_broker_vcpu or 2,
            min_memory_gb=spec.kafka_broker_memory_gb or 0.0,
            dsn=dsn,
        )
        if point:
            result.items.append(
                _hourly_line(
                    f"Kafka brokers \u00d7 {spec.kafka_broker_count}", point, spec.kafka_broker_count
                )
            )
        else:
            result.missing.append("managed Kafka broker")

    # ---- search / analytics (OpenSearch) ----
    if spec.search_node_count:
        point = store.cheapest_compute_like(
            provider=provider,
            region=region,
            category="search",
            min_vcpu=spec.search_node_vcpu or 2,
            min_memory_gb=spec.search_node_memory_gb or 0.0,
            dsn=dsn,
        )
        if point:
            result.items.append(
                _hourly_line(
                    f"Search nodes \u00d7 {spec.search_node_count}", point, spec.search_node_count
                )
            )
        else:
            result.missing.append("search node")

        if spec.search_storage_gb:
            volume = store.get_price(
                provider, region, "search_storage", "opensearch:gp3-storage", dsn=dsn
            )
            if volume:
                result.items.append(
                    _metered_line("Search storage", volume, spec.search_storage_gb)
                )
            else:
                result.missing.append("search storage")

    # ---- data warehouse (Redshift) ----
    if spec.warehouse_node_count:
        point = store.cheapest_compute_like(
            provider=provider,
            region=region,
            category="warehouse",
            min_vcpu=spec.warehouse_node_vcpu or 2,
            min_memory_gb=spec.warehouse_node_memory_gb or 0.0,
            dsn=dsn,
        )
        if point:
            result.items.append(
                _hourly_line(
                    f"Warehouse nodes \u00d7 {spec.warehouse_node_count}",
                    point,
                    spec.warehouse_node_count,
                )
            )
        else:
            result.missing.append("data warehouse node")

    # ---- Fargate ----
    # Priced instead of EC2, not alongside it: a task is the compute tier.
    if spec.fargate_task_count:
        prefix = "fargate:arm-" if spec.fargate_arm else "fargate:"
        vcpu_point = store.get_price(
            provider, region, "fargate", f"{prefix}vcpu-hour", dsn=dsn
        )
        gb_point = store.get_price(provider, region, "fargate", f"{prefix}gb-hour", dsn=dsn)
        if vcpu_point and gb_point:
            hours = HOURS_PER_MONTH * Decimal(spec.fargate_task_count)
            vcpu_qty = hours * Decimal(str(spec.fargate_task_vcpu))
            gb_qty = hours * Decimal(str(spec.fargate_task_memory_gb))
            # Extra tasks only bill for the hours they run. Pricing the
            # peak around the clock would overstate an autoscaled service
            # by the whole difference between base and peak.
            extra = max(0, spec.fargate_peak_tasks - spec.fargate_task_count)
            if extra and spec.fargate_peak_hours_per_day:
                burst = (
                    Decimal(extra)
                    * Decimal(str(spec.fargate_peak_hours_per_day))
                    * Decimal("30.4")
                )
                vcpu_qty += burst * Decimal(str(spec.fargate_task_vcpu))
                gb_qty += burst * Decimal(str(spec.fargate_task_memory_gb))
                label = (
                    f"Fargate vCPU × {spec.fargate_task_count}"
                    f"–{spec.fargate_peak_tasks} tasks"
                )
            else:
                label = f"Fargate vCPU × {spec.fargate_task_count} tasks"
            result.items.append(
                LineItem(
                    label=label,
                    sku=vcpu_point.sku,
                    unit="vCPU-hour",
                    unit_price=vcpu_point.price_usd,
                    quantity=vcpu_qty,
                    monthly_usd=vcpu_point.price_usd * vcpu_qty,
                )
            )
            result.items.append(
                LineItem(
                    label=label.replace("Fargate vCPU", "Fargate memory"),
                    sku=gb_point.sku,
                    unit="GB-hour",
                    unit_price=gb_point.price_usd,
                    quantity=gb_qty,
                    monthly_usd=gb_point.price_usd * gb_qty,
                )
            )
        else:
            result.missing.append("Fargate capacity")

    # ---- database storage ----
    if spec.db_storage_gb and spec.database_vcpu:
        sku = (
            "rds:gp3-storage-multi-az" if spec.database_multi_az else "rds:gp3-storage"
        )
        point = store.get_price(provider, region, "db_storage", sku, dsn=dsn)
        if point:
            result.items.append(
                _metered_line("Database storage", point, spec.db_storage_gb)
            )
        else:
            result.missing.append("database storage")

    # ---- ALB capacity units ----
    if spec.alb_lcu and spec.load_balancer:
        point = store.get_price(provider, region, "lcu", "alb:lcu-hour", dsn=dsn)
        if point:
            result.items.append(
                LineItem(
                    label="Load balancer LCUs",
                    sku=point.sku,
                    unit="LCU-hour",
                    unit_price=point.price_usd,
                    quantity=HOURS_PER_MONTH * Decimal(str(spec.alb_lcu)),
                    monthly_usd=point.price_usd * HOURS_PER_MONTH * Decimal(str(spec.alb_lcu)),
                )
            )
        else:
            result.missing.append("load balancer LCUs")

    # ---- S3 requests ----
    if spec.s3_put_requests or spec.s3_get_requests:
        put = store.get_price(provider, region, "s3_requests", "s3:put-requests", dsn=dsn)
        get = store.get_price(provider, region, "s3_requests", "s3:get-requests", dsn=dsn)
        if put and spec.s3_put_requests:
            result.items.append(_metered_line("S3 write requests", put, spec.s3_put_requests))
        if get and spec.s3_get_requests:
            result.items.append(_metered_line("S3 read requests", get, spec.s3_get_requests))
        if not put or not get:
            result.missing.append("S3 requests")

    # ---- secrets ----
    if spec.secret_count:
        point = _by_role(provider, region, "secrets", "secret", dsn)
        if point:
            result.items.append(
                _metered_line(f"Secrets × {spec.secret_count}", point, spec.secret_count)
            )
        elif not _models(provider, "secrets"):
            result.missing.append("secrets manager")

    # ---- threat detection (GuardDuty) ----
    # Priced from the vCPU count actually being monitored -- the compute
    # tier's own size -- rather than a flat per-account guess.
    if spec.threat_detection:
        ec2 = _by_role(provider, region, "threat", "compute", dsn)
        rds = _by_role(provider, region, "threat", "database", dsn)
        fargate = _by_role(provider, region, "threat", "fargate", dsn)
        if ec2 and ec2.unit == "core-hour":
            # Billed per protected core, so the quantity is vCPUs and the
            # rate is hourly -- neither a node count nor a vCPU-month.
            cores = spec.compute_count * spec.compute_vcpu
            result.items.append(
                _hourly_line("Threat detection", ec2, cores)
            )
        elif ec2 and ec2.unit == "node-hour":
            # Per-node providers charge by the machine, not by its vCPUs,
            # so converting a vCPU count into node-hours would invent load
            # the provider never bills for.
            nodes = spec.compute_count + (1 if spec.database_vcpu else 0)
            result.items.append(
                _hourly_line("Threat detection", ec2, nodes)
            )
        elif ec2:
            # Whichever compute tier is actually running. A Fargate task's
            # vCPUs are monitored on their own meter -- counting them at
            # zero because no EC2 instance exists would put a $0.00 line on
            # the bill, which asserts "free" rather than "not applicable".
            ec2_vcpus = spec.compute_count * spec.compute_vcpu
            fargate_vcpus = spec.fargate_task_count * spec.fargate_task_vcpu
            if ec2_vcpus:
                result.items.append(
                    _tiered_line("Threat detection: compute", ec2, ec2_vcpus)
                )
            if fargate_vcpus and fargate:
                # A distinct label: two lines reading "Threat detection:
                # compute" collapse to one key when options are diffed, and
                # one silently overwrites the other.
                result.items.append(
                    _tiered_line("Threat detection: Fargate", fargate, fargate_vcpus)
                )
            if rds and spec.database_vcpu:
                db_vcpus = spec.database_vcpu * (1 + spec.database_read_replicas)
                result.items.append(
                    _tiered_line("Threat detection: database", rds, db_vcpus)
                )
        else:
            result.missing.append("threat detection")

    # ---- distributed tracing (X-Ray) ----
    if spec.tracing_monthly_traces:
        point = _by_role(provider, region, "tracing", "traces", dsn) or _by_role(
            provider, region, "tracing", "ingest", dsn
        )
        if point and point.unit == "GB":
            # Per-GB providers bill telemetry volume, not trace count.
            # A trace is roughly a kilobyte of spans; converting keeps the
            # line honest about which unit was actually charged.
            gb = spec.tracing_monthly_traces / 1_000_000
            result.items.append(_metered_line("Telemetry ingestion", point, gb))
        elif point:
            result.items.append(
                _tiered_line("Distributed tracing", point, spec.tracing_monthly_traces)
            )
        else:
            result.missing.append("distributed tracing")

    # ---- security posture (Security Hub) ----
    if spec.posture_monthly_checks:
        point = _by_role(provider, region, "posture", "checks", dsn)
        if point and point.unit == "node-hour":
            nodes = spec.compute_count + (1 if spec.database_vcpu else 0)
            result.items.append(_hourly_line("Security posture", point, nodes))
        elif point:
            result.items.append(
                _tiered_line("Security posture checks", point, spec.posture_monthly_checks)
            )
        elif not _models(provider, "posture"):
            result.missing.append("security posture")

    # ---- VPC flow logs ----
    if spec.flowlog_gb:
        point = _by_role(provider, region, "flowlogs", "ingest", dsn)
        if point:
            result.items.append(_tiered_line("VPC flow logs", point, spec.flowlog_gb))
        else:
            result.missing.append("VPC flow logs")

    # ---- KMS ----
    if spec.kms_key_count:
        point = _by_role(provider, region, "kms", "key", dsn)
        if point and point.unit == "operation":
            # Per-operation providers charge nothing for holding a key, so
            # multiplying the key count by an operation rate produced
            # "$0.00" -- which reads as free rather than as a different
            # billing model.
            result.items.append(
                _metered_line(
                    "Key management operations", point, spec.kms_monthly_operations
                )
            )
        elif point:
            result.items.append(
                _metered_line(
                    f"KMS keys × {spec.kms_key_count}", point, spec.kms_key_count
                )
            )
        else:
            result.missing.append("KMS")

    return result


def compare(
    spec: ArchitectureSpec,
    providers: tuple[str, ...] = ("aws", "azure", "gcp"),
    dsn: str | None = None,
) -> list[Estimate]:
    """Price the same architecture on each provider, cheapest first.

    Incomplete estimates sort last regardless of price — a total that is missing
    a database is not cheaper, it is wrong, and ranking it first would be a lie.
    """
    results = [estimate(spec, p, dsn=dsn) for p in providers]
    return sorted(results, key=lambda e: (not e.is_complete, e.total_monthly))
