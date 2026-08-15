"""Turn a priced architecture into a diagram.

The interface needs to draw boxes and arrows, and every box needs to carry its
own cost. That is the thing neither a diagram tool nor a cost tool does — one
draws without prices, the other prices without drawing.

The topology is derived from the **priced estimate**, never from the request.
If a component could not be priced it does not appear as a confident node; it
appears as an unpriced one. A diagram that shows a database we failed to price
would be lying in the most convincing possible format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from .estimator import ArchitectureSpec, Estimate, LineItem

# Which line-item labels map to which node. Labels come from the estimator, so
# this is the one place the two modules agree on vocabulary.
_KIND_BY_PREFIX = {
    "Compute": "compute",
    "Database": "database",
    "Object storage": "storage",
    "Egress": "network",
    "Load balancer": "loadbalancer",
    "Cache": "cache",
    "Monitoring": "monitoring",
}


@dataclass(frozen=True, slots=True)
class Node:
    id: str
    label: str
    kind: str  # client | network | loadbalancer | compute | database | storage
    monthly_usd: Decimal
    sku: str = ""
    detail: str = ""  # "t4g.large × 3"
    priced: bool = True
    optimized_by: tuple[str, ...] = ()  # technique ids that touched this node

    def share_of(self, total: Decimal) -> float:
        """Fraction of the bill. Drives border weight in the diagram —
        the expensive node should look expensive."""
        if not total:
            return 0.0
        return float(self.monthly_usd / total)


@dataclass(frozen=True, slots=True)
class Edge:
    source: str
    target: str
    label: str = ""


@dataclass(slots=True)
class Topology:
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    @property
    def total_monthly(self) -> Decimal:
        return sum((n.monthly_usd for n in self.nodes), Decimal(0))

    def node(self, node_id: str) -> Node | None:
        return next((n for n in self.nodes if n.id == node_id), None)


def _kind_for(item: LineItem) -> str:
    for prefix, kind in _KIND_BY_PREFIX.items():
        if item.label.startswith(prefix):
            return kind
    return "compute"


def _detail_for(item: LineItem, spec: ArchitectureSpec, kind: str) -> str:
    if kind == "compute":
        parts = [item.sku, f"× {spec.compute_count}"]
        if spec.compute_duty_cycle < 1.0:
            parts.append(f"@ {spec.compute_duty_cycle:.0%}")
        return " ".join(parts)
    if kind == "database":
        return item.sku
    if kind in ("storage", "network"):
        return f"{item.quantity:g} GB"
    return item.sku


# Effect keys, mapped to the node they alter. Lets the diagram mark which boxes
# a technique actually touched, rather than listing techniques separately.
_EFFECT_TARGETS = {
    "arch": "compute",
    "use_spot": "compute",
    "compute_duty_cycle": "compute",
    "database_arch": "database",
    "database_multi_az": "database",
}


def build(
    spec: ArchitectureSpec,
    estimate: Estimate,
    applied: tuple = (),
) -> Topology:
    """Nodes and edges for one priced option.

    `applied` is the option's AppliedTechnique tuple; each one is attributed to
    the node its effect changed, so the interface can put a mark on the box
    rather than only in a list underneath.
    """
    topology = Topology()

    # Which node did each technique change?
    touched: dict[str, list[str]] = {}
    for entry in applied:
        for key in entry.technique.effect:
            kind = _EFFECT_TARGETS.get(key)
            if kind:
                touched.setdefault(kind, []).append(entry.technique.id)

    # Everything that was actually priced becomes a node.
    by_kind: dict[str, Node] = {}
    for item in estimate.items:
        kind = _kind_for(item)
        node = Node(
            id=kind,
            label=item.label.split(" ×")[0].split(" (")[0],
            kind=kind,
            monthly_usd=item.monthly_usd,
            sku=item.sku,
            detail=_detail_for(item, spec, kind),
            priced=True,
            optimized_by=tuple(dict.fromkeys(touched.get(kind, ()))),
        )
        by_kind[kind] = node

    # Anything the estimator could not price still belongs on the diagram —
    # drawn as unpriced, never silently omitted.
    for missing in estimate.missing:
        kind = next(
            (k for k in ("database", "storage", "network", "loadbalancer", "compute")
             if k in missing.lower()),
            None,
        )
        if kind and kind not in by_kind:
            by_kind[kind] = Node(
                id=kind,
                label=kind.title(),
                kind=kind,
                monthly_usd=Decimal(0),
                detail=missing,
                priced=False,
            )

    # The client is always present and always free — it anchors the flow.
    topology.nodes.append(
        Node(id="users", label="Users", kind="client", monthly_usd=Decimal(0))
    )
    for kind in ("network", "loadbalancer", "compute", "cache", "database",
                 "storage", "monitoring"):
        if kind in by_kind:
            topology.nodes.append(by_kind[kind])

    # ── edges: request path, then data path ──
    present = set(by_kind)
    entry = (
        "network" if "network" in present
        else "loadbalancer" if "loadbalancer" in present
        else "compute" if "compute" in present
        else None
    )
    if entry:
        topology.edges.append(Edge("users", entry))

    if "network" in present:
        nxt = "loadbalancer" if "loadbalancer" in present else "compute"
        if nxt in present:
            topology.edges.append(Edge("network", nxt))
        if "storage" in present:
            topology.edges.append(Edge("network", "storage", "assets"))
    elif "storage" in present and "compute" in present:
        topology.edges.append(Edge("compute", "storage", "assets"))

    if "loadbalancer" in present and "compute" in present:
        topology.edges.append(Edge("loadbalancer", "compute"))

    if "compute" in present and "cache" in present:
        topology.edges.append(Edge("compute", "cache"))
    if "compute" in present and "database" in present:
        topology.edges.append(Edge("compute", "database"))

    return topology
