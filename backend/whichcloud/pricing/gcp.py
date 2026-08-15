"""GCP pricing adapter.

Google's own Cloud Billing Catalog API requires an API key (verified: it
returns 403 PERMISSION_DENIED to unregistered callers). But Vantage publishes a
credential-free GCP machine-type catalog with specs, on-demand, spot and
committed-use rates — 5.9 MB, versus 298 MB for the AWS equivalent.

So GCP compute needs no key. Storage, egress and Cloud SQL still do; that path
is gated on GOOGLE_CLOUD_API_KEY and stays dormant until one is supplied.
"""

from __future__ import annotations

import json
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path

import httpx

from .models import ComputeQuery, PricePoint, provider_region
from .specs import gcp_arch_for

INSTANCES_URL = "https://instances.vantage.sh/gcp/instances.json"
CATALOG_API = "https://cloudbilling.googleapis.com/v1/services"

CACHE_DIR = Path(os.getenv("WHICHCLOUD_CACHE", Path.home() / ".cache" / "whichcloud"))

def _decimal(value: object) -> Decimal | None:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return d if d > 0 else None


def _cache_path(name: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / name


def download_instances(force: bool = False) -> Path:
    dest = _cache_path("gcp-instances.json")
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


def load_compute_prices(region_key: str, path: Path | None = None) -> list[PricePoint]:
    """Every Linux machine type in this region, on-demand and spot."""
    region = provider_region(region_key, "gcp")
    path = path or download_instances()

    with path.open() as fh:
        catalog = json.load(fh)

    points: list[PricePoint] = []
    for machine in catalog:
        linux = ((machine.get("pricing") or {}).get(region) or {}).get("linux") or {}
        name = machine.get("instance_type")
        if not name:
            continue

        vcpu = int(machine["vCPU"]) if machine.get("vCPU") else None
        mem = float(machine["memory"]) if machine.get("memory") else None
        arch = gcp_arch_for(name)
        family = machine.get("family", "")

        for purchase, key in (("ondemand", "ondemand"), ("spot", "spot")):
            price = _decimal(linux.get(key))
            if price is None:
                continue
            sku = name if purchase == "ondemand" else f"{name}:spot"
            points.append(
                PricePoint(
                    provider="gcp",
                    category="compute",
                    sku=sku,
                    name=name if purchase == "ondemand" else f"{name} (spot)",
                    region=region,
                    unit="hour",
                    price_usd=price,
                    vcpu=vcpu,
                    memory_gb=mem,
                    arch=arch,
                    attributes={"family": family, "purchase": purchase},
                )
            )

    return points


def cheapest_compute(query: ComputeQuery, path: Path | None = None) -> PricePoint | None:
    candidates = [
        p
        for p in load_compute_prices(query.region, path)
        if query.matches(p) and p.attributes.get("purchase") == "ondemand"
    ]
    return min(candidates, key=lambda p: p.price_usd, default=None)


def catalog_api_available() -> bool:
    return bool(os.getenv("GOOGLE_CLOUD_API_KEY"))


def fetch_catalog_services() -> list[dict]:
    """List billable GCP services. Requires GOOGLE_CLOUD_API_KEY.

    Kept minimal on purpose: it exists so storage/egress/Cloud SQL can be wired
    up the moment a key is supplied, without restructuring anything.
    """
    key = os.getenv("GOOGLE_CLOUD_API_KEY")
    if not key:
        raise RuntimeError(
            "GOOGLE_CLOUD_API_KEY is not set. GCP compute works without it; "
            "storage, egress and Cloud SQL need a key from "
            "https://console.cloud.google.com/apis/credentials"
        )
    r = httpx.get(CATALOG_API, params={"key": key}, timeout=60.0)
    r.raise_for_status()
    return r.json().get("services", [])


# ---------------------------------------------------------------------------
# Cloud Billing Catalog API
#
# Everything below needs GOOGLE_CLOUD_API_KEY. The mechanism -- paging, price
# arithmetic, SKU selection -- is written and tested here; what it cannot be
# is *validated*, because validation means comparing what these selectors pick
# against Google's published rates, and that needs a live call.
#
# That distinction matters. The equivalent Azure selector looked correct and
# silently picked a Windows-priced meter, making 36 machine types read 2.65x
# too expensive. So these selectors are deliberately narrow: each one states
# the resource family, group and usage type it will accept, and anything that
# does not match is skipped rather than approximated. scripts/validate_gcp.py
# prints what was chosen so it can be checked against Google's pricing pages
# before any of it is believed.
# ---------------------------------------------------------------------------


def sku_price(sku: dict) -> Decimal | None:
    """The first tier's unit price.

    Google splits a price into whole currency units and nanos -- billionths --
    so 0.031611 USD arrives as {"units": "0", "nanos": 31611000}. Both halves
    are needed; reading only `units` silently prices most SKUs at zero.
    """
    for info in sku.get("pricingInfo", []):
        tiers = info.get("pricingExpression", {}).get("tieredRates", [])
        for tier in tiers:
            unit = tier.get("unitPrice", {})
            units = Decimal(str(unit.get("units", "0") or "0"))
            nanos = Decimal(str(unit.get("nanos", 0) or 0)) / Decimal(1_000_000_000)
            price = units + nanos
            if price > 0:
                return price
    return None


def sku_unit(sku: dict) -> str:
    for info in sku.get("pricingInfo", []):
        unit = info.get("pricingExpression", {}).get("usageUnit")
        if unit:
            return str(unit)
    return ""


def _paged(url: str, key: str, field: str, max_pages: int = 40):
    token = ""
    for _ in range(max_pages):
        params = {"key": key, "pageSize": 5000}
        if token:
            params["pageToken"] = token
        response = httpx.get(url, params=params, timeout=90.0)
        response.raise_for_status()
        payload = response.json()
        yield from payload.get(field, [])
        token = payload.get("nextPageToken") or ""
        if not token:
            return


def find_service_id(display_name: str) -> str | None:
    """The catalog id for a service, matched on its display name."""
    target = display_name.strip().lower()
    for service in fetch_catalog_services():
        if str(service.get("displayName", "")).strip().lower() == target:
            return str(service.get("serviceId") or "")
    return None


def fetch_skus(service_id: str) -> list[dict]:
    key = os.getenv("GOOGLE_CLOUD_API_KEY")
    if not key:
        raise RuntimeError("GOOGLE_CLOUD_API_KEY is not set")
    url = f"{CATALOG_API}/{service_id}/skus"
    return list(_paged(url, key, "skus"))


def select_skus(
    skus: list[dict],
    region: str,
    *,
    resource_family: str = "",
    resource_group: str = "",
    usage_type: str = "OnDemand",
    must_contain: tuple[str, ...] = (),
    must_not_contain: tuple[str, ...] = (),
) -> list[dict]:
    """SKUs matching an explicit shape. Everything else is skipped.

    Every filter is opt-in and compared exactly, because the failure that
    matters here is not "found nothing" -- that shows up as an unpriced
    component -- but "found something plausible and wrong", which shows up as
    a number nobody questions.
    """
    chosen = []
    for sku in skus:
        if region not in sku.get("serviceRegions", []) and "global" not in sku.get(
            "serviceRegions", []
        ):
            continue
        category = sku.get("category", {})
        if resource_family and category.get("resourceFamily") != resource_family:
            continue
        if resource_group and category.get("resourceGroup") != resource_group:
            continue
        if usage_type and category.get("usageType") != usage_type:
            continue
        description = str(sku.get("description", "")).lower()
        if any(term.lower() not in description for term in must_contain):
            continue
        if any(term.lower() in description for term in must_not_contain):
            continue
        if sku_price(sku) is None:
            continue
        chosen.append(sku)
    return chosen


def fetch_storage_prices(region_key: str) -> list[PricePoint]:
    """Standard object storage, per GB-month."""
    region = provider_region(region_key, "gcp")
    service = find_service_id("Cloud Storage")
    if not service:
        return []
    matches = select_skus(
        fetch_skus(service),
        region,
        resource_family="Storage",
        must_contain=("standard storage",),
        # Nearline/Coldline/Archive are cheaper per GB and completely wrong as
        # a default -- the same trap that made S3 archive tiers win on AWS.
        must_not_contain=("nearline", "coldline", "archive", "durable reduced"),
    )
    if not matches:
        return []
    sku = min(matches, key=lambda s: sku_price(s))
    return [
        PricePoint(
            provider="gcp",
            category="storage",
            sku="gcs:standard",
            name="Cloud Storage (Standard)",
            region=region,
            unit="GB-month",
            price_usd=sku_price(sku),
            attributes={"sku_id": str(sku.get("skuId", "")), "tier": "standard"},
        )
    ]


def fetch_egress_prices(region_key: str) -> list[PricePoint]:
    """Internet egress, per GB."""
    region = provider_region(region_key, "gcp")
    service = find_service_id("Compute Engine")
    if not service:
        return []
    matches = select_skus(
        fetch_skus(service),
        region,
        resource_family="Network",
        must_contain=("internet egress",),
        # Inter-region and intra-continent traffic are different products;
        # so is Cloud CDN egress, which is billed separately.
        must_not_contain=("inter region", "intra", "cdn", "interconnect"),
    )
    if not matches:
        return []
    sku = min(matches, key=lambda s: sku_price(s))
    return [
        PricePoint(
            provider="gcp",
            category="network",
            sku="egress:internet",
            name="Internet egress",
            region=region,
            unit="GB",
            price_usd=sku_price(sku),
            attributes={"sku_id": str(sku.get("skuId", "")), "transfer_type": "outbound"},
        )
    ]


def fetch_database_prices(region_key: str) -> list[PricePoint]:
    """Cloud SQL for PostgreSQL, composed from its parts.

    Google does not sell a database instance; it sells vCPU-hours and RAM
    GB-hours, and a machine is whatever you assemble from them. So the shapes
    the engine asks for are built here rather than looked up, and the price of
    each is the sum of its two SKUs.

    This is the one place a GCP price is *computed* instead of read. The
    arithmetic is Google's own published model, and both component rates are
    recorded on the point so the total can be taken apart again.
    """
    region = provider_region(region_key, "gcp")
    service = find_service_id("Cloud SQL")
    if not service:
        return []
    skus = fetch_skus(service)

    def rate(*terms: str) -> Decimal | None:
        matches = select_skus(
            skus,
            region,
            must_contain=("postgresql",) + terms,
            must_not_contain=("replica", "ha ", "regional"),
        )
        return min((sku_price(s) for s in matches), default=None)

    vcpu_hour = rate("vcpu")
    ram_hour = rate("ram")
    if vcpu_hour is None or ram_hour is None:
        return []

    points: list[PricePoint] = []
    for vcpus, memory in ((1, 3.75), (2, 7.5), (4, 15.0), (8, 30.0), (16, 60.0)):
        hourly = vcpu_hour * Decimal(vcpus) + ram_hour * Decimal(str(memory))
        points.append(
            PricePoint(
                provider="gcp",
                category="database",
                sku=f"cloudsql-pg-{vcpus}vcpu-{memory:g}gb",
                name=f"Cloud SQL PostgreSQL {vcpus} vCPU / {memory:g} GB",
                region=region,
                unit="hour",
                price_usd=hourly,
                vcpu=vcpus,
                memory_gb=memory,
                attributes={
                    "engine": "postgres",
                    "composed": "true",
                    "vcpu_hour_usd": str(vcpu_hour),
                    "ram_gb_hour_usd": str(ram_hour),
                },
            )
        )
    return points


def fetch_cache_prices(region_key: str) -> list[PricePoint]:
    """Memorystore for Redis, priced per GB of capacity."""
    region = provider_region(region_key, "gcp")
    service = find_service_id("Cloud Memorystore for Redis") or find_service_id(
        "Cloud Memorystore"
    )
    if not service:
        return []
    matches = select_skus(
        fetch_skus(service),
        region,
        must_contain=("capacity",),
        must_not_contain=("standard", "ha", "replica"),  # Basic tier is the baseline
    )
    if not matches:
        return []
    per_gb_hour = min(sku_price(s) for s in matches)

    points: list[PricePoint] = []
    for memory in (1.0, 2.0, 4.0, 8.0, 16.0):
        points.append(
            PricePoint(
                provider="gcp",
                category="cache",
                sku=f"memorystore-redis-{memory:g}gb",
                name=f"Memorystore for Redis {memory:g} GB",
                region=region,
                unit="hour",
                price_usd=per_gb_hour * Decimal(str(memory)),
                memory_gb=memory,
                attributes={
                    "engine": "redis",
                    "tier": "basic",
                    "composed": "true",
                    "gb_hour_usd": str(per_gb_hour),
                },
            )
        )
    return points


def fetch_loadbalancer_prices(region_key: str) -> list[PricePoint]:
    """The forwarding-rule charge, which is the fixed part of a load balancer."""
    region = provider_region(region_key, "gcp")
    service = find_service_id("Compute Engine")
    if not service:
        return []
    matches = select_skus(
        fetch_skus(service),
        region,
        must_contain=("forwarding rule",),
        must_not_contain=("data processing",),
    )
    if not matches:
        return []
    sku = min(matches, key=lambda s: sku_price(s))
    return [
        PricePoint(
            provider="gcp",
            category="loadbalancer",
            sku="lb:forwarding-rule",
            name="Cloud Load Balancing (forwarding rule)",
            region=region,
            unit="hour",
            price_usd=sku_price(sku),
            attributes={"sku_id": str(sku.get("skuId", ""))},
        )
    ]


def fetch_monitoring_prices(region_key: str) -> list[PricePoint]:
    """Metric ingestion, converted to a per-metric-per-month rate.

    Google bills monitoring by ingested volume, the same as Azure and unlike
    AWS. The conversion assumes one sample a minute at roughly 8 bytes a
    sample, and both figures are recorded so the arithmetic can be redone.
    """
    region = provider_region(region_key, "gcp")
    service = find_service_id("Stackdriver Monitoring") or find_service_id(
        "Cloud Monitoring"
    )
    if not service:
        return []
    matches = select_skus(
        fetch_skus(service),
        region,
        must_contain=("metric",),
        must_not_contain=("api", "query", "uptime"),
    )
    if not matches:
        return []
    per_unit = min(sku_price(s) for s in matches)

    samples_per_month = Decimal(60 * 24 * 30)
    bytes_per_sample = Decimal(8)
    mib = Decimal(1024 * 1024)
    per_metric_month = per_unit * (samples_per_month * bytes_per_sample / mib)

    return [
        PricePoint(
            provider="gcp",
            category="monitoring",
            sku="monitoring:metrics",
            name="Metrics ingestion (1-minute resolution)",
            region=region,
            unit="metric-month",
            price_usd=per_metric_month,
            attributes={
                "published_rate_usd": str(per_unit),
                "samples_per_metric_month": str(samples_per_month),
                "assumed_bytes_per_sample": str(bytes_per_sample),
                "assumed_resolution": "1 minute",
            },
        )
    ]


def load_all(region_key: str, path: Path | None = None) -> list[PricePoint]:
    """Every GCP category we can price.

    Compute needs no credentials. Everything else comes from the Catalog API
    and is skipped entirely when no key is set — the estimator then reports
    those components as missing, which is the honest outcome, rather than the
    engine inventing them.
    """
    points = load_compute_prices(region_key, path)
    if not catalog_api_available():
        return points

    for loader in (
        fetch_storage_prices,
        fetch_egress_prices,
        fetch_database_prices,
        fetch_cache_prices,
        fetch_loadbalancer_prices,
        fetch_monitoring_prices,
    ):
        try:
            points.extend(loader(region_key))
        except (httpx.HTTPError, RuntimeError):
            # One service failing must not lose the other five, nor the
            # compute catalog that needed no key in the first place.
            continue
    return points
