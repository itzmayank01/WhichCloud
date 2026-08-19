"""Placing a graph on a canvas."""

from whichcloud.architecture import Architecture, Boundary, Service
from whichcloud.architecture.graph import build_graph
from whichcloud.architecture.layout import COMPONENT_COLS, build_layout


def svc(name, tier="compute", flow="sync", connects=(), component=""):
    return Service(
        name=name, tier=tier, flow=flow,
        connects_to=list(connects), component=component,
    )


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


def test_the_first_component_is_where_traffic_arrives():
    """Ordering used to be by tier alone, which put the API component at the
    top and the data store it queries four rows down, so its arrows crossed
    everything between. Components are ordered by what they talk to now, but
    the sequence still starts where a request enters."""
    lay = layout_of(
        svc("CloudWatch", "observability", component="Observability"),
        svc("Aurora", "data", component="Data"),
        svc("Route 53", "edge", connects=["Aurora"], component="Edge"),
    )

    assert [c.name for c in lay.components][0] == "Edge"


def test_connected_components_are_placed_next_to_each_other():
    """In a hand-drawn architecture almost every line is short, and that is
    not a drawing convention -- it is what happens when whoever drew it put
    related things together."""
    lay = layout_of(
        svc("Route 53", "edge", connects=["Aurora"], component="Edge"),
        svc("Aurora", "data", component="Data"),
        svc("CloudWatch", "observability", component="Observability"),
        svc("CodeBuild", "cicd", component="Delivery"),
    )
    order = [c.name for c in lay.components]

    # Data is what Edge talks to, so it follows immediately; the two that
    # connect to nothing come after.
    assert order[:2] == ["Edge", "Data"]


def test_tier_still_orders_services_inside_a_component():
    """Within a group a request still reads downward."""
    lay = layout_of(
        svc("CloudWatch", "observability", component="One"),
        svc("Route 53", "edge", component="One"),
        svc("Aurora", "data", component="One"),
    )
    placed = sorted(lay.nodes, key=lambda n: (n.y, n.x))

    assert [n.label for n in placed] == ["Route 53", "Aurora", "CloudWatch"]


def test_services_of_one_component_sit_inside_its_box():
    lay = layout_of(
        svc("A", "compute", component="Web UI"),
        svc("B", "data", component="Web UI"),
        svc("C", "data", component="Data"),
    )
    box = next(c for c in lay.components if c.name == "Web UI")
    inside = [n for n in lay.nodes if n.label in ("A", "B")]

    for node in inside:
        assert box.x <= node.x and node.x + node.w <= box.x + box.w
        assert box.y <= node.y and node.y + node.h <= box.y + box.h


def test_ungrouped_services_are_collected_rather_than_dropped():
    lay = layout_of(svc("Loose", "compute"), svc("Grouped", "compute", component="Web"))

    assert len(lay.nodes) == 2
    assert "Other" in [c.name for c in lay.components]


def test_a_large_component_wraps_into_a_grid():
    """Eight boxes in one row would force the diagram to scale down until
    nothing on it could be read."""
    crowded = [svc(f"svc{i}", "security", component="Security") for i in range(8)]
    lay = layout_of(*crowded)

    rows = sorted({n.y for n in lay.nodes})
    per_row = [sum(1 for n in lay.nodes if n.y == y) for y in rows]

    assert max(per_row) <= COMPONENT_COLS
    assert sum(per_row) == 8


def test_the_canvas_grows_with_its_contents():
    narrow = layout_of(svc("a", component="One"))
    wide = layout_of(
        *[svc(f"s{i}", component=f"C{i}") for i in range(3)]
    )

    assert wide.width > narrow.width


def test_nothing_is_placed_outside_the_canvas():
    lay = layout_of(*[svc(f"s{i}", "data") for i in range(9)])

    for n in lay.nodes:
        assert 0 <= n.x and n.x + n.w <= lay.width
        assert 0 <= n.y and n.y + n.h <= lay.height


