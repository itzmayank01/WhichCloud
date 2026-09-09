"""Serving predictions from a trained model.

PROBE-4, verbatim:

    "We have a trained model that scores loan applications. About 50
     predictions a second during business hours, almost none at night."

Severity CRITICAL, for two independent reasons:

  * NO ACCELERATED COMPUTE CONCEPT EXISTED. Not a wiring gap -- there was
    no GPU or inference instance family anywhere in the engine, and no
    managed endpoint. A model-serving workload was costed as a web
    application with a relational database behind it.

  * "during business hours" WAS READ AS AN UPTIME REQUIREMENT. The phrase
    table matched it as availability=high, which is a false positive on a
    statement about TRAFFIC TIMING. The prompt says when the load
    arrives, not that downtime is unacceptable -- and the difference
    decides whether the endpoint may be scaled down at night, which is
    most of what makes this shape cheap.

"almost none at night" is the whole cost story. An endpoint held at full
size around the clock costs three times one sized for the nine hours it
actually serves, and the duty cycle is the difference.

CANDIDATE SET
From the SageMaker inference decision guide (real-time endpoints for
steady low-latency scoring; asynchronous and serverless inference answer
different questions and are deliberately not offered here), and the
Well-Architected machine-learning lens on separating the model artefact
store from the serving fleet.
"""

from __future__ import annotations

from whichcloud.archetypes.base import (
    ArchetypeGraph, Candidate, Forbidden, SizingDriver,
    has_cdn, has_load_balancer, has_relational_database, resilience_wanted,
)
from whichcloud.estimator import ArchitectureSpec

#: Predictions one endpoint instance sustains per second. A tabular
#: scoring model is not a language model; this is the conservative end
#: for a gradient-boosted or small neural scorer.
PREDICTIONS_PER_INSTANCE_PER_SEC = 40.0

#: The endpoint type chosen when the model fits comfortably in CPU
#: memory. Loan scoring is tabular, so the honest default is a
#: compute-optimised instance rather than a GPU nobody needs.
CPU_ENDPOINT = "ml.c6i.xlarge"

#: Chosen when the model is large enough to want accelerator memory.
GPU_ENDPOINT = "ml.g5.xlarge"

#: Above this, the artefact stops fitting comfortably alongside a
#: runtime on a general-purpose instance and an accelerator earns its
#: place. Deliberately generous: a GPU nobody needs is the single
#: easiest way to triple this bill.
GPU_MODEL_GB = 8.0

#: Self-managed equivalents, for the cheapest tier.
CPU_VCPU, CPU_MEMORY_GB = 4, 8.0

#: Default artefact size when the text does not say. Surfaced as an
#: assumption, and it only moves the endpoint choice at the boundary.
DEFAULT_MODEL_GB = 2.0


def _predictions_per_second(constraints) -> float:
    """Peak prediction rate.

    requests_per_day is already normalised over the ACTIVE window (Part
    3), so dividing by that window rather than by a full day is what
    keeps "50/sec in business hours" from becoming 19/sec.
    """
    hours = _active_hours(constraints)
    per_day = float(constraints.requests_per_day or 0)
    if per_day <= 0:
        return 0.0
    return per_day / (hours * 3600.0)


def _active_hours(constraints) -> float:
    hours = float(getattr(constraints, "active_hours_per_day", 24.0) or 24.0)
    return max(1.0, min(24.0, hours))


def _model_gb(constraints) -> float:
    return float(constraints.model_size_gb or DEFAULT_MODEL_GB)


def _needs_accelerator(constraints) -> bool:
    return _model_gb(constraints) >= GPU_MODEL_GB


def _endpoint_type(constraints) -> str:
    return GPU_ENDPOINT if _needs_accelerator(constraints) else CPU_ENDPOINT


def _instance_count(constraints) -> int:
    rate = _predictions_per_second(constraints)
    if rate <= 0:
        return 1
    import math

    return max(1, math.ceil(rate / PREDICTIONS_PER_INSTANCE_PER_SEC))


def _endpoint_hours(constraints) -> float:
    """Hours a month the endpoint is up.

    "almost none at night" is the whole cost story: an endpoint held at
    full size around the clock costs three times one sized for the nine
    hours it serves.
    """
    return _active_hours(constraints) * 30.0


def _describe(constraints, load) -> str:
    return (
        f"{_predictions_per_second(constraints):,.0f} predictions/sec at peak "
        f"across {_instance_count(constraints)} endpoint instance(s), "
        f"{_model_gb(constraints):.1f} GB model on "
        f"{_endpoint_type(constraints)}, "
        f"up {_endpoint_hours(constraints):,.0f} hours/month "
        f"(not 730)"
    )


