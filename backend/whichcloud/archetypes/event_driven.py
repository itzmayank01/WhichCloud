"""Reacting to events that arrive, rather than to requests a user makes.

PROBE-3, verbatim:

    "We receive payment webhooks from three providers, roughly 40,000 a
     day in unpredictable bursts. Each one triggers a few database writes
     and an email. We cannot drop a single one."

Severity CRITICAL. Not because the bill was large -- it was $65 -- but
because the prompt makes an explicit reliability PROMISE ("we cannot drop
a single one") and the architecture returned had nothing in it that keeps
that promise. No queue existed anywhere in the engine's vocabulary, so
the answer was a synchronous compute-and-database stack in which a
webhook arriving during a restart is simply gone.

THE QUEUE IS RUNG ONE HERE.
A durable buffer between the endpoint and the processing is not a
production nicety to be sold at tier 2. It is the single component that
makes "we cannot drop one" true, and a design without it does not meet
the stated requirement at any price. So it is present on the cheapest
tier, and the tiers differ on what happens AFTER the event is safely
held -- ordering, replay, archive -- rather than on whether it is held at
all.

"in unpredictable bursts" is the second half of the same point. A burst
is exactly when a synchronous stack sheds load, and exactly when a queue
earns its place: the buffer absorbs the spike and the consumers drain it
at their own rate.

CANDIDATE SET
From the AWS Architecture Center's webhook-ingestion and
event-driven-architecture references (API Gateway -> SQS -> Lambda, with
EventBridge for routing and a Kinesis stream where ordering or replay
matters), and the Well-Architected reliability pillar on queueing to
decouple producers from consumer availability.
"""

from __future__ import annotations

from whichcloud.archetypes.base import (
    ArchetypeGraph, Candidate, Forbidden, SizingDriver,
    has_cdn, has_load_balancer, resilience_wanted,
)
from whichcloud.estimator import ArchitectureSpec

#: SQS bills per request, and one event costs three: the send, the
#: receive, and the delete that acknowledges it. Modelling one would
#: understate the queue by two thirds, and the queue is the component
#: this whole archetype turns on.
SQS_REQUESTS_PER_EVENT = 3

#: What a burst multiplies the steady rate by, when the text says there
#: are bursts but not how big. Surfaced as an assumption -- it sizes the
#: consumer concurrency and nothing else, so getting it wrong costs
#: headroom rather than correctness.
DEFAULT_BURST_FACTOR = 10.0

#: Milliseconds a consumer spends on one event. A few database writes and
#: an email is not a long function; 250ms is the conservative end.
DEFAULT_CONSUMER_MS = 250.0
DEFAULT_CONSUMER_MB = 512.0

#: Bytes per event. Payment webhooks are small JSON documents.
EVENT_KB = 4.0

#: How long raw events are kept once archived, as a share that has gone
#: cold. Financial event archives are read almost never and retained for
#: years, which is what the archive tier is for.
COLD_SHARE = 0.8


def _events_per_day(constraints) -> float:
    return float(constraints.requests_per_day or 10_000)


def _events_per_month(constraints) -> float:
    return _events_per_day(constraints) * 30.0


def _archive_gb(constraints) -> float:
    """Raw events retained, in GB/month."""
    return _events_per_month(constraints) * EVENT_KB / 1_048_576.0


def _burst_factor(constraints) -> float:
    return DEFAULT_BURST_FACTOR if constraints.peak_shape == "spiky" else 3.0


def _describe(constraints, load) -> str:
    per_day = _events_per_day(constraints)
    return (
        f"{per_day:,.0f} events/day ({_events_per_month(constraints):,.0f}/month) "
        f"at {EVENT_KB:.0f} KB each, bursting to "
        f"{_burst_factor(constraints):.0f}x the steady rate"
    )


SIZING = SizingDriver(
    name="events per day and burst factor",
    fields=("requests_per_day", "peak_shape", "durability"),
    describe=_describe,
)


