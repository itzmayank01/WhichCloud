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

from .models import ComputeQuery, PricePoint, PriceTier, provider_region
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


def _decimal_allow_zero(value: object) -> Decimal | None:
    """Like `_decimal`, but a published $0 band is a real rate, not absent."""
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return d if d >= 0 else None


def _is_commercial(item: dict) -> bool:
    """Reject sovereign-cloud rows: US Gov, China, Germany.

    They sit alongside commercial ones and are priced differently, so an
    unfiltered scan can hand back a rate from a cloud the customer cannot
    buy. The naming is not consistent -- DNS publishes "US Gov Zone 1"
    with spaces, B2C publishes "usgovtexas" without -- so this normalises
    before matching rather than testing for one spelling.
    """
    region = (item.get("armRegionName") or "").lower().replace(" ", "")
    return not any(mark in region for mark in ("usgov", "usdod", "china", "germany"))


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
                attributes=_with_baseline(
                    {
                        "meter": item.get("meterName", ""),
                        "family": spec.family,
                        "purchase": "spot" if is_spot else "ondemand",
                    },
                    "azure",
                    key,
                ),
            )
        )
    return points


def _with_baseline(attrs: dict, provider: str, sku: str) -> dict:
    """Tag a row with its CPU baseline when the family is credit-limited, so
    the sizing rule can ask the catalog rather than carry its own table."""
    from .models import burstable_baseline

    b = burstable_baseline(provider, sku)
    return {**attrs, "burstable_baseline": str(b)} if b is not None else attrs


def cheapest_compute(query: ComputeQuery) -> PricePoint | None:
    candidates = [
        p
        for p in fetch_vm_prices(query.region)
        if query.matches(p) and p.attributes.get("purchase") == "ondemand"
    ]
    return min(candidates, key=lambda p: p.price_usd, default=None)


#: Memory per vCore for the two Flexible Server tiers Azure sells by vCore.
#: General Purpose is 4 GiB/vCore and Memory Optimized 8 GiB/vCore; the series
#: name in productName is the only thing that says which.
_PG_TIER_MEMORY_PER_VCPU = {"general purpose": 4.0, "memory optimized": 8.0}


def _vcore_series_spec(sku_name: str, product_name: str):
    """("D4ds_v5-class name", vcpu, memory_gb) for a per-vCore Postgres meter.

    Returns None for rows that really are billing fragments -- "Auto Tune",
    "Extended Support" and the free tier -- so those stay dropped.
    """
    import re

    m = re.match(r"^(\d+)m?\s+vcore$", sku_name.strip().lower())
    if not m or "free" in sku_name.lower():
        return None
    vcpu = int(m.group(1))
    low = product_name.lower()
    for tier, per_vcpu in _PG_TIER_MEMORY_PER_VCPU.items():
        if tier in low:
            # Series is the word before "Series", e.g. "... Ddsv5 Series ..."
            series = ""
            words = product_name.split()
            for i, w in enumerate(words):
                if w.lower() == "series" and i:
                    series = words[i - 1]
                    break
            if not series:
                return None
            return (f"{series}-{vcpu}vcore", vcpu, float(vcpu) * per_vcpu)
    return None


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
        price = _decimal(item.get("retailPrice"))
        if price is None:
            continue

        spec = azure_spec_for(raw) if raw else None
        if spec is None:
            # NOT a billing fragment. Azure publishes Burstable servers BY NAME
            # ("B2ms") but General Purpose and Memory Optimized PER VCORE
            # ("4 vCore"), with the series only in productName. Resolving the
            # sku name against the machine catalog therefore dropped every
            # production database tier as noise and left the catalog holding
            # burstable machines alone -- so every Azure estimate was sized on
            # a tier that throttles under sustained load, and none could be
            # reserved, because Azure sells no reservation for Burstable. That
            # was read as "Azure offers no database commitment"; it offers 28
            # of them, for the tiers we were discarding.
            resolved = _vcore_series_spec(raw, item.get("productName") or "")
            if resolved is None:
                continue
            raw, vcpu, memory_gb, price = resolved[0], resolved[1], resolved[2], price * resolved[1]
            spec = None
        else:
            vcpu, memory_gb = spec.vcpu, spec.memory_gb

        if raw.upper() in seen:
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
                vcpu=vcpu,
                memory_gb=memory_gb,
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
                memory_gb=memory_gb,
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


def fetch_nat_prices(region_key: str) -> list[PricePoint]:
    """NAT Gateway: hourly per gateway, plus per-GB processed.

    Published against armRegionName 'Global' rather than a real region, the
    same as Standard Load Balancer -- filtering by region returns nothing,
    which is why this looked unavailable at first.
    """
    region = provider_region(region_key, "azure")
    wanted = {
        "standard gateway": ("nat:gateway-hour", "NAT Gateway", "hour"),
        "standard data processed": ("nat:gb-processed", "NAT Gateway data processing", "GB"),
    }
    found: dict[str, PricePoint] = {}

    for item in _paged("serviceName eq 'NAT Gateway' and priceType eq 'Consumption'", max_pages=5):
        # US Gov is a separate cloud at its own rates.
        if item.get("armRegionName") not in ("Global", ""):
            continue
        meter = (item.get("meterName") or "").lower()
        if meter not in wanted or wanted[meter][0] in found:
            continue
        price = _decimal(item.get("retailPrice"))
        if price is None:
            continue
        sku, name, unit = wanted[meter]
        found[sku] = PricePoint(
            provider="azure",
            category="nat",
            sku=sku,
            name=name,
            region=region,
            unit=unit,
            price_usd=price,
            attributes={"priced_globally": "true"},
        )
    return list(found.values())


