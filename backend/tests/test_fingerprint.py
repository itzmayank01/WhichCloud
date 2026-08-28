"""Architecture fingerprint assertions.

The full DIVERGENCE / TIER-SPREAD matrix across every fixture lives in
scripts/fingerprint_matrix.py -- at baseline it FAILS on the template bug
(media-streaming shares web-ecommerce's fingerprint; most fixtures' tiers
differ by < 3 services), which is the proof the bug is real and the target
Step 3 drives to zero, one archetype per commit.

These tests lock in the two properties that must hold NOW: determinism
(stability), and that the one archetype already rebuilt (event_driven) passes
both divergence-from-web and tier spread -- the pattern every other archetype
must reach before its commit lands.
"""

from __future__ import annotations

import pytest

from whichcloud.engine import recommend
from whichcloud.fingerprint import fingerprint, tier_spread
from whichcloud.pricing.store import stats
from whichcloud.requirements import Requirement

pytestmark = pytest.mark.skipif(
    sum(r["n"] for r in stats()) == 0, reason="needs an ingested price catalog"
)


def _web(**over) -> Requirement:
    base = dict(
        goal="online store", workload_type="web", traffic_scale="high",
        daily_transactions=50_000, region="india", storage_gb=200, egress_gb=400,
    )
    base.update(over)
    return Requirement(**base)


def _iot(**over) -> Requirement:
    base = dict(
        goal="IoT telemetry", workload_type="mixed", traffic_scale="high",
        interruptible=True, event_driven=True, telemetry=True, needs_analytics=True,
        daily_transactions=5_000_000, region="india", storage_gb=2_000, egress_gb=500,
        ingress_shape="streams", processing_mode="near-real-time",
        data_shape="time-series", egress_shape="dashboards",
    )
    base.update(over)
    return Requirement(**base)


@pytest.mark.slow
def test_stability_same_requirement_same_fingerprint_100x():
    """STABILITY: the engine is deterministic, so a fixed requirement yields
    a byte-identical fingerprint on every one of 100 runs.

    Opt-in (`pytest -m slow`): 100 real pricings cost minutes. Determinism is
    a property of the engine's logic, not the catalog, so the default suite
    skips this without losing coverage of the logic it exercises."""
    req = Requirement(
        goal="small internal tool", workload_type="web", traffic_scale="low",
        daily_transactions=1_000, region="india", storage_gb=20, egress_gb=10,
    )
    first = [fingerprint(o) for o in recommend(req, "aws")]
    for _ in range(99):
        again = [fingerprint(o) for o in recommend(req, "aws")]
        assert again == first


def test_event_driven_diverges_from_web():
    """DIVERGENCE (the rebuilt archetype): an event-driven telemetry pipeline
    and a relational web app must not share a tier-1 architecture."""
    iot = fingerprint(recommend(_iot(), "aws")[0])
    web = fingerprint(recommend(_web(), "aws")[0])
    assert iot != web
    # And specifically: telemetry is NOT in a relational store.
    assert "database" not in iot
    assert "timestream" in iot


def test_event_driven_tier_spread_at_least_three():
    """TIER SPREAD (the rebuilt archetype): its consecutive tiers differ by
    at least three services, not by size."""
    spreads = tier_spread(recommend(_iot(), "aws"))
    assert all(s >= 3 for s in spreads), spreads
