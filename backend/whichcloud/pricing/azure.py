"""Azure pricing adapter.

The Azure Retail Prices API is the friendliest of the three: public, no
authentication, OData-filterable, JSON out. Verified 2026-08 against
`centralindia`.

One gap it does not fill: it returns SKU names and prices but no CPU or memory
specs. Matching "2 vCPU / 4 GB" therefore needs a spec table, curated below for
the families we actually recommend. An unmapped SKU is skipped, never guessed.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

import httpx

from .models import ComputeQuery, PricePoint, provider_region

RETAIL_API = "https://prices.azure.com/api/retail/prices"

AZURE_VM_SPECS: dict[str, tuple[int, float, str]] = {
    # B-series burstable — the budget tier
    "Standard_B1s": (1, 1.0, "x86_64"),
    "Standard_B1ms": (1, 2.0, "x86_64"),
    "Standard_B2s": (2, 4.0, "x86_64"),
    "Standard_B2ms": (2, 8.0, "x86_64"),
    "Standard_B4ms": (4, 16.0, "x86_64"),
    "Standard_B8ms": (8, 32.0, "x86_64"),
    # D-series v5 general purpose (Intel)
    "Standard_D2s_v5": (2, 8.0, "x86_64"),
    "Standard_D4s_v5": (4, 16.0, "x86_64"),
    "Standard_D8s_v5": (8, 32.0, "x86_64"),
    "Standard_D16s_v5": (16, 64.0, "x86_64"),
    # D-series v5 AMD
    "Standard_D2as_v5": (2, 8.0, "x86_64"),
    "Standard_D4as_v5": (4, 16.0, "x86_64"),
    "Standard_D8as_v5": (8, 32.0, "x86_64"),
    # Dps v5 — Ampere Altra ARM. Azure's Graviton equivalent.
    "Standard_D2ps_v5": (2, 8.0, "arm64"),
    "Standard_D4ps_v5": (4, 16.0, "arm64"),
    "Standard_D8ps_v5": (8, 32.0, "arm64"),
    "Standard_D16ps_v5": (16, 64.0, "arm64"),
    # Eps v5 — ARM, memory optimized
    "Standard_E2ps_v5": (2, 16.0, "arm64"),
    "Standard_E4ps_v5": (4, 32.0, "arm64"),
    "Standard_E8ps_v5": (8, 64.0, "arm64"),
    # E-series v5 memory optimized (Intel)
    "Standard_E2s_v5": (2, 16.0, "x86_64"),
    "Standard_E4s_v5": (4, 32.0, "x86_64"),
    # F-series compute optimized
    "Standard_F2s_v2": (2, 4.0, "x86_64"),
    "Standard_F4s_v2": (4, 8.0, "x86_64"),
    "Standard_F8s_v2": (8, 16.0, "x86_64"),
}

# Azure Database for PostgreSQL flexible-server sizes. vCore, GB.
AZURE_DB_SPECS: dict[str, tuple[int, float]] = {
    "B1MS": (1, 2.0),
    "B2S": (2, 4.0),
    "B2MS": (2, 8.0),
    "B4MS": (4, 16.0),
    "B8MS": (8, 32.0),
    "B16MS": (16, 64.0),
    "D2S_V3": (2, 8.0),
    "D4S_V3": (4, 16.0),
    "D8S_V3": (8, 32.0),
    "D2DS_V4": (2, 8.0),
    "D4DS_V4": (4, 16.0),
    "E2S_V3": (2, 16.0),
    "E4S_V3": (4, 32.0),
}

# Meter names carrying any of these are not plain on-demand Linux capacity.
_EXCLUDE_VM = ("low priority", "windows")


def _decimal(value: object) -> Decimal | None:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return d if d > 0 else None


def _blob(item: dict, *keys: str) -> str:
    return " ".join(str(item.get(k, "")) for k in keys).lower()


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
        sku = item.get("armSkuName") or ""
        if sku not in AZURE_VM_SPECS:
            continue
        blob = _blob(item, "skuName", "meterName", "productName")
        if any(term in blob for term in _EXCLUDE_VM):
            continue

        is_spot = "spot" in blob
        key = f"{sku}:spot" if is_spot else sku
        if key in seen:
            continue

        price = _decimal(item.get("retailPrice"))
        if price is None:
            continue

        vcpu, mem, arch = AZURE_VM_SPECS[sku]
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
                vcpu=vcpu,
                memory_gb=mem,
                arch=arch,
                attributes={
                    "meter": item.get("meterName", ""),
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

    Same problem as VMs: the API returns meter names, not specs. Many of those
    meters ("vCore", "Extended Support", "Auto Tune") are billing fragments
    rather than server sizes, so anything outside the spec table is skipped.
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
        spec = AZURE_DB_SPECS.get(raw.upper())
        if spec is None or raw.upper() in seen:
            continue

        price = _decimal(item.get("retailPrice"))
        if price is None:
            continue

        vcpu, mem = spec
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
                vcpu=vcpu,
                memory_gb=mem,
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
                vcpu=vcpu,
                memory_gb=mem,
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


def load_all(region_key: str) -> list[PricePoint]:
    """Every category we price on Azure, for one region."""
    points: list[PricePoint] = []
    for loader in (
        fetch_vm_prices,
        fetch_database_prices,
        fetch_storage_prices,
        fetch_egress_prices,
        fetch_loadbalancer_prices,
    ):
        try:
            points.extend(loader(region_key))
        except Exception as exc:
            print(f"  ! azure {loader.__name__} failed: {exc}")
    return points
