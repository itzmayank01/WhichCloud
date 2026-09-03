"""Pan-India quick-commerce marketplace — ap-south-1 (Mumbai), Multi-AZ.

Drawn from a WhichCloud priced estimate, so every box on this diagram is a
line item on the bill (AWS "Most optimized" tier, $138,040/mo). Nothing here
is decorative.

Layer plan:
  L0  Users
  L1  Global edge        Route 53, CloudFront, WAF
  L2  Region             ap-south-1 (Mumbai)  — DPDP: all data stays in India
  L3  VPC                10.0.0.0/16
  L4  Shared ingress     IGW, ALB  (spans both AZs)
  L5  Private app        web + app tier per AZ
  L6  Private data       RDS, ElastiCache, OpenSearch per AZ
  L7  Regional services  S3, Redshift, SQS, SNS, SES, Cognito  (outside VPC)
  L8  Governance strip   CloudWatch, CloudTrail, X-Ray, GuardDuty, Security
                         Hub, KMS, Secrets Manager, Backup

Layout notes that matter (learned the hard way on the 3-tier version):
  * constraint="false" on every cross-AZ and long-haul edge. Those edges still
    draw, they just do not vote on rank — without it Graphviz staggers the AZ
    clusters diagonally and stretches the canvas into a tower.
  * With rankdir=LR, same-rank clusters stack BOTTOM-UP, so ap-south-1b is
    declared first to make 1a render on top.
  * Shared data services live inside an AZ, never at VPC level. A node with no
    AZ parent has no rank to anchor to and drifts onto the cluster border.
"""

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.analytics import ElasticsearchService, Redshift
from diagrams.aws.compute import ECS, EC2
from diagrams.aws.database import ElastiCache, RDS
from diagrams.aws.devtools import XRay
from diagrams.aws.engagement import SimpleEmailServiceSes
from diagrams.aws.integration import SNS, SQS
from diagrams.aws.management import Cloudtrail, Cloudwatch
from diagrams.aws.network import (
    ELB,
    CloudFront,
    InternetGateway,
    NATGateway,
    Route53,
)
from diagrams.aws.security import (
    KMS,
    WAF,
    Cognito,
    Guardduty,
    SecretsManager,
    SecurityHub,
)
from diagrams.aws.storage import S3, Backup
from diagrams.onprem.client import Users

graph_attr = {
    "fontsize": "16",
    "fontname": "Sans-Serif",
    "bgcolor": "white",
    "splines": "ortho",
    "nodesep": "0.7",
    "ranksep": "1.1",
    "pad": "0.6",
    "compound": "true",
    "concentrate": "false",
}
node_attr = {"fontsize": "11", "fontname": "Sans-Serif"}
edge_attr = {"color": "#4A5568", "fontsize": "10", "fontname": "Sans-Serif"}

REGION = {"bgcolor": "#F0F8FF", "pencolor": "#232F3E", "style": "dashed", "margin": "22"}
VPC = {"bgcolor": "#E8F5E9", "pencolor": "#248814", "style": "solid", "margin": "22"}
AZ = {"bgcolor": "#F3E5F5", "pencolor": "#147EBA", "style": "dashed", "margin": "20"}
PUBLIC = {"bgcolor": "#E8F6E8", "pencolor": "#248814", "margin": "26"}
PRIVATE = {"bgcolor": "#E6F2FB", "pencolor": "#147EBA", "margin": "26"}
EDGE_SVC = {"bgcolor": "#FFF4E5", "pencolor": "#ED7100", "margin": "18"}
REGIONAL = {"bgcolor": "#EFEBF7", "pencolor": "#7157D9", "margin": "20"}
GOVERN = {"bgcolor": "#FDEEF4", "pencolor": "#E7157B", "margin": "20"}

REQUEST = "#4A5568"
REPLICATE = "#B0BEC5"
SECURITY = "#E7157B"

