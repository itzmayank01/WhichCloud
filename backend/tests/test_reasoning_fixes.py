"""Four narrow fixes on top of the reasoning layer, each with its own prompt.

Not the Pune contract (test_acceptance_pune.py) -- these check behaviour the
Pune prompt cannot distinguish because it triggers every signal at once.
"""

from __future__ import annotations

from whichcloud.constraints import extract
from whichcloud.plan import build

# ── country_lock: naming a place is not the same as locking to it ──


def test_naming_a_city_alone_does_not_lock_the_region():
    """Pune with no residency phrase and no regulator: the country is known,
    but nothing said data may never leave it."""
    c = extract(
        "We run a small clinic booking app in Pune for 20 staff, about "
        "50 bookings a day, steady traffic. Budget $150 a month."
    )
    assert c.country == "IN"
    assert c.country_lock is False


def test_a_residency_phrase_locks_the_region():
    c = extract(
        "Our team is based in Singapore and data must stay in Singapore. "
        "200 users, 2000 requests a day."
    )
    assert c.country == "SG"
    assert c.country_lock is True


def test_a_named_regulator_locks_the_region_even_without_the_word_residency():
    c = extract(
        "A Mumbai-based lending app regulated by RBI, 5000 users, 20000 "
        "transactions a day, budget $2000."
    )
    assert c.country == "IN"
    assert c.country_lock is True


def test_region_deny_guardrail_only_appears_when_the_country_is_locked():
    plan = build(
        "A steady internal reporting tool for our Pune office, 30 staff, "
        "300 report views a day, budget $200 a month."
    )
    for tier in plan.tiers:
        assert tier.spec.region_deny_guardrail is False


# ── Graviton/ARM is the default, not a function of the sector label ──


def test_compute_defaults_to_arm_even_outside_named_sectors():
    """'other' used to fall back to x86 for no reason tied to the text."""
    plan = build(
        "An internal tool with no particular category, 10 users, 500 "
        "requests a day, budget $100 a month."
    )
    for tier in plan.tiers:
        assert tier.spec.arch == "arm64"


def test_compute_falls_back_to_x86_only_when_the_text_says_so():
    plan = build(
        "A legacy Windows Server app requiring .NET Framework, 10 users, "
        "500 requests a day, budget $300 a month."
    )
    for tier in plan.tiers:
        assert tier.spec.arch is None


# ── committed-use savings: advisory, and never inside the total ──


def test_committed_use_is_a_separate_note_not_part_of_the_total():
    plan = build(
        "A steady internal tool, 40 staff, 800 requests a day, budget "
        "$250 a month."
    )
    for tier in plan.tiers:
        assert tier.committed_use_note
        assert "not included in the total" in tier.committed_use_note
        assert "compute" in tier.committed_use_note


# ── VPC endpoints carry the reason they exist ──


def test_vpc_endpoint_line_explains_the_nat_saving():
    """Gateway endpoints (S3 + DynamoDB) are free and always added, and say
    so. Interface endpoints are a real per-AZ-per-hour cost and are only
    added when they are cheaper than the NAT charge they divert -- not
    asserted here, since this workload's traffic does not justify them."""
    plan = build(
        "A steady internal tool, 40 staff, 800 requests a day, budget "
        "$250 a month."
    )
    labels = " ".join(i.label for i in plan.tiers[0].estimate.items)
    assert "keeps that traffic off NAT" in labels
