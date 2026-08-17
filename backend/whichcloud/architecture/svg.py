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

Icons are embedded as data URIs rather than linked. An SVG that references
files beside it stops being one file: mail it, drop it in a document, open it
on another machine and the marks are gone. AWS's own icons are vendored in the
frontend's public directory, and the eighty five of them together are smaller
than one screenshot of the diagram they draw.
"""

from __future__ import annotations

import base64
import functools
import re
from pathlib import Path
from xml.sax.saxutils import escape

from whichcloud.architecture.layout import Layout, badge_point
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
    "sync": ("#5A6B7F", ""),
    "async": ("#8B5CF6", "6 4"),
    "replication": ("#0EA5E9", "2 4"),
    "control": ("#AAB4C0", "1 4"),
}

#: AWS's own conventions for the boxes a system sits inside: the VPC is green
#: and solid, subnets are tinted and carry a padlock, regions and availability
#: zones are dashed because they are locations rather than things you can put a
#: boundary on. Each gets a small square badge in its own colour, which is how
#: these are told apart at a glance in AWS's published diagrams.
#:
#: (stroke, fill, dashed, glyph)
GROUP_STYLE: dict[str, tuple[str, str, bool, str]] = {
    "account": ("#232F3E", "none", True, "account"),
    "region": ("#147EBA", "none", True, "region"),
    "vpc": ("#248814", "none", False, "vpc"),
    #: No mark on a zone. In AWS's diagrams it is a dashed outline and a
    #: label, because it is a place rather than a thing you can point at.
    "az": ("#00A4A6", "none", True, ""),
    "subnet": ("#147EBA", "#F2F8FC", False, "private-subnet"),
    #: A public subnet is green in AWS's scheme, a private one blue. The
    #: distinction is the point of drawing them separately at all.
    "subnet-public": ("#248814", "#F2F9F0", False, "public-subnet"),
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

#: Where the official AWS marks are vendored. Shared with the interface, which
#: serves the same files -- one copy, so the page and the export cannot drift
#: into showing different icons for the same service.
ICON_DIR = (
    Path(__file__).resolve().parents[3] / "frontend" / "public" / "icons" / "aws"
)

#: keyword -> vendored filename. Kept in step with lib/serviceIcon.ts, which
#: resolves the same names for the page.
ICON_KEYS: dict[str, str] = {
    "elastic kubernetes": "elastickubernetesservice",
    "elastic container registry": "elasticcontainerregistry",
    "elastic container": "elasticcontainerservice",
    "elastic load balanc": "elasticloadbalancing",
    "elastic beanstalk": "elasticbeanstalk",
    "certificate manager": "certificatemanager",
    "identity and access": "identityandaccessmanagement",
    "key management": "keymanagementservice",
    "secrets manager": "secretsmanager",
    "systems manager": "systemsmanager",
    "storage gateway": "storagegateway",
    "step functions": "stepfunctions",
    "lake formation": "lakeformation",
    "network firewall": "networkfirewall",
    "transit gateway": "transitgateway",
    "direct connect": "directconnect",
    "global accelerator": "globalaccelerator",
    "trusted advisor": "trustedadvisor",
    "control tower": "controltower",
    "nat gateway": "vpcnatgateway",
    "api gateway": "apigateway",
    "auto scaling": "autoscaling",
    "cloudformation": "cloudformation",
    "elasticache": "elasticache",
    "opensearch": "opensearchservice",
    "open search": "opensearchservice",
    "codepipeline": "codepipeline",
    "codeartifact": "codeartifact",
    "cloudfront": "cloudfront",
    "cloudwatch": "cloudwatch",
    "cloudtrail": "cloudtrail",
    "documentdb": "documentdb",
    "eventbridge": "eventbridge",
    "codecommit": "codecommit",
    "codedeploy": "codedeploy",
    "sagemaker": "sagemakerai",
    "rekognition": "rekognition",
    "comprehend": "comprehend",
    "guardduty": "guardduty",
    "securityhub": "securityhub",
    "security hub": "securityhub",
    "beanstalk": "elasticbeanstalk",
    "lightsail": "lightsail",
    "memorydb": "memorydb",
    "keyspaces": "keyspaces",
    "timestream": "timestream",
    "firehose": "datafirehose",
    "cloudhsm": "cloudhsm",
    "codebuild": "codebuild",
    "route 53": "route53",
    "route53": "route53",
    "dynamodb": "dynamodb",
    "redshift": "redshift",
    "inspector": "inspector",
    "amplify": "amplify",
    "appsync": "appsync",
    "aurora": "aurora",
    "athena": "athena",
    "bedrock": "bedrock",
    "backup": "backup",
    "cognito": "cognito",
    "fargate": "fargate",
    "kinesis": "kinesis",
    "neptune": "neptune",
    "textract": "textract",
    "kafka": "managedstreamingforapachekafka",
    "lambda": "lambda",
    "config": "config",
    "batch": "batch",
    "macie": "macie",
    "polly": "polly",
    "redis": "elasticache",
    "shield": "shield",
    "x-ray": "xray",
    "xray": "xray",
    "glue": "glue",
    "msk": "managedstreamingforapachekafka",
    "sqs": "simplequeueservice",
    "sns": "simplenotificationservice",
    "eks": "elastickubernetesservice",
    "ecs": "elasticcontainerservice",
    "ecr": "elasticcontainerregistry",
    "efs": "efs",
    "elb": "elasticloadbalancing",
    "emr": "emr",
    "ec2": "ec2",
    "iam": "identityandaccessmanagement",
    "kms": "keymanagementservice",
    "rds": "rds",
    "vpc": "vpc",
    "waf": "waf",
    "fsx": "fsx",
    "s3": "simplestorageservice",
    "mq": "mq",
}

#: Longest first, so a specific name is never beaten by a substring of it --
#: otherwise "API Gateway" matches "api" and "OpenSearch" loses to "search".
_SORTED_KEYS = sorted(ICON_KEYS, key=len, reverse=True)


@functools.lru_cache(maxsize=256)
def _data_uri(filename: str) -> str | None:
    """The vendored PNG, base64 encoded. Cached: one icon serves many boxes."""
    path = ICON_DIR / f"{filename}.png"
    if not path.exists():
        return None
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def icon_for(label: str) -> str | None:
    """The official mark for this service, embedded, or None if there is none."""
    name = re.sub(r"[^a-z0-9 /-]", " ", label.lower())
    for key in _SORTED_KEYS:
        if key in name:
            return _data_uri(ICON_KEYS[key])
    return None


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


BADGE = 26


#: AWS's own group marks, vendored beside the service icons. These are the
#: exact squares their reference architectures use -- the green VPC cloud, the
#: green padlock on a public subnet, the blue one on a private subnet -- and
#: hand-drawing approximations of them was the last thing separating a diagram
#: from theirs.
GROUP_ICON_DIR = ICON_DIR.parent / "aws-groups"


@functools.lru_cache(maxsize=32)
def _group_uri(name: str) -> str | None:
    path = GROUP_ICON_DIR / f"{name}.png"
    if not path.exists():
        return None
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def _badge(x: int, y: int, colour: str, glyph: str) -> str:
    """A boundary's mark, at the top left of its box.

    AWS's own file where there is one. An availability zone deliberately has
    none: in their diagrams a zone is a dashed outline and a label, because it
    is a place rather than a thing you can point at.
    """
    if not glyph:
        return ""
    uri = _group_uri(glyph)
    if uri:
        return f'<image x="{x}" y="{y}" width="26" height="26" href="{uri}"/>'
    return f'<rect x="{x}" y="{y}" width="23" height="23" rx="4" fill="{colour}"/>'


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

    # ── the provider boundary, and the people outside it ──
    if layout.cloud:
        c = layout.cloud
        out.append(
            f'<rect x="{c.x}" y="{c.y}" width="{c.w}" height="{c.h}" rx="6" '
            f'fill="none" stroke="#232F3E" stroke-width="1.6"/>'
        )
        # The AWS mark: the wordmark in white with the orange smile beneath
        # it, on their navy. Previously this was the word alone in orange,
        # which is not the logo -- the arc is the half people recognise.
        bx, by = c.x + 12, c.y + 10
        out.append(f'<rect x="{bx}" y="{by}" width="42" height="36" rx="7" fill="#232F3E"/>')
        out.append(
            f'<text x="{bx + 21}" y="{by + 19}" text-anchor="middle" '
            f'font-family="system-ui,sans-serif" font-size="15" font-weight="800" '
            f'letter-spacing="-0.5" fill="#ffffff">aws</text>'
        )
        # The smile, which is the half of the logo people recognise.
        out.append(
            f'<path d="M{bx + 8} {by + 25} q 11 8 22 1" fill="none" '
            f'stroke="#FF9900" stroke-width="2.6" stroke-linecap="round"/>'
        )
        out.append(
            f'<path d="M{bx + 26} {by + 23} l5 3.2 l-6 2.6 z" fill="#FF9900"/>'
        )
        out.append(
            f'<text x="{c.x + 66}" y="{c.y + 33}" '
            f'font-family="system-ui,sans-serif" font-size="15" font-weight="600" '
            f'fill="#232F3E">{escape(c.label)}</text>'
        )

    if layout.actor:
        a = layout.actor
        cx = a.x + a.w // 2
        out.append(
            f'<circle cx="{cx}" cy="{a.y + 26}" r="11" fill="none" '
            f'stroke="#5A6B7F" stroke-width="2"/>'
        )
        out.append(
            f'<path d="M{cx - 20} {a.y + 62} a20 20 0 0 1 40 0" fill="none" '
            f'stroke="#5A6B7F" stroke-width="2"/>'
        )
        out.append(
            f'<text x="{cx}" y="{a.y + 84}" text-anchor="middle" '
            f'font-family="system-ui,sans-serif" font-size="13" fill="#3F4B5B">'
            f"{escape(a.label)}</text>"
        )

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
        key = group.kind
        if key == "subnet" and "public" in group.label.lower():
            key = "subnet-public"
        stroke, fill, dashed, glyph = GROUP_STYLE.get(key, GROUP_STYLE["subnet"])

        dash = ' stroke-dasharray="6 5"' if dashed else ""
        out.append(
            f'<rect x="{group.x}" y="{group.y}" width="{group.w}" '
            f'height="{group.h}" rx="4" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="1.5"{dash}/>'
        )
        out.append(_badge(group.x + 10, group.y + 9, stroke, glyph))
        out.append(
            f'<text x="{group.x + 44}" y="{group.y + 27}" '
            f'font-family="system-ui,sans-serif" font-size="13" '
            f'font-weight="600" fill="{stroke}">{escape(group.label)}</text>'
        )

    # ── edges, under the boxes so no line crosses a label ──
    for edge in layout.edges:
        colour, dash = FLOW_STROKE.get(edge.flow, FLOW_STROKE["sync"])
        points = " ".join(
            f"{'M' if i == 0 else 'L'}{x} {y}" for i, (x, y) in enumerate(edge.points)
        )
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        out.append(
            f'<path d="{points}" fill="none" stroke="{colour}" stroke-width="1.4"'
            f'{dash_attr} stroke-linecap="round" stroke-linejoin="round" '
            f'marker-end="url(#a-{edge.flow})" opacity="0.8"/>'
        )

    # ── step numbers ──
    # Placed on the arrow, at the corner where it turns, which is where there
    # is room. AWS numbers these so a reader can follow the sequence rather
    # than merely look at the picture.
    placed_badges: set[tuple[int, int]] = set()
    for edge in sorted(
        (e for e in layout.edges if e.step), key=lambda e: e.step or 0
    ):
        if len(edge.points) < 2:
            continue
        bx, by = badge_point(edge.points, layout.nodes, placed_badges)
        placed_badges.add((bx, by))
        x, y = bx - 11, by - 11
        out.append(
            f'<rect x="{x}" y="{y}" width="22" height="22" rx="4" '
            f'fill="#2F62E8"/>'
        )
        out.append(
            f'<text x="{x + 11}" y="{y + 15}" text-anchor="middle" '
            f'font-family="system-ui,sans-serif" font-size="12" font-weight="700" '
            f'fill="#ffffff">{edge.step}</text>'
        )

    # ── services ──
    # An icon above a centred name, with no box around it. AWS draws services
    # this way and it is most of why their diagrams read as diagrams: the
    # marks are the content, and a card with a border, a fill and a coloured
    # bar puts three pieces of chrome between the reader and each one. The
    # component boxes already do the grouping a card would imply.
    for node in layout.nodes:
        centre = node.x + node.w // 2
        icon = icon_for(node.label)

        if icon:
            out.append(
                f'<image x="{centre - 28}" y="{node.y + 4}" width="56" height="56" '
                f'href="{icon}" preserveAspectRatio="xMidYMid meet"/>'
            )
        else:
            # No official mark: a plain tile in the service's category colour,
            # which says what kind of thing it is without claiming to be a
            # product that is not there.
            colour = TIER_COLOR.get(node.tier, "#64748B")
            out.append(
                f'<rect x="{centre - 26}" y="{node.y + 6}" width="52" height="52" '
                f'rx="9" fill="{colour}" opacity="0.16"/>'
            )
            out.append(
                f'<rect x="{centre - 12}" y="{node.y + 24}" width="24" height="17" '
                f'rx="3" fill="{colour}"/>'
            )

        y = node.y + 76
        for line in _wrap(node.label, node.w + 8, limit=2):
            out.append(
                f'<text x="{centre}" y="{y}" text-anchor="middle" '
                f'font-family="system-ui,sans-serif" font-size="12.5" '
                f'font-weight="600" fill="#232F3E">{escape(line)}</text>'
            )
            y += 15

        if node.priced and node.monthly_usd is not None:
            out.append(
                f'<text x="{centre}" y="{y + 1}" text-anchor="middle" '
                f'font-family="ui-monospace,monospace" font-size="10.5" '
                f'fill="#1F9D55">${node.monthly_usd:,.2f}/mo</text>'
            )

    out.append("</svg>")
    return "\n".join(out)
