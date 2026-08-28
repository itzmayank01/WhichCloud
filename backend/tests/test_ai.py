"""The managed-AI architecture shape, end to end.

An AI-powered app used to come out as a generic EC2 cluster with no AI
services in it -- the prices were internally right but answered the wrong
question. These lock in that an AI workload now gets the managed AI services
it actually described (Rekognition for images, Comprehend for text), priced
per call, on a serverless backend, with no phantom servers.

    .venv/bin/pytest tests/test_ai.py -q
"""

from __future__ import annotations

import pytest

from whichcloud.architecture.costed import PricedNode, architecture_from
from whichcloud.engine import ai_spec, recommend
from whichcloud.estimator import ArchitectureSpec, estimate
from whichcloud.pricing.store import stats
from whichcloud.requirements import Requirement
from whichcloud import topology as topo

pytestmark = pytest.mark.skipif(
    sum(r["n"] for r in stats()) == 0, reason="needs an ingested price catalog"
)


def _ai_req(**over) -> Requirement:
    base = dict(
        goal="an AI image + sentiment platform",
        workload_type="api",
        traffic_scale="high",
        ai=True,
        ai_vision=True,
        ai_language=True,
        daily_transactions=500_000,
        region="india",
        storage_gb=200.0,
        egress_gb=100.0,
    )
    base.update(over)
    return Requirement(**base)


# ── pricing ──────────────────────────────────────────────────────────────


def test_rekognition_and_comprehend_meters_price():
    spec = ArchitectureSpec(
        name="ai", region="india", compute_count=0,
        rekognition_images_per_month=15_000_000,
        comprehend_units_per_month=45_000_000,
    )
    est = estimate(spec, "aws")
    labels = {i.label for i in est.items}
    assert "Rekognition images" in labels
    assert "Comprehend sentiment" in labels
    assert not est.missing
    assert est.total_monthly > 0


def test_rekognition_uses_graduated_tiers():
    """15M images is not billed at the entry rate: the volume bands must
    lower the effective price below the first tier."""
    spec = ArchitectureSpec(
        name="ai", region="india", compute_count=0,
        rekognition_images_per_month=15_000_000,
    )
    est = estimate(spec, "aws")
    line = next(i for i in est.items if i.label == "Rekognition images")
    # Entry rate is $0.00125/image; the blended rate across 15M must be lower.
    assert float(line.unit_price) < 0.00125


# ── engine ───────────────────────────────────────────────────────────────


def test_ai_spec_uses_managed_ai_not_servers():
    spec = ai_spec(_ai_req(), "Cheapest")
    assert spec.compute_count == 0
    assert spec.database_vcpu is None
    assert spec.rekognition_images_per_month > 0
    assert spec.comprehend_units_per_month > 0


def test_only_the_capabilities_named_appear():
    vision_only = ai_spec(_ai_req(ai_language=False), "Cheapest")
    assert vision_only.rekognition_images_per_month > 0
    assert vision_only.comprehend_units_per_month == 0

    language_only = ai_spec(_ai_req(ai_vision=False), "Cheapest")
    assert language_only.comprehend_units_per_month > 0
    assert language_only.rekognition_images_per_month == 0


def test_recommend_returns_ai_options_with_no_servers():
    for o in recommend(_ai_req(), "aws"):
        labels = {i.label for i in o.estimate.items}
        assert any(l.startswith("Rekognition") for l in labels), o.label
        assert any(l.startswith("Comprehend") for l in labels), o.label
        assert not any(l.startswith("Compute") for l in labels), o.label
        assert not any(l.startswith("Database (") for l in labels), o.label
        assert not any(l.startswith("NAT") for l in labels), o.label


def test_a_non_ai_workload_gets_no_ai_services():
    """The signal is conservative: a plain app never acquires Rekognition."""
    req = Requirement(
        goal="a billing app", workload_type="web", traffic_scale="medium",
        daily_transactions=8000, region="india", storage_gb=100.0, egress_gb=50.0,
    )
    for o in recommend(req, "aws"):
        labels = {i.label for i in o.estimate.items}
        assert not any(l.startswith(("Rekognition", "Comprehend")) for l in labels)


# ── diagram ──────────────────────────────────────────────────────────────


def test_ai_diagram_draws_the_ai_services_and_no_vpc():
    o = recommend(_ai_req(), "aws")[0]
    g = topo.build(o.spec, o.estimate, o.applied)
    nodes = [
        PricedNode(
            kind=n.kind, label=n.label,
            monthly_usd=float(n.monthly_usd) if n.priced else None, sku=n.sku,
        )
        for n in g.nodes if n.kind != "client"
    ]
    arch, _ = architecture_from(
        nodes, o.spec.database_multi_az,
        o.spec.nat_gateway_count or None, o.spec.serves_requests,
    )
    names = {s.name for s in arch.services}
    assert "Amazon Rekognition" in names
    assert "Amazon Comprehend" in names
    assert not arch.boundaries, [b.kind for b in arch.boundaries]
    assert "Amazon EC2 Auto Scaling" not in names
