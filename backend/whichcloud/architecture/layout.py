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

from whichcloud.architecture.graph import TIER_ORDER, ArchitectureGraph, GraphNode
from whichcloud.architecture.schema import BoundaryKind, Flow, Tier

# Box and spacing sizes. Widened from 176 after watching real labels truncate:
# "Global Accelerator" became "Global Accelerat…" and a one-line purpose lost
# its last word. Service names in these descriptions run long -- "Aurora
# PostgreSQL Global Database" is typical -- and a diagram whose labels are cut
# off is not one someone can hand to a colleague.
# Proportioned for an icon above a centred label, which is how AWS draws a
# service: the mark carries the identification and the name confirms it. A card
# with a border, a fill and a coloured bar reads as a dashboard tile -- the
# chrome competes with the icon for the attention the icon should have.
NODE_W = 152
NODE_H = 116
# Wide enough to route a line between two columns. At 26 the gap was 26 and
# the clearance 14, so a corridor centred between two boxes sat 13px from each
# -- under the clearance, which made every lane count as blocked and left the
# router with nowhere to go. Gutters are what a diagram uses to breathe and to
# carry its own wiring.
GAP_X = 44
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

# ── component packing ──
#
# AWS's reference architectures group by function -- "Web UI component",
# "Data component" -- rather than by layer, and that is what makes them
# readable: someone looking for how search works finds one box containing all
# of it, instead of tracing a service out of the compute row, down to the data
# row and back up.
#
#: Services per row inside a component. Three keeps a component roughly square,
#: which packs better than a long strip and matches how these are drawn.
COMPONENT_COLS = 3
COMPONENT_PAD = 20
COMPONENT_LABEL_H = 30
COMPONENT_GAP = 44
ROW_GAP_INNER = 30

#: The actor and the gap between it and the cloud boundary.
ACTOR_W = 96
ACTOR_H = 96
ACTOR_GAP = 56
CLOUD_PAD = 26
CLOUD_LABEL_H = 34

#: The canvas wraps to a new row of components past this. Wide enough for
#: three average components side by side; beyond that a reader is scrolling
#: rather than reading.
MAX_CANVAS_W = 1700


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
    #: Position in the request path, or None for links that are not on it.
    #: AWS's reference diagrams number the sequence so a reader can follow it
    #: rather than merely look at it -- the difference between a picture and
    #: an explanation.
    #:
    #: Declared last on purpose: inserted before `points` it silently captured
    #: the routed polyline from the positional call below, leaving every edge
    #: with no geometry and a list where its number should be.
    step: int | None = None


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


def badge_point(
    points: list[tuple[int, int]],
    boxes: list[PlacedNode] | None = None,
    taken: set[tuple[int, int]] | None = None,
) -> tuple[int, int]:
    """Where a step number sits on its arrow.

    Segments are tried longest first, and the first one whose midpoint is
    clear of every box and of every badge already placed wins.

    Two earlier versions of this were wrong in instructive ways. The middle
    index of the polyline lands on a corner -- exactly where lines meet and a
    box usually is. The longest segment alone is better but still crosses
    boxes, because the longest run of a same-row link passes straight over
    whatever sits between its ends. Length is a proxy for room; what is
    actually wanted is room.
    """
    if len(points) < 2:
        return points[0] if points else (0, 0)

    boxes = boxes or []
    taken = taken if taken is not None else set()

    segments = sorted(
        zip(points, points[1:]),
        key=lambda pair: -(abs(pair[0][0] - pair[1][0]) + abs(pair[0][1] - pair[1][1])),
    )

    def clear(x: int, y: int) -> bool:
        if any(b.x - 4 < x < b.x + b.w + 4 and b.y - 4 < y < b.y + b.h + 4 for b in boxes):
            return False
        return all(abs(x - tx) > 24 or abs(y - ty) > 24 for tx, ty in taken)

    for (x1, y1), (x2, y2) in segments:
        # Along the segment rather than only at its centre: a long run blocked
        # in the middle is usually open a third of the way along.
        for fraction in (0.5, 0.35, 0.65, 0.25, 0.75):
            x = int(x1 + (x2 - x1) * fraction)
            y = int(y1 + (y2 - y1) * fraction)
            if clear(x, y):
                return (x, y)

    # Nothing on the line is clear, which happens when a link's whole route
    # runs over boxes. Step sideways off the line rather than sit on a label:
    # a badge beside its arrow is still obviously that arrow's, and a badge on
    # top of a service name obscures the thing the diagram is naming.
    (x1, y1), (x2, y2) = segments[0]
    mid_x, mid_y = (x1 + x2) // 2, (y1 + y2) // 2
    horizontal = y1 == y2
    for offset in (18, -18, 30, -30, 42, -42):
        x = mid_x if horizontal else mid_x + offset
        y = mid_y + offset if horizontal else mid_y
        if clear(x, y):
            return (x, y)
    return (mid_x, mid_y)


