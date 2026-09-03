"""3-tier, Multi-AZ web application in ap-south-1 (Mumbai).

Layer plan (declared in this order so Graphviz ranks them in flow order):
  L0  Users
  L1  Global edge      Route 53, CloudFront, WAF          - outside the region box
  L2  Region           ap-south-1 (Mumbai)
  L3  VPC              10.0.0.0/16
  L4  Public subnets   IGW, ALB, NAT per AZ
  L5  Private app      web + app tier per AZ
  L6  Private data     RDS + ElastiCache per AZ
  L7  Regional         S3 (outside the VPC, inside the region)

Direction is TB so the two AZs sit SIDE BY SIDE as mirrored columns and the
tiers stack as rows -- the arrangement official AWS multi-AZ diagrams use. It
is what removes the crossings: every edge then runs straight down its own
column instead of reaching across to a shared node.

Two fixes over the naive version:
  * ElastiCache is declared INSIDE each AZ's data subnet rather than once at
    VPC level. A node declared at VPC level with no AZ parent has no rank to
    anchor to and drifts to the cluster edge, and every app->cache edge then
    crosses whichever AZ box lies between them. Multi-AZ ElastiCache really is
    a node per AZ, so this is more accurate as well as cleaner.
  * The AZs are declared with identical internal order, so they render as
    mirror images. Symmetry is what keeps the arrows parallel.
"""

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import ECS, EC2
from diagrams.aws.database import ElastiCache, RDS
from diagrams.aws.network import (
    ELB,
    CloudFront,
    InternetGateway,
    NATGateway,
    Route53,
)
from diagrams.aws.security import WAF
from diagrams.aws.storage import S3
from diagrams.onprem.client import Users

graph_attr = {
    "fontsize": "16",
    "fontname": "Sans-Serif",
    "bgcolor": "white",
    "splines": "ortho",
    "nodesep": "0.75",
    "ranksep": "1.15",
    "pad": "0.6",
    "compound": "true",
    "concentrate": "false",
}
node_attr = {"fontsize": "11", "fontname": "Sans-Serif"}
edge_attr = {"color": "#4A5568", "fontsize": "10", "fontname": "Sans-Serif"}

# AWS-style cluster palettes, per the house rules.
REGION = {"bgcolor": "#F0F8FF", "pencolor": "#232F3E", "style": "dashed", "margin": "22"}
VPC = {"bgcolor": "#E8F5E9", "pencolor": "#248814", "style": "solid", "margin": "22"}
AZ = {"bgcolor": "#F3E5F5", "pencolor": "#147EBA", "style": "dashed", "margin": "20"}
PUBLIC = {"bgcolor": "#E8F6E8", "pencolor": "#248814", "margin": "26"}
PRIVATE = {"bgcolor": "#E6F2FB", "pencolor": "#147EBA", "margin": "26"}
EDGE_SVC = {"bgcolor": "#FFF4E5", "pencolor": "#ED7100", "margin": "18"}

# Flow colours: live request path vs replication vs origin fetch.
REQUEST = "#4A5568"
REPLICATE = "#B0BEC5"

