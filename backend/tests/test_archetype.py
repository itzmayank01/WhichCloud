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
    RECOGNISED_UNPRICED,
    STATE_UNKNOWN,
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
    """These are recognised_unpriced, not unknown -- the shape IS known,
    what is missing is a validated price for it. Both states withhold."""
    plan = build(prompt)
    assert plan.archetype_state == RECOGNISED_UNPRICED
    assert plan.priced is False
    assert plan.tiers == []
    assert plan.withheld_reason


@pytest.mark.parametrize("prompt", list(PROBES.values()))
def test_a_recognised_shape_is_named_and_described_not_just_refused(prompt):
    """Withholding a price must not mean discarding the analysis. For a
    recognised shape the useful answer is what that architecture needs --
    not the clarifying questions, which would be asking the user to
    re-explain something already understood."""
    plan = build(prompt)
    assert plan.constraints is not None
    assert plan.load.sizing_basis()["load_tier"]
    assert plan.archetype != UNKNOWN
    assert plan.archetype_requirements, "a recognised shape must be describable"
    assert plan.clarifying_questions == []
    assert plan.covered_archetypes


def test_an_unclassifiable_prompt_asks_questions_instead(prompt="Please help us with our infrastructure."):
    plan = build(prompt)
    assert plan.archetype_state == STATE_UNKNOWN
    assert plan.priced is False
    assert plan.tiers == []
    assert len(plan.clarifying_questions) >= 3
    assert "withheld rather than guessed" in plan.withheld_reason


def test_coverage_is_reported_as_two_numbers_not_one():
    """"Coverage" alone would hide which of two very different claims it
    referred to: shapes we can name, versus shapes we can price."""
    plan = build("Please help us with our infrastructure.")
    assert plan.coverage_summary["shapes_recognised"] == 7
    assert plan.coverage_summary["shapes_priced"] == 1


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


def test_durability_normal_still_takes_backups():
    """The correction: being offline for an hour and losing the data are
    independent axes. The old ladder read "nobody minds an hour of
    downtime" as consent to hold no backups at all."""
    plan = build(
        "An internal tool for our ops team to track equipment. About 200 page "
        "views a day. If it is down for an hour nobody minds. Budget $60."
    )
    assert plan.constraints.durability == "normal"
    for tier in plan.tiers:
        assert tier.spec.backup_gb > 0, "normal durability must still back up"
        assert tier.spec.backup_retention_days == 7
        # What high adds is surviving loss of the REGION, not backups at all.
        assert tier.spec.backup_copy_gb == 0
        assert tier.spec.object_lock is False


def test_durability_high_adds_region_survival_on_top():
    plan = build(
        "A patient records system for a clinic in Jaipur. Cannot lose data, "
        "cannot have downtime. Budget is $80 a month."
    )
    assert plan.constraints.durability == "high"
    for tier in plan.tiers:
        assert tier.spec.backup_gb > 0
        assert tier.spec.backup_retention_days == 35
        assert tier.spec.backup_copy_gb > 0
        assert tier.spec.object_lock is True


def test_ephemeral_is_the_only_value_that_removes_backups_and_must_be_stated():
    plan = build(
        "A rendering cache for our internal build system, about 300 requests "
        "a day. The data is disposable, we can rebuild it any time. Budget $40."
    )
    assert plan.constraints.durability == "ephemeral"
    assert plan.constraints.source("durability") == "stated"
    for tier in plan.tiers:
        assert tier.spec.backup_gb == 0


def test_ephemeral_is_never_inferred_from_silence():
    """Absence of a durability statement means `normal`, which backs up.
    Only an explicit statement may remove backups."""
    plan = build(
        "An internal tool for our ops team to track equipment. About 200 page "
        "views a day. Budget $60."
    )
    assert plan.constraints.durability == "normal"
    assert plan.tiers[0].spec.backup_gb > 0


# ── storage/egress defaults scale, rather than being one constant ──


def test_default_storage_scales_with_headcount():
    """A 12-person tool and a 450-staff hospital must not share a storage
    assumption -- the flat 500 GB default was setting totals unexamined."""
    small = build(
        "An internal tool for our 12-person ops team to track equipment. "
        "About 200 page views a day. Budget $60."
    )
    large = build(
        "An internal tool for our 450 staff to track equipment. About 200 "
        "page views a day. Budget $600."
    )
    assert small.tiers[0].spec.storage_gb < large.tiers[0].spec.storage_gb


def test_default_storage_scales_with_load_band():
    quiet = build("An internal tool, 300 requests a day. Budget $100.")
    busy = build("A marketplace, about 2 million requests a day. Budget $5000.")
    assert quiet.tiers[0].spec.storage_gb < busy.tiers[0].spec.storage_gb


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


# ── the LLM path itself ──
# Marked with the `llm` fixture, which opts back in to the model that
# conftest disables for the rest of the suite. These are the only tests
# here that touch the network, and they are about extraction rather than
# about any decision made from it.


