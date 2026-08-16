"""The parts of architecture reading that do not need a model."""

import pytest
from pydantic import ValidationError

from whichcloud.architecture import Architecture, Boundary, Service, normalize_edges


def svc(name, tier="compute", flow="sync", connects=()):
    return Service(name=name, tier=tier, flow=flow, connects_to=list(connects))


def test_flow_and_tier_are_closed_sets():
    """Left open, a model fills flow with prose instead of choosing.

    This is not hypothetical -- a free-string schema returned "Global DNS
    resolution and traffic routing" where a stroke style was needed.
    """
    with pytest.raises(ValidationError):
        Service(name="Route 53", tier="edge", flow="Global DNS resolution")
    with pytest.raises(ValidationError):
        Service(name="Route 53", tier="networking-layer", flow="sync")


def test_reciprocal_mentions_draw_one_edge():
    """Models name a link from both ends; the diagram needs it once."""
    arch = Architecture(
        services=[
            svc("Route 53", "edge", connects=["CloudFront"]),
            svc("CloudFront", "edge", connects=["Route 53"]),
        ]
    )
    edges = normalize_edges(arch)

    assert len(edges) == 1
    # The earlier mention points downstream: services arrive in request order.
    assert edges[0][:2] == ("Route 53", "CloudFront")


def test_edges_to_unknown_services_are_dropped():
    """A name that resolves to no box cannot be drawn as an arrow to one."""
    arch = Architecture(services=[svc("EKS", connects=["Aurora", "Nonexistent"])])
    assert normalize_edges(arch) == []


def test_self_reference_is_not_an_edge():
    arch = Architecture(services=[svc("EKS", connects=["EKS"])])
    assert normalize_edges(arch) == []


def test_flow_is_carried_onto_the_edge():
    """Replication and request paths must not render identically."""
    arch = Architecture(
        services=[
            svc("Aurora", "data", flow="replication", connects=["Aurora Replica"]),
            svc("Aurora Replica", "data"),
        ]
    )
    assert normalize_edges(arch)[0][2] == "replication"


def test_boundaries_are_not_services():
    """A VPC contains boxes; it is not one. Keeping them apart is what lets
    the diagram draw containers rather than a stray node."""
    arch = Architecture(
        services=[svc("EKS")],
        boundaries=[Boundary(kind="vpc", name="prod-vpc", contains=["EKS"])],
    )
    assert [s.name for s in arch.services] == ["EKS"]
    assert arch.boundaries[0].contains == ["EKS"]


def test_an_empty_description_yields_an_empty_architecture():
    """Defaults must not invent a single-region system out of nothing."""
    arch = Architecture()
    assert arch.services == [] and arch.boundaries == []
    assert normalize_edges(arch) == []