def test_every_segment_of_a_route_is_axis_aligned():
    """No diagonals. A diagonal across the page crosses everything between,
    and these diagrams are read by following a line with the eye."""
    lay = layout_of(
        svc("Route 53", "edge", connects=["Aurora"], component="Edge"),
        svc("Aurora", "data", component="Data"),
        svc("EKS", "compute", connects=["Aurora"], component="Compute"),
    )

    for edge in lay.edges:
        for (x1, y1), (x2, y2) in zip(edge.points, edge.points[1:]):
            assert x1 == x2 or y1 == y2, "a segment runs diagonally"


def test_a_route_starts_and_ends_on_the_boxes_it_joins():
    lay = layout_of(
        svc("Route 53", "edge", connects=["Aurora"], component="Edge"),
        svc("Aurora", "data", component="Data"),
    )
    edge = lay.edges[0]
    src, dst = lay.node(edge.source), lay.node(edge.target)

    def touches(point, box):
        x, y = point
        return (
            box.x - 1 <= x <= box.x + box.w + 1
            and box.y - 1 <= y <= box.y + box.h + 1
        )

    assert touches(edge.points[0], src)
    assert touches(edge.points[-1], dst)


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
        svc("Route 53", "edge", connects=["Aurora"], component="Edge"),
        svc("Aurora", "data", component="Data"),
        boundaries=[
            Boundary(kind="account", name="a", contains=["r"]),
            Boundary(kind="region", name="r", contains=["Route 53", "Aurora"]),
        ],
    )
    src = lay.node("route-53")
    start = lay.edges[0].points[0]
    assert src.x <= start[0] <= src.x + src.w
    assert src.y <= start[1] <= src.y + src.h


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
    # Every service is named. Counting boxes would only test the current
    # drawing style, which changed when services stopped being cards.
    for node in lay.nodes:
        assert node.label.split()[0] in doc


def test_exported_icons_are_embedded_not_linked():
    """An SVG that references files beside it stops being one file: mail it,
    open it elsewhere, and the marks are gone."""
    from whichcloud.architecture.svg import render

    lay = layout_of(svc("Amazon S3", "data", component="Data"))
    doc = render(lay)

    assert "data:image/png;base64," in doc
    assert 'href="/icons' not in doc
    assert "http" not in doc.split("<image")[1][:200]


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
        svc("Edge", "edge", connects=["Store"], component="A"),
        svc("Middle", "compute", component="B"),
        svc("Store", "data", component="C"),
    )
    edge = lay.edges[0]
    src, dst = lay.node(edge.source), lay.node(edge.target)

    assert src.x <= edge.points[0][0] <= src.x + src.w
    assert dst.x <= edge.points[-1][0] <= dst.x + dst.w


def test_the_request_path_is_numbered_from_where_traffic_enters():
    lay = layout_of(
        svc("Route 53", "edge", connects=["CloudFront"], component="Edge"),
        svc("CloudFront", "edge", connects=["EKS"], component="Edge"),
        svc("EKS", "compute", connects=["Aurora"], component="App"),
        svc("Aurora", "data", component="Data"),
    )
    steps = {(e.source, e.target): e.step for e in lay.edges if e.step}

    assert steps[("route-53", "cloudfront")] == 1
    assert steps[("cloudfront", "eks")] == 2
    assert steps[("eks", "aurora")] == 3


def test_only_the_request_path_is_numbered():
    """Numbering the telemetry and the build pipeline too puts a badge on
    every line and numbers nothing -- the sequence a reader follows is the one
    a request takes."""
    lay = layout_of(
        svc("Route 53", "edge", connects=["EKS"], component="Edge"),
        svc("EKS", "compute", connects=["MSK"], flow="async", component="App"),
        svc("MSK", "async", component="Async"),
    )
    numbered = [e for e in lay.edges if e.step]

    assert all(e.flow == "sync" for e in numbered)


