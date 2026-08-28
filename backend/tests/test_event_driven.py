"""The event_driven archetype — fixture 9, the IoT telemetry case.

Live evidence that opened this: an IoT telemetry prompt (5M events/day,
continuous processing, restartable jobs) produced EC2 + ElastiCache + RDS
behind an ALB, RDS at 60% of a $13,222 bill, with no streaming ingest, no
purpose-built store, and no Spot despite restartable work being stated.

Every assertion below is one of the acceptance criteria for that fixture.

    .venv/bin/pytest tests/test_event_driven.py -q
"""

from __future__ import annotations

import pytest

from whichcloud.architecture.costed import PricedNode, architecture_from
from whichcloud.engine import event_driven_spec, recommend
from whichcloud.estimator import ArchitectureSpec, estimate
from whichcloud.pricing.store import stats
from whichcloud.requirements import Requirement
from whichcloud import topology as topo

pytestmark = pytest.mark.skipif(
    sum(r["n"] for r in stats()) == 0, reason="needs an ingested price catalog"
)

# Fixture 9: the IoT telemetry workload, as the extractor reads it.
IOT = Requirement(
    goal="IoT telemetry ingestion and processing",
    workload_type="mixed",
    traffic_scale="high",
    interruptible=True,
    event_driven=True,
    telemetry=True,
    needs_analytics=True,
    daily_transactions=5_000_000,
    region="india",
    storage_gb=2000.0,
    egress_gb=500.0,
)


def _families(option) -> set[str]:
    """Service families in an option, one entry per service (size/count
    stripped) so 'differs by service' is measured, not 'differs by size'."""
    return {i.label.split(" ×")[0].split(" (")[0] for i in option.estimate.items}


def _diagram_services(option) -> frozenset[str]:
    g = topo.build(option.spec, option.estimate, option.applied)
    nodes = [
        PricedNode(
            kind=n.kind, label=n.label,
            monthly_usd=float(n.monthly_usd) if n.priced else None, sku=n.sku,
        )
        for n in g.nodes if n.kind != "client"
    ]
    arch, _ = architecture_from(
        nodes, option.spec.database_multi_az,
        option.spec.nat_gateway_count or None, option.spec.serves_requests,
    )
    return frozenset(s.name for s in arch.services)


# ── the 5 new services price ──────────────────────────────────────────────


def test_the_event_driven_services_all_price():
    spec = ArchitectureSpec(
        name="ed", region="india", compute_count=0,
        iot_messages_per_month=150_000_000, timestream_write_gb=150,
        timestream_storage_gb=1800, firehose_gb_per_month=150,
        athena_tb_scanned_per_month=5, glue_dpu_hours_per_month=200,
    )
    est = estimate(spec, "aws")
    assert not est.missing
    labels = {i.label for i in est.items}
    for expected in ("IoT Core messages", "Timestream writes", "Firehose delivery",
                     "Athena data scanned", "Glue ETL"):
        assert expected in labels


# ── acceptance criteria ───────────────────────────────────────────────────


def test_no_tier_puts_telemetry_in_rds():
    """The load-bearing rule: a stated telemetry stream never lands in a
    relational database as its primary store."""
    for o in recommend(IOT, "aws"):
        assert o.spec.database_vcpu is None, o.label
        labels = {i.label for i in o.estimate.items}
        assert not any(l.startswith("Database") for l in labels), o.label
        # And it IS in the purpose-built store.
        assert any(l.startswith("Timestream") for l in labels), o.label


def test_cheapest_uses_spot_for_restartable_work():
    cheapest = recommend(IOT, "aws")[0]
    assert cheapest.spec.use_spot is True


def test_each_tier_differs_from_the_next_by_at_least_three_services():
    options = recommend(IOT, "aws")
    for lower, higher in zip(options, options[1:]):
        a, b = _families(lower), _families(higher)
        differ = (a - b) | (b - a)
        assert len(differ) >= 3, (
            f"{lower.label} -> {higher.label} differ by only "
            f"{len(differ)} services: {sorted(differ)}"
        )


def test_each_tier_renders_a_distinct_diagram():
    diagrams = [_diagram_services(o) for o in recommend(IOT, "aws")]
    assert len(set(diagrams)) == 3, "tiers must not share a diagram"
    assert not any("Amazon RDS" in d for d in diagrams)


def test_the_pipeline_uses_streaming_ingest_and_purpose_built_stores():
    """The shape the web template lacked: a stream in, a time-series store,
    and analytics that are not a relational read replica."""
    optimized = recommend(IOT, "aws")[2]
    names = _diagram_services(optimized)
    assert "Amazon MSK" in names or "Amazon Kinesis Data Streams" in names
    assert "Amazon Timestream" in names
    assert "AWS IoT Core" in names
    assert "Amazon OpenSearch" in names or "Amazon Redshift" in names


def test_totals_are_reported_for_the_record():
    """Not an assertion of exact totals -- those are heuristic and will move --
    but a guard that all three price, are ordered, and land well under the
    $5,765 / $11,403 / $13,222 the mis-routed web shape charged."""
    totals = [float(o.monthly) for o in recommend(IOT, "aws")]
    assert all(t > 0 for t in totals)
    assert totals[0] <= totals[1] <= totals[2]
    # The web misroute over-charged with RDS/cache/ALB it never needed.
    assert totals[2] < 13_222