def fetch_dns_prices(region_key: str) -> list[PricePoint]:
    """Azure DNS public zones and queries, both graduated.

    Three traps in this feed, all of them silent:

    * **US Gov rows sit alongside commercial ones.** Unfiltered, the US Gov
      query rate ($0.50/M) wins over the commercial $0.40/M -- a 25% error
      on an Indian estimate, from a cloud the customer cannot even use.
    * **Pricing is by geographic Zone, not by region.** There is no
      `centralindia` row; every commercial zone publishes the same rate, so
      excluding US Gov is what makes the choice safe rather than arbitrary.
    * **Rates are tiered.** $0.50 per zone for the first 25 and $0.10
      after; $0.40 per million queries then $0.20 past a billion. Taking
      only the entry rate would overstate a large estate.

    Public, not Private: private zones are a different product at a
    coincidentally identical headline rate.
    """
    region = provider_region(region_key, "azure")
    wanted = {
        "public zone": ("dns:hosted-zone", "Azure DNS public zone", "month", 1),
        "public queries": ("dns:queries", "Azure DNS queries", "query", 1_000_000),
    }
    bands: dict[str, list[PriceTier]] = {}

    for item in _paged("serviceName eq 'Azure DNS' and priceType eq 'Consumption'", max_pages=8):
        if "US Gov" in (item.get("armRegionName") or ""):
            continue
        meter = (item.get("meterName") or "").lower()
        if meter not in wanted:
            continue
        price = _decimal(item.get("retailPrice"))
        if price is None:
            continue
        sku, _, _, per = wanted[meter]
        # The boundary is counted in the SAME published unit as the price:
        # tierMinimumUnits of 1000 against a "1M" unit means a billion
        # queries, not a thousand. Scaling the price but not the boundary
        # billed 10M queries as if 9,999,000 of them were past the discount
        # threshold -- half the true figure.
        begin = Decimal(str(item.get("tierMinimumUnits") or 0)) * per
        existing = bands.setdefault(sku, [])
        if any(t.begin == begin for t in existing):
            continue  # same band, another zone, same rate
        existing.append(PriceTier(begin=begin, end=None, price_usd=price / per))

    points: list[PricePoint] = []
    for meter, (sku, name, unit, _) in wanted.items():
        tiers = sorted(bands.get(sku, []), key=lambda t: t.begin)
        if not tiers:
            continue
        # A band runs until the next one starts; the last is unbounded.
        closed = tuple(
            PriceTier(
                begin=t.begin,
                end=tiers[i + 1].begin if i + 1 < len(tiers) else None,
                price_usd=t.price_usd,
            )
            for i, t in enumerate(tiers)
        )
        points.append(
            PricePoint(
                provider="azure",
                category="dns",
                sku=sku,
                name=name,
                region=region,
                unit=unit,
                price_usd=closed[0].price_usd,
                tiers=closed,
            )
        )
    return points


def fetch_keyvault_prices(region_key: str) -> list[PricePoint]:
    """Key Vault operations -- Azure's analogue of KMS and Secrets Manager.

    Deliberately NOT the "Standard Instance" meter. That one is $4.85 an
    HOUR, because it prices a Managed HSM pool (~$3,500/month), not a key
    vault. Standard Key Vault has no per-key and no per-secret monthly
    charge at all: it bills $0.03 per 10,000 operations and nothing else.

    So this is not a like-for-like row against AWS's $1/key and
    $0.40/secret -- it is genuinely a different pricing model, and the
    honest thing is to price the meter Azure actually charges.
    """
    region = provider_region(region_key, "azure")

    for item in _paged("serviceName eq 'Key Vault' and priceType eq 'Consumption'", max_pages=5):
        if (item.get("meterName") or "").lower() != "operations":
            continue
        price = _decimal(item.get("retailPrice"))
        if price is None:
            continue
        return [
            PricePoint(
                provider="azure",
                category="kms",
                sku="keyvault:operations",
                name="Key Vault operations",
                region=region,
                unit="operation",
                # Published per 10,000; the engine counts single operations.
                price_usd=price / Decimal(10_000),
                attributes={"model": "per-operation, no per-key charge"},
            )
        ]
    return []


def fetch_backup_prices(region_key: str) -> list[PricePoint]:
    """Azure Backup vault storage, locally redundant.

    EXACT meter match, not a substring, and the reason is worth stating:
    this feed publishes both "Standard LRS Data Stored" at $0.0246/GB-month
    and a legacy "LRS Data Stored" at $260,013. A contains() test on "LRS
    Data Stored" matches the second, and a backup line would have come out
    roughly ten million times too high. The same pair exists for GRS, ZRS
    and RA-GRS.

    LRS is the default redundancy; GRS and ZRS are deliberate upgrades.
    """
    region = provider_region(region_key, "azure")

    for item in _paged(
        f"serviceName eq 'Backup' and armRegionName eq '{region}'", max_pages=8
    ):
        if (item.get("meterName") or "") != "Standard LRS Data Stored":
            continue
        price = _decimal(item.get("retailPrice"))
        if price is None:
            continue
        return [
            PricePoint(
                provider="azure",
                category="backup",
                sku="backup:vault-lrs",
                name="Backup vault storage (LRS)",
                region=region,
                unit="GB-month",
                price_usd=price,
            )
        ]
    return []


def fetch_flowlog_prices(region_key: str) -> list[PricePoint]:
    """VNet flow log collection -- published at zero.

    A real $0, like ACM's public certificates: Azure collects flow logs at
    no charge and bills the storage they land in separately. Traffic
    Analytics on top of them is $2.30/GB, but that is an optional product,
    not the cost of having flow logs on.
    """
    region = provider_region(region_key, "azure")

    for item in _paged("serviceName eq 'Network Watcher'", max_pages=8):
        if "US Gov" in (item.get("armRegionName") or ""):
            continue
        if (item.get("meterName") or "") != "Standard VNet Flow Logs Collected":
            continue
        price = item.get("retailPrice")
        if price is None:
            continue
        return [
            PricePoint(
                provider="azure",
                category="flowlogs",
                sku="networkwatcher:flow-logs",
                name="VNet flow log collection",
                region=region,
                unit="GB",
                price_usd=Decimal(str(price)),
                attributes={"excludes": "Traffic Analytics ($2.30/GB, optional)"},
            )
        ]
    return []


