"""A laid-out architecture as a standalone SVG file.

Exists so a diagram can leave the browser. An architecture that can only be
looked at on the page it was made on is a demo; one that can be dropped into a
report, a pull request or a slide is a tool. SVG specifically because it opens
in draw.io, Figma and Illustrator as editable shapes rather than a picture of
shapes, so the output is a starting point rather than a dead end.

Rendered here rather than serialised from the browser. The layout already
lives on this side, and reading the DOM back would mean reconstructing
geometry the server computed in the first place -- and would inherit whatever
the viewport happened to be doing at the time.

Logos are deliberately absent. They are fetched by the interface at runtime
from an icon service, and inlining them here would mean either bundling
several hundred marks or making the export wait on a third party. The category
colour carries the same information at a glance, and the service name is
written out in full.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

from whichcloud.architecture.layout import Layout
from whichcloud.architecture.schema import Flow, Tier

#: AWS's published architecture-icon palette, so an exported diagram sits
#: beside one drawn in draw.io without clashing.
TIER_COLOR: dict[Tier, str] = {
    "edge": "#8C4FFF",
    "api": "#8C4FFF",
    "compute": "#ED7100",
    "data": "#C925D1",
    "async": "#E7157B",
    "analytics": "#8C4FFF",
    "ml": "#01A88D",
    "security": "#DD344C",
    "cicd": "#3334B9",
    "observability": "#E7157B",
}

FLOW_STROKE: dict[Flow, tuple[str, str]] = {
    "sync": ("#2F62E8", ""),
    "async": ("#8B5CF6", "7 5"),
    "replication": ("#0EA5E9", "2 4"),
    "control": ("#94A3B8", "1 4"),
}

GROUP_STROKE: dict[str, str] = {
    "account": "#94A3B8",
    "region": "#60A5FA",
    "az": "#34D399",
    "vpc": "#FBBF24",
    "subnet": "#CBD5E1",
}

TIER_LABEL: dict[Tier, str] = {
    "edge": "EDGE",
    "api": "API",
    "compute": "COMPUTE",
    "data": "DATA",
    "async": "ASYNC",
    "analytics": "ANALYTICS",
    "ml": "MACHINE LEARNING",
    "security": "SECURITY",
    "cicd": "DELIVERY",
    "observability": "OBSERVABILITY",
}

#: Roughly the width of one character at 13px in the chosen family. Used only
#: to decide where to break a label; being slightly wrong costs a line break
#: in a marginally different place, not a broken document.
CHAR_W = 6.9


def _wrap(text: str, width: int, limit: int = 2) -> list[str]:
    """Break a label to fit the box, on word boundaries.

    SVG text does not wrap, so any label longer than its box either runs over
    the next one or has to be cut. Breaking it is the only option that keeps
    the whole name readable.
    """
    if not text:
        return []
    per_line = max(1, int(width / CHAR_W))
    words, lines, current = text.split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= per_line:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
        if len(lines) == limit:
            break
    if current and len(lines) < limit:
        lines.append(current)
    if len(lines) == limit and len(" ".join(lines)) < len(text):
        lines[-1] = lines[-1][: max(0, per_line - 1)].rstrip() + "…"
    return lines


def render(layout: Layout, title: str = "Architecture") -> str:
    """The whole diagram, as one self-contained SVG document."""
    out: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{layout.width}" height="{layout.height}" '
        f'viewBox="0 0 {layout.width} {layout.height}">',
        f"<title>{escape(title)}</title>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        "<defs>",
    ]

    for flow, (colour, _) in FLOW_STROKE.items():
        out.append(
            f'<marker id="a-{flow}" viewBox="0 0 10 10" refX="9" refY="5" '
            f'markerWidth="5" markerHeight="5" orient="auto-start-reverse">'
            f'<path d="M0 0 L10 5 L0 10 z" fill="{colour}"/></marker>'
        )
    out.append("</defs>")

    # ── functional components ──
    # Drawn first, so everything else lands on top of them. These are the
    # organising idea of the picture: a reader looking for how search works
    # finds one box holding all of it.
    for component in layout.components:
        out.append(
            f'<rect x="{component.x}" y="{component.y}" width="{component.w}" '
            f'height="{component.h}" rx="12" fill="#FBFCFD" stroke="#9BB4D8" '
            f'stroke-width="1.3" stroke-dasharray="7 5"/>'
        )
        out.append(
            f'<text x="{component.x + 16}" y="{component.y + 22}" '
            f'font-family="system-ui,sans-serif" font-size="14" '
            f'font-weight="600" fill="#4A6285">'
            f"{escape(component.name)} component</text>"
        )

    # ── tier bands ──
    # Only when there are no components to organise the picture instead.
    for i, band in enumerate(layout.bands if not layout.components else []):
        if i % 2 == 1:
            out.append(
                f'<rect x="0" y="{band.y}" width="{layout.width}" '
                f'height="{band.h}" fill="#F6F7F9"/>'
            )
        out.append(
            f'<text x="18" y="{band.y + 14}" font-family="ui-monospace,monospace" '
            f'font-size="11.5" letter-spacing="1.4" fill="#9AA4B2">'
            f"{escape(TIER_LABEL.get(band.tier, band.tier.upper()))}</text>"
        )

    # ── containers, outermost first so nesting lands on top ──
    for group in layout.groups:
        stroke = GROUP_STROKE.get(group.kind, "#CBD5E1")
        out.append(
            f'<rect x="{group.x}" y="{group.y}" width="{group.w}" '
            f'height="{group.h}" rx="14" fill="none" stroke="{stroke}" '
            f'stroke-width="1.4" stroke-dasharray="6 5"/>'
        )
        out.append(
            f'<text x="{group.x + 14}" y="{group.y + 20}" '
            f'font-family="ui-monospace,monospace" font-size="11.5" '
            f'letter-spacing="0.8" fill="{stroke}">'
            f"{escape(group.kind.upper())} · {escape(group.label)}</text>"
        )

    # ── edges, under the boxes so no line crosses a label ──
    for edge in layout.edges:
        colour, dash = FLOW_STROKE.get(edge.flow, FLOW_STROKE["sync"])
        points = " ".join(
            f"{'M' if i == 0 else 'L'}{x} {y}" for i, (x, y) in enumerate(edge.points)
        )
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        out.append(
            f'<path d="{points}" fill="none" stroke="{colour}" stroke-width="1.8"'
            f'{dash_attr} stroke-linecap="round" stroke-linejoin="round" '
            f'marker-end="url(#a-{edge.flow})" opacity="0.8"/>'
        )

    # ── service boxes ──
    for node in layout.nodes:
        colour = TIER_COLOR.get(node.tier, "#64748B")
        out.append(
            f'<rect x="{node.x}" y="{node.y}" width="{node.w}" height="{node.h}" '
            f'rx="11" fill="#ffffff" stroke="#D6DAE1" stroke-width="1.3"/>'
        )
        # The category bar, clipped to the card's rounded top corners.
        out.append(
            f'<path d="M{node.x + 11} {node.y} h{node.w - 22} '
            f"a11 11 0 0 1 11 11 v0 h-{node.w} v0 "
            f'a11 11 0 0 1 11 -11 z" fill="{colour}"/>'
        )

        y = node.y + 26
        for line in _wrap(node.label, node.w - 26, limit=2):
            out.append(
                f'<text x="{node.x + 13}" y="{y}" font-family="system-ui,sans-serif" '
                f'font-size="13.5" font-weight="600" fill="#12161C">'
                f"{escape(line)}</text>"
            )
            y += 16

        for line in _wrap(node.purpose, node.w - 26, limit=1):
            out.append(
                f'<text x="{node.x + 13}" y="{y + 2}" '
                f'font-family="system-ui,sans-serif" font-size="11.5" fill="#6B7480">'
                f"{escape(line)}</text>"
            )
            y += 15

        price = (
            f"${node.monthly_usd:,.2f}/mo"
            if node.priced and node.monthly_usd is not None
            else "not priced"
        )
        out.append(
            f'<text x="{node.x + 13}" y="{node.y + node.h - 10}" '
            f'font-family="ui-monospace,monospace" font-size="10.5" '
            f'fill="{"#1F9D55" if node.priced else "#9AA4B2"}">{escape(price)}</text>'
        )

    out.append("</svg>")
    return "\n".join(out)
