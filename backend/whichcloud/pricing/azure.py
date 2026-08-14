"""Azure pricing adapter.

The Azure Retail Prices API is the friendliest of the three: public, no
authentication, OData-filterable, and it returns JSON directly. Verified
2026-08 against `centralindia`.

One gap it does not fill: the API returns SKU names and prices but no CPU or
memory specs. Matching "2 vCPU / 4 GB" therefore needs a spec table, which we
curate below for the general-purpose families we actually recommend.
"""

from __future__ import annotations

from decimal import Decimal

import httpx

from .models import ComputeQuery, PricePoint, provider_region

RETAIL_API = "https://prices.azure.com/api/retail/prices"

# Azure VM specs are not in the pricing API, so we carry a table for the
# families the engine recommends. vCPU, GB, arch.
# Extend deliberately — an unmapped SKU is skipped, never guessed.
AZURE_VM_SPECS: dict[str, tuple[int, float, str]] = {
    # B-series burstable — the budget tier
    "Standard_B1s": (1, 1.0, "x86_64"),
    "Standard_B1ms": (1, 2.0, "x86_64"),
    "Standard_B2s": (2, 4.0, "x86_64"),
    "Standard_B2ms": (2, 8.0, "x86_64"),
    "Standard_B4ms": (4, 16.0, "x86_64"),
    # D-series v5 general purpose (Intel)
    "Standard_D2s_v5": (2, 8.0, "x86_64"),
    "Standard_D4s_v5": (4, 16.0, "x86_64"),
    "Standard_D8s_v5": (8, 32.0, "x86_64"),
    # D-series v5 AMD
    "Standard_D2as_v5": (2, 8.0, "x86_64"),
    "Standard_D4as_v5": (4, 16.0, "x86_64"),
    # Dps v5 — Ampere Altra ARM. Azure's Graviton equivalent.
    "Standard_D2ps_v5": (2, 8.0, "arm64"),
    "Standard_D4ps_v5": (4, 16.0, "arm64"),
    "Standard_D8ps_v5": (8, 32.0, "arm64"),
    # Eps v5 — ARM, memory optimized
    "Standard_E2ps_v5": (2, 16.0, "arm64"),
    "Standard_E4ps_v5": (4, 32.0, "arm64"),
    # F-series compute optimized
    "Standard_F2s_v2": (2, 4.0, "x86_64"),
    "Standard_F4s_v2": (4, 8.0, "x86_64"),
}

# Meter names carrying any of these are not plain on-demand Linux capacity.
_EXCLUDE = ("low priority", "spot", "windows")


def _is_ondemand_linux(item: dict) -> bool:
    blob = " ".join(
        str(item.get(k, "")) for k in ("skuName", "meterName", "productName")
    ).lower()
    return not any(term in blob for term in _EXCLUDE)


def fetch_vm_prices(region_key: str, max_pages: int = 20) -> list[PricePoint]:
    """All on-demand Linux VM prices for a region.

    The API pages 100 items at a time via NextPageLink; `max_pages` bounds a
    runaway crawl.
    """
    region = provider_region(region_key, "azure")
    query = (
        "serviceName eq 'Virtual Machines' "
        f"and armRegionName eq '{region}' "
        "and priceType eq 'Consumption'"
    )
    url: str | None = RETAIL_API
    params: dict[str, str] | None = {"$filter": query, "currencyCode": "USD"}

    points: list[PricePoint] = []
    seen: set[str] = set()

    with httpx.Client(timeout=60.0) as client:
        for _ in range(max_pages):
            if not url:
                break
            r = client.get(url, params=params)
            r.raise_for_status()
            payload = r.json()

            for item in payload.get("Items", []):
                sku = item.get("armSkuName") or ""
                if sku in seen or sku not in AZURE_VM_SPECS:
                    continue
                if not _is_ondemand_linux(item):
                    continue
                price = Decimal(str(item.get("retailPrice", 0)))
                if price <= 0:
                    continue

                vcpu, mem, arch = AZURE_VM_SPECS[sku]
                seen.add(sku)
                points.append(
                    PricePoint(
                        provider="azure",
                        category="compute",
                        sku=sku,
                        name=item.get("skuName") or sku,
                        region=region,
                        unit="hour",
                        price_usd=price,
                        vcpu=vcpu,
                        memory_gb=mem,
                        arch=arch,
                        attributes={"meter": item.get("meterName", "")},
                    )
                )

            url = payload.get("NextPageLink")
            params = None  # NextPageLink already carries the query string

    return points


def cheapest_compute(query: ComputeQuery) -> PricePoint | None:
    candidates = [p for p in fetch_vm_prices(query.region) if query.matches(p)]
    return min(candidates, key=lambda p: p.price_usd, default=None)
