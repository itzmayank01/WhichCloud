"""Tests for the diagram topology, option diff, and shape trade-offs.

These three exist to let the interface draw a system rather than list a bill.
What is tested is that the drawing stays truthful: every node's cost comes
from the priced estimate, unpriced components are visible rather than dropped,
and a diff reports one change as one change.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from whichcloud import topology as topo
from whichcloud.engine import diff_options, recommend
from whichcloud.estimator import ArchitectureSpec, Estimate, LineItem
from whichcloud.requirements import Requirement


def item(label: str, sku: str, monthly: str, unit: str = "hour") -> LineItem:
    return LineItem(
        label=label,
        sku=sku,
        unit=unit,
        unit_price=Decimal("1"),
        quantity=Decimal("1"),
        monthly_usd=Decimal(monthly),
    )


def spec(**kw) -> ArchitectureSpec:
    base = dict(name="t", region="india", compute_count=3, compute_vcpu=2,
                compute_memory_gb=8.0)
    base.update(kw)
    return ArchitectureSpec(**base)


def db_available() -> bool:
    try:
        from whichcloud.pricing.store import stats

        return sum(r["n"] for r in stats()) > 0
    except Exception:
        return False


needs_db = pytest.mark.skipif(not db_available(), reason="needs a price catalog")


# ── topology ────────────────────────────────────────────────────────────


def test_every_node_carries_its_own_cost():
    """The whole point: a box on the diagram shows what that box costs."""
    est = Estimate("aws", "ap-south-1", spec(), [
        item("Compute × 3", "t4g.large", "58.87"),
        item("Database", "db.t4g.large", "121.91"),
    ])
    graph = topo.build(spec(), est)

    compute = graph.node("compute")
    assert compute is not None
    assert compute.monthly_usd == Decimal("58.87")
    assert graph.node("database").monthly_usd == Decimal("121.91")


def test_read_replica_gets_its_own_node_not_the_primarys():
    """REGRESSION-GUARD: 'Database read replica' starts with 'Database', the
    same prefix the primary matches. Checked in the wrong order the replica's
    price would overwrite the primary's node instead of getting its own."""
    est = Estimate("aws", "ap-south-1", spec(), [
        item("Database", "db.t4g.large", "121.91"),
        item("Database read replica × 2", "db.t4g.large", "60.96"),
    ])
    graph = topo.build(spec(), est)

    assert graph.node("database").monthly_usd == Decimal("121.91")
    replica = graph.node("database_replica")
    assert replica is not None
    assert replica.monthly_usd == Decimal("60.96")
    assert replica.label == "Database read replica"


def test_waf_line_items_merge_into_one_node():
    """REGRESSION-GUARD: WAF prices three line items (Web ACL, rules,
    requests) that are still one box. Overwriting by kind instead of summing
    would keep only the last price and silently drop the other two from the
    node's total while they stayed in the actual bill."""
    est = Estimate("aws", "ap-south-1", spec(), [
        item("WAF Web ACL", "waf:webacl", "5.00"),
        item("WAF rules × 10", "waf:rule", "10.00"),
        item("WAF request inspection", "waf:request", "6.00"),
    ])
    graph = topo.build(spec(), est)

    waf = graph.node("waf")
    assert waf is not None
    assert waf.monthly_usd == Decimal("21.00")


def test_share_drives_visual_weight():
    """The expensive node should look expensive, so share must be real."""
    est = Estimate("aws", "ap-south-1", spec(), [
        item("Compute × 3", "t4g.large", "25.00"),
        item("Database", "db.t4g.large", "75.00"),
    ])
    graph = topo.build(spec(), est)
    total = graph.total_monthly

    assert graph.node("database").share_of(total) == pytest.approx(0.75)
    assert graph.node("compute").share_of(total) == pytest.approx(0.25)


def test_share_of_zero_total_does_not_divide_by_zero():
    est = Estimate("aws", "ap-south-1", spec(), [])
    graph = topo.build(spec(), est)
    node = topo.Node(id="x", label="x", kind="compute", monthly_usd=Decimal(0))
    assert node.share_of(graph.total_monthly) == 0.0


def test_unpriced_components_appear_rather_than_vanish():
    """A diagram that silently drops the database we could not price would be
    lying in the most convincing possible format."""
    est = Estimate("gcp", "asia-south1", spec(),
                   [item("Compute × 3", "n2-standard-2", "58.87")],
                   ["database 2vCPU/8GB", "object storage"])
    graph = topo.build(spec(), est)

    database = graph.node("database")
    assert database is not None
    assert database.priced is False
    assert database.monthly_usd == Decimal(0)


