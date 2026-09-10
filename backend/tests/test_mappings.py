"""Cross-cloud comparison refuses what it cannot honestly compare.

The failure this guards: the old comparison summed whatever each cloud
happened to price and ranked the totals. AWS priced twenty-one
components; Azure and GCP had adapters for seven. So their totals were
lower for a reason that had nothing to do with being cheaper, and the
ranking put "$336" above "$649" and called it the winner.

The interface worked around it by intersecting line-item LABELS, which is
a guess about equivalence made from text. These tests hold the actual
answer: a table that says what corresponds, what does not, and refuses
where nobody has established either.
"""

from __future__ import annotations

import pytest

from whichcloud import mappings
from whichcloud.mappings import MappingError, _parse


def test_the_table_loads_and_is_not_empty():
    entries = mappings.load()
    assert entries
    assert all(m.id and m.role for m in entries)


def test_every_confidence_level_is_represented():
    """A table with no `none` entries has not been honest about gaps --
    there are always services one cloud has and another does not."""
    levels = {m.confidence for m in mappings.load()}
    assert "none" in levels, "no gaps recorded — that is not credible"
    assert levels <= {"exact", "close", "partial", "none"}


def test_a_no_equivalent_mapping_refuses_comparison():
    """The whole point. Where nothing corresponds, the comparison must
    stop rather than substitute a rough analogue."""
    verdict = mappings.may_compare("inference", ("aws", "gcp"))
    assert not verdict.comparable
    assert verdict.confidence == "none"
    # And it says WHY, specifically enough to be checked.
    assert "Vertex" in verdict.reason or "not ingested" in verdict.reason.lower()


def test_an_unmapped_category_refuses_rather_than_assuming():
    """The stricter of the two possible defaults, and the right one. A
    category nobody has written a mapping for is one nobody has checked
    the equivalence of."""
    verdict = mappings.may_compare("a_category_nobody_mapped", ("aws", "gcp"))
    assert not verdict.comparable
    assert verdict.confidence == "unmapped"


def test_a_clean_mapping_compares_without_a_caveat():
    verdict = mappings.may_compare("storage", ("aws", "gcp", "azure"))
    assert verdict.comparable
    assert verdict.confidence == "exact"
    assert not verdict.caveat


def test_a_close_mapping_compares_but_carries_its_caveat():
    """`close` is comparable and not identical, and the difference has to
    travel with the number rather than being dropped."""
    verdict = mappings.may_compare("compute", ("aws", "gcp", "azure"))
    assert verdict.comparable
    assert verdict.caveat
    # The specific thing that does not compare on compute.
    assert "sustained" in verdict.caveat.lower()


def test_azure_ha_being_derived_is_disclosed_on_the_mapping():
    """Azure publishes no HA meter, so this engine bills the standby as a
    second instance. Comparing a published rate against a derived one is
    a comparison of two different kinds of number."""
    verdict = mappings.may_compare("database", ("aws", "azure"))
    assert verdict.comparable
    assert "derived" in verdict.caveat.lower()


# ── the schema refuses to let a mapping contradict itself ────────────


def test_claiming_a_clean_mapping_while_naming_two_clouds_fails():
    from pathlib import Path

    with pytest.raises(MappingError, match="only"):
        _parse({
            "id": "x", "role": "r", "confidence": "exact",
            "aws": {"service": "A"}, "gcp": {"service": "G"},
            "does_not_map": "something",
        }, Path("t.yaml"))


def test_claiming_no_equivalent_while_naming_two_clouds_fails():
    from pathlib import Path

    with pytest.raises(MappingError, match="no equivalent"):
        _parse({
            "id": "x", "role": "r", "confidence": "none",
            "aws": {"service": "A"}, "gcp": {"service": "G"},
        }, Path("t.yaml"))


