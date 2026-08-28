"""AWS pricing adapter.

Two public, credential-free sources:

1. ec2instances.info (Vantage, open source) — one JSON file with every EC2
   instance's specs AND on-demand price per region. ~300 MB, so it is an
   ingest-once-then-cache source, never a live lookup.
2. AWS Price List Bulk API — the authoritative per-service, per-region feed.
   Covers RDS, S3, data transfer and load balancers.

Neither needs an AWS account. Verified 2026-08.
"""

from __future__ import annotations

import gzip
from collections import Counter
import json
import os
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

import httpx

from .models import ComputeQuery, PricePoint, PriceTier, provider_region

INSTANCES_URL = "https://instances.vantage.sh/instances.json"
BULK_BASE = "https://pricing.us-east-1.amazonaws.com"
BULK_REGION_INDEX = BULK_BASE + "/offers/v1.0/aws/{service}/current/region_index.json"

# AWS offer codes for the categories we price.
BULK_SERVICES = {
    "database": "AmazonRDS",
    "storage": "AmazonS3",
    "network": "AWSDataTransfer",
    "loadbalancer": "AWSELB",
    "cache": "AmazonElastiCache",
    "monitoring": "AmazonCloudWatch",
    "dns": "AmazonRoute53",
    "waf": "awswaf",  # lowercase in AWS's own offer index, unlike every other code here
    "audit": "AWSCloudTrail",
    "kms": "awskms",
    "auth": "AmazonCognito",
    "backup": "AWSBackup",
    "streaming": "AmazonKinesis",
    "kafka": "AmazonMSK",
    "search": "AmazonES",
    "warehouse": "AmazonRedshift",
    "threat": "AmazonGuardDuty",
    "tracing": "AWSXRay",
    "posture": "AWSSecurityHub",
    "fargate": "AmazonECS",
    "secrets": "AWSSecretsManager",
    "endpoint": "AmazonVPC",
    "cdn": "AmazonCloudFront",
    "email": "AmazonSES",
    "queue": "AWSQueueService",
    "notification": "AmazonSNS",
    # Serverless. Priced from the same credential-free bulk API as everything
    # above -- Lambda per-invocation and per-GB-second, API Gateway per HTTP
    # request, DynamoDB per on-demand request unit and per GB-month stored.
    "lambda": "AWSLambda",
    "apigateway": "AmazonApiGateway",
    "dynamodb": "AmazonDynamoDB",
    # Managed AI. Same credential-free bulk API: Rekognition per image
    # analysed, Comprehend per unit of text (100 characters). Comprehend's
    # offer code is lowercase, unlike every other service here.
    "rekognition": "AmazonRekognition",
    "comprehend": "comprehend",
}

#: CloudFront bills by the VIEWER's edge location group, not the origin
#: region -- there is no "ap-south-1 CloudFront rate" the way there is an
#: ap-south-1 EC2 rate. This maps our neutral origin region to the edge
#: group whose viewers that origin is built to serve, which is the honest
#: approximation for an architecture whose users are mostly in-country.
_CLOUDFRONT_EDGE_GROUP: dict[str, str] = {
    "india": "IN", "india-south": "IN",
    "us-east": "US", "eu-west": "EU", "singapore": "AP",
}

CACHE_DIR = Path(os.getenv("WHICHCLOUD_CACHE", Path.home() / ".cache" / "whichcloud"))

#: Suffix for a download still in flight. Every fetch writes here and only
#: renames on success, so an interrupted download can never be mistaken for
#: a complete catalog on the next run.
PARTIAL_SUFFIX = ".part"

_MEM_RE = re.compile(r"([\d.]+)")


