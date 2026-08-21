"""Part 1: classify honestly, and refuse to price what is not covered.

The property under test is not "classification is accurate" -- a phrase
table will always have gaps. It is that gaps are SAFE: an unmatched or
ambiguous description withholds pricing instead of falling back to the
one shape the engine happens to build.
"""

from __future__ import annotations

import pytest

from whichcloud.archetype import (
    IMPLEMENTED_ARCHETYPES,
    UNKNOWN,
    classify,
    coverage,
    is_priceable,
)
from whichcloud.plan import build

PROBES = {
    "static_site": "Marketing site for our design studio. About 30,000 "
                   "visitors a month, mostly from India. It's just pages and "
                   "images, no login, no database. We want it cheap.",
    "batch_etl": "Every night we pull about 500 GB of sensor readings off our "
                 "factory machines and turn them into next-day reports. "
                 "Nobody uses it during the day.",
    "event_driven": "We receive payment webhooks from three providers, roughly "
                    "40,000 a day in unpredictable bursts. We cannot drop a "
                    "single one.",
    "ml_inference": "We have a trained model that scores loan applications. "
                    "About 50 predictions a second during business hours.",
    "realtime": "In-app chat for our 100,000 users. Messages must arrive "
                "instantly and history must be searchable.",
    "migration": "We run 40 virtual machines in our own server room, a mix of "
                 "Windows and Linux. We want to move them to the cloud as-is.",
}


# ── classification ──


@pytest.mark.parametrize("expected,prompt", list(PROBES.items()))
def test_each_probe_is_recognised_as_its_own_shape(expected, prompt):
    detected, evidence = classify(prompt)
    assert detected == expected, f"got {detected} ({evidence})"


def test_web_app_must_earn_its_classification_not_win_by_default():
    """The whole point. web_app is the only shape this engine can build,
    which is precisely why it must not be what an unrecognised
    description falls back to -- that is the silent default the coverage
    map found, just relocated."""
    detected, _ = classify(
        "We need something for the team. It should be reliable and not "
        "cost too much."
    )
    assert detected == UNKNOWN


def test_nothing_recognisable_is_unknown_not_web_app():
    detected, evidence = classify("Please help us with our infrastructure.")
    assert detected == UNKNOWN
    assert "no archetype phrase matched" in evidence


def test_a_tie_between_two_archetypes_is_unknown():
    """Ambiguity resolves to a refusal, not to whichever key sorted
    first -- a coin-flip between two shapes is not knowledge."""
    # One signal each from static_site and migration, nothing else.
    detected, evidence = classify(
        "It is just pages. We also want to move them to the cloud."
    )
    assert detected == UNKNOWN
    assert "ambiguous" in evidence


# ── the priced/unpriced boundary ──


def test_only_web_app_is_priceable_today():
    assert is_priceable("web_app")
    for name in PROBES:
        assert not is_priceable(name), f"{name} has no service graph yet"


def test_coverage_lists_every_archetype_with_its_status():
    entries = coverage()
    assert len(entries) == 7
    priced = {e["archetype"] for e in entries if e["status"] == "priced"}
    assert priced == set(IMPLEMENTED_ARCHETYPES)
    for e in entries:
        assert e["description"], f"{e['archetype']} has no description"


# ── INV-12, at the plan level ──


@pytest.mark.parametrize("prompt", list(PROBES.values()))
def test_no_priced_tier_is_emitted_for_an_unimplemented_shape(prompt):
    plan = build(prompt)
    assert plan.archetype == UNKNOWN
    assert plan.priced is False
    assert plan.tiers == []
    assert "withheld rather than guessed" in plan.withheld_reason


@pytest.mark.parametrize("prompt", list(PROBES.values()))
def test_a_refusal_still_returns_what_it_did_work_out(prompt):
    """Withholding a price must not mean discarding the analysis -- the
    extraction and sizing are real findings, and a reader who can see
    them can judge whether the refusal is reasonable."""
    plan = build(prompt)
    assert plan.constraints is not None
    assert plan.load.sizing_basis()["load_tier"]
    assert plan.detected_archetype and plan.detected_archetype != UNKNOWN
    assert len(plan.clarifying_questions) >= 3
    assert plan.covered_archetypes


def test_a_covered_workload_is_still_priced_normally():
    plan = build(
        "A patient records system for a clinic in Jaipur. Cannot lose data, "
        "cannot have downtime. Budget is $80 a month."
    )
    assert plan.archetype == "web_app"
    assert plan.priced is True
    assert len(plan.tiers) == 3


# ── PROVISIONAL ──


def test_a_plan_resting_on_an_architecture_deciding_assumption_is_provisional():
    plan = build(
        "An internal tool for our ops team to track equipment. About 200 page "
        "views a day. If it is down for an hour nobody minds. Budget $60."
    )
    assert plan.priced is True
    assert plan.provisional is True
    # durability was never stated, and that decides whether backups exist.
    assert any("durability" in r for r in plan.provisional_reasons)


def test_a_fully_stated_workload_is_not_flagged_provisional():
    plan = build(
        "I manage IT for a 3-hospital group in Pune. We want to move patient "
        "appointments, records and lab reports online so doctors and front "
        "desk can access them from all three sites. About 450 staff use it, "
        "roughly 6,000 record lookups a day, with peaks in the morning. "
        "Patient data must stay inside India and cannot be lost. Downtime "
        "during OPD hours is unacceptable. Budget is about $900 a month."
    )
    assert plan.priced is True
    assert plan.provisional is False, plan.provisional_reasons
