"""Placing a graph on a canvas."""

from whichcloud.architecture import Architecture, Boundary, Service
from whichcloud.architecture.graph import build_graph
from whichcloud.architecture.layout import (
    MAX_PER_ROW,
    NODE_W,
    build_layout,
)


def svc(name, tier="compute", flow="sync", connects=()):
    return Service(name=name, tier=tier, flow=flow, connects_to=list(connects))


def layout_of(*services, boundaries=()):
    return build_layout(
        build_graph(Architecture(services=list(services), boundaries=list(boundaries)))
    )


def test_the_same_graph_lays_out_identically_every_time():
    """A diagram that reshuffles on reload is the extraction-drift bug one
    layer further on."""
    services = [
        svc("Route 53", "edge", connects=["CloudFront"]),
        svc("CloudFront", "edge", connects=["EKS"]),
        svc("EKS", "compute", connects=["Aurora", "Redis"]),
        svc("Aurora", "data"),
        svc("Redis", "data"),
    ]
    a = layout_of(*services)
    b = layout_of(*services)

    assert [(n.id, n.x, n.y) for n in a.nodes] == [(n.id, n.x, n.y) for n in b.nodes]
    assert (a.width, a.height) == (b.width, b.height)


def test_tiers_run_down_the_page():
    lay = layout_of(
        svc("CloudWatch", "observability"), svc("Aurora", "data"), svc("Route 53", "edge")
    )
    ys = {n.label: n.y for n in lay.nodes}

    assert ys["Route 53"] < ys["Aurora"] < ys["CloudWatch"]


def test_a_crowded_tier_wraps_instead_of_running_off_the_canvas():
    """Eight boxes in one row would force the whole diagram to scale down
    until nothing on it could be read."""
    crowded = [svc(f"svc{i}", "security") for i in range(8)]
    lay = layout_of(*crowded)

    rows = {n.y for n in lay.nodes}
    assert len(rows) == 2
    per_row = [sum(1 for n in lay.nodes if n.y == y) for y in sorted(rows)]
    assert max(per_row) <= MAX_PER_ROW
    # Split evenly: 6 and 2 reads as a mistake, 4 and 4 as a decision.
    assert per_row == [4, 4]


def test_the_canvas_grows_with_the_widest_row():
    narrow = layout_of(svc("a"), svc("b"))
    wide = layout_of(*[svc(f"s{i}") for i in range(MAX_PER_ROW)])

    assert wide.width > narrow.width
    assert wide.width >= MAX_PER_ROW * NODE_W


def test_nothing_is_placed_outside_the_canvas():
    lay = layout_of(*[svc(f"s{i}", "data") for i in range(9)])

    for n in lay.nodes:
        assert 0 <= n.x and n.x + n.w <= lay.width
        assert 0 <= n.y and n.y + n.h <= lay.height


def test_an_edge_down_the_page_is_an_elbow_not_a_diagonal():
    """A diagonal across rows crosses everything between them."""
    lay = layout_of(svc("Route 53", "edge", connects=["Aurora"]), svc("Aurora", "data"))
    points = lay.edges[0].points

    assert len(points) == 4
    assert points[0][1] < points[-1][1]          # runs downward
    assert points[1][1] == points[2][1]          # via a horizontal mid-segment


def test_an_edge_within_a_row_leaves_from_the_side():
    """Otherwise a replication arrow is drawn straight through both boxes."""
    lay = layout_of(
        svc("Aurora", "data", flow="replication", connects=["Aurora Replica"]),
        svc("Aurora Replica", "data"),
    )
    points = lay.edges[0].points

    assert len(points) == 2
    assert points[0][1] == points[1][1]          # horizontal, same row


def test_flow_survives_onto_the_placed_edge():
    lay = layout_of(
        svc("EKS", "compute", flow="async", connects=["MSK"]), svc("MSK", "async")
    )
    assert lay.edges[0].flow == "async"


def test_a_group_encloses_what_it_holds():
    lay = layout_of(
        svc("EKS"),
        boundaries=[Boundary(kind="vpc", name="prod", contains=["EKS"])],
    )
    group = lay.groups[0]
    node = lay.nodes[0]

    assert group.x < node.x
    assert group.y < node.y
    assert group.x + group.w > node.x + node.w
    assert group.y + group.h > node.y + node.h


def test_an_outer_group_encloses_the_group_inside_it():
    """A region must contain its VPC's box, not just the nodes it names."""
    lay = layout_of(
        svc("EKS"),
        boundaries=[
            Boundary(kind="region", name="us-east-1", contains=["prod-vpc"]),
            Boundary(kind="vpc", name="prod-vpc", contains=["EKS"]),
        ],
    )
    region = next(g for g in lay.groups if g.kind == "region")
    vpc = next(g for g in lay.groups if g.kind == "vpc")

    assert region.x < vpc.x and region.y < vpc.y
    assert region.x + region.w > vpc.x + vpc.w
    assert region.depth < vpc.depth


def test_groups_come_back_outermost_first():
    """So the interface can paint them in order and have nesting land on top."""
    lay = layout_of(
        svc("EKS"),
        boundaries=[
            Boundary(kind="region", name="r", contains=["v"]),
            Boundary(kind="vpc", name="v", contains=["EKS"]),
        ],
    )
    assert [g.depth for g in lay.groups] == sorted(g.depth for g in lay.groups)


def test_an_empty_boundary_is_not_drawn():
    lay = layout_of(
        svc("EKS"), boundaries=[Boundary(kind="vpc", name="empty", contains=[])]
    )
    assert [g.label for g in lay.groups] == []


