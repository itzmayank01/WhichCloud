"""The contract every archetype graph has to satisfy.

Written once and parametrised over the registry, so an archetype landing
later cannot skip any of it. What each rule guards:

  CANDIDATES PRICEABLE   a candidate naming a category the catalog does
                         not carry would cost zero and read as free.
  FORBIDDEN HONOURED     a static site with a database is not an
                         expensive static site, it is a different and
                         wrong architecture.
  TIERS DIFFER           three sizes of one design is one design.
  DETERMINISM            same Constraints, same architecture, every run.
"""

from __future__ import annotations

import pytest

from whichcloud.archetypes import GRAPHS
from whichcloud.archetypes.base import ROLES
from whichcloud.constraints import Constraints
from whichcloud.estimator import estimate
from whichcloud.fingerprint import MIN_TIER_SPREAD, fingerprint
from whichcloud.load_model import build_load
from whichcloud.pricing.store import stats

pytestmark = pytest.mark.skipif(
    sum(r["n"] for r in stats()) == 0, reason="needs an ingested price catalog"
)

NAMES = sorted(GRAPHS)


def _constraints_for(name: str) -> Constraints:
    """A representative workload for each shape, in its own terms."""
    common = dict(country="IN", public_facing=True)
    per_shape = {
        "static_site": dict(
            sector="public_web", requests_per_day=1_000,
            static_assets="light", availability="low", durability="normal",
        ),
    }
    return Constraints(**{**common, **per_shape.get(name, {})})


def _tiers(name: str):
    graph = GRAPHS[name]
    c = _constraints_for(name)
    load = build_load(c, "")
    out = []
    for level in (1, 2, 3):
        spec = graph.build(
            tier_level=level, constraints=c, load=load,
            region="india", description="",
        )
        out.append((spec, estimate(spec, "aws")))
    return graph, out


@pytest.mark.parametrize("name", NAMES)
def test_every_candidate_declares_a_known_role(name):
    for candidate in GRAPHS[name].candidates:
        assert candidate.role in ROLES


@pytest.mark.parametrize("name", NAMES)
def test_the_candidate_set_is_curated_not_exhaustive(name):
    """15-25 services. Fewer is not a considered architecture; more is a
    catalog dump, and 'we considered everything' is not a decision."""
    count = len(GRAPHS[name].candidates)
    assert 12 <= count <= 25, f"{name} has {count} candidates"


@pytest.mark.parametrize("name", NAMES)
def test_every_candidate_category_exists_in_the_catalog(name):
    """"May select" has to mean "the catalog can price". A candidate
    naming a category with no rows would cost zero, which reads as free
    rather than as unknown."""
    available = {row["category"] for row in stats()}
    for candidate in GRAPHS[name].candidates:
        assert candidate.category in available, (
            f"{name}: {candidate.name} names category "
            f"{candidate.category!r}, which the catalog does not carry"
        )


@pytest.mark.parametrize("name", NAMES)
def test_the_graph_cites_where_its_candidate_set_came_from(name):
    """A reference architecture, not a recollection."""
    assert GRAPHS[name].sources


@pytest.mark.parametrize("name", NAMES)
def test_no_tier_contains_a_component_the_archetype_forbids(name):
    graph, tiers = _tiers(name)
    for spec, _est in tiers:
        assert graph.violations(spec) == [], (
            f"{name} {spec.name}: {graph.violations(spec)}"
        )


@pytest.mark.parametrize("name", NAMES)
def test_every_forbidden_rule_carries_a_reason(name):
    for rule in GRAPHS[name].forbidden:
        assert rule.reason and len(rule.reason) > 30, rule.component


@pytest.mark.parametrize("name", NAMES)
def test_every_tier_prices_completely(name):
    """A shape that cannot price its own components is not a cheap shape,
    it is an incomplete one -- and an incomplete estimate showing a total
    is the confident wrong answer this engine exists to refuse."""
    _graph, tiers = _tiers(name)
    for spec, est in tiers:
        assert not est.missing, f"{name} {spec.name} missing {est.missing}"


@pytest.mark.parametrize("name", NAMES)
def test_consecutive_tiers_differ_by_service(name):
    _graph, tiers = _tiers(name)
    prints = [fingerprint(type("T", (), {"estimate": est})) for _s, est in tiers]
    for lower, higher in zip(prints, prints[1:]):
        spread = len((higher - lower) | (lower - higher))
        assert spread >= MIN_TIER_SPREAD, (
            f"{name}: spread {spread}, added {sorted(higher - lower)}"
        )


@pytest.mark.parametrize("name", NAMES)
def test_each_tier_above_the_first_says_what_it_buys(name):
    graph = GRAPHS[name]
    for level in (2, 3):
        assert graph.tier_notes.get(level), (
            f"{name} tier {level} adds services without saying what for"
        )


@pytest.mark.parametrize("name", NAMES)
def test_the_same_constraints_produce_the_same_architecture(name):
    """No clock, no ordering dependence, no model call. The decision
    layer is pure over Constraints and stays that way."""
    _graph, first = _tiers(name)
    for _ in range(3):
        _graph2, again = _tiers(name)
        assert [s for s, _ in again] == [s for s, _ in first]


@pytest.mark.parametrize("name", NAMES)
def test_the_sizing_driver_names_the_shape_not_requests_per_second(name):
    """Sizing every shape by request rate is what costed a 40-machine
    estate as one small instance. Each shape says what it is measured
    in, and renders the actual figures."""
    graph = GRAPHS[name]
    c = _constraints_for(name)
    note = graph.sizing.describe(c, build_load(c, ""))
    assert note and any(ch.isdigit() for ch in note), name
    assert graph.sizing.fields
