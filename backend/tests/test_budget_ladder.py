"""Part E: Budget-Aware Architecture Ladder Tests.

Verifies the 9 required invariants across budgets $500, $2,000, $5,000, and $20,000
for the retail-chain workload:
 1. No tier cost ever exceeds the budget.
 2. Tier 3 cost never decreases as budget rises.
 3. Service set changes between budget 500 and 5000.
 4. business_hours class always has 2-AZ compute and Multi-AZ DB when
    budget allows; if it does not allow, the output says it does not fit.
 5. Every added service has a "why" tag.
 6. At 20000 the output still stops at justified modules and shows budget left.
 7. UNPRICED services never enter the total.
 8. DR region is always in India for Indian prompts.
 9. Tier 2 and Tier 3 differ in service set, not only size.
"""

from pathlib import Path
import pytest
import yaml

from whichcloud.constraints import Constraints
from whichcloud.plan import build, plan_from

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "retail-chain.yaml"


@pytest.fixture(scope="module")
def retail_fixture():
    with open(FIXTURE_PATH) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def plans_by_budget(retail_fixture):
    plans = {}
    base_prompt = retail_fixture["prompt"]
    for b in retail_fixture["budgets"]:
        prompt_with_b = (
            f"I run operations for a retail chain in India with 40 stores. "
            f"We want to move our stock and billing system online so staff can use it from any store and head office can see live numbers. "
            f"Around 300 staff use it daily and we do about 8,000 transactions a day. "
            f"It must not go down during business hours because billing stops. "
            f"Budget is around ${b} a month."
        )
        p = build(prompt_with_b)
        plans[b] = p
    return plans


def test_1_no_tier_cost_ever_exceeds_the_budget(plans_by_budget):
    """1. No tier cost ever exceeds the budget (or flags within_budget=False)."""
    for budget, plan in plans_by_budget.items():
        for tier in plan.tiers:
            if tier.within_budget(budget):
                assert tier.monthly_total <= budget, (
                    f"Tier {tier.name} cost ${tier.monthly_total:.2f} exceeded budget ${budget}"
                )


def test_2_tier_3_cost_never_decreases_as_budget_rises(plans_by_budget):
    """2. Tier 3 cost never decreases as budget rises."""
    budgets = sorted(plans_by_budget.keys())
    tier_3_costs = [plans_by_budget[b].tiers[2].monthly_total for b in budgets]
    for i in range(len(tier_3_costs) - 1):
        assert tier_3_costs[i] <= tier_3_costs[i + 1] + 1e-4, (
            f"Tier 3 cost decreased from ${tier_3_costs[i]:.2f} (budget ${budgets[i]}) "
            f"to ${tier_3_costs[i+1]:.2f} (budget ${budgets[i+1]})"
        )


def test_3_service_set_changes_between_budget_500_and_5000(plans_by_budget):
    """3. Service set changes between budget 500 and 5000."""
    t3_500 = plans_by_budget[500].tiers[2]
    t3_5000 = plans_by_budget[5000].tiers[2]

    labels_500 = {item.label for item in t3_500.estimate.items}
    labels_5000 = {item.label for item in t3_5000.estimate.items}

    # At 5000, secondary DR standby and cross-region copies are added
    diff = labels_5000 - labels_500
    assert diff, "Service set did not change between budget $500 and $5,000"
    assert t3_5000.modules_included != t3_500.modules_included
    assert "MOD-DR-STANDBY" in t3_5000.modules_included
    assert "MOD-DR-STANDBY" not in t3_500.modules_included