with Diagram(
    "Quick-Commerce Marketplace — ap-south-1 (Mumbai), Multi-AZ  ·  $138,040/mo",
    filename="arch-marketplace-ap-south-1",
    show=False,
    direction="LR",
    outformat=["png", "svg"],
    graph_attr=graph_attr,
    node_attr=node_attr,
    edge_attr=edge_attr,
):
    users = Users("Customers &\n40k delivery partners")

    with Cluster("Edge / Global Services", graph_attr=EDGE_SVC):
        dns = Route53("Route 53")
        cdn = CloudFront("CloudFront\n400 TB egress")
        waf = WAF("AWS WAF\n10 rules")

    with Cluster(
        "Region: ap-south-1 (Mumbai)  —  DPDP: all customer data resides in India",
        graph_attr=REGION,
    ):
        with Cluster("VPC 10.0.0.0/16", graph_attr=VPC):
            with Cluster("Shared ingress (spans both AZs)", graph_attr=PUBLIC):
                igw = InternetGateway("Internet\nGateway")
                alb = ELB("Application\nLoad Balancer")

            # ap-south-1b declared FIRST so 1a renders on top (LR stacks
            # same-rank clusters bottom-up). Identical internal order = mirror.
            with Cluster("Availability Zone ap-south-1b", graph_attr=AZ):
                with Cluster("Public subnet 10.0.2.0/24", graph_attr=PUBLIC):
                    nat_b = NATGateway("NAT Gateway")
                with Cluster("Private app subnet 10.0.12.0/24", graph_attr=PRIVATE):
                    web_b = EC2("Web tier")
                    app_b = ECS("App tier\n(Fargate)")
                with Cluster("Private data subnet 10.0.22.0/24", graph_attr=PRIVATE):
                    db_b = RDS("RDS PostgreSQL\nstandby")
                    cache_b = ElastiCache("ElastiCache\nreplica")
                    search_b = ElasticsearchService("OpenSearch\n2M SKU catalogue")

            with Cluster("Availability Zone ap-south-1a", graph_attr=AZ):
                with Cluster("Public subnet 10.0.1.0/24", graph_attr=PUBLIC):
                    nat_a = NATGateway("NAT Gateway")
                with Cluster("Private app subnet 10.0.11.0/24", graph_attr=PRIVATE):
                    web_a = EC2("Web tier\n12 × 4 vCPU")
                    app_a = ECS("App tier\n(Fargate)")
                with Cluster("Private data subnet 10.0.21.0/24", graph_attr=PRIVATE):
                    db_a = RDS("RDS PostgreSQL\nprimary 32 vCPU")
                    replicas = RDS("Read replicas\n× 5")
                    cache_a = ElastiCache("ElastiCache\nprimary")
                    search_a = ElasticsearchService("OpenSearch\nprimary")

        # L7 — regional, outside the VPC.
        with Cluster("Regional services", graph_attr=REGIONAL):
            assets = S3("S3\n80 TB media\n(Standard + IA)")
            warehouse = Redshift("Redshift\n4 nodes\nmerchant analytics")
            queue = SQS("SQS\norder events")
            notify = SNS("SNS\npush alerts")
            email = SimpleEmailServiceSes("SES\ntransactional")
            auth = Cognito("Cognito\n8M MAU")

        # L8 — governance and observability strip.
        with Cluster("Security, governance & observability", graph_attr=GOVERN):
            cw = Cloudwatch("CloudWatch")
            trail = Cloudtrail("CloudTrail\naudit")
            xray = XRay("X-Ray\ntracing")
            gd = Guardduty("GuardDuty")
            hub = SecurityHub("Security Hub\nPCI-DSS pack")
            kms = KMS("KMS")
            secrets = SecretsManager("Secrets\nManager")
            backup = Backup("AWS Backup")

    # ---- live request path -------------------------------------------------
    users >> Edge(label="HTTPS 443", color=REQUEST) >> dns
    dns >> Edge(color=REQUEST) >> cdn
    cdn >> Edge(color=REQUEST) >> waf
    waf >> Edge(label="filtered", color=REQUEST) >> igw
    igw >> Edge(color=REQUEST) >> alb
    alb >> Edge(color=REQUEST) >> web_a
    alb >> Edge(color=REQUEST) >> web_b

    web_a >> Edge(color=REQUEST) >> app_a
    web_b >> Edge(color=REQUEST) >> app_b
    app_a >> Edge(color=REQUEST) >> cache_a
    app_b >> Edge(color=REQUEST) >> cache_b
    app_a >> Edge(color=REQUEST) >> db_a
    app_b >> Edge(color=REQUEST) >> db_b
    app_a >> Edge(label="catalogue search", color=REQUEST) >> search_a
    app_b >> Edge(color=REQUEST) >> search_b

    # ---- async / regional (constraint=false: draw, do not rank) ------------
    app_a >> Edge(label="orders", color=REQUEST) >> queue   # anchors Regional
    queue >> Edge(color=REQUEST, constraint="false") >> notify
    app_a >> Edge(color=REQUEST, style="dotted", constraint="false") >> email
    app_a >> Edge(label="sign-in", color=REQUEST, style="dotted",
                  constraint="false") >> auth
    cdn >> Edge(label="origin", color=REQUEST, style="dashed",
                constraint="false") >> assets
    app_a >> Edge(label="VPC endpoint", color=REQUEST, style="dotted",
                  constraint="false") >> assets

    # ---- replication / batch (dashed, muted) ------------------------------
    db_a >> Edge(label="sync", color=REPLICATE, style="dashed",
                 constraint="false") >> db_b
    db_a >> Edge(label="async", color=REPLICATE, style="dashed",
                 constraint="false") >> replicas
    cache_a >> Edge(color=REPLICATE, style="dashed", constraint="false") >> cache_b
    search_a >> Edge(color=REPLICATE, style="dashed", constraint="false") >> search_b
    assets >> Edge(label="nightly ETL", color=REPLICATE, style="dashed",
                   constraint="false") >> warehouse
    db_a >> Edge(label="backup", color=REPLICATE, style="dashed",
                 constraint="false") >> backup
    app_a >> Edge(color=REPLICATE, style="dashed", constraint="false") >> nat_a
    app_b >> Edge(color=REPLICATE, style="dashed", constraint="false") >> nat_b

    # ---- governance (pink dashed, non-ranking) ----------------------------
    app_a >> Edge(color=SECURITY, style="dashed") >> cw   # anchors Governance
    app_a >> Edge(color=SECURITY, style="dashed", constraint="false") >> xray
    db_a >> Edge(color=SECURITY, style="dashed", constraint="false") >> kms
    app_a >> Edge(color=SECURITY, style="dashed", constraint="false") >> secrets
    gd >> Edge(color=SECURITY, style="dashed", constraint="false") >> hub
    trail >> Edge(color=SECURITY, style="dashed", constraint="false") >> hub
    # Nodes in a cluster with no edges between them share a rank, and in LR a
    # shared rank stacks VERTICALLY -- which turned "Regional services" into a
    # 6-high column and the canvas into a 5,200px tower. An invisible chain
    # gives each node its own rank so the cluster lays out as a horizontal
    # strip instead. Same trick for the governance row below.
    assets >> Edge(style="invis") >> warehouse >> Edge(style="invis") >> queue
    queue >> Edge(style="invis") >> notify >> Edge(style="invis") >> email
    email >> Edge(style="invis") >> auth

    cw >> Edge(style="invis") >> trail >> Edge(style="invis") >> xray
    xray >> Edge(style="invis") >> gd >> Edge(style="invis") >> hub
    hub >> Edge(style="invis") >> kms >> Edge(style="invis") >> secrets
    secrets >> Edge(style="invis") >> backup
