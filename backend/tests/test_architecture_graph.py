"""Building a drawable graph out of an extracted architecture."""

from decimal import Decimal

from whichcloud.architecture import Architecture, Boundary, Service
from whichcloud.architecture.graph import attach_prices, build_graph, slug


def svc(name, tier="compute", flow="sync", connects=(), purpose=""):
    return Service(
        name=name, tier=tier, flow=flow, connects_to=list(connects), purpose=purpose
    )


def test_every_service_becomes_its_own_node():
    """The point of the module: identity is the service, not the category.

    The old builder keyed nodes by kind, so a second database overwrote the
    first and no description could ever draw more than eight boxes.
    """
    arch = Architecture(
        services=[
            svc("Aurora PostgreSQL", "data"),
            svc("DynamoDB", "data"),
            svc("ElastiCache Redis", "data"),
            svc("S3", "data"),
        ]
    )
    graph = build_graph(arch)

    assert len(graph.nodes) == 4
    assert len({n.id for n in graph.nodes}) == 4


def test_the_same_service_named_twice_is_two_boxes():
    """Two Aurora clusters for different domains are two things."""
    arch = Architecture(services=[svc("Aurora", "data"), svc("Aurora", "data")])
    ids = [n.id for n in build_graph(arch).nodes]

    assert ids == ["aurora", "aurora-2"]


def test_slug_is_stable_for_the_same_name():
    assert slug("Amazon MSK") == slug("Amazon MSK") == "amazon-msk"
    assert slug("Route 53!") == "route-53"


def test_edges_are_rewritten_to_node_ids():
    arch = Architecture(
        services=[
            svc("Route 53", "edge", connects=["CloudFront"]),
            svc("CloudFront", "edge"),
        ]
    )
    edge = build_graph(arch).edges[0]

    assert (edge.source, edge.target, edge.flow) == ("route-53", "cloudfront", "sync")


def test_tiers_come_back_in_reading_order():
    """Traffic enters at the top; support sits underneath."""
    arch = Architecture(
        services=[
            svc("CloudWatch", "observability"),
            svc("Aurora", "data"),
            svc("Route 53", "edge"),
        ]
    )
    assert [t for t, _ in build_graph(arch).tiers()] == ["edge", "data", "observability"]


def test_a_service_lands_in_the_innermost_boundary_that_claims_it():
    """A region and a subnet can both list the same service. The subnet is
    the specific claim, so drawing it in the region would lose information."""
    arch = Architecture(
        services=[svc("EKS")],
        boundaries=[
            Boundary(kind="region", name="us-east-1", contains=["EKS"]),
            Boundary(kind="subnet", name="private-a", contains=["EKS"]),
        ],
    )
    groups = {g.kind: g.node_ids for g in build_graph(arch).groups}

    assert groups["subnet"] == ["eks"]
    assert groups["region"] == []


def test_nested_boundaries_are_linked_as_children():
    arch = Architecture(
        boundaries=[
            Boundary(kind="region", name="us-east-1", contains=["prod-vpc"]),
            Boundary(kind="vpc", name="prod-vpc"),
        ]
    )
    region = next(g for g in build_graph(arch).groups if g.kind == "region")

    assert region.child_ids == ["vpc-prod-vpc"]


def test_an_unpriced_node_is_absent_not_zero():
    """Zero is a price. These must not render alike."""
    arch = Architecture(services=[svc("MSK", "async"), svc("EKS")])
    graph = build_graph(arch)
    attach_prices(graph, {"eks": (Decimal("120.50"), "t4g.large")})

    eks = next(n for n in graph.nodes if n.id == "eks")
    msk = next(n for n in graph.nodes if n.id == "msk")

    assert eks.priced and eks.monthly_usd == Decimal("120.50")
    assert not msk.priced and msk.monthly_usd is None
    assert graph.priced_count == 1


def test_regions_never_fall_below_one():
    """A description that does not say still describes one region."""
    assert build_graph(Architecture(regions=0)).regions == 1


def test_a_plural_and_its_singular_are_one_node():
    """Descriptions switch between "NAT Gateway" and "NAT Gateways" for one
    thing; both were observed for the same architecture across runs. Two
    boxes for one service is the visible symptom."""
    assert slug("NAT Gateway") == slug("NAT Gateways") == "nat-gateway"
    assert slug("VPC endpoint") == slug("VPC endpoints")


def test_words_ending_in_s_are_not_mangled():
    """Kinesis is not a plural Kinesi."""
    assert slug("Amazon Kinesis") == "amazon-kinesis"
    assert slug("Access Analyzer") == "access-analyzer"
    assert slug("Direct Connect Gateways") == "direct-connect-gateway"
