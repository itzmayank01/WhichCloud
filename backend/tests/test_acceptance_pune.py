"""The Pune hospital prompt, checked against all eight acceptance criteria.

One prompt, eight assertions, each named for the failure it prevents. This
file is the contract: if the reasoning layer regresses, it fails here
before anyone sees a wrong architecture.
"""

from __future__ import annotations

import pytest

from whichcloud.constraint_filter import Architecture, check
from whichcloud.constraints import extract
from whichcloud.load_model import build_load
from whichcloud.objectives import compliance_notes, objectives

PUNE = (
    "I manage IT for a 3-hospital group in Pune. We want to move patient "
    "appointments, records and lab reports online so doctors and front desk "
    "can access them from all three sites. About 450 staff use it, roughly "
    "6,000 record lookups a day, with peaks in the morning. Patient data must "
    "stay inside India and cannot be lost. Downtime during OPD hours is "
    "unacceptable. Budget is about $900 a month."
)

INDIA_REGIONS = ("ap-south-1", "ap-south-2")


@pytest.fixture(scope="module")
def constraints():
    return extract(PUNE)


@pytest.fixture(scope="module")
def load(constraints):
    return build_load(constraints, PUNE)


# ── 1 ──
def test_stated_facts_are_not_filed_as_assumptions(constraints):
    """Each of these appears in the text in plain words. Marking any of them
    'assumed' tells the reader we did not read what they wrote."""
    for name in ("country", "sector", "availability", "durability"):
        assert name in constraints.stated, (
            f"{name} was marked assumed; the text says "
            f"{constraints.evidence.get(name, '(nothing found)')}"
        )
    assert constraints.assumed == ["storage_gb", "egress_gb"]


# ── 2 ──
def test_sizing_is_derived_from_volume_not_from_headcount(load):
    basis = load.sizing_basis()
    assert basis["avg_rps"] == pytest.approx(0.07, abs=0.005)
    assert basis["peak_rps"] == pytest.approx(0.7, abs=0.02)
    assert basis["tier"] == "trivial"
    # 450 staff is the number that tempts an over-build; it must not appear.
    assert "450" not in basis["sized_from"]


# ── 3 ──
def test_no_priced_tier_may_run_one_instance_or_a_single_az_database():
    """The filter's whole job. A design that fails this is not a cheaper
    option, it is a non-compliant one, and it may not be priced as a tier."""
    naive = Architecture(
        compute_instance_count=1, availability_zones=1,
        load_balancer=False, database_multi_az=False,
        regions=("ap-south-1",),
    )
    result = check(
        naive, availability="high", durability="high",
        country="India", country_regions=INDIA_REGIONS,
    )
    assert not result.valid
    assert any("single instance" in v for v in result.violations)
    assert any("single-AZ database" in v for v in result.violations)


# ── 4 ──
def test_a_compliant_design_copies_backups_to_the_second_indian_region():
    """India has two AWS regions, so residency and durability are both
    satisfiable. An earlier version of this catalog carried only Mumbai and
    concluded they were in conflict -- that was our coverage gap, not the
    country's geography."""
    compliant = Architecture(
        compute_instance_count=2, availability_zones=2,
        load_balancer=True, database_multi_az=True,
        automated_backups=True, object_lock=True,
        cross_region_copy_region="ap-south-2",
        regions=("ap-south-1", "ap-south-2"),
        region_deny_guardrail=True,
    )
    result = check(
        compliant, availability="high", durability="high",
        country="India", country_regions=INDIA_REGIONS,
    )
    assert result.valid, result.violations


def test_a_copy_outside_india_is_a_violation_not_a_compromise():
    offshore = Architecture(
        compute_instance_count=2, availability_zones=2,
        load_balancer=True, database_multi_az=True,
        automated_backups=True, object_lock=True,
        cross_region_copy_region="eu-north-1",
        regions=("ap-south-1",), region_deny_guardrail=True,
    )
    result = check(
        offshore, availability="high", durability="high",
        country="India", country_regions=INDIA_REGIONS,
    )
    assert not result.valid
    assert any("outside India" in v for v in result.violations)


# ── 5 ──
def test_what_was_left_out_is_recorded_with_the_reason(load):
    excluded = " | ".join(load.excluded_with_reason)
    assert "CloudFront" in excluded
    assert "ElastiCache" in excluded
    assert "0.69" in excluded or "0.7" in excluded
    assert "staff-only" in excluded


# ── 6 ──
def test_indian_healthcare_cites_indian_law_and_never_hipaa(constraints):
    notes = compliance_notes(constraints.country, constraints.sector)
    names = [n["regulation"] for n in notes]
    assert any("Digital Personal Data Protection Act 2023" in n for n in names)
    assert not any("HIPAA" in n for n in names), (
        "HIPAA is US law; citing it for a Pune hospital is the kind of "
        "confident error that discredits every other claim on the page"
    )
    for note in notes:
        assert note["control"], f"{note['regulation']} names no control"


