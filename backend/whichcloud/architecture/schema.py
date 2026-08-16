"""The shape of an architecture read out of a description.

Separate from `Requirement` on purpose. A Requirement is what the *pricer*
needs -- a workload class, a traffic tier, a region -- and it deliberately
throws away everything it cannot cost. That is the right shape for producing a
number and the wrong one for producing a picture: a description naming twenty
six services collapses into it and comes out the other side as six.

This is the picture's shape. It keeps every service the description named,
whether or not the catalog can price it, because a diagram that silently omits
what it cannot cost is not a diagram of the system the user described.

Two distinctions were learned by running a real description through a model
rather than assumed up front:

Boundaries are not services. VPCs, subnets, NAT gateways and security groups
came back missing from a service list, and that was correct -- they are the
regions the boxes sit inside, not boxes. They get their own field, and they
are what the diagram's containers are drawn from.

Flow and tier are closed sets. Left as free strings the model fills `flow`
with prose -- "Global DNS resolution and traffic routing" where "sync" was
wanted -- which is unusable for choosing a stroke style. Literal types make
the model pick from the list instead of describing.
"""

from typing import Literal

from pydantic import BaseModel, Field

#: Where a service sits in the request path. Doubles as the diagram's layer
#: order, which is why it is a sequence rather than a set.
Tier = Literal[
    "edge",           # DNS, CDN, DDoS, global routing
    "api",            # gateways, load balancers
    "compute",        # containers, functions, instances
    "data",           # databases, caches, object storage
    "async",          # queues, topics, streams
    "analytics",      # warehouses, lakes, ETL
    "ml",             # training, inference
    "security",       # identity, keys, secrets
    "cicd",           # build, registry, deploy
    "observability",  # metrics, logs, traces
]

#: How one service reaches another. Drives the stroke style, so that a request
#: path and a replication path do not read as the same thing.
Flow = Literal[
    "sync",         # request/response on the critical path
    "async",        # events, queues, fire and forget
    "replication",  # data copied between regions or stores
    "control",      # management, deployment, telemetry
]

BoundaryKind = Literal["account", "region", "az", "vpc", "subnet"]


class Service(BaseModel):
    """One box on the diagram."""

    name: str = Field(description="The service as named, e.g. 'Amazon MSK'")
    tier: Tier
    #: The functional group this belongs to -- "Web UI", "Data", "Delivery".
    #: AWS's own reference architectures are organised this way rather than by
    #: layer, and it is what makes them readable: a reader looking for how
    #: search works finds one box containing the whole of it, instead of
    #: tracing a service out of the compute row, down to the data row and back
    #: up. Tier still decides vertical order inside a component.
    component: str = Field(
        default="",
        description=(
            "Functional grouping, two or three words, e.g. 'Web UI', "
            "'Data', 'Cost reporting', 'Image deployment'. Services that "
            "work together to do one job share a component."
        ),
    )
    connects_to: list[str] = Field(
        default_factory=list,
        description="Names of services this one talks to, as written in `name`",
    )
    flow: Flow = Field(description="How it reaches them")
    purpose: str = Field(
        default="",
        description="What it does here, in one short phrase, from the description only",
    )


class Boundary(BaseModel):
    """A region, VPC or subnet: something the boxes sit inside."""

    kind: BoundaryKind
    name: str
    contains: list[str] = Field(
        default_factory=list,
        description="Names of services or nested boundaries inside this one",
    )


class Architecture(BaseModel):
    """Everything the description said, before anything is priced."""

    services: list[Service] = Field(default_factory=list)
    boundaries: list[Boundary] = Field(default_factory=list)
    regions: int = Field(default=1, description="How many regions, as a number")
    azs_per_region: int = Field(default=1)
    #: Anything named that is not a cloud service -- GitHub Actions, a payment
    #: gateway. Recorded rather than dropped, because they are real parts of
    #: the system and belong on the diagram as external boxes.
    external: list[str] = Field(default_factory=list)


def normalize_edges(arch: Architecture) -> list[tuple[str, str, str]]:
    """Directed, de-duplicated edges.

    Models describe a link from both ends -- Route 53 lists CloudFront and
    CloudFront lists Route 53 -- which draws every arrow twice, once in each
    direction. Keeping the first direction seen is not arbitrary: services are
    emitted roughly in request order, so the earlier mention is the one
    pointing downstream.
    """
    known = {s.name for s in arch.services}
    seen: set[frozenset[str]] = set()
    edges: list[tuple[str, str, str]] = []

    for service in arch.services:
        for target in service.connects_to:
            if target not in known or target == service.name:
                continue  # a name we cannot resolve is not an edge
            pair = frozenset((service.name, target))
            if pair in seen:
                continue
            seen.add(pair)
            edges.append((service.name, target, service.flow))

    return edges
