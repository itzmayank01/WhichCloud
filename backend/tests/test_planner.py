"""The planner's contract: what it may emit, and what it may never invent."""

from __future__ import annotations

import pytest

from whichcloud.planner import (
    CATALOG,
    SCALE_FLOOR_RPS,
    build_plan,
    derive_rates,
    in_country_regions,
    instances_for,
)
from whichcloud.pricing.store import connect


def _plan(**over):
    args = dict(
        rates=derive_rates(8000, "morning"),
        availability="high",
        durability="high",
        region_lock="India",
        sector="fintech",
        storage_gb=100,
        budget_monthly_usd=5000,
    )
    args.update(over)
    return build_plan(**args)


def test_every_component_the_planner_emits_can_actually_be_priced():
    """THE governing rule. A spec naming a component the catalog cannot
    price is worse than an incomplete one, because it looks finished.

    Checked against the database rather than the CATALOG constant -- the
    constant is a promise, and this is the thing that keeps the promise
    honest when an adapter silently stops returning rows.
    """
    with connect() as conn, conn.cursor() as cur:
        cur.execute("select distinct category from price_points where provider = 'aws'")
        priceable = {r["category"] for r in cur.fetchall()}

    for tier in _plan().tiers:
        for component in tier.components:
            assert component["category"] in priceable, (
                f"{tier.name} emits {component['category']!r}, which no AWS "
                "adapter returns a price for"
            )


def test_the_catalog_constant_does_not_drift_from_the_database():
    """CATALOG is what the planner is allowed to reach for. If it lists a
    category nothing prices, the guard above stops catching real mistakes.
    """
    with connect() as conn, conn.cursor() as cur:
        cur.execute("select distinct category from price_points where provider = 'aws'")
        priceable = {r["category"] for r in cur.fetchall()}

    invented = CATALOG - priceable
    assert not invented, f"CATALOG names unpriceable categories: {sorted(invented)}"


def test_a_component_outside_the_catalog_is_refused_rather_than_emitted():
    from whichcloud.planner import _c

    with pytest.raises(ValueError, match="not in the catalog"):
        _c("service-mesh")


# ── Step 2: size from the rate, not the budget ──

def test_peak_is_derived_from_volume_and_shape_not_from_users_or_budget():
    rates = derive_rates(8_640_000, "flat")
    assert rates.average_rps == pytest.approx(100.0)
    assert rates.peak_rps == pytest.approx(200.0)  # flat multiplier is 2

    morning = derive_rates(8_640_000, "morning")
    assert morning.peak_rps == pytest.approx(1000.0)


def test_small_traffic_gets_no_cache_however_large_the_budget():
    """The rule that stops a bakery being handed an enterprise stack.

    8,000 requests a day is under one request per second at peak. A cache,
    CDN, replica or queue there costs money and operational surface to
    change nothing, and a large budget is not a reason to add one.
    """
    rates = derive_rates(8000, "morning")
    assert rates.below_scale_floor

    for budget in (500, 5_000, 500_000):
        plan = build_plan(
            rates=rates, availability="low", durability="normal",
            region_lock="", sector="internal", storage_gb=50,
            budget_monthly_usd=budget,
        )
        for tier in plan.tiers:
            emitted = {c["category"] for c in tier.components}
            assert "cache" not in emitted
            assert "network" not in emitted  # CDN


def test_real_load_does_get_a_cache():
    rates = derive_rates(20_000_000, "morning")
    assert rates.peak_rps > SCALE_FLOOR_RPS

    plan = build_plan(
        rates=rates, availability="low", durability="normal", region_lock="",
        sector="ecommerce", storage_gb=500, budget_monthly_usd=None,
    )
    recommended = plan.tiers[1]
    assert "cache" in {c["category"] for c in recommended.components}
    assert "cache" in recommended.justifications


# ── Step 3: hard filters are filters, not preferences ──