def test_each_path_is_finished_before_the_next_begins():
    """Seeding one queue with every entry point interleaves them, so a diagram
    counts 1 at the CDN, 2 in the build pipeline and 3 back at the CDN --
    unrelated journeys sharing a numbering, which is worse than none."""
    lay = layout_of(
        svc("Route 53", "edge", connects=["CloudFront"], component="Edge"),
        svc("CloudFront", "edge", connects=["EKS"], component="Edge"),
        svc("EKS", "compute", component="App"),
        svc("GitHub", "cicd", connects=["ECR"], component="CI"),
        svc("ECR", "cicd", component="CI"),
    )
    steps = {(e.source, e.target): e.step for e in lay.edges if e.step}

    # The edge path takes 1 and 2; the build pipeline follows it.
    assert steps[("route-53", "cloudfront")] == 1
    assert steps[("cloudfront", "eks")] == 2
    assert steps[("github", "ecr")] == 3


def test_the_cloud_boundary_encloses_everything():
    lay = layout_of(svc("EKS", "compute", component="App"))

    assert lay.cloud is not None
    for node in lay.nodes:
        assert lay.cloud.x < node.x
        assert lay.cloud.y < node.y
        assert lay.cloud.x + lay.cloud.w > node.x + node.w


def test_the_actor_stands_outside_the_cloud():
    """Users are not inside the provider's boundary. Every reference
    architecture is framed this way and it is the whole point of the frame."""
    lay = layout_of(svc("EKS", "compute", component="App"))

    assert lay.actor is not None
    assert lay.actor.x + lay.actor.w <= lay.cloud.x
    assert lay.actor.x >= 0


def test_a_badge_avoids_the_boxes_and_the_other_badges():
    from whichcloud.architecture.layout import badge_point

    lay = layout_of(
        *[svc(f"s{i}", "compute", connects=[f"s{i + 1}"], component="C") for i in range(5)],
        svc("s5", "data", component="D"),
    )
    taken: set[tuple[int, int]] = set()
    for edge in sorted((e for e in lay.edges if e.step), key=lambda e: e.step or 0):
        point = badge_point(edge.points, lay.nodes, taken)
        assert point not in taken
        taken.add(point)


def _nested_arch():
    from whichcloud.architecture import Architecture

    return Architecture(
        services=[
            svc("ELB", "api", connects=["EC2"]),
            svc("EC2", "compute", connects=["RDS"]),
            svc("RDS", "data"),
            svc("NAT", "security"),
        ],
        boundaries=[
            Boundary(kind="vpc", name="VPC", contains=["AZ 1", "AZ 2"]),
            Boundary(kind="az", name="AZ 1", contains=["Public subnet 1", "Private subnet 1"]),
            Boundary(kind="az", name="AZ 2", contains=["Public subnet 2", "Private subnet 2"]),
            Boundary(kind="subnet", name="Public subnet 1", contains=["ELB"]),
            Boundary(kind="subnet", name="Private subnet 1", contains=["EC2"]),
            Boundary(kind="subnet", name="Public subnet 2", contains=["NAT"]),
            Boundary(kind="subnet", name="Private subnet 2", contains=["RDS"]),
        ],
    )


def test_a_network_description_nests_its_boundaries():
    """A VPC is not a shape fitted around scattered boxes; it is the thing
    they are inside. Drawn the other way round the containers overlap each
    other and their own contents."""
    from whichcloud.architecture.graph import build_graph

    lay = build_layout(build_graph(_nested_arch()))
    by_kind = {g.kind: g for g in lay.groups}

    vpc, az = by_kind["vpc"], by_kind["az"]
    assert vpc.x < az.x and vpc.y < az.y
    assert vpc.x + vpc.w > az.x + az.w
    assert vpc.y + vpc.h > az.y + az.h


def test_zones_sit_side_by_side_and_their_subnets_stack():
    """Every multi-AZ diagram is read by comparing one zone against the next,
    with public above private inside each."""
    from whichcloud.architecture.graph import build_graph

    lay = build_layout(build_graph(_nested_arch()))
    zones = sorted((g for g in lay.groups if g.kind == "az"), key=lambda g: g.x)
    subnets = [g for g in lay.groups if g.kind == "subnet"]

    assert zones[0].y == zones[1].y and zones[0].x < zones[1].x

    public = [g for g in subnets if "Public" in g.label]
    private = [g for g in subnets if "Private" in g.label]
    assert max(g.y for g in public) < min(g.y for g in private)