CANDIDATES = (
    # ── ingest ──
    Candidate("Amazon API Gateway", "ingest", "apigateway",
              "The HTTPS endpoint the providers POST to.",
              instead_of="an always-on load-balanced fleet waiting for "
                         "a webhook that arrives twice a minute"),
    # ── async: the part that keeps the promise ──
    Candidate("Amazon SQS", "async", "queue",
              "Holds each event until a consumer confirms it. THIS is "
              "what makes 'we cannot drop one' true.",
              instead_of="processing synchronously and losing whatever "
                         "arrives during a restart"),
    Candidate("Amazon EventBridge", "async", "eventbridge",
              "Routes by provider and event type, so adding a fourth "
              "provider is a rule rather than a deploy."),
    Candidate("Amazon Kinesis Data Streams", "async", "streaming",
              "Ordered, replayable log for events where sequence matters.",
              instead_of="a queue, which gives no ordering and no replay"),
    Candidate("Amazon Data Firehose", "async", "firehose",
              "Continuous delivery of raw events into object storage."),
    Candidate("Amazon SNS", "async", "notification",
              "Fan-out and dead-letter alerting."),
    # ── compute ──
    Candidate("AWS Lambda", "compute", "lambda-requests",
              "Consumers that scale with queue depth and cost nothing "
              "between bursts.",
              instead_of="instances provisioned for the peak all month"),
    Candidate("Lambda duration", "compute", "lambda-duration",
              "Per-GB-second charge for the time consumers actually run."),
    # ── store ──
    Candidate("Amazon DynamoDB", "store", "dynamodb-writes",
              "Per-event writes, priced per request rather than per hour.",
              instead_of="a relational instance sized for a peak that "
                         "lasts ninety seconds"),
    Candidate("DynamoDB reads", "store", "dynamodb-reads",
              "Idempotency checks — has this event been seen before."),
    Candidate("DynamoDB storage", "store", "dynamodb-storage",
              "The processed-event table."),
    Candidate("Amazon S3", "store", "storage",
              "Raw event archive, for replay and for audit."),
    Candidate("S3 requests", "store", "s3_requests",
              "PUTs from the delivery stream."),
    Candidate("S3 lifecycle tiering", "store", "storage_lifecycle",
              "Financial event archives are read almost never and kept "
              "for years."),
    # ── analytics ──
    Candidate("Amazon Athena", "analytics", "athena",
              "SQL over the raw archive when a provider disputes a "
              "payment."),
    # ── the side effect the prompt names ──
    Candidate("Amazon SES", "async", "email",
              "The email each event triggers."),
    # ── ops ──
    Candidate("Amazon CloudWatch", "ops", "monitoring",
              "Queue depth, consumer errors, dead-letter count."),
    Candidate("AWS CloudTrail", "ops", "audit",
              "Who changed the queue or the consumers."),
    Candidate("AWS X-Ray", "ops", "tracing",
              "Following one event from endpoint to database."),
    # ── security ──
    Candidate("AWS KMS", "security", "kms",
              "Encryption for the queue and the table."),
    Candidate("AWS Secrets Manager", "security", "secrets",
              "Signing secrets for verifying each provider's webhooks."),
    Candidate("Amazon GuardDuty", "security", "threat", "Account detection."),
    Candidate("AWS Security Hub", "security", "posture", "Configuration drift."),
    # ── resilience ──
    Candidate("AWS Backup", "resilience", "backup", "The event table."),
    Candidate("Cross-region backup copy", "resilience", "backup_copy",
              "A copy elsewhere, for events that cannot be re-requested."),
)


FORBIDDEN = (
    Forbidden(
        "load balancer",
        "API Gateway is the endpoint. A balancer in front of it balances "
        "across nothing, and an always-on fleet behind it is exactly the "
        "idle capacity a burst-shaped workload should not be buying.",
        has_load_balancer,
    ),
    Forbidden(
        "CDN",
        "Providers POST to this endpoint; nobody browses it. An edge "
        "cache in front of a webhook receiver would cache responses "
        "nobody reads twice.",
        has_cdn,
    ),
    Forbidden(
        "always-on instances",
        "The rate is 0.5 events/second with bursts. Instances provisioned "
        "for the burst idle for the other 23 hours, which is the cost "
        "shape a queue plus scaling consumers exists to avoid.",
        lambda spec: spec.compute_count > 0,
    ),
)