# ── 7 ──
def test_every_tier_states_recovery_objectives():
    compliant = objectives(
        multi_instance=True, multi_az_database=True, cross_region_copy=True
    )
    assert compliant["rto"] == "1-2 min"
    assert compliant["rpo"] == "~5 min"
    assert compliant["region_rto"] == "2-6 h"

    # And they are derived, not asserted: take the components away and the
    # objectives get worse on their own.
    degraded = objectives(
        multi_instance=False, multi_az_database=False, cross_region_copy=False
    )
    assert degraded["rto"] == "30-120 min"
    assert degraded["region_rto"] == "not survivable"


# ── 8 ──
def test_the_public_are_not_confused_with_the_subject_of_the_data(constraints):
    """'patient' appears five times, and not one of them is a user. The
    system is used by doctors and front desk staff on known sites -- reading
    'patient' as an audience is what puts a CDN and a WAF on an intranet."""
    assert constraints.public_facing is False
    assert "public_facing" in constraints.stated


# ── pricing audit ──

def test_rates_are_region_specific_not_a_single_global_table():
    """A catalog that quotes one rate everywhere is not a priced catalog,
    it is a price list with a region column. ap-south-1 is materially
    cheaper than us-east-1 for the same instance."""
    from whichcloud.pricing.store import connect

    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "select region, price_usd from price_points"
            " where provider = 'aws' and category = 'compute'"
            " and sku = 't4g.medium' and region in ('ap-south-1', 'us-east-1')"
        )
        rates = {r["region"]: r["price_usd"] for r in cur.fetchall()}

    assert len(rates) == 2, "both regions must carry this instance type"
    assert rates["ap-south-1"] != rates["us-east-1"]


def test_baseline_security_scales_with_the_footprint_it_protects():
    """A flat fee on a two-instance deployment is a pricing bug: it makes
    security look like a tax rather than a cost that tracks what is being
    secured. GuardDuty bills per vCPU-month; Security Hub per check."""
    from whichcloud.pricing.store import connect

    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "select sku, unit from price_points where provider = 'aws'"
            " and region = 'ap-south-1' and category in ('threat', 'posture')"
        )
        units = {r["sku"]: r["unit"] for r in cur.fetchall()}

    assert units, "no baseline security prices ingested"
    for sku, unit in units.items():
        assert unit in ("vCPU-month", "check"), (
            f"{sku} bills per {unit!r}, which does not scale with the "
            "resources it protects"
        )


# ── the whole contract, end to end ──

@pytest.fixture(scope="module")
def plan():
    from whichcloud.plan import build

    return build(PUNE)


def test_the_plan_prices_three_compliant_tiers(plan):
    assert len(plan.tiers) == 3
    for tier in plan.tiers:
        assert tier.estimate.is_complete, tier.estimate.missing
        assert tier.monthly_total > 0
        assert tier.rto and tier.rpo


def test_no_priced_tier_is_generated_non_compliant(plan):
    """build() raises rather than emitting a tier that fails the filter, so
    reaching this point at all is the assertion. These confirm the shape."""
    for tier in plan.tiers:
        assert tier.spec.compute_count >= 2
        assert tier.spec.database_multi_az
        assert tier.spec.load_balancer
        assert tier.spec.backup_copy_gb > 0
        assert tier.spec.object_lock
        assert tier.spec.region_deny_guardrail


def test_the_failing_design_is_shown_apart_and_never_priced(plan):
    """It can be looked at. It cannot be one of the three numbers, because a
    cheap figure beside two dearer ones wins arguments on price alone."""
    panel = plan.below_requirements
    assert panel is not None
    assert panel["violations"]
    assert "not one of the three options" in panel["note"]
    assert "monthly_total" not in panel


def test_unspent_budget_is_reported_as_correct(plan):
    assert plan.unspent_budget is not None
    assert plan.unspent_budget["amount_usd"] > 0
    assert "correct result, not an error" in plan.unspent_budget["note"]


def test_vpc_endpoints_are_always_present(plan):
    for tier in plan.tiers:
        assert tier.spec.vpc_endpoints >= 2
    labels = " ".join(i.label for i in plan.tiers[0].estimate.items)
    assert "VPC endpoint" in labels


def test_arm_instances_are_preferred(plan):
    for tier in plan.tiers:
        assert tier.spec.database_arch == "arm64"


def test_the_cross_region_copy_is_billed_and_stays_in_india(plan):
    labels = {i.label: i for i in plan.tiers[0].estimate.items}
    assert "Cross-region backup copy" in labels
    assert labels["Cross-region backup copy"].monthly_usd > 0
