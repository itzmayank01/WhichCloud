"""Placing an architecture graph on a canvas.

The existing diagram is authored: a fixed 1180x560 with coordinates written by
hand, which is why it can only draw the eight boxes someone sat down and
placed. Twenty three services cannot be hand-placed, and forty certainly
cannot, so the positions have to be computed.

The approach is the standard layered one. Nodes are assigned to rows by tier,
ordered within each row to pull connected boxes near each other, and the
canvas is then sized to whatever that produced rather than the other way
round. It is a small Sugiyama without the cycle-removal step, which is not
needed here because tiers already impose a direction: edges run down the page
from edge services to data and support.

Everything is deterministic. The same graph must produce the same coordinates
every time, or the diagram reshuffles under a user who only reloaded the page
-- which is the same failure the extraction cache exists to prevent, one layer
further on. That is why ordering uses stable sorts throughout and never
iterates a set.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from whichcloud.architecture.graph import ArchitectureGraph, GraphNode
from whichcloud.architecture.schema import BoundaryKind, Flow, Tier

# Box and spacing sizes. Widened from 176 after watching real labels truncate:
# "Global Accelerator" became "Global Accelerat…" and a one-line purpose lost
# its last word. Service names in these descriptions run long -- "Aurora
# PostgreSQL Global Database" is typical -- and a diagram whose labels are cut
# off is not one someone can hand to a colleague.
NODE_W = 212
NODE_H = 84
# Wide enough to route a line between two columns. At 26 the gap was 26 and
# the clearance 14, so a corridor centred between two boxes sat 13px from each
# -- under the clearance, which made every lane count as blocked and left the
# router with nowhere to go. Gutters are what a diagram uses to breathe and to
# carry its own wiring.
GAP_X = 48
ROW_GAP = 104

#: Beyond this a row is wrapped rather than allowed to run off the canvas.
#: Eight security services in one row would otherwise force the whole diagram
#: to scale down until nothing else could be read.
MAX_PER_ROW = 6

#: Space between a group's edge and the boxes inside it, per level of nesting,
#: so a region does not sit flush against the VPC drawn inside it.
GROUP_PAD = 22
CANVAS_PAD = 56

#: Room above each row of boxes for the tier's label.
BAND_LABEL_H = 22


@dataclass
class PlacedNode:
    id: str
    label: str
    tier: Tier
    purpose: str
    priced: bool
    monthly_usd: float | None
    sku: str | None
    x: int
    y: int
    w: int = NODE_W
    h: int = NODE_H

    @property
    def cx(self) -> int:
        return self.x + self.w // 2

    @property
    def cy(self) -> int:
        return self.y + self.h // 2


@dataclass
class PlacedEdge:
    source: str
    target: str
    flow: Flow
    #: Polyline, already routed. The interface draws it rather than working
    #: out where an arrow should meet a box.
    points: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class PlacedGroup:
    id: str
    kind: BoundaryKind
    label: str
    depth: int
    x: int
    y: int
    w: int
    h: int


@dataclass
class Band:
    """A tier's horizontal lane, so the eye can find "the data layer"."""

    tier: Tier
    y: int
    h: int


@dataclass
class Layout:
    width: int
    height: int
    nodes: list[PlacedNode] = field(default_factory=list)
    edges: list[PlacedEdge] = field(default_factory=list)
    groups: list[PlacedGroup] = field(default_factory=list)
    bands: list[Band] = field(default_factory=list)

    def node(self, node_id: str) -> PlacedNode | None:
        for n in self.nodes:
            if n.id == node_id:
                return n
        return None