def fetch_defender_prices(region_key: str) -> list[PricePoint]:
    """Defender for Servers P1 and Defender CSPM, per node-hour.

    Two products from one service, and both are per NODE rather than per
    vCPU as GuardDuty is -- so the estimator prices whichever unit the
    provider actually bills rather than converting between them.

    P1, not P2: P1 is the baseline server plan. Trial meters publish at
    zero and are excluded, since a trial rate is not the ongoing price.
    """
    region = provider_region(region_key, "azure")
    wanted = {
        "Standard P1 Node": ("defender:server-node", "Defender for Servers P1", "threat"),
        "DCSPM Node Defender Workload Unit": (
            "defender:cspm-node", "Defender CSPM", "posture",
        ),
    }
    found: dict[str, PricePoint] = {}

    for item in _paged(
        "serviceName eq 'Microsoft Defender for Cloud' and priceType eq 'Consumption'",
        max_pages=10,
    ):
        if "US Gov" in (item.get("armRegionName") or ""):
            continue
        meter = item.get("meterName") or ""
        if meter not in wanted or wanted[meter][0] in found:
            continue
        price = _decimal(item.get("retailPrice"))
        if price is None:
            continue
        sku, name, category = wanted[meter]
        found[sku] = PricePoint(
            provider="azure",
            category=category,
            sku=sku,
            name=name,
            region=region,
            unit="node-hour",
            price_usd=price,
        )
    return list(found.values())


def fetch_auth_prices(region_key: str) -> list[PricePoint]:
    """Entra External ID (B2C) monthly active users, with its free band.

    Free to 50,000 MAU and graduated above it, which is close enough to
    Cognito's shape that the two compare directly. Sovereign-cloud rows
    charge from the first user, so filtering them out is what keeps a
    300-staff estimate at zero rather than $2.06.
    """
    region = provider_region(region_key, "azure")
    bands: list[PriceTier] = []

    for item in _paged("serviceName eq 'Azure Active Directory B2C'", max_pages=8):
        if not _is_commercial(item):
            continue
        if (item.get("meterName") or "") != "Standard Monthly Active Users":
            continue
        price = _decimal_allow_zero(item.get("retailPrice"))
        if price is None:
            continue
        begin = Decimal(str(item.get("tierMinimumUnits") or 0))
        if any(t.begin == begin for t in bands):
            continue
        bands.append(PriceTier(begin=begin, end=None, price_usd=price))

    if not bands:
        return []

    bands.sort(key=lambda t: t.begin)
    closed = tuple(
        PriceTier(
            begin=t.begin,
            end=bands[i + 1].begin if i + 1 < len(bands) else None,
            price_usd=t.price_usd,
        )
        for i, t in enumerate(bands)
    )
    return [
        PricePoint(
            provider="azure",
            category="auth",
            sku="entra:external-id-mau",
            name="Entra External ID (monthly active users)",
            region=region,
            unit="MAU",
            price_usd=closed[0].price_usd,
            tiers=closed,
        )
    ]


def fetch_tracing_prices(region_key: str) -> list[PricePoint]:
    """Application Insights data ingestion.

    Billed per GB ingested where X-Ray bills per trace recorded, so the
    two are not convertible and the estimator prices whichever unit the
    provider publishes. Ingestion, not "Data Retention" ($0.10/GB-month):
    retention is what you pay to keep telemetry after the free period, not
    what you pay to collect it.
    """
    region = provider_region(region_key, "azure")

    for item in _paged("serviceName eq 'Application Insights'", max_pages=8):
        if not _is_commercial(item):
            continue
        if (item.get("meterName") or "") != "Enterprise Overage Data":
            continue
        price = _decimal(item.get("retailPrice"))
        if price is None:
            continue
        return [
            PricePoint(
                provider="azure",
                category="tracing",
                sku="appinsights:ingestion",
                name="Application Insights ingestion",
                region=region,
                unit="GB",
                price_usd=price,
            )
        ]
    return []


def fetch_free_tier_prices(region_key: str) -> list[PricePoint]:
    """Azure services that are genuinely free, recorded so they appear.

    ASSERTED, NOT FETCHED -- the same exception ACM gets on AWS, and
    flagged for the same reason. Neither has a meter in the retail feed
    because neither is metered:

      * Activity Log keeps 90 days of control-plane events at no charge.
        Exporting them to a workspace costs; having them does not.
      * App Service managed certificates are issued and renewed free.

    Safe in a way an asserted non-zero price would not be: a wrong $0 here
    cannot inflate anyone's bill. If Microsoft starts charging, this goes
    silently wrong -- which is why it is flagged here and in each point's
    attributes rather than buried.
    """
    region = provider_region(region_key, "azure")
    basis = "asserted: Microsoft publishes no meter, service is free"
    return [
        PricePoint(
            provider="azure",
            category="audit",
            sku="activitylog:events",
            name="Activity Log (90-day retention)",
            region=region,
            unit="month",
            price_usd=Decimal(0),
            attributes={"basis": basis},
        ),
        PricePoint(
            provider="azure",
            category="tls",
            sku="appservice:managed-certificate",
            name="App Service managed certificate",
            region=region,
            unit="month",
            price_usd=Decimal(0),
            attributes={"basis": basis},
        ),
    ]