def test_every_service_lands_inside_the_subnet_that_claims_it():
    from whichcloud.architecture.graph import build_graph

    lay = build_layout(build_graph(_nested_arch()))
    subnets = [g for g in lay.groups if g.kind == "subnet"]

    for node in lay.nodes:
        holder = [
            g for g in subnets
            if g.x <= node.x and node.x + node.w <= g.x + g.w
            and g.y <= node.y and node.y + node.h <= g.y + g.h
        ]
        assert holder, f"{node.label} sits in no subnet"


def test_a_lone_container_does_not_trigger_nesting():
    """One VPC holding everything is not a hierarchy and gains nothing from
    being laid out as one."""
    from whichcloud.architecture import Architecture
    from whichcloud.architecture.graph import build_graph

    arch = Architecture(
        services=[svc("EKS", "compute", component="App")],
        boundaries=[Boundary(kind="vpc", name="VPC", contains=["EKS"])],
    )
    lay = build_layout(build_graph(arch))

    assert lay.components, "expected the component layout"


def test_a_corner_is_drawn_as_a_curve():
    """stroke-linejoin only softens a corner by the stroke width, which at 2px
    is invisible. The turn has to be drawn."""
    from whichcloud.architecture.svg import rounded_path

    assert "Q" in rounded_path([(0, 0), (0, 60), (80, 60)])
    # A straight run has no corner to turn.
    assert "Q" not in rounded_path([(0, 0), (100, 0)])


def test_a_tight_corner_curves_less_rather_than_overshooting():
    """A radius larger than the segment would carry the curve past the next
    corner and back on itself."""
    from whichcloud.architecture.svg import CORNER_R, rounded_path

    path = rounded_path([(0, 0), (0, 8), (20, 8)])
    # The curve starts inside the 8px segment, not before it began.
    assert "L0 4" in path
    assert CORNER_R > 4


def test_every_routed_edge_survives_rounding():
    from whichcloud.architecture.graph import build_graph
    from whichcloud.architecture.svg import rounded_path

    lay = build_layout(build_graph(_nested_arch()))
    for edge in lay.edges:
        path = rounded_path(edge.points)
        assert path.startswith("M")
        assert str(edge.points[-1][0]) in path


def test_a_container_is_never_narrower_than_its_own_label():
    """Sized from contents alone, an availability zone holding two nearly
    empty subnets came out narrower than the words "Availability Zone 2", so
    the label ran past its border into the zone drawn beside it."""
    from whichcloud.architecture import Architecture
    from whichcloud.architecture.graph import build_graph
    from whichcloud.architecture.layout import LABEL_CHAR_W

    arch = Architecture(
        services=[svc("EC2", "compute")],
        boundaries=[
            Boundary(kind="vpc", name="VPC", contains=["Availability Zone 1"]),
            Boundary(
                kind="az",
                name="Availability Zone 1",
                contains=["Private subnet 1"],
            ),
            Boundary(kind="subnet", name="Private subnet 1", contains=["EC2"]),
        ],
    )
    lay = build_layout(build_graph(arch))

    for group in lay.groups:
        assert group.w >= len(group.label) * LABEL_CHAR_W, (
            f"{group.label!r} is narrower than its own name"
        )


def test_containers_never_overlap_their_siblings():
    """Two zones drawn on top of each other is the failure a reader sees
    first, and it survived every earlier test because they all checked
    nesting rather than separation."""
    from whichcloud.architecture.graph import build_graph

    lay = build_layout(build_graph(_nested_arch()))

    for kind in ("az", "subnet"):
        boxes = [g for g in lay.groups if g.kind == kind]
        for a, b in ((x, y) for i, x in enumerate(boxes) for y in boxes[i + 1 :]):
            apart = (
                a.x + a.w <= b.x
                or b.x + b.w <= a.x
                or a.y + a.h <= b.y
                or b.y + b.h <= a.y
            )
            assert apart, f"{a.label!r} overlaps {b.label!r}"