def test_an_empty_graph_does_not_crash():
    lay = build_layout(build_graph(Architecture()))
    assert lay.nodes == [] and lay.edges == [] and lay.width > 0


def test_groups_are_inside_the_canvas_too():
    """A group is drawn around its nodes and each nesting level adds padding,
    so an outer region reaches further than anything it contains. Sizing the
    canvas from nodes alone put the account box at x=-76 on a 1298 canvas."""
    lay = layout_of(
        svc("EKS"),
        boundaries=[
            Boundary(kind="account", name="acct", contains=["r"]),
            Boundary(kind="region", name="r", contains=["v"]),
            Boundary(kind="vpc", name="v", contains=["EKS"]),
        ],
    )
    assert lay.groups, "expected the nested boundaries to be drawn"
    for g in lay.groups:
        assert g.x >= 0 and g.y >= 0, f"{g.label} starts off-canvas at ({g.x},{g.y})"
        assert g.x + g.w <= lay.width, f"{g.label} overflows the width"
        assert g.y + g.h <= lay.height, f"{g.label} overflows the height"


def test_edges_move_with_the_nodes_when_the_canvas_shifts():
    """Translating nodes without their arrows would detach every line."""
    lay = layout_of(
        svc("Route 53", "edge", connects=["Aurora"]),
        svc("Aurora", "data"),
        boundaries=[
            Boundary(kind="account", name="a", contains=["r"]),
            Boundary(kind="region", name="r", contains=["Route 53", "Aurora"]),
        ],
    )
    src = lay.node("route-53")
    assert lay.edges[0].points[0] == (src.cx, src.y + src.h)


def test_exported_svg_is_well_formed_and_complete():
    """The export leaves this machine and gets opened in other tools, so it
    has to be valid XML rather than merely look right in one renderer."""
    import xml.etree.ElementTree as ET

    from whichcloud.architecture.svg import render

    lay = layout_of(
        svc("Route 53", "edge", connects=["Aurora"]),
        svc("Aurora", "data"),
        boundaries=[Boundary(kind="vpc", name="prod", contains=["Aurora"])],
    )
    doc = render(lay, title="Test & <check>")

    root = ET.fromstring(doc)          # raises if malformed
    assert root.attrib["width"] == str(lay.width)
    # Titles and labels reach the file through XML escaping, not raw.
    assert "Test &amp; &lt;check&gt;" in doc
    assert doc.count('rx="11"') == len(lay.nodes)


def test_a_long_label_wraps_rather_than_overflowing():
    """SVG text does not wrap, so a name longer than its box would run across
    the next one. Real service names are long: "Aurora PostgreSQL Global
    Database" is typical."""
    from whichcloud.architecture.svg import _wrap

    lines = _wrap("Aurora PostgreSQL Global Database", 186, limit=2)

    assert len(lines) == 2
    assert lines[0].startswith("Aurora")
    assert all(len(line) < 32 for line in lines)


def test_wrapping_an_empty_purpose_yields_nothing():
    from whichcloud.architecture.svg import _wrap

    assert _wrap("", 186) == []


def _crosses_a_box(points, boxes, endpoints):
    """Does any vertical run of this polyline pass through an unrelated box?"""
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        if x1 != x2:
            continue  # horizontal runs sit in the gap between rows
        top, bottom = sorted((y1, y2))
        for box in boxes:
            if box.id in endpoints:
                continue
            if box.x < x1 < box.x + box.w and box.y < bottom and box.y + box.h > top:
                return box.id
    return None


def test_a_line_steps_around_a_box_in_its_way():
    """A straight drop past an intervening row goes through whatever sits
    there, which is what makes a dense diagram look like a wiring fault."""
    lay = layout_of(
        svc("Edge", "edge", connects=["Store"]),
        # Directly between them, in the source's column.
        svc("Middle", "compute"),
        svc("Store", "data"),
    )
    edge = lay.edges[0]
    hit = _crosses_a_box(edge.points, lay.nodes, {edge.source, edge.target})

    assert hit is None, f"the arrow is drawn through {hit}"


def test_no_arrow_crosses_an_unrelated_box_in_a_dense_diagram():
    """The case that matters: many rows, many boxes, every line checked."""
    services = [
        svc("R53", "edge", connects=["EKS", "Aurora"]),
        svc("CDN", "edge", connects=["EKS"]),
        svc("GW", "api", connects=["EKS"]),
        svc("EKS", "compute", connects=["Aurora", "Redis", "S3"]),
        svc("Aurora", "data"),
        svc("Redis", "data"),
        svc("S3", "data"),
        svc("Watch", "observability"),
    ]
    lay = layout_of(*services)

    offenders = [
        (e.source, e.target, _crosses_a_box(e.points, lay.nodes, {e.source, e.target}))
        for e in lay.edges
    ]
    bad = [o for o in offenders if o[2]]
    assert bad == [], f"arrows drawn through boxes: {bad}"


def test_a_detoured_line_still_starts_and_ends_on_its_boxes():
    """Routing around must not detach the arrow from what it connects."""
    lay = layout_of(
        svc("Edge", "edge", connects=["Store"]),
        svc("Middle", "compute"),
        svc("Store", "data"),
    )
    edge = lay.edges[0]
    src, dst = lay.node(edge.source), lay.node(edge.target)

    assert edge.points[0] == (src.cx, src.y + src.h)
    assert edge.points[-1] == (dst.cx, dst.y)
