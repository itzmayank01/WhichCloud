"""Regression guards for the five defects the audit ranked by impact.

Each of these changed the answer a user would act on, not a rate by a few
percent. They are grouped here rather than scattered because they were found
by one process and share one property: every single one was invisible to the
existing suite, which was green throughout.
"""

from __future__ import annotations

import pytest

from whichcloud import engine, topology
from whichcloud.estimator import ArchitectureSpec, estimate
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


def _kinds(option) -> set[str]:
    return {n.kind for n in topology.build(
        option.spec, option.estimate, option.applied
    ).nodes}


def _tiers(requirement, provider):
    return {o.label: o for o in engine.recommend(requirement, provider, dsn=None)}


# ── 1. a warehouse is never free, and is never a compute box ──────────────


@needs_db
def test_a_data_warehouse_is_never_priced_at_zero():
    """BigQuery sells no provisioned capacity, so the catalog row for it is a
    zero-priced placeholder. Pricing the warehouse tier from it produced a
    $0.00 data warehouse -- and a "Most optimized" that cost LESS than the
    tier below it, having dropped the scan charge and gained nothing
    chargeable in return."""
    spec = ArchitectureSpec(
        name="etl", region="india", compute_count=0,
        warehouse_node_count=4, warehouse_node_vcpu=2, warehouse_node_memory_gb=16.0,
    )
    for provider in ("aws", "gcp", "azure"):
        est = estimate(spec, provider)
        warehouse = [
            i for i in est.items
            if topology._kind_for(i) in ("warehouse", "athena")
        ]
        assert warehouse, f"{provider}: no warehouse line at all"
        assert sum(i.monthly_usd for i in warehouse) > 0, (
            f"{provider}: a data warehouse priced at zero"
        )


@needs_db
def test_the_warehouse_is_drawn_as_a_warehouse_on_every_cloud():
    """Azure's pool fell through to `compute`, so the diagram drew a
    $4,934/month data warehouse as an application server."""
    spec = ArchitectureSpec(
        name="etl", region="india", compute_count=0,
        warehouse_node_count=4, warehouse_node_vcpu=2, warehouse_node_memory_gb=16.0,
    )
    for provider in ("aws", "gcp", "azure"):
        est = estimate(spec, provider)
        kinds = {topology._kind_for(i) for i in est.items}
        assert kinds & {"warehouse", "athena"}, (
            f"{provider}: the warehouse is not drawn as one — kinds were {sorted(kinds)}"
        )
        assert "compute" not in kinds, (
            f"{provider}: something in a warehouse-only architecture is drawn as compute"
        )


@needs_db
def test_azure_buys_one_pool_rather_than_four_of_them():
    """Synapse dedicated SQL is ONE pool sized in data warehouse units. There
    is no such thing as four pools serving one warehouse, and "x 4" described
    a purchase nobody can make."""
    spec = ArchitectureSpec(
        name="etl", region="india", compute_count=0,
        warehouse_node_count=4, warehouse_node_vcpu=2, warehouse_node_memory_gb=16.0,
    )
    labels = [i.label for i in estimate(spec, "azure").items if "Synapse" in i.label]
    assert labels, "no Synapse line"
    assert any("DW400c" in x for x in labels), labels
    assert not any("× 4" in x for x in labels), labels


# ── 2. edge protection follows exposure, not request-serving ──────────────


def _internal_tool() -> Requirement:
    return Requirement(
        goal="Internal HR tool", workload_type="web", audience="internal",
        traffic_scale="low", region="india",
    )


def _public_site() -> Requirement:
    return Requirement(
        goal="Product catalogue", workload_type="web", audience="public",
        traffic_scale="high", region="india", egress_gb=500.0,
    )


def test_serving_requests_is_not_the_same_as_being_on_the_internet():
    assert not _internal_tool().internet_facing
    assert _internal_tool().serves_requests, "an internal tool still serves requests"
    assert _public_site().internet_facing


@needs_db
def test_an_internal_tool_is_not_sold_a_web_firewall():
    """The top tier used to assume an attack surface because it "should".
    Assuming one put $368/month of Azure Application Gateway in front of a
    workload whose attacker is not on the network."""
    for provider in ("aws", "gcp", "azure"):
        for label, option in _tiers(_internal_tool(), provider).items():
            assert "waf" not in _kinds(option), (
                f"{provider}/{label}: a web firewall for eighty internal staff"
            )


