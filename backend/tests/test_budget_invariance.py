"""Budget is a CONSTRAINT, never an input to sizing.

Four knobs were capped in sequence over as many sessions -- compute, then
read replicas, then cache, then the database's own size -- and each time a cap
landed the growth loop moved the money to whichever knob was still open. That
is not four bugs. It is one loop expanding toward the stated budget until
something stops it, and capping knobs one at a time will always be a knob
behind.

The fix is that sizing must not see the budget at all. These tests are how we
know it does not: hold the workload still, vary only the money, and the
architecture must not move.
"""

from __future__ import annotations

import pytest

from whichcloud import engine
from whichcloud.requirements import Requirement

PROVIDERS = ("aws", "gcp", "azure")
BUDGETS = (500.0, 5_000.0, 50_000.0)


def _workload(budget: float, daily: int = 8_000) -> Requirement:
    """One workload. Only the budget varies between calls."""
    return Requirement(
        goal="Retail billing",
        workload_type="web",
        traffic_pattern="steady",
        traffic_scale="high",
        region="india",
        budget_monthly_usd=budget,
        storage_gb=500,
        egress_gb=500,
        high_availability=True,
        daily_transactions=daily,
    )


def _shape(option) -> tuple:
    """Everything about an architecture that money must not be able to move."""
    s = option.spec
    return (
        s.compute_count,
        s.compute_vcpu,
        s.compute_memory_gb,
        s.database_vcpu,
        s.database_memory_gb,
        s.database_read_replicas,
        s.database_multi_az,
        s.cache_vcpu,
        s.cache_memory_gb,
        str(option.monthly),
    )


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


def _no_budget(daily: int = 8_000) -> Requirement:
    """The same workload with no budget stated at all.

    This is the reference design: what the load alone asks for. Every
    sufficient budget must reproduce it exactly.
    """
    r = _workload(5_000.0, daily)
    return replace_budget(r, None)


def replace_budget(req: Requirement, budget):
    from dataclasses import replace

    return replace(req, budget_monthly_usd=budget)


def _sizes(shape: tuple) -> tuple:
    """The capacity part of a shape, without the price."""
    return shape[:-1]


@needs_db
@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("daily", (8_000, 8_000_000))
def test_a_sufficient_budget_never_changes_the_architecture(provider, daily):
    """More money must buy exactly the same design.

    The reference is the design with NO budget stated -- what the load alone
    asks for. Any budget large enough to afford it must reproduce it to the
    byte, at both a small and a large workload: on a small one the sizing
    happens to be cheap enough that a bug can hide, so the large case is the
    one that asks the question honestly.
    """
    reference = {
        o.label: _shape(o) for o in engine.recommend(_no_budget(daily), provider, dsn=None)
    }
    for budget in (5_000.0, 50_000.0, 500_000.0):
        got = {
            o.label: _shape(o)
            for o in engine.recommend(_workload(budget, daily), provider, dsn=None)
        }
        for label, shape in got.items():
            if float(reference[label][-1]) > budget:
                continue  # legitimately unaffordable; see the degradation test
            assert shape == reference[label], (
                f"{provider}/{label} at {daily:,}/day: a ${budget:,.0f} budget "
                f"produced a different architecture than no budget at all\n"
                f"  no budget: {reference[label]}\n"
                f"  ${budget:,.0f}: {shape}"
            )


@needs_db
@pytest.mark.parametrize("provider", PROVIDERS)
def test_an_insufficient_budget_only_ever_shrinks_the_design(provider):
    """Too little money degrades, and never the other way.

    Budget is allowed to take capacity away -- that is the whole point of
    stating one -- but no component may come back LARGER than the design the
    load asked for.
    """
    reference = {o.label: _shape(o) for o in engine.recommend(_no_budget(), provider, dsn=None)}
    tight = {
        o.label: _shape(o) for o in engine.recommend(_workload(200.0), provider, dsn=None)
    }
    for label, shape in tight.items():
        for i, (got, want) in enumerate(zip(_sizes(shape), _sizes(reference[label]))):
            if isinstance(got, (int, float)) and isinstance(want, (int, float)):
                assert got <= want, (
                    f"{provider}/{label}: a $200 budget produced a LARGER "
                    f"component than the load asked for (index {i}: {got} > {want})"
                )


@needs_db
@pytest.mark.parametrize("provider", PROVIDERS)
def test_load_does_change_the_architecture(provider):
    """The other half of the same bug.

    Budget must not move the design, but load must. A sizing function that
    ignores both is just as broken as one that reads the budget.
    """
    small = {o.label: _shape(o) for o in engine.recommend(_workload(5_000.0, 8_000), provider, dsn=None)}
    large = {o.label: _shape(o) for o in engine.recommend(_workload(5_000.0, 8_000_000), provider, dsn=None)}
    assert any(small[k] != large[k] for k in small), (
        f"{provider}: a thousandfold more load produced an identical "
        f"architecture -- sizing is ignoring the workload"
    )