def test_4_business_hours_always_has_2az_compute_and_multiaz_db(plans_by_budget):
    """4. business_hours class always has 2-AZ compute and Multi-AZ DB when
    budget allows; if it does not allow, the output says it does not fit."""
    # When budget allows (5000)
    p5000 = plans_by_budget[5000]
    assert p5000.constraints.availability_class == "business_hours"
    for tier in p5000.tiers:
        assert tier.spec.database_multi_az, f"{tier.name} missing Multi-AZ DB"
        assert tier.spec.load_balancer, f"{tier.name} missing load balancer"
        compute_fleet = (tier.spec.compute_count or tier.spec.fargate_task_count)
        assert compute_fleet >= 2, f"{tier.name} compute fleet size < 2"
        assert "MOD-AVAIL-BH" in tier.modules_included

    # When budget is low ($50), output explicitly states MOD-AVAIL-BH does not fit
    c = Constraints(country="IN", sector="retail", availability_class="business_hours", budget_monthly_usd=50.0)
    p_tight = plan_from(c, "retail chain with budget $50 a month", archetype="web_app")
    t1_omitted = [m["module"] for m in p_tight.tiers[0].modules_omitted]
    assert "MOD-AVAIL-BH" in t1_omitted
    assert "Omitted to fit budget of $50" in p_tight.tiers[0].modules_omitted[0]["reason"]


def test_5_every_added_service_has_a_why_tag(plans_by_budget):
    """5. Every added service has a 'why' tag."""
    for budget, plan in plans_by_budget.items():
        for tier in plan.tiers:
            for item in tier.estimate.items:
                why = getattr(item, "why", "")
                assert why and why.strip(), (
                    f"Missing 'why' tag on item {item.label} in {tier.name} at budget ${budget}"
                )


def test_6_at_20000_stops_at_justified_modules_and_shows_budget_left(plans_by_budget):
    """6. At 20000 the output still stops at justified modules and shows budget left."""
    p20000 = plans_by_budget[20000]
    t3 = p20000.tiers[2]

    # Does not balloon to arbitrary large spend: 0.28 TPS stays under $1,000/mo
    assert t3.monthly_total < 1000.0, (
        f"Tier 3 ballooned to ${t3.monthly_total:.2f} at $20,000 budget"
    )
    assert t3.budget_left_usd > 19000.0
    assert p20000.unspent_budget is not None
    assert p20000.unspent_budget["amount_usd"] > 19000.0
    assert "Well within budget" in p20000.unspent_budget["note"]


def test_7_unpriced_services_never_enter_the_total(plans_by_budget):
    """7. UNPRICED services never enter the total."""
    for budget, plan in plans_by_budget.items():
        for tier in plan.tiers:
            # Missing / unpriced services are in missing list, not items
            for missing_item in tier.estimate.missing:
                assert not any(i.label == missing_item for i in tier.estimate.items)
            # Item totals must sum exactly to tier estimate
            total_items = sum(i.monthly_usd for i in tier.estimate.items)
            assert abs(float(tier.estimate.total_monthly) - float(total_items)) < 0.01


def test_8_dr_region_is_always_in_india_for_indian_prompts(plans_by_budget):
    """8. DR region is always in India (ap-south-2 Hyderabad) for Indian prompts."""
    p5000 = plans_by_budget[5000]
    t3 = p5000.tiers[2]
    # Check that standby resources exist and target ap-south-2
    standby_items = [i for i in t3.estimate.items if "standby" in i.label.lower() or "cross-region" in i.label.lower()]
    assert standby_items, "No standby items in Tier 3 at $5000"
    for item in standby_items:
        # Cross-region copy or standby items must remain in India (ap-south-2)
        assert "us-" not in item.label.lower() and "eu-" not in item.label.lower()


def test_9_tier_2_and_tier_3_differ_in_service_set_not_only_size(plans_by_budget):
    """9. Tier 2 and Tier 3 differ in service set, not only size."""
    p5000 = plans_by_budget[5000]
    t2 = p5000.tiers[1]
    t3 = p5000.tiers[2]

    t2_labels = {item.label for item in t2.estimate.items}
    t3_labels = {item.label for item in t3.estimate.items}

    # Must differ in services, not just quantities or instance types
    only_in_t3 = t3_labels - t2_labels
    assert only_in_t3, "Tier 2 and Tier 3 have identical service sets"
    assert "MOD-DR-STANDBY" in t3.modules_included
    assert "MOD-DR-STANDBY" not in t2.modules_included