# ── 3. every derived role says why it is there ────────────────────────────


@needs_db
def test_no_role_appears_without_a_reason():
    """A role that cannot say why it is present is indistinguishable from a
    default that leaked in. Baseline roles are exempt BY NAME -- the exemption
    list is short on purpose, since anything on it stops having to justify
    its cost."""
    for requirement in (_internal_tool(), _public_site()):
        for provider in ("aws", "gcp", "azure"):
            for label, option in _tiers(requirement, provider).items():
                nodes = topology.build(
                    option.spec, option.estimate, option.applied
                ).nodes
                silent = [
                    n.kind for n in nodes
                    if not n.because and not n.baseline and n.kind != "client"
                ]
                assert not silent, f"{provider}/{label}: {silent} have no reason"


def test_the_baseline_exemption_stays_short():
    """This list is the escape hatch from the rule above. Every name on it is
    a role excused from justifying its cost, so it growing is a regression
    even when nothing else fails."""
    assert len(topology.BASELINE_KINDS) <= 14, sorted(topology.BASELINE_KINDS)
    for earned in ("compute", "database", "cache", "waf", "cdn", "warehouse"):
        assert earned not in topology.BASELINE_KINDS


# ── 4. a public site earns a CDN on readers, not on bytes ─────────────────


@needs_db
def test_a_public_read_heavy_site_gets_a_cdn_under_the_byte_threshold():
    """Five million page views of near-static content is the textbook CDN
    case, and every vendor reference for it puts one in front. It came out at
    500 GB of egress, under the one-terabyte bar, and got none."""
    site = _public_site()
    assert site.egress_gb < 1000, "this test is pointless above the threshold"
    for provider in ("aws", "gcp", "azure"):
        for label, option in _tiers(site, provider).items():
            assert "cdn" in _kinds(option), f"{provider}/{label}: no CDN"


@needs_db
def test_an_internal_tool_still_gets_no_cdn():
    """The other half. A rule that gives everything a CDN has not derived
    anything."""
    for provider in ("aws", "gcp", "azure"):
        for label, option in _tiers(_internal_tool(), provider).items():
            assert "cdn" not in _kinds(option), f"{provider}/{label}: CDN for 80 staff"


@needs_db
def test_a_cdn_and_plain_egress_are_not_the_same_box():
    """They shared the `network` kind, so an architecture WITH an edge cache
    and one without drew the identical node -- and on GCP and Azure that node
    is already named "Cloud CDN" and "Azure Front Door", which put a CDN on
    the picture for workloads that had none."""
    with_cdn = _tiers(_public_site(), "gcp")["Most reliable"]
    without = _tiers(_internal_tool(), "gcp")["Most reliable"]
    assert "cdn" in _kinds(with_cdn)
    assert "cdn" not in _kinds(without)
    assert _kinds(with_cdn) != _kinds(without)


# ── 6. the free allowance every cloud gives, actually applied ─────────────


@needs_db
def test_the_first_hundred_gigabytes_of_egress_are_free():
    """All three clouds give this away, and this billed from the first byte.

    On a large workload the difference is rounding. On an internal tool
    moving 5 GB it was the whole line -- traffic none of the three would have
    charged for. A free allowance nobody applies is the same error as a wrong
    rate; it just looks more defensible.
    """
    from whichcloud.estimator import EGRESS_FREE_TIER_GB

    for provider in ("aws", "gcp", "azure"):
        inside = ArchitectureSpec(
            name="small", region="india", compute_count=1,
            egress_gb=EGRESS_FREE_TIER_GB - 5,
        )
        assert not [
            i for i in estimate(inside, provider).items if i.label == "Egress"
        ], f"{provider}: charged for egress inside the free tier"

        outside = ArchitectureSpec(
            name="big", region="india", compute_count=1,
            egress_gb=EGRESS_FREE_TIER_GB + 400,
        )
        line = next(
            i for i in estimate(outside, provider).items if i.label == "Egress"
        )
        assert float(line.quantity) == 400, (
            f"{provider}: billed {line.quantity} GB, the allowance was not deducted"
        )
