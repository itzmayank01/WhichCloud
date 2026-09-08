"""The four billing dimensions that did not exist.

Four archetypes could not have been priced correctly even once their
service graphs existed, because the meters they bill on were not in the
catalog at all. The coverage map recorded these as structural gaps rather
than wiring gaps, and it was right:

    duty cycle    `compute_duty_cycle` was on the spec from the start and
                  nothing ever set it. PROBE-2's nightly ETL -- described
                  as idle during the day -- was billed 730 hours.
    event bus     EventBridge had no rate at any price, so an
                  event-driven shape costed its bus at zero, which reads
                  as "free" rather than "unknown".
    connections   No concurrent-connection or connection-minute meter
                  existed anywhere, so `realtime` could not be sized on
                  the only figure that describes it.
    accelerated   No GPU/inference selection path and no SageMaker
                  endpoint hours.

Every meter here was confirmed present in the ap-south-1 offer index
before anything was allowed to select it -- a rate nobody publishes is
one this engine must not quote.
"""

from __future__ import annotations

import pytest

from whichcloud.constraints import Constraints
from whichcloud.estimator import ArchitectureSpec, estimate
from whichcloud.plan import DUTY_CYCLED_ARCHETYPES, _duty_cycle_for
from whichcloud.pricing.store import stats

pytestmark = pytest.mark.skipif(
    sum(r["n"] for r in stats()) == 0, reason="needs an ingested price catalog"
)

HOURS_PER_MONTH = 730


# ── duty cycle ───────────────────────────────────────────────────────


def test_a_nightly_job_is_not_billed_for_the_whole_month():
    """PROBE-2 verbatim: two hours a night is ~61 hours a month, not 730."""
    duty = _duty_cycle_for("batch_etl", Constraints(active_hours_per_day=2))
    assert duty == pytest.approx(2 / 24)
    assert duty * HOURS_PER_MONTH == pytest.approx(60.8, abs=0.5)


def test_a_business_hours_WEB_app_is_still_billed_for_the_month():
    """The distinction that makes duty cycle safe to apply at all.

    "Busy during business hours" is a statement about TRAFFIC. A web app
    still needs its servers up at 3am to answer the one request that
    arrives, so billing it for nine hours would not be a cheaper answer
    -- it would be an answer to a workload nobody described. Under-billing
    is no more honest than over-billing.
    """
    assert _duty_cycle_for("web_app", Constraints(active_hours_per_day=9)) == 1.0
    assert _duty_cycle_for("realtime", Constraints(active_hours_per_day=9)) == 1.0


def test_only_archetypes_whose_compute_stops_are_duty_cycled():
    assert DUTY_CYCLED_ARCHETYPES == {"batch_etl", "ml_inference"}


def test_an_unstated_window_never_invents_a_saving():
    """24 hours is the default, so silence bills a full month."""
    assert _duty_cycle_for("batch_etl", Constraints()) == 1.0


def test_a_vanishingly_short_window_still_pays_for_a_cold_start():
    """A job claiming six minutes a night still pays scheduler overhead,
    an image pull and a cold start. Rounding towards zero would quote a
    number nobody can achieve."""
    assert _duty_cycle_for("batch_etl", Constraints(active_hours_per_day=0.05)) > 0


def test_the_duty_cycle_reaches_the_bill():
    """A duty cycle that is set and then not applied is indistinguishable
    from one that was never set, and only the line item reaches a user."""
    full = estimate(ArchitectureSpec(
        name="full", region="india", compute_count=2, compute_vcpu=2,
    ), "aws")
    part = estimate(ArchitectureSpec(
        name="part", region="india", compute_count=2, compute_vcpu=2,
        compute_duty_cycle=0.25,
    ), "aws")
    full_compute = next(i for i in full.items if i.label.startswith("Compute"))
    part_compute = next(i for i in part.items if i.label.startswith("Compute"))
    assert float(part_compute.quantity) == pytest.approx(
        float(full_compute.quantity) * 0.25
    )


# ── the event bus ────────────────────────────────────────────────────


