"""A conflict between two stated requirements is an answer, not a 500.

"move it to the cloud before modernising anything" and "it cannot be down
during working hours" ask for a lift-and-shift that also survives a zone
failure. A 1:1 copy of an estate has one instance per source machine and no
load balancer BY DESIGN -- that is what lift-and-shift means -- so the
compliance check correctly reports single instance, no balancer, single-AZ
database.

The planner used to `raise AssertionError` there, which reached users as a
bare HTTP 500 with no message. The invariant is right; treating every route
to it as a programming error was not.

Silently adding a load balancer would be the re-architecture the user ruled
out in the same sentence, so the engine refuses and names the conflict.
Which requirement to relax is theirs to choose.
"""

from __future__ import annotations

import pytest

from whichcloud.plan import IncompatibleRequirements


def test_it_is_an_exception_type_callers_can_catch() -> None:
    exc = IncompatibleRequirements("migration", "tier_1", ["runs a single instance"])
    assert exc.archetype == "migration"
    assert exc.tier == "tier_1"
    assert exc.violations == ["runs a single instance"]


def test_the_message_keeps_the_full_diagnostic() -> None:
    """The harness and the logs still need the original assertion text."""
    exc = IncompatibleRequirements("migration", "tier_1", ["a", "b"])
    assert "migration tier_1 was generated non-compliant" in str(exc)
    assert "'a'" in str(exc) and "'b'" in str(exc)


def test_a_conflicting_description_is_withheld_not_crashed(monkeypatch) -> None:
    """End to end on the phrase-table reader, so it needs no model and no
    network. The description states both halves of the conflict."""
    monkeypatch.setenv("WHICHCLOUD_DISABLE_LLM", "1")
    from whichcloud import plan as planning

    # A lift-and-shift that must not go down, with an estate big enough that
    # the single-instance tier is the one the checker objects to.
    description = (
        "We have 1 server in our own server room running the order system and "
        "we want to move it to the cloud before modernising anything. It "
        "cannot be down during working hours. Budget is around $900 a month."
    )
    try:
        plan = planning.build(description, provider="aws")
    except IncompatibleRequirements:  # pragma: no cover
        pytest.fail("the conflict must be reported as a plan, not raised to the caller")

    # Either it priced a compliant design or it withheld with a reason --
    # what it must never do is raise, which is what produced the 500.
    if not plan.priced:
        assert plan.withheld_reason
        assert "withheld" in plan.withheld_reason.lower()
