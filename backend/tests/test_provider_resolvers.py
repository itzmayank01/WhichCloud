"""Each cloud must resolve the requirement into its OWN architecture.

The proof test. Selecting Google Cloud currently renders an AWS architecture
with GCP container names: AWS and GCP emit identical node kind lists, in the
same order, and 20 of 21 labels match. The renderer is drawing faithfully what
the backend hands it, and the backend hands it one architecture with three
sets of names.

These assertions fail while that is true and pass only when the resolvers
genuinely diverge -- for stated reasons, not by adding a cosmetic difference.
"""

from __future__ import annotations

import itertools

import pytest

from whichcloud import engine
from whichcloud.requirements import Requirement

PROVIDERS = ("aws", "gcp", "azure")


def _requirement() -> Requirement:
    return Requirement(
        goal="Retail billing",
        workload_type="web",
        traffic_pattern="steady",
        traffic_scale="high",
        region="india",
        budget_monthly_usd=5000.0,
        storage_gb=500,
        egress_gb=500,
        high_availability=True,
        daily_transactions=8_000,
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


def _kinds(provider: str, tier_index: int = -1) -> list[str]:
    from whichcloud import topology as topo

    option = engine.recommend(_requirement(), provider, dsn=None)[tier_index]
    graph = topo.build(option.spec, option.estimate, option.applied)
    return [n.kind for n in graph.nodes]


@needs_db
@pytest.mark.parametrize("left,right", list(itertools.combinations(PROVIDERS, 2)))
def test_each_cloud_resolves_its_own_node_set(left, right):
    """No two clouds may produce the same architecture.

    They genuinely differ: one Cloud NAT serves a whole GCP region where AWS
    needs a NAT Gateway per zone, Google's global load balancer sits outside
    the region entirely, and Azure's Key Vault covers both secrets and keys
    where AWS has two separate services. An identical node set means the
    resolver never ran -- only the labels changed.
    """
    a, b = _kinds(left), _kinds(right)
    assert a != b, (
        f"{left} and {right} produced identical architectures "
        f"({len(a)} nodes): {a}"
    )


@needs_db
def test_google_buys_one_regional_cloud_nat_not_one_per_zone():
    """T5. Cloud NAT is regional; there is no per-zone variant to buy.

    An AWS NAT Gateway lives in one subnet in one availability zone, so a
    three-zone design buys three. Google's Cloud NAT is a configuration on a
    Cloud Router, one per region per VPC, serving every zone -- quoting three
    invented two resources that cannot be purchased.
    """
    from whichcloud.estimator import estimate

    option = engine.recommend(_requirement(), "gcp", dsn=None)[-1]
    assert option.spec.nat_gateway_count > 1, (
        "fixture no longer spans zones; this test would pass vacuously"
    )
    lines = [
        i for i in estimate(option.spec, "gcp", dsn=None).items
        if "nat" in i.sku.lower() and "gateway" in i.label.lower()
    ]
    assert lines, "GCP estimate has no NAT line at all"
    # The line is billed in gateway-hours, so the count is hours / 730.
    gateways = float(lines[0].quantity) / 730
    assert gateways == 1, (
        f"GCP quoted {gateways:g} Cloud NATs; the region has one"
    )


@needs_db
def test_aws_still_buys_a_nat_gateway_per_zone():
    """The other half: making Cloud NAT regional must not change AWS.

    AWS really does bill a gateway per zone, and a design that paid for one
    would route two zones' egress across a zone boundary -- slower, and
    separately charged.
    """
    from whichcloud.estimator import estimate

    option = engine.recommend(_requirement(), "aws", dsn=None)[-1]
    lines = [
        i for i in estimate(option.spec, "aws", dsn=None).items
        if "nat" in i.sku.lower() and "gateway" in i.label.lower()
    ]
    assert lines
    gateways = float(lines[0].quantity) / 730
    assert gateways == option.spec.nat_gateway_count, (
        f"AWS quoted {gateways:g} NAT gateways for "
        f"{option.spec.nat_gateway_count} zones"
    )