def test_the_event_bus_has_a_real_rate():
    est = estimate(ArchitectureSpec(
        name="bus", region="india", compute_count=0,
        eventbridge_events_per_month=1_200_000,
    ), "aws")
    line = next(i for i in est.items if i.label == "Event bus")
    assert line.monthly_usd > 0
    assert "eventbridge" in line.sku
    assert "event bus" not in est.missing


# ── connections ──────────────────────────────────────────────────────


def test_connections_are_metered_on_time_held_not_on_requests():
    """A chat backend is sized by how many sockets are open and for how
    long. Two meters, because holding a connection and sending over it
    are two different charges."""
    est = estimate(ArchitectureSpec(
        name="ws", region="india", compute_count=0,
        ws_connection_minutes_per_month=48_000_000,
        ws_messages_per_month=5_000_000,
    ), "aws")
    labels = {i.label for i in est.items}
    assert "Connection minutes" in labels
    assert "Connection messages" in labels
    assert not est.missing


def test_connection_cost_scales_with_time_held():
    def cost(minutes):
        est = estimate(ArchitectureSpec(
            name="ws", region="india", compute_count=0,
            ws_connection_minutes_per_month=minutes,
        ), "aws")
        return float(next(i for i in est.items
                          if i.label == "Connection minutes").monthly_usd)

    assert cost(2_000_000) == pytest.approx(cost(1_000_000) * 2, rel=0.01)


# ── accelerated / managed inference ──────────────────────────────────


def test_a_model_endpoint_prices_from_the_catalog():
    est = estimate(ArchitectureSpec(
        name="ml", region="india", compute_count=0,
        inference_instance="ml.g5.xlarge", inference_instance_count=1,
        inference_hours_per_month=270,
    ), "aws")
    line = next(i for i in est.items if i.label.startswith("Model endpoint"))
    assert line.sku == "sagemaker:ml.g5.xlarge"
    assert line.monthly_usd > 0
    assert not est.missing


def test_inference_hours_carry_the_duty_cycle():
    """A model serving only in business hours costs less than one serving
    around the clock -- which is the whole reason the hours are a field."""
    def cost(hours):
        est = estimate(ArchitectureSpec(
            name="ml", region="india", compute_count=0,
            inference_instance="ml.g5.xlarge", inference_instance_count=1,
            inference_hours_per_month=hours,
        ), "aws")
        return float(next(i for i in est.items
                          if i.label.startswith("Model endpoint")).monthly_usd)

    assert cost(270) < cost(730)


def test_an_unknown_endpoint_type_is_missing_not_free():
    """A component with no catalog rate must make the estimate INCOMPLETE.
    Pricing it at zero is the failure this engine exists to avoid."""
    est = estimate(ArchitectureSpec(
        name="ml", region="india", compute_count=0,
        inference_instance="ml.does-not-exist", inference_instance_count=1,
        inference_hours_per_month=730,
    ), "aws")
    assert any("does-not-exist" in m for m in est.missing)
    assert not est.is_complete


# ── OpenSearch, which existed and was never called ───────────────────


def test_opensearch_prices_from_the_catalog():
    """213 search rows sat in the catalog, priced and tested, and plan.py
    never set search_node_count -- so a workload that explicitly asked for
    searchable history had a working pricing path the decision layer
    simply never reached."""
    est = estimate(ArchitectureSpec(
        name="s", region="india", compute_count=0,
        search_node_count=2, search_node_vcpu=2, search_node_memory_gb=8.0,
        search_storage_gb=200.0,
    ), "aws")
    labels = {i.label.split(" ×")[0] for i in est.items}
    assert "Search nodes" in labels
    assert "Search storage" in labels
    assert not est.missing


# ── every new meter is its own node ──────────────────────────────────


def test_the_new_meters_are_not_drawn_as_application_servers():
    from whichcloud.topology import _kind_for, unmapped_labels

    est = estimate(ArchitectureSpec(
        name="all", region="india", compute_count=0,
        eventbridge_events_per_month=1e6,
        ws_connection_minutes_per_month=1e6, ws_messages_per_month=1e6,
        inference_instance="ml.g5.xlarge", inference_instance_count=1,
        inference_hours_per_month=730,
    ), "aws")
    assert not unmapped_labels(est.items)
    kinds = {_kind_for(i) for i in est.items}
    assert {"eventbus", "connections", "inference"} <= kinds
    assert "compute" not in kinds