def test_a_container_holding_nothing_is_not_drawn():
    """Descriptions name subnets they never put anything in. An empty box with
    a label is a rectangle asserting structure the diagram cannot show."""
    from whichcloud.architecture import Architecture
    from whichcloud.architecture.graph import build_graph

    arch = Architecture(
        services=[svc("EC2", "compute")],
        boundaries=[
            Boundary(kind="vpc", name="VPC", contains=["AZ 1", "AZ 2"]),
            Boundary(kind="az", name="AZ 1", contains=["Private subnet 1"]),
            Boundary(kind="az", name="AZ 2", contains=["Private subnet 2"]),
            Boundary(kind="subnet", name="Private subnet 1", contains=["EC2"]),
            Boundary(kind="subnet", name="Private subnet 2", contains=[]),
        ],
    )
    labels = {g.label for g in build_layout(build_graph(arch)).groups}

    assert "Private subnet 1" in labels
    assert "Private subnet 2" not in labels
    assert "AZ 2" not in labels


def test_a_boundary_named_in_two_parents_is_drawn_once():
    """A description saying "a public subnet in each availability zone" names
    one subnet and lists it inside both zones, which makes the boundaries a
    graph rather than a tree. Following every link placed that subnet -- and
    everything in it -- once per zone: six services came out as eighteen
    boxes and the diagram was three times the height of the system."""
    from collections import Counter

    from whichcloud.architecture import Architecture
    from whichcloud.architecture.graph import build_graph

    arch = Architecture(
        services=[svc("ALB", "api"), svc("EC2", "compute")],
        boundaries=[
            Boundary(kind="vpc", name="VPC", contains=["AZ 1", "AZ 2"]),
            # Both zones claim the same two subnets, as a reader writes it.
            Boundary(kind="az", name="AZ 1", contains=["Public subnet", "Private subnet"]),
            Boundary(kind="az", name="AZ 2", contains=["Public subnet", "Private subnet"]),
            Boundary(kind="subnet", name="Public subnet", contains=["ALB"]),
            Boundary(kind="subnet", name="Private subnet", contains=["EC2"]),
        ],
    )
    graph = build_graph(arch)
    lay = build_layout(graph)

    assert len(lay.nodes) == len(graph.nodes) == 2
    assert not [k for k, v in Counter(n.id for n in lay.nodes).items() if v > 1]
    assert not [k for k, v in Counter(g.id for g in lay.groups).items() if v > 1]


def test_the_layout_never_invents_a_node():
    """Whatever the boundaries do, one graph node is one box."""
    from whichcloud.architecture.graph import build_graph

    graph = build_graph(_nested_arch())
    lay = build_layout(graph)

    assert {n.id for n in lay.nodes} == {n.id for n in graph.nodes}


def test_the_actor_is_joined_to_the_system():
    """The figure was drawn beside a boundary with no line into it, so the
    diagram opened with users who touch nothing. Every reference architecture
    begins with exactly that arrow: traffic has to be shown arriving."""
    from whichcloud.architecture.graph import build_graph

    lay = build_layout(build_graph(_nested_arch()))

    assert lay.actor_edge is not None
    assert lay.node(lay.actor_edge.target) is not None
    assert len(lay.actor_edge.points) >= 2


def test_the_actor_arrow_reaches_the_first_box_traffic_touches():
    from whichcloud.architecture import Architecture
    from whichcloud.architecture.graph import build_graph

    arch = Architecture(
        services=[
            svc("CloudFront", "edge", connects=["ELB"], component="Edge"),
            svc("ELB", "api", connects=["ECS"], component="Edge"),
            svc("ECS", "compute", component="App"),
        ]
    )
    lay = build_layout(build_graph(arch))

    assert lay.actor_edge.target == "cloudfront"


