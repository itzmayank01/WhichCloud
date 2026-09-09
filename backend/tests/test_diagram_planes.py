"""The diagram is a graph, not a pile of boxes.

THE DISCONNECTED BOTTOM ROW WAS NEVER A LAYOUT BUG. On a hospital tier-2,
eleven of nineteen nodes had no edge at all. No amount of elkjs tuning
fixes that, because the graph handed to the layout genuinely had no edges
for those nodes — three different kinds of thing were being drawn as one
kind:

    DATA     a request FLOWS through a load balancer to compute
    CONTROL  KMS does not flow anywhere; it is ATTACHED to the database
             whose volumes it encrypts
    ACCOUNT  CloudTrail attaches to nothing, because it records every API
             call in the account — any edge from it is invented

Fixing the model took the orphan count from 11 to 0 across all 39 tiers
of all 14 fixtures. These hold that, and the two bugs the split exposed.
"""

from __future__ import annotations

import pytest

from whichcloud import topology as topo
from whichcloud.archetypes import GRAPHS
from whichcloud.constraints import Constraints
from whichcloud.plan import plan_from
from whichcloud.pricing.store import stats

pytestmark = pytest.mark.skipif(
    sum(r["n"] for r in stats()) == 0, reason="needs an ingested price catalog"
)


def _web_plan():
    return plan_from(
        Constraints(
            country="IN", sector="healthcare", availability="high",
            durability="high", users=450, requests_per_day=6000,
            storage_gb=200, egress_gb=100, public_facing=True,
        ),
        "a hospital records system", archetype="web_app",
    )


def _graph(tier, archetype):
    return topo.build(tier.spec, tier.estimate, archetype=archetype)


# ── the plane model ──────────────────────────────────────────────────


def test_the_three_planes_are_distinct_and_closed():
    assert topo.PLANES == ("data", "control", "account")


def test_a_key_is_control_and_an_audit_trail_is_account():
    """The distinction the whole fix rests on. A key belongs to one
    database; an audit trail belongs to the account."""
    assert topo.plane_for("kms") == topo.CONTROL_PLANE
    assert topo.plane_for("secrets") == topo.CONTROL_PLANE
    assert topo.plane_for("audit") == topo.ACCOUNT_PLANE
    assert topo.plane_for("threat") == topo.ACCOUNT_PLANE
    # And a request-path service is data, which is the default.
    assert topo.plane_for("compute") == topo.DATA_PLANE
    assert topo.plane_for("anything-new") == topo.DATA_PLANE


def test_no_data_plane_node_is_left_unreachable():
    """11 of 19 before. An unconnected data-plane node is a service
    nobody can see the purpose of."""
    plan = _web_plan()
    for tier in plan.tiers:
        graph = _graph(tier, plan.archetype)
        linked = {e.source for e in graph.edges} | {e.target for e in graph.edges}
        orphans = [
            n.id for n in graph.nodes
            if n.plane == topo.DATA_PLANE and n.id not in linked
        ]
        assert not orphans, f"{tier.name}: {orphans}"


def test_control_plane_services_attach_to_a_real_subject():
    """A key attaches to the store it encrypts, not to whatever happened
    to be on the canvas. A control service whose subject is absent
    attaches to NOTHING rather than to something arbitrary."""
    plan = _web_plan()
    graph = _graph(plan.tiers[1], plan.archetype)
    node_ids = {n.id for n in graph.nodes}
    attachments = [e for e in graph.edges if e.kind == "attaches"]
    assert attachments
    for edge in attachments:
        assert edge.source in node_ids
        assert edge.target in node_ids
        # A binding says what it does. An unlabelled one is just a line.
        assert edge.label


