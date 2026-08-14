#!/usr/bin/env python3
"""Fetch provider prices and load them into Postgres.

This is the job that turns "we can reach the pricing APIs" into "the engine can
query prices". Run it on a schedule; it is idempotent.

    python scripts/ingest_prices.py --region india
    python scripts/ingest_prices.py --region india --provider aws --force
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from datetime import datetime, timezone

from whichcloud.pricing import aws, azure, gcp, store
from whichcloud.pricing.models import REGIONS

BOLD, DIM, GREEN, YELLOW, RED, RESET = (
    "\033[1m",
    "\033[2m",
    "\033[32m",
    "\033[33m",
    "\033[31m",
    "\033[0m",
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--region", default="india", choices=sorted(REGIONS))
    ap.add_argument(
        "--provider", choices=["aws", "azure", "gcp", "all"], default="all"
    )
    ap.add_argument("--force", action="store_true", help="re-download cached catalogs")
    args = ap.parse_args()

    print(f"\n{BOLD}WhichCloud · price ingest{RESET}")
    print(f"{DIM}region '{args.region}' → {REGIONS[args.region]}{RESET}\n")

    if args.force:
        aws.download_instances(force=True)
        gcp.download_instances(force=True)
        aws.load_spot_prices(args.region, force=True)
        for service in aws.BULK_SERVICES.values():
            aws.download_bulk(service, args.region, force=True)

    providers = ["aws", "azure", "gcp"] if args.provider == "all" else [args.provider]
    total = 0

    for name in providers:
        started = time.monotonic()
        print(f"{BOLD}{name}{RESET}")
        module = {"aws": aws, "azure": azure, "gcp": gcp}[name]
        try:
            points = module.load_all(args.region)
        except Exception as exc:
            print(f"  {RED}✗ fetch failed: {type(exc).__name__}: {exc}{RESET}\n")
            continue

        if not points:
            print(f"  {YELLOW}no prices returned{RESET}\n")
            continue

        by_category = Counter(p.category for p in points)
        run_started = datetime.now(timezone.utc)
        written = store.upsert_prices(points)
        total += written

        # Drop anything this run did not refresh, so retired SKUs cannot be
        # quoted later.
        pruned = sum(
            store.prune_stale(name, region, run_started)
            for region in {p.region for p in points}
        )

        elapsed = time.monotonic() - started
        detail = "  ".join(f"{k} {v}" for k, v in sorted(by_category.items()))
        note = f", {pruned} stale removed" if pruned else ""
        print(
            f"  {GREEN}✓ {written:,} prices{RESET}  "
            f"{DIM}({detail}) in {elapsed:.1f}s{note}{RESET}\n"
        )

    if not total:
        print(f"{RED}Nothing ingested.{RESET}")
        return 1

    print(f"{BOLD}Catalog now holds{RESET}")
    print(f"{DIM}{'provider':<9}{'region':<16}{'category':<14}{'rows':>7}{RESET}")
    for row in store.stats():
        print(
            f"{row['provider']:<9}{row['region']:<16}"
            f"{row['category']:<14}{row['n']:>7,}"
        )

    print(f"\n{GREEN}✓ {total:,} prices written.{RESET}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
