#!/usr/bin/env python3
"""Validate our catalog against AWS's own authoritative price list.

Our EC2 prices come from ec2instances.info (Vantage), which is convenient but
second-hand. AWS publishes the authoritative rates in its Price List CSV. This
script streams that CSV and compares it, row by row, against what we ingested.

That makes the PRD's accuracy target measurable instead of aspirational: if
these two independent sources agree, our compute pricing is correct by
construction, not by assumption.

The CSV is ~195 MB and is streamed, never loaded into memory.

    python scripts/validate_pricing.py --region india
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from decimal import Decimal

import httpx

from whichcloud.pricing import aws
from whichcloud.pricing.models import REGIONS, provider_region
from whichcloud.pricing.store import connect

BOLD, DIM, GREEN, YELLOW, RED, RESET = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m",
)

# The combination that identifies a plain on-demand Linux instance-hour.
WANTED = {
    "TermType": "OnDemand",
    "Operating System": "Linux",
    "Tenancy": "Shared",
    "Pre Installed S/W": "NA",
    "CapacityStatus": "Used",
    "License Model": "No License required",
}


def csv_url(region_key: str) -> str:
    region = provider_region(region_key, "aws")
    index = httpx.get(
        aws.BULK_REGION_INDEX.format(service="AmazonEC2"), timeout=90.0
    )
    index.raise_for_status()
    path = index.json()["regions"][region]["currentVersionUrl"]
    return aws.BULK_BASE + path.replace(".json", ".csv")


def authoritative_prices(region_key: str) -> dict[str, Decimal]:
    """Stream AWS's CSV and pull out on-demand Linux instance-hour rates."""
    url = csv_url(region_key)
    prices: dict[str, Decimal] = {}

    with httpx.stream("GET", url, timeout=900.0, follow_redirects=True) as response:
        response.raise_for_status()
        lines = response.iter_lines()

        # The first five lines are metadata; the sixth is the header.
        for _ in range(5):
            next(lines)
        reader = csv.DictReader(lines, fieldnames=next(csv.reader([next(lines)])))

        for row in reader:
            if any(row.get(k) != v for k, v in WANTED.items()):
                continue
            if row.get("Unit") != "Hrs":
                continue
            instance = row.get("Instance Type") or ""
            raw = row.get("PricePerUnit") or "0"
            try:
                price = Decimal(raw)
            except Exception:
                continue
            if not instance or price <= 0:
                continue
            # Keep the lowest rate published for the type.
            if instance not in prices or price < prices[instance]:
                prices[instance] = price

    return prices


