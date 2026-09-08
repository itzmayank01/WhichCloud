"""Files served to visitors. No application server, no database.

PROBE-1, verbatim:

    "Marketing site for our design studio. About 30,000 visitors a month,
     mostly from India. It's just pages and images, no login, no
     database. We want it cheap."

The engine answered that with a running compute instance ($16.35) and a
relational database ($15.33) -- for a workload whose own description says
"no login, no database" in those words. That is not an expensive static
site; it is a different architecture, and the person who wrote the prompt
had already ruled it out.

CANDIDATE SET
Drawn from AWS's own "Host a static website" reference pattern (S3 origin
behind CloudFront with an Origin Access Control, Route 53 for the apex,
ACM for the certificate) and the Well-Architected cost pillar's guidance
on serving content from the edge rather than from an origin. Nothing here
runs in a VPC, which is why the whole per-hour compute and NAT layer this
engine models simply does not apply.

WHAT THE TIERS BUY
The progression is deliberately about DELIVERY and DURABILITY, because
those are the only axes a static site has:

  cheapest   the origin serves the internet directly. Correct, and
             genuinely the cheapest thing that works at low volume.
  balanced   an edge cache in front of it, so the origin stops paying
             per-GB for every viewer, plus managed keys and a backup.
  optimized  the archive tier for assets nobody fetches, immutability so
             a compromised credential cannot erase the site, a copy in a
             second region, and detection.
"""

from __future__ import annotations

from whichcloud.archetypes.base import (
    ArchetypeGraph, Candidate, Forbidden, SizingDriver,
    has_load_balancer, has_nat_gateway, has_relational_database,
    has_vpc_compute,
)
from whichcloud.estimator import ArchitectureSpec

#: Bytes leaving the origin per page view, when nothing says otherwise.
#: A marketing page with images is the case this shape exists for; 1.8 MB
#: is the HTTP Archive's long-running median page weight, and it is
#: surfaced as an assumption rather than buried.
DEFAULT_PAGE_WEIGHT_MB = 1.8

#: How much of a hot object store a small site actually occupies when it
#: has not said. Deliberately small: the failure mode here is inventing
#: terabytes for a brochure site.
DEFAULT_ASSET_GB = 5.0

#: Share of viewer traffic the origin still serves once an edge cache is
#: in front of it -- cache misses, invalidations and first-in-region
#: fetches. CloudFront's published cache-hit ratios for static content
#: sit well above this; 15% is the conservative end.
ORIGIN_FILL_SHARE = 0.15

#: Fraction of stored bytes old enough to move to an archive class. Only
#: applied at tier 3, and only as a cost optimisation -- an archived
#: object is still served, just more slowly on first fetch.
ARCHIVE_SHARE = 0.4


def _page_views(constraints) -> float:
    """Monthly page views. requests_per_day is already normalised from
    whatever unit the text used -- "30,000 visitors a month" included."""
    return float(constraints.requests_per_day) * 30.0


def _viewer_gb(constraints) -> float:
    """Total bytes reaching viewers per month."""
    if constraints.egress_gb:
        return float(constraints.egress_gb)
    return _page_views(constraints) * DEFAULT_PAGE_WEIGHT_MB / 1024.0


def _asset_gb(constraints) -> float:
    stated = (
        constraints.storage_gb
        or constraints.content_storage_gb
    )
    return float(stated) if stated else DEFAULT_ASSET_GB


def _describe(constraints, load) -> str:
    return (
        f"{_page_views(constraints):,.0f} page views/month against "
        f"{_asset_gb(constraints):,.1f} GB of assets, "
        f"{_viewer_gb(constraints):,.1f} GB reaching viewers"
    )


SIZING = SizingDriver(
    name="page views and asset size",
    fields=("requests_per_day", "storage_gb", "egress_gb"),
    describe=_describe,
)


CANDIDATES = (
    # ── edge: what faces the internet ──
    Candidate("Amazon S3 (website origin)", "store", "storage",
              "Holds the built site — HTML, CSS, images.",
              instead_of="an application server rendering pages per request"),
    Candidate("S3 requests", "store", "s3_requests",
              "Per-GET charge for objects served from the origin."),
    Candidate("Amazon CloudFront", "edge", "cdn",
              "Caches the site at the edge so the origin stops paying "
              "per-GB for every viewer.",
              instead_of="serving every byte from the origin bucket"),
    Candidate("Amazon Route 53", "edge", "dns",
              "The apex domain and its records."),
    Candidate("AWS Certificate Manager", "edge", "tls",
              "TLS certificate for the custom domain. No charge."),
    Candidate("AWS WAF", "edge", "waf",
              "Request filtering, only where the site is a target."),
    Candidate("Origin egress", "edge", "network",
              "Bytes leaving the origin — all of it without a CDN, cache "
              "misses only with one."),
    # ── store / lifecycle ──
    Candidate("S3 Glacier Instant Retrieval", "store", "storage_lifecycle",
              "Archive class for assets nobody fetches any more.",
              instead_of="paying hot-class rates for a 2019 press kit"),
    # ── ops ──
    Candidate("Amazon CloudWatch", "ops", "monitoring",
              "Request and error metrics for the distribution."),
    Candidate("AWS CloudTrail", "ops", "audit",
              "Who changed the bucket or the distribution."),
    # ── security ──
    Candidate("AWS KMS", "security", "kms",
              "Customer-managed key for the bucket."),
    Candidate("Amazon GuardDuty", "security", "threat",
              "Detection on the account holding the site."),
    Candidate("AWS Security Hub", "security", "posture",
              "Whether the bucket is public when it should not be."),
    # ── resilience ──
    Candidate("AWS Backup", "resilience", "backup",
              "A copy of the built site, so a bad deploy is recoverable."),
    Candidate("Cross-region backup copy", "resilience", "backup_copy",
              "The same copy in a second region."),
    Candidate("S3 Object Lock", "resilience", "storage",
              "WORM retention, so a compromised credential cannot erase "
              "the site.",
              instead_of="a backup an attacker with valid keys can delete"),
)