def fetch_waf_prices(region_key: str) -> list[PricePoint]:
    """Application Gateway WAF v2: the gateway itself, hourly.

    Azure sells the firewall as a tier of Application Gateway rather than a
    separate product, which is why searching for a "Web Application
    Firewall" service returns nothing -- the meter lives under
    `Application Gateway`, product `Application Gateway WAF v2`.
    """
    region = provider_region(region_key, "azure")
    for item in _paged(
        "serviceName eq 'Application Gateway' and priceType eq 'Consumption'",
        max_pages=5,
    ):
        if item.get("armRegionName") not in (region, "Global", ""):
            continue
        if item.get("productName") != "Application Gateway WAF v2":
            continue
        if item.get("meterName") != "Standard Fixed Cost":
            continue
        price = _decimal(item.get("retailPrice"))
        if price is None:
            continue
        return [
            PricePoint(
                provider="azure",
                category="waf",
                sku="appgw-waf-v2:gateway-hour",
                name="Application Gateway WAF v2",
                region=region,
                unit="hour",
                price_usd=price,
                attributes={"tier": "WAF_v2"},
            )
        ]
    return []


def fetch_lcu_prices(region_key: str) -> list[PricePoint]:
    """Application Gateway capacity units -- Azure's equivalent of an LCU.

    One unit covers a bundle of throughput, connections and compute, the
    same shape as an AWS load balancer capacity unit, so the estimator can
    size both from one number.
    """
    region = provider_region(region_key, "azure")
    for item in _paged(
        "serviceName eq 'Application Gateway' and priceType eq 'Consumption'",
        max_pages=5,
    ):
        if item.get("armRegionName") not in (region, "Global", ""):
            continue
        if item.get("productName") != "Application Gateway WAF v2":
            continue
        if item.get("meterName") != "Standard Capacity Units":
            continue
        price = _decimal(item.get("retailPrice"))
        if price is None:
            continue
        return [
            PricePoint(
                provider="azure",
                category="lcu",
                sku="appgw:capacity-unit-hour",
                name="Application Gateway capacity units",
                region=region,
                unit="hour",
                price_usd=price,
                attributes={"tier": "WAF_v2"},
            )
        ]
    return []


#: Azure Front Door bills egress by client ZONE, not by the origin region.
#: Microsoft's documented zones: North America/Europe = Zone 1, Asia-Pacific =
#: Zone 2, India = Zone 5. We map each region we serve to its Front Door zone
#: and take that zone's "Standard Data Transfer Out" first-tier rate.
_AZURE_FRONTDOOR_ZONE = {
    "india": "Zone 5", "india-south": "Zone 5", "singapore": "Zone 2",
    "us-east": "Zone 1", "eu-west": "Zone 1",
}


#: Cosmos DB bills ONE request-unit rate; the read/write asymmetry is in how
#: many RUs an operation consumes, not in the price. Microsoft's documented
#: model for a 1 KB item: a point read costs 1 RU, a write costs ~5 RU. The
#: engine passes read and write REQUEST COUNTS (the DynamoDB model, where the
#: asymmetry is priced instead), so the write rate is scaled by this factor to
#: keep both providers answering the same question. Derived, and labelled so.
_COSMOS_RU_PER_WRITE = 5


def _first_paid(items, match) -> "Decimal | None":
    """Lowest non-zero rate among rows `match` accepts.

    Azure publishes consumption meters as graduated bands with a free grant at
    tierMinimumUnits 0. `_decimal` already returns None for a zero price, so
    this picks the first band a real workload actually pays.
    """
    best = None
    for item in items:
        if not match(item):
            continue
        price = _decimal(item.get("retailPrice"))
        if price is None:
            continue
        if best is None or price < best:
            best = price
    return best


def _consumption(service: str, region: str, pages: int = 6) -> list[dict]:
    return [
        it for it in _paged(
            f"serviceName eq '{service}' and priceType eq 'Consumption' "
            f"and armRegionName eq '{region}'", max_pages=pages
        )
    ]


def fetch_streaming_prices(region_key: str) -> list[PricePoint]:
    """Event Hubs -- the Kinesis-equivalent event stream.

    A Standard throughput unit is the capacity unit a Kinesis shard is, and
    ingress events are billed per million the way Kinesis put payload units
    are, so both map onto the streaming role's existing sku names.
    """
    region = provider_region(region_key, "azure")
    items = _consumption("Event Hubs", region)
    def meter(name):
        return _first_paid(items, lambda i: (i.get("meterName") or "") == name)
    tu, ingress = meter("Standard Throughput Unit"), meter("Standard Ingress Events")
    capture, kafka = meter("Standard Capture"), meter("Standard Kafka Endpoint")
    out: list[PricePoint] = []
    if capture is not None:
        # Firehose bills delivery per GB; Event Hubs Capture bills per hour of
        # the capture feature. Different meters for the same capability, so it
        # is published in its own category and the estimator prices it hourly
        # rather than multiplying an hourly rate by a GB figure.
        out.append(PricePoint(provider="azure", category="capture_hour",
            sku="eventhubs:capture-hour", name="Event Hubs Capture",
            region=region, unit="hour", price_usd=capture))
    if kafka is not None:
        # MSK sells sized broker NODES; Event Hubs exposes a Kafka endpoint on
        # the namespace at an hourly rate, with capacity coming from throughput
        # units. Published as an endpoint, priced per broker requested.
        out.append(PricePoint(provider="azure", category="kafka_endpoint",
            sku="eventhubs:kafka-endpoint", name="Event Hubs Kafka endpoint",
            region=region, unit="hour", price_usd=kafka))
    if tu is not None:
        out.append(PricePoint(provider="azure", category="streaming",
            sku="kinesis:shard-hour", name="Event Hubs throughput unit",
            region=region, unit="hour", price_usd=tu))
    if ingress is not None:
        out.append(PricePoint(provider="azure", category="streaming",
            sku="kinesis:put-payload-units", name="Event Hubs ingress events",
            region=region, unit="request",
            price_usd=ingress / Decimal(1_000_000)))   # published per 1M
    return out


