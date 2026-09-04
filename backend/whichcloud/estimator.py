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
    #: Fraction of object storage moved to an infrequent-access class by a
    #: lifecycle policy. 0.0 = everything stays on the standard class.
    #: HEURISTIC like the sizing table: most buckets have a cold tail, but how
    #: cold depends on the workload, so it is one number stated in one place.
    cold_storage_fraction: float = 0.0
    egress_gb: float = 0.0
    #: Application data crossing an AZ boundary in a Multi-AZ deployment
    #: (app<->database, app<->cache). Billed at ~$0.01/GB per direction --
    #: the line most estimates forget. Volume is a HEURISTIC proxy on
    #: egress, so an internal-only app (no egress) understates rather than
    #: invents. Zero in single-AZ tiers, where no boundary is crossed.
    inter_az_gb: float = 0.0
    load_balancer: bool = False
    #: CloudFront in front of the origin. None means "not requested" --
    #: priced on top of egress rather than netted against it, since this
    #: catalog does not model the free origin-to-edge transfer that would
    #: offset part of the direct egress line; the total this produces is
    #: therefore a conservative (slightly high) one, not an invented one.
    cdn_gb: float = 0.0
    cdn_monthly_requests: float = 0.0
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
    #: How long backups are kept. Carried for disclosure rather than
    #: billing: AWS Backup's warm-storage rate is per GB-month of stored
    #: data, which `backup_gb` already expresses, so multiplying by a
    #: retention window here would double-count it. Recorded so the
    #: architecture can state its retention rather than implying one.
    backup_retention_days: int = 0

    # ── the components a stated requirement makes mandatory ──
    #: GB copied to a second region. Zero means every copy sits beside the
    #: thing it protects, which does not survive losing the region.
    backup_copy_gb: float = 0.0
    #: DEFECT 8. What actually crosses the region boundary each month --
    #: the CHANGED fraction of the dataset, not the whole of it. The full
    #: dataset crosses once, at seed; billing that every month charged a
    #: video library 3.4x its own storage cost to sit still.
    backup_transfer_gb: float = 0.0
    #: The one-off seed, carried so it can be shown and labelled rather
    #: than folded into a monthly figure it is not part of.
    backup_seed_gb: float = 0.0
    #: Write-once retention on the primary document store, and a policy
    #: denying regions outside the lock. Both are billed at nothing and
    #: both are load-bearing, so they are carried as components rather
    #: than assumed -- an architecture cannot point at what it never named.
    object_lock: bool = False
    region_deny_guardrail: bool = False
    #: S3 and DynamoDB gateway endpoints -- always free, so always worth
    #: adding when there is any S3 traffic to divert. Priced at the
    #: catalog's own published $0 rather than assumed free by omission.
    gateway_endpoints: int = 0
    #: Transactional email, queue and push, each priced only when the
    #: workload actually stated the volume -- an unstated 0 means no
    #: component, which is different from a component priced at nothing.
    emails_per_month: float = 0.0
    queue_requests_per_month: float = 0.0
    notifications_per_month: float = 0.0
    #: Interface endpoints (ECR, SSM, Secrets Manager, CloudWatch Logs,
    #: KMS...), pre-multiplied by AZ count at the point this spec is
    #: built -- each one bills per AZ per hour, unlike the gateway kind.
    #: Only worth adding when the NAT data-processing charge it diverts
    #: is larger than its own hourly cost; see whichcloud.plan.
    vpc_endpoints: int = 0
    vpc_endpoint_gb: float = 0.0
    #: GB of write-once data aged into a colder class.
    lifecycle_gb: float = 0.0

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

    # ── serverless ──
    # All default to 0, so no server-based shape ever acquires a Lambda or
    # DynamoDB line -- these are filled only by the serverless spec builder.
    # Lambda bills per invocation AND per GB-second (invocations x duration x
    # memory), so the spec carries all three and the estimator does the
    # arithmetic rather than storing a pre-multiplied number that hides it.
    lambda_invocations_per_month: float = 0.0
    lambda_avg_ms: float = 0.0
    lambda_memory_mb: float = 0.0
    #: Provisioned concurrency keeps N execution environments warm around the
    #: clock -- the reliability lever for a latency-sensitive serverless API.
    #: Billed as its own GB-second stream on top of on-demand duration.
    lambda_provisioned_concurrency: int = 0
    apigateway_requests_per_month: float = 0.0
    #: DynamoDB on-demand, in request units. A strongly-consistent or
    #: transactional read costs more than one unit, but the sizing layer
    #: states the unit count directly so the estimator never has to guess.
    dynamodb_read_units_per_month: float = 0.0
    dynamodb_write_units_per_month: float = 0.0
    dynamodb_storage_gb: float = 0.0

    # ── managed AI ──
    # All default 0, so no non-AI shape acquires them. Priced per call
    # against the real Rekognition/Comprehend meters -- an AI app's core cost
    # is the inference volume, not a server.
    rekognition_images_per_month: float = 0.0
    #: Comprehend units of text (1 unit = 100 characters).
    comprehend_units_per_month: float = 0.0

    # ── event-driven / IoT ──
    # All default 0. Timestream is the purpose-built time-series store an
    # event pipeline routes telemetry to instead of a relational database.
    iot_messages_per_month: float = 0.0
    timestream_write_gb: float = 0.0
    timestream_storage_gb: float = 0.0
    firehose_gb_per_month: float = 0.0
    athena_tb_scanned_per_month: float = 0.0
    glue_dpu_hours_per_month: float = 0.0

    # Spot capacity can be reclaimed at short notice, so it is opt-in and only
    # ever appropriate for interruptible work.
    use_spot: bool = False
    #: Price compute against a 1-year commitment (AWS Compute Savings Plan)
    #: instead of on-demand. The largest single lever on a real bill, and the
    #: one the planner previously could only mention as an advisory range.
    use_commitment: bool = False
    #: Refuse credit-limited ("burstable") compute. Set by the engine when the
    #: projected sustained load would run such a machine above its baseline,
    #: and on the tier whose promise is headroom for an unstated peak -- the
    #: one thing CPU credits cannot deliver.
    forbid_burstable: bool = False

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
    # Four categories that used to hardcode the AWS SKU name for every
    # provider, so an Azure estimate asked Azure for "alb:lcu-hour" and
    # reported the component missing however well the catalog covered it.
    ("aws", "waf", "acl"): "waf:webacl",
    ("aws", "waf", "rule"): "waf:rule",
    ("aws", "waf", "request"): "waf:request",
    ("azure", "waf", "acl"): "appgw-waf-v2:gateway-hour",
    ("gcp", "waf", "acl"): "cloudarmor:policy",
    ("gcp", "waf", "rule"): "cloudarmor:rule",
    ("gcp", "waf", "request"): "cloudarmor:request",
    ("aws", "lcu", "hour"): "alb:lcu-hour",
    ("azure", "lcu", "hour"): "appgw:capacity-unit-hour",
    # GCP has no LCU; the traffic-proportional LB charge is data processing
    # per GB, priced in the estimator's LB block on the GCP branch.
    ("gcp", "lb_data", "gb"): "lb:data-processing",
    ("aws", "db_storage", "gp3"): "rds:gp3-storage",
    ("aws", "db_storage", "gp3-multi-az"): "rds:gp3-storage-multi-az",
    ("azure", "db_storage", "gp3"): "postgres-flex:storage",
    # Azure bills storage the same either way; the standby's copy is part
    # of the Flexible Server high-availability charge, not a second rate.
    ("azure", "db_storage", "gp3-multi-az"): "postgres-flex:storage",
    # GCP Cloud SQL: zonal storage single-AZ, regional (HA) for multi-AZ.
    ("gcp", "db_storage", "gp3"): "cloudsql:ssd-storage",
    ("gcp", "db_storage", "gp3-multi-az"): "cloudsql:ssd-storage:multi-az",
    ("aws", "s3_requests", "put"): "s3:put-requests",
    ("aws", "s3_requests", "get"): "s3:get-requests",
    ("azure", "s3_requests", "put"): "blob:put-requests",
    ("azure", "s3_requests", "get"): "blob:get-requests",
    ("gcp", "s3_requests", "put"): "gcs:put-requests",
    ("gcp", "s3_requests", "get"): "gcs:get-requests",

    ("aws", "backup_copy", "warm"): "backup:cross-region-warm",
    ("aws", "network", "inter-region"): "transfer:inter-region",
    ("aws", "storage_lifecycle", "archive-instant"): "s3:glacier-instant",
    ("aws", "storage_lifecycle", "infrequent"): "s3:standard-ia",
    ("azure", "storage_lifecycle", "infrequent"): "blob:cool-lrs",
    ("azure", "storage_lifecycle", "archive-instant"): "blob:archive-lrs",
    ("gcp", "storage_lifecycle", "infrequent"): "gcs:nearline",
    ("gcp", "storage_lifecycle", "archive-instant"): "gcs:archive",
    ("aws", "endpoint", "interface-hour"): "vpce:interface-hour",
    ("aws", "endpoint", "gb-processed"): "vpce:gb-processed",
    ("aws", "endpoint", "gateway"): "vpce:gateway",
    ("aws", "email", "outbound"): "ses:outbound-email",
    ("aws", "queue", "requests"): "sqs:requests",
    ("aws", "notification", "requests"): "sns:requests",
    # Serverless meters. Each is a straight category->sku lookup, priced by
    # its graduated tiers so the real free allowances (Lambda's first
    # million requests, DynamoDB's first 25 GB) are honoured, not billed.
    ("aws", "lambda-requests", "requests"): "lambda:requests",
    ("aws", "lambda-duration", "gb-second"): "lambda:duration",
    ("aws", "apigateway", "requests"): "apigateway:http-requests",
    ("aws", "dynamodb-reads", "request-units"): "dynamodb:read-request-units",
    ("aws", "dynamodb-writes", "request-units"): "dynamodb:write-request-units",
    ("aws", "dynamodb-storage", "gb-month"): "dynamodb:storage",
    # Key-value equivalents. Azure Cosmos DB serverless and GCP Firestore both
    # bill per request + per GB, the same shape DynamoDB does.
    ("azure", "dynamodb-reads", "request-units"): "cosmos:read-request-units",
    ("azure", "dynamodb-writes", "request-units"): "cosmos:write-request-units",
    ("azure", "dynamodb-storage", "gb-month"): "cosmos:storage",
    ("gcp", "dynamodb-reads", "request-units"): "firestore:read-ops",
    ("gcp", "dynamodb-writes", "request-units"): "firestore:write-ops",
    ("gcp", "dynamodb-storage", "gb-month"): "firestore:storage",
    ("aws", "rekognition", "images"): "rekognition:images",
    ("aws", "comprehend", "units"): "comprehend:sentiment",
    ("aws", "iot", "messages"): "iot:messages",
    ("aws", "timestream-ingest", "gb"): "timestream:ingest",
    ("aws", "timestream-storage", "gb-month"): "timestream:storage",
    ("aws", "firehose", "gb"): "firehose:ingest",
    ("aws", "athena", "tb"): "athena:scanned",
    ("aws", "glue", "dpu-hour"): "glue:etl-dpu-hour",
    # ---- Azure / GCP equivalents for the serverless + analytics roles ----
    ("azure", "lambda-requests", "requests"): "functions:executions",
    ("azure", "lambda-duration", "gb-second"): "functions:duration",
    ("azure", "apigateway", "requests"): "apim:consumption-calls",
    ("azure", "queue", "requests"): "servicebus:operations",
    ("azure", "notification", "requests"): "notificationhubs:pushes",
    ("azure", "athena", "tb"): "synapse:serverless-scanned",
    ("azure", "glue", "dpu-hour"): "datafactory:data-movement",
    ("gcp", "lambda-requests", "requests"): "cloudrunfunctions:invocations",
    ("gcp", "lambda-duration", "gb-second"): "cloudrunfunctions:memory-time",
    ("gcp", "queue", "requests"): "pubsub:messages",
    ("gcp", "notification", "requests"): "pubsub:notifications",
    ("gcp", "athena", "tb"): "bigquery:analysis",
    ("gcp", "glue", "dpu-hour"): "dataflow:vcpu-hour",
    ("azure", "rekognition", "images"): "aivision:transactions",
    ("gcp", "rekognition", "images"): "cloudvision:images",
    ("gcp", "apigateway", "requests"): "cloudrun:https-endpoint",
    ("aws", "cdn", "data-transfer"): "cloudfront:data-transfer-out",
    ("aws", "cdn", "requests"): "cloudfront:requests-https",
    ("azure", "cdn", "data-transfer"): "frontdoor:data-transfer-out",
    ("gcp", "cdn", "data-transfer"): "cloudcdn:cache-egress",
    ("aws", "governance", "object-lock"): "s3:object-lock",
    ("aws", "governance", "region-deny"): "organizations:scp",

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