def test_the_minimum_evidence_bar_refuses_a_single_weak_signal(llm):
    """Part 3's requirement, end to end: one unopposed weak phrase must
    not classify. This exact prompt was the phrase table's only
    false-confident -- it called it `migration` on the strength of
    'move to the cloud' alone."""
    from whichcloud.llm_extract import extract

    _c, meta = extract(
        "We need to move to the cloud. What would it cost?",
        use_cache=True, allow_fallback=False,
    )
    assert meta.archetype == UNKNOWN
    assert meta.archetype_confidence < 0.6


def test_extraction_reads_a_volume_the_phrase_tables_missed(llm):
    """'80,000 loan applications a month' extracted as 0 under phrase
    matching -- no unit phrase matched 'loan applications', and the
    figure is monthly rather than daily. Both are handled by reading
    rather than matching."""
    from whichcloud.llm_extract import extract

    c, _meta = extract(
        "lending platform in Bengaluru, 80,000 loan applications a month, "
        "KYC documents and repayment records, RBI audits us, data must "
        "remain in India, budget $3,000 a month.",
        use_cache=True, allow_fallback=False,
    )
    assert c.requests_per_day > 0
    assert c.country == "IN"
    assert c.country_lock is True


def test_the_fallback_is_marked_degraded(monkeypatch):
    """With no model reachable, a plan still comes back -- and says
    plainly that it was read by the weaker reader."""
    monkeypatch.setenv("WHICHCLOUD_DISABLE_LLM", "1")
    plan = build(
        "I manage IT for a 3-hospital group in Pune. We want to move "
        "patient appointments, records and lab reports online. About 450 "
        "staff use it, roughly 6,000 record lookups a day, with peaks in "
        "the morning. Patient data must stay inside India and cannot be "
        "lost. Downtime during OPD hours is unacceptable. Budget is about "
        "$900 a month."
    )
    assert plan.degraded is True
    assert plan.extraction_reader == "phrase-tables"
    assert "phrase matching" in plan.degraded_reason
    # Still a usable answer, not an error.
    assert plan.tiers


# ── the evidence bar (confidence bands) ──
# Pure function over (confidence, spans), so these run offline and are
# the authoritative check on the rule -- the measurement scripts only
# confirm it against live model output.


def test_high_confidence_with_one_substantive_span_classifies():
    """The eight misses the flat two-span rule produced all looked like
    this: 0.90 confidence, one long span quoting the workload. Rejecting
    them measured quoting style, not evidence."""
    from whichcloud.llm_extract import passes_evidence_bar

    ok, why = passes_evidence_bar(
        0.90,
        ["Consultants need to log candidates, attach CVs, and track where "
         "each one is in the process"],
    )
    assert ok, why


def test_high_confidence_on_an_incidental_keyword_does_not_classify():
    """A high score resting on a bare noun is still a guess -- the span
    has to describe behaviour."""
    from whichcloud.llm_extract import passes_evidence_bar

    ok, why = passes_evidence_bar(0.95, ["Postgres"])
    assert not ok
    assert "incidental keyword" in why


def test_mid_band_needs_corroboration():
    from whichcloud.llm_extract import passes_evidence_bar

    one, _ = passes_evidence_bar(0.70, ["drivers log what they picked up"])
    two, _ = passes_evidence_bar(
        0.70, ["drivers log what they picked up", "office can invoice from it"]
    )
    assert not one, "one mid-band span must not be enough"
    assert two, "two mid-band spans corroborate"


def test_low_confidence_never_classifies():
    """'We need to move to the cloud. What would it cost?' scored 0.10
    with no spans -- the single false-confident the phrase table produced,
    and it must stay refused under every band."""
    from whichcloud.llm_extract import passes_evidence_bar

    for spans in ([], ["move to the cloud"], ["we need to move to the cloud now"]):
        ok, why = passes_evidence_bar(0.10, spans)
        assert not ok, f"0.10 classified on {spans}: {why}"


def test_every_recorded_miss_now_classifies():
    """Replayed from the measured run that produced the 40% figure. Each
    of these returned web_app at 0.90 with exactly one span and was
    refused by MIN_ARCHETYPE_SPANS=2. Checked here against the recorded
    values so the fix is provable without re-spending model quota."""
    from whichcloud.llm_extract import passes_evidence_bar

    recorded = {
        "business-1": (0.90, ["Consultants need to log candidates, attach CVs, "
                              "and track where each one is in the process"]),
        "backstory-1": (0.90, ["case workers to be able to open a client file, "
                               "add notes after a visit, and have the "
                               "supervisor sign it off"]),
        "mixed-2": (0.90, ["portal where our suppliers can update their own "
                           "compliance documents"]),
        "jargon-3": (0.90, ["Headless CMS driving a Next.js storefront"]),
    }
    for pid, (confidence, spans) in recorded.items():
        ok, why = passes_evidence_bar(confidence, spans)
        assert ok, f"{pid} still refused: {why}"