def fetch_warehouse_prices(region_key: str) -> list[PricePoint]:
    """Synapse dedicated SQL pool, priced per DW100c unit-hour.

    Redshift sells sized NODES; Synapse sells data-warehouse units. DW100c --
    100 DWUs, the smallest dedicated pool you can provision -- is the closest
    like-for-like to one node, so it is published in its own category and the
    estimator prices one unit per requested node.
    """
    region = provider_region(region_key, "azure")
    price = _first_paid(
        _consumption("Azure Synapse Analytics", region),
        lambda i: "DWU" in (i.get("meterName") or "")
        and "Provisioned" in (i.get("productName") or ""),
    )
    if price is None:
        return []
    return [PricePoint(provider="azure", category="warehouse_unit",
        sku="synapse:dw100c-hour", name="Synapse dedicated SQL (DW100c)",
        region=region, unit="hour", price_usd=price,
        attributes={"dwu": "100"})]


def fetch_vision_prices(region_key: str) -> list[PricePoint]:
    """Azure Vision image analysis, per transaction -- the Rekognition role.

    Published under serviceName "Foundry Tools" since the Azure AI Foundry
    rebrand (the older "Cognitive Services" name returns nothing), and priced
    per 1K transactions. Commitment-tier and disconnected-container meters are
    excluded: those are annual capacity purchases, not pay-as-you-go.
    """
    region = provider_region(region_key, "azure")
    best = None
    for item in _paged(
        "serviceName eq 'Foundry Tools' and priceType eq 'Consumption'", max_pages=8
    ):
        product = item.get("productName") or ""
        meter = item.get("meterName") or ""
        if "Vision" not in product or "Disconnected" in product:
            continue
        # ALLOW-LIST the image-analysis meter specifically. "Vision" +
        # "Transactions" alone also matches Image Retrieval ingestion ($0.03/1K
        # -- a vector-index feature, not analysis), and taking the cheapest
        # priced image recognition 33x under AWS and GCP. Commitment-tier and
        # overage bands are excluded: those price a prepaid capacity purchase.
        if "Image Analysis" not in meter or "Transactions" not in meter:
            continue
        if "Commitment" in meter or "Overage" in meter or "Free" in meter:
            continue
        if item.get("armRegionName") not in (region, "Global", ""):
            continue
        price = _decimal(item.get("retailPrice"))
        if price is not None and (best is None or price < best):
            best = price
    if best is None:
        return []
    return [PricePoint(provider="azure", category="rekognition", sku="aivision:transactions",
        name="Azure Vision image analysis", region=region, unit="image",
        price_usd=best / Decimal(1000))]   # published per 1K transactions


#: Hours in the one-year reservation term Azure quotes a total price for.
_RESERVATION_HOURS_1YR = 365 * 24


def fetch_vm_reservation_prices(region_key: str) -> list[PricePoint]:
    """One-year Reserved VM Instances, converted to an hourly rate.

    Azure publishes reservations as the TOTAL cost of the term (a 1-Year row
    reads e.g. $10,842) even though unitOfMeasure says "1 Hour" -- so the
    figure has to be divided by the hours in the term to compare with the
    on-demand rate. Quoting it as published would overstate compute by four
    orders of magnitude.

    Matched to the same armSkuName the on-demand VM rows use, so the estimator
    finds the committed variant of the machine it already chose.
    """
    region = provider_region(region_key, "azure")
    best: dict[str, Decimal] = {}
    for item in _paged(
        f"serviceName eq 'Virtual Machines' and armRegionName eq '{region}' "
        "and priceType eq 'Reservation'", max_pages=12
    ):
        if item.get("reservationTerm") != "1 Year":
            continue
        sku = item.get("armSkuName") or ""
        # Same allow-list the on-demand loader uses: Linux only, no Windows /
        # sovereign-cloud / low-priority variants riding the same sku name.
        blob = _blob(item, "skuName", "meterName", "productName")
        if not sku or any(term in blob for term in _EXCLUDE_VM):
            continue
        if not _is_commercial(item):
            continue
        total = _decimal(item.get("retailPrice"))
        if total is None:
            continue
        hourly = total / Decimal(_RESERVATION_HOURS_1YR)
        if sku not in best or hourly < best[sku]:
            best[sku] = hourly

    # Carry the machine's SPECS across from the on-demand rows. The reservation
    # feed publishes no vCPU/memory/arch, and cheapest_compute selects on
    # exactly those columns -- so without this the committed rates load fine
    # and are then invisible to every lookup that could use them.
    specs = {
        pt.sku: pt
        for pt in fetch_vm_prices(region_key)
        if pt.attributes.get("purchase") == "ondemand"
    }
    points: list[PricePoint] = []
    for sku, hourly in best.items():
        base = specs.get(sku)
        if base is None:
            continue      # a machine we do not otherwise quote
        points.append(PricePoint(
            provider="azure", category="compute", sku=f"{sku}:commit1yr",
            name=f"{sku} (1-yr reserved)", region=region, unit="hour",
            price_usd=hourly,
            vcpu=base.vcpu, memory_gb=base.memory_gb, arch=base.arch,
            attributes=_with_baseline({"purchase": "commit1yr",
                        "term": "1-year Reserved VM Instance"}, "azure", base.sku),
        ))
    return points


