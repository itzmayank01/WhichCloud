#!/usr/bin/env python3
"""Check our GCP compute prices against Google's own Cloud Billing Catalog.

GCP compute is the one part of the catalog with no second source: it comes
from Vantage's machine-type feed, which is convenient and third-party. The
Catalog API changes that, because Google publishes the rates it bills at --
not per instance, but per vCPU-hour and per GB-of-RAM-hour, per machine
family.

A predefined machine type is exactly its parts, so the two can be compared:

    expected = vCPUs x core rate  +  memory GB x ram rate

Anything that is not a plain predefined type is skipped rather than forced:
shared-core types (e2-micro and friends) are not sold as whole cores and do
not follow the formula, and sole-tenancy, commitment, spot and premium SKUs
are different products that happen to match on family name.

    python scripts/validate_gcp_compute.py --region india
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whichcloud.pricing import gcp
from whichcloud.pricing.models import provider_region
from whichcloud.pricing.store import connect

GREEN, YELLOW, RED, BOLD, DIM, RESET = (
    "\033[32m", "\033[33m", "\033[31m", "\033[1m", "\033[2m", "\033[0m",
)

# Sole tenancy, commitments, spot and the various premiums are separate
# products that mention the same family names.
EXCLUDE = ("sole tenancy", "premium", "commitment", "preemptible", "spot", "custom")

# e2-micro, e2-small and e2-medium are fractions of a core, sold as a bundle
# rather than as cores plus RAM, so the formula does not describe them.
SHARED_CORE = re.compile(r"-(micro|small|medium)$")

# Machines that carry hardware beyond cores and RAM. Their price legitimately
# includes SKUs this formula does not add up -- local SSD, GPUs, a whole host
# for bare metal -- so comparing them would report our figure as wrong when
# what is actually wrong is the comparison. They are excluded rather than
# counted as failures, and the count of exclusions is printed.
ATTACHED = re.compile(r"(lssd|metal|gpu|tpu|ultramem|megamem)")

# Z3 is the storage-optimised family: every shape ships local SSD whether or
# not the name says so, so it belongs with the above.
ATTACHED_FAMILIES = {"Z3"}


def family_of(name: str) -> str | None:
    """n2d-standard-2 -> N2D."""
    head = name.split("-", 1)[0]
    return head.upper() if head else None


def catalog_rates(region: str) -> dict[str, dict[str, Decimal]]:
    """Per-family core and RAM rates, straight from Google."""
    service = gcp.find_service_id("Compute Engine")
    if not service:
        return {}

    rates: dict[str, dict[str, Decimal]] = {}
    for sku in gcp.fetch_skus(service):
        if region not in sku.get("serviceRegions", []):
            continue
        if sku.get("category", {}).get("usageType") != "OnDemand":
            continue
        desc = sku["description"].lower()
        if any(term in desc for term in EXCLUDE):
            continue

        if "instance core" in desc:
            kind = "core"
        elif "instance ram" in desc:
            kind = "ram"
        else:
            continue

        price = gcp.sku_price(sku)
        if price is None:
            continue

        # "N2D AMD Instance Core running in Mumbai" -> N2D
        family = desc.split(" instance ")[0].split()[0].upper()
        rates.setdefault(family, {})
        # Lowest rate per family: the plain one, not an upgrade tier.
        if kind not in rates[family] or price < rates[family][kind]:
            rates[family][kind] = price
    return rates


def ours(region: str) -> dict[str, tuple[Decimal, int, float]]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT sku, price_usd, vcpu, memory_gb FROM price_points
               WHERE provider='gcp' AND region=%s AND category='compute'
                 AND attributes->>'purchase' = 'ondemand'""",
            (region,),
        )
        return {
            r["sku"]: (r["price_usd"], r["vcpu"], float(r["memory_gb"] or 0))
            for r in cur.fetchall()
            if r["vcpu"] and r["memory_gb"]
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="india")
    parser.add_argument("--tolerance", type=float, default=1.0)
    args = parser.parse_args()

    if not gcp.catalog_api_available():
        print("GOOGLE_CLOUD_API_KEY is not set — nothing to validate against.")
        return 1

    region = provider_region(args.region, "gcp")
    print(f"{BOLD}GCP compute — our catalog (Vantage) vs Google's Cloud Billing Catalog{RESET}")
    print(f"{DIM}region {region}{RESET}")

    rates = catalog_rates(region)
    mine = ours(region)
    if not rates or not mine:
        print(f"  {RED}nothing to compare{RESET}")
        return 2

    exact = within = 0
    checked = 0
    skipped_family = 0
    skipped_attached = 0
    worst: list[tuple[str, Decimal, Decimal, float]] = []

    for name, (price, vcpu, memory) in sorted(mine.items()):
        if SHARED_CORE.search(name):
            continue
        if ATTACHED.search(name) or family_of(name) in ATTACHED_FAMILIES:
            skipped_attached += 1
            continue
        fam = family_of(name)
        r = rates.get(fam or "")
        if not r or "core" not in r or "ram" not in r:
            skipped_family += 1
            continue

        expected = r["core"] * Decimal(vcpu) + r["ram"] * Decimal(str(memory))
        if expected <= 0:
            continue
        checked += 1
        drift = float(abs(price - expected) / expected * 100)
        if drift < 0.01:
            exact += 1
        if drift <= args.tolerance:
            within += 1
        else:
            worst.append((name, price, expected, drift))

    if not checked:
        print(f"  {RED}no comparable machine types{RESET}")
        return 2

    print(f"  compared              {checked} predefined types")
    print(f"  exact match           {exact}   {exact / checked * 100:.1f}%")
    print(f"  within {args.tolerance:g}%             {within}   {within / checked * 100:.1f}%")
    print(f"  outside tolerance     {len(worst)}")
    if skipped_family:
        print(f"{DIM}  {skipped_family} skipped: family not priced as cores + RAM{RESET}")
    if skipped_attached:
        print(
            f"{DIM}  {skipped_attached} skipped: local SSD, GPU or bare metal, "
            f"priced with SKUs this formula does not sum{RESET}"
        )

    if worst:
        print(f"{YELLOW}  largest discrepancies{RESET}")
        for name, a, b, d in sorted(worst, key=lambda x: -x[3])[:5]:
            print(f"    {name:<22} ours ${a:<14} google ${b:.8f}   {d:.2f}%")

    # Anything still outside tolerance is reported, not excluded. The C4D
    # highmem shapes sit at a steady 3.4%, which is this script taking one
    # RAM rate per family where Google charges a different one for highmem --
    # a limit of the comparison, not evidence about the price. Naming it is
    # worth more than a higher number would be. 
    ok = within / checked >= 0.95
    print(
        f"  {GREEN}✓ validated{RESET}" if ok else f"  {RED}✗ below 95%{RESET}",
        f"— {within / checked * 100:.1f}% agree within {args.tolerance:g}%",
    )
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