def our_prices(region_key: str, provider: str = "aws") -> dict[str, Decimal]:
    region = provider_region(region_key, provider)
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT sku, price_usd FROM price_points
               WHERE provider=%s AND region=%s AND category='compute'
                 AND attributes->>'purchase' = 'ondemand'""",
            (provider, region),
        )
        return {r["sku"]: Decimal(r["price_usd"]) for r in cur.fetchall()}


def azure_reference_prices(region_key: str) -> dict[str, Decimal]:
    """Azure VM prices from the Vantage catalog.

    This is a genuinely independent second source: our catalog is built from
    Microsoft's Retail Prices API, while this file is compiled separately. If
    the two agree, the numbers are not an artefact of one feed.

    Vantage spells regions with hyphens ('central-india') where ARM uses none
    ('centralindia'), so the key is normalised by removing them.
    """
    from whichcloud.pricing import specs

    arm_region = provider_region(region_key, "azure")

    with specs.download_azure_catalog().open() as fh:
        catalog = json.load(fh)

    prices: dict[str, Decimal] = {}
    for entry in catalog:
        name = entry.get("instance_type")
        if not name:
            continue
        for raw_region, pricing in (entry.get("pricing") or {}).items():
            if raw_region.replace("-", "") != arm_region:
                continue
            value = ((pricing or {}).get("linux") or {}).get("ondemand")
            try:
                price = Decimal(str(value))
            except Exception:
                continue
            if price > 0:
                prices[specs.normalize_azure_sku(str(name))] = price
    return prices


def compare_sources(
    label: str,
    ours: dict[str, Decimal],
    theirs: dict[str, Decimal],
    tolerance: float,
) -> bool:
    """Report agreement between our catalog and an independent source."""
    print(f"\n{BOLD}{label}{RESET}")
    if not ours:
        print(f"  {RED}catalog is empty — run ingest_prices.py first{RESET}")
        return False
    if not theirs:
        print(f"  {YELLOW}reference source returned nothing — skipped{RESET}")
        return True

    shared = sorted(set(ours) & set(theirs))
    if not shared:
        print(f"  {RED}no overlapping instance types — cannot validate{RESET}")
        return False

    exact = 0
    within = 0
    mismatches: list[tuple[str, Decimal, Decimal, float]] = []

    for name in shared:
        mine, theirs_price = ours[name], theirs[name]
        if mine == theirs_price:
            exact += 1
            within += 1
            continue
        drift = float(abs(mine - theirs_price) / theirs_price * 100)
        if drift <= tolerance:
            within += 1
        else:
            mismatches.append((name, mine, theirs_price, drift))

    total = len(shared)
    pct_exact = exact / total * 100
    pct_within = within / total * 100

    print(f"  compared             {total:>6,} types present in both sources")
    print(f"  exact match          {exact:>6,}   {pct_exact:5.1f}%")
    print(f"  within {tolerance:g}%           {within:>6,}   {pct_within:5.1f}%")
    print(f"  outside tolerance    {len(mismatches):>6,}")

    if mismatches:
        print(f"  {YELLOW}largest discrepancies{RESET}")
        for name, mine, theirs_price, drift in sorted(
            mismatches, key=lambda m: -m[3]
        )[:8]:
            print(f"    {name:<22} ours ${mine:<12} ref ${theirs_price:<12} {drift:6.2f}%")

    only_ours = set(ours) - set(theirs)
    only_theirs = set(theirs) - set(ours)
    if only_ours or only_theirs:
        print(f"  {DIM}coverage: {len(only_ours)} only in our catalog, "
              f"{len(only_theirs)} only in the reference{RESET}")

    if pct_within >= 99:
        print(f"  {GREEN}✓ validated — {pct_within:.1f}% agree within "
              f"{tolerance:g}%{RESET}")
        return True
    if pct_within >= 90:
        print(f"  {YELLOW}⚠ mostly correct ({pct_within:.1f}%); "
              f"{len(mismatches)} types drift{RESET}")
        return True
    print(f"  {RED}✗ only {pct_within:.1f}% agree — source not trustworthy{RESET}")
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--region", default="india", choices=sorted(REGIONS))
    ap.add_argument("--tolerance", type=float, default=1.0, help="percent")
    ap.add_argument("--skip-aws", action="store_true", help="skip the 195 MB download")
    args = ap.parse_args()

    print(f"\n{BOLD}WhichCloud · price validation{RESET}")
    print(f"{DIM}each provider checked against an independent second source, "
          f"region '{args.region}'{RESET}")

    ok = True

    if not args.skip_aws:
        print(f"{DIM}\n  streaming AWS price list (~195 MB, takes a minute)…{RESET}")
        ok &= compare_sources(
            "AWS — our catalog (ec2instances.info) vs AWS Price List CSV",
            our_prices(args.region, "aws"),
            authoritative_prices(args.region),
            args.tolerance,
        )

    ours_azure = {
        k.split(":")[0].removeprefix("Standard_").replace("_", "").lower(): v
        for k, v in our_prices(args.region, "azure").items()
    }
    ok &= compare_sources(
        "Azure — our catalog (Retail Prices API) vs Vantage catalog",
        ours_azure,
        azure_reference_prices(args.region),
        args.tolerance,
    )

    print(f"\n{DIM}GCP has no second credential-free source; its compute prices "
          f"come from one feed and are unvalidated.{RESET}\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
