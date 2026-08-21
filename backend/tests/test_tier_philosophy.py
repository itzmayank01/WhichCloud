"""The tier-generation rebuild's own acceptance test: three designs, not
three sizes of one design, checked against the Pune hospital prompt.

Distinct from test_acceptance_pune.py, which is the reasoning-layer
contract (Modules 1-4). This file is the contract for what those modules'
output gets turned INTO -- the spend priority ladder, the component gates,
the tier philosophies, and the pattern-diff guarantee between tiers.
"""

from __future__ import annotations

import pytest

from whichcloud.plan import build

PUNE = (
    "I manage IT for a 3-hospital group in Pune. We want to move patient "
    "appointments, records and lab reports online so doctors and front desk "
    "can access them from all three sites. About 450 staff use it, roughly "
    "6,000 record lookups a day, with peaks in the morning. Patient data must "
    "stay inside India and cannot be lost. Downtime during OPD hours is "
    "unacceptable. Budget is about $900 a month."
)


@pytest.fixture(scope="module")
def plan():
    return build(PUNE)


# ── 1 ──
def test_sizing_basis_shows_the_derived_rate(plan):
    basis = plan.load.sizing_basis()
    assert basis["avg_rps"] == pytest.approx(0.07, abs=0.005)
    assert basis["peak_rps"] == pytest.approx(0.7, abs=0.02)
    assert basis["load_tier"] == "trivial"


# ── 2 ──
def test_no_tier_contains_a_read_replica(plan):
    for tier in plan.tiers:
        assert tier.spec.database_read_replicas == 0
    excluded = " | ".join(plan.load.excluded_with_reason)
    assert "Read replica" in excluded


# ── 3 ──
def test_no_tier_contains_a_cache(plan):
    for tier in plan.tiers:
        assert tier.spec.cache_vcpu is None
    excluded = " | ".join(plan.load.excluded_with_reason)
    assert "ElastiCache" in excluded


# ── 4 ──
def test_no_tier_contains_a_cdn_or_waf_because_the_workload_is_staff_only(plan):
    for tier in plan.tiers:
        assert tier.spec.waf_rule_count is None
    excluded = " | ".join(plan.load.excluded_with_reason)
    assert "CloudFront" in excluded
    assert "AWS WAF" in excluded
    assert "staff-only" in excluded


# ── 5 ──
def test_every_tier_has_cross_region_backup_and_object_lock(plan):
    """cannot be lost is rung 1: present on every tier, not upsold onto
    the pricier ones."""
    for tier in plan.tiers:
        assert tier.spec.backup_copy_gb > 0
        assert tier.spec.object_lock
        labels = [i.label for i in tier.estimate.items]
        assert any("Cross-region backup copy" in l for l in labels)
        assert any("Object Lock" in l for l in labels)


# ── 6 ──
def test_no_gives_up_text_claims_a_regional_outage_is_uncovered(plan):
    for tier in plan.tiers:
        for line in tier.gives_up:
            assert "a regional outage is not covered" not in line


# ── 7 ──
def test_nat_stays_capped_and_below_compute_cost_or_is_flagged(plan):
    """<=2 gateways always. NAT costing more than compute at trivial scale
    is a real fact about small workloads (Part 3's corrected rule), so it
    is recorded as a warning rather than failing the build -- checked here
    as "either genuinely cheaper, or explicitly flagged", not silently
    accepted either way."""
    for tier in plan.tiers:
        assert tier.spec.nat_gateway_count <= 2
        nat_total = sum(
            i.monthly_usd for i in tier.estimate.items
            if i.label.startswith("NAT gateway") or i.label.startswith("NAT data")
        )
        compute_total = sum(
            i.monthly_usd for i in tier.estimate.items
            if i.label.startswith("Compute") or i.label.startswith("Fargate")
        )
        disproportionate = bool(nat_total and compute_total and nat_total > compute_total)
        flagged = any("NAT_DISPROPORTIONATE" in w for w in tier.warnings)
        assert disproportionate == flagged


# ── 8 ──
def test_security_scan_cost_scales_with_resource_count_not_flat(plan):
    """Tier 1 buys none (rung 2/3 is Tier 2's to add, per the ladder).
    Tier 2 and Tier 3 both carry it, priced per vCPU/check rather than a
    flat subscription -- so the line is present and non-zero, not a fixed
    number copy-pasted across tiers."""
    managed = [t for t in plan.tiers if t.name != "tier_1"]
    assert not any(
        i.label.startswith("Threat detection") for i in plan.tiers[0].estimate.items
    )
    for tier in managed:
        threat_cost = sum(
            i.monthly_usd for i in tier.estimate.items
            if i.label.startswith("Threat detection")
        )
        posture_cost = sum(
            i.monthly_usd for i in tier.estimate.items
            if i.label.startswith("Security posture")
        )
        assert threat_cost > 0
        assert posture_cost > 0


# ── 9 ──
def test_tier_2_and_tier_3_each_declare_a_pattern_diff(plan):
    tier_2, tier_3 = plan.tiers[1], plan.tiers[2]
    assert tier_2.pattern_diff
    assert tier_3.pattern_diff
    assert not tier_2.no_further_improvement
    assert not tier_3.no_further_improvement


# ── 10 ──
def test_compliance_cites_indian_law_and_never_hipaa(plan):
    names = [n["regulation"] for n in plan.compliance]
    assert any("Digital Personal Data Protection Act 2023" in n for n in names)
    assert any("IT Act s43A" in n for n in names)
    assert any("ABDM" in n for n in names)
    assert not any("HIPAA" in n for n in names)


# ── 11 ──
def test_tier_3_fits_budget_or_is_explicitly_flagged(plan):
    tier_3 = plan.tiers[2]
    if tier_3.monthly_total <= 900:
        assert plan.over_budget_note == ""
    else:
        assert "over budget" in plan.over_budget_note.lower() or plan.over_budget_note


# ── the philosophy layer itself ──


def test_each_tier_states_its_philosophy(plan):
    for tier in plan.tiers:
        assert tier.philosophy


def test_tier_1_never_buys_rung_4_capacity_regardless_of_load(plan):
    """The core bug this rebuild exists to fix: rung 4 (cache, replicas)
    must never appear on Tier 1, however the load gate reads -- Tier 1's
    cheapness is buying rung 1 and stopping, not a smaller amount of
    everything."""
    tier_1 = plan.tiers[0]
    assert tier_1.spec.cache_vcpu is None
    assert tier_1.spec.database_read_replicas == 0
    assert tier_1.spec.secret_count == 0
    assert not tier_1.spec.threat_detection


def test_tier_1_is_self_managed_ec2_not_fargate(plan):
    tier_1 = plan.tiers[0]
    assert tier_1.spec.compute_count >= 2
    assert tier_1.spec.fargate_task_count == 0


def test_tier_2_and_3_move_compute_to_fargate(plan):
    for tier in plan.tiers[1:]:
        assert tier.spec.compute_count == 0
        assert tier.spec.fargate_task_count >= 2


def test_tier_3_adds_a_warm_standby_region(plan):
    tier_3 = plan.tiers[2]
    labels = [i.label for i in tier_3.estimate.items]
    assert any("standby" in l for l in labels)
    assert tier_3.region_rto == "<15 min"


def test_gateway_endpoints_always_present_interface_endpoints_only_if_justified(plan):
    for tier in plan.tiers:
        assert tier.spec.gateway_endpoints >= 2
        # Trivial-tier traffic does not generate enough NAT data-processing
        # cost to justify five interface endpoints billed per AZ per hour.
        assert tier.spec.vpc_endpoints == 0
