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
from functools import partial

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
#:
#: This was 5, chosen when the canvas was scaled to fit its container **on
#: width alone** -- under that rule narrow-and-tall was free, because height
#: never entered the calculation. It produced a 1252x1328 canvas: portrait,
#: for a workspace whose canvas area is landscape.
#:
#: The renderer now fits both axes, so height is usually the binding
#: constraint and that trade inverts -- a portrait diagram in a landscape
#: frame wastes the width it has and gets scaled down to fit the height it
#: does not. Eight per row is wider and considerably shorter, which lands
#: much closer to the aspect ratio of the frame it is drawn in and so
#: renders LARGER, not smaller.
MAX_PER_ROW = 8

#: Space between a group's edge and the boxes inside it, per level of nesting,
#: so a region does not sit flush against the VPC drawn inside it.
GROUP_PAD = 22
CANVAS_PAD = 56
BOX_PAD = 18
BOX_LABEL_H = 30
BOX_GAP = 22

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

#: A component narrower than this looks like an accident. Two services side by
#: side is a reasonable minimum and keeps a row of mixed-size components from
#: having one thin sliver beside three wide boxes.
MIN_COMPONENT_W = 2 * NODE_W + GAP_X + COMPONENT_PAD * 2

#: An availability zone drawn as a column should never be narrower than two
#: nodes. A single-service AZ produces a tall thin strip that looks wrong
#: next to a populated one and wastes vertical space.
MIN_AZ_W = 2 * NODE_W + GAP_X + BOX_PAD * 2

#: The source id on the arrow from the actor. It is not a node -- there is no
#: box for the people -- so anything walking edges has to know to skip it.
ACTOR_SOURCE = "__users__"

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
    #: The arrow from the people into the system. Kept out of `edges` because
    #: it has no source node: putting it there meant everything walking edges
    #: -- numbering, routing, every test indexing edges[0] -- had to know
    #: about a source that is not a box.
    actor_edge: PlacedEdge | None = None

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


#: Vertical separation between two arrows sharing a horizontal channel.
#: Wide enough to read as two lines at full size, tight enough that a
#: fanned bundle still reads as one group heading the same way.
CHANNEL_GAP = 11


def separate_channels(edges: list[PlacedEdge]) -> None:
    """Fan apart arrows that would be drawn on top of each other.

    Every elbow puts its horizontal run halfway between the two rows it
    joins, so edges leaving the same row for the same row all landed on
    one Y -- eight of them on a single line in a full architecture. Drawn,
    that is one thick arrow with several heads, and no reader can tell
    which service it came from.

    Each edge in a colliding group is moved to its own channel, spread
    around the original line so the bundle stays centred where it was.
    Only the interior horizontal run moves; the stubs that meet the boxes
    stay put, so every arrow still leaves and arrives where it did.
    """
    interior: dict[int, list[tuple[PlacedEdge, int]]] = {}
    for edge in edges:
        # The first and last segments anchor to a box; anything between is
        # free to move.
        for i in range(1, len(edge.points) - 2):
            (x1, y1), (x2, y2) = edge.points[i], edge.points[i + 1]
            if y1 == y2 and x1 != x2:
                interior.setdefault(y1, []).append((edge, i))

    for y, members in interior.items():
        if len(members) < 2:
            continue
        # Order by where the arrow starts, so neighbouring sources get
        # neighbouring channels and the bundle does not cross itself.
        members.sort(key=lambda m: m[0].points[0][0])
        offset = -(len(members) - 1) / 2
        for step, (edge, i) in enumerate(members):
            shift = int(round((offset + step) * CHANNEL_GAP))
            if not shift:
                continue
            x1, _ = edge.points[i]
            x2, _ = edge.points[i + 1]
            edge.points[i] = (x1, y + shift)
            edge.points[i + 1] = (x2, y + shift)


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

    # ── same row ──
    #
    # Straight across when nothing is in the way. When something is, the
    # line dips below the row and comes back up, because the naive version
    # drew ECS -> RDS as a flat line straight through the ElastiCache box
    # sitting between them -- three services in a row and the arrow went
    # through the middle one as if it were not there.
    left, right = (source, target) if target.x >= source.x else (target, source)
    gap_start, gap_end = left.x + left.w, right.x
    between = [
        b
        for b in boxes
        if b.id not in (source.id, target.id)
        and b.x < gap_end
        and b.x + b.w > gap_start
        and b.y < source.y + source.h
        and b.y + b.h > source.y
    ]

    if not between:
        if target.x >= source.x:
            return [(source.x + source.w, source.cy), (target.x, target.cy)]
        return [(source.x, source.cy), (target.x + target.w, target.cy)]

    # Under the row, clearing the tallest thing in the way.
    duck = max(b.y + b.h for b in between) + 22
    if target.x >= source.x:
        return [
            (source.x + source.w, source.cy),
            (source.x + source.w + 14, source.cy),
            (source.x + source.w + 14, duck),
            (target.cx, duck),
            (target.cx, target.y + target.h),
        ]
    return [
        (source.x, source.cy),
        (source.x - 14, source.cy),
        (source.x - 14, duck),
        (target.cx, duck),
        (target.cx, target.y + target.h),
    ]


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
        max(inner_w + COMPONENT_PAD * 2, MIN_COMPONENT_W),
        inner_h + COMPONENT_PAD * 2 + COMPONENT_LABEL_H,
        cols,
        rows,
    )


