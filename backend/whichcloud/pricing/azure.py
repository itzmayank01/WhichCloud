"""Azure pricing adapter.

The Azure Retail Prices API is the friendliest of the three: public, no
authentication, OData-filterable, JSON out. Verified 2026-08 against
`centralindia`.

One gap it does not fill: it returns SKU names and prices but no CPU or memory
specs. Those come from the real machine catalog in specs.py — never from a
hand-written table. A SKU absent from that catalog is skipped, never guessed.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

import httpx

from .models import ComputeQuery, PricePoint, provider_region
from .specs import azure_spec_for

RETAIL_API = "https://prices.azure.com/api/retail/prices"

# A single armSkuName can carry a dozen meters in one region: Linux, Windows,
# legacy "Cloud Services", dev/test rates, reservations, spot and low-priority.
# Name-matching alone is not enough — the Windows-priced "Dasv5 Series Cloud
# Services" meter contains neither "windows" nor anything else distinctive, and
# picking it made 36 Azure machine types read 2.65x too expensive until
# validation caught it. So we allow-list instead of deny-list.
_EXCLUDE_VM = ("low priority", "windows")

# Only the plain on-demand consumption meter counts.
_ALLOWED_PRICE_TYPE = "Consumption"

# ...and only products in the Virtual Machines line, never Cloud Services.
_REQUIRED_PRODUCT = "virtual machines"


def _decimal(value: object) -> Decimal | None:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return d if d > 0 else None


def _blob(item: dict, *keys: str) -> str:
    return " ".join(str(item.get(k, "")) for k in keys).lower()


def is_ondemand_vm_meter(item: dict) -> bool:
    """Is this retail item a plain on-demand Linux VM rate?

    Extracted so the rule is unit-testable without a network call. See the
    _EXCLUDE_VM comment for why this is an allow-list.
    """
    if item.get("type") != _ALLOWED_PRICE_TYPE:
        return False
    if _REQUIRED_PRODUCT not in str(item.get("productName", "")).lower():
        return False
    blob = _blob(item, "skuName", "meterName", "productName")
    return not any(term in blob for term in _EXCLUDE_VM)


def _paged(query: str, max_pages: int = 25):
    """Walk the Retail Prices API's NextPageLink chain."""
    url: str | None = RETAIL_API
    params: dict[str, str] | None = {"$filter": query, "currencyCode": "USD"}
    with httpx.Client(timeout=90.0) as client:
        for _ in range(max_pages):
            if not url:
                return
            r = client.get(url, params=params)
            r.raise_for_status()
            payload = r.json()
            yield from payload.get("Items", [])
            url = payload.get("NextPageLink")
            params = None  # NextPageLink already carries the query


def fetch_vm_prices(region_key: str) -> list[PricePoint]:
    """On-demand and spot Linux VM prices for a region."""
    region = provider_region(region_key, "azure")
    query = (
        "serviceName eq 'Virtual Machines' "
        f"and armRegionName eq '{region}' "
        "and priceType eq 'Consumption'"
    )

    points: list[PricePoint] = []
    seen: set[str] = set()

    for item in _paged(query):
        if not is_ondemand_vm_meter(item):
            continue

        sku = item.get("armSkuName") or ""
        spec = azure_spec_for(sku) if sku else None
        if spec is None:
            continue

        blob = _blob(item, "skuName", "meterName", "productName")
        is_spot = "spot" in blob
        key = f"{sku}:spot" if is_spot else sku
        if key in seen:
            continue

        price = _decimal(item.get("retailPrice"))
        if price is None:
            continue

        seen.add(key)
        points.append(
            PricePoint(
                provider="azure",
                category="compute",
                sku=key,
                name=item.get("skuName") or sku,
                region=region,
                unit="hour",
                price_usd=price,
                vcpu=spec.vcpu,
                memory_gb=spec.memory_gb,
                arch=spec.arch,
                attributes={
                    "meter": item.get("meterName", ""),
                    "family": spec.family,
                    "purchase": "spot" if is_spot else "ondemand",
                },
            )
        )
    return points


def cheapest_compute(query: ComputeQuery) -> PricePoint | None:
    candidates = [
        p
        for p in fetch_vm_prices(query.region)
        if query.matches(p) and p.attributes.get("purchase") == "ondemand"
    ]
    return min(candidates, key=lambda p: p.price_usd, default=None)