def _wrap(nodes: list[GraphNode]) -> list[list[GraphNode]]:
    """Split one tier into rows no wider than MAX_PER_ROW.

    Split evenly rather than filling the first row and leaving a remainder:
    six then two reads as a mistake, four and four reads as a decision.
    """
    if len(nodes) <= MAX_PER_ROW:
        return [nodes]
    rows = -(-len(nodes) // MAX_PER_ROW)  # ceiling division
    per = -(-len(nodes) // rows)
    return [nodes[i : i + per] for i in range(0, len(nodes), per)]


def _order_rows(
    rows: list[list[GraphNode]], graph: ArchitectureGraph
) -> list[list[GraphNode]]:
    """Pull connected boxes towards each other, row by row.

    Each row is sorted by the average position of its neighbours in the row
    above -- the barycentre heuristic. It does not minimise crossings, but it
    removes most of them for a fraction of the work of doing it properly, and
    on a diagram this size the difference is not visible.

    Nodes with no neighbour above keep their position: `sorted` is stable, so
    giving them their current index as a key leaves them where they were
    instead of collecting them all at one end.
    """
    neighbours: dict[str, list[str]] = {}
    for edge in graph.edges:
        neighbours.setdefault(edge.target, []).append(edge.source)
        neighbours.setdefault(edge.source, []).append(edge.target)

    ordered: list[list[GraphNode]] = []
    for row_index, row in enumerate(rows):
        if row_index == 0:
            ordered.append(list(row))
            continue

        above = {n.id: i for i, n in enumerate(ordered[row_index - 1])}
        scale = len(row) / max(1, len(above))

        def key(item: tuple[int, GraphNode]) -> float:
            index, node = item
            positions = [above[n] for n in neighbours.get(node.id, []) if n in above]
            if not positions:
                return float(index)
            return (sum(positions) / len(positions)) * scale

        ordered.append([n for _, n in sorted(enumerate(row), key=key)])

    return ordered


#: How close a line may pass to a box it is not connected to.
CLEARANCE = 12


def _blocked(x: int, y1: int, y2: int, boxes: list[PlacedNode], skip: set[str]) -> bool:
    """Does a vertical run at x, between y1 and y2, cross any box?"""
    top, bottom = (y1, y2) if y1 <= y2 else (y2, y1)
    for box in boxes:
        if box.id in skip:
            continue
        if box.x - CLEARANCE < x < box.x + box.w + CLEARANCE:
            if box.y - CLEARANCE < bottom and box.y + box.h + CLEARANCE > top:
                return True
    return False


def _clear_elbow(
    source: PlacedNode, target: PlacedNode, boxes: list[PlacedNode], mid: int
) -> bool:
    """Does the plain elbow cross anything?

    An elbow has two vertical runs, not one: down the source's column to the
    midline, then down the target's column from it. Checking a single lane
    across the whole span -- which is what an earlier version did -- passes
    routes whose second leg goes straight through a box, and measured 23
    crossings on a real diagram while reporting none.
    """
    skip = {source.id, target.id}
    return not (
        _blocked(source.cx, source.y + source.h, mid, boxes, skip)
        or _blocked(target.cx, mid, target.y, boxes, skip)
    )


def _free_lane(
    source: PlacedNode,
    target: PlacedNode,
    boxes: list[PlacedNode],
    canvas_w: int,
    top: int,
    bottom: int,
) -> int | None:
    """The clear vertical corridor nearest the source, anywhere on the canvas.

    An earlier version searched only a few hundred pixels either side of the
    source and gave up, which on a tall diagram is the wrong place to look:
    rows hold different numbers of boxes and are centred, so a gap in one row
    sits behind a box in the next, and the only corridor running the whole
    height is often the page margin. Failing to find one meant falling back to
    a route that goes straight through whatever is in the way.

    Scanning the full width costs a few thousand comparisons per edge, which
    is nothing against drawing a line through a box someone is trying to read.
    """
    skip = {source.id, target.id}
    best: int | None = None
    best_distance = 10**9

    for lane in range(10, max(11, canvas_w - 10), 8):
        distance = abs(lane - source.cx)
        if distance >= best_distance:
            continue
        if not _blocked(lane, top, bottom, boxes, skip):
            best, best_distance = lane, distance

    return best


def _route(
    source: PlacedNode,
    target: PlacedNode,
    boxes: list[PlacedNode] | None = None,
    canvas_w: int = 0,
) -> list[tuple[int, int]]:
    """Where the arrow actually goes.

    Down the page is the common case and gets an elbow rather than a diagonal,
    because a diagonal across three rows crosses everything between them. A
    link within one row leaves from the side instead, which is what keeps a
    replication arrow between two databases from being drawn through them.

    When the elbow would pass through a box that is neither end, the line
    steps sideways into a clear corridor first. Boxes are what a reader is
    trying to read; a line through one costs more than the detour does.
    """
    boxes = boxes or []

    if target.y > source.y + source.h:          # target is below
        mid = (source.y + source.h + target.y) // 2
        if _clear_elbow(source, target, boxes, mid):
            return [
                (source.cx, source.y + source.h),
                (source.cx, mid),
                (target.cx, mid),
                (target.cx, target.y),
            ]

        # Step out of the source, run down a clear corridor, step back in.
        # The stubs are short, so they stay inside the gap below the box they
        # leave and above the one they meet.
        out_y = source.y + source.h + 16
        in_y = target.y - 16
        lane = _free_lane(source, target, boxes, canvas_w, out_y, in_y)
        if lane is None:
            return [
                (source.cx, source.y + source.h),
                (source.cx, mid),
                (target.cx, mid),
                (target.cx, target.y),
            ]
        return [
            (source.cx, source.y + source.h),
            (source.cx, out_y),
            (lane, out_y),
            (lane, in_y),
            (target.cx, in_y),
            (target.cx, target.y),
        ]

    if target.y + target.h < source.y:          # target is above
        # Same treatment as downward. Leaving this branch naive is what left
        # thirteen lines running through boxes while the downward ones were
        # clean: an edge from the security row back up to compute crosses
        # every row between, and half a diagram's edges point upward.
        mid = (target.y + target.h + source.y) // 2
        skip = {source.id, target.id}
        clear = not (
            _blocked(source.cx, mid, source.y, boxes, skip)
            or _blocked(target.cx, target.y + target.h, mid, boxes, skip)
        )
        if clear:
            return [
                (source.cx, source.y),
                (source.cx, mid),
                (target.cx, mid),
                (target.cx, target.y + target.h),
            ]

        out_y = source.y - 16
        in_y = target.y + target.h + 16
        lane = _free_lane(source, target, boxes, canvas_w, in_y, out_y)
        if lane is None:
            return [
                (source.cx, source.y),
                (source.cx, mid),
                (target.cx, mid),
                (target.cx, target.y + target.h),
            ]
        return [
            (source.cx, source.y),
            (source.cx, out_y),
            (lane, out_y),
            (lane, in_y),
            (target.cx, in_y),
            (target.cx, target.y + target.h),
        ]

    # same row: leave from the facing sides
    if target.x >= source.x:
        return [(source.x + source.w, source.cy), (target.x, target.cy)]
    return [(source.x, source.cy), (target.x + target.w, target.cy)]


def _depth_of(group_id: str, parents: dict[str, str]) -> int:
    depth, seen = 0, set()
    current = group_id
    while current in parents and current not in seen:
        seen.add(current)          # a malformed cycle must not hang the layout
        current = parents[current]
        depth += 1
    return depth


def build_layout(graph: ArchitectureGraph) -> Layout:
    """Coordinates for everything in the graph."""
    rows: list[list[GraphNode]] = []
    band_of_row: list[Tier] = []
    for tier, nodes in graph.tiers():
        for row in _wrap(nodes):
            rows.append(row)
            band_of_row.append(tier)

    rows = _order_rows(rows, graph)

    widest = max((len(r) for r in rows), default=1)
    content_w = widest * NODE_W + (widest - 1) * GAP_X
    width = content_w + CANVAS_PAD * 2

    # ── place ──
    placed: list[PlacedNode] = []
    bands: list[Band] = []
    y = CANVAS_PAD
    for row, tier in zip(rows, band_of_row):
        row_w = len(row) * NODE_W + (len(row) - 1) * GAP_X
        x = (width - row_w) // 2       # rows are centred, so the diagram has an axis
        top = y + BAND_LABEL_H

        if not bands or bands[-1].tier != tier:
            bands.append(Band(tier=tier, y=y, h=BAND_LABEL_H + NODE_H))
        else:
            bands[-1].h = top + NODE_H - bands[-1].y

        for node in row:
            placed.append(
                PlacedNode(
                    id=node.id,
                    label=node.label,
                    tier=node.tier,
                    purpose=node.purpose,
                    priced=node.priced,
                    monthly_usd=float(node.monthly_usd) if node.priced else None,
                    sku=node.sku,
                    x=x,
                    y=top,
                )
            )
            x += NODE_W + GAP_X
        y = top + NODE_H + ROW_GAP

    height = (y - ROW_GAP) + CANVAS_PAD
    layout = Layout(width=width, height=height, nodes=placed, bands=bands)

    # ── edges ──
    for edge in graph.edges:
        source, target = layout.node(edge.source), layout.node(edge.target)
        if source and target:
            layout.edges.append(
                PlacedEdge(
                    edge.source,
                    edge.target,
                    edge.flow,
                    _route(source, target, placed, width),
                )
            )

    # ── groups ──
    # A group's box is the extent of what it holds. Drawn deepest first so an
    # outer region ends up containing the boxes of everything nested in it,
    # rather than only the nodes it names directly.
    parents = {
        child: group.id for group in graph.groups for child in group.child_ids
    }
    boxes: dict[str, tuple[int, int, int, int]] = {}
    for group in sorted(
        graph.groups, key=lambda g: -_depth_of(g.id, parents)
    ):
        xs: list[int] = []
        ys: list[int] = []
        for node_id in group.node_ids:
            node = layout.node(node_id)
            if node:
                xs += [node.x, node.x + node.w]
                ys += [node.y, node.y + node.h]
        for child in group.child_ids:
            if child in boxes:
                cx, cy, cw, ch = boxes[child]
                xs += [cx, cx + cw]
                ys += [cy, cy + ch]
        if not xs:
            continue  # a boundary holding nothing placeable is not drawn

        depth = _depth_of(group.id, parents)
        pad = GROUP_PAD * (depth + 1)
        box = (
            min(xs) - pad,
            min(ys) - pad - BAND_LABEL_H,
            max(xs) - min(xs) + pad * 2,
            max(ys) - min(ys) + pad * 2 + BAND_LABEL_H,
        )
        boxes[group.id] = box
        layout.groups.append(
            PlacedGroup(
                id=group.id,
                kind=group.kind,
                label=group.label,
                depth=depth,
                x=box[0],
                y=box[1],
                w=box[2],
                h=box[3],
            )
        )

    # Outermost first, so the interface can paint them in order and have the
    # nested ones land on top.
    layout.groups.sort(key=lambda g: g.depth)

    _fit_canvas(layout)
    return layout


def _fit_canvas(layout: Layout) -> None:
    """Grow the canvas around the groups and shift everything back inside.

    The canvas is sized from the nodes, but a group is drawn *around* nodes
    and each level of nesting adds padding, so an outer region reaches further
    than anything it contains. Three levels of nesting put the account box at
    x=-76 on a 1298-wide canvas -- off the left edge, and clipped by any
    viewport that trusts the stated width.

    Rather than guess the overhang in advance, which depends on how deeply the
    description happens to nest, measure what was produced and translate.
    """
    if not layout.nodes and not layout.groups:
        return

    xs = [n.x for n in layout.nodes] + [g.x for g in layout.groups]
    ys = [n.y for n in layout.nodes] + [g.y for g in layout.groups]
    right = [n.x + n.w for n in layout.nodes] + [g.x + g.w for g in layout.groups]
    bottom = [n.y + n.h for n in layout.nodes] + [g.y + g.h for g in layout.groups]

    dx = CANVAS_PAD - min(xs)
    dy = CANVAS_PAD - min(ys)

    if dx or dy:
        for node in layout.nodes:
            node.x += dx
            node.y += dy
        for group in layout.groups:
            group.x += dx
            group.y += dy
        for band in layout.bands:
            band.y += dy
        for edge in layout.edges:
            edge.points = [(x + dx, y + dy) for x, y in edge.points]

    layout.width = max(right) + dx + CANVAS_PAD
    layout.height = max(bottom) + dy + CANVAS_PAD
