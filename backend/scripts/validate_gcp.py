#!/usr/bin/env python3
"""Show exactly which GCP SKU each selector picked, so it can be checked.

The selectors cannot be validated by unit tests: a filter that compiles and
returns *something* still tells you nothing about whether that something is
the right rate. This prints every choice with its SKU id, description and
unit, so each can be compared against Google's published pricing page before
any of it is trusted.

That check is not optional. The Azure equivalent looked perfectly reasonable
and silently selected a Windows-priced meter, making 36 machine types read
2.65x too expensive -- caught only by comparing against a second source.

    python3 scripts/validate_gcp.py --region india
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whichcloud.pricing import gcp
from whichcloud.pricing.models import HOURS_PER_MONTH, provider_region

# What each category should look like, for a human reading the output.
EXPECTATIONS = {
    "storage": "Standard (not Nearline/Coldline/Archive), per GB-month",
    "network": "Internet egress, per GB — not inter-region, not CDN",
    "database": "Cloud SQL PostgreSQL, composed from vCPU-hour + RAM GB-hour",
    "cache":    "Memorystore Redis Basic, per GB of capacity",
    "loadbalancer": "Forwarding rule, hourly",
    "monitoring": "Metric ingestion, converted to metric-month",
}

LOADERS = [
    ("storage", gcp.fetch_storage_prices),
    ("network", gcp.fetch_egress_prices),
    ("database", gcp.fetch_database_prices),
    ("cache", gcp.fetch_cache_prices),
    ("loadbalancer", gcp.fetch_loadbalancer_prices),
    ("monitoring", gcp.fetch_monitoring_prices),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="india")
    args = parser.parse_args()

    if not gcp.catalog_api_available():
        print("GOOGLE_CLOUD_API_KEY is not set — nothing to validate.")
        print("GCP compute needs no key; everything else does.")
        return 1

    region = provider_region(args.region, "gcp")
    print(f"GCP catalog picks for {args.region} ({region})")
    print("Check each against https://cloud.google.com/pricing before trusting it.\n")

    failures = 0
    for category, loader in LOADERS:
        print(f"── {category}  · expected: {EXPECTATIONS[category]}")
        try:
            points = loader(args.region)
        except Exception as exc:  # noqa: BLE001 - a failure here is a result
            print(f"   FAILED: {type(exc).__name__}: {exc}\n")
            failures += 1
            continue

        if not points:
            print("   nothing selected — component stays unpriced\n")
            failures += 1
            continue

        for point in points[:6]:
            monthly = ""
            if point.unit == "hour":
                monthly = f"  (= ${point.price_usd * HOURS_PER_MONTH:,.2f}/mo)"
            print(f"   {point.sku:<34} ${point.price_usd:>12.8f} / {point.unit}{monthly}")
            extra = {k: v for k, v in point.attributes.items() if k != "sku_id"}
            if extra:
                print(f"      {extra}")
        if len(points) > 6:
            print(f"   … and {len(points) - 6} more")
        print()

    print(f"{len(LOADERS) - failures}/{len(LOADERS)} categories priced.")
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