@dataclass
class PlacedActor:
    """The people outside the cloud. Every one of these diagrams starts here."""

    label: str
    x: int
    y: int
    w: int
    h: int


@dataclass
class PlacedCloud:
    """The provider boundary everything else sits inside."""

    label: str
    x: int
    y: int
    w: int
    h: int


@dataclass
class PlacedComponent:
    """A functional group's box: "Web UI component", "Data component"."""

    name: str
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
    components: list[PlacedComponent] = field(default_factory=list)
    actor: PlacedActor | None = None
    cloud: PlacedCloud | None = None

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


def _component_size(count: int) -> tuple[int, int, int, int]:
    """(box width, box height, columns, rows) for a component of this size."""
    cols = min(COMPONENT_COLS, max(1, count))
    rows = -(-count // cols)
    inner_w = cols * NODE_W + (cols - 1) * GAP_X
    inner_h = rows * NODE_H + (rows - 1) * ROW_GAP_INNER
    return (
        inner_w + COMPONENT_PAD * 2,
        inner_h + COMPONENT_PAD * 2 + COMPONENT_LABEL_H,
        cols,
        rows,
    )


def _number_the_path(graph: ArchitectureGraph, layout: Layout) -> None:
    """Number the request path, in the order a request travels it.

    Only the synchronous edges are numbered. Numbering all of them -- the
    telemetry, the replication, the deployment pipeline -- puts a badge on
    every line and numbers nothing, because the sequence a reader is trying to
    follow is the one a request takes.

    Walked breadth-first from wherever traffic enters, which is a node with no
    synchronous edge arriving at it. A graph where everything has an incoming
    edge has no entry, so the earliest tier is used instead of giving up.
    """
    sync = [e for e in layout.edges if e.flow == "sync"]
    if not sync:
        return

    outgoing: dict[str, list[PlacedEdge]] = {}
    has_incoming: set[str] = set()
    for edge in sync:
        outgoing.setdefault(edge.source, []).append(edge)
        has_incoming.add(edge.target)

    # Entry points, earliest tier first: traffic arrives at the edge, so that
    # is where the numbering has to start. Ties break left to right.
    order = {n.id: (TIER_ORDER.index(n.tier), n.x) for n in layout.nodes}
    starts = sorted(
        (n.id for n in layout.nodes if n.id not in has_incoming),
        key=lambda i: order[i],
    )
    if not starts:
        starts = [min(layout.nodes, key=lambda n: (n.y, n.x)).id]

    step = 1
    numbered: set[int] = set()
    visited: set[str] = set()

    # Each entry's path is followed to its end before the next one begins.
    # Seeding one queue with every entry interleaves them, so a diagram counts
    # 1 at the CDN, 2 in the identity service and 3 in the build pipeline --
    # three unrelated journeys sharing a numbering, which is worse than none.
    for start in starts:
        if start in visited:
            continue
        queue = [start]
        visited.add(start)
        while queue:
            node_id = queue.pop(0)
            # Left to right, so two branches out of one box are numbered the
            # way they are read rather than the order they were extracted in.
            for edge in sorted(
                outgoing.get(node_id, []),
                key=lambda e: (layout.node(e.target).x if layout.node(e.target) else 0),
            ):
                if id(edge) in numbered:
                    continue
                numbered.add(id(edge))
                edge.step = step
                step += 1
                if edge.target not in visited:
                    visited.add(edge.target)
                    queue.append(edge.target)


def build_layout(graph: ArchitectureGraph) -> Layout:
    """Coordinates for everything in the graph.

    Components are packed left to right and wrapped, in the order the graph
    returns them -- edge-facing first, support last. Inside a component,
    services are laid out in a small grid ordered by tier, so a request still
    reads downward within the group it belongs to.
    """
    components = graph.components()
    if not components:
        return _fit(Layout(width=CANVAS_PAD * 2, height=CANVAS_PAD * 2))

    placed: list[PlacedNode] = []
    boxes: list[PlacedComponent] = []

    x = CANVAS_PAD
    y = CANVAS_PAD
    row_height = 0
    widest = 0

    for name, members in components:
        box_w, box_h, cols, _ = _component_size(len(members))

        # Wrap when this component would run past the canvas, unless it is the
        # first on the row -- one that is wider than the limit still has to go
        # somewhere, and shunting it to an empty row changes nothing.
        if x > CANVAS_PAD and x + box_w > MAX_CANVAS_W:
            x = CANVAS_PAD
            y += row_height + COMPONENT_GAP
            row_height = 0

        boxes.append(PlacedComponent(name=name, x=x, y=y, w=box_w, h=box_h))

        inner_x = x + COMPONENT_PAD
        inner_y = y + COMPONENT_PAD + COMPONENT_LABEL_H
        for index, node in enumerate(members):
            col, row = index % cols, index // cols
            placed.append(
                PlacedNode(
                    id=node.id,
                    label=node.label,
                    tier=node.tier,
                    purpose=node.purpose,
                    priced=node.priced,
                    monthly_usd=float(node.monthly_usd) if node.priced else None,
                    sku=node.sku,
                    x=inner_x + col * (NODE_W + GAP_X),
                    y=inner_y + row * (NODE_H + ROW_GAP_INNER),
                )
            )

        x += box_w + COMPONENT_GAP
        row_height = max(row_height, box_h)
        widest = max(widest, x - COMPONENT_GAP)

    width = widest + CANVAS_PAD
    height = y + row_height + CANVAS_PAD

    layout = Layout(width=width, height=height, nodes=placed, components=boxes)

    # ── edges ──
    for edge in graph.edges:
        source, target = layout.node(edge.source), layout.node(edge.target)
        if source and target:
            layout.edges.append(
                PlacedEdge(
                    source=edge.source,
                    target=edge.target,
                    flow=edge.flow,
                    points=_route(source, target, placed, width),
                )
            )

    # ── boundaries ──
    # Drawn deepest first so an outer region ends up containing the boxes of
    # everything nested in it, not only the nodes it names directly.
    parents = {c: g.id for g in graph.groups for c in g.child_ids}
    drawn: dict[str, tuple[int, int, int, int]] = {}
    for group in sorted(graph.groups, key=lambda g: -_depth_of(g.id, parents)):
        xs: list[int] = []
        ys: list[int] = []
        for node_id in group.node_ids:
            node = layout.node(node_id)
            if node:
                xs += [node.x, node.x + node.w]
                ys += [node.y, node.y + node.h]
        for child in group.child_ids:
            if child in drawn:
                cx, cy, cw, ch = drawn[child]
                xs += [cx, cx + cw]
                ys += [cy, cy + ch]
        if not xs:
            continue

        depth = _depth_of(group.id, parents)
        pad = GROUP_PAD * (depth + 1) + COMPONENT_PAD
        box = (
            min(xs) - pad,
            min(ys) - pad - COMPONENT_LABEL_H,
            max(xs) - min(xs) + pad * 2,
            max(ys) - min(ys) + pad * 2 + COMPONENT_LABEL_H,
        )
        drawn[group.id] = box
        layout.groups.append(
            PlacedGroup(
                id=group.id, kind=group.kind, label=group.label, depth=depth,
                x=box[0], y=box[1], w=box[2], h=box[3],
            )
        )

    layout.groups.sort(key=lambda g: g.depth)
    _number_the_path(graph, layout)

    # ── the provider boundary, and the people outside it ──
    # Every reference architecture is framed this way: users on the outside,
    # everything the provider runs inside a labelled box. Without it a diagram
    # is a pile of services with no edge to the system.
    if layout.nodes:
        extent = [*layout.nodes, *layout.groups, *layout.components]
        left = min(b.x for b in extent)
        top = min(b.y for b in extent)
        right = max(b.x + b.w for b in extent)
        bottom = max(b.y + b.h for b in extent)

        layout.cloud = PlacedCloud(
            label="AWS Cloud",
            x=left - CLOUD_PAD,
            y=top - CLOUD_PAD - CLOUD_LABEL_H,
            w=(right - left) + CLOUD_PAD * 2,
            h=(bottom - top) + CLOUD_PAD * 2 + CLOUD_LABEL_H,
        )
        layout.actor = PlacedActor(
            label="Users",
            x=layout.cloud.x - ACTOR_GAP - ACTOR_W,
            y=layout.cloud.y + (layout.cloud.h - ACTOR_H) // 2,
            w=ACTOR_W,
            h=ACTOR_H,
        )

    return _fit(layout)


def _fit(layout: Layout) -> Layout:
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
    if not layout.nodes and not layout.groups and not layout.components:
        return

    everything = [*layout.nodes, *layout.groups, *layout.components]
    if layout.cloud:
        everything.append(layout.cloud)
    if layout.actor:
        everything.append(layout.actor)
    xs = [b.x for b in everything]
    ys = [b.y for b in everything]
    right = [b.x + b.w for b in everything]
    bottom = [b.y + b.h for b in everything]

    dx = CANVAS_PAD - min(xs)
    dy = CANVAS_PAD - min(ys)

    if dx or dy:
        for node in layout.nodes:
            node.x += dx
            node.y += dy
        for group in layout.groups:
            group.x += dx
            group.y += dy
        for component in layout.components:
            component.x += dx
            component.y += dy
        for box in (layout.cloud, layout.actor):
            if box:
                box.x += dx
                box.y += dy
        for band in layout.bands:
            band.y += dy
        for edge in layout.edges:
            edge.points = [(x + dx, y + dy) for x, y in edge.points]

    layout.width = max(right) + dx + CANVAS_PAD
    layout.height = max(bottom) + dy + CANVAS_PAD
