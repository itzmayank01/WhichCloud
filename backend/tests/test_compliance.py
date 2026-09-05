"""Cheapest, and cheapest that meets the brief, are different architectures.

The cheapest way to serve traffic is always one machine and one database.
So on a workload whose owner wrote that it cannot go down, the cheapest
option is simultaneously the lowest number on the screen and the one shape
that fails the requirement -- and it was presented as a peer of the other
two, with nothing to say so.

The engine already knew: `_fit_within_budget` refuses to trade a standby
away on a CRITICAL workload. Nothing carried that knowledge out to the
caller, which is the gap these close.
"""

from __future__ import annotations

import pytest

from whichcloud import engine
from whichcloud.engine import business_criticality, unmet_requirements
from whichcloud.estimator import ArchitectureSpec
from whichcloud.requirements import Requirement


def db_available() -> bool:
    try:
        from whichcloud.pricing.store import connect

        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) AS n FROM price_points")
            return cur.fetchone()["n"] > 0
    except Exception:
        return False


needs_db = pytest.mark.skipif(
    not db_available(), reason="needs an ingested price catalog"
)


def retail() -> Requirement:
    """The requirement the audit was run against. Every word is load-bearing:
    'must not go down' is what makes it CRITICAL, and $500 is what forces the
    budget ladder to start taking things away."""
    return Requirement(
        goal="Retail billing",
        workload_type="web",
        traffic_pattern="steady",
        traffic_scale="high",
        region="india",
        budget_monthly_usd=500.0,
        storage_gb=500,
        egress_gb=500,
        high_availability=True,
        daily_transactions=8_000,
    )


# ── the distinction itself ────────────────────────────────────────────────


def test_a_tradeoff_and_an_unmet_requirement_are_not_the_same_thing():
    """Only the requirement's own words tell them apart.

    A single-zone database is a tradeoff on most workloads and a broken
    promise on one that asked for high availability. Same spec, same
    sentence, different meaning -- which is why this reads the requirement
    and `tradeoffs` does not.
    """
    fragile = ArchitectureSpec(
        name="web", region="india", compute_count=1, database_vcpu=2,
        database_memory_gb=8.0, database_multi_az=False,
    )
    asked = Requirement(goal="shop", workload_type="web", high_availability=True)
    did_not_ask = Requirement(goal="shop", workload_type="web")

    assert unmet_requirements(fragile, asked), "a broken promise went unreported"
    assert unmet_requirements(fragile, did_not_ask) == (), (
        "nothing was promised, so nothing is unmet"
    )


def test_a_shape_that_delivers_what_was_asked_has_nothing_unmet():
    solid = ArchitectureSpec(
        name="web", region="india", compute_count=2, database_vcpu=2,
        database_memory_gb=8.0, database_multi_az=True,
    )
    asked = Requirement(goal="shop", workload_type="web", high_availability=True)
    assert unmet_requirements(solid, asked) == ()


def test_each_broken_promise_is_named_separately():
    """One line per gap, so the reader can see whether it is the database,
    the instance count, or both."""
    asked = Requirement(goal="shop", workload_type="web", high_availability=True)
    one_instance = ArchitectureSpec(
        name="web", region="india", compute_count=1, database_vcpu=2,
        database_memory_gb=8.0, database_multi_az=True,
    )
    no_standby = ArchitectureSpec(
        name="web", region="india", compute_count=3, database_vcpu=2,
        database_memory_gb=8.0, database_multi_az=False,
    )
    assert len(unmet_requirements(one_instance, asked)) == 1
    assert len(unmet_requirements(no_standby, asked)) == 1
    assert "instance" in unmet_requirements(one_instance, asked)[0]
    assert "standby" in unmet_requirements(no_standby, asked)[0]


def test_a_database_free_shape_is_not_faulted_for_having_no_standby():
    """A shape with no database cannot fail to make it highly available.

    The multi-AZ note used to appear on architectures that had no database
    at all; the same mistake here would put a permanent warning on every
    static site.
    """
    asked = Requirement(goal="site", workload_type="web", high_availability=True)
    static = ArchitectureSpec(name="site", region="india", compute_count=2)
    assert unmet_requirements(static, asked) == ()


# ── what the engine hands out ─────────────────────────────────────────────


