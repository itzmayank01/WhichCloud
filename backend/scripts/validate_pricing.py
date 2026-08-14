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


def our_prices(region_key: str) -> dict[str, Decimal]:
    region = provider_region(region_key, "aws")
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT sku, price_usd FROM price_points
               WHERE provider='aws' AND region=%s AND category='compute'
                 AND attributes->>'purchase' = 'ondemand'""",
            (region,),
        )
        return {r["sku"]: Decimal(r["price_usd"]) for r in cur.fetchall()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--region", default="india", choices=sorted(REGIONS))
    ap.add_argument("--tolerance", type=float, default=1.0, help="percent")
    args = ap.parse_args()

    print(f"\n{BOLD}WhichCloud · price validation{RESET}")
    print(f"{DIM}our catalog (ec2instances.info) vs AWS Price List CSV, "
          f"region '{args.region}'{RESET}\n")

    ours = our_prices(args.region)
    if not ours:
        print(f"{RED}Catalog is empty — run ingest_prices.py first.{RESET}")
        return 1
    print(f"{DIM}  catalog holds {len(ours):,} on-demand instance types{RESET}")
    print(f"{DIM}  streaming AWS price list (~195 MB, this takes a minute)…{RESET}")

    theirs = authoritative_prices(args.region)
    print(f"{DIM}  AWS published {len(theirs):,} on-demand Linux types{RESET}\n")

    shared = sorted(set(ours) & set(theirs))
    if not shared:
        print(f"{RED}No overlapping instance types — cannot validate.{RESET}")
        return 1

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
        if drift <= args.tolerance:
            within += 1
        else:
            mismatches.append((name, mine, theirs_price, drift))

    total = len(shared)
    pct_exact = exact / total * 100
    pct_within = within / total * 100

    print(f"{BOLD}Compared {total:,} instance types present in both sources{RESET}")
    print(f"  exact match          {exact:>6,}   {pct_exact:5.1f}%")
    print(f"  within {args.tolerance:g}%           {within:>6,}   {pct_within:5.1f}%")
    print(f"  outside tolerance    {len(mismatches):>6,}")

    if mismatches:
        print(f"\n{YELLOW}Largest discrepancies{RESET}")
        for name, mine, theirs_price, drift in sorted(
            mismatches, key=lambda m: -m[3]
        )[:10]:
            print(f"  {name:<20} ours ${mine:<12} aws ${theirs_price:<12} {drift:6.2f}%")

    only_ours = set(ours) - set(theirs)
    only_theirs = set(theirs) - set(ours)
    if only_ours or only_theirs:
        print(f"\n{DIM}coverage: {len(only_ours)} types only in our catalog, "
              f"{len(only_theirs)} only in AWS's list{RESET}")

    print()
    if pct_within >= 99:
        print(f"{GREEN}✓ Validated: {pct_within:.1f}% of prices match AWS's own "
              f"published rates within {args.tolerance:g}%.{RESET}\n")
        return 0
    if pct_within >= 90:
        print(f"{YELLOW}⚠ Mostly correct ({pct_within:.1f}%), but "
              f"{len(mismatches)} types drift. Investigate before quoting.{RESET}\n")
        return 0
    print(f"{RED}✗ Only {pct_within:.1f}% agree. The compute source is not "
          f"trustworthy as-is.{RESET}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
