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
import json
import os
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

import httpx

from .models import ComputeQuery, PricePoint, provider_region

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
}

CACHE_DIR = Path(os.getenv("WHICHCLOUD_CACHE", Path.home() / ".cache" / "whichcloud"))

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

    tmp = dest.with_suffix(".part")
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
    tmp = dest.with_suffix(".part")
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
                arch="arm64" if ".t4g." in instance or ".m7g." in instance else "x86_64",
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
                arch="arm64" if ".r7g." in instance or ".t4g." in instance else "x86_64",
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


def load_dns_prices(region_key: str) -> list[PricePoint]:
    """Route 53 hosted zone — a flat monthly charge per domain."""
    region = provider_region(region_key, "aws")
    doc = _load_bulk(BULK_SERVICES["dns"], region_key)

    for sku, product in doc.get("products", {}).items():
        usage = (product.get("attributes", {}).get("usagetype") or "").lower()
        if "hostedzone" not in usage:
            continue
        found = _cheapest_dimension(doc, sku)
        if not found:
            continue
        price, unit = found
        return [
            PricePoint(
                provider="aws",
                category="dns",
                sku="route53:hosted-zone",
                name="Route 53 hosted zone",
                region=region,
                unit="month",
                price_usd=price,
                attributes={"published_unit": unit},
            )
        ]
    return []


def load_all(region_key: str, path: Path | None = None) -> list[PricePoint]:
    """Every category we price on AWS, for one region."""
    points = load_compute_prices(region_key, path)
    for loader in (
        load_spot_prices,
        load_database_prices,
        load_storage_prices,
        load_egress_prices,
        load_loadbalancer_prices,
        load_cache_prices,
        load_monitoring_prices,
        load_dns_prices,
    ):
        try:
            points.extend(loader(region_key))
        except Exception as exc:  # one bad feed must not sink the ingest
            print(f"  ! aws {loader.__name__} failed: {exc}")
    return points