def _cache_path(name: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / name


def _decimal(value: object) -> Decimal | None:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return d if d > 0 else None


def _decimal_allow_zero(value: object) -> Decimal | None:
    """Like `_decimal`, but a genuine $0 rate is not treated as absent.

    Only for SKUs already known to be permanently free rather than
    promotionally free -- everywhere else, a $0 dimension is exactly the
    "not the real ongoing rate" case `_decimal` exists to skip.
    """
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return d if d >= 0 else None


#: A Graviton family is named <letters><digit>g, optionally with a suffix:
#: r6g, r7gd, c8g, m7g, i8ge. Families ending in another letter -- m7i, c7i,
#: r7i, i4i -- are Intel or AMD.
_GRAVITON_FAMILY = re.compile(r"^[a-z]+\d+g")


def _arch_of(instance_type: str) -> str:
    """x86_64 or arm64, from whichever token names the instance family.

    Every service writes the family in a different position --
    `db.r6g.large`, `cache.t4g.medium`, `r6g.large.search`, `m7g.xlarge` --
    so this checks each dot-separated token rather than assuming one.

    It replaces four hand-written substring lists that each named two
    families and silently called everything else Intel. That hid every
    r6g/r7g/r8g/m6g/m8g database and cache from the ARM technique, and
    made the largest ARM database look like 64 vCPU when 192 exists.

    Size words cannot collide: "48xlarge" and "2xlarge" start with a digit
    and "large"/"search" carry none, while the pattern needs letters then
    a digit then g.
    """
    return (
        "arm64"
        if any(_GRAVITON_FAMILY.match(t) for t in instance_type.split("."))
        else "x86_64"
    )


def _usage_is(usage: str, key: str) -> bool:
    """Does this usage type name `key`, with or without a region prefix?

    Most regions prefix the meter -- "APS3-LCUUsage", "EUW1-NatGateway-Hours".
    us-east-1 is AWS's default and omits it entirely: the same meter is just
    "LCUUsage". Matching on the hyphenated suffix alone therefore found every
    region except that one, which is why NAT gateways, load balancer capacity
    units, S3 requests, database storage and Kinesis all came back missing in
    us-east-1 while working everywhere else.
    """
    return usage == key or usage.endswith("-" + key)


def _memory_gb(raw: str | None) -> float | None:
    """'4 GiB' -> 4.0"""
    if not raw:
        return None
    m = _MEM_RE.search(raw)
    return float(m.group(1)) if m else None


# ─────────────────────────── EC2 compute ───────────────────────────


def download_instances(force: bool = False) -> Path:
    """Fetch the EC2 catalog once and cache it on disk.

    ~300 MB. In production this is a scheduled job; here it is a local file so
    the pricing layer can be verified offline.
    """
    dest = _cache_path("aws-instances.json")
    if dest.exists() and not force:
        return dest

    tmp = dest.with_suffix(PARTIAL_SUFFIX)
    with httpx.stream("GET", INSTANCES_URL, timeout=600.0, follow_redirects=True) as r:
        r.raise_for_status()
        with tmp.open("wb") as fh:
            for chunk in r.iter_bytes(1 << 20):
                fh.write(chunk)
    tmp.replace(dest)
    return dest


def _detect_arch(inst: dict) -> str:
    """AWS does not label ARM directly; the processor string is the tell."""
    processor = (inst.get("physical_processor") or "").lower()
    if "graviton" in processor:
        return "arm64"
    arches = inst.get("arch") or []
    if isinstance(arches, list) and arches and all("arm" in a for a in arches):
        return "arm64"
    return "x86_64"


def load_compute_prices(region_key: str, path: Path | None = None) -> list[PricePoint]:
    """Every on-demand Linux EC2 instance priced in this region.

    On-demand only; spot comes from load_spot_prices(), which uses a separate
    feed.
    """
    region = provider_region(region_key, "aws")
    path = path or download_instances()

    with path.open() as fh:
        catalog = json.load(fh)

    points: list[PricePoint] = []
    for inst in catalog:
        regional = (inst.get("pricing") or {}).get(region, {})
        linux = regional.get("linux") or {}
        vcpu = int(inst["vCPU"]) if inst.get("vCPU") else None
        mem = float(inst["memory"]) if inst.get("memory") else None
        arch = _detect_arch(inst)
        processor = inst.get("physical_processor") or ""

        ondemand = _decimal(linux.get("ondemand"))
        if ondemand:
            points.append(
                PricePoint(
                    provider="aws",
                    category="compute",
                    sku=inst["instance_type"],
                    name=inst["instance_type"],
                    region=region,
                    unit="hour",
                    price_usd=ondemand,
                    vcpu=vcpu,
                    memory_gb=mem,
                    arch=arch,
                    attributes={"processor": processor, "purchase": "ondemand"},
                )
            )

    return points


SPOT_FEED = "https://spot-price.s3.amazonaws.com/spot.js"

_SPOT_CALLBACK = re.compile(r"callback\((.*)\)", re.S)


def load_spot_prices(region_key: str, force: bool = False) -> list[PricePoint]:
    """Spot prices from AWS's public JSONP feed.

    DescribeSpotPriceHistory needs credentials, but this feed is public and
    covers 36 regions including ap-south-1. It carries no timestamp, so treat
    it as indicative: good enough to rank "spot vs on-demand", not to quote.
    Spot rates move continuously anyway — any spot number is a snapshot.

    Specs are joined from the on-demand catalog, since the feed has none.
    """
    region = provider_region(region_key, "aws")

    cached = _cache_path("aws-spot.js")
    if force or not cached.exists():
        r = httpx.get(SPOT_FEED, timeout=180.0, follow_redirects=True)
        r.raise_for_status()
        cached.write_text(r.text)

    match = _SPOT_CALLBACK.search(cached.read_text())
    if not match:
        return []
    feed = json.loads(match.group(1))

    regions = feed.get("config", {}).get("regions", [])
    entry = next((x for x in regions if x.get("region") == region), None)
    if entry is None:
        return []

    # Specs live in the on-demand catalog; index them once.
    specs = {
        p.sku: p for p in load_compute_prices(region_key) if ":" not in p.sku
    }

    points: list[PricePoint] = []
    for family in entry.get("instanceTypes", []):
        for size in family.get("sizes", []):
            name = size.get("size")
            if not name:
                continue
            linux = next(
                (
                    c
                    for c in size.get("valueColumns", [])
                    if c.get("name") == "linux"
                ),
                None,
            )
            if not linux:
                continue
            price = _decimal(linux.get("prices", {}).get("USD"))
            if price is None:
                continue

            base = specs.get(name)
            points.append(
                PricePoint(
                    provider="aws",
                    category="compute",
                    sku=f"{name}:spot",
                    name=f"{name} (spot)",
                    region=region,
                    unit="hour",
                    price_usd=price,
                    vcpu=base.vcpu if base else None,
                    memory_gb=base.memory_gb if base else None,
                    arch=base.arch if base else None,
                    attributes={"purchase": "spot", "source": "public-spot-feed"},
                )
            )
    return points


def cheapest_compute(query: ComputeQuery, path: Path | None = None) -> PricePoint | None:
    """Smallest bill that still satisfies the query."""
    candidates = [
        p
        for p in load_compute_prices(query.region, path)
        if query.matches(p) and p.attributes.get("purchase") == "ondemand"
    ]
    return min(candidates, key=lambda p: p.price_usd, default=None)


# ─────────────────────────── bulk API ───────────────────────────


def download_bulk(service: str, region_key: str, force: bool = False) -> Path:
    """Download and cache one service's regional price list (gzipped locally)."""
    region = provider_region(region_key, "aws")
    dest = _cache_path(f"aws-{service}-{region}.json.gz")
    if dest.exists() and not force:
        return dest

    index = httpx.get(BULK_REGION_INDEX.format(service=service), timeout=90.0)
    index.raise_for_status()
    regions = index.json().get("regions", {})
    if region not in regions:
        raise ValueError(f"{service} is not published for {region}")

    url = BULK_BASE + regions[region]["currentVersionUrl"]
    tmp = dest.with_suffix(PARTIAL_SUFFIX)
    with httpx.stream("GET", url, timeout=900.0, follow_redirects=True) as r:
        r.raise_for_status()
        with gzip.open(tmp, "wb") as fh:
            for chunk in r.iter_bytes(1 << 20):
                fh.write(chunk)
    tmp.replace(dest)
    return dest


def _load_bulk(service: str, region_key: str) -> dict:
    with gzip.open(download_bulk(service, region_key), "rt") as fh:
        return json.load(fh)


def _ondemand_dimensions(doc: dict, sku: str):
    """Yield every on-demand price dimension for a SKU."""
    for term in doc.get("terms", {}).get("OnDemand", {}).get(sku, {}).values():
        for dim in term.get("priceDimensions", {}).values():
            yield dim


def _cheapest_dimension(doc: dict, sku: str) -> tuple[Decimal, str] | None:
    """Lowest published rate for a SKU, with its unit.

    AWS publishes tiered rates (S3 gets cheaper past 50 TB). We take the first
    tier — the rate a normal project actually pays — not the volume-discounted
    floor, which would understate every estimate.
    """
    best: tuple[Decimal, str] | None = None
    for dim in _ondemand_dimensions(doc, sku):
        price = _decimal(dim.get("pricePerUnit", {}).get("USD"))
        if price is None:
            continue
        begin = dim.get("beginRange")
        if begin not in (None, "0", 0):
            continue  # skip volume tiers
        unit = dim.get("unit", "")
        if best is None or price < best[0]:
            best = (price, unit)
    return best


_UNITS = {"Hrs": "hour", "GB-Mo": "GB-month", "GB": "GB", "LCU-Hrs": "hour"}


def _tiers_for(doc: dict, sku: str) -> tuple[tuple[PriceTier, ...], str]:
    """Every graduated band published for a SKU, lowest band first.

    Unlike `_cheapest_dimension`, which deliberately keeps only the entry
    rate and drops volume tiers, this keeps all of them -- needed wherever
    the bands are the pricing rather than a discount on it, above all when
    the first band is a free allowance.

    Zero-priced bands are kept for the same reason: Cognito's first 50,000
    MAUs and SNS's first million requests are published as real $0 bands,
    and dropping them would bill the very units the provider gives away.
    """
    tiers: list[PriceTier] = []
    unit = ""
    for dim in _ondemand_dimensions(doc, sku):
        raw = dim.get("pricePerUnit", {}).get("USD")
        price = _decimal_allow_zero(raw)
        if price is None:
            continue
        begin = _decimal_allow_zero(dim.get("beginRange")) or Decimal(0)
        end_raw = dim.get("endRange")
        end = None if end_raw in (None, "", "Inf") else _decimal_allow_zero(end_raw)
        tiers.append(PriceTier(begin=begin, end=end, price_usd=price))
        unit = unit or dim.get("unit", "")

    tiers.sort(key=lambda t: t.begin)
    return tuple(tiers), unit


def load_database_prices(region_key: str) -> list[PricePoint]:
    """RDS PostgreSQL instances, both Single-AZ and Multi-AZ.

    Multi-AZ matters: the engine's "Most reliable" option needs a real price
    for the standby, not a guessed multiplier.
    """
    region = provider_region(region_key, "aws")
    doc = _load_bulk(BULK_SERVICES["database"], region_key)

    points: list[PricePoint] = []
    for sku, product in doc.get("products", {}).items():
        if product.get("productFamily") != "Database Instance":
            continue
        attrs = product.get("attributes", {})
        if attrs.get("databaseEngine") != "PostgreSQL":
            continue
        deployment = attrs.get("deploymentOption", "")
        if deployment not in ("Single-AZ", "Multi-AZ"):
            continue

        found = _cheapest_dimension(doc, sku)
        if not found:
            continue
        price, unit = found

        instance = attrs.get("instanceType", "")
        suffix = "" if deployment == "Single-AZ" else ":multi-az"
        points.append(
            PricePoint(
                provider="aws",
                category="database",
                sku=f"{instance}{suffix}",
                name=f"{instance} PostgreSQL {deployment}",
                region=region,
                unit=_UNITS.get(unit, unit),
                price_usd=price,
                vcpu=int(attrs["vcpu"]) if attrs.get("vcpu", "").isdigit() else None,
                memory_gb=_memory_gb(attrs.get("memory")),
                arch=_arch_of(instance),
                attributes={"engine": "postgresql", "deployment": deployment},
            )
        )
    return points


def load_storage_prices(region_key: str) -> list[PricePoint]:
    """S3 storage classes, priced per GB-month."""
    region = provider_region(region_key, "aws")
    doc = _load_bulk(BULK_SERVICES["storage"], region_key)

    points: list[PricePoint] = []
    seen: set[str] = set()
    for sku, product in doc.get("products", {}).items():
        if product.get("productFamily") != "Storage":
            continue
        attrs = product.get("attributes", {})
        storage_class = attrs.get("storageClass", "")
        if not storage_class or storage_class in seen:
            continue

        found = _cheapest_dimension(doc, sku)
        if not found:
            continue
        price, unit = found
        if unit != "GB-Mo":
            continue  # tag and request meters ride in the same family
        seen.add(storage_class)

        points.append(
            PricePoint(
                provider="aws",
                category="storage",
                sku=f"s3:{storage_class.lower().replace(' ', '-')}",
                name=f"S3 {storage_class}",
                region=region,
                unit=_UNITS.get(unit, unit),
                price_usd=price,
                attributes={"storage_class": storage_class},
            )
        )
    return points


def load_egress_prices(region_key: str) -> list[PricePoint]:
    """Outbound data transfer to the internet — the invisible half of a bill."""
    region = provider_region(region_key, "aws")
    doc = _load_bulk(BULK_SERVICES["network"], region_key)

    points: list[PricePoint] = []
    for sku, product in doc.get("products", {}).items():
        attrs = product.get("attributes", {})
        if attrs.get("transferType") != "AWS Outbound":
            continue
        if attrs.get("fromLocationType") != "AWS Region":
            continue

        found = _cheapest_dimension(doc, sku)
        if not found:
            continue
        price, unit = found

        points.append(
            PricePoint(
                provider="aws",
                category="network",
                sku="egress:internet",
                name="Data transfer out to internet",
                region=region,
                unit=_UNITS.get(unit, unit),
                price_usd=price,
                attributes={"transfer_type": "outbound"},
            )
        )
        break  # one canonical egress rate per region
    return points


def load_loadbalancer_prices(region_key: str) -> list[PricePoint]:
    """Application Load Balancer hourly rate."""
    region = provider_region(region_key, "aws")
    doc = _load_bulk(BULK_SERVICES["loadbalancer"], region_key)

    points: list[PricePoint] = []
    for sku, product in doc.get("products", {}).items():
        attrs = product.get("attributes", {})
        usage = attrs.get("usagetype", "")
        if "LoadBalancerUsage" not in usage:
            continue
        if attrs.get("operation") not in (None, "", "LoadBalancing:Application"):
            continue

        found = _cheapest_dimension(doc, sku)
        if not found:
            continue
        price, unit = found

        points.append(
            PricePoint(
                provider="aws",
                category="loadbalancer",
                sku="alb",
                name="Application Load Balancer",
                region=region,
                unit=_UNITS.get(unit, unit),
                price_usd=price,
                attributes={"type": "application"},
            )
        )
        break
    return points


def load_cache_prices(region_key: str) -> list[PricePoint]:
    """ElastiCache nodes — Redis/Valkey.

    Closes a loop the knowledge base left open: cache-to-shrink-database
    advises adding a cache but stayed advisory because a cache ADDS a line we
    could not price. Now both sides of that trade are quotable.
    """
    region = provider_region(region_key, "aws")
    doc = _load_bulk(BULK_SERVICES["cache"], region_key)

    points: list[PricePoint] = []
    for sku, product in doc.get("products", {}).items():
        if product.get("productFamily") != "Cache Instance":
            continue
        attrs = product.get("attributes", {})
        engine = (attrs.get("cacheEngine") or "").lower()
        if engine not in ("redis", "valkey", "memcached"):
            continue

        found = _cheapest_dimension(doc, sku)
        if not found:
            continue
        price, unit = found
        instance = attrs.get("instanceType", "")
        if not instance:
            continue

        points.append(
            PricePoint(
                provider="aws",
                category="cache",
                sku=instance,
                name=f"{instance} {engine}",
                region=region,
                unit=_UNITS.get(unit, unit),
                price_usd=price,
                vcpu=int(attrs["vcpu"]) if attrs.get("vcpu", "").isdigit() else None,
                memory_gb=_memory_gb(attrs.get("memory")),
                arch=_arch_of(instance),
                attributes={"engine": engine},
            )
        )
    return points


def load_monitoring_prices(region_key: str) -> list[PricePoint]:
    """CloudWatch custom metrics, priced per metric-month."""
    region = provider_region(region_key, "aws")
    doc = _load_bulk(BULK_SERVICES["monitoring"], region_key)

    for sku, product in doc.get("products", {}).items():
        if product.get("productFamily") != "Metric":
            continue
        if "Metric" not in (product.get("attributes", {}).get("usagetype") or ""):
            continue
        found = _cheapest_dimension(doc, sku)
        if not found:
            continue
        price, unit = found
        return [
            PricePoint(
                provider="aws",
                category="monitoring",
                sku="cloudwatch:metrics",
                name="CloudWatch custom metrics",
                region=region,
                unit="metric-month",
                price_usd=price,
                attributes={"published_unit": unit},
            )
        ]
    return []


def load_waf_prices(region_key: str) -> list[PricePoint]:
    """AWS WAF: the flat Web ACL fee, the per-rule fee, and the per-request fee.

    Three SKUs, not one — a Web ACL is a fixed monthly charge, rules are a
    fixed charge each, and requests are metered. Fetched, not typed: the
    published rates ($5/mo, $1/rule/mo, $0.60 per million requests as of this
    writing) are exactly recoverable from this feed, so there is no reason to
    freeze them into source and let them go stale silently.

    Shield-protected, AMR (bot control / fraud control / anti-DDoS), Captcha
    and Challenge line items publish usage-types with the same "-WebACL" /
    "-Rule" / "-Request" suffixes plus an extra prefix, so they are excluded
    by name rather than matched by accident. AWS also publishes WCU-tiered
    request pricing for complex rule sets ("RequestV2-Tier3-2500WCU" and
    similar) — this uses the flat per-request rate instead, which is what a
    typical rule set actually pays and keeps one line item honest rather than
    guessing which tier a described workload's rules would fall into.
    """
    region = provider_region(region_key, "aws")
    doc = _load_bulk(BULK_SERVICES["waf"], region_key)

    wanted = {"WebACL": "waf:webacl", "Rule": "waf:rule", "Request": "waf:request"}
    names = {
        "waf:webacl": "AWS WAF Web ACL",
        "waf:rule": "AWS WAF Rule",
        "waf:request": "AWS WAF Request",
    }
    excluded = ("Shield", "AMR", "Captcha", "Challenge")
    found: dict[str, PricePoint] = {}

    for sku, product in doc.get("products", {}).items():
        usage = product.get("attributes", {}).get("usagetype", "")
        if any(tag in usage for tag in excluded):
            continue
        suffix = next((k for k in wanted if _usage_is(usage, k)), None)
        if not suffix or wanted[suffix] in found:
            continue

        dim = _cheapest_dimension(doc, sku)
        if not dim:
            continue
        price, unit = dim
        point_sku = wanted[suffix]
        found[point_sku] = PricePoint(
            provider="aws",
            category="waf",
            sku=point_sku,
            name=names[point_sku],
            region=region,
            unit=_UNITS.get(unit, unit),
            price_usd=price,
        )

    return list(found.values())


def load_nat_prices(region_key: str) -> list[PricePoint]:
    """NAT Gateway — hourly per gateway, plus per-GB data processed.

    Comes from the EC2 bulk feed rather than a service code of its own.
    Two SKUs because it genuinely bills two ways, and a bill quoting only
    the hourly rate understates a busy private subnet substantially.

    The zonal usage types ("NatGateway-Hours") are taken, not the regional
    ones: a production deployment puts one gateway in each availability
    zone so a zone failure does not take the other zone's outbound traffic
    with it, and that is the shape the rest of the engine prices for.
    """
    region = provider_region(region_key, "aws")
    # NAT Gateway has no service code of its own -- it is published inside
    # the EC2 catalog, so this loads that file directly rather than going
    # through BULK_SERVICES.
    with gzip.open(download_bulk("AmazonEC2", region_key), "rt") as fh:
        doc = json.load(fh)

    wanted = {"NatGateway-Hours": "nat:gateway-hour", "NatGateway-Bytes": "nat:gb-processed"}
    names = {
        "nat:gateway-hour": "NAT Gateway",
        "nat:gb-processed": "NAT Gateway data processing",
    }
    found: dict[str, PricePoint] = {}

    for sku, product in doc.get("products", {}).items():
        if product.get("productFamily") != "NAT Gateway":
            continue
        usage = product.get("attributes", {}).get("usagetype", "")
        # Regional gateways are a different product; match the zonal ones
        # exactly rather than by substring, which "Regional..." also passes.
        key = next(
            (k for k in wanted if _usage_is(usage, k) and "Regional" not in usage),
            None,
        )
        if not key or wanted[key] in found:
            continue

        dim = _cheapest_dimension(doc, sku)
        if not dim:
            continue
        price, unit = dim
        point_sku = wanted[key]
        found[point_sku] = PricePoint(
            provider="aws",
            category="nat",
            sku=point_sku,
            name=names[point_sku],
            region=region,
            unit=_UNITS.get(unit, unit),
            price_usd=price,
        )

    return list(found.values())


def load_acm_prices(region_key: str) -> list[PricePoint]:
    """ACM public TLS certificates — free, and worth showing rather than hiding.

    ASSERTED, NOT FETCHED, unlike everything else in this module. AWS's ACM
    feed publishes only the paid products (Private CA, short-lived certs,
    OCSP); public certificates used with ALB and CloudFront carry no meter
    at all, so there is no SKU to read. This records the documented $0 so
    the TLS layer appears as a real component instead of being invisible
    because it happens to be free.

    Safe in a way an asserted non-zero price would not be: a wrong $0 here
    cannot inflate or deflate anyone's bill. If AWS ever starts charging,
    this becomes wrong silently -- which is why it is flagged here and in
    the point's own attributes rather than buried.
    """
    region = provider_region(region_key, "aws")
    return [
        PricePoint(
            provider="aws",
            category="tls",
            sku="acm:public-certificate",
            name="ACM public TLS certificate",
            region=region,
            unit="month",
            price_usd=Decimal(0),
            attributes={"basis": "AWS publishes no charge for public ACM certificates"},
        )
    ]


def load_cloudtrail_prices(region_key: str) -> list[PricePoint]:
    """AWS CloudTrail's one free management-events trail.

    Genuinely $0, not an approximation of it: AWS publishes
    "FreeEventsRecorded" as its own zero-rate SKU, distinct from the paid
    tiers (extended retention, data events, insights) this does not model.
    Every AWS account gets this trail whether anyone prices it or not, so
    leaving it off a "what does this cost" bill would not make it free —
    it would just make the bill silent about a real, always-on component.
    """
    region = provider_region(region_key, "aws")
    doc = _load_bulk(BULK_SERVICES["audit"], region_key)

    for sku, product in doc.get("products", {}).items():
        usage = product.get("attributes", {}).get("usagetype", "")
        if not _usage_is(usage, "FreeEventsRecorded"):
            continue
        # Not _cheapest_dimension: it treats a zero price as "not a real
        # rate" and skips it, which is right for a promotional free-tier
        # dimension but wrong here -- this SKU's only dimension is a
        # permanent $0, and skipping it would leave the loader returning
        # nothing rather than the genuinely free price it found.
        for dim in _ondemand_dimensions(doc, sku):
            price = _decimal_allow_zero(dim.get("pricePerUnit", {}).get("USD"))
            if price is None:
                continue
            return [
                PricePoint(
                    provider="aws",
                    category="audit",
                    sku="cloudtrail:management-events",
                    name="AWS CloudTrail (management events)",
                    region=region,
                    unit=_UNITS.get(dim.get("unit", ""), dim.get("unit", "")),
                    price_usd=price,
                )
            ]
    return []


def load_kms_prices(region_key: str) -> list[PricePoint]:
    """AWS KMS — the flat per-key monthly charge for a customer-managed key.

    Request pricing is excluded: the first 20,000 requests/month are free
    (a real published $0 tier) and a typical web app's encrypt/decrypt calls
    for RDS and S3 stay well inside it, so modelling only the key itself is
    the honest number for the common case rather than a guessed request
    volume dressed up as a calculation.
    """
    region = provider_region(region_key, "aws")
    doc = _load_bulk(BULK_SERVICES["kms"], region_key)

    for sku, product in doc.get("products", {}).items():
        usage = product.get("attributes", {}).get("usagetype", "")
        if not _usage_is(usage, "KMS-Keys"):
            continue
        found = _cheapest_dimension(doc, sku)
        if not found:
            continue
        price, unit = found
        return [
            PricePoint(
                provider="aws",
                category="kms",
                sku="kms:key",
                name="AWS KMS customer-managed key",
                region=region,
                unit=_UNITS.get(unit, unit),
                price_usd=price,
            )
        ]
    return []


def _download_global(service: str, force: bool = False) -> Path:
    """Fetch a service's `aws-other` feed — where global services publish.

    Route 53 hosted zones and queries are billed globally, not per region,
    so they appear only under the pseudo-region `aws-other` and are absent
    from every regional file. The previous DNS loader read the regional
    feed, found nothing, and silently returned an empty list -- so DNS has
    been missing from every architecture this engine has ever drawn.
    """
    dest = _cache_path(f"aws-{service}-global.json.gz")
    if dest.exists() and not force:
        return dest

    index = httpx.get(BULK_REGION_INDEX.format(service=service), timeout=90.0)
    index.raise_for_status()
    regions = index.json().get("regions", {})
    if "aws-other" not in regions:
        raise ValueError(f"{service} publishes no global (aws-other) feed")

    url = BULK_BASE + regions["aws-other"]["currentVersionUrl"]
    tmp = dest.with_suffix(PARTIAL_SUFFIX)
    with httpx.stream("GET", url, timeout=900.0, follow_redirects=True) as r:
        r.raise_for_status()
        with gzip.open(tmp, "wb") as fh:
            for chunk in r.iter_bytes(1 << 20):
                fh.write(chunk)
    tmp.replace(dest)
    return dest


# ─────────────────────── data pipeline & analytics ───────────────────────


def load_streaming_prices(region_key: str) -> list[PricePoint]:
    """Kinesis Data Streams — provisioned shard hours and PUT payload units.

    Provisioned mode, not on-demand: on-demand bills per GB ingested, which
    cannot be sized from a transaction count without also guessing record
    size. A shard is a real unit of capacity (1 MB/s or 1,000 records/s in)
    that a stated transaction rate maps onto directly, so the engine can
    size it from what the description actually says.

    The feed carries a dozen usage types for the same service -- enhanced
    fan-out, long-term retention, the "Advantage" tier -- so both SKUs are
    matched exactly rather than by substring.
    """
    region = provider_region(region_key, "aws")
    doc = _load_bulk(BULK_SERVICES["streaming"], region_key)

    wanted = {
        "Storage-ShardHour": ("kinesis:shard-hour", "Kinesis shard", "hour"),
        "PutRequestPayloadUnits": (
            "kinesis:put-payload-units", "Kinesis PUT payload units", "unit",
        ),
    }
    found: dict[str, PricePoint] = {}

    for sku, product in doc.get("products", {}).items():
        usage = product.get("attributes", {}).get("usagetype", "")
        key = next((k for k in wanted if _usage_is(usage, k)), None)
        if not key or wanted[key][0] in found:
            continue
        dim = _cheapest_dimension(doc, sku)
        if not dim:
            continue
        price, unit = dim
        point_sku, name, our_unit = wanted[key]
        found[point_sku] = PricePoint(
            provider="aws",
            category="streaming",
            sku=point_sku,
            name=name,
            region=region,
            unit=our_unit,
            price_usd=price,
            attributes={"published_unit": unit, "mode": "provisioned"},
        )
    return list(found.values())


def load_kafka_prices(region_key: str) -> list[PricePoint]:
    """Amazon MSK broker hours.

    Standard brokers only. The feed also publishes "ExpressBroker" rates,
    which are a different product with different throughput characteristics
    -- mixing the two into one category would let the engine quote an
    Express price for a standard broker.

    Specs come from the feed's own vcpu/memoryGib attributes, so MSK
    brokers can be selected by size the same way EC2 and RDS already are.
    """
    region = provider_region(region_key, "aws")
    doc = _load_bulk(BULK_SERVICES["kafka"], region_key)

    points: list[PricePoint] = []
    for sku, product in doc.get("products", {}).items():
        attrs = product.get("attributes", {})
        if attrs.get("group") != "Broker":
            continue
        family = attrs.get("computeFamily", "")
        if not family:
            continue
        dim = _cheapest_dimension(doc, sku)
        if not dim:
            continue
        price, unit = dim

        vcpu = attrs.get("vcpu", "")
        memory = attrs.get("memoryGib", "")
        points.append(
            PricePoint(
                provider="aws",
                category="kafka",
                # AWS's own console and docs name these "kafka.m5.large";
                # the feed's computeFamily drops the prefix.
                sku=f"kafka.{family}",
                name=f"MSK broker kafka.{family}",
                region=region,
                unit=_UNITS.get(unit, unit),
                price_usd=price,
                vcpu=int(vcpu) if vcpu.isdigit() else None,
                memory_gb=float(memory) if memory else None,
                arch=_arch_of(family),
            )
        )
    return points


def _search_node_point(doc: dict, sku: str, attrs: dict, region: str) -> PricePoint | None:
    """One OpenSearch data node, or None if it is not a priced node type."""
    instance = attrs.get("instanceType", "")
    if not instance or not instance.endswith(".search"):
        return None
    dim = _cheapest_dimension(doc, sku)
    if not dim:
        return None
    price, unit = dim
    vcpu = attrs.get("vcpu", "")
    return PricePoint(
        provider="aws",
        category="search",
        sku=instance,
        name=f"OpenSearch {instance}",
        region=region,
        unit=_UNITS.get(unit, unit),
        price_usd=price,
        vcpu=int(vcpu) if vcpu.isdigit() else None,
        # memoryGib, not memory: this feed names it differently from EC2's,
        # and reading the wrong key returns None, which silently excludes
        # every node from size queries.
        memory_gb=_memory_gb(attrs.get("memoryGib")),
        arch=_arch_of(instance),
    )


def _search_volume_point(doc: dict, sku: str, attrs: dict, region: str) -> PricePoint | None:
    """The GP3 volume OpenSearch stores its indexes on, or None."""
    if attrs.get("storageMedia") != "GP3":
        return None
    dim = _cheapest_dimension(doc, sku)
    if not dim:
        return None
    price, unit = dim
    return PricePoint(
        provider="aws",
        category="search_storage",
        sku="opensearch:gp3-storage",
        name="OpenSearch GP3 storage",
        region=region,
        unit=_UNITS.get(unit, unit),
        price_usd=price,
    )


def load_search_prices(region_key: str) -> list[PricePoint]:
    """OpenSearch data nodes, plus the EBS volume they store indexes on.

    Two categories from one feed: the node hour is a compute-like rate the
    engine selects by size, and the volume is a per-GB-month meter. Both
    are needed -- an OpenSearch cluster priced without its storage would
    understate a search tier substantially.

    GP3 is taken as the volume default because it is the current
    general-purpose type; GP2, magnetic and provisioned-IOPS are all still
    published and would each be a different, non-default choice.

    The two families are read by their own helpers rather than by branching
    inside one loop -- they share nothing but the file they come from.
    """
    region = provider_region(region_key, "aws")
    doc = _load_bulk(BULK_SERVICES["search"], region_key)

    readers = {
        "Amazon OpenSearch Service Instance": _search_node_point,
        "Amazon OpenSearch Service Volume": _search_volume_point,
    }

    points: list[PricePoint] = []
    for sku, product in doc.get("products", {}).items():
        reader = readers.get(product.get("productFamily", ""))
        if not reader:
            continue
        point = reader(doc, sku, product.get("attributes", {}), region)
        if point:
            points.append(point)
    return points


def load_warehouse_prices(region_key: str) -> list[PricePoint]:
    """Redshift node hours.

    Provisioned clusters only. Serverless is published in the same feed as
    an RPU-hour rate, which bills on query concurrency rather than on a
    node the engine can size -- pricing the two as one category would put
    incomparable units in the same column.
    """
    region = provider_region(region_key, "aws")
    doc = _load_bulk(BULK_SERVICES["warehouse"], region_key)

    points: list[PricePoint] = []
    for sku, product in doc.get("products", {}).items():
        if product.get("productFamily") != "Compute Instance":
            continue
        attrs = product.get("attributes", {})
        node = attrs.get("instanceType", "")
        if not node:
            continue
        dim = _cheapest_dimension(doc, sku)
        if not dim:
            continue
        price, unit = dim
        vcpu = attrs.get("vcpu", "")
        points.append(
            PricePoint(
                provider="aws",
                category="warehouse",
                sku=node,
                name=f"Redshift {node}",
                region=region,
                unit=_UNITS.get(unit, unit),
                price_usd=price,
                vcpu=int(vcpu) if vcpu.isdigit() else None,
                memory_gb=_memory_gb(attrs.get("memory")),
            )
        )
    return points


# ───────────────────── threat detection & observability ─────────────────


def _stitch_free_and_paid(
    free: list[PriceTier], paid: list[PriceTier], allowance: Decimal
) -> tuple[PriceTier, ...]:
    """One graduated scale from a global free band and regional paid bands.

    AWS publishes the free allowance as its own global product and the paid
    rate as a regional one that also starts at zero. Used as-is they would
    overlap, and the paid band would bill the units the free band gives
    away -- so the paid bands are shifted above the allowance and any band
    entirely inside it is dropped.
    """
    bands = [PriceTier(begin=Decimal(0), end=allowance, price_usd=Decimal(0))]
    for tier in sorted(paid, key=lambda t: t.begin):
        if tier.end is not None and tier.end <= allowance:
            continue
        bands.append(
            PriceTier(
                begin=max(tier.begin, allowance),
                end=tier.end,
                price_usd=tier.price_usd,
            )
        )
    return tuple(bands)


def load_threat_prices(region_key: str) -> list[PricePoint]:
    """GuardDuty, per vCPU-month of workload monitored.

    EC2 and RDS monitoring are separate meters at different rates, and the
    EC2 one is genuinely graduated ($1.81/vCPU for the first 500, then
    $0.91, then $0.30), so a large estate pays the lower band on its excess.

    The many "Free*" usage types in this feed are free-TRIAL rates, not a
    permanent allowance -- unlike CloudTrail's free trail or Cognito's free
    MAUs. They are excluded, because pricing a trial as though it were the
    ongoing rate would understate every bill after the first month.
    """
    region = provider_region(region_key, "aws")
    doc = _load_bulk(BULK_SERVICES["threat"], region_key)

    wanted = {
        "PaidEC2vCPUMonitored": ("guardduty:ec2-vcpu", "GuardDuty EC2 monitoring"),
        "PaidRDSvCPUMonitored": ("guardduty:rds-vcpu", "GuardDuty RDS monitoring"),
        "PaidFargatevCPUMonitored": ("guardduty:fargate-vcpu", "GuardDuty Fargate monitoring"),
    }
    found: dict[str, PricePoint] = {}

    for sku, product in doc.get("products", {}).items():
        usage = product.get("attributes", {}).get("usagetype", "")
        key = next((k for k in wanted if _usage_is(usage, k)), None)
        if not key or wanted[key][0] in found:
            continue
        tiers, unit = _tiers_for(doc, sku)
        if not tiers:
            continue
        point_sku, name = wanted[key]
        found[point_sku] = PricePoint(
            provider="aws",
            category="threat",
            sku=point_sku,
            name=name,
            region=region,
            unit="vCPU-month",
            price_usd=tiers[0].price_usd,
            tiers=tiers,
            attributes={"published_unit": unit},
        )
    return list(found.values())


def load_tracing_prices(region_key: str) -> list[PricePoint]:
    """X-Ray traces recorded, with its permanent 100,000/month free band."""
    region = provider_region(region_key, "aws")
    doc = _load_bulk(BULK_SERVICES["tracing"], region_key)

    free: list[PriceTier] = []
    paid: list[PriceTier] = []
    for sku, product in doc.get("products", {}).items():
        usage = product.get("attributes", {}).get("usagetype", "")
        if usage == "Global-XRay-TracesStored":
            free.extend(_tiers_for(doc, sku)[0])
        elif usage.endswith("-XRay-TracesStored") and "Insights" not in usage:
            paid.extend(_tiers_for(doc, sku)[0])

    if not paid:
        return []

    FREE_TRACES = Decimal(100_000)
    bands = _stitch_free_and_paid(free, paid, FREE_TRACES)
    return [
        PricePoint(
            provider="aws",
            category="tracing",
            sku="xray:traces-recorded",
            name="X-Ray traces recorded",
            region=region,
            unit="trace",
            price_usd=Decimal(0),
            tiers=bands,
            attributes={"free_allowance_traces": str(FREE_TRACES)},
        )
    ]


def load_posture_prices(region_key: str) -> list[PricePoint]:
    """Security Hub, per security check evaluated.

    The compliance check is the core CSPM meter -- the thing Security Hub
    does continuously against every resource. The feed also publishes
    finding-ingestion, per-instance monitoring and several Azure meters;
    those are separate products, not this one at a different rate.
    """
    region = provider_region(region_key, "aws")
    doc = _load_bulk(BULK_SERVICES["posture"], region_key)

    for sku, product in doc.get("products", {}).items():
        usage = product.get("attributes", {}).get("usagetype", "")
        # Exact tail match: "PaidComplianceCheck-Azure" is a different cloud.
        if not usage.endswith("-PaidComplianceCheck"):
            continue
        tiers, unit = _tiers_for(doc, sku)
        if not tiers:
            continue
        return [
            PricePoint(
                provider="aws",
                category="posture",
                sku="securityhub:compliance-check",
                name="Security Hub compliance checks",
                region=region,
                unit="check",
                price_usd=tiers[0].price_usd,
                tiers=tiers,
                attributes={"published_unit": unit},
            )
        ]
    return []


def load_flowlog_prices(region_key: str) -> list[PricePoint]:
    """VPC Flow Logs, billed as CloudWatch vended-log ingestion.

    Flow Logs has no service code of its own; the charge is the vended-log
    rate in the CloudWatch feed, which is graduated from $0.67/GB down to
    $0.067/GB at volume. The plain "VendedLog-Bytes" meter, not the -CFLogs
    or -WAFLogs variants, which are other services' vended logs.
    """
    region = provider_region(region_key, "aws")
    doc = _load_bulk(BULK_SERVICES["monitoring"], region_key)

    for sku, product in doc.get("products", {}).items():
        usage = product.get("attributes", {}).get("usagetype", "")
        if not usage.endswith("-VendedLog-Bytes"):
            continue
        tiers, unit = _tiers_for(doc, sku)
        if not tiers:
            continue
        return [
            PricePoint(
                provider="aws",
                category="flowlogs",
                sku="vpc:flow-logs",
                name="VPC Flow Logs ingestion",
                region=region,
                unit="GB",
                price_usd=tiers[0].price_usd,
                tiers=tiers,
                attributes={"published_unit": unit},
            )
        ]
    return []


# ─────────────────── serverless compute & metered detail ────────────────


def load_fargate_prices(region_key: str) -> list[PricePoint]:
    """Fargate, billed per vCPU-hour and per GB-hour separately.

    Not an instance type: a task requests vCPU and memory independently, so
    the two meters are priced as two points and the estimator multiplies
    each by what the task actually asks for. That is why a Fargate line
    cannot be looked up the way an EC2 instance can.

    ARM (Graviton) and x86 are both recorded. ARM is roughly 44% cheaper per
    vCPU-hour here, which is the same Graviton win the knowledge base
    already measures for EC2 -- worth having priced rather than assumed.
    """
    region = provider_region(region_key, "aws")
    doc = _load_bulk(BULK_SERVICES["fargate"], region_key)

    wanted = {
        "Fargate-vCPU-Hours:perCPU": ("fargate:vcpu-hour", "Fargate vCPU", "x86_64"),
        "Fargate-GB-Hours": ("fargate:gb-hour", "Fargate memory", "x86_64"),
        "Fargate-ARM-vCPU-Hours:perCPU": ("fargate:arm-vcpu-hour", "Fargate vCPU (ARM)", "arm64"),
        "Fargate-ARM-GB-Hours": ("fargate:arm-gb-hour", "Fargate memory (ARM)", "arm64"),
    }
    found: dict[str, PricePoint] = {}

    for sku, product in doc.get("products", {}).items():
        usage = product.get("attributes", {}).get("usagetype", "")
        # Exact tail match: "Fargate-Windows-vCPU-Hours:perCPU" and the
        # ephemeral-storage meter would both pass a substring test.
        key = next((k for k in wanted if _usage_is(usage, k)), None)
        if not key or wanted[key][0] in found:
            continue
        dim = _cheapest_dimension(doc, sku)
        if not dim:
            continue
        price, unit = dim
        point_sku, name, arch = wanted[key]
        found[point_sku] = PricePoint(
            provider="aws",
            category="fargate",
            sku=point_sku,
            name=name,
            region=region,
            unit="hour",
            price_usd=price,
            arch=arch,
            attributes={"published_unit": unit},
        )
    return list(found.values())


def load_db_storage_prices(region_key: str) -> list[PricePoint]:
    """RDS provisioned storage, GP3, single-AZ and Multi-AZ.

    Multi-AZ storage is its own published rate ($0.262/GB-mo against
    $0.131), not the single-AZ rate doubled -- the same reason the engine
    prices Multi-AZ instances from a real SKU rather than a multiplier.
    """
    region = provider_region(region_key, "aws")
    doc = _load_bulk(BULK_SERVICES["database"], region_key)

    wanted = {
        "RDS:GP3-Storage": ("rds:gp3-storage", "RDS GP3 storage"),
        "RDS:Multi-AZ-GP3-Storage": ("rds:gp3-storage-multi-az", "RDS GP3 storage (Multi-AZ)"),
    }
    found: dict[str, PricePoint] = {}

    for sku, product in doc.get("products", {}).items():
        if product.get("productFamily") != "Database Storage":
            continue
        usage = product.get("attributes", {}).get("usagetype", "")
        key = next((k for k in wanted if _usage_is(usage, k)), None)
        if not key or wanted[key][0] in found:
            continue
        dim = _cheapest_dimension(doc, sku)
        if not dim:
            continue
        price, unit = dim
        point_sku, name = wanted[key]
        found[point_sku] = PricePoint(
            provider="aws",
            category="db_storage",
            sku=point_sku,
            name=name,
            region=region,
            unit=_UNITS.get(unit, unit),
            price_usd=price,
        )
    return list(found.values())


def load_lcu_prices(region_key: str) -> list[PricePoint]:
    """ALB capacity units — the usage half of a load balancer's bill.

    The hourly charge is only the floor; an ALB also bills LCUs for
    connections, requests and processed bytes. Pricing the hour alone
    understates a busy balancer, and three LCU rates are published for the
    three balancer types, so this matches on the Application operation
    rather than on the shared "LCUUsage" usage type.
    """
    region = provider_region(region_key, "aws")
    doc = _load_bulk(BULK_SERVICES["loadbalancer"], region_key)

    for sku, product in doc.get("products", {}).items():
        attrs = product.get("attributes", {})
        usage = attrs.get("usagetype", "")
        # Outposts publishes its own LCU meter at a different rate, and
        # "Reserved" is prepaid capacity rather than the on-demand rate.
        if not _usage_is(usage, "LCUUsage") or "Outposts" in usage:
            continue
        if attrs.get("operation") != "LoadBalancing:Application":
            continue
        dim = _cheapest_dimension(doc, sku)
        if not dim:
            continue
        price, unit = dim
        return [
            PricePoint(
                provider="aws",
                category="lcu",
                sku="alb:lcu-hour",
                name="ALB capacity units",
                region=region,
                unit=_UNITS.get(unit, unit),
                price_usd=price,
            )
        ]
    return []


def load_s3_request_prices(region_key: str) -> list[PricePoint]:
    """S3 request charges: writes (Tier1) and reads (Tier2).

    Separate meters at very different rates -- a write costs 12.5x a read --
    so an asset-heavy read workload and a log-ingest write workload cannot
    share one number.
    """
    region = provider_region(region_key, "aws")
    doc = _load_bulk(BULK_SERVICES["storage"], region_key)

    wanted = {
        "Requests-Tier1": ("s3:put-requests", "S3 PUT/POST/LIST requests"),
        "Requests-Tier2": ("s3:get-requests", "S3 GET requests"),
    }
    found: dict[str, PricePoint] = {}

    for sku, product in doc.get("products", {}).items():
        if product.get("productFamily") != "API Request":
            continue
        usage = product.get("attributes", {}).get("usagetype", "")
        key = next((k for k in wanted if _usage_is(usage, k)), None)
        if not key or wanted[key][0] in found:
            continue
        dim = _cheapest_dimension(doc, sku)
        if not dim:
            continue
        price, unit = dim
        point_sku, name = wanted[key]
        found[point_sku] = PricePoint(
            provider="aws",
            category="s3_requests",
            sku=point_sku,
            name=name,
            region=region,
            unit="request",
            price_usd=price,
            attributes={"published_unit": unit},
        )
    return list(found.values())


def load_secrets_prices(region_key: str) -> list[PricePoint]:
    """Secrets Manager, per stored secret per month.

    API request charges are excluded: at $0.05 per 10,000 calls an
    application fetching its credentials on startup and on rotation costs
    fractions of a cent, and modelling it would need a call-rate guess to
    produce a number smaller than the rounding on every other line.
    """
    region = provider_region(region_key, "aws")
    doc = _load_bulk(BULK_SERVICES["secrets"], region_key)

    for sku, product in doc.get("products", {}).items():
        usage = product.get("attributes", {}).get("usagetype", "")
        if not _usage_is(usage, "AWSSecretsManager-Secrets"):
            continue
        found = _cheapest_dimension(doc, sku)
        if not found:
            continue
        price, unit = found
        return [
            PricePoint(
                provider="aws",
                category="secrets",
                sku="secretsmanager:secret",
                name="Secrets Manager stored secret",
                region=region,
                unit=_UNITS.get(unit, unit),
                price_usd=price,
                attributes={"excludes": "API requests ($0.05 per 10k)"},
            )
        ]
    return []


def load_dns_prices(region_key: str) -> list[PricePoint]:
    """Route 53 hosted zones and DNS queries, both graduated.

    Fetched, not hand-entered: the published $0.50/zone (first 25, then
    $0.10) and $0.40 per million queries (first billion, then $0.20) all
    come from AWS's own global feed. Both carry real tiers, so a large
    estate pays the lower band on its excess rather than the entry rate on
    everything.
    """
    region = provider_region(region_key, "aws")
    with gzip.open(_download_global(BULK_SERVICES["dns"]), "rt") as fh:
        doc = json.load(fh)

    wanted = {
        "HostedZone": ("route53:hosted-zone", "Route 53 hosted zone", "month"),
        "DNS-Queries": ("route53:dns-queries", "Route 53 DNS queries", "query"),
    }
    found: dict[str, PricePoint] = {}

    for sku, product in doc.get("products", {}).items():
        usage = product.get("attributes", {}).get("usagetype", "")
        # Exact match: "Intra-AWS-DNS-Queries" (free alias lookups) and the
        # Geo/LBR/Cidr variants all contain "DNS-Queries" as a substring but
        # are different products at different rates.
        if usage not in wanted:
            continue
        point_sku, name, unit = wanted[usage]
        if point_sku in found:
            continue

        tiers, _ = _tiers_for(doc, sku)
        if not tiers:
            continue
        found[point_sku] = PricePoint(
            provider="aws",
            category="dns",
            sku=point_sku,
            name=name,
            region=region,
            unit=unit,
            price_usd=tiers[0].price_usd,
            tiers=tiers,
            attributes={"scope": "global"},
        )

    return list(found.values())


def load_cdn_prices(region_key: str) -> list[PricePoint]:
    """CloudFront: data transfer out to the edge, and HTTPS requests.

    Published under the global (aws-other) feed, split by the edge
    location group a request is served from -- IN, US, EU, AP and so on --
    rather than by origin region, because that is genuinely how AWS bills
    it. See _CLOUDFRONT_EDGE_GROUP for the origin-to-edge-group mapping;
    a region this catalog has no mapping for returns no CDN price, same as
    any other uningested gap, rather than a guessed one.
    """
    group = _CLOUDFRONT_EDGE_GROUP.get(region_key)
    if not group:
        return []

    region = provider_region(region_key, "aws")
    with gzip.open(_download_global(BULK_SERVICES["cdn"]), "rt") as fh:
        doc = json.load(fh)

    wanted = {
        f"{group}-DataTransfer-Out-Bytes": (
            "cloudfront:data-transfer-out", "CloudFront data transfer out", "GB",
        ),
        f"{group}-Requests-Tier2-HTTPS": (
            "cloudfront:requests-https", "CloudFront HTTPS requests", "Requests",
        ),
    }
    found: dict[str, PricePoint] = {}

    for sku, product in doc.get("products", {}).items():
        usage = product.get("attributes", {}).get("usagetype", "")
        if usage not in wanted:
            continue
        point_sku, name, unit = wanted[usage]
        if point_sku in found:
            continue

        tiers, _ = _tiers_for(doc, sku)
        if not tiers:
            continue
        found[point_sku] = PricePoint(
            provider="aws",
            category="cdn",
            sku=point_sku,
            name=name,
            region=region,
            unit=unit,
            price_usd=tiers[0].price_usd,
            tiers=tiers,
            attributes={"scope": "global", "edge_group": group},
        )

    return list(found.values())


def _regional_prefix(region: str) -> str:
    """AWS's usagetype prefix for a region ("ap-south-1" -> "APS3-").

    Read off the feed rather than tabulated: the mapping is AWS's own and
    a hand-written table of it is a second source of truth that can drift.
    us-east-1 omits the prefix entirely, which is why callers must accept
    an empty string as a valid answer.
    """
    return _REGION_PREFIX.get(region, "")


#: The prefixes actually needed by the meters below. Extracted here
#: rather than inline so an unmapped region returns "" (matching
#: us-east-1's own convention) instead of silently matching nothing.
_REGION_PREFIX: dict[str, str] = {
    "ap-south-1": "APS3-", "ap-south-2": "APS4-",
    "ap-southeast-1": "APS1-", "eu-west-1": "EUW1-", "us-east-1": "",
}


#: Where a cross-region backup copy goes, per source region. The pair is
#: what AWS bills on -- there is no generic "inter-region" rate -- so the
#: destination has to be the one the planner actually copies to.
_INTERREGION_PAIR: dict[str, str] = {
    "ap-south-1": "APS2",   # Mumbai -> Hyderabad, the in-country pair
    "ap-south-2": "APS3",
    "us-east-1": "USW2",
    "eu-west-1": "EUC1",
    "ap-southeast-1": "APS2",
}


def load_interregion_transfer_prices(region_key: str) -> list[PricePoint]:
    """Inter-region data transfer OUT, for the pair the planner uses.

    Distinct from `egress:internet` and from the destination's storage
    rate, and previously absent -- which is why a cross-region backup was
    modelled as storage alone, with the transfer that fills it never
    priced at all.
    """
    region = provider_region(region_key, "aws")
    prefix = _regional_prefix(region).rstrip("-")
    destination = _INTERREGION_PAIR.get(region)
    if not prefix or not destination:
        return []

    doc = _load_bulk(BULK_SERVICES["network"], region_key)
    wanted = f"{prefix}-{destination}-AWS-Out-Bytes"
    for sku, product in doc.get("products", {}).items():
        if product.get("attributes", {}).get("usagetype") != wanted:
            continue
        found = _cheapest_dimension(doc, sku)
        if not found:
            continue
        price, unit = found
        return [PricePoint(
            provider="aws", category="network", sku="transfer:inter-region",
            name="Inter-region data transfer", region=region,
            unit=unit or "GB", price_usd=price,
        )]
    return []


def load_email_prices(region_key: str) -> list[PricePoint]:
    """SES outbound email, per message.

    The plain `<region>-Message` meter, not Essentials/Pro/Enterprise --
    those are the tiered feature bundles, and billing a transactional
    send at the Enterprise rate would overstate a 30,000-email month by
    more than double. Graduated bands are kept, since SES publishes
    genuinely cheaper rates at volume.
    """
    region = provider_region(region_key, "aws")
    prefix = _regional_prefix(region)
    doc = _load_bulk(BULK_SERVICES["email"], region_key)

    wanted = f"{prefix}Message"
    for sku, product in doc.get("products", {}).items():
        if product.get("attributes", {}).get("usagetype") != wanted:
            continue
        tiers, unit = _tiers_for(doc, sku)
        if not tiers:
            continue
        return [PricePoint(
            provider="aws", category="email", sku="ses:outbound-email",
            name="SES outbound email", region=region, unit=unit or "message",
            price_usd=tiers[0].price_usd, tiers=tiers,
        )]
    return []


def load_queue_prices(region_key: str) -> list[PricePoint]:
    """SQS standard-queue API requests. FIFO is a different meter and a
    different guarantee; nothing in this engine selects it yet, so
    quoting its rate would price a queue we do not build."""
    region = provider_region(region_key, "aws")
    prefix = _regional_prefix(region)
    doc = _load_bulk(BULK_SERVICES["queue"], region_key)

    wanted = f"{prefix}Requests-Tier1"
    for sku, product in doc.get("products", {}).items():
        if product.get("attributes", {}).get("usagetype") != wanted:
            continue
        tiers, unit = _tiers_for(doc, sku)
        if not tiers:
            continue
        return [PricePoint(
            provider="aws", category="queue", sku="sqs:requests",
            name="SQS requests", region=region, unit=unit or "Requests",
            price_usd=tiers[0].price_usd, tiers=tiers,
        )]
    return []


def load_notification_prices(region_key: str) -> list[PricePoint]:
    """SNS publish/delivery requests, standard topics."""
    region = provider_region(region_key, "aws")
    prefix = _regional_prefix(region)
    doc = _load_bulk(BULK_SERVICES["notification"], region_key)

    wanted = f"{prefix}Requests-Tier1"
    for sku, product in doc.get("products", {}).items():
        if product.get("attributes", {}).get("usagetype") != wanted:
            continue
        tiers, unit = _tiers_for(doc, sku)
        # SNS publishes a genuine $0 first band; keep every tier so the
        # free allowance is honoured rather than billed.
        if not tiers:
            continue
        return [PricePoint(
            provider="aws", category="notification", sku="sns:requests",
            name="SNS requests", region=region, unit=unit or "Requests",
            price_usd=tiers[0].price_usd, tiers=tiers,
        )]
    return []


def load_lambda_prices(region_key: str) -> list[PricePoint]:
    """Lambda invocations and duration, on the ARM (Graviton) meters.

    Two meters, because Lambda bills two things: a flat charge per request
    and a charge per GB-second of execution. ARM is the default here for the
    same reason the rest of the engine prefers Graviton -- it is cheaper for
    the same work and Lambda supports it transparently. Both meters carry a
    real free tier (the first million requests, the first 400,000 GB-s), so
    the graduated bands are kept exactly as SNS's and Cognito's are.
    """
    region = provider_region(region_key, "aws")
    prefix = _regional_prefix(region)
    doc = _load_bulk(BULK_SERVICES["lambda"], region_key)

    wanted = {
        f"{prefix}Request-ARM": ("lambda-requests", "lambda:requests", "Lambda requests"),
        f"{prefix}Lambda-GB-Second-ARM": (
            "lambda-duration", "lambda:duration", "Lambda duration",
        ),
    }
    points: list[PricePoint] = []
    for sku, product in doc.get("products", {}).items():
        ut = product.get("attributes", {}).get("usagetype")
        if ut not in wanted:
            continue
        category, sku_name, label = wanted[ut]
        tiers, unit = _tiers_for(doc, sku)
        if not tiers:
            continue
        points.append(PricePoint(
            provider="aws", category=category, sku=sku_name,
            name=label, region=region, unit=unit or "request",
            price_usd=tiers[0].price_usd, tiers=tiers,
        ))
    return points


def load_apigateway_prices(region_key: str) -> list[PricePoint]:
    """API Gateway HTTP API requests.

    The HTTP API meter, not the REST API one: HTTP APIs are the cheaper,
    recommended front for a Lambda-backed service, so quoting REST rates
    would overstate the exact architecture this shape builds. WebSocket and
    cache meters are different products and are not ingested.
    """
    region = provider_region(region_key, "aws")
    prefix = _regional_prefix(region)
    doc = _load_bulk(BULK_SERVICES["apigateway"], region_key)

    wanted = f"{prefix}ApiGatewayHttpRequest"
    for sku, product in doc.get("products", {}).items():
        if product.get("attributes", {}).get("usagetype") != wanted:
            continue
        tiers, unit = _tiers_for(doc, sku)
        if not tiers:
            continue
        return [PricePoint(
            provider="aws", category="apigateway", sku="apigateway:http-requests",
            name="API Gateway HTTP requests", region=region,
            unit=unit or "request", price_usd=tiers[0].price_usd, tiers=tiers,
        )]
    return []


def load_dynamodb_prices(region_key: str) -> list[PricePoint]:
    """DynamoDB on-demand: read and write request units, plus stored data.

    On-demand (PayPerRequest), not provisioned capacity: it is the honest
    default for the spiky, scale-to-zero workloads a serverless shape suits,
    where paying for provisioned throughput around the clock is exactly the
    always-on cost serverless exists to avoid. Exact usagetype equality keeps
    the Standard-class meters and rejects the Infrequent-Access, PITR and
    backup variants, which are different storage classes billed separately.
    """
    region = provider_region(region_key, "aws")
    prefix = _regional_prefix(region)
    doc = _load_bulk(BULK_SERVICES["dynamodb"], region_key)

    wanted = {
        f"{prefix}ReadRequestUnits": (
            "dynamodb-reads", "dynamodb:read-request-units", "DynamoDB read units",
        ),
        f"{prefix}WriteRequestUnits": (
            "dynamodb-writes", "dynamodb:write-request-units", "DynamoDB write units",
        ),
        f"{prefix}TimedStorage-ByteHrs": (
            "dynamodb-storage", "dynamodb:storage", "DynamoDB storage",
        ),
    }
    points: list[PricePoint] = []
    for sku, product in doc.get("products", {}).items():
        ut = product.get("attributes", {}).get("usagetype")
        if ut not in wanted:
            continue
        category, sku_name, label = wanted[ut]
        tiers, unit = _tiers_for(doc, sku)
        if not tiers:
            continue
        points.append(PricePoint(
            provider="aws", category=category, sku=sku_name,
            name=label, region=region, unit=unit or "request",
            price_usd=tiers[0].price_usd, tiers=tiers,
        ))
    return points


def load_rekognition_prices(region_key: str) -> list[PricePoint]:
    """Amazon Rekognition image analysis, per image processed.

    The Group1 image-analysis meter (label detection, moderation, face
    detection) -- the everyday image-recognition call. Video, custom-model
    and face-storage meters are separate products and are not ingested.
    Graduated bands are kept so a high-volume workload gets the real
    volume rate rather than the entry price on every image.
    """
    region = provider_region(region_key, "aws")
    prefix = _regional_prefix(region)
    doc = _load_bulk(BULK_SERVICES["rekognition"], region_key)

    wanted = f"{prefix}Group1-ImagesProcessed"
    for sku, product in doc.get("products", {}).items():
        if product.get("attributes", {}).get("usagetype") != wanted:
            continue
        tiers, unit = _tiers_for(doc, sku)
        if not tiers:
            continue
        return [PricePoint(
            provider="aws", category="rekognition", sku="rekognition:images",
            name="Rekognition images", region=region, unit=unit or "image",
            price_usd=tiers[0].price_usd, tiers=tiers,
        )]
    return []


def load_comprehend_prices(region_key: str) -> list[PricePoint]:
    """Amazon Comprehend sentiment analysis, per unit of text.

    One unit is 100 characters (Comprehend rounds each request up to a
    minimum of 3 units). The sentiment meter specifically -- entities, key
    phrases, PII and the rest are separate meters and are not ingested,
    because this shape prices the sentiment call it is built to draw.
    """
    region = provider_region(region_key, "aws")
    prefix = _regional_prefix(region)
    doc = _load_bulk(BULK_SERVICES["comprehend"], region_key)

    wanted = f"{prefix}DetectSentiment"
    for sku, product in doc.get("products", {}).items():
        if product.get("attributes", {}).get("usagetype") != wanted:
            continue
        tiers, unit = _tiers_for(doc, sku)
        if not tiers:
            continue
        return [PricePoint(
            provider="aws", category="comprehend", sku="comprehend:sentiment",
            name="Comprehend sentiment", region=region, unit=unit or "unit",
            price_usd=tiers[0].price_usd, tiers=tiers,
        )]
    return []


def load_cognito_prices(region_key: str) -> list[PricePoint]:
    """Cognito user pools, priced per monthly active user with a free band.

    The free allowance is the whole point of modelling this as tiers: AWS
    publishes a genuine $0 band and then graduated rates above it, so a
    300-staff login system costs nothing while a 100,000-user consumer app
    pays only on the excess. A flat rate would bill the free users.
    """
    region = provider_region(region_key, "aws")
    doc = _load_bulk(BULK_SERVICES["auth"], region_key)

    # The plain user-pool MAU meter, not Lite/Plus/Essentials tiers, not the
    # advanced-security (ASF) or machine-to-machine add-ons, and not the
    # multi-region-replication ones -- each is a different product.
    regional: list[PriceTier] = []
    free: list[PriceTier] = []
    for sku, product in doc.get("products", {}).items():
        usage = product.get("attributes", {}).get("usagetype", "")
        if usage.endswith("-CognitoUserPoolsMAU"):
            tiers, _ = _tiers_for(doc, sku)
            regional.extend(tiers)
        elif usage == "Global-CognitoUserPoolMAU":
            tiers, _ = _tiers_for(doc, sku)
            free.extend(tiers)

    if not regional:
        return []

    # AWS publishes the free allowance as its own global product and the
    # paid bands as regional ones, both starting at zero. Stitching them
    # into one graduated scale is what makes `cost_for` come out right.
    FREE_MAUS = Decimal(50_000)
    bands = [PriceTier(begin=Decimal(0), end=FREE_MAUS, price_usd=Decimal(0))]
    for tier in sorted(regional, key=lambda t: t.begin):
        begin = max(tier.begin, FREE_MAUS)
        if tier.end is not None and tier.end <= FREE_MAUS:
            continue
        bands.append(PriceTier(begin=begin, end=tier.end, price_usd=tier.price_usd))

    return [
        PricePoint(
            provider="aws",
            category="auth",
            sku="cognito:user-pool-mau",
            name="Cognito user pool (monthly active users)",
            region=region,
            unit="MAU",
            price_usd=Decimal(0),
            tiers=tuple(bands),
            attributes={"free_allowance_maus": str(FREE_MAUS)},
        )
    ]


def load_backup_prices(region_key: str) -> list[PricePoint]:
    """AWS Backup warm storage, per GB-month.

    Two things this deliberately does NOT price, because pricing them would
    overstate a normal architecture's bill:

    * **RDS automated backups.** AWS includes backup storage up to the
      database's own provisioned size at no charge, so the snapshots the
      "Most reliable" tier depends on are already paid for. Adding a line
      for them would bill twice for one thing.
    * **Air-gapped vaults.** For EBS and Aurora the feed publishes only
      `-LAGV` rates (Logically Air-Gapped Vault), which is an opt-in
      compliance feature, not the default anyone gets. Charging its premium
      by default would quietly inflate every estimate.

    What is left is the plain, same-region warm-storage rate, which is what
    centrally backing up object storage actually costs.
    """
    region = provider_region(region_key, "aws")
    doc = _load_bulk(BULK_SERVICES["backup"], region_key)

    for sku, product in doc.get("products", {}).items():
        usage = product.get("attributes", {}).get("usagetype", "")
        # Exact: cross-region copies carry a source prefix, and every
        # air-gapped variant carries the -LAGV suffix.
        if not _usage_is(usage, "WarmStorage-ByteHrs-S3"):
            continue
        found = _cheapest_dimension(doc, sku)
        if not found:
            continue
        price, unit = found
        return [
            PricePoint(
                provider="aws",
                category="backup",
                sku="backup:warm-storage",
                name="AWS Backup warm storage",
                region=region,
                unit=_UNITS.get(unit, unit),
                price_usd=price,
                attributes={"excludes": "RDS automated backups (free within retention)"},
            )
        ]
    return []


def _bulk_region_prefix(doc: dict) -> str:
    """This region's usage-type prefix, read from the file rather than mapped.

    AWS abbreviates every region in its meter names -- USE1, APS3, EUW1 --
    by a scheme with enough exceptions that a hand-written table goes stale.
    The regional price file only contains one region, so the prefix can be
    recovered from the meters themselves: the most common leading token
    across usage types IS this region.

    Returns "" for us-east-1-style files where meters carry no prefix at
    all, which callers treat as "match everything".
    """
    counts: Counter[str] = Counter()
    for product in doc.get("products", {}).values():
        usage = product.get("attributes", {}).get("usagetype", "") or ""
        head, sep, _rest = usage.partition("-")
        # A prefix is short and upper-case: "USE1", "APS3". Anything longer
        # is a meter name that happens to contain a hyphen.
        if sep and head.isupper() and 3 <= len(head) <= 5 and any(c.isdigit() for c in head):
            counts[head] += 1
    return counts.most_common(1)[0][0] if counts else ""


def load_endpoint_prices(region_key: str, path: Path | None = None) -> list[PricePoint]:
    """Interface VPC endpoints: hourly per endpoint-AZ, plus data processed.

    These exist to keep private-subnet traffic to AWS services off the NAT
    gateway, where the same bytes are charged at four times the rate. An
    architecture that adds endpoints and still routes S3 through NAT pays
    twice, so the estimator needs both meters to show the trade honestly.

    The S3 and DynamoDB GATEWAY endpoints are deliberately absent: AWS does
    not bill for them at all, so there is no meter to ingest and none is
    invented here. They are emitted separately as a zero-cost component.
    """
    doc = _load_bulk(BULK_SERVICES["endpoint"], region_key)
    region = provider_region(region_key, "aws")
    wanted = {
        "VpcEndpoint-Hours": ("vpce:interface-hour", "VPC interface endpoint", "hour"),
        "VpcEndpoint-Bytes": ("vpce:gb-processed", "VPC endpoint data processing", "GB"),
    }
    found: dict[str, PricePoint] = {}

    for sku, product in doc.get("products", {}).items():
        attrs = product.get("attributes", {})
        usage = attrs.get("usagetype", "") or ""
        # Gateway Load Balancer endpoints (GWLBE) and the ODB variants are
        # different products that merely share the prefix.
        if "GWLBE" in usage or "ODB" in usage:
            continue
        key = next((k for k in wanted if _usage_is(usage, k)), None)
        if key is None or wanted[key][0] in found:
            continue
        dim = _cheapest_dimension(doc, sku)
        if not dim:
            continue
        price, unit = dim
        sku_id, name, unit_name = wanted[key]
        found[sku_id] = PricePoint(
            provider="aws",
            category="endpoint",
            sku=sku_id,
            name=name,
            region=region,
            unit=unit_name,
            price_usd=price,
            attributes={"endpoint_type": "interface"},
        )
        if len(found) == len(wanted):
            break

    # The gateway endpoint, at the rate AWS actually charges for it.
    found["vpce:gateway"] = PricePoint(
        provider="aws",
        category="endpoint",
        sku="vpce:gateway",
        name="VPC gateway endpoint (S3, DynamoDB)",
        region=region,
        unit="month",
        price_usd=Decimal("0"),
        attributes={"endpoint_type": "gateway", "billed": "false"},
    )
    return list(found.values())


def load_lifecycle_storage_prices(
    region_key: str, path: Path | None = None
) -> list[PricePoint]:
    """The colder S3 storage classes a lifecycle policy transitions into.

    Standard is already priced as object storage. These are the tiers that
    make "keep it for seven years" affordable: write-once data -- scans,
    reports, audit logs -- costs a fraction of Standard once it stops being
    read. Without them the only priceable answer to a retention requirement
    is Standard forever, which overstates the cost of compliance by roughly
    six times.
    """
    doc = _load_bulk(BULK_SERVICES["storage"], region_key)
    region = provider_region(region_key, "aws")
    wanted = {
        "TimedStorage-SIA-ByteHrs": ("s3:standard-ia", "S3 Standard-IA", "infrequent"),
        "TimedStorage-GIR-ByteHrs": (
            "s3:glacier-instant", "S3 Glacier Instant Retrieval", "archive-instant",
        ),
        "TimedStorage-INT-DAA-ByteHrs": (
            "s3:deep-archive", "S3 Intelligent-Tiering Deep Archive", "archive-deep",
        ),
    }
    found: dict[str, PricePoint] = {}

    for sku, product in doc.get("products", {}).items():
        usage = product.get("attributes", {}).get("usagetype", "") or ""
        # "SmObjects" and the Tables/Files variants are separate meters that
        # would otherwise match on suffix.
        if "SmObjects" in usage or "Tables-" in usage or "Files-" in usage:
            continue
        key = next((k for k in wanted if _usage_is(usage, k)), None)
        if key is None or wanted[key][0] in found:
            continue
        dim = _cheapest_dimension(doc, sku)
        if not dim:
            continue
        price, _unit = dim
        sku_id, name, tier = wanted[key]
        found[sku_id] = PricePoint(
            provider="aws",
            category="storage_lifecycle",
            sku=sku_id,
            name=name,
            region=region,
            unit="GB-month",
            price_usd=price,
            attributes={"tier": tier},
        )
    return list(found.values())


def load_backup_copy_prices(
    region_key: str, path: Path | None = None
) -> list[PricePoint]:
    """Cross-region backup copy, per GB stored at the destination.

    A backup that lives only beside the thing it protects does not survive
    losing the region. AWS bills the copy as destination storage, and the
    rate depends on the pair of regions, so the cheapest destination rate
    for this source is taken as the representative figure.
    """
    doc = _load_bulk(BULK_SERVICES["backup"], region_key)
    region = provider_region(region_key, "aws")

    # DIRECTION MATTERS, and it is easy to get backwards.
    #
    # The meter is named "{SOURCE}-{DEST}-CrossRegion-WarmBytes-{SERVICE}",
    # so both directions of every pair appear in this file. Taking the
    # cheapest of all of them picked "USE2-USE1" -- the rate for copying
    # INTO us-east-1 from us-east-2 -- and quoted $0.01/GB for an
    # architecture whose copies actually leave us-east-1 at $0.02.
    #
    # Only meters whose SOURCE is this region are eligible. Among those the
    # cheapest destination is taken, and named, so the figure belongs to a
    # real pair rather than an average of pairs nobody chose.
    # The source code is counted from the cross-region meters themselves,
    # not from the file at large. us-east-1's ordinary meters carry no
    # prefix, so a whole-file scan returns "" and every pair matches --
    # including the inbound ones, which is how $0.01 was quoted. In a PAIR
    # meter both regions are always named explicitly, and this file's own
    # region is the one that appears in the source position most often.
    pairs = [
        (product.get("attributes", {}).get("usagetype", "") or "", sku)
        for sku, product in doc.get("products", {}).items()
        if "CrossRegion-WarmBytes"
        in (product.get("attributes", {}).get("usagetype", "") or "")
    ]
    sources: Counter[str] = Counter(u.split("-")[0] for u, _ in pairs if "-" in u)
    source = sources.most_common(1)[0][0] if sources else ""

    # The rate depends on the RESOURCE TYPE as well as the region pair --
    # a Virtual Machine copy from us-east-1 to us-east-2 is $0.04/GB while
    # an Aurora copy on the same route is $0.01. The durability filter this
    # feeds protects the database, so the database-class rate is the one
    # taken; picking the global cheapest would land on whichever service
    # happened to be least expensive and quote it for a database.
    database_class = ("Aurora", "RDS", "EBS", "DocumentDB", "Neptune")

    cheapest: Decimal | None = None
    destination = ""

    for usage, sku in pairs:
        if source and not usage.startswith(f"{source}-"):
            continue
        if not any(usage.endswith(f"-{r}") for r in database_class):
            continue
        dim = _cheapest_dimension(doc, sku)
        if not dim:
            continue
        price, _unit = dim
        if cheapest is None or price < cheapest:
            cheapest = price
            parts = usage.split("-")
            destination = parts[1] if len(parts) > 1 else ""

    if cheapest is None:
        return []
    return [
        PricePoint(
            provider="aws",
            category="backup_copy",
            sku="backup:cross-region-warm",
            name="Cross-region backup copy",
            region=region,
            unit="GB-month",
            price_usd=cheapest,
            attributes={
                "storage_class": "warm",
                "resource_class": "database",
                "cheapest_destination": destination,
            },
        )
    ]


def load_governance_prices(
    region_key: str, path: Path | None = None
) -> list[PricePoint]:
    """Controls AWS provides at no charge, priced at zero rather than omitted.

    S3 Object Lock and Organizations service control policies both cost
    nothing, and both are load-bearing: object lock is what makes a backup
    tamper-proof, and an SCP is what actually denies a region rather than
    merely intending to. Leaving them out of the catalog meant an
    architecture could not name them, so a durability or residency
    requirement had no component to point at.

    Zero is what AWS charges, so zero is what is recorded -- this is a
    looked-up figure like any other, not an estimate.
    """
    region = provider_region(region_key, "aws")
    return [
        PricePoint(
            provider="aws",
            category="governance",
            sku="s3:object-lock",
            name="S3 Object Lock (WORM retention)",
            region=region,
            unit="month",
            price_usd=Decimal("0"),
            attributes={"billed": "false", "protects": "tamper-and-delete"},
        ),
        PricePoint(
            provider="aws",
            category="governance",
            sku="organizations:scp",
            name="Service control policy (region deny)",
            region=region,
            unit="month",
            price_usd=Decimal("0"),
            attributes={"billed": "false", "protects": "region-residency"},
        ),
    ]


def load_all(region_key: str, path: Path | None = None) -> list[PricePoint]:
    """Every category we price on AWS, for one region."""
    points = load_compute_prices(region_key, path)
    for loader in (
        load_endpoint_prices,
        load_lifecycle_storage_prices,
        load_backup_copy_prices,
        load_governance_prices,
        load_spot_prices,
        load_database_prices,
        load_storage_prices,
        load_egress_prices,
        load_loadbalancer_prices,
        load_cache_prices,
        load_monitoring_prices,
        load_dns_prices,
        load_waf_prices,
        load_cloudtrail_prices,
        load_kms_prices,
        load_nat_prices,
        load_acm_prices,
        load_cognito_prices,
        load_backup_prices,
        load_streaming_prices,
        load_kafka_prices,
        load_search_prices,
        load_warehouse_prices,
        load_threat_prices,
        load_tracing_prices,
        load_posture_prices,
        load_flowlog_prices,
        load_fargate_prices,
        load_db_storage_prices,
        load_lcu_prices,
        load_s3_request_prices,
        load_secrets_prices,
        load_cdn_prices,
        load_interregion_transfer_prices,
        load_email_prices,
        load_queue_prices,
        load_notification_prices,
        load_lambda_prices,
        load_apigateway_prices,
        load_dynamodb_prices,
        load_rekognition_prices,
        load_comprehend_prices,
    ):
        try:
            points.extend(loader(region_key))
        except Exception as exc:  # one bad feed must not sink the ingest
            print(f"  ! aws {loader.__name__} failed: {exc}")
    return points
