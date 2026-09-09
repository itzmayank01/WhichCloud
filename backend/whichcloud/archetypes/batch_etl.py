"""Scheduled work that processes data on a timetable and is idle between runs.

PROBE-2, verbatim:

    "Every night we pull about 500 GB of sensor readings off our factory
     machines and turn them into next-day reports. Nobody uses it during
     the day. If a night's run fails we can rerun it in the morning."

Three things that description says plainly, and the old engine acted on
none of them:

  "nobody uses it during the day"     -> billed 730 compute hours anyway,
                                         ~12x the real figure
  "we can rerun it in the morning"    -> on-demand capacity, when the
                                         workload had just volunteered
                                         for spot
  "sensor readings"                   -> a relational database, for
                                         append-only telemetry

The third is the one that matters most. Time-series data in an OLTP store
is not merely a costlier design, it is the wrong storage engine: the
access pattern is append-and-scan, not row-level read-modify-write, and a
relational primary makes every later analytics decision worse. It is
FORBIDDEN here rather than merely not selected.

CANDIDATE SET
From the AWS Analytics Lens and the Architecture Center's serverless-ETL
reference (S3 landing zone -> Glue crawler/ETL -> partitioned Parquet in a
curated zone -> Athena, orchestrated on a schedule), plus the
Well-Architected cost pillar's guidance on interruptible capacity for
restartable batch work.

WHAT THE TIERS BUY
The progression is about WHO RUNS THE JOB and WHAT THE RESULTS LAND IN:

  cheapest   your own instance, on spot, awake only while a run is in
             flight. The most cost-efficient thing that works, and only
             legitimate because the text volunteered restartability.
  balanced   managed ETL replaces the instance entirely -- no host to
             patch, no scheduler to babysit -- and results become
             queryable in place.
  optimized  a purpose-built columnar warehouse instead of scanning
             files, plus immutability and a second-region copy for data
             that cannot be regenerated once the sensors have moved on.
"""

from __future__ import annotations

from whichcloud.archetypes.base import (
    ArchetypeGraph, Candidate, Forbidden, SizingDriver,
    has_cdn, has_load_balancer, has_relational_database,
)
from whichcloud.estimator import ArchitectureSpec

#: Hours a run takes when the text gives a data volume but no duration.
#: Deliberately conservative -- over-stating the window costs money on
#: the bill, under-stating it quotes a number the job cannot finish in.
DEFAULT_RUN_HOURS = 2.0

#: How much of the landing zone is still hot. Raw sensor data is read
#: once by the job that transforms it and then rarely again, which is
#: exactly what lifecycle tiering is for.
HOT_SHARE = 0.35

#: Curated output as a fraction of raw input. Columnar Parquet with
#: partitioning is materially smaller than the raw feed it came from;
#: 0.25 is the conservative end of what compression typically achieves.
CURATED_SHARE = 0.25

#: DPU-hours per GB processed. AWS Glue bills per DPU-hour and a DPU
#: handles roughly this much in an hour on a straightforward transform.
DPU_HOURS_PER_GB = 0.004

#: TB scanned per query, and queries per run. Athena bills per TB
#: scanned, and partitioned Parquet is what keeps that number small --
#: which is why the curated zone exists at all.
QUERIES_PER_RUN = 20


def _gb_per_run(constraints) -> float:
    """Data one run reads. storage_gb is where "500 GB of sensor
    readings" lands -- the figure the whole plan is sized from."""
    return float(
        constraints.storage_gb or constraints.content_storage_gb or 100.0
    )


def _runs_per_month(constraints) -> float:
    """Nightly unless the text says otherwise."""
    return 30.0


def _run_hours(constraints) -> float:
    """How long one run takes.

    A full 24 means the text never said, so the default applies -- this
    archetype is by definition not running all day. Zero would mean the
    same thing and is guarded at extraction, but guarded again here
    because an archetype must not depend on a caller having sanitised
    its input.
    """
    hours = float(getattr(constraints, "active_hours_per_day", 24.0) or 24.0)
    if hours <= 0 or hours >= 24.0:
        return DEFAULT_RUN_HOURS
    return hours


def _raw_gb(constraints) -> float:
    """The landing zone accumulates. One month retained is the floor."""
    return _gb_per_run(constraints) * _runs_per_month(constraints)


def _curated_gb(constraints) -> float:
    return _raw_gb(constraints) * CURATED_SHARE


