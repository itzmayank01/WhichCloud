"""Turning a priced option into a drawable AWS architecture."""

from whichcloud.architecture.costed import AWS_SERVICE, PricedNode, architecture_from
from whichcloud.architecture.graph import build_graph
from whichcloud.architecture.layout import build_layout


def nodes(*kinds, price=10.0):
    return [
        PricedNode(kind=k, label=k.title(), monthly_usd=price, sku=f"{k}-sku")
        for k in kinds
    ]


def test_every_priced_category_becomes_a_named_aws_service():
    """"Database, db.t4g.large, $121.91" is a line on a bill. Amazon RDS in a
    private subnet is an architecture."""
    arch, prices = architecture_from(
        nodes("network", "loadbalancer", "compute", "cache", "database"), False
    )
    names = {s.name for s in arch.services}

    assert "Amazon RDS" in names
    assert "Elastic Load Balancing" in names
    assert "Amazon ECS" in names
    assert len(prices) == 5


def test_the_request_path_runs_through_the_load_balancer_not_past_it():
    """A CDN that reaches both the load balancer and compute directly draws
    two request paths where the system has one."""
    arch, _ = architecture_from(nodes("network", "loadbalancer", "compute"), False)
    cdn = next(s for s in arch.services if s.name == "Amazon CloudFront")

    assert cdn.connects_to == ["Elastic Load Balancing"]


def test_without_a_load_balancer_the_cdn_reaches_compute():
    arch, _ = architecture_from(nodes("network", "compute"), False)
    cdn = next(s for s in arch.services if s.name == "Amazon CloudFront")

    assert cdn.connects_to == ["Amazon ECS"]


def test_high_availability_is_drawn_as_two_zones():
    """The standby database in the reliable tier *is* the second zone. Drawing
    one would contradict the price that was quoted for it."""
    ha, _ = architecture_from(nodes("compute", "database"), True)
    single, _ = architecture_from(nodes("compute", "database"), False)

    assert ha.azs_per_region == 2
    assert len([b for b in ha.boundaries if b.kind == "az"]) == 2
    assert single.azs_per_region == 1


def test_databases_are_private_and_load_balancers_public():
    arch, _ = architecture_from(nodes("loadbalancer", "database"), False)
    public = next(b for b in arch.boundaries if b.name.startswith("Public"))
    private = next(b for b in arch.boundaries if b.name.startswith("Private"))

    assert "Elastic Load Balancing" in public.contains
    assert "Amazon RDS" in private.contains


def test_the_result_lays_out_without_losing_anything():
    arch, _ = architecture_from(
        nodes("network", "loadbalancer", "compute", "cache", "database", "storage"),
        True,
    )
    lay = build_layout(build_graph(arch))

    assert len(lay.nodes) == 6
    assert lay.cloud is not None and lay.actor is not None
    for node in lay.nodes:
        assert 0 <= node.x and node.x + node.w <= lay.width


def test_an_unpriced_category_is_drawn_without_a_price():
    """Zero is a price. A category the engine could not cost is not free."""
    unpriced = [PricedNode(kind="database", label="Database", monthly_usd=None, sku=None)]
    arch, prices = architecture_from(unpriced, False)

    assert [s.name for s in arch.services] == ["Amazon RDS"]
    assert prices == {}


def test_the_mapping_covers_every_category_the_catalog_prices():
    """A category with no row here is silently dropped from the drawing."""
    assert set(AWS_SERVICE) == {
        "network", "loadbalancer", "compute", "cache",
        "database", "database_replica", "storage", "monitoring", "waf",
        "audit", "kms", "nat", "tls", "dns", "auth", "backup",
        "streaming", "kafka", "search", "warehouse",
        "threat", "tracing", "posture", "flowlogs",
    }


def test_a_replica_gets_its_own_name_not_the_primarys():
    """Two services sharing a name collide in the name->Service map used to
    resolve edges, and one silently disappears from the drawing while the
    bill still charges for it."""
    name, _, _, _ = AWS_SERVICE["database_replica"]
    assert name != AWS_SERVICE["database"][0]
