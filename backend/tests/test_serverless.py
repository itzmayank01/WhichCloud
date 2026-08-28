"""The serverless architecture shape, end to end.

The engine used to fit every workload onto one shape — a 3-tier server app.
A serverless-suited workload is a different architecture, not a smaller one:
Lambda + API Gateway + DynamoDB, no VPC, no NAT, no standby database, and a
bill that falls to almost nothing when idle. These lock that in.

    .venv/bin/pytest tests/test_serverless.py -q
"""

from __future__ import annotations

from whichcloud.architecture.costed import PricedNode, architecture_from
from whichcloud.engine import recommend, serverless_spec
from whichcloud.estimator import ArchitectureSpec, estimate
from whichcloud.pricing.store import stats
from whichcloud.requirements import Requirement
from whichcloud import topology as topo

import pytest

pytestmark = pytest.mark.skipif(
    sum(r["n"] for r in stats()) == 0, reason="needs an ingested price catalog"
)


def _serverless_req(**over) -> Requirement:
    base = dict(
        goal="a spiky event-driven API",
        workload_type="api",
        traffic_scale="medium",
        serverless=True,
        daily_transactions=100_000,
        region="india",
        storage_gb=50.0,
        egress_gb=100.0,
    )
    base.update(over)
    return Requirement(**base)


# ── pricing ──────────────────────────────────────────────────────────────


def test_the_three_serverless_meters_ingested_and_price():
    spec = ArchitectureSpec(
        name="s", region="india", compute_count=0,
        lambda_invocations_per_month=30_000_000, lambda_avg_ms=150,
        lambda_memory_mb=512, apigateway_requests_per_month=30_000_000,
        dynamodb_read_units_per_month=90_000_000,
        dynamodb_write_units_per_month=30_000_000, dynamodb_storage_gb=50,
    )
    est = estimate(spec, "aws")
    labels = {i.label for i in est.items}
    assert "Lambda requests" in labels
    assert "Lambda duration" in labels
    assert "API Gateway requests" in labels
    assert "DynamoDB reads" in labels
    assert "DynamoDB writes" in labels
    assert not est.missing
    assert est.total_monthly > 0


def test_provisioned_concurrency_costs_more_duration():
    """The reliability lever is priced, not asserted: warm environments bill
    GB-seconds around the clock, so the duration line must go up."""
    common = dict(
        name="s", region="india", compute_count=0,
        lambda_invocations_per_month=10_000_000, lambda_avg_ms=150,
        lambda_memory_mb=512,
    )
    cold = estimate(ArchitectureSpec(**common), "aws")
    warm = estimate(
        ArchitectureSpec(lambda_provisioned_concurrency=5, **common), "aws"
    )
    assert warm.total_monthly > cold.total_monthly


# ── engine ───────────────────────────────────────────────────────────────


def test_serverless_spec_has_no_servers():
    spec = serverless_spec(_serverless_req(), "Cheapest")
    assert spec.compute_count == 0
    assert spec.database_vcpu is None
    assert spec.nat_gateway_count == 0
    assert not spec.load_balancer
    assert spec.lambda_invocations_per_month > 0
    assert spec.dynamodb_read_units_per_month > 0


def test_recommend_returns_serverless_options_for_a_serverless_workload():
    options = recommend(_serverless_req(), "aws")
    assert len(options) == 3
    for o in options:
        labels = {i.label for i in o.estimate.items}
        assert any(l.startswith("Lambda") for l in labels), o.label
        assert any(l.startswith("DynamoDB") for l in labels), o.label
        # No server lines at all.
        assert not any(l.startswith("Compute") for l in labels), o.label
        assert not any(l.startswith("Database") for l in labels), o.label
        assert not any(l.startswith("NAT") for l in labels), o.label


def test_the_three_serverless_tiers_actually_differ():
    options = recommend(_serverless_req(), "aws")
    totals = [float(o.monthly) for o in options]
    assert totals[0] < totals[1] < totals[2], totals


def test_a_steady_workload_is_still_a_server_architecture():
    """The signal is conservative: without it, nothing changes. A steady app
    still gets EC2/RDS, never Lambda."""
    options = recommend(_serverless_req(serverless=False), "aws")
    for o in options:
        labels = {i.label for i in o.estimate.items}
        assert not any(l.startswith("Lambda") for l in labels)
        assert any(l.startswith("Compute") for l in labels)


# ── diagram ──────────────────────────────────────────────────────────────


def _draw(option):
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
    return arch


def test_serverless_diagram_draws_the_managed_services_and_no_vpc():
    arch = _draw(recommend(_serverless_req(), "aws")[0])
    names = {s.name for s in arch.services}
    assert "AWS Lambda" in names
    assert "Amazon API Gateway" in names
    assert "Amazon DynamoDB" in names
    # The absence of a VPC is the point: no subnet to run in, no NAT to pay.
    assert not arch.boundaries, [b.kind for b in arch.boundaries]
    # And no server box manufactured from an unmapped line.
    assert "Amazon EC2 Auto Scaling" not in names


def test_server_diagram_still_has_its_vpc():
    """Regression: the serverless VPC guard must not strip the VPC from a
    real server architecture that genuinely runs inside one."""
    req = Requirement(
        goal="billing", workload_type="web", traffic_scale="medium",
        daily_transactions=8000, region="india", high_availability=True,
        storage_gb=100.0, egress_gb=50.0,
    )
    arch = _draw(recommend(req, "aws")[1])
    kinds = {b.kind for b in arch.boundaries}
    assert "vpc" in kinds