with Diagram(
    "3-Tier Web Application — ap-south-1 (Mumbai), Multi-AZ",
    filename="arch-3tier-ap-south-1",
    show=False,
    direction="LR",
    outformat=["png", "svg"],
    graph_attr=graph_attr,
    node_attr=node_attr,
    edge_attr=edge_attr,
):
    users = Users("Users\n(India)")

    # L1 - genuinely global services, drawn outside the region box.
    with Cluster("Edge / Global Services", graph_attr=EDGE_SVC):
        dns = Route53("Route 53")
        cdn = CloudFront("CloudFront")
        waf = WAF("AWS WAF")

    with Cluster("Region: ap-south-1 (Mumbai)", graph_attr=REGION):
        with Cluster("VPC 10.0.0.0/16", graph_attr=VPC):
            with Cluster("Shared ingress (spans both AZs)", graph_attr=PUBLIC):
                igw = InternetGateway("Internet\nGateway")
                alb = ELB("Application\nLoad Balancer")

            # L4-L6. Both AZs declared with IDENTICAL internal order so they
            # render as mirrored columns.
            # NOTE ON ORDER: with rankdir=LR Graphviz stacks same-rank clusters
            # BOTTOM-UP, so the block declared first lands lowest. ap-south-1b is
            # therefore declared first to make ap-south-1a render on top, which is
            # the order a reader expects. Both AZs keep IDENTICAL internal order
            # (public, app, data) so they render as true mirrors.
            with Cluster("Availability Zone ap-south-1b", graph_attr=AZ):
                with Cluster("Public subnet 10.0.2.0/24", graph_attr=PUBLIC):
                    nat_b = NATGateway("NAT Gateway")
                with Cluster("Private app subnet 10.0.12.0/24", graph_attr=PRIVATE):
                    web_b = EC2("Web tier")
                    app_b = ECS("App tier")
                with Cluster("Private data subnet 10.0.22.0/24", graph_attr=PRIVATE):
                    cache_b = ElastiCache("ElastiCache\nreplica")
                    db_b = RDS("RDS PostgreSQL\nstandby")

            with Cluster("Availability Zone ap-south-1a", graph_attr=AZ):
                with Cluster("Public subnet 10.0.1.0/24", graph_attr=PUBLIC):
                    nat_a = NATGateway("NAT Gateway")
                with Cluster("Private app subnet 10.0.11.0/24", graph_attr=PRIVATE):
                    web_a = EC2("Web tier")
                    app_a = ECS("App tier")
                with Cluster("Private data subnet 10.0.21.0/24", graph_attr=PRIVATE):
                    cache_a = ElastiCache("ElastiCache\nprimary")
                    db_a = RDS("RDS PostgreSQL\nprimary")

        # L7 - regional, outside the VPC. S3 is reached over a gateway
        # endpoint from the app tier and as a CloudFront origin.
        assets = S3("S3\nstatic assets")

    # ---- live request path -------------------------------------------------
    users >> Edge(label="HTTPS 443", color=REQUEST) >> dns
    dns >> Edge(color=REQUEST) >> cdn
    cdn >> Edge(color=REQUEST) >> waf
    waf >> Edge(label="filtered", color=REQUEST) >> igw
    igw >> Edge(color=REQUEST) >> alb

    # Balanced across both AZs -- declared adjacently so the two edges stay
    # parallel rather than fanning.
    alb >> Edge(color=REQUEST) >> web_a
    alb >> Edge(color=REQUEST) >> web_b

    # Each column runs straight down: web -> app -> cache -> db.
    web_a >> Edge(color=REQUEST) >> app_a
    web_b >> Edge(color=REQUEST) >> app_b
    app_a >> Edge(label="cache read", color=REQUEST) >> cache_a
    app_b >> Edge(label="cache read", color=REQUEST) >> cache_b
    app_a >> Edge(color=REQUEST) >> db_a
    app_b >> Edge(color=REQUEST) >> db_b

    # ---- origin fetch and egress ------------------------------------------
    # constraint=false: draw these, but keep them OUT of rank computation.
    # Long-haul and cross-AZ edges are exactly what pulled the two AZ clusters
    # into a diagonal stagger and stretched the canvas to 3800px tall.
    cdn >> Edge(label="origin", color=REQUEST, style="dashed",
                constraint="false") >> assets
    app_a >> Edge(label="VPC endpoint", color=REQUEST, style="dotted",
                  constraint="false") >> assets
    app_b >> Edge(color=REQUEST, style="dotted", constraint="false") >> assets

    # ---- replication / outbound (dashed, muted) ---------------------------
    db_a >> Edge(label="sync", color=REPLICATE, style="dashed",
                 constraint="false") >> db_b
    cache_a >> Edge(label="replica", color=REPLICATE, style="dashed",
                    constraint="false") >> cache_b
    app_a >> Edge(label="outbound", color=REPLICATE, style="dashed",
                  constraint="false") >> nat_a
    app_b >> Edge(label="outbound", color=REPLICATE, style="dashed",
                  constraint="false") >> nat_b
