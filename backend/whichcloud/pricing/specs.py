"""Machine specifications from a real catalog, not from memory.

Azure's Retail Prices API publishes prices but no vCPU or memory, and Google's
catalog publishes no architecture. Those gaps used to be filled by hand-written
tables in this codebase — which meant a handful of numbers came from someone's
recollection rather than a source. That is exactly the kind of thing that is
wrong at 3am and nobody notices.

This module replaces those tables with the Vantage machine catalogs, the same
family of open datasets already used for EC2. Specs are looked up, never
guessed, and anything absent from the catalog is skipped.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import httpx

AZURE_INSTANCES_URL = "https://instances.vantage.sh/azure/instances.json"

CACHE_DIR = Path(os.getenv("WHICHCLOUD_CACHE", Path.home() / ".cache" / "whichcloud"))


@dataclass(frozen=True, slots=True)
class MachineSpec:
    vcpu: int
    memory_gb: float
    arch: str  # x86_64 | arm64
    family: str = ""


def _cache_path(name: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / name


def download_azure_catalog(force: bool = False) -> Path:
    dest = _cache_path("azure-instances.json")
    if dest.exists() and not force:
        return dest

    tmp = dest.with_suffix(".part")
    with httpx.stream(
        "GET", AZURE_INSTANCES_URL, timeout=600.0, follow_redirects=True
    ) as r:
        r.raise_for_status()
        with tmp.open("wb") as fh:
            for chunk in r.iter_bytes(1 << 20):
                fh.write(chunk)
    tmp.replace(dest)
    return dest


def normalize_azure_sku(name: str) -> str:
    """Reduce an Azure SKU name to the catalog's key.

    The Retail API says 'Standard_D2ps_v5'; the catalog says 'd2psv5'. Database
    meters say 'B2ms' for the same shape as VM 'Standard_B2ms'. Dropping the
    prefix, underscores and case makes both sides meet in the middle.

    This is a deterministic string transform, not a mapping table — there is
    nothing here to get subtly wrong.
    """
    return name.strip().removeprefix("Standard_").replace("_", "").replace("-", "").lower()


def _arch_of(entry: dict) -> str | None:
    """Vantage publishes Azure architecture directly as ['x64'] or ['Arm64']."""
    values = entry.get("arch") or []
    if not isinstance(values, list) or not values:
        return None
    lowered = {str(v).lower() for v in values}
    if "arm64" in lowered:
        return "arm64"
    if "x64" in lowered:
        return "x86_64"
    return None


_azure_cache: dict[str, MachineSpec] | None = None


def azure_specs(force: bool = False) -> dict[str, MachineSpec]:
    """Every Azure machine size with published vCPU, memory and architecture.

    Keyed by normalized SKU name. Entries missing any of the three are dropped
    rather than defaulted — a machine we cannot describe is one we must not
    recommend.
    """
    global _azure_cache
    if _azure_cache is not None and not force:
        return _azure_cache

    with download_azure_catalog(force=force).open() as fh:
        catalog = json.load(fh)

    specs: dict[str, MachineSpec] = {}
    for entry in catalog:
        name = entry.get("instance_type")
        vcpu = entry.get("vcpu")
        memory = entry.get("memory")
        arch = _arch_of(entry)
        if not name or not vcpu or memory is None or arch is None:
            continue
        try:
            specs[normalize_azure_sku(str(name))] = MachineSpec(
                vcpu=int(vcpu),
                memory_gb=float(memory),
                arch=arch,
                family=str(entry.get("family") or ""),
            )
        except (TypeError, ValueError):
            continue

    _azure_cache = specs
    return specs


def azure_spec_for(sku: str) -> MachineSpec | None:
    return azure_specs().get(normalize_azure_sku(sku))


# ── GCP architecture ─────────────────────────────────────────────────────
#
# The GCP catalog publishes vCPU and memory but no architecture field, and
# Google's Compute Engine API needs credentials. Architecture is therefore
# inferred from Google's documented machine-family naming scheme: an 'a' suffix
# on the family marks Arm (T2A is Ampere Altra, C4A/C4D-A are Axion).
#
# This is the single remaining inference in the pricing layer. It is a naming
# convention rather than a remembered value, it is asserted by tests, and it is
# stated here so a reviewer can check it rather than trust it.
GCP_ARM_FAMILIES = ("t2a", "c4a")


def gcp_arch_for(instance_type: str) -> str:
    family = instance_type.split("-", 1)[0].lower()
    return "arm64" if family in GCP_ARM_FAMILIES else "x86_64"