def test_a_comparable_mapping_must_say_what_does_not_map():
    """A mapping with no caveat has not been thought about. Every real
    pair of cloud services differs somewhere."""
    from pathlib import Path

    with pytest.raises(MappingError, match="what does NOT map"):
        _parse({
            "id": "x", "role": "r", "confidence": "exact",
            "aws": {"service": "A"}, "gcp": {"service": "G"},
            "azure": {"service": "Z"},
        }, Path("t.yaml"))


def test_an_unknown_confidence_level_fails_loudly():
    from pathlib import Path

    with pytest.raises(MappingError, match="confidence"):
        _parse({
            "id": "x", "role": "r", "confidence": "probably-fine",
            "aws": {"service": "A"},
        }, Path("t.yaml"))


# ── coverage reporting ───────────────────────────────────────────────


def test_coverage_names_the_gaps_rather_than_counting_them():
    """"9 of 12 mapped" hides which three, and the three are the useful
    part -- they are the workloads a user must not compare on price."""
    coverage = mappings.coverage()
    assert coverage["total"] == len(mappings.load())
    assert coverage["no_equivalent"]
    for gap in coverage["no_equivalent"]:
        assert gap["role"] and gap["why"]


# ── the knowledge base's own contract ────────────────────────────────


def test_the_knowledge_base_reached_its_v1_target():
    """20-30 hand-verified entries was the PRD's target. It sat at 10."""
    from whichcloud.knowledge import load_techniques

    techniques = load_techniques()
    assert 22 <= len(techniques) <= 30, len(techniques)


def test_every_technique_carries_a_rule_the_engine_evaluates():
    """The brief's requirement: a rule, not prose advice.

    The rule is `applies_when` -- the engine evaluates it against the
    Requirement to decide whether the technique is offered at all. EVERY
    technique has one.

    `effect` is a different and narrower thing: whether the technique is
    AUTO-APPLIED to the architecture. Only selections qualify (ARM vs
    x86, spot vs on-demand, gp3 vs gp2), because an effect is folded
    into the real spec -- so a technique declaring a QUANTITY would
    resize the fleet or overwrite a figure the user gave rather than
    describe a saving. Techniques whose lever is a quantity are surfaced
    as advisory, which is a statement about who decides how much to buy,
    not about whether the technique is real."""
    from whichcloud.knowledge import load_techniques

    for technique in load_techniques():
        has_rule = bool(
            technique.workload_types
            or technique.traffic_patterns
            or technique.min_monthly_spend_usd
            or technique.requires
        )
        assert has_rule, f"{technique.id} has no applies_when rule"


def test_auto_applied_effects_are_selections_never_quantities():
    """The guard on the mistake above. An effect that sets a COUNT or a
    GB figure overrides the engine's sizing; one that swaps a class or an
    architecture cannot."""
    from whichcloud.knowledge import KNOWN_EFFECTS

    forbidden_shapes = {
        "compute_count", "nat_gateway_count", "egress_gb", "cdn_gb",
        "vpc_endpoints", "lifecycle_gb", "cache_vcpu",
        "database_read_replicas", "block_storage_gb", "storage_gb",
    }
    assert not (KNOWN_EFFECTS & forbidden_shapes)


def test_every_technique_states_a_trade_off():
    """A technique with no downside is one that has not been understood."""
    from whichcloud.knowledge import load_techniques

    for technique in load_techniques():
        assert technique.tradeoffs, f"{technique.id} claims no trade-off"


def test_every_savings_claim_cites_its_basis():
    """A percentage with no source is a number somebody remembered."""
    from whichcloud.knowledge import load_techniques

    for technique in load_techniques():
        assert technique.basis, f"{technique.id} has an uncited saving"
        assert len(technique.basis) > 40, technique.id


def test_every_technique_names_a_tool():
    """Advice without a tool is not actionable."""
    from whichcloud.knowledge import load_techniques

    for technique in load_techniques():
        assert technique.tools, f"{technique.id} names no implementing tool"