def test_client_node_is_always_present():
    est = Estimate("aws", "ap-south-1", spec(), [item("Compute × 3", "t4g.large", "10")])
    graph = topo.build(spec(), est)
    assert graph.node("users") is not None
    assert graph.node("users").monthly_usd == Decimal(0)


def test_edges_form_a_path_from_the_client():
    est = Estimate("aws", "ap-south-1", spec(), [
        item("Compute × 3", "t4g.large", "58.87"),
        item("Database", "db.t4g.large", "121.91"),
        item("Load balancer", "alb", "17.45"),
        item("Egress", "egress:internet", "54.65", "GB"),
    ])
    graph = topo.build(spec(), est)

    assert any(e.source == "users" for e in graph.edges)
    ids = {n.id for n in graph.nodes}
    for edge in graph.edges:
        assert edge.source in ids, f"edge from unknown node {edge.source}"
        assert edge.target in ids, f"edge to unknown node {edge.target}"


def test_no_edge_points_at_a_missing_node():
    """Compute only — nothing should dangle."""
    est = Estimate("aws", "ap-south-1", spec(), [item("Compute × 3", "t4g.large", "10")])
    graph = topo.build(spec(), est)
    ids = {n.id for n in graph.nodes}
    assert all(e.source in ids and e.target in ids for e in graph.edges)


def test_duty_cycle_shows_in_the_node_detail():
    s = spec(compute_duty_cycle=0.6)
    est = Estimate("aws", "ap-south-1", s, [item("Compute × 3", "t4g.large", "35")])
    graph = topo.build(s, est)
    assert "60%" in graph.node("compute").detail


# ── diff ────────────────────────────────────────────────────────────────


@needs_db
def test_an_upgrade_is_one_change_not_a_removal_plus_an_addition():
    """REGRESSION: matching on the raw label reported the Multi-AZ upgrade as
    'Database removed' + 'Database (Multi-AZ) added', hiding the actual event."""
    req = Requirement(goal="shop", workload_type="web", traffic_scale="medium")
    options = {o.label: o for o in recommend(req, "aws")}

    diff = diff_options(options["Balanced"], options["Most reliable"])
    database = next(c for c in diff.changes if c.label == "Database")

    assert database.kind == "changed"
    assert database.delta > 0
    assert not diff.removed


@needs_db
def test_diff_delta_equals_the_difference_in_totals():
    req = Requirement(goal="shop", workload_type="web", traffic_scale="medium")
    options = {o.label: o for o in recommend(req, "aws")}
    a, b = options["Cheapest"], options["Balanced"]

    diff = diff_options(a, b)
    assert diff.delta_monthly == pytest.approx(b.monthly - a.monthly, abs=Decimal("0.01"))


@needs_db
def test_unchanged_lines_are_reported_not_omitted():
    """'Everything else is unchanged' is information the user needs."""
    req = Requirement(goal="shop", workload_type="web", traffic_scale="medium")
    options = {o.label: o for o in recommend(req, "aws")}

    diff = diff_options(options["Balanced"], options["Most reliable"])
    assert diff.unchanged
    assert all(c.delta == 0 for c in diff.unchanged)


def test_line_key_collapses_qualifiers_and_counts():
    from whichcloud.engine import _line_key

    assert _line_key("Database (Multi-AZ)") == "Database"
    assert _line_key("Compute × 3") == "Compute"
    assert _line_key("Compute × 1 (spot) @60%") == "Compute"


# ── trade-offs ──────────────────────────────────────────────────────────


@needs_db
def test_every_shape_states_what_it_gives_up():
    """A cheap option that does not state its cost in reliability is how
    people get burned."""
    req = Requirement(goal="shop", workload_type="web", traffic_scale="medium")
    for option in recommend(req, "aws"):
        assert option.tradeoffs, f"{option.label} declares no trade-offs"


@needs_db
def test_the_cheapest_option_admits_it_is_a_single_instance():
    req = Requirement(goal="shop", workload_type="web", traffic_scale="medium")
    cheapest = recommend(req, "aws")[0]
    assert any("single instance" in t.lower() for t in cheapest.tradeoffs)