def fetch_container_prices(region_key: str) -> list[PricePoint]:
    """Azure Container Instances -- the Fargate-equivalent serverless container
    tier, billed per vCPU-hour and per GB-hour exactly as Fargate is.

    Published under the sku names the estimator's container block looks up, so
    the same code path prices all three clouds.
    """
    region = provider_region(region_key, "azure")
    items = _consumption("Container Instances", region)
    def std(word):
        return _first_paid(items, lambda i: (i.get("productName") or "") == "Container Instances"
                           and (i.get("meterName") or "") == f"Standard {word} Duration")
    vcpu, mem = std("vCPU"), std("Memory")
    out: list[PricePoint] = []
    if vcpu is not None:
        out.append(PricePoint(provider="azure", category="fargate", sku="fargate:vcpu-hour",
            name="Container Instances vCPU", region=region, unit="hour", price_usd=vcpu))
    if mem is not None:
        out.append(PricePoint(provider="azure", category="fargate", sku="fargate:gb-hour",
            name="Container Instances memory", region=region, unit="hour", price_usd=mem))
    return out


def fetch_functions_prices(region_key: str) -> list[PricePoint]:
    """Azure Functions consumption: executions and GB-second duration --
    the same two meters AWS Lambda bills, so they map onto the same roles."""
    region = provider_region(region_key, "azure")
    items = _consumption("Functions", region)
    out: list[PricePoint] = []
    execs = _first_paid(items, lambda i: "Total Executions" in (i.get("meterName") or ""))
    dur = _first_paid(items, lambda i: "Execution Time" in (i.get("meterName") or ""))
    if execs is not None:
        # Published per 10 executions; the estimator bills per execution.
        out.append(PricePoint(provider="azure", category="lambda-requests",
            sku="functions:executions", name="Functions executions", region=region,
            unit="request", price_usd=execs / Decimal(10)))
    if dur is not None:
        out.append(PricePoint(provider="azure", category="lambda-duration",
            sku="functions:duration", name="Functions execution time", region=region,
            unit="GB-second", price_usd=dur))
    return out


def fetch_apigateway_prices(region_key: str) -> list[PricePoint]:
    """API Management consumption tier, billed per call."""
    region = provider_region(region_key, "azure")
    price = _first_paid(_consumption("API Management", region),
                        lambda i: (i.get("meterName") or "") == "Consumption Calls")
    if price is None:
        return []
    return [PricePoint(provider="azure", category="apigateway",
        sku="apim:consumption-calls", name="API Management calls", region=region,
        unit="request", price_usd=price / Decimal(10_000))]   # published per 10K


def fetch_queue_prices(region_key: str) -> list[PricePoint]:
    """Service Bus messaging operations -- the SQS-equivalent queue meter."""
    region = provider_region(region_key, "azure")
    price = _first_paid(_consumption("Service Bus", region),
                        lambda i: "Messaging Operations" in (i.get("meterName") or ""))
    if price is None:
        return []
    return [PricePoint(provider="azure", category="queue",
        sku="servicebus:operations", name="Service Bus operations", region=region,
        unit="request", price_usd=price / Decimal(1_000_000))]  # published per 1M


def fetch_notification_prices(region_key: str) -> list[PricePoint]:
    """Notification Hubs pushes -- the SNS-equivalent notification meter."""
    region = provider_region(region_key, "azure")
    price = _first_paid(_consumption("Notification Hubs", region),
                        lambda i: "Pushes" in (i.get("meterName") or ""))
    if price is None:
        return []
    return [PricePoint(provider="azure", category="notification",
        sku="notificationhubs:pushes", name="Notification Hubs pushes", region=region,
        unit="request", price_usd=price / Decimal(1_000_000))]


def fetch_query_engine_prices(region_key: str) -> list[PricePoint]:
    """Synapse serverless SQL, billed per TB scanned -- Athena's model."""
    region = provider_region(region_key, "azure")
    price = _first_paid(_consumption("Azure Synapse Analytics", region),
        lambda i: "Serverless SQL Pool" in (i.get("productName") or "")
                  and "Data Processed" in (i.get("meterName") or ""))
    if price is None:
        return []
    return [PricePoint(provider="azure", category="athena",
        sku="synapse:serverless-scanned", name="Synapse serverless SQL data processed",
        region=region, unit="TB", price_usd=price)]


def fetch_etl_prices(region_key: str) -> list[PricePoint]:
    """Data Factory cloud data movement, per DIU-hour -- Glue's DPU-hour analogue."""
    region = provider_region(region_key, "azure")
    items = _consumption("Azure Data Factory", region)
    price = _first_paid(items, lambda i: "Data Movement" in (i.get("meterName") or "")
                                          and "On Premises" not in (i.get("meterName") or ""))
    if price is None:
        price = _first_paid(items, lambda i: "Data Movement" in (i.get("meterName") or ""))
    if price is None:
        return []
    return [PricePoint(provider="azure", category="glue",
        sku="datafactory:data-movement", name="Data Factory data movement",
        region=region, unit="DIU-hour", price_usd=price)]


def fetch_search_prices(region_key: str) -> list[PricePoint]:
    """Azure AI Search, billed per SEARCH UNIT-hour rather than per sized node.

    OpenSearch sells vCPU/RAM nodes; Azure AI Search sells capacity units at
    fixed tiers, and the feed publishes no vCPU or RAM per unit. Rather than
    invent specs so the node-spec lookup matches, this is published in its own
    category and the estimator prices units against the requested node count.
    Standard S1 is the honest production default -- Basic caps at low storage
    and small index counts, the way DEFAULT_SKUS names a sensible default
    rather than the cheapest row.
    """
    region = provider_region(region_key, "azure")
    # The product was renamed to "Azure AI Search" but the retail feed still
    # publishes its unit meters under the legacy "Azure Cognitive Search"
    # serviceName in most regions, so both are queried.
    items = []
    for service in ("Azure Cognitive Search", "Azure AI Search"):
        items = list(_paged(
            f"serviceName eq '{service}' and priceType eq 'Consumption' "
            f"and armRegionName eq '{region}'", max_pages=6
        ))
        if items:
            break
    for item in items:
        if item.get("armRegionName") not in (region, "Global", ""):
            continue
        # Exactly the S1 unit meter -- not "S1 CC Unit" (confidential compute,
        # ~45% dearer) and not the semantic-ranker / image-extraction add-ons.
        if item.get("meterName") != "Standard S1 Unit":
            continue
        price = _decimal(item.get("retailPrice"))
        if price is None:
            continue
        return [PricePoint(
            provider="azure", category="search_unit", sku="aisearch:s1-unit",
            name="Azure AI Search unit (Standard S1)", region=region,
            unit="hour", price_usd=price, attributes={"tier": "standard-s1"},
        )]
    return []