SIZING = SizingDriver(
    name="predictions per second and model size",
    fields=("requests_per_day", "model_size_gb", "active_hours_per_day"),
    describe=_describe,
)


CANDIDATES = (
    # ── compute: who serves the model ──
    Candidate("EC2 inference instance", "compute", "compute",
              "Your own serving process, up only during the hours the "
              "model is asked for anything.",
              instead_of="a managed endpoint you pay a premium to not "
                         "operate"),
    Candidate("SageMaker real-time endpoint", "compute", "inference",
              "Managed serving with autoscaling and blue/green model "
              "rollout.",
              instead_of="patching, restarting and rolling back the "
                         "serving host yourself"),
    # ── ingest ──
    Candidate("Amazon API Gateway", "ingest", "apigateway",
              "The scoring endpoint callers reach."),
    Candidate("AWS Lambda", "compute", "lambda-requests",
              "Request shaping and feature lookup in front of the model."),
    Candidate("Lambda duration", "compute", "lambda-duration",
              "Per-GB-second charge for that shaping."),
    # ── store ──
    Candidate("Amazon S3 (model artefacts)", "store", "storage",
              "Versioned model files the endpoint loads.",
              instead_of="baking the model into the serving image"),
    Candidate("S3 requests", "store", "s3_requests",
              "Artefact loads on cold start and rollout."),
    Candidate("Amazon DynamoDB (feature store)", "store", "dynamodb-reads",
              "Features looked up per scoring call.",
              instead_of="re-querying a relational system per prediction"),
    Candidate("DynamoDB writes", "store", "dynamodb-writes",
              "Prediction log, for later monitoring of drift."),
    Candidate("DynamoDB storage", "store", "dynamodb-storage",
              "The feature and prediction tables."),
    Candidate("Amazon ElastiCache", "store", "cache",
              "Hot features, so a scoring call does not pay a round trip.",
              instead_of="a feature lookup on the critical path of every "
                         "prediction"),
    Candidate("S3 lifecycle tiering", "store", "storage_lifecycle",
              "Superseded model versions, kept but not at hot rates."),
    # ── analytics ──
    Candidate("Amazon Athena", "analytics", "athena",
              "Querying the prediction log for drift and fairness review."),
    # ── ops ──
    Candidate("Amazon CloudWatch", "ops", "monitoring",
              "Latency, invocation count, model errors."),
    Candidate("AWS CloudTrail", "ops", "audit",
              "Who deployed which model version — the audit trail a "
              "lending decision needs."),
    Candidate("AWS X-Ray", "ops", "tracing",
              "Where a slow scoring call spent its time."),
    # ── security ──
    Candidate("AWS KMS", "security", "kms",
              "Encryption for artefacts and the prediction log."),
    Candidate("AWS Secrets Manager", "security", "secrets",
              "Credentials for the systems features are pulled from."),
    Candidate("Amazon GuardDuty", "security", "threat", "Account detection."),
    Candidate("AWS Security Hub", "security", "posture", "Configuration drift."),
    # ── resilience ──
    Candidate("AWS Backup", "resilience", "backup",
              "Artefacts and prediction history."),
    Candidate("Cross-region backup copy", "resilience", "backup_copy",
              "A copy elsewhere of the model that made a decision."),
)


FORBIDDEN = (
    Forbidden(
        "relational database as the artefact store",
        "A model artefact is a large binary read whole on load, not a set "
        "of rows. Object storage is where it belongs, and a relational "
        "instance here bills by the hour to hold a file.",
        has_relational_database,
    ),
    Forbidden(
        "load balancer",
        "A managed endpoint already fronts its own fleet, and API Gateway "
        "fronts the endpoint. A third balancer balances across nothing.",
        has_load_balancer,
    ),
    Forbidden(
        "CDN",
        "Predictions are computed per request and depend on the features "
        "supplied. There is nothing cacheable at an edge.",
        has_cdn,
    ),
)