def fetch_database_prices(region_key: str) -> list[PricePoint]:
    """Azure Database for PostgreSQL — flexible server compute.

    Many of these meters ("vCore", "Extended Support", "Auto Tune") are billing
    fragments rather than server sizes. Resolving each name against the machine
    catalog filters them out: a fragment has no spec, so it is dropped.
    """
    region = provider_region(region_key, "azure")
    query = (
        "serviceName eq 'Azure Database for PostgreSQL' "
        f"and armRegionName eq '{region}' "
        "and priceType eq 'Consumption'"
    )

    points: list[PricePoint] = []
    seen: set[str] = set()
    for item in _paged(query):
        blob = _blob(item, "skuName", "meterName", "productName")
        if "backup" in blob or "storage" in blob:
            continue

        raw = (item.get("skuName") or "").strip()
        spec = azure_spec_for(raw) if raw else None
        if spec is None or raw.upper() in seen:
            continue

        price = _decimal(item.get("retailPrice"))
        if price is None:
            continue

        seen.add(raw.upper())
        points.append(
            PricePoint(
                provider="azure",
                category="database",
                sku=raw,
                name=f"PostgreSQL Flexible Server {raw}",
                region=region,
                unit="hour",
                price_usd=price,
                vcpu=spec.vcpu,
                memory_gb=spec.memory_gb,
                attributes={"engine": "postgresql", "deployment": "Single-AZ"},
            )
        )

        # Azure publishes no high-availability meter. Zone-redundant HA
        # provisions a standby that is billed as a second instance of the same
        # SKU, so the rate is exactly 2x. This is DERIVED, not published —
        # the attribute records that so the estimator can say so out loud.
        points.append(
            PricePoint(
                provider="azure",
                category="database",
                sku=f"{raw}:multi-az",
                name=f"PostgreSQL Flexible Server {raw} (zone-redundant HA)",
                region=region,
                unit="hour",
                price_usd=price * 2,
                vcpu=spec.vcpu,
                memory_gb=spec.memory_gb,
                attributes={
                    "engine": "postgresql",
                    "deployment": "Multi-AZ",
                    "derived": "2x primary; Azure bills the HA standby as a "
                    "second instance and publishes no separate HA meter",
                },
            )
        )
    return points


def fetch_loadbalancer_prices(region_key: str) -> list[PricePoint]:
    """Standard Load Balancer hourly rule charge.

    Azure publishes this against armRegionName 'Global' rather than a real
    region, so filtering by region returns nothing. We query unfiltered and
    attribute the result to the requested region.
    """
    region = provider_region(region_key, "azure")
    query = "serviceName eq 'Load Balancer' and priceType eq 'Consumption'"

    for item in _paged(query, max_pages=5):
        meter = (item.get("meterName") or "").lower()
        unit = (item.get("unitOfMeasure") or "").lower()
        if "included lb rules" not in meter or "hour" not in unit:
            continue
        price = _decimal(item.get("retailPrice"))
        if price is None:
            continue
        return [
            PricePoint(
                provider="azure",
                category="loadbalancer",
                sku="lb:standard",
                name="Standard Load Balancer",
                region=region,
                unit="hour",
                price_usd=price,
                attributes={"type": "standard", "priced_globally": "true"},
            )
        ]
    return []


def fetch_storage_prices(region_key: str) -> list[PricePoint]:
    """Blob storage, hot tier, per GB-month."""
    region = provider_region(region_key, "azure")
    query = (
        "serviceName eq 'Storage' "
        f"and armRegionName eq '{region}' "
        "and priceType eq 'Consumption'"
    )

    points: list[PricePoint] = []
    seen: set[str] = set()
    for item in _paged(query, max_pages=10):
        unit = (item.get("unitOfMeasure") or "").lower()
        if "gb/month" not in unit and "gb-month" not in unit:
            continue
        blob = _blob(item, "skuName", "meterName", "productName")
        if "hot" not in blob or "lrs" not in blob:
            continue
        sku = item.get("meterName") or ""
        if not sku or sku in seen:
            continue
        price = _decimal(item.get("retailPrice"))
        if price is None:
            continue
        seen.add(sku)
        points.append(
            PricePoint(
                provider="azure",
                category="storage",
                sku="blob:hot-lrs",
                name="Blob storage (hot, LRS)",
                region=region,
                unit="GB-month",
                price_usd=price,
                attributes={"tier": "hot"},
            )
        )
        break
    return points


def fetch_egress_prices(region_key: str) -> list[PricePoint]:
    """Outbound bandwidth to the internet.

    Azure publishes egress as volume tiers: a free allowance at
    tierMinimumUnits 0, then progressively cheaper bands. We want the first
    *paid* band — the rate a normal project actually hits — not the free tier
    (which would price egress at zero) and not the volume floor (which would
    understate it).
    """
    region = provider_region(region_key, "azure")
    query = (
        "serviceName eq 'Bandwidth' and priceType eq 'Consumption' "
        f"and armRegionName eq '{region}' "
        "and meterName eq 'Standard Data Transfer Out'"
    )

    best: tuple[float, Decimal] | None = None
    for item in _paged(query, max_pages=5):
        price = _decimal(item.get("retailPrice"))
        if price is None:
            continue  # skips the free tier, which is 0
        tier = float(item.get("tierMinimumUnits") or 0)
        if best is None or tier < best[0]:
            best = (tier, price)

    if best is None:
        return []

    return [
        PricePoint(
            provider="azure",
            category="network",
            sku="egress:internet",
            name="Data transfer out to internet",
            region=region,
            unit="GB",
            price_usd=best[1],
            attributes={"transfer_type": "outbound", "tier_from_gb": str(best[0])},
        )
    ]