def build(*, tier_level, constraints, load, region, **_) -> ArchitectureSpec:
    """One tier of an event-ingestion pipeline."""
    events = _events_per_month(constraints)
    routed = tier_level >= 2      # a bus, rather than point-to-point
    replayable = tier_level >= 3  # an ordered log and a raw archive
    # A STATED "we cannot drop a single one" is a requirement, not an
    # upgrade. It applies on the cheapest tier too -- a design that fails
    # it is not a cheaper option, it is a non-compliant one.
    resilient = resilience_wanted(constraints, tier_level)

    return ArchitectureSpec(
        name=f"tier_{tier_level}",
        region=region,
        # Nothing runs between bursts.
        compute_count=0,
        fargate_task_count=0,
        database_vcpu=None,
        database_memory_gb=None,
        load_balancer=False,
        serves_requests=False,
        nat_gateway_count=0,
        cdn_gb=0.0,
        # ── ingest ──
        apigateway_requests_per_month=events,
        # ── THE QUEUE. Rung one, not a tier upsell: it is what makes
        # "we cannot drop a single one" true, and a design without it
        # fails the stated requirement at any price. ──
        queue_requests_per_month=events * SQS_REQUESTS_PER_EVENT,
        # ── consumers ──
        lambda_invocations_per_month=events,
        lambda_avg_ms=DEFAULT_CONSUMER_MS,
        lambda_memory_mb=DEFAULT_CONSUMER_MB,
        # ── the writes and the idempotency check ──
        dynamodb_write_units_per_month=events * 3,
        dynamodb_read_units_per_month=events,
        dynamodb_storage_gb=max(1.0, _archive_gb(constraints) * 3),
        # ── the email the prompt names ──
        emails_per_month=float(constraints.emails_per_month or events),
        # ── ops and resilience on every tier ──
        monitored_metrics=25,
        audit_logging=True,
        backup_gb=(
            0.0 if constraints.durability == "ephemeral"
            else max(1.0, _archive_gb(constraints) * 3)
        ),
        backup_retention_days=(
            0 if constraints.durability == "ephemeral" else 35
        ),
        # ── tier 2: a bus, alerting, keys, signing secrets, tracing ──
        eventbridge_events_per_month=events if routed else 0.0,
        notifications_per_month=events * 0.01 if routed else 0.0,
        kms_key_count=1 if routed else None,
        secret_count=3 if routed else 0,
        tracing_monthly_traces=events if routed else 0.0,
        # ── tier 3: ordering, replay, a raw archive to query ──
        stream_shards=2 if replayable else 0,
        stream_put_units=events if replayable else 0.0,
        firehose_gb_per_month=_archive_gb(constraints) if replayable else 0.0,
        storage_gb=_archive_gb(constraints) * 12 if replayable else 0.0,
        s3_put_requests=events if replayable else 0.0,
        athena_tb_scanned_per_month=0.05 if replayable else 0.0,
        lifecycle_gb=(
            _archive_gb(constraints) * 12 * COLD_SHARE if replayable else 0.0
        ),
        object_lock=resilient,
        backup_copy_gb=(
            max(1.0, _archive_gb(constraints) * 3) if resilient else 0.0
        ),
        backup_seed_gb=(
            max(1.0, _archive_gb(constraints) * 3) if resilient else 0.0
        ),
        backup_transfer_gb=_archive_gb(constraints) if resilient else 0.0,
        threat_detection=replayable,
        posture_monthly_checks=200.0 if replayable else 0.0,
    )


GRAPH = ArchetypeGraph(
    name="event_driven",
    summary="Reacting to external events rather than to direct user "
            "requests — webhooks, queues, uploads.",
    sources=(
        "AWS Architecture Center: webhook ingestion (API Gateway -> SQS "
        "-> Lambda), and the event-driven architecture reference for "
        "EventBridge routing",
        "Well-Architected reliability pillar: queue to decouple producers "
        "from consumer availability, so a consumer restart does not lose "
        "work in flight",
        "Well-Architected cost pillar: scale consumers with queue depth "
        "rather than provisioning for the burst",
    ),
    sizing=SIZING,
    candidates=CANDIDATES,
    forbidden=FORBIDDEN,
    build=build,
    tier_notes={
        2: "Routing: consumers wired directly to the queue → EventBridge "
           "routing by provider and event type, with signing secrets and "
           "tracing — removes a fourth provider needing a deploy, and "
           "removes guesswork when one event out of a million goes wrong.",
        3: "Replay: a queue that forgets once acknowledged → an ordered "
           "Kinesis log plus every raw event archived and queryable — "
           "removes 'we processed it wrong and cannot reconstruct what "
           "arrived' as a possibility, which is the one failure a "
           "payments pipeline cannot answer for.",
    },
)