def test_the_actor_arrow_is_not_a_numbered_step():
    """It is where traffic arrives, not a step between two services.
    Numbering it shifts every other number by one."""
    from whichcloud.architecture.graph import build_graph

    lay = build_layout(build_graph(_nested_arch()))

    assert lay.actor_edge.step is None
    assert min((e.step for e in lay.edges if e.step), default=1) == 1


def test_the_actor_arrow_moves_with_the_canvas():
    """Translating everything else and leaving it behind detaches it."""
    from whichcloud.architecture.graph import build_graph

    lay = build_layout(build_graph(_nested_arch()))
    target = lay.node(lay.actor_edge.target)

    assert lay.actor_edge.points[-1][0] <= target.x + target.w
    assert all(x >= 0 and y >= 0 for x, y in lay.actor_edge.points)


def test_edge_services_outside_the_network_are_placed_before_it():
    """A CDN is the first thing a request touches. Placing everything outside
    the boundaries underneath sent it to the bottom of the page, so the eye
    went from the users down past the whole VPC, back up into it, and left to
    right from there. A diagram is read in the order it is laid out."""
    from whichcloud.architecture import Architecture
    from whichcloud.architecture.graph import build_graph

    arch = Architecture(
        services=[
            svc("CloudFront", "edge", connects=["ELB"]),
            svc("ELB", "api", connects=["ECS"]),
            svc("ECS", "compute"),
            svc("CloudWatch", "observability", flow="control"),
        ],
        boundaries=[
            Boundary(kind="vpc", name="VPC", contains=["AZ 1"]),
            Boundary(kind="az", name="AZ 1", contains=["Public subnet", "Private subnet"]),
            Boundary(kind="subnet", name="Public subnet", contains=["ELB"]),
            Boundary(kind="subnet", name="Private subnet", contains=["ECS"]),
        ],
    )
    lay = build_layout(build_graph(arch))
    at = {n.label: n.y for n in lay.nodes}
    vpc = next(g for g in lay.groups if g.kind == "vpc")

    assert at["CloudFront"] < vpc.y, "the CDN should meet the request before the network"
    assert at["CloudWatch"] > vpc.y, "telemetry is read after the request path"


def _componentised():
    from whichcloud.architecture import Architecture

    return Architecture(
        services=[
            svc("CloudFront", "edge", connects=["AppSync"], component="Web UI"),
            svc("AppSync", "api", connects=["Lambda"], component="Web UI"),
            svc("Lambda", "compute", connects=["Neptune"], component="Data"),
            svc("Neptune", "data", component="Data"),
            svc("CodeBuild", "cicd", component="Delivery"),
        ],
        boundaries=[
            Boundary(kind="vpc", name="VPC", contains=["Private subnet"]),
            Boundary(kind="subnet", name="Private subnet", contains=["Lambda", "Neptune"]),
        ],
    )


def test_components_survive_a_description_that_has_a_network():
    """Treating the two as alternatives meant a description with a VPC lost
    its functional grouping and became an inventory of where things live
    rather than a picture of what they do. AWS's own diagrams have both."""
    from whichcloud.architecture.graph import build_graph

    lay = build_layout(build_graph(_componentised()))

    assert {c.name for c in lay.components} >= {"Web UI", "Data"}


def test_a_network_boundary_wraps_the_components_inside_it():
    from whichcloud.architecture.graph import build_graph

    lay = build_layout(build_graph(_componentised()))
    subnet = next(g for g in lay.groups if g.kind == "subnet")
    data = next(c for c in lay.components if c.name == "Data")
    web = next(c for c in lay.components if c.name == "Web UI")

    assert subnet.x <= data.x and data.x + data.w <= subnet.x + subnet.w
    assert subnet.y <= data.y and data.y + data.h <= subnet.y + subnet.h
    # And does not swallow one that lives outside the network.
    assert not (subnet.y <= web.y and web.y + web.h <= subnet.y + subnet.h)


def test_a_boundary_is_drawn_once():
    from whichcloud.architecture.graph import build_graph

    lay = build_layout(build_graph(_componentised()))
    ids = [g.id for g in lay.groups]

    assert len(ids) == len(set(ids))
