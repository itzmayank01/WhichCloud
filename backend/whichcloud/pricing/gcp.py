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

INSTANCES_URL = "https://instances.vantage.sh/gcp/instances.json"
CATALOG_API = "https://cloudbilling.googleapis.com/v1/services"

CACHE_DIR = Path(os.getenv("WHICHCLOUD_CACHE", Path.home() / ".cache" / "whichcloud"))

# GCP does not label architecture in the catalog. These families are ARM:
# T2A is Ampere Altra, C4A is Google's own Axion.
_ARM_PREFIXES = ("t2a-", "c4a-")


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


def _arch(instance_type: str) -> str:
    return "arm64" if instance_type.startswith(_ARM_PREFIXES) else "x86_64"


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
        arch = _arch(name)
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


def load_all(region_key: str, path: Path | None = None) -> list[PricePoint]:
    """Every GCP category we can price without credentials.

    Compute only. Storage, egress and managed databases need the Catalog API
    key — the estimator will report them as missing rather than guess.
    """
    return load_compute_prices(region_key, path)
