"""AWS pricing adapter.

Two public, credential-free sources:

1. ec2instances.info (Vantage, open source) — one JSON file with every EC2
   instance's specs AND on-demand price per region. ~300 MB, so it is an
   ingest-once-then-cache source, never a live lookup.
2. AWS Price List Bulk API — the authoritative per-service, per-region feed.
   Used for RDS/S3 where instances.json has no coverage.

Neither needs an AWS account. Verified 2026-08.
"""

from __future__ import annotations

import json
import os
from decimal import Decimal
from pathlib import Path

import httpx

from .models import ComputeQuery, PricePoint, provider_region

INSTANCES_URL = "https://instances.vantage.sh/instances.json"
BULK_BASE = "https://pricing.us-east-1.amazonaws.com"
BULK_REGION_INDEX = BULK_BASE + "/offers/v1.0/aws/{service}/current/region_index.json"

CACHE_DIR = Path(os.getenv("WHICHCLOUD_CACHE", Path.home() / ".cache" / "whichcloud"))


def _cache_path(name: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / name


def download_instances(force: bool = False) -> Path:
    """Fetch the EC2 catalog once and cache it on disk.

    ~300 MB. In production this is a scheduled job that writes to Postgres;
    here it is a local file so the pricing layer can be verified offline.
    """
    dest = _cache_path("aws-instances.json")
    if dest.exists() and not force:
        return dest

    tmp = dest.with_suffix(".part")
    with httpx.stream("GET", INSTANCES_URL, timeout=300.0, follow_redirects=True) as r:
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
    """Every on-demand Linux EC2 instance priced in this region."""
    region = provider_region(region_key, "aws")
    path = path or download_instances()

    with path.open() as fh:
        catalog = json.load(fh)

    points: list[PricePoint] = []
    for inst in catalog:
        pricing = (inst.get("pricing") or {}).get(region, {})
        ondemand = (pricing.get("linux") or {}).get("ondemand")
        if not ondemand:
            continue
        try:
            price = Decimal(str(ondemand))
        except (ArithmeticError, ValueError):
            continue
        if price <= 0:
            continue

        points.append(
            PricePoint(
                provider="aws",
                category="compute",
                sku=inst["instance_type"],
                name=inst["instance_type"],
                region=region,
                unit="hour",
                price_usd=price,
                vcpu=int(inst["vCPU"]) if inst.get("vCPU") else None,
                memory_gb=float(inst["memory"]) if inst.get("memory") else None,
                arch=_detect_arch(inst),
                attributes={"processor": inst.get("physical_processor") or ""},
            )
        )
    return points


def cheapest_compute(query: ComputeQuery, path: Path | None = None) -> PricePoint | None:
    """Smallest bill that still satisfies the query."""
    candidates = [p for p in load_compute_prices(query.region, path) if query.matches(p)]
    return min(candidates, key=lambda p: p.price_usd, default=None)


def bulk_region_url(service: str, region_key: str) -> str:
    """Resolve a service+region to its Price List Bulk API URL.

    `service` is an AWS offer code: AmazonRDS, AmazonS3, AmazonEC2.
    """
    region = provider_region(region_key, "aws")
    r = httpx.get(BULK_REGION_INDEX.format(service=service), timeout=60.0)
    r.raise_for_status()
    regions = r.json().get("regions", {})
    if region not in regions:
        raise ValueError(f"{service} is not published for {region}")
    return BULK_BASE + regions[region]["currentVersionUrl"]
