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
import sys
import time
from functools import lru_cache
from decimal import Decimal, InvalidOperation
from pathlib import Path

import httpx

from .models import ComputeQuery, PricePoint, PriceTier, provider_region
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


def _paged(url: str, key: str, field: str, max_pages: int = 40):
    token = ""
    for _ in range(max_pages):
        params = {"pageSize": 5000}
        if token:
            params["pageToken"] = token
        # The key travels in a header, never the query string: httpx puts the
        # request URL into its exception text, so a key in the URL is a key in
        # every traceback and log line that follows a failure.
        response = httpx.get(
            url, params=params, headers={"x-goog-api-key": key}, timeout=90.0
        )
        response.raise_for_status()
        payload = response.json()
        yield from payload.get(field, [])
        token = payload.get("nextPageToken") or ""
        if not token:
            return


def catalog_api_available() -> bool:
    return bool(os.getenv("GOOGLE_CLOUD_API_KEY"))


@lru_cache(maxsize=1)
def fetch_catalog_services() -> tuple[dict, ...]:
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
    # The catalog lists every billable service on the platform, Marketplace
    # included -- thousands of them, and Google's own are not first. A single
    # unpaged GET returns whatever fits on page one, so "Cloud Storage" is
    # quietly absent and its component silently goes unpriced.
    return tuple(_paged(CATALOG_API, key, "services"))


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


@lru_cache(maxsize=64)
def find_service_id(display_name: str) -> str | None:
    """The catalog id for a service, matched on its display name."""
    target = display_name.strip().lower()
    for service in fetch_catalog_services():
        if str(service.get("displayName", "")).strip().lower() == target:
            return str(service.get("serviceId") or "")
    return None


@lru_cache(maxsize=16)
def _skus_cached(service_id: str) -> tuple[dict, ...]:
    key = os.getenv("GOOGLE_CLOUD_API_KEY")
    if not key:
        raise RuntimeError("GOOGLE_CLOUD_API_KEY is not set")
    url = f"{CATALOG_API}/{service_id}/skus"
    return tuple(_paged(url, key, "skus"))