def _connect_the_actor(layout: Layout) -> None:
    """Draw the arrow from the people into the system.

    The actor was drawn and left unattached, so a diagram opened with a figure
    labelled Users standing beside a boundary with no line into it -- and
    every reference architecture begins with exactly that line. Traffic has to
    be shown arriving from somewhere or the first box is where the story
    starts, which is not true.

    It lands on whatever has no synchronous edge arriving at it and sits
    earliest in the request path, which is the box traffic actually reaches
    first.
    """
    if not layout.actor or not layout.nodes:
        return

    has_incoming = {e.target for e in layout.edges if e.flow == "sync"}
    entry_candidates = [n for n in layout.nodes if n.id not in has_incoming]
    if not entry_candidates:
        entry_candidates = layout.nodes

    # Earliest tier first, then nearest the actor, which is leftmost.
    entry = min(
        entry_candidates, key=lambda n: (TIER_ORDER.index(n.tier), n.x, n.y)
    )

    start = (layout.actor.x + layout.actor.w, layout.actor.y + layout.actor.h // 2)

    # Straight in when the entry is on the actor's own line.
    if start[1] == entry.cy:
        points = [start, (entry.x, entry.cy)]
    else:
        # Otherwise up the clear margin between the actor and the cloud, then
        # over the top and down into the entry.
        #
        # The lane used to be `entry.x - 24`, which for a DNS entry near the
        # middle of the edge row sat INSIDE the network -- the arrow left the
        # actor, crossed the compute box, turned upward through the NAT
        # gateway and arrived from underneath. Nothing is placed left of the
        # cloud, so that strip is the one corridor guaranteed to be free.
        lane = (layout.actor.x + layout.actor.w + entry.x) // 2
        lane = min(lane, layout.actor.x + layout.actor.w + 28)
        above = entry.y - 26
        points = [
            start,
            (lane, start[1]),
            (lane, above),
            (entry.cx, above),
            (entry.cx, entry.y),
        ]
    layout.actor_edge = PlacedEdge(
        source=ACTOR_SOURCE, target=entry.id, flow="sync", points=points
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
    # The arrow from the people is the entry, not a step between services.
    # Numbering it shifts every other number by one and makes the sequence a
    # reader follows disagree with the one they were shown before.
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
    # Components are the unit of layout even when there is a network, which is
    # how AWS's own diagrams are built: "Web UI component" and "Cost
    # component" sit outside the VPC, "Data component" and "Discovery
    # component" sit inside it. Treating the two as alternatives -- pack by
    # component OR nest by network -- meant a description with a VPC lost its
    # functional grouping entirely and became an inventory of where things
    # live rather than a picture of what they do.
    #
    # The nested layout is still used when a description has network structure
    # and no components to organise it with. Two zones of subnets is a real
    # shape and worth drawing as one.
    if _has_network_nesting(graph) and not _has_components(graph):
        return _nested_layout(graph)

    components = graph.components()
    if not components:
        return _fit(Layout(width=CANVAS_PAD * 2, height=CANVAS_PAD * 2))

    network = _network_of(graph)
    components = _order_by_connection(components, graph, network)

    placed: list[PlacedNode] = []
    boxes: list[PlacedComponent] = []

    x = CANVAS_PAD
    y = CANVAS_PAD
    row_height = 0
    widest = 0

    previous_network: str | None = None
    for name, members in components:
        box_w, box_h, cols, _ = _component_size(len(members))
        this_network = network.get(name, "")

        # A new row whenever the boundary changes, so components sharing one
        # stay together and the box drawn round them is a rectangle rather
        # than a shape reaching across the page to collect a stray.
        if previous_network is not None and this_network != previous_network:
            x = CANVAS_PAD
            y += row_height + COMPONENT_GAP
            row_height = 0
        previous_network = this_network

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

    # ── network boundaries, drawn around the components inside them ──
    # This is what makes the picture read as AWS's do: the VPC is a box around
    # "Data component" and "Discovery component", not a separate arrangement
    # competing with them. A boundary with no component inside is not drawn --
    # there is nothing for it to contain.
    for group in graph.groups:
        if group.kind not in ("vpc", "subnet", "az", "region"):
            continue
        inside = [
            box for box in boxes if network.get(box.name) == group.id
        ]
        if not inside:
            continue
        pad = COMPONENT_PAD + 12
        left = min(b.x for b in inside) - pad
        top = min(b.y for b in inside) - pad - COMPONENT_LABEL_H
        layout.groups.append(
            PlacedGroup(
                id=group.id, kind=group.kind, label=group.label, depth=0,
                x=left, y=top,
                w=max(b.x + b.w for b in inside) - left + pad,
                h=max(b.y + b.h for b in inside) - top + pad,
            )
        )

    # ── boundaries around loose nodes ──
    # Drawn deepest first so an outer region ends up containing the boxes of
    # everything nested in it, not only the nodes it names directly.
    parents = {c: g.id for g in graph.groups for c in g.child_ids}
    drawn: dict[str, tuple[int, int, int, int]] = {}
    already_drawn = {g.id for g in layout.groups}
    for group in sorted(graph.groups, key=lambda g: -_depth_of(g.id, parents)):
        if group.id in already_drawn:
            continue
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

    _number_the_path(graph, layout)
    _connect_the_actor(layout)

    separate_channels(layout.edges)
    return _fit(layout)




# ── boundary-first placement ──────────────────────────────────────────────
#
# The other layout packs components and then draws each boundary as a box
# around wherever its services happened to land. That is backwards for a
# description with real network structure: a VPC is not a shape fitted around
# scattered boxes, it is the thing the boxes are inside, and drawn the other
# way round the containers overlap each other and their contents.
#
# So when a description has network nesting -- a VPC, availability zones,
# subnets -- the boundaries are placed first and the services put inside them.
# Availability zones sit side by side as columns, because that is what makes a
# multi-AZ diagram legible: the eye compares one zone against the other.
# Everything else stacks.

#: Zones go side by side; every other container stacks its children.
SIDE_BY_SIDE: set[str] = {"az", "region"}


@dataclass
class _Box:
    """A boundary being sized before it is placed."""

    group: GraphGroup
    nodes: list[GraphNode]
    children: list["_Box"]
    w: int = 0
    h: int = 0


def _prune(box: _Box) -> _Box | None:
    """Drop containers that ended up holding nothing.

    A description mentions subnets it never puts anything in, and an empty box
    with a label is not information -- it is a rectangle asserting a structure
    the diagram cannot show.
    """
    box.children = [c for c in (_prune(child) for child in box.children) if c]
    if not box.nodes and not box.children:
        return None
    return box


def _tree(graph: ArchitectureGraph) -> list[_Box]:
    """The boundary hierarchy, with each one's own services attached.

    Built as a tree, which the boundaries are not. A description saying "a
    public subnet in each availability zone" names one "Public subnet" and
    lists it inside both zones, so following every parent-child link visited
    that subnet -- and the services in it -- once per zone. Six services came
    out as eighteen boxes and the diagram was three times as tall as the
    system it drew.

    The first parent to claim a boundary keeps it. Which parent wins does not
    matter much; drawing it once does.
    """
    by_id = {g.id: g for g in graph.groups}
    node_by_id = {n.id: n for n in graph.nodes}
    child_ids = {c for g in graph.groups for c in g.child_ids}
    claimed: set[str] = set()

    def build(group: GraphGroup) -> _Box:
        claimed.add(group.id)
        children = []
        for child_id in group.child_ids:
            child = by_id.get(child_id)
            if child and child_id not in claimed:
                children.append(build(child))
        return _Box(
            group=group,
            nodes=[node_by_id[n] for n in group.node_ids if n in node_by_id],
            children=children,
        )

    roots = (build(g) for g in graph.groups if g.id not in child_ids)
    return [box for box in (_prune(root) for root in roots) if box]


#: Roughly the width of one character of a boundary label at 13px semibold.
#: Only used to stop a box being narrower than its own name; being a little
#: out costs a few pixels of slack, not a broken diagram.
LABEL_CHAR_W = 7.4
LABEL_BADGE_W = 42


def _label_width(box: _Box) -> int:
    """How wide this box has to be for its own label to fit inside it."""
    return int(len(box.group.label) * LABEL_CHAR_W) + LABEL_BADGE_W + BOX_PAD


def _measure(box: _Box) -> None:
    """Size a box from the bottom up: children first, then itself."""
    for child in box.children:
        _measure(child)

    cols = min(COMPONENT_COLS, max(1, len(box.nodes)))
    rows = -(-len(box.nodes) // cols) if box.nodes else 0
    nodes_w = cols * NODE_W + (cols - 1) * GAP_X if box.nodes else 0
    nodes_h = rows * NODE_H + (rows - 1) * ROW_GAP_INNER if box.nodes else 0

    if box.children:
        # Whether children go side by side is a fact about the children, not
        # about their parent. Testing the parent's kind put the subnets of an
        # availability zone in a row, where every multi-AZ diagram stacks
        # them: public above private, one zone beside the next.
        side = any(c.group.kind in SIDE_BY_SIDE for c in box.children)
        if side:
            kids_w = sum(c.w for c in box.children) + BOX_GAP * (len(box.children) - 1)
            kids_h = max(c.h for c in box.children)
        else:
            kids_w = max(c.w for c in box.children)
            kids_h = sum(c.h for c in box.children) + BOX_GAP * (len(box.children) - 1)
    else:
        kids_w = kids_h = 0

    inner_w = max(nodes_w, kids_w)
    inner_h = nodes_h + (BOX_GAP if nodes_h and kids_h else 0) + kids_h

    # A box has to be at least as wide as its own name. Sized from contents
    # alone, an availability zone holding two nearly empty subnets came out
    # narrower than the words "Availability Zone 2", so the label ran past the
    # border and collided with the zone drawn beside it.
    #
    # AZs and subnets also enforce a minimum width so they spread
    # horizontally like AWS reference architectures instead of stacking into
    # tall thin columns.
    min_w = _label_width(box)
    if box.group.kind in ("az", "subnet"):
        min_w = max(min_w, MIN_AZ_W)
    box.w = max(inner_w + BOX_PAD * 2, min_w)
    box.h = inner_h + BOX_PAD * 2 + BOX_LABEL_H


def _place(
    box: _Box, x: int, y: int, nodes: list[PlacedNode], groups: list[PlacedGroup],
    depth: int = 0,
) -> None:
    """Put a measured box down, then everything inside it."""
    groups.append(
        PlacedGroup(
            id=box.group.id, kind=box.group.kind, label=box.group.label,
            depth=depth, x=x, y=y, w=box.w, h=box.h,
        )
    )

    inner_x = x + BOX_PAD
    inner_y = y + BOX_PAD + BOX_LABEL_H

    if box.nodes:
        cols = min(COMPONENT_COLS, len(box.nodes))
        for index, node in enumerate(box.nodes):
            col, row = index % cols, index // cols
            nodes.append(
                PlacedNode(
                    id=node.id, label=node.label, tier=node.tier,
                    purpose=node.purpose, priced=node.priced,
                    monthly_usd=float(node.monthly_usd) if node.priced else None,
                    sku=node.sku,
                    x=inner_x + col * (NODE_W + GAP_X),
                    y=inner_y + row * (NODE_H + ROW_GAP_INNER),
                )
            )
        rows = -(-len(box.nodes) // cols)
        inner_y += rows * NODE_H + (rows - 1) * ROW_GAP_INNER + BOX_GAP

    if not box.children:
        return

    side = any(c.group.kind in SIDE_BY_SIDE for c in box.children)
    cursor_x, cursor_y = inner_x, inner_y
    for child in box.children:
        _place(child, cursor_x, cursor_y, nodes, groups, depth + 1)
        if side:
            cursor_x += child.w + BOX_GAP
        else:
            cursor_y += child.h + BOX_GAP


def _order_by_connection(
    components: list[tuple[str, list[GraphNode]]],
    graph: ArchitectureGraph,
    network: dict[str, str],
) -> list[tuple[str, list[GraphNode]]]:
    """Place components that talk to each other next to each other.

    Ordering by tier alone put the API component at the top and the data store
    it queries four rows down, so its arrows crossed everything between them.
    In a hand-drawn architecture almost every line is short, and that is not a
    drawing convention -- it is what happens when whoever drew it put related
    things together.

    Greedy rather than optimal: start at the component the request enters, then
    repeatedly take whichever unplaced component has the most links to what is
    already down. Ordering a dozen components perfectly is a travelling
    salesman; this gets most of the shortening for none of the cost.

    Components sharing a network boundary still finish adjacent, because the
    box drawn round them afterwards has to be one rectangle rather than a
    shape reaching across the page to collect a stray.
    """
    if len(components) < 3:
        return components

    of_node = {n.id: (n.component or "Other") for n in graph.nodes}
    links: dict[str, dict[str, int]] = {}
    for edge in graph.edges:
        a, b = of_node.get(edge.source), of_node.get(edge.target)
        if a and b and a != b:
            links.setdefault(a, {}).setdefault(b, 0)
            links.setdefault(b, {}).setdefault(a, 0)
            links[a][b] += 1
            links[b][a] += 1

    remaining = dict(components)
    order: list[str] = []

    def score(name: str, placed: set[str], last: str) -> tuple[int, int, str]:
        """How well `name` follows what is already placed.

        Takes the placed set explicitly rather than closing over it. Defined
        inside the loop it would capture the name late, so a call deferred
        past the next iteration would silently score against a different
        set than the caller meant -- the ordering would still look
        plausible, which is the kind of wrong that never gets noticed.
        """
        joined = sum(links.get(name, {}).get(other, 0) for other in placed)
        # Same boundary as the last one placed beats a stronger link
        # elsewhere: a boundary split across the order cannot be drawn as
        # one box afterwards.
        same_boundary = network.get(name, "") == network.get(last, "")
        return (int(same_boundary), joined, name)

    # Start where traffic arrives: the component holding the earliest tier.
    first = min(
        remaining,
        key=lambda name: min(TIER_ORDER.index(n.tier) for n in remaining[name]),
    )
    order.append(first)
    del remaining[first]

    while remaining:
        # partial binds this iteration's values eagerly, so the key function
        # cannot read a later iteration's state.
        best = max(remaining, key=partial(score, placed=set(order), last=order[-1]))
        order.append(best)
        del remaining[best]

    by_name = dict(components)
    return [(name, by_name[name]) for name in order]


def _has_components(graph: ArchitectureGraph) -> bool:
    """Did the reader group the services into functional components?

    One component holding everything is not a grouping -- it is the absence of
    one wearing a name -- so it does not count.
    """
    named = {n.component for n in graph.nodes if n.component}
    return len(named) >= 2


def _network_of(graph: ArchitectureGraph) -> dict[str, str]:
    """Which network boundary each component's services mostly sit in.

    A component is placed as a unit, so it belongs to whichever boundary holds
    most of it. Splitting one across a VPC edge would draw half a component
    inside the network and half outside, which is not a thing a system does.
    """
    by_node = {
        node_id: group.id
        for group in graph.groups
        if group.kind in ("vpc", "subnet", "az")
        for node_id in group.node_ids
    }
    tally: dict[str, dict[str, int]] = {}
    for node in graph.nodes:
        boundary = by_node.get(node.id)
        if boundary:
            component = node.component or "Other"
            tally.setdefault(component, {}).setdefault(boundary, 0)
            tally[component][boundary] += 1

    return {
        component: max(counts, key=lambda b: counts[b])
        for component, counts in tally.items()
    }


def _has_network_nesting(graph: ArchitectureGraph) -> bool:
    """Is there real structure to lay out, or only a stray container?

    One VPC holding everything is not a hierarchy and gains nothing from this;
    a VPC with zones and subnets inside it is exactly what it is for.
    """
    kinds = {g.kind for g in graph.groups if g.node_ids or g.child_ids}
    return len(kinds & {"vpc", "az", "subnet", "region"}) >= 2


def _nested_layout(graph: ArchitectureGraph) -> Layout:
    """Boundaries first, services inside them.

    For a description with real network structure this is the shape of the
    thing: a VPC holding zones holding subnets holding services. Placing the
    services first and fitting boxes around them afterwards produces
    containers that overlap each other and their own contents, because a
    bounding box drawn round scattered nodes is not a boundary -- it is a
    shape that happens to enclose them.
    """
    roots = _tree(graph)
    for root in roots:
        _measure(root)

    nodes: list[PlacedNode] = []
    groups: list[PlacedGroup] = []

    x = CANVAS_PAD
    y = CANVAS_PAD
    for root in roots:
        _place(root, x, y, nodes, groups)
        y += root.h + BOX_GAP

    # Services in no boundary at all -- a CDN, a CI pipeline, an external
    # gateway -- are part of the system and have to go somewhere. Where
    # matters: putting them all underneath sent CloudFront, which is the first
    # thing a request touches, to the bottom of the page, so the eye went from
    # the users down past the whole VPC, back up into it, and left to right
    # from there. A diagram is read in the order it is laid out.
    #
    # So they are split by where they sit in the request path. Anything at the
    # edge or the API tier goes above the network, which is where a request
    # meets it; everything else -- pipelines, telemetry, management -- goes
    # below, which is where a reader looks after following the request.
    placed_ids = {n.id for n in nodes}
    loose = [n for n in graph.nodes if n.id not in placed_ids]
    before = [n for n in loose if TIER_ORDER.index(n.tier) <= TIER_ORDER.index("api")]
    after = [n for n in loose if n not in before]

    def place_row(items: list[GraphNode], top: int) -> int:
        """Lay a row of loose services out, returning the height used."""
        if not items:
            return 0
        # Prefer a single wide row so edge services (CloudFront, Route 53,
        # WAF, Shield) sit side by side across the top, matching how AWS
        # reference architectures draw them. Only wrap when there are too
        # many to fit.
        cols = min(MAX_PER_ROW, len(items))
        for index, node in enumerate(items):
            col, row = index % cols, index // cols
            nodes.append(
                PlacedNode(
                    id=node.id, label=node.label, tier=node.tier,
                    purpose=node.purpose, priced=node.priced,
                    monthly_usd=float(node.monthly_usd) if node.priced else None,
                    sku=node.sku,
                    x=CANVAS_PAD + col * (NODE_W + GAP_X),
                    y=top + row * (NODE_H + ROW_GAP_INNER),
                )
            )
        rows = -(-len(items) // cols)
        return rows * NODE_H + (rows - 1) * ROW_GAP_INNER

    if before:
        # Above the boundaries, so everything below shifts down to make room.
        used = place_row(before, CANVAS_PAD)
        shift = used + BOX_GAP * 2
        for node in nodes[: len(nodes) - len(before)]:
            node.y += shift
        for group in groups:
            group.y += shift
        y += shift

    place_row(after, y + BOX_GAP)

    width = max((n.x + n.w for n in nodes), default=CANVAS_PAD)
    width = max(width, max((g.x + g.w for g in groups), default=0)) + CANVAS_PAD
    height = max((n.y + n.h for n in nodes), default=CANVAS_PAD)
    height = max(height, max((g.y + g.h for g in groups), default=0)) + CANVAS_PAD

    layout = Layout(width=width, height=height, nodes=nodes, groups=groups)

    for edge in graph.edges:
        source, target = layout.node(edge.source), layout.node(edge.target)
        if source and target:
            layout.edges.append(
                PlacedEdge(
                    source=edge.source, target=edge.target, flow=edge.flow,
                    points=_route(source, target, nodes, width),
                )
            )

    _number_the_path(graph, layout)

    extent = [*layout.nodes, *layout.groups]
    left = min(b.x for b in extent)
    top = min(b.y for b in extent)
    right = max(b.x + b.w for b in extent)
    bottom = max(b.y + b.h for b in extent)
    layout.cloud = PlacedCloud(
        label="AWS Cloud",
        x=left - CLOUD_PAD, y=top - CLOUD_PAD - CLOUD_LABEL_H,
        w=(right - left) + CLOUD_PAD * 2,
        h=(bottom - top) + CLOUD_PAD * 2 + CLOUD_LABEL_H,
    )
    layout.actor = PlacedActor(
        label="Users",
        x=layout.cloud.x - ACTOR_GAP - ACTOR_W,
        y=layout.cloud.y + (layout.cloud.h - ACTOR_H) // 2,
        w=ACTOR_W, h=ACTOR_H,
    )
    _connect_the_actor(layout)
    separate_channels(layout.edges)
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
        if layout.actor_edge:
            layout.actor_edge.points = [
                (x + dx, y + dy) for x, y in layout.actor_edge.points
            ]

    layout.width = max(right) + dx + CANVAS_PAD
    layout.height = max(bottom) + dy + CANVAS_PAD