@needs_db
def test_the_cheapest_option_on_a_critical_workload_says_it_fails_the_brief():
    """REGRESSION-GUARD. This is the audit finding, as a test.

    Before this, the retail requirement produced a Cheapest option with one
    instance and no standby, marked with nothing at all, sitting beside two
    compliant options and showing the lowest price of the three.
    """
    options = {o.label: o for o in engine.recommend(retail(), "aws", dsn=None)}
    assert business_criticality(retail()) == "CRITICAL"

    cheapest = options["Cheapest"]
    assert not cheapest.compliant, "a single point of failure passed as compliant"
    assert cheapest.unmet, "flagged non-compliant with no reason given"
    assert cheapest.criticality == "CRITICAL"

    for label in ("Most reliable", "Most optimized"):
        assert options[label].compliant, f"{label} should meet the brief"


@needs_db
def test_nothing_is_flagged_when_availability_was_never_asked_for():
    """The badge has to stay off, or it stops meaning anything.

    A single-instance design is the RIGHT answer for a workload whose owner
    never said otherwise; warning about it there would train the reader to
    ignore the warning where it matters.
    """
    relaxed = Requirement(goal="an internal tool", workload_type="web")
    for option in engine.recommend(relaxed, "aws", dsn=None):
        assert option.compliant, f"{option.label} flagged with nothing promised"
        assert option.criticality in ("LOW", "MEDIUM")


@needs_db
def test_the_budget_ladder_never_reports_keeping_what_the_shape_does_not_have():
    """The message that shipped attached to the option it was false about.

    `_fit_within_budget` protects the standby and the second instance on a
    CRITICAL workload, and said so -- including on the Cheapest variant,
    which is built without either by definition. So a reader looking at a
    one-instance, one-zone design was told those two things had been kept
    for them.
    """
    for option in engine.recommend(retail(), "aws", dsn=None):
        claims = [t for t in option.tradeoffs if t.startswith("kept ")]
        if not claims:
            continue
        claim = claims[0]
        if "the standby database" in claim:
            assert option.spec.database_multi_az, f"{option.label}: {claim}"
        if "a second instance" in claim:
            assert option.spec.compute_count > 1, f"{option.label}: {claim}"


@needs_db
def test_saturation_is_never_claimed_on_a_shape_that_fails_the_brief():
    """"A higher budget won't add useful capacity" has to be true when shown.

    It is only true of a shape that already delivers what was asked for. On
    one that does not, a higher budget buys precisely the thing it is
    missing -- so the Cheapest option told a reader looking at a single
    point of failure that spending more would not help them.
    """
    for option in engine.recommend(retail(), "aws", dsn=None):
        if not option.compliant:
            assert not option.budget_saturated, (
                f"{option.label} claims more budget buys nothing, while "
                f"missing: {option.unmet[0]}"
            )


# ── what the API hands out ────────────────────────────────────────────────


@needs_db
def test_the_answer_names_the_cheapest_shape_that_meets_the_brief():
    """A warning the reader cannot act on is only half of one.

    Telling someone the cheapest option fails their requirement, without
    saying which one does not, leaves them to work it out by clicking.
    """
    from whichcloud.api import _cheapest_compliant

    options = engine.recommend(retail(), "aws", dsn=None)
    named = _cheapest_compliant(options)
    assert named == "Most reliable", named

    # Cheapest BY PRICE, not by position: the tiers are ordered by posture,
    # and a budget ladder can reorder them by cost.
    meets = [o for o in options if o.compliant]
    assert named == min(meets, key=lambda o: o.monthly).label


@needs_db
def test_nothing_compliant_is_reported_as_nothing_rather_than_guessed_at():
    """The honest answer when no shape on offer meets the requirement."""
    from whichcloud.api import _cheapest_compliant

    options = engine.recommend(retail(), "aws", dsn=None)
    assert _cheapest_compliant([o for o in options if not o.compliant]) is None


@needs_db
def test_the_route_carries_compliance_out_to_the_interface():
    """The engine knew all along; the gap was that nothing said so."""
    from fastapi.testclient import TestClient

    from whichcloud.api import _option_out, app  # noqa: F401

    options = engine.recommend(retail(), "aws", dsn=None)
    shipped = {o.label: _option_out(o, "aws") for o in options}
    assert shipped["Cheapest"].compliant is False
    assert shipped["Cheapest"].unmet
    assert shipped["Most reliable"].compliant is True
    assert shipped["Most reliable"].unmet == []