def _redis_memory_gb(sku: str) -> float | None:
    """Memory for an Azure Managed Redis SKU, read out of the SKU name.

    The Balanced tier names each size after its memory in GB — B3 is 3 GB,
    B250 is 250 GB. That makes the size a property of the published data
    rather than something we type in from documentation, which is the whole
    reason this tier is the one we price. The classic C-series does *not*
    work this way (C3 is 6 GB, not 3), so it is deliberately skipped rather
    than guessed at.
    """
    if len(sku) < 2 or sku[0] != "B" or not sku[1:].isdigit():
        return None
    n = int(sku[1:])
    return 0.5 if n == 0 else float(n)


def fetch_cache_prices(region_key: str) -> list[PricePoint]:
    """Managed Redis nodes, Balanced tier."""
    region = provider_region(region_key, "azure")
    query = (
        "serviceName eq 'Redis Cache' "
        f"and armRegionName eq '{region}' "
        "and priceType eq 'Consumption'"
    )

    points: list[PricePoint] = []
    seen: set[str] = set()
    for item in _paged(query, max_pages=10):
        if "balanced" not in str(item.get("productName", "")).lower():
            continue
        if (item.get("unitOfMeasure") or "").lower() != "1 hour":
            continue
        sku = str(item.get("skuName") or "")
        memory = _redis_memory_gb(sku)
        if memory is None or sku in seen:
            continue
        price = _decimal(item.get("retailPrice"))
        if price is None:
            continue
        seen.add(sku)
        points.append(
            PricePoint(
                provider="azure",
                category="cache",
                sku=f"redis:{sku.lower()}",
                name=f"Azure Managed Redis {sku}",
                region=region,
                unit="hour",
                price_usd=price,
                memory_gb=memory,
                # vCPU is not published for these. Cache sizing is governed by
                # memory anyway, so we leave it unset rather than invent one.
                attributes={"tier": "balanced", "engine": "redis"},
            )
        )
    return points


def fetch_monitoring_prices(region_key: str) -> list[PricePoint]:
    """Metric ingestion, converted to a per-metric-per-month rate.

    Azure meters metrics by sample volume (per 10M samples) while AWS meters
    them per metric per month. To compare them at all, one has to be expressed
    in the other's unit, so we convert Azure's here using an explicit
    assumption: one sample per minute, which is the default resolution.

    The assumption is recorded in the attributes so the arithmetic can be
    checked. It is worth knowing that the two clouds genuinely price this very
    differently -- Azure's rate really is orders of magnitude lower per metric,
    because AWS charges per custom metric where Azure charges for throughput.
    """
    region = provider_region(region_key, "azure")
    query = (
        "serviceName eq 'Azure Monitor' "
        f"and armRegionName eq '{region}' "
        "and priceType eq 'Consumption' "
        "and meterName eq 'Metrics ingestion Metric samples'"
    )

    samples_per_metric_month = 60 * 24 * 30  # one sample a minute

    for item in _paged(query, max_pages=3):
        price = _decimal(item.get("retailPrice"))
        if price is None:
            continue
        per_sample = price / Decimal(10_000_000)
        return [
            PricePoint(
                provider="azure",
                category="monitoring",
                sku="monitor:metrics",
                name="Metrics ingestion (1-minute resolution)",
                region=region,
                unit="metric-month",
                price_usd=per_sample * Decimal(samples_per_metric_month),
                attributes={
                    "published_rate_usd_per_10m_samples": str(price),
                    "samples_per_metric_month": str(samples_per_metric_month),
                    "assumed_resolution": "1 minute",
                },
            )
        ]
    return []


def load_all(region_key: str) -> list[PricePoint]:
    """Every category we price on Azure, for one region."""
    points: list[PricePoint] = []
    for loader in (
        fetch_vm_prices,
        fetch_database_prices,
        fetch_storage_prices,
        fetch_egress_prices,
        fetch_cache_prices,
        fetch_monitoring_prices,
        fetch_loadbalancer_prices,
    ):
        try:
            points.extend(loader(region_key))
        except Exception as exc:
            print(f"  ! azure {loader.__name__} failed: {exc}")
    return points