def fetch_keyvalue_prices(region_key: str) -> list[PricePoint]:
    """Azure Cosmos DB serverless -- the DynamoDB-equivalent key-value store.

    Serverless (per-RU) rather than provisioned throughput, because that is the
    mode that bills per request the way DynamoDB on-demand does.
    """
    region = provider_region(region_key, "azure")
    ru_price = None
    storage = None
    for item in _paged(
        "serviceName eq 'Azure Cosmos DB' and priceType eq 'Consumption'", max_pages=8
    ):
        if item.get("armRegionName") not in (region, "Global", ""):
            continue
        product = item.get("productName") or ""
        meter = item.get("meterName") or ""
        price = _decimal(item.get("retailPrice"))
        if price is None:
            continue
        if product == "Azure Cosmos DB serverless" and meter == "1M RUs":
            if ru_price is None or price < ru_price:
                ru_price = price
        elif product == "Azure Cosmos DB" and meter == "Data Stored":
            # ALLOW-LIST, not min(). One product/meter pair carries several
            # skuNames at very different rates: the RU-based account's
            # transactional storage (RUs/RUm/mRUs, ~$0.25/GB) alongside
            # "Data Capacity"/"Managed RUs" at $0.008 -- a different product
            # entirely. Taking the cheapest silently priced Cosmos storage 30x
            # too low, which is the "plausible and wrong" failure this catalog
            # exists to avoid.
            if item.get("skuName") not in ("RUs", "RUm", "mRUs"):
                continue
            if storage is None or price < storage:
                storage = price

    out: list[PricePoint] = []
    if ru_price is not None:
        per_ru = ru_price / Decimal(1_000_000)   # published per 1M RUs
        out.append(PricePoint(
            provider="azure", category="dynamodb-reads", sku="cosmos:read-request-units",
            name="Cosmos DB read requests (1 RU each)", region=region,
            unit="request", price_usd=per_ru,
            attributes={"ru_per_op": "1", "rate_per_1m_ru": str(ru_price)}))
        out.append(PricePoint(
            provider="azure", category="dynamodb-writes", sku="cosmos:write-request-units",
            name=f"Cosmos DB write requests (~{_COSMOS_RU_PER_WRITE} RU each)",
            region=region, unit="request",
            price_usd=per_ru * Decimal(_COSMOS_RU_PER_WRITE),
            attributes={"ru_per_op": str(_COSMOS_RU_PER_WRITE),
                        "derived": "write billed at documented ~5 RU per 1KB item",
                        "rate_per_1m_ru": str(ru_price)}))
    if storage is not None:
        out.append(PricePoint(
            provider="azure", category="dynamodb-storage", sku="cosmos:storage",
            name="Cosmos DB storage", region=region, unit="GB-month", price_usd=storage))
    return out


def fetch_cdn_prices(region_key: str) -> list[PricePoint]:
    """Azure Front Door Standard data transfer out, per GB, for the region's
    zone. The modern CDN equivalent of CloudFront/Cloud CDN egress."""
    region = provider_region(region_key, "azure")
    zone = _AZURE_FRONTDOOR_ZONE.get(region_key)
    if not zone:
        return []
    query = (
        "serviceName eq 'Azure Front Door Service' and priceType eq 'Consumption' "
        f"and armRegionName eq '{zone}' "
        "and meterName eq 'Standard Data Transfer Out'"
    )
    best: tuple[float, Decimal] | None = None
    for item in _paged(query, max_pages=4):
        price = _decimal(item.get("retailPrice"))
        if price is None:
            continue
        tier = float(item.get("tierMinimumUnits") or 0)
        if best is None or tier < best[0]:
            best = (tier, price)
    if best is None:
        return []
    return [PricePoint(
        provider="azure", category="cdn", sku="frontdoor:data-transfer-out",
        name="Front Door data transfer out", region=region, unit="GB",
        price_usd=best[1], attributes={"zone": zone},
    )]


def fetch_db_storage_prices(region_key: str) -> list[PricePoint]:
    """Storage attached to the managed database, per GB-month.

    Billed separately from the database instance on every provider, and
    large enough on a real workload that omitting it understates the bill.
    """
    region = provider_region(region_key, "azure")
    for item in _paged(
        "serviceName eq 'Azure Database for PostgreSQL' and priceType eq 'Consumption'",
        max_pages=6,
    ):
        if item.get("armRegionName") not in (region, "Global", ""):
            continue
        # The Flexible Server storage product, not HorizonDB (a different
        # engine at more than twice the rate) and not Single Server (retired).
        # The published product name is "Flex Server Storage", not the older
        # "Flexible" spelling the earlier filter looked for -- which matched
        # nothing, so db storage silently vanished from every Azure estimate.
        product = item.get("productName") or ""
        if "Flex Server Storage" not in product:
            continue
        # Exact match excludes the "Storage Data Stored - Free" $0 tier and the
        # IOPS/throughput provisioning meters that share the product.
        if item.get("meterName") != "Storage Data Stored":
            continue
        price = _decimal(item.get("retailPrice"))
        if price is None:
            continue
        return [
            PricePoint(
                provider="azure",
                category="db_storage",
                sku="postgres-flex:storage",
                name="Database storage",
                region=region,
                unit="GB-month",
                price_usd=price,
                attributes={"engine": "postgres-flexible"},
            )
        ]
    return []


