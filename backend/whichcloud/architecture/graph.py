"""An Architecture, turned into something drawable.

The existing `topology.build` is left alone. It serves the priced flow, where
a node *is* a category -- one compute box, one database box -- and its
`by_kind[kind] = node` is exactly right for that. It is also why it can never
draw more than eight boxes: identity is the category, so a second database
overwrites the first.

Here identity is the service. Twenty four services make twenty four nodes,
and `tier` becomes an attribute that says which row a node belongs in rather
than which node it is.

Prices are attached per node where the catalog has one and left absent where
it does not. There is deliberately no total: most services in a real
description are not in the catalog, so any sum would be a small number
wearing the authority of a complete one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal

from whichcloud.architecture.schema import (
    Architecture,
    BoundaryKind,
    Flow,
    Tier,
    normalize_edges,
)

#: Row order on the diagram, top to bottom. Traffic enters at the top and the
#: supporting concerns sit underneath, which is how these diagrams are read.
TIER_ORDER: tuple[Tier, ...] = (
    "edge",
    "api",
    "compute",
    "data",
    "async",
    "analytics",
    "ml",
    "security",
    "cicd",
    "observability",
)

#: Boundaries nest in this order, outermost first, so a region is never drawn
#: inside the subnet it contains.
BOUNDARY_DEPTH: dict[BoundaryKind, int] = {
    "account": 0,
    "region": 1,
    "vpc": 2,
    "az": 3,
    "subnet": 4,
}


def slug(name: str) -> str:
    """A stable id from a service name.

    Stable matters: the id is what edges, groups and the interface all point
    at, so it has to come out the same for the same name every time rather
    than depending on the order things were seen in.
    """
    out = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return out or "node"


@dataclass
class GraphNode:
    id: str
    label: str
    tier: Tier
    purpose: str = ""
    #: Absent rather than zero when the catalog cannot price it. Zero is a
    #: price; this is the absence of one, and the two must not render alike.
    monthly_usd: Decimal | None = None
    sku: str | None = None

    @property
    def priced(self) -> bool:
        return self.monthly_usd is not None


@dataclass
class GraphEdge:
    source: str
    target: str
    flow: Flow


@dataclass
class GraphGroup:
    id: str
    kind: BoundaryKind
    label: str
    node_ids: list[str] = field(default_factory=list)
    child_ids: list[str] = field(default_factory=list)


@dataclass
class ArchitectureGraph:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    groups: list[GraphGroup] = field(default_factory=list)
    external: list[str] = field(default_factory=list)
    regions: int = 1
    azs_per_region: int = 1

    @property
    def priced_count(self) -> int:
        return sum(1 for n in self.nodes if n.priced)

    def tiers(self) -> list[tuple[Tier, list[GraphNode]]]:
        """Nodes grouped into rows, empty tiers omitted."""
        by_tier: dict[Tier, list[GraphNode]] = {}
        for node in self.nodes:
            by_tier.setdefault(node.tier, []).append(node)
        return [(t, by_tier[t]) for t in TIER_ORDER if t in by_tier]


def build_graph(arch: Architecture) -> ArchitectureGraph:
    """Everything the description named, as a graph.

    Nothing is dropped for being unpriceable, and nothing is invented to fill
    a gap. What comes out is the system as described.
    """
    graph = ArchitectureGraph(
        external=list(arch.external),
        regions=max(1, arch.regions),
        azs_per_region=max(1, arch.azs_per_region),
    )

    # ── nodes ──
    # A description can name the same service twice -- two Aurora clusters for
    # different domains. They are different boxes, so the id is suffixed
    # rather than the second one silently replacing the first, which is the
    # bug this whole module exists to avoid.
    by_name: dict[str, str] = {}
    used: set[str] = set()
    for service in arch.services:
        base = slug(service.name)
        node_id = base
        n = 2
        while node_id in used:
            node_id = f"{base}-{n}"
            n += 1
        used.add(node_id)
        by_name.setdefault(service.name, node_id)

        graph.nodes.append(
            GraphNode(
                id=node_id,
                label=service.name,
                tier=service.tier,
                purpose=service.purpose,
            )
        )

    # ── edges ──
    for source, target, flow in normalize_edges(arch):
        if source in by_name and target in by_name:
            graph.edges.append(GraphEdge(by_name[source], by_name[target], flow))

    # ── groups ──
    # Kept outermost first, which is the order they have to be drawn in for a
    # region to contain its subnets rather than sit inside one.
    boundaries = sorted(
        arch.boundaries, key=lambda b: BOUNDARY_DEPTH.get(b.kind, 99)
    )
    group_ids: dict[str, str] = {}
    used_group: set[str] = set()
    for boundary in boundaries:
        base = f"{boundary.kind}-{slug(boundary.name)}"
        gid = base
        n = 2
        while gid in used_group:
            gid = f"{base}-{n}"
            n += 1
        used_group.add(gid)
        group_ids.setdefault(boundary.name, gid)
        graph.groups.append(
            GraphGroup(id=gid, kind=boundary.kind, label=boundary.name)
        )

    # Nodes are assigned innermost first, the reverse of the drawing order. A
    # region and the subnet inside it can both name the same service; the
    # subnet is the specific claim, and letting the region take it first --
    # which is what iterating in drawing order does -- throws that away.
    placed: set[str] = set()
    for boundary, group in reversed(list(zip(boundaries, graph.groups))):
        for member in boundary.contains:
            if member in by_name:
                node_id = by_name[member]
                if node_id not in placed:
                    group.node_ids.append(node_id)
                    placed.add(node_id)
            elif member in group_ids and group_ids[member] != group.id:
                group.child_ids.append(group_ids[member])

    return graph


def attach_prices(graph: ArchitectureGraph, priced: dict[str, tuple[Decimal, str]]) -> None:
    """Put a price on the nodes the catalog can price, and only those.

    `priced` maps node id to (monthly_usd, sku). Nodes absent from it keep a
    price of None, which the interface renders as unpriced rather than free.
    """
    for node in graph.nodes:
        if node.id in priced:
            node.monthly_usd, node.sku = priced[node.id]