FORBIDDEN = (
    Forbidden(
        "relational database",
        "The description says there is no database. A static site's state "
        "is the files themselves; adding one bills for a server to hold "
        "data nobody stores.",
        has_relational_database,
    ),
    Forbidden(
        "load balancer",
        "There is no origin fleet to balance across. S3 and CloudFront are "
        "each a single endpoint.",
        has_load_balancer,
    ),
    Forbidden(
        "NAT gateway",
        "Nothing runs in a private subnet, so nothing needs a route out "
        "of one. A NAT gateway here is $32/month for an empty VPC.",
        has_nat_gateway,
    ),
    Forbidden(
        "VPC compute",
        "No application server renders these pages. Adding compute makes "
        "this a web application, which is a different archetype with a "
        "different bill.",
        has_vpc_compute,
    ),
)


def build(*, tier_level, constraints, load, region, **_) -> ArchitectureSpec:
    """One tier of a static site.

    Every branch here is a rule over Constraints -- there is no point at
    which a model chooses a service, and the same Constraints produce the
    same spec on every run.
    """
    assets = _asset_gb(constraints)
    viewer_gb = _viewer_gb(constraints)
    page_views = _page_views(constraints)

    edge_cached = tier_level >= 2
    resilient = tier_level >= 3

    # Route the viewer bytes to exactly ONE meter: the edge when a CDN is
    # present, the origin otherwise. Billing both would double-count every
    # byte, which is the error the web_app shape already learned.
    cdn_gb = viewer_gb if edge_cached else 0.0
    origin_gb = viewer_gb * ORIGIN_FILL_SHARE if edge_cached else viewer_gb

    return ArchitectureSpec(
        name=f"tier_{tier_level}",
        region=region,
        # NOTHING RUNS. This is the whole point of the archetype.
        compute_count=0,
        fargate_task_count=0,
        database_vcpu=None,
        database_memory_gb=None,
        load_balancer=False,
        nat_gateway_count=0,
        serves_requests=False,
        # ── the site itself ──
        storage_gb=assets,
        s3_get_requests=page_views,
        egress_gb=origin_gb,
        cdn_gb=cdn_gb,
        cdn_monthly_requests=page_views if edge_cached else 0.0,
        # ── the domain ──
        dns_hosted_zones=1,
        dns_monthly_queries=page_views,
        tls_certificate=True,
        # WAF attaches to the distribution, so it cannot exist before one
        # does -- and it is only bought for a site the public can reach.
        # A private or internal artefact bucket gets neither.
        #
        # Gated on exposure rather than on availability, deliberately.
        # AWS's own static-site reference pattern puts WAF in front of
        # CloudFront, and a filter is a security control: "an hour of
        # downtime is fine" says nothing about whether the site is worth
        # defacing.
        waf_rule_count=3 if (edge_cached and constraints.public_facing) else None,
        waf_monthly_requests=page_views if edge_cached else 0.0,
        # ── ops, on every tier ──
        monitored_metrics=10,
        audit_logging=True,
        # A BACKUP IS NOT A TIER FEATURE. The files ARE the product here:
        # a deleted bucket is a deleted site, and "we can rebuild it from
        # the repo" is a claim only the user can make, not one the engine
        # may assume. Present on every tier unless the text states the
        # data is disposable -- the same rule INV-13 enforces everywhere
        # else, and it caught this archetype getting it wrong.
        backup_gb=0.0 if constraints.durability == "ephemeral" else assets,
        backup_retention_days=(
            0 if constraints.durability == "ephemeral" else 30
        ),
        # ── tier 2: the edge cache, a filter in front of it, managed keys ──
        kms_key_count=1 if edge_cached else None,
        # ── tier 3: archive, immutability, DR, posture ──
        lifecycle_gb=assets * ARCHIVE_SHARE if resilient else 0.0,
        object_lock=resilient,
        backup_copy_gb=assets if resilient else 0.0,
        backup_seed_gb=assets if resilient else 0.0,
        backup_transfer_gb=assets * 0.05 if resilient else 0.0,
        threat_detection=resilient,
        posture_monthly_checks=200.0 if resilient else 0.0,
    )


GRAPH = ArchetypeGraph(
    name="static_site",
    summary="Files served to visitors, with no application server and no "
            "database.",
    sources=(
        "AWS reference pattern: Host a static website (S3 origin + "
        "CloudFront + OAC + Route 53 + ACM)",
        "Well-Architected cost pillar: serve content from the edge rather "
        "than repeatedly from the origin",
        "Well-Architected reliability pillar: versioned, immutable "
        "artefacts for static content",
    ),
    sizing=SIZING,
    candidates=CANDIDATES,
    forbidden=FORBIDDEN,
    build=build,
    tier_notes={
        2: "Delivery: origin serves every byte → CloudFront caches at the "
           "edge — removes the origin paying per-GB for every viewer, and "
           "the latency of a single-region origin serving a global "
           "audience.",
        3: "Durability: a mutable bucket → Object Lock, a second-region "
           "copy and an archive tier — removes a compromised credential "
           "erasing the site, and stops hot-class rates being paid for "
           "assets nobody fetches.",
    },
)