#: The unit-priced warehouse SKU per cloud, for providers that do not sell
#: sized warehouse nodes the way Redshift does.
_WAREHOUSE_UNIT_SKU: dict[str, str] = {
    "azure": "synapse:dw100c-hour",
    "gcp": "bigquery:serverless",
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
            exclude_burstable=spec.forbid_burstable,
        )
        # Spot wins over a commitment when both are set: you cannot buy a
        # Savings Plan for capacity you are already getting at spot rates.
        purchase = (
            "spot" if spec.use_spot
            else "commit1yr" if spec.use_commitment
            else "ondemand"
        )
        point = store.cheapest_compute(
            query, provider=provider, purchase=purchase, dsn=dsn
        )
        if point:
            label = f"Compute × {spec.compute_count}"
            if spec.use_spot:
                label += " (spot)"
            elif spec.use_commitment:
                label += " (1-yr commitment)"
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
            commitment=spec.use_commitment,
            dsn=dsn,
        )
        # A committed rate only exists for some families; fall back to
        # on-demand rather than reporting the database missing.
        if not point and spec.use_commitment:
            point = store.cheapest_database(
                provider=provider, region=region,
                min_vcpu=spec.database_vcpu,
                min_memory_gb=spec.database_memory_gb or 0.0,
                multi_az=spec.database_multi_az, arch=spec.database_arch,
                commitment=False, dsn=dsn,
            )
        if point:
            label = "Database" + (" (Multi-AZ)" if spec.database_multi_az else "")
            if spec.use_commitment and point.sku.endswith(":commit1yr"):
                label += " (1-yr reserved)"
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
                    commitment=spec.use_commitment,
                    dsn=dsn,
                )
            )
            # Replicas run around the clock exactly as the primary does, so a
            # commitment covers them too. Leaving them on-demand priced a
            # reserved primary beside a full-price replica -- the replica line
            # came out DEARER than the database it copies.
            if not replica_point and spec.use_commitment:
                replica_point = store.cheapest_database(
                    provider=provider, region=region,
                    min_vcpu=spec.database_vcpu,
                    min_memory_gb=spec.database_memory_gb or 0.0,
                    multi_az=False, arch=spec.database_arch,
                    commitment=False, dsn=dsn,
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
            cold_gb = spec.storage_gb * min(max(spec.cold_storage_fraction, 0.0), 1.0)
            cold_point = (
                _by_role(provider, region, "storage_lifecycle", "infrequent", dsn)
                if cold_gb else None
            )
            if cold_point:
                result.items.append(
                    _metered_line("Object storage (standard)", point,
                                  spec.storage_gb - cold_gb)
                )
                result.items.append(
                    _metered_line("Object storage (infrequent access)",
                                  cold_point, cold_gb)
                )
            else:
                result.items.append(
                    _metered_line("Object storage", point, spec.storage_gb)
                )
        else:
            result.missing.append("object storage")

    # ---- egress ----
    if spec.egress_gb > 0:
        point = _preferred(provider, region, "network", dsn)
        if point:
            result.items.append(_metered_line("Egress", point, spec.egress_gb))
        else:
            result.missing.append("egress")

    # ---- cross-AZ (intra-region) data transfer ----
    # Only AWS publishes this meter in our catalog today; other providers
    # simply have no row and the line is omitted (not marked missing -- it is
    # an optional refinement, not a component the architecture depends on).
    if spec.inter_az_gb > 0:
        point = store.get_price(
            provider, region, "network", "transfer:intra-region-az", dsn=dsn
        )
        if point:
            # Billed on BOTH sides of the boundary (egress from one AZ, ingress
            # to the other), so the charged volume is twice the app-level GB.
            result.items.append(
                _metered_line(
                    "Cross-AZ data transfer (in+out)", point, spec.inter_az_gb * 2
                )
            )

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

    # ---- CDN (CloudFront) ----
    if spec.cdn_gb:
        transfer = _by_role(provider, region, "cdn", "data-transfer", dsn)
        requests = _by_role(provider, region, "cdn", "requests", dsn)
        if transfer:
            result.items.append(_metered_line("CDN data transfer", transfer, spec.cdn_gb))
            if requests and spec.cdn_monthly_requests:
                result.items.append(
                    _metered_line("CDN requests", requests, spec.cdn_monthly_requests)
                )
        else:
            result.missing.append("CDN")

    # ---- transactional email (SES) ----
    if spec.emails_per_month:
        point = _by_role(provider, region, "email", "outbound", dsn)
        if point:
            result.items.append(
                _tiered_line("Transactional email", point, spec.emails_per_month)
            )
        else:
            result.missing.append("transactional email")

    # ---- queue (SQS) ----
    if spec.queue_requests_per_month:
        point = _by_role(provider, region, "queue", "requests", dsn)
        if point:
            result.items.append(
                _tiered_line("Queue requests", point, spec.queue_requests_per_month)
            )
        else:
            result.missing.append("queue")

    # ---- push / fan-out (SNS) ----
    if spec.notifications_per_month:
        point = _by_role(provider, region, "notification", "requests", dsn)
        if point:
            result.items.append(
                _tiered_line("Notifications", point, spec.notifications_per_month)
            )
        else:
            result.missing.append("notifications")

    # ---- serverless compute (Lambda) ----
    # Two lines, because Lambda is billed two ways. Both are tiered so the
    # free allowances are honoured rather than billed.
    if spec.lambda_invocations_per_month:
        req = _by_role(provider, region, "lambda-requests", "requests", dsn)
        dur = _by_role(provider, region, "lambda-duration", "gb-second", dsn)
        if req and dur:
            result.items.append(
                _tiered_line(
                    "Lambda requests", req, spec.lambda_invocations_per_month
                )
            )
            # GB-seconds = invocations x (avg duration in seconds) x (memory in GB).
            gb_seconds = (
                spec.lambda_invocations_per_month
                * (spec.lambda_avg_ms / 1000.0)
                * (spec.lambda_memory_mb / 1024.0)
            )
            # Provisioned concurrency keeps N environments warm every second of
            # the month, on the same GB-second meter -- an always-on cost the
            # reliability tier opts into, priced for real, not a multiplier.
            if spec.lambda_provisioned_concurrency > 0:
                gb_seconds += (
                    spec.lambda_provisioned_concurrency
                    * (spec.lambda_memory_mb / 1024.0)
                    * float(HOURS_PER_MONTH)
                    * 3600.0
                )
            if gb_seconds:
                result.items.append(_tiered_line("Lambda duration", dur, gb_seconds))
        else:
            result.missing.append("lambda")

    # ---- API Gateway (HTTP API) ----
    if spec.apigateway_requests_per_month:
        point = _by_role(provider, region, "apigateway", "requests", dsn)
        if point:
            result.items.append(
                _tiered_line("API Gateway requests", point, spec.apigateway_requests_per_month)
            )
        else:
            result.missing.append("api gateway")

    # ---- DynamoDB (on-demand) ----
    if spec.dynamodb_read_units_per_month or spec.dynamodb_write_units_per_month:
        # The store's real product name per cloud -- an Azure bill showing
        # "DynamoDB reads" beside a cosmos: SKU reads as a mistake.
        _kv_name = {"aws": "DynamoDB", "azure": "Cosmos DB", "gcp": "Firestore"}.get(
            provider, "Key-value store"
        )
        reads = _by_role(provider, region, "dynamodb-reads", "request-units", dsn)
        writes = _by_role(provider, region, "dynamodb-writes", "request-units", dsn)
        store_pt = _by_role(provider, region, "dynamodb-storage", "gb-month", dsn)
        if reads and writes:
            if spec.dynamodb_read_units_per_month:
                result.items.append(
                    _tiered_line(f"{_kv_name} reads", reads, spec.dynamodb_read_units_per_month)
                )
            if spec.dynamodb_write_units_per_month:
                result.items.append(
                    _tiered_line(f"{_kv_name} writes", writes, spec.dynamodb_write_units_per_month)
                )
            if store_pt and spec.dynamodb_storage_gb:
                result.items.append(
                    _tiered_line(f"{_kv_name} storage", store_pt, spec.dynamodb_storage_gb)
                )
        else:
            result.missing.append("dynamodb")

    # ---- managed AI: Rekognition (images) ----
    if spec.rekognition_images_per_month:
        point = _by_role(provider, region, "rekognition", "images", dsn)
        if point:
            result.items.append(
                _tiered_line("Rekognition images", point, spec.rekognition_images_per_month)
            )
        else:
            result.missing.append("rekognition")

    # ---- managed AI: Comprehend (sentiment) ----
    if spec.comprehend_units_per_month:
        point = _by_role(provider, region, "comprehend", "units", dsn)
        if point:
            result.items.append(
                _tiered_line("Comprehend sentiment", point, spec.comprehend_units_per_month)
            )
        else:
            result.missing.append("comprehend")

    # ---- event-driven / IoT ----
    if spec.iot_messages_per_month:
        point = _by_role(provider, region, "iot", "messages", dsn)
        if point:
            result.items.append(_tiered_line("IoT Core messages", point, spec.iot_messages_per_month))
        else:
            result.missing.append("iot core")

    if spec.timestream_write_gb:
        w = _by_role(provider, region, "timestream-ingest", "gb", dsn)
        s = _by_role(provider, region, "timestream-storage", "gb-month", dsn)
        if w:
            result.items.append(_tiered_line("Timestream writes", w, spec.timestream_write_gb))
            if s and spec.timestream_storage_gb:
                result.items.append(_tiered_line("Timestream storage", s, spec.timestream_storage_gb))
        else:
            result.missing.append("timestream")

    if spec.firehose_gb_per_month:
        point = _by_role(provider, region, "firehose", "gb", dsn)
        if point:
            result.items.append(_tiered_line("Firehose delivery", point, spec.firehose_gb_per_month))
        else:
            cap = store.get_price(provider, region, "capture_hour",
                                  "eventhubs:capture-hour", dsn=dsn)
            if cap:
                result.items.append(_hourly_line("Event Hubs Capture", cap, 1))
            else:
                result.missing.append("stream delivery to storage")

    if spec.athena_tb_scanned_per_month:
        point = _by_role(provider, region, "athena", "tb", dsn)
        if point:
            _q = {"aws": "Athena", "azure": "Synapse serverless SQL",
                  "gcp": "BigQuery"}.get(provider, "Query engine")
            result.items.append(
                _tiered_line(f"{_q} data scanned", point, spec.athena_tb_scanned_per_month)
            )
        else:
            result.missing.append("query engine")

    if spec.glue_dpu_hours_per_month:
        point = _by_role(provider, region, "glue", "dpu-hour", dsn)
        if point:
            _e = {"aws": "Glue ETL", "azure": "Data Factory",
                  "gcp": "Dataflow"}.get(provider, "Managed ETL")
            result.items.append(
                _tiered_line(_e, point, spec.glue_dpu_hours_per_month)
            )
        else:
            result.missing.append("managed ETL")

    # ---- cross-region backup copy ----
    if spec.backup_copy_gb:
        point = _by_role(provider, region, "backup_copy", "warm", dsn)
        if point:
            # Destination STORAGE: the full dataset does sit in the second
            # region every month, and that part was always right.
            result.items.append(
                _metered_line(
                    "Cross-region backup copy (storage at destination)",
                    point, spec.backup_copy_gb,
                )
            )
            # Destination TRANSFER: only what changed. Previously absent
            # entirely, which is why the storage line was doing duty for
            # both and looked like a monthly full copy.
            if spec.backup_transfer_gb:
                moved = _by_role(provider, region, "network", "inter-region", dsn)
                if moved:
                    result.items.append(
                        _metered_line(
                            "Cross-region backup transfer (changed data)",
                            moved, spec.backup_transfer_gb,
                        )
                    )
                else:
                    result.missing.append("inter-region transfer")
        else:
            result.missing.append("cross-region backup copy")

    # ---- lifecycle-tiered retention ----
    if spec.lifecycle_gb:
        point = _by_role(provider, region, "storage_lifecycle", "archive-instant", dsn)
        if point:
            result.items.append(
                _metered_line("Archived retention", point, spec.lifecycle_gb)
            )
        else:
            result.missing.append("lifecycle storage")

    # ---- gateway endpoints (S3, DynamoDB) ----
    # Free on every account that has them, so there is no cost trade-off to
    # make -- they are added whenever there is S3 traffic to divert, not
    # gated on whether they earn their keep like the interface kind below.
    if spec.gateway_endpoints:
        point = _by_role(provider, region, "endpoint", "gateway", dsn)
        if point:
            result.items.append(
                _metered_line(
                    f"Gateway endpoints × {spec.gateway_endpoints} "
                    "(S3 + DynamoDB — no charge, keeps that traffic off NAT)",
                    point, spec.gateway_endpoints,
                )
            )
        else:
            result.missing.append("gateway endpoints")

    # ---- interface endpoints (ECR, SSM, Secrets Manager, CloudWatch Logs, KMS) ----
    # Unlike the gateway kind, these bill per AZ per hour -- five of them
    # across two AZs costs more than the NAT gateway they would replace.
    # whichcloud.plan only sets spec.vpc_endpoints when the NAT
    # data-processing charge diverted is larger than that cost, so their
    # presence here already means they were worth buying.
    if spec.vpc_endpoints:
        hourly = _by_role(provider, region, "endpoint", "interface-hour", dsn)
        processed = _by_role(provider, region, "endpoint", "gb-processed", dsn)
        if hourly and processed:
            result.items.append(
                _hourly_line(
                    f"Interface endpoints × {spec.vpc_endpoints} "
                    "(ECR, SSM, Secrets Manager, CloudWatch Logs, KMS — "
                    "cheaper than the NAT data they divert)",
                    hourly, spec.vpc_endpoints,
                )
            )
            if spec.vpc_endpoint_gb:
                result.items.append(
                    _metered_line(
                        "Interface endpoint data processing", processed,
                        spec.vpc_endpoint_gb,
                    )
                )
        else:
            result.missing.append("VPC interface endpoints")

    # ---- governance controls AWS does not charge for ----
    # Priced at zero because that is the published rate, not because the
    # figure is unknown. They appear as lines so the architecture can point
    # at the control that satisfies a residency or immutability obligation.
    for enabled, role, label in (
        (spec.object_lock, "object-lock", "Object Lock (WORM retention)"),
        (spec.region_deny_guardrail, "region-deny", "Region-deny guardrail"),
    ):
        if not enabled:
            continue
        point = _by_role(provider, region, "governance", role, dsn)
        if point:
            result.items.append(_metered_line(label, point, 1))
        else:
            result.missing.append(label.lower())

    # ---- WAF ----
    # Three real SKUs, not a bundled guess: a Web ACL is a flat fee, rules
    # are a flat fee each, and inspected requests are metered. All three
    # or none -- a Web ACL priced without its rules would understate what
    # protection actually costs.
    if spec.waf_rule_count is not None:
        webacl = _by_role(provider, region, "waf", "acl", dsn)
        rule = _by_role(provider, region, "waf", "rule", dsn)
        request = _by_role(provider, region, "waf", "request", dsn)

        # Azure does not sell a firewall this way. Application Gateway WAF
        # v2 is one hourly charge for the gateway, with throughput billed
        # as capacity units under the load balancer -- there is no per-rule
        # or per-request meter to find. Demanding all three marked a fully
        # priced Azure firewall as missing, which is the opposite of true.
        if webacl and not rule and not request:
            result.items.append(_hourly_line("Web application firewall", webacl, 1))
        elif webacl and rule and request:
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
        priced_serverless = False
        shard = store.get_price(provider, region, "streaming", "kinesis:shard-hour", dsn=dsn)
        puts = store.get_price(
            provider, region, "streaming", "kinesis:put-payload-units", dsn=dsn
        )
        if not shard:
            # Pub/Sub has no provisioned shards -- it is serverless, billed on
            # ingest alone. Price the ingest and add no capacity line rather
            # than reporting the stream missing.
            serverless_ingest = store.get_price(
                provider, region, "streaming", "pubsub:stream-ingest", dsn=dsn
            )
            if serverless_ingest and spec.stream_put_units:
                result.items.append(
                    _metered_line("Pub/Sub stream ingest", serverless_ingest,
                                  spec.stream_put_units)
                )
                priced_serverless = True
        if shard:
            result.items.append(
                _hourly_line(f"Event stream shards \u00d7 {spec.stream_shards}", shard, spec.stream_shards)
            )
            if puts and spec.stream_put_units:
                result.items.append(
                    _metered_line("Event stream PUT units", puts, spec.stream_put_units)
                )
        elif not priced_serverless:
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
            endpoint = store.get_price(provider, region, "kafka_endpoint",
                                       "eventhubs:kafka-endpoint", dsn=dsn)
            if endpoint:
                result.items.append(
                    _hourly_line(f"Kafka endpoint \u00d7 {spec.kafka_broker_count}",
                                 endpoint, spec.kafka_broker_count)
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
        # Azure AI Search sells capacity UNITS at fixed tiers, with no vCPU or
        # RAM published per unit, so the node-spec lookup above finds nothing.
        # Price one search unit per requested node instead -- the closest
        # like-for-like the two models allow, and a real published rate.
        unit = (
            None if point
            else store.get_price(provider, region, "search_unit", "aisearch:s1-unit", dsn=dsn)
        )
        if point:
            result.items.append(
                _hourly_line(
                    f"Search nodes \u00d7 {spec.search_node_count}", point, spec.search_node_count
                )
            )
        elif unit:
            result.items.append(
                _hourly_line(
                    f"Search units \u00d7 {spec.search_node_count}", unit, spec.search_node_count
                )
            )
        else:
            # Names the capability, not a product: GCP sells no first-party
            # managed search cluster (Elastic on GCP is a marketplace product),
            # so this is a real absence rather than an unmapped SKU.
            result.missing.append("managed search cluster")

        if spec.search_storage_gb:
            volume = store.get_price(
                provider, region, "search_storage", "opensearch:gp3-storage", dsn=dsn
            )
            if volume:
                result.items.append(
                    _metered_line("Search storage", volume, spec.search_storage_gb)
                )
            elif unit:
                # An AI Search unit includes its own storage allowance; there is
                # no separate per-GB meter to add, so this is not a gap.
                pass
            else:
                result.missing.append("managed search storage")

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
        # Only Redshift sells sized warehouse NODES. Synapse sells DW100c
        # units, and BigQuery sells nothing at all (it is serverless, billed
        # per TiB scanned on the analysis line). Both are published in
        # `warehouse_unit` and priced one unit per requested node.
        unit = (
            None if point
            else store.get_price(provider, region, "warehouse_unit",
                                 _WAREHOUSE_UNIT_SKU.get(provider, ""), dsn=dsn)
        )
        if point:
            result.items.append(
                _hourly_line(
                    f"Warehouse nodes \u00d7 {spec.warehouse_node_count}",
                    point,
                    spec.warehouse_node_count,
                )
            )
        elif unit:
            result.items.append(
                _hourly_line(f"{unit.name} \u00d7 {spec.warehouse_node_count}",
                             unit, spec.warehouse_node_count)
            )
        else:
            result.missing.append("data warehouse node")

    # ---- Fargate ----
    # Priced instead of EC2, not alongside it: a task is the compute tier.
    if spec.fargate_task_count:
        prefix = "fargate:arm-" if spec.fargate_arm else "fargate:"
        # The serverless-container product per cloud, so an Azure bill does not
        # read "Fargate vCPU" beside an ACI rate.
        _ctr = {"aws": "Fargate", "azure": "Container Instances",
                "gcp": "Cloud Run"}.get(provider, "Container")
        vcpu_point = store.get_price(
            provider, region, "fargate", f"{prefix}vcpu-hour", dsn=dsn
        )
        gb_point = store.get_price(provider, region, "fargate", f"{prefix}gb-hour", dsn=dsn)
        # Only AWS prices Arm containers as a separate, cheaper SKU (Graviton
        # Fargate). Azure Container Instances and Cloud Run publish ONE rate
        # whatever the architecture, so an Arm request there falls back to the
        # standard rate rather than reporting the whole container tier missing.
        if prefix.endswith("arm-") and not (vcpu_point and gb_point):
            vcpu_point = vcpu_point or store.get_price(
                provider, region, "fargate", "fargate:vcpu-hour", dsn=dsn
            )
            gb_point = gb_point or store.get_price(
                provider, region, "fargate", "fargate:gb-hour", dsn=dsn
            )
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
                    f"{_ctr} vCPU × {spec.fargate_task_count}"
                    f"–{spec.fargate_peak_tasks} tasks"
                )
            else:
                label = f"{_ctr} vCPU × {spec.fargate_task_count} tasks"
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
                    label=label.replace(f"{_ctr} vCPU", f"{_ctr} memory"),
                    sku=gb_point.sku,
                    unit="GB-hour",
                    unit_price=gb_point.price_usd,
                    quantity=gb_qty,
                    monthly_usd=gb_point.price_usd * gb_qty,
                )
            )
        else:
            result.missing.append("container compute")

    # ---- database storage ----
    if spec.db_storage_gb and spec.database_vcpu:
        role = "gp3-multi-az" if spec.database_multi_az else "gp3"
        point = _by_role(provider, region, "db_storage", role, dsn)
        if point:
            result.items.append(
                _metered_line("Database storage", point, spec.db_storage_gb)
            )
        else:
            result.missing.append("database storage")

    # ---- ALB capacity units ----
    if spec.alb_lcu and spec.load_balancer:
        point = _by_role(provider, region, "lcu", "hour", dsn)
        data_pt = _by_role(provider, region, "lb_data", "gb", dsn)
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
        elif data_pt:
            # GCP: no LCU-hour meter. The traffic-proportional LB charge is
            # data processing per GB, approximated on egress (the bytes the LB
            # forwards outward) -- HEURISTIC volume, like NAT and cross-AZ.
            gb = spec.egress_gb
            if gb:
                result.items.append(
                    _metered_line("Load balancer data processing", data_pt, gb)
                )
        else:
            result.missing.append("load balancer LCUs")

    # ---- S3 requests ----
    if spec.s3_put_requests or spec.s3_get_requests:
        put = _by_role(provider, region, "s3_requests", "put", dsn)
        get = _by_role(provider, region, "s3_requests", "get", dsn)
        if put and spec.s3_put_requests:
            result.items.append(
                _metered_line("Object storage write requests", put, spec.s3_put_requests)
            )
        if get and spec.s3_get_requests:
            result.items.append(
                _metered_line("Object storage read requests", get, spec.s3_get_requests)
            )
        if not put or not get:
            result.missing.append("object storage requests")

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