def test_kms_attaches_to_the_store_not_to_the_compute():
    """A key encrypts data at rest. Attaching it to whatever calls it
    would draw the wrong relationship."""
    plan = _web_plan()
    graph = _graph(plan.tiers[1], plan.archetype)
    kms = [e for e in graph.edges if e.source == "kms"]
    assert kms
    assert kms[0].target in ("database", "dynamodb", "storage", "search",
                             "block_storage")


def test_account_plane_nodes_have_no_edges_at_all():
    """CloudTrail does not talk to the database. Any edge from it would
    be an invented relationship, and the old graph avoided that by
    leaving it unconnected — which read as an omission rather than as
    the truth."""
    plan = _web_plan()
    for tier in plan.tiers:
        graph = _graph(tier, plan.archetype)
        account = {n.id for n in graph.nodes if n.plane == topo.ACCOUNT_PLANE}
        assert account, "expected some account-plane services"
        touched = {e.source for e in graph.edges} | {e.target for e in graph.edges}
        assert not (account & touched)


# ── the two bugs the split exposed ───────────────────────────────────


def test_every_priced_kind_gets_a_node():
    """topology.py has warned since a previous session that "serverless
    and messaging services silently vanished from the diagram while
    still appearing on the bill". The mechanism meant to prevent it was
    a hand-maintained tuple that decided MEMBERSHIP as well as order --
    so nine kinds added afterwards were priced and never drawn."""
    plan = _web_plan()
    for tier in plan.tiers:
        graph = _graph(tier, plan.archetype)
        drawn = {n.id for n in graph.nodes}
        priced = {topo._kind_for(i) for i in tier.estimate.items} - {"client"}
        assert not (priced - drawn), f"{tier.name}: {sorted(priced - drawn)}"


def test_no_edge_points_at_a_node_that_does_not_exist():
    plan = _web_plan()
    for tier in plan.tiers:
        graph = _graph(tier, plan.archetype)
        ids = {n.id for n in graph.nodes}
        for edge in graph.edges:
            assert edge.source in ids, edge
            assert edge.target in ids, edge


# ── every archetype declares its own path ────────────────────────────


@pytest.mark.parametrize("name", sorted(GRAPHS))
def test_every_archetype_declares_a_request_path(name):
    """The builder knew exactly one path -- users -> DNS -> WAF -> load
    balancer -> compute -> database. Running the other six through it
    left their real services floating: an event pipeline's API Gateway,
    queue, consumers and email are none of those things."""
    assert GRAPHS[name].flow, f"{name} declares no data-plane flow"


@pytest.mark.parametrize("name", sorted(GRAPHS))
def test_a_declared_flow_only_names_kinds_that_can_exist(name):
    """A flow naming a kind nothing produces is an edge that can never
    be drawn -- dead data that looks like coverage."""
    known = set(topo._KIND_BY_PREFIX.values()) | {"users", "compute", "client"}
    for source, target, _label in GRAPHS[name].flow:
        assert source in known, f"{name}: unknown source {source!r}"
        assert target in known, f"{name}: unknown target {target!r}"


def test_a_shape_with_no_requester_gets_no_requester_box():
    """A nightly batch job has no user in its request path — a schedule
    starts it. Drawing a Users box anyway and leaving it unconnected says
    the diagram is unfinished; removing it says the truth."""
    plan = plan_from(
        Constraints(
            sector="other", storage_gb=500.0, active_hours_per_day=2.0,
            interruptible=True, availability="low", durability="normal",
        ),
        "a nightly etl", archetype="batch_etl",
    )
    graph = _graph(plan.tiers[0], "batch_etl")
    assert "users" not in {n.id for n in graph.nodes}


def test_a_shape_with_a_requester_keeps_one():
    plan = plan_from(
        Constraints(
            sector="fintech", requests_per_day=40000, peak_shape="spiky",
            availability="high", durability="high", emails_per_month=1_200_000,
        ),
        "payment webhooks", archetype="event_driven",
    )
    graph = _graph(plan.tiers[0], "event_driven")
    assert "users" in {n.id for n in graph.nodes}
