#!/usr/bin/env python3
"""Price a complete architecture, and compare it across clouds.

The scenario is the one from the UI mockup: an e-commerce site, 50k monthly
users, spiky weekend traffic, hosted in India. Three shapes are priced —
Cheapest, Balanced, Most Reliable — exactly as the product will present them.

    python scripts/estimate_architecture.py
    python scripts/estimate_architecture.py --region us-east
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal

from whichcloud.estimator import ArchitectureSpec, Estimate, compare
from whichcloud.pricing.models import REGIONS

BOLD, DIM, GREEN, YELLOW, RESET = "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[0m"


def money(d: Decimal) -> str:
    return f"${d:,.2f}"


def shapes(region: str) -> list[ArchitectureSpec]:
    return [
        ArchitectureSpec(
            name="Cheapest",
            region=region,
            compute_count=1,
            compute_vcpu=2,
            compute_memory_gb=4,
            arch="arm64",
            database_vcpu=2,
            database_memory_gb=4,
            storage_gb=200,
            egress_gb=500,
            load_balancer=False,
        ),
        ArchitectureSpec(
            name="Most reliable",
            region=region,
            compute_count=3,
            compute_vcpu=2,
            compute_memory_gb=8,
            arch="arm64",
            database_vcpu=2,
            database_memory_gb=8,
            storage_gb=200,
            egress_gb=500,
            load_balancer=True,
        ),
        ArchitectureSpec(
            name="Most reliable",
            region=region,
            compute_count=4,
            compute_vcpu=4,
            compute_memory_gb=16,
            database_vcpu=4,
            database_memory_gb=16,
            database_multi_az=True,
            storage_gb=200,
            egress_gb=500,
            load_balancer=True,
        ),
    ]


def render(est: Estimate) -> None:
    flag = "" if est.is_complete else f"  {YELLOW}incomplete{RESET}"
    print(f"\n  {BOLD}{est.provider.upper():<6}{RESET} {DIM}{est.region}{RESET}{flag}")
    for item in est.items:
        print(
            f"    {item.label:<22} {DIM}{item.sku:<22}{RESET}"
            f"{money(item.monthly_usd):>11}   {DIM}{item.detail}{RESET}"
        )
    if est.missing:
        for gap in est.missing:
            print(f"    {YELLOW}{'not priced':<22} {gap}{RESET}")
    print(f"    {BOLD}{'Total':<22}{'':<22}{money(est.total_monthly):>11}{RESET}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--region", default="india", choices=sorted(REGIONS))
    args = ap.parse_args()

    print(
        f"\n{BOLD}WhichCloud · architecture cost estimate{RESET}\n"
        f"{DIM}e-commerce, 50k monthly users, 200 GB assets, 500 GB egress, "
        f"region '{args.region}'{RESET}"
    )

    any_priced = False
    for spec in shapes(args.region):
        print(f"\n{BOLD}{'─' * 72}{RESET}")
        print(f"{BOLD}{spec.name}{RESET}  {DIM}"
              f"{spec.compute_count}× {spec.compute_vcpu}vCPU/{spec.compute_memory_gb:g}GB"
              f"{' arm64' if spec.arch else ''}"
              f"{', multi-AZ db' if spec.database_multi_az else ''}{RESET}")

        estimates = compare(spec)
        for est in estimates:
            render(est)
            if est.items:
                any_priced = True

        complete = [e for e in estimates if e.is_complete]
        if len(complete) > 1:
            best, second = complete[0], complete[1]
            gap = second.total_monthly - best.total_monthly
            pct = gap / second.total_monthly * 100 if second.total_monthly else 0
            print(
                f"\n  {GREEN}→ {best.provider.upper()} is cheaper by {money(gap)}/mo "
                f"({pct:.0f}%){RESET}"
            )

    print(f"\n{DIM}{'─' * 72}{RESET}")
    print(f"{DIM}List prices only. No committed-use or reserved discounts. "
          f"Estimate, not a quote.{RESET}\n")
    return 0 if any_priced else 1


if __name__ == "__main__":
    sys.exit(main())
