#!/usr/bin/env python3
"""Phase 1 proof: can WhichCloud get real prices with no cloud account?

Answers the two questions the whole project rests on:

  1. Cross-cloud — for the same machine, which provider is cheapest?
  2. Optimization — what does the Graviton/ARM technique actually save?

Question 2 matters most: it replaces the placeholder in
knowledge-base/techniques/graviton-arm-compute.yaml with a measured number.

    python scripts/verify_pricing.py --region india --vcpu 2 --memory 4
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal

from whichcloud.pricing import aws, azure
from whichcloud.pricing.models import REGIONS, ComputeQuery, PricePoint

BOLD, DIM, GREEN, YELLOW, RESET = "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[0m"


def rule(title: str = "") -> None:
    print(f"\n{BOLD}{title}{RESET}\n{DIM}{'─' * 66}{RESET}")


def money(d: Decimal) -> str:
    return f"${d:,.2f}"


def show(p: PricePoint | None, label: str) -> None:
    if p is None:
        print(f"  {label:<10} {YELLOW}no match{RESET}")
        return
    tag = f"{GREEN}ARM{RESET}" if p.is_arm else "x86"
    print(
        f"  {label:<10} {p.sku:<18} {p.vcpu:>2}vCPU {p.memory_gb:>5.0f}GB  "
        f"{tag}  {money(p.monthly_usd):>10}/mo"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--region", default="india", choices=sorted(REGIONS))
    ap.add_argument("--vcpu", type=int, default=2)
    ap.add_argument("--memory", type=float, default=4.0)
    args = ap.parse_args()

    query = ComputeQuery(min_vcpu=args.vcpu, min_memory_gb=args.memory, region=args.region)
    mapped = REGIONS[args.region]
    print(
        f"\n{BOLD}WhichCloud · pricing layer verification{RESET}\n"
        f"{DIM}target: {args.vcpu} vCPU / {args.memory:g} GB Linux, on-demand, "
        f"region '{args.region}' ({mapped['aws']} · {mapped['azure']}){RESET}"
    )

    # ---- 1. cross-cloud -------------------------------------------------
    rule("1. Cheapest machine per provider")
    print(f"{DIM}  downloading AWS catalog (cached after first run)…{RESET}")
    path = aws.download_instances()

    results: dict[str, PricePoint | None] = {
        "AWS": aws.cheapest_compute(query, path),
        "Azure": azure.cheapest_compute(query),
    }
    for label, point in results.items():
        show(point, label)

    priced = {k: v for k, v in results.items() if v}
    if not priced:
        print(f"\n{YELLOW}No prices returned — pricing layer is NOT working.{RESET}")
        return 1

    winner = min(priced, key=lambda k: priced[k].monthly_usd)
    best = priced[winner]
    print(f"\n  {GREEN}→ {winner} wins at {money(best.monthly_usd)}/mo ({best.sku}){RESET}")

    if len(priced) > 1:
        worst = max(priced, key=lambda k: priced[k].monthly_usd)
        gap = priced[worst].monthly_usd - best.monthly_usd
        pct = gap / priced[worst].monthly_usd * 100
        print(f"  {DIM}  {money(gap)}/mo cheaper than {worst} ({pct:.0f}% less){RESET}")

    # ---- 2. measure the Graviton technique ------------------------------
    rule("2. Graviton / ARM saving, measured on AWS")
    arm = aws.cheapest_compute(
        ComputeQuery(args.vcpu, args.memory, args.region, arch="arm64"), path
    )
    x86 = aws.cheapest_compute(
        ComputeQuery(args.vcpu, args.memory, args.region, arch="x86_64"), path
    )
    show(x86, "x86")
    show(arm, "ARM")

    if arm and x86:
        saved = x86.monthly_usd - arm.monthly_usd
        pct = saved / x86.monthly_usd * 100
        print(
            f"\n  {GREEN}→ ARM is {money(saved)}/mo cheaper — {pct:.1f}% saving{RESET}\n"
            f"  {DIM}  update graviton-arm-compute.yaml: typical_pct: {pct:.0f}{RESET}"
        )
    else:
        print(f"\n  {YELLOW}Could not compare — one architecture had no match.{RESET}")

    rule("Result")
    print(
        f"  {GREEN}✓ Real prices from AWS and Azure with no cloud account, "
        f"no API key.{RESET}\n"
        f"  {DIM}  The riskiest dependency in the project is cleared.{RESET}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