def fetch_skus(service_id: str) -> list[dict]:
    """SKUs for one service, fetched once per process.

    Compute Engine publishes over 32,000 of them and more than one loader
    needs the set, so without this a single ingest pages the same catalog
    repeatedly and spends minutes doing it.
    """
    return list(_skus_cached(service_id))


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
    # Google meters egress per destination continent, and the resource group
    # is what separates ordinary internet egress from VPN, interconnect, CDN
    # and inter-region traffic -- the description alone does not. Most
    # destinations share one rate; the dearer ones (Australia, China) are
    # destination surcharges rather than the general rate, so the common one
    # is what belongs in a like-for-like comparison.
    matches = select_skus(
        fetch_skus(service),
        region,
        resource_family="Network",
        resource_group="PremiumInternetEgress",
        must_contain=("internet data transfer out",),
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

    # Cloud SQL is custom-sized: any vCPU count with any RAM between 0.9 and
    # 6.5 GB per vCPU, in 256 MB steps. So the grid below is not a guess at
    # which machines exist -- every one of these is orderable, and its price
    # is exactly the sum of its parts.
    #
    # It needs to be dense for a reason. A sparse ladder does not fail
    # visibly; the lookup just returns the next size up, and a request for
    # 2 vCPU / 8 GB quietly gets priced as 4 vCPU / 15 GB -- twice the machine
    # and twice the bill, reported as though it were the answer.
    points: list[PricePoint] = []
    shapes: set[tuple[int, float]] = set()
    for vcpus in (1, 2, 4, 8, 16, 32):
        for per_vcpu in (0.9, 2.0, 3.75, 4.0, 5.0, 6.5):
            memory = round(vcpus * per_vcpu * 4) / 4  # 256 MB steps
            if 0.9 * vcpus <= memory <= 6.5 * vcpus:
                shapes.add((vcpus, memory))

    for vcpus, memory in sorted(shapes):
        hourly = vcpu_hour * Decimal(vcpus) + ram_hour * Decimal(str(memory))
        points.append(
            PricePoint(
                provider="gcp",
                category="database",
                sku=f"db-custom-{vcpus}-{int(memory * 1024)}",
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
        # High-availability (regional) Cloud SQL runs a synchronous standby in
        # a second zone, billed as a second instance -- so the HA rate is 2x
        # the primary. This is DERIVED, not a distinct published meter (the
        # same model used for Azure HA), and marked so on the point. Without
        # it the engine's reliable/optimized tiers -- which ask for a
        # ':multi-az' database -- find nothing on GCP and drop their single
        # largest line, understating the bill and inverting the tier order.
        points.append(
            PricePoint(
                provider="gcp",
                category="database",
                sku=f"db-custom-{vcpus}-{int(memory * 1024)}:multi-az",
                name=f"Cloud SQL PostgreSQL {vcpus} vCPU / {memory:g} GB (HA / regional)",
                region=region,
                unit="hour",
                price_usd=hourly * 2,
                vcpu=vcpus,
                memory_gb=memory,
                attributes={
                    "engine": "postgres",
                    "composed": "true",
                    "high_availability": "true",
                    "ha_model": "derived: standby billed as a second instance (2x)",
                    "vcpu_hour_usd": str(vcpu_hour),
                    "ram_gb_hour_usd": str(ram_hour),
                },
            )
        )
    return points


#: Cloud CDN cache egress is billed by DESTINATION continent, not by the
#: region the origin sits in. India and Singapore serve Asia; the US and EU
#: regions serve their own continent. All these meters live under 'global'.
_GCP_CDN_CONTINENT = {
    "india": "to asia", "india-south": "to asia", "singapore": "to asia",
    "us-east": "to north america", "eu-west": "to europe",
}


def fetch_cdn_prices(region_key: str) -> list[PricePoint]:
    """Cloud CDN cache egress, per GB, to the region's own continent."""
    region = provider_region(region_key, "gcp")
    continent = _GCP_CDN_CONTINENT.get(region_key)
    if not continent:
        return []
    sku = _one(
        "Networking", region,
        ("cloud cdn traffic cache data transfer", continent),
    )
    if not sku:
        return []
    price = sku_price(sku)
    if price is None:
        return []
    return [PricePoint(
        provider="gcp", category="cdn", sku="cloudcdn:cache-egress",
        name="Cloud CDN cache egress", region=region, unit="GB",
        price_usd=price, attributes={"destination": continent},
    )]


def fetch_db_storage_prices(region_key: str) -> list[PricePoint]:
    """Cloud SQL storage, per GB-month. Zonal is single-AZ; Regional is the
    HA variant (a synchronous copy in a second zone, ~2x), matched to the
    ':multi-az' database the reliable/optimized tiers ask for."""
    region = provider_region(region_key, "gcp")
    sid = find_service_id("Cloud SQL")
    if not sid:
        return []
    skus = fetch_skus(sid)
    common_excl = ("trial", "low cost", "enterprise", "hyperdisk",
                   "iops", "throughput", "cache", "backup")
    points: list[PricePoint] = []
    for tier_word, sku_name in (("zonal", "cloudsql:ssd-storage"),
                                ("regional", "cloudsql:ssd-storage:multi-az")):
        matches = select_skus(
            skus, region,
            must_contain=(tier_word, "standard storage"),
            must_not_contain=common_excl + (
                ("regional",) if tier_word == "zonal" else ("zonal",)
            ),
        )
        price = min((sku_price(m) for m in matches), default=None)
        if price is None:
            continue
        points.append(PricePoint(
            provider="gcp", category="db_storage", sku=sku_name,
            name="Database storage" + (" (HA / regional)" if tier_word == "regional" else ""),
            region=region, unit="GB-month", price_usd=price,
            attributes={"tier": tier_word},
        ))
    return points


#: Firestore SKUs are named by LOCATION rather than region code, and their
#: serviceRegions are inconsistent (some "global", some the real region), so
#: they are matched on the location word in the description.
_GCP_FIRESTORE_LOCATION = {
    "india": "mumbai", "india-south": "delhi",
    "singapore": "singapore", "us-east": "south carolina", "eu-west": "belgium",
}


def fetch_keyvalue_prices(region_key: str) -> list[PricePoint]:
    """Cloud Firestore -- GCP's serverless document/key-value store, and the
    closest analogue to DynamoDB's per-request + per-GB billing.

    Mapped onto the estimator's dynamodb read/write/storage roles: Firestore
    bills "Read Ops", "Entity Writes" and "Storage" the same way DynamoDB bills
    read units, write units and GB-month, so no model is invented here.
    """
    region = provider_region(region_key, "gcp")
    place = _GCP_FIRESTORE_LOCATION.get(region_key)
    sid = find_service_id("Cloud Firestore")
    if not sid or not place:
        return []
    skus = fetch_skus(sid)

    def rate(*words: str) -> "Decimal | None":
        best = None
        for sku in skus:
            text = str(sku.get("description", "")).lower()
            if place not in text or "enterprise" in text:
                continue
            if not all(w in text for w in words):
                continue
            price = sku_price(sku)
            if price is not None and (best is None or price < best):
                best = price
        return best

    reads = rate("read ops")
    writes = rate("entity writes")
    # "storage" alone would also match backup/recovery/clone storage meters.
    stored = rate("firestore storage")

    out: list[PricePoint] = []
    if reads is not None:
        out.append(PricePoint(provider="gcp", category="dynamodb-reads",
                              sku="firestore:read-ops", name="Firestore read operations",
                              region=region, unit="request", price_usd=reads))
    if writes is not None:
        out.append(PricePoint(provider="gcp", category="dynamodb-writes",
                              sku="firestore:write-ops", name="Firestore write operations",
                              region=region, unit="request", price_usd=writes))
    if stored is not None:
        out.append(PricePoint(provider="gcp", category="dynamodb-storage",
                              sku="firestore:storage", name="Firestore storage",
                              region=region, unit="GB-month", price_usd=stored))
    return out


#: Pub/Sub bills THROUGHPUT ($/TiB), not messages. Google's documented
#: minimum billable message size is 1 KB, so a per-message rate is derived at
#: that floor -- the same "state the model, don't invent a number" approach
#: used for Cosmos RUs. Messages larger than 1 KB cost proportionally more, so
#: this is a floor, and it is labelled as derived on the point.
_PUBSUB_MIN_BILLABLE_BYTES = 1024
_BYTES_PER_TIB = 1024 ** 4


def _loc_rate(skus, region, place, *words, exclude=()):
    """Cheapest matching SKU, preferring one priced FOR THIS REGION.

    Google publishes some meters per region (named by location, e.g. "Analysis
    (asia-south1)") and others once as "global". Taking the cheapest across
    both picked the global list price over the real regional one -- BigQuery
    analysis came out at $6.25/TiB instead of asia-south1's $7.50. So regional
    matches win outright, and global is only a fallback for meters that have
    no regional variant at all (Cloud Run functions invocations, for one).
    """
    regional = None
    globalish = None
    for sku in skus:
        text = str(sku.get("description", "")).lower()
        regs = sku.get("serviceRegions") or []
        if not all(w in text for w in words):
            continue
        if any(x in text for x in exclude):
            continue
        price = sku_price(sku)
        if price is None:
            continue
        is_regional = (place and place in text) or region in regs
        if is_regional:
            if regional is None or price < regional:
                regional = price
        elif "global" in regs:
            if globalish is None or price < globalish:
                globalish = price
    return regional if regional is not None else globalish


def fetch_functions_prices(region_key: str) -> list[PricePoint]:
    """Cloud Run functions: invocations, plus CPU and memory time.

    Lambda bills requests + GB-seconds. Cloud Run functions bills invocations +
    vCPU-seconds + GiB-seconds separately, so the duration role is filled with
    the MEMORY (GiB-second) rate -- the same unit Lambda's GB-second is -- and
    the vCPU rate is recorded on the point rather than silently folded in.
    """
    region = provider_region(region_key, "gcp")
    place = _GCP_FIRESTORE_LOCATION.get(region_key, "")
    sid = find_service_id("Cloud Run Functions")
    if not sid:
        return []
    skus = fetch_skus(sid)
    out: list[PricePoint] = []
    inv = _loc_rate(skus, region, place, "invocations", exclude=("1st gen",))
    mem = _loc_rate(skus, region, place, "memory", exclude=("min-instance", "min instance", "1st gen"))
    cpu = _loc_rate(skus, region, place, "cpu", exclude=("min-instance", "min instance", "1st gen"))
    if inv is not None:
        out.append(PricePoint(provider="gcp", category="lambda-requests",
            sku="cloudrunfunctions:invocations", name="Cloud Run functions invocations",
            region=region, unit="request", price_usd=inv))
    if mem is not None:
        out.append(PricePoint(provider="gcp", category="lambda-duration",
            sku="cloudrunfunctions:memory-time", name="Cloud Run functions memory time",
            region=region, unit="GB-second", price_usd=mem,
            attributes={"vcpu_second_usd": str(cpu) if cpu is not None else ""}))
    return out


def fetch_pubsub_prices(region_key: str) -> list[PricePoint]:
    """Pub/Sub, filling BOTH the queue and notification roles.

    One service does what SQS and SNS do separately on AWS, so the same rate
    answers both. See _PUBSUB_MIN_BILLABLE_BYTES for the per-message derivation.
    """
    region = provider_region(region_key, "gcp")
    sid = find_service_id("Cloud Pub/Sub")
    if not sid:
        return []
    per_tib = _loc_rate(fetch_skus(sid), region, "", "message delivery basic")
    if per_tib is None:
        return []
    per_msg = per_tib * Decimal(_PUBSUB_MIN_BILLABLE_BYTES) / Decimal(_BYTES_PER_TIB)
    attrs = {"derived": "per-message at Google's 1 KB minimum billable size",
             "rate_per_tib": str(per_tib)}
    return [
        PricePoint(provider="gcp", category="queue", sku="pubsub:messages",
                   name="Pub/Sub messages", region=region, unit="request",
                   price_usd=per_msg, attributes=attrs),
        PricePoint(provider="gcp", category="notification", sku="pubsub:notifications",
                   name="Pub/Sub notifications", region=region, unit="request",
                   price_usd=per_msg, attributes=attrs),
    ]


def fetch_query_engine_prices(region_key: str) -> list[PricePoint]:
    """BigQuery on-demand analysis, per TiB scanned -- Athena's model."""
    region = provider_region(region_key, "gcp")
    sid = find_service_id("BigQuery")
    if not sid:
        return []
    price = _loc_rate(fetch_skus(sid), region, "", "analysis", exclude=("slots", "attribution"))
    if price is None:
        return []
    return [PricePoint(provider="gcp", category="athena", sku="bigquery:analysis",
        name="BigQuery on-demand analysis", region=region, unit="TB", price_usd=price)]


def fetch_etl_prices(region_key: str) -> list[PricePoint]:
    """Dataflow batch vCPU time -- Glue's DPU-hour analogue."""
    region = provider_region(region_key, "gcp")
    place = _GCP_FIRESTORE_LOCATION.get(region_key, "")
    sid = find_service_id("Cloud Dataflow")
    if not sid:
        return []
    price = _loc_rate(fetch_skus(sid), region, place, "vcpu time", "batch",
                      exclude=("flexrs", "arm", "streaming"))
    if price is None:
        return []
    return [PricePoint(provider="gcp", category="glue", sku="dataflow:vcpu-hour",
        name="Dataflow batch vCPU time", region=region, unit="DPU-hour", price_usd=price)]


def fetch_waf_prices(region_key: str) -> list[PricePoint]:
    """Cloud Armor: a security policy, its rules, and per-request inspection.

    The same three-part shape as AWS WAF (policy ~= Web ACL, rule, request),
    so it maps onto the estimator's existing waf acl/rule/request roles.
    """
    region = provider_region(region_key, "gcp")
    sid = find_service_id("Networking")
    if not sid:
        return []
    skus = fetch_skus(sid)
    out: list[PricePoint] = []
    for terms, sku, name, unit in (
        (("cloud armor policy",), "cloudarmor:policy", "Cloud Armor policy", "month"),
        (("cloud armor rule",), "cloudarmor:rule", "Cloud Armor rule", "month"),
        (("cloud armor requests",), "cloudarmor:request", "Cloud Armor request inspection", "request"),
    ):
        matches = select_skus(skus, region, must_contain=terms,
                              must_not_contain=("enterprise", "media", "regional"))
        price = min((sku_price(m) for m in matches), default=None)
        if price is not None:
            out.append(PricePoint(provider="gcp", category="waf", sku=sku,
                                  name=name, region=region, unit=unit, price_usd=price))
    return out


def fetch_object_request_prices(region_key: str) -> list[PricePoint]:
    """Cloud Storage operations -- Class A (writes) and Class B (reads),
    GCS's equivalent of S3 PUT/GET request charges."""
    region = provider_region(region_key, "gcp")
    sid = find_service_id("Cloud Storage")
    if not sid:
        return []
    skus = fetch_skus(sid)
    excl = ("autoclass", "hns", "tagging", "dual", "multi-region",
            "durable", "nearline", "coldline", "archive", "trial")
    out: list[PricePoint] = []
    for cls, sku, name in (("class a operations", "gcs:put-requests", "GCS Class A operations (writes)"),
                           ("class b operations", "gcs:get-requests", "GCS Class B operations (reads)")):
        matches = select_skus(skus, region,
                              must_contain=("regional", "standard", cls),
                              must_not_contain=excl)
        price = min((sku_price(m) for m in matches), default=None)
        if price is not None:
            out.append(PricePoint(provider="gcp", category="s3_requests", sku=sku,
                                  name=name, region=region, unit="request", price_usd=price))
    return out


def fetch_lb_data_prices(region_key: str) -> list[PricePoint]:
    """External Application Load Balancer data processing, per GB. GCP's
    analogue of ALB capacity units -- the traffic-proportional LB charge on
    top of the flat forwarding rule."""
    region = provider_region(region_key, "gcp")
    sid = find_service_id("Networking")
    if not sid:
        return []
    skus = fetch_skus(sid)
    matches = select_skus(
        skus, region,
        must_contain=("external application load balancer", "outbound data processing"),
    )
    price = min((sku_price(m) for m in matches), default=None)
    if price is None:
        return []
    return [PricePoint(provider="gcp", category="lb_data", sku="lb:data-processing",
                       name="Load balancer data processing", region=region,
                       unit="GB", price_usd=price)]


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

    # Memorystore is sold in whole GB, so every size here is real.
    points: list[PricePoint] = []
    for memory in (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 16.0, 24.0, 32.0):
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
    # Load balancing is billed under "Networking", not Compute Engine.
    service = find_service_id("Networking")
    if not service:
        return []
    # "Minimum" is what it costs to have a load balancer; "Additional" is the
    # marginal rate for rules past the fifth. Taking the cheapest match would
    # pick the marginal rate and price a load balancer at a third of the
    # truth, so the base charge is required by name.
    matches = select_skus(
        fetch_skus(service),
        region,
        resource_group="LoadBalancing",
        must_contain=("external application load balancer", "forwarding rule", "minimum"),
        must_not_contain=("internal", "cross regional", "additional"),
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
    service = find_service_id("Cloud Monitoring")
    if not service:
        return []
    # "Metric Volume", per MiB, is the ingestion charge. The service also
    # publishes per-count meters for Prometheus samples, workload metrics and
    # billed time series, all of them far cheaper per unit and none of them
    # this. Selecting the cheapest "metric" match picked one of those and
    # priced monitoring at five hundredths of a cent a month.
    matches = select_skus(
        fetch_skus(service), region, must_contain=("metric volume",)
    )
    if not matches:
        return []
    per_mib = min(sku_price(s) for s in matches)

    samples_per_month = Decimal(60 * 24 * 30)
    bytes_per_sample = Decimal(8)
    mib = Decimal(1024 * 1024)
    per_metric_month = per_mib * (samples_per_month * bytes_per_sample / mib)

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
                "published_rate_usd_per_mib": str(per_mib),
                "samples_per_metric_month": str(samples_per_month),
                "assumed_bytes_per_sample": str(bytes_per_sample),
                "assumed_resolution": "1 minute",
            },
        )
    ]


def sku_tiers(sku: dict) -> tuple[PriceTier, ...]:
    """Every graduated band on a SKU, lowest first.

    Google publishes a free allowance as a real $0 band with the paid rate
    starting at `startUsageAmount` -- Secret Manager's first six secrets,
    Cloud Trace's first 2.5 million spans. `sku_price` keeps only the first
    band, which is right for a flat rate and wrong here: it would report
    everything as free.
    """
    info = (sku.get("pricingInfo") or [{}])[0]
    rates = info.get("pricingExpression", {}).get("tieredRates", []) or []

    bands: list[PriceTier] = []
    for rate in rates:
        unit = rate.get("unitPrice", {})
        price = Decimal(str(unit.get("units", 0))) + Decimal(
            str(unit.get("nanos", 0))
        ) / Decimal(1_000_000_000)
        bands.append(
            PriceTier(
                begin=Decimal(str(rate.get("startUsageAmount", 0) or 0)),
                end=None,
                price_usd=price,
            )
        )

    bands.sort(key=lambda t: t.begin)
    return tuple(
        PriceTier(
            begin=t.begin,
            end=bands[i + 1].begin if i + 1 < len(bands) else None,
            price_usd=t.price_usd,
        )
        for i, t in enumerate(bands)
    )


def _one(
    service: str,
    region: str,
    contains: tuple[str, ...],
    *,
    excludes: tuple[str, ...] = (),
) -> dict | None:
    """The single SKU whose description carries every phrase in `contains`.

    Matching on description because these services publish one meter per
    variant -- HSM against software keys, premium against standard tiers --
    and picking by family alone would take whichever came first.
    """
    sid = find_service_id(service)
    if not sid:
        return None
    for sku in fetch_skus(sid):
        text = str(sku.get("description", "")).lower()
        if not all(c in text for c in contains):
            continue
        if any(x in text for x in excludes):
            continue
        regions = sku.get("serviceRegions") or []
        if region not in regions and "global" not in regions:
            continue
        return sku
    return None


def fetch_dns_prices(region_key: str) -> list[PricePoint]:
    """Cloud DNS managed zones and queries."""
    region = provider_region(region_key, "gcp")
    points: list[PricePoint] = []

    zone = _one("Cloud DNS", region, ("managedzone",))
    if zone:
        points.append(PricePoint(
            provider="gcp", category="dns", sku="clouddns:managed-zone",
            name="Cloud DNS managed zone", region=region, unit="month",
            price_usd=sku_price(zone), tiers=sku_tiers(zone),
        ))

    query = _one("Cloud DNS", region, ("dns query",))
    if query:
        points.append(PricePoint(
            provider="gcp", category="dns", sku="clouddns:queries",
            name="Cloud DNS queries", region=region, unit="query",
            price_usd=sku_price(query), tiers=sku_tiers(query),
        ))
    return points


def fetch_kms_prices(region_key: str) -> list[PricePoint]:
    """Cloud KMS software symmetric key versions.

    Software symmetric, not HSM or external: HSM key versions cost up to
    forty times more and are a deliberate compliance choice, not what a
    workload gets by asking for encryption at rest.
    """
    region = provider_region(region_key, "gcp")
    sku = _one(
        "Cloud Key Management Service (KMS)", region,
        ("active software symmetric key versions",),
        excludes=("hsm", "external"),
    )
    if not sku:
        return []
    return [PricePoint(
        provider="gcp", category="kms", sku="cloudkms:key-version",
        name="Cloud KMS key version", region=region, unit="month",
        price_usd=sku_price(sku), tiers=sku_tiers(sku),
    )]


def fetch_secrets_prices(region_key: str) -> list[PricePoint]:
    """Secret Manager version storage -- free for the first six."""
    region = provider_region(region_key, "gcp")
    sku = _one("Secret Manager", region, ("secret version replica storage",))
    if not sku:
        return []
    return [PricePoint(
        provider="gcp", category="secrets", sku="secretmanager:version",
        name="Secret Manager version", region=region, unit="month",
        price_usd=sku_price(sku), tiers=sku_tiers(sku),
    )]


def fetch_tracing_prices(region_key: str) -> list[PricePoint]:
    """Cloud Trace spans ingested -- free for the first 2.5 million."""
    region = provider_region(region_key, "gcp")
    sku = _one("Cloud Trace", region, ("spans ingested",))
    if not sku:
        return []
    return [PricePoint(
        provider="gcp", category="tracing", sku="cloudtrace:spans",
        name="Cloud Trace spans", region=region, unit="span",
        price_usd=sku_price(sku), tiers=sku_tiers(sku),
    )]


def fetch_nat_prices(region_key: str) -> list[PricePoint]:
    """Cloud NAT gateway uptime and data processed.

    Public NAT, not Private: "Private Nat Gateway Uptime" is a different
    product at thirty times the hourly rate.
    """
    region = provider_region(region_key, "gcp")
    points: list[PricePoint] = []

    gw = _one("Networking", region, ("cloud nat gateway uptime",), excludes=("private",))
    if gw:
        points.append(PricePoint(
            provider="gcp", category="nat", sku="cloudnat:gateway-hour",
            name="Cloud NAT gateway", region=region, unit="hour",
            price_usd=sku_price(gw), tiers=sku_tiers(gw),
        ))

    data = _one("Networking", region, ("cloud nat data processing",))
    if data:
        points.append(PricePoint(
            provider="gcp", category="nat", sku="cloudnat:gb-processed",
            name="Cloud NAT data processing", region=region, unit="GB",
            price_usd=sku_price(data), tiers=sku_tiers(data),
        ))
    return points


def fetch_tls_prices(region_key: str) -> list[PricePoint]:
    """Certificate Manager -- free for the first hundred certificates.

    The plain "Certificates usage" meter, not "Regional Certificates
    usage": both are published, at the same rate, and taking whichever
    came first would make the choice arbitrary.
    """
    region = provider_region(region_key, "gcp")
    sku = _one("Certificate Manager", region, ("certificates usage",), excludes=("regional",))
    if not sku:
        return []
    return [PricePoint(
        provider="gcp", category="tls", sku="certmanager:certificate",
        name="Certificate Manager certificate", region=region, unit="month",
        price_usd=sku_price(sku), tiers=sku_tiers(sku),
    )]


def fetch_auth_prices(region_key: str) -> list[PricePoint]:
    """Identity Platform monthly active users -- free to 50,000.

    Tier 1, and not a Tenant variant: tenants are multi-tenancy add-ons
    that start charging at fifty users rather than fifty thousand, so
    picking one would bill a 300-staff system that should be free.
    """
    region = provider_region(region_key, "gcp")
    sku = _one(
        "Identity Platform", region,
        ("tier 1 monthly active users",),
        excludes=("tenant",),
    )
    if not sku:
        return []
    return [PricePoint(
        provider="gcp", category="auth", sku="identityplatform:mau",
        name="Identity Platform (monthly active users)", region=region, unit="MAU",
        price_usd=sku_price(sku), tiers=sku_tiers(sku),
    )]


def fetch_audit_prices(region_key: str) -> list[PricePoint]:
    """Cloud Logging storage -- free for the first 50 GiB a month.

    Audit logs themselves are free to generate; what is billed is keeping
    them. "Log Storage cost", not "Log Retention cost" ($0.01/GiB-month),
    which is the charge for holding logs beyond the default window.
    """
    region = provider_region(region_key, "gcp")
    sku = _one("Cloud Logging", region, ("log storage cost",), excludes=("retention",))
    if not sku:
        return []
    return [PricePoint(
        provider="gcp", category="audit", sku="cloudlogging:storage",
        name="Cloud Logging storage", region=region, unit="GB",
        price_usd=sku_price(sku), tiers=sku_tiers(sku),
    )]


def fetch_flowlog_prices(region_key: str) -> list[PricePoint]:
    """VPC flow logs, billed as Cloud Logging vended-log storage."""
    region = provider_region(region_key, "gcp")
    sku = _one("Cloud Logging", region, ("vended logs storage",))
    if not sku:
        return []
    return [PricePoint(
        provider="gcp", category="flowlogs", sku="cloudlogging:vended-logs",
        name="VPC flow logs (vended log storage)", region=region, unit="GB",
        price_usd=sku_price(sku), tiers=sku_tiers(sku),
    )]


def fetch_backup_prices(region_key: str) -> list[PricePoint]:
    """Backup and DR management storage for Compute Engine VMs."""
    region = provider_region(region_key, "gcp")
    sku = _one(
        "Backup and DR Service", region,
        ("management", "gce vm"),
        excludes=("networking", "prepay", "commitment"),
    )
    if not sku:
        return []
    return [PricePoint(
        provider="gcp", category="backup", sku="backupdr:gce-vm",
        name="Backup and DR (GCE VM)", region=region, unit="GB-month",
        price_usd=sku_price(sku), tiers=sku_tiers(sku),
    )]


def fetch_threat_prices(region_key: str) -> list[PricePoint]:
    """Security Command Center Premium, per protected core-hour.

    SCC bills by the cores it watches, and one subscription covers both
    threat detection and posture management -- there is no separate
    product for each the way AWS splits GuardDuty from Security Hub. So
    this is priced once and the posture line folds into it rather than
    charging the same subscription twice.

    Compute Engine cores, not the BigQuery/Cloud SQL/App Engine variants:
    each of those prices SCC for a different protected service.
    """
    region = provider_region(region_key, "gcp")
    sku = _one(
        "Security Command Center", region,
        ("organization level", "compute engine", "core running"),
    )
    if not sku:
        return []
    return [PricePoint(
        provider="gcp", category="threat", sku="scc:compute-core",
        name="Security Command Center Premium", region=region, unit="core-hour",
        price_usd=sku_price(sku), tiers=sku_tiers(sku),
    )]


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
        fetch_db_storage_prices,
        fetch_cdn_prices,
        fetch_waf_prices,
        fetch_keyvalue_prices,
        fetch_functions_prices,
        fetch_pubsub_prices,
        fetch_query_engine_prices,
        fetch_etl_prices,
        fetch_object_request_prices,
        fetch_lb_data_prices,
        fetch_cache_prices,
        fetch_loadbalancer_prices,
        fetch_monitoring_prices,
        fetch_dns_prices,
        fetch_kms_prices,
        fetch_secrets_prices,
        fetch_tracing_prices,
        fetch_nat_prices,
        fetch_tls_prices,
        fetch_auth_prices,
        fetch_audit_prices,
        fetch_flowlog_prices,
        fetch_backup_prices,
        fetch_threat_prices,
    ):
        name = loader.__name__.replace("fetch_", "").replace("_prices", "")
        for attempt in range(3):
            try:
                points.extend(loader(region_key))
                break
            except (httpx.HTTPError, RuntimeError) as exc:
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue
                # One service failing must not lose the other five, nor the
                # compute catalog that needed no key. But it must not pass
                # unremarked either: silently dropping a component makes a
                # network blip indistinguishable from a real gap in the
                # catalog, and the diagram reports both as "not priced".
                print(
                    f"  ! gcp {name} could not be priced: "
                    f"{type(exc).__name__}: {str(exc)[:120]}",
                    file=sys.stderr,
                )
    return points