def fetch_storage_tier_prices(region_key: str) -> list[PricePoint]:
    """Blob cool and archive tiers -- the targets a lifecycle policy moves to.

    Without these the catalog held only the hot tier, so "move cold data to a
    cheaper class" could be priced on AWS and nowhere else -- the same
    single-cloud bias the technique catalog already had.
    """
    region = provider_region(region_key, "azure")
    query = (
        "serviceName eq 'Storage' "
        f"and armRegionName eq '{region}' and priceType eq 'Consumption'"
    )
    wanted = {"cool": ("blob:cool-lrs", "Blob storage (cool, LRS)", "infrequent"),
              "archive": ("blob:archive-lrs", "Blob storage (archive, LRS)", "archive")}
    best: dict[str, tuple] = {}
    for item in _paged(query, max_pages=12):
        unit = (item.get("unitOfMeasure") or "").lower()
        if "gb/month" not in unit and "gb-month" not in unit:
            continue
        blob = _blob(item, "skuName", "meterName", "productName")
        if "lrs" not in blob or "premium" in blob:
            continue
        for tier in wanted:
            if tier not in blob:
                continue
            price = _decimal(item.get("retailPrice"))
            if price is None:
                continue
            if tier not in best or price < best[tier][0]:
                best[tier] = (price, item)
    out: list[PricePoint] = []
    for tier, (price, _item) in best.items():
        sku, name, role = wanted[tier]
        out.append(PricePoint(provider="azure", category="storage_lifecycle",
            sku=sku, name=name, region=region, unit="GB-month",
            price_usd=price, attributes={"tier": tier, "role": role}))
    return out


def fetch_blob_request_prices(region_key: str) -> list[PricePoint]:
    """Blob read and write operations, Azure's answer to S3 requests.

    Hot tier, locally redundant: the tier and redundancy an application's
    own object storage actually runs on. Cool and archive are cheaper to
    store and dearer to touch, and the geo-redundant variants cost
    multiples of the local one.

    Each meter is fetched with its own server-side filter rather than by
    scanning the Storage service. That service publishes tens of thousands
    of meters -- blobs, files, queues, tables, disks, every tier crossed
    with every redundancy -- and the read meter sits far enough down the
    listing that a paged scan gave up before reaching it, returning the
    write price alone and calling the pair complete.
    """
    region = provider_region(region_key, "azure")

    # The asymmetry is Azure's, not a typo: the write meter carries the
    # redundancy in its name and the read meter does not.
    wanted = (
        ("Hot LRS Write Operations", "blob:put-requests", "Blob write requests"),
        ("Hot Read Operations", "blob:get-requests", "Blob read requests"),
    )

    points: list[PricePoint] = []
    for meter, sku, name in wanted:
        for item in _paged(
            f"serviceName eq 'Storage' and meterName eq '{meter}'"
            " and priceType eq 'Consumption'",
            max_pages=4,
        ):
            if item.get("armRegionName") not in (region, "Global", ""):
                continue
            if item.get("productName") != "General Block Blob v2":
                continue
            price = _decimal(item.get("retailPrice"))
            if price is None:
                continue
            # Normalised to per-request, because that is what the
            # estimator multiplies by and what AWS already stores.
            # Azure publishes per 10,000 operations, and billing the raw
            # meter rate against a request count overstated object storage
            # by four orders of magnitude -- $12,000 a month of blob writes
            # on a workload whose real figure is $1.20.
            #
            # The two providers agree once the units match: Azure's
            # $0.05/10K and AWS's $0.000005/request are both $5 per million.
            points.append(
                PricePoint(
                    provider="azure",
                    category="s3_requests",
                    sku=sku,
                    name=name,
                    region=region,
                    unit="request",
                    price_usd=price / Decimal("10000"),
                    attributes={
                        "tier": "hot",
                        "redundancy": "LRS",
                        "published_per": "10K operations",
                    },
                )
            )
            break
    return points


def load_all(region_key: str) -> list[PricePoint]:
    """Every category we price on Azure, for one region."""
    points: list[PricePoint] = []
    for loader in (
        fetch_vm_prices,
        fetch_database_prices,
        fetch_storage_prices,
        fetch_egress_prices,
        fetch_cdn_prices,
        fetch_keyvalue_prices,
        fetch_search_prices,
        fetch_functions_prices,
        fetch_vm_reservation_prices,
        fetch_container_prices,
        fetch_vision_prices,
        fetch_warehouse_prices,
        fetch_streaming_prices,
        fetch_apigateway_prices,
        fetch_queue_prices,
        fetch_notification_prices,
        fetch_query_engine_prices,
        fetch_etl_prices,
        fetch_cache_prices,
        fetch_monitoring_prices,
        fetch_loadbalancer_prices,
        fetch_nat_prices,
        fetch_dns_prices,
        fetch_keyvault_prices,
        fetch_backup_prices,
        fetch_flowlog_prices,
        fetch_defender_prices,
        fetch_auth_prices,
        fetch_tracing_prices,
        fetch_free_tier_prices,
        fetch_waf_prices,
        fetch_lcu_prices,
        fetch_db_storage_prices,
        fetch_storage_tier_prices,
        fetch_blob_request_prices,
    ):
        try:
            points.extend(loader(region_key))
        except Exception as exc:
            print(f"  ! azure {loader.__name__} failed: {exc}")
    return points