def _describe(constraints, load) -> str:
    return (
        f"{_gb_per_run(constraints):,.0f} GB per run x "
        f"{_runs_per_month(constraints):,.0f} runs/month, "
        f"{_run_hours(constraints):.1f}h per run "
        f"({_run_hours(constraints) * _runs_per_month(constraints):,.0f} "
        f"compute hours, not 730)"
    )


SIZING = SizingDriver(
    name="GB per run and run duration",
    fields=("storage_gb", "active_hours_per_day", "interruptible"),
    describe=_describe,
)


CANDIDATES = (
    # ── store: the two zones every ETL pipeline has ──
    Candidate("Amazon S3 (landing zone)", "store", "storage",
              "Raw sensor data as it arrives, before anything touches it.",
              instead_of="loading raw telemetry straight into a database"),
    Candidate("Amazon S3 (curated zone)", "store", "storage",
              "Partitioned Parquet the query layer reads."),
    Candidate("S3 requests", "store", "s3_requests",
              "Per-object PUT and GET across both zones."),
    Candidate("S3 lifecycle tiering", "store", "storage_lifecycle",
              "Raw data is read once and rarely again; archive it.",
              instead_of="paying hot rates for last quarter's readings"),
    # ── compute: who actually runs the job ──
    Candidate("EC2 Spot", "compute", "compute",
              "Your own runner, awake only during a run, on interruptible "
              "capacity because the work was stated restartable.",
              instead_of="an on-demand instance idling 22 hours a day"),
    Candidate("AWS Glue", "compute", "glue",
              "Managed ETL billed per DPU-hour — no host to patch and no "
              "scheduler to babysit.",
              instead_of="a self-managed runner you keep alive yourself"),
    # ── analytics: what the results land in ──
    Candidate("Amazon Athena", "analytics", "athena",
              "SQL over the curated zone, billed per TB scanned.",
              instead_of="standing a database up to answer twenty queries"),
    Candidate("Amazon Redshift", "analytics", "warehouse",
              "Purpose-built columnar store for reports that are read "
              "repeatedly.",
              instead_of="re-scanning the same Parquet on every query"),
    # ── async: what starts the run and reports on it ──
    Candidate("Amazon EventBridge Scheduler", "async", "eventbridge",
              "Starts the run on a timetable."),
    Candidate("Amazon SQS", "async", "queue",
              "Work items for a run that fans out across shards."),
    Candidate("Amazon SNS", "async", "notification",
              "Tells somebody when a night's run failed."),
    # ── ops ──
    Candidate("Amazon CloudWatch", "ops", "monitoring",
              "Run duration, failure count, records processed."),
    Candidate("AWS CloudTrail", "ops", "audit",
              "Who changed the job or the buckets."),
    Candidate("AWS X-Ray", "ops", "tracing",
              "Where a slow run spent its time."),
    # ── security ──
    Candidate("AWS KMS", "security", "kms",
              "Encryption for both zones."),
    Candidate("AWS Secrets Manager", "security", "secrets",
              "Credentials for the source systems the job pulls from."),
    Candidate("Amazon GuardDuty", "security", "threat",
              "Detection on the account holding the data."),
    Candidate("AWS Security Hub", "security", "posture",
              "Whether either zone is exposed."),
    # ── resilience ──
    Candidate("AWS Backup", "resilience", "backup",
              "The curated zone, which is expensive to regenerate."),
    Candidate("Cross-region backup copy", "resilience", "backup_copy",
              "A copy elsewhere, for data the sensors will not produce "
              "again."),
    Candidate("Egress", "store", "network",
              "Reports leaving for whoever consumes them."),
)


FORBIDDEN = (
    Forbidden(
        "relational database",
        "Sensor readings are append-only time-series. A relational store "
        "is the wrong engine for append-and-scan, not merely a costlier "
        "one — it makes every later analytics decision worse, and this "
        "workload's primary home is object storage with a query layer "
        "over it.",
        has_relational_database,
    ),
    Forbidden(
        "load balancer",
        "Nothing serves requests. There is no endpoint to balance across, "
        "and a balancer here is $17/month for traffic that never arrives.",
        has_load_balancer,
    ),
    Forbidden(
        "CDN",
        "There are no viewers. A cache in front of a nightly job caches "
        "nothing.",
        has_cdn,
    ),
)


