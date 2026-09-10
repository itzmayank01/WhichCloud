"""Fingerprint properties on the PLAN path.

tests/test_fingerprint.py covers the other engine -- the one that takes a
Requirement. This covers `plan.plan_from()`, which is where the archetype
lives and therefore where the one-shape bug lived.

The baseline this work started from, measured by
scripts/plan_fingerprint_matrix.py before anything changed:

    7 fixtures priced, 6 withheld
    TIER SPREAD  7 of 7 FAILED -- every one [n, 0], tier_2 and tier_3
                 fingerprinting identically
    DIVERGENCE   0 collisions, but VACUOUSLY: 6 of the 7 priced fixtures
                 shared one profile, and the six genuinely different
                 archetypes were all withheld, so the rule had almost
                 nothing to test

Both numbers are the proof the bug was real: six of seven shapes produced
no architecture at all, and the seventh produced two identical ones.
"""

from __future__ import annotations

import pytest

from whichcloud.constraints import Constraints
from whichcloud.fingerprint import (
    MIN_TIER_SPREAD, fingerprint, plan_profile, tier_spread,
)
from whichcloud.plan import plan_from
from whichcloud.pricing.store import stats

pytestmark = pytest.mark.skipif(
    sum(r["n"] for r in stats()) == 0, reason="needs an ingested price catalog"
)


def _web(**over) -> Constraints:
    base = dict(
        country="IN", sector="ecommerce", availability="high",
        durability="high", users=5_000, requests_per_day=200_000,
        peak_shape="evening", budget_monthly_usd=2_000.0,
        storage_gb=500.0, egress_gb=800.0, public_facing=True,
    )
    base.update(over)
    return Constraints(**base)


def _plan(**over):
    return plan_from(_web(**over), "an online store", archetype="web_app")


# ── TIER SPREAD ──────────────────────────────────────────────────────


def test_consecutive_tiers_differ_by_service_not_size():
    """The headline fix. Tier 3 used to be tier 2 provisioned for 3x the
    stated peak -- same services, same shape, +93% on the bill on
    ecommerce-scale ($1,787.54 -> $3,444.72). Capacity is not a tier."""
    built = _plan()
    spreads = tier_spread(built.tiers)
    for i, spread in enumerate(spreads):
        upper = built.tiers[i + 1]
        assert spread >= MIN_TIER_SPREAD or upper.no_further_improvement, (
            f"{built.tiers[i].name}->{upper.name} spread={spread}"
        )


def test_every_tier_is_sized_for_the_same_peak():
    """Capacity follows the requirement; the tier follows the design.
    Three tiers sized differently for the same stated peak is a size
    decision sold as an architecture."""
    built = _plan()
    counts = {
        t.name: (t.spec.compute_count or t.spec.fargate_task_count)
        for t in built.tiers
    }
    assert len(set(counts.values())) == 1, counts


def test_tier_three_buys_resilience_when_something_was_stated():
    """A workload that said its data cannot be lost, or that being down
    costs it, gets the resilience upgrades at tier 3."""
    built = _plan(durability="normal", availability="high")
    top, mid = built.tiers[2].spec, built.tiers[1].spec
    assert top.object_lock and not mid.object_lock
    assert top.backup_copy_gb and not mid.backup_copy_gb


def test_a_low_stakes_workload_is_not_padded_at_tier_three():
    """The escape hatch, in the direction that matters. A tool whose own
    description says nobody minds an hour of downtime has nothing worth
    selling it at tier 3, and inventing a difference would be padding --
    which the brief forbids as firmly as it forbids a silent thin tier."""
    built = plan_from(
        Constraints(
            country="IN", sector="internal_tools", availability="low",
            durability="normal", users=40, requests_per_day=800,
            budget_monthly_usd=100.0, storage_gb=20.0, egress_gb=5.0,
            public_facing=False,
        ),
        "a small internal tool", archetype="web_app",
    )
    top = built.tiers[2].spec
    assert not top.object_lock
    assert not top.backup_copy_gb
    # ...and it SAYS so rather than staying silent.
    assert built.tiers[2].no_further_improvement


# ── the fingerprint itself ───────────────────────────────────────────


def test_a_standby_region_is_visible_to_the_fingerprint():
    """Two of the seven baseline failures were hidden rather than absent:
    the warm standby WAS priced, but its line items folded onto the
    primary's service kinds, so a tier carrying a whole extra geography
    fingerprinted the same as one without it."""
    from types import SimpleNamespace

    from whichcloud.estimator import LineItem

    def item(label):
        return LineItem(label=label, sku="x", unit="hour", unit_price=1.0,
                        quantity=1.0, monthly_usd=1.0)

    one = SimpleNamespace(estimate=SimpleNamespace(items=[item("Database")]))
    two = SimpleNamespace(estimate=SimpleNamespace(items=[
        item("Database"), item("Database (standby — second region)"),
    ]))
    assert fingerprint(one) != fingerprint(two)
    assert any(k.endswith("@standby") for k in fingerprint(two))


def test_every_line_item_maps_to_a_real_service_kind():
    """The `compute` fallback in _kind_for is a trap that has been sprung
    repeatedly -- Secrets Manager once manufactured an EC2 box on a
    serverless diagram. Object Lock, the cross-region backup copy, the
    archive tier and the region-deny guardrail were all summing silently
    onto the compute node, which made the fingerprint blind to exactly
    the differences a tier is made of."""
    from whichcloud.topology import unmapped_labels

    built = _plan()
    for tier in built.tiers:
        unmapped = unmapped_labels(tier.estimate.items)
        assert not unmapped, f"{tier.name} has unmapped line items: {unmapped}"


# ── STABILITY ────────────────────────────────────────────────────────


def test_the_same_constraints_produce_the_same_fingerprint():
    """Cheap stability: the decision layer is pure over Constraints, so a
    handful of repeats catches any accidental dependence on ordering or
    clock. The 100-iteration form is in test_fingerprint.py under
    `-m slow`, where its minutes are opt-in."""
    first = [fingerprint(t) for t in _plan().tiers]
    for _ in range(4):
        assert [fingerprint(t) for t in _plan().tiers] == first


def test_profile_separates_the_axes_that_change_the_architecture():
    """Divergence is only as strong as the profile behind it: every extra
    element makes a collision easier to explain away."""
    web = plan_from(_web(), "a store", archetype="web_app")
    assert plan_profile(web)[0] == "web_app"
    async_web = plan_from(
        _web(async_processing=True), "a store", archetype="web_app",
    )
    assert plan_profile(web) != plan_profile(async_web)
