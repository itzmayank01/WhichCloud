"""The determinism claim, asserted rather than asserted-about.

Moving extraction to a language model split this project's core claim in
two. This file holds up the half that must remain absolute:

    given the same Constraints, the decision and pricing layers produce
    the same components and the same totals, every time.

Nothing here calls a model. That is the point -- `plan_from()` takes a
Constraints object directly, so the deterministic half can be exercised
with no network, no cache, and no variance to average out.

The other half (does extraction return the same Constraints twice?) is
measured, not asserted, in tests/probes/extraction_variance.py -- because
it is a property of a model, and a test that pretends otherwise would be
claiming something this code cannot enforce.
"""

from __future__ import annotations

from whichcloud.constraints import Constraints
from whichcloud.plan import plan_from

ITERATIONS = 100


def _hospital() -> Constraints:
    """The Pune workload, as Constraints -- built directly rather than
    extracted, so this test is unaffected by how extraction behaves."""
    c = Constraints(
        country="IN", sector="healthcare", availability="high",
        durability="high", users=450, requests_per_day=6000,
        peak_shape="morning", budget_monthly_usd=900.0,
        storage_gb=0.0, egress_gb=0.0, public_facing=False,
        country_lock=True,
    )
    c.stated.update({
        "country", "sector", "availability", "durability", "users",
        "requests_per_day", "peak_shape", "budget_monthly_usd",
        "public_facing",
    })
    return c


def _fingerprint(plan) -> tuple:
    """Everything a user would see change, in one comparable value."""
    return (
        plan.archetype,
        plan.archetype_state,
        plan.network_topology,
        tuple(
            (
                tier.name,
                round(tier.monthly_total, 6),
                tuple((i.label, i.sku, str(i.monthly_usd)) for i in tier.estimate.items),
                tier.rto, tier.rpo, tier.region_rto, tier.region_rpo,
                tuple(tier.gives_up),
                tuple(sorted(tier.justifications.items())),
                tuple(tier.pattern_diff),
            )
            for tier in plan.tiers
        ),
        tuple(n["regulation"] for n in plan.compliance),
        plan.over_budget_note,
    )


def test_the_decision_layer_is_deterministic_over_100_runs():
    """100 identical inputs, one distinct output. If this ever fails, the
    project's headline claim -- that the numbers are computed rather than
    generated -- has stopped being true, whatever the extractor does."""
    constraints = _hospital()
    fingerprints = {
        _fingerprint(plan_from(constraints, "", archetype="web_app")) for _ in range(ITERATIONS)
    }
    assert len(fingerprints) == 1, (
        f"{len(fingerprints)} distinct outputs from {ITERATIONS} identical "
        "inputs -- the decision layer is not deterministic"
    )


def test_determinism_holds_for_a_withheld_plan_too():
    """A refusal is an answer, and has to be as stable as a price."""
    c = Constraints(users=10, requests_per_day=100)
    c.stated.update({"users", "requests_per_day"})
    fingerprints = {
        _fingerprint(plan_from(c, "")) for _ in range(ITERATIONS)
    }
    assert len(fingerprints) == 1


def test_plan_from_never_calls_a_model(monkeypatch):
    """Guards the split itself. If plan_from() ever grows a call back into
    extraction, this fails rather than quietly making every 'deterministic'
    test above dependent on a network round trip."""
    import whichcloud.llm_extract as llm

    def explode(*a, **k):  # noqa: ANN002, ANN003
        raise AssertionError("plan_from() must not call the extractor")

    monkeypatch.setattr(llm, "extract", explode)
    monkeypatch.setattr(llm, "_call_with_failover", explode)
    plan = plan_from(_hospital(), "", archetype="web_app")
    assert plan.tiers


def test_the_same_constraints_price_identically_regardless_of_description():
    """The description is read for a few narrow gates (x86, isolation) and
    nothing else. Two runs with the same Constraints and unrelated prose
    must agree on every price."""
    c = _hospital()
    a = plan_from(c, "some entirely unrelated sentence", archetype="web_app")
    b = plan_from(c, "another unrelated sentence", archetype="web_app")
    assert [t.monthly_total for t in a.tiers] == [t.monthly_total for t in b.tiers]