def test_availability_high_forces_two_instances_a_balancer_and_multi_az():
    plan = _plan(availability="high", durability="normal", region_lock="")
    for tier in plan.tiers:
        emitted = [c for c in tier.components]
        compute = next(c for c in emitted if c["category"] == "compute")
        assert compute["quantity"] >= 2, f"{tier.name} runs a single instance"
        assert any(c["category"] == "loadbalancer" for c in emitted)

        databases = [c for c in emitted if c["category"] == "database"]
        assert len(databases) == 1, "the single-AZ database was left alongside"
        assert databases[0].get("size") == "multi-az"


def test_availability_high_puts_a_nat_gateway_in_each_zone():
    """A zone-redundant design whose only NAT sits in the failed zone has
    not survived the failure: the instances are up and cannot reach out."""
    ha = _plan(availability="high")
    low = _plan(availability="low")

    nat_ha = next(c for c in ha.tiers[0].components if c["category"] == "nat")
    nat_low = next(c for c in low.tiers[0].components if c["category"] == "nat")
    assert nat_ha["quantity"] == 2
    assert nat_low["quantity"] == 1


def test_durability_high_demands_object_lock_not_just_a_backup():
    plan = _plan(durability="high")
    emitted = plan.tiers[0].components
    assert any(c["category"] == "backup" for c in emitted)
    locks = [c for c in emitted if c.get("size") == "object-lock"]
    assert locks, "a backup an attacker can delete is not durability"


def test_a_region_lock_is_enforced_by_a_policy_not_by_intention():
    plan = _plan(region_lock="India")
    denies = [
        c for c in plan.tiers[0].components if c.get("size") == "region-deny-scp"
    ]
    assert denies, "nothing actually prevents deploying outside India"


# ── the conflict this planner exists to surface ──

def test_single_region_country_plus_high_durability_is_reported_unsatisfiable():
    """India has one AWS region, so a cross-region copy leaves the country.

    The planner must say so rather than silently shipping regulated data
    offshore to satisfy a checkbox.
    """
    assert in_country_regions("India") == ("ap-south-1",)

    plan = _plan(region_lock="India", durability="high")
    assert plan.unsatisfiable
    assert any("cannot both be satisfied" in u for u in plan.unsatisfiable)

    for tier in plan.tiers:
        emitted = {c["category"] for c in tier.components}
        assert "backup_copy" not in emitted, "data was sent offshore silently"


def test_rbi_localisation_is_named_only_for_indian_fintech():
    named = _plan(sector="fintech", region_lock="India").compliance_notes
    assert any("RBI" in n for n in named)

    # No regime invented where none is known.
    unknown = _plan(sector="other", region_lock="Singapore").compliance_notes
    assert any("would be inventing it" in n for n in unknown)


# ── Step 5 / the rules ──

def test_endpoints_are_always_present_to_keep_bytes_off_the_nat_gateway():
    for plan in (_plan(availability="low"), _plan(availability="high")):
        for tier in plan.tiers:
            assert any(c["category"] == "endpoint" for c in tier.components)


def test_unspent_budget_is_stated_as_correct_rather_than_an_opportunity():
    plan = _plan(budget_monthly_usd=500_000)
    assert "unspent" in plan.budget_note
    assert "not an opportunity" in plan.budget_note


def test_headroom_carries_three_times_the_traffic():
    plan = _plan()
    base = next(c for c in plan.tiers[1].components if c["category"] == "compute")
    head = next(c for c in plan.tiers[2].components if c["category"] == "compute")
    assert head["quantity"] >= base["quantity"]
    assert "compute" in plan.tiers[2].justifications


def test_every_tier_says_what_it_does_not_protect_against():
    for tier in _plan().tiers:
        assert tier.gives_up, f"{tier.name} claims to give nothing up"
        assert tier.rto and tier.rpo


def test_instances_never_fall_below_the_availability_floor():
    # Even at a rate that needs one instance, high availability needs two.
    assert instances_for(0.5, high_availability=True) == 2
    assert instances_for(0.5, high_availability=False) == 1
    # And sizing may exceed the floor, never undercut it.
    assert instances_for(400.0, high_availability=True) == 10