def build(*, tier_level, constraints, load, region, **_) -> ArchitectureSpec:
    """One tier of a model-serving endpoint."""
    count = _instance_count(constraints)
    hours = _endpoint_hours(constraints)
    duty = min(1.0, max(0.01, hours / 730.0))
    predictions = float(constraints.requests_per_day or 0) * 30.0
    model_gb = _model_gb(constraints)

    managed = tier_level >= 2       # SageMaker replaces the self-managed host
    featured = tier_level >= 3      # a feature cache and a queryable log
    resilient = resilience_wanted(constraints, tier_level)

    return ArchitectureSpec(
        name=f"tier_{tier_level}",
        region=region,
        # ── serving ──
        # Tier 1 runs it yourself; tier 2 hands the host to SageMaker.
        # Either way it is up for the hours it serves, not for the month.
        compute_count=0 if managed else count,
        compute_vcpu=CPU_VCPU,
        compute_memory_gb=CPU_MEMORY_GB,
        compute_duty_cycle=duty,
        inference_instance=_endpoint_type(constraints) if managed else "",
        inference_instance_count=count if managed else 0,
        inference_hours_per_month=hours if managed else 0.0,
        # A model artefact is a file, not a table.
        database_vcpu=None,
        database_memory_gb=None,
        load_balancer=False,
        cdn_gb=0.0,
        # The self-managed host sits in a private subnet and reaches S3
        # and CloudWatch through VPC endpoints. No NAT gateway: this
        # workload has no general internet egress to pay $32/month for,
        # and buying one to satisfy a checkbox would be the padding this
        # engine refuses.
        private_subnets=not managed,
        gateway_endpoints=2 if not managed else 0,
        vpc_endpoints=3 if not managed else 0,
        vpc_endpoint_gb=5.0 if not managed else 0.0,
        nat_gateway_count=0,
        serves_requests=True,
        # ── artefacts ──
        storage_gb=max(1.0, model_gb * 5),
        s3_get_requests=count * 60,
        # ── ops and resilience, on every tier ──
        monitored_metrics=25,
        audit_logging=True,
        backup_gb=(
            0.0 if constraints.durability == "ephemeral"
            else max(1.0, model_gb * 5)
        ),
        backup_retention_days=(
            0 if constraints.durability == "ephemeral" else 35
        ),
        # ── tier 2: a managed endpoint, a front door, keys, tracing ──
        apigateway_requests_per_month=predictions if managed else 0.0,
        lambda_invocations_per_month=predictions if managed else 0.0,
        lambda_avg_ms=40.0,
        lambda_memory_mb=512.0,
        kms_key_count=1 if managed else None,
        secret_count=2 if managed else 0,
        tracing_monthly_traces=predictions if managed else 0.0,
        # ── tier 3: features off the critical path, a queryable log ──
        cache_vcpu=2 if featured else None,
        cache_memory_gb=4.0 if featured else None,
        dynamodb_read_units_per_month=predictions if featured else 0.0,
        dynamodb_write_units_per_month=predictions if featured else 0.0,
        dynamodb_storage_gb=max(1.0, model_gb) if featured else 0.0,
        athena_tb_scanned_per_month=0.05 if featured else 0.0,
        lifecycle_gb=model_gb * 4 if featured else 0.0,
        threat_detection=featured,
        posture_monthly_checks=200.0 if featured else 0.0,
        # ── resilience: a stated requirement applies on every tier ──
        object_lock=resilient,
        backup_copy_gb=max(1.0, model_gb * 5) if resilient else 0.0,
        backup_seed_gb=max(1.0, model_gb * 5) if resilient else 0.0,
        backup_transfer_gb=model_gb if resilient else 0.0,
    )


GRAPH = ArchetypeGraph(
    name="ml_inference",
    summary="Serving predictions from a trained model.",
    sources=(
        "SageMaker inference decision guide: real-time endpoints for "
        "steady low-latency scoring (asynchronous and serverless "
        "inference bill on different shapes and answer different "
        "questions, so neither is offered here)",
        "Well-Architected machine-learning lens: keep the model artefact "
        "store separate from the serving fleet, and version artefacts",
        "Well-Architected cost pillar: match endpoint capacity to the "
        "hours the model is actually asked for anything",
    ),
    sizing=SIZING,
    candidates=CANDIDATES,
    forbidden=FORBIDDEN,
    build=build,
    tier_notes={
        2: "Serving: a host you patch and restart → a managed real-time "
           "endpoint behind API Gateway, with tracing — removes the "
           "serving host as something to operate, and removes "
           "model rollout being a deploy you hand-roll.",
        3: "Features: a lookup on the critical path of every prediction → "
           "a hot feature cache with the prediction log queryable for "
           "drift — removes per-call latency you cannot explain, and "
           "removes 'we cannot tell what the model was told' when a "
           "lending decision is challenged.",
    },
)