def build(*, tier_level, constraints, load, region, **_) -> ArchitectureSpec:
    """One tier of a scheduled batch pipeline."""
    gb_run = _gb_per_run(constraints)
    raw = _raw_gb(constraints)
    curated = _curated_gb(constraints)
    runs = _runs_per_month(constraints)
    run_hours = _run_hours(constraints)

    managed = tier_level >= 2      # Glue replaces the self-managed runner
    warehoused = tier_level >= 3   # a columnar store replaces file scans

    # SPOT IS EARNED, NOT ASSUMED. Interruptible capacity is reclaimed
    # with two minutes' notice, so only a STATED tolerance for re-running
    # justifies it. Silence means on-demand.
    spot = bool(constraints.interruptible) and not managed

    return ArchitectureSpec(
        name=f"tier_{tier_level}",
        region=region,
        # ── compute: only while a run is in flight ──
        # The whole month is 730 hours; this job wants run_hours x runs.
        compute_count=0 if managed else 1,
        compute_vcpu=4,
        compute_memory_gb=16.0,
        compute_duty_cycle=(
            1.0 if managed else max(0.01, min(1.0, run_hours * runs / 730.0))
        ),
        use_spot=spot,
        arch="arm64",
        # Nothing serves requests, so none of the request-path layer
        # applies. Stated rather than left to default, because these are
        # the components the old engine added anyway.
        database_vcpu=None,
        database_memory_gb=None,
        load_balancer=False,
        serves_requests=False,
        nat_gateway_count=0,
        cdn_gb=0.0,
        # ── the two zones ──
        storage_gb=raw + curated,
        s3_put_requests=runs * 2000,
        s3_get_requests=runs * 5000,
        egress_gb=curated * 0.05,
        # ── tier 2: managed ETL, a query layer, keys and alerting ──
        glue_dpu_hours_per_month=(
            gb_run * runs * DPU_HOURS_PER_GB if managed else 0.0
        ),
        athena_tb_scanned_per_month=(
            (curated / 1024.0) * QUERIES_PER_RUN / 100.0 if managed else 0.0
        ),
        kms_key_count=1 if managed else None,
        secret_count=2 if managed else 0,
        notifications_per_month=runs if managed else 0.0,
        eventbridge_events_per_month=runs * 50,
        # ── tier 3: a purpose-built store, immutability, DR ──
        warehouse_node_count=2 if warehoused else 0,
        warehouse_node_vcpu=2 if warehoused else None,
        warehouse_node_memory_gb=16.0 if warehoused else None,
        lifecycle_gb=raw * (1.0 - HOT_SHARE) if warehoused else 0.0,
        object_lock=warehoused,
        backup_copy_gb=curated if warehoused else 0.0,
        backup_seed_gb=curated if warehoused else 0.0,
        backup_transfer_gb=curated * 0.1 if warehoused else 0.0,
        threat_detection=warehoused,
        posture_monthly_checks=200.0 if warehoused else 0.0,
        tracing_monthly_traces=100_000.0 if warehoused else 0.0,
        # ── ops and resilience, on every tier ──
        monitored_metrics=20,
        audit_logging=True,
        backup_gb=0.0 if constraints.durability == "ephemeral" else curated,
        backup_retention_days=(
            0 if constraints.durability == "ephemeral" else 30
        ),
    )


GRAPH = ArchetypeGraph(
    name="batch_etl",
    summary="Scheduled work that processes data on a timetable and is idle "
            "in between.",
    sources=(
        "AWS Analytics Lens: landing/curated zone separation with a "
        "query layer over partitioned columnar data",
        "AWS Architecture Center: serverless ETL (S3 -> Glue -> Athena) "
        "orchestrated on a schedule",
        "Well-Architected cost pillar: interruptible capacity for "
        "restartable batch work, and matching supply to demand rather "
        "than provisioning for the peak all month",
    ),
    sizing=SIZING,
    candidates=CANDIDATES,
    forbidden=FORBIDDEN,
    build=build,
    tier_notes={
        2: "Execution: a self-managed runner you keep alive → AWS Glue "
           "billed per DPU-hour, with Athena querying the curated zone in "
           "place — removes host patching, scheduler babysitting and the "
           "standing instance as risks.",
        3: "Results: re-scanning Parquet on every query → a columnar "
           "warehouse, plus Object Lock and a second-region copy — removes "
           "repeat scan cost, and removes losing readings the sensors will "
           "never produce again.",
    },
)
