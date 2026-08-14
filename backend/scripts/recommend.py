#!/usr/bin/env python3
"""Describe a workload, get three priced architectures.

This is the engine end to end: requirements in, sized shapes out, techniques
applied, everything priced against the real catalog.

    python scripts/recommend.py --describe "an e-commerce site for 50k users, spiky weekend traffic, $400/mo"
    python scripts/recommend.py --goal "e-commerce site" --scale medium --spiky
    python scripts/recommend.py --workload batch --interruptible --scale high
    python scripts/recommend.py --goal "internal dashboard" --scale low --all-clouds
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal

from whichcloud.engine import SIZING_BASIS, Option, recommend, recommend_across_clouds, why_not
from whichcloud.pricing.models import REGIONS
from whichcloud.requirements import VALID_SCALES, VALID_WORKLOADS, Requirement

BOLD, DIM, GREEN, YELLOW, CYAN, RESET = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[36m", "\033[0m",
)


def money(d: Decimal) -> str:
    return f"${d:,.2f}"


def render(option: Option, provider: str) -> None:
    budget_note = ""
    if option.within_budget is False:
        budget_note = f"  {YELLOW}over budget{RESET}"
    elif option.within_budget is True:
        budget_note = f"  {GREEN}within budget{RESET}"

    flag = "" if option.estimate.is_complete else f"  {YELLOW}incomplete{RESET}"
    print(f"\n  {BOLD}{option.label}{RESET} {DIM}· {provider}{RESET}{budget_note}{flag}")
    print(f"  {DIM}{option.rationale}{RESET}")

    spec = option.spec
    shape = (
        f"{spec.compute_count}× {spec.compute_vcpu} vCPU / "
        f"{spec.compute_memory_gb:g} GB"
    )
    if spec.arch:
        shape += f" {spec.arch}"
    if spec.use_spot:
        shape += " spot"
    if spec.database_multi_az:
        shape += " · multi-AZ db"
    print(f"  {DIM}{shape}{RESET}")

    for item in option.estimate.items:
        print(
            f"    {item.label:<24}{DIM}{item.sku:<24}{RESET}"
            f"{money(item.monthly_usd):>11}"
        )
    for gap in option.estimate.missing:
        print(f"    {YELLOW}{'not priced':<24}{gap}{RESET}")

    print(f"    {BOLD}{'Total':<24}{'':<24}{money(option.monthly):>11}{RESET}")

    if option.applied:
        saved = option.measured_saving
        print(
            f"    {GREEN}{'measured saving':<24}{'':<24}"
            f"{money(saved):>11}  ({option.saving_pct:.0f}% vs untuned){RESET}"
        )
        for applied in option.applied:
            tool = applied.technique.primary_tool
            print(f"      {GREEN}✓{RESET} {applied.technique.name}"
                  f"   {GREEN}−{money(applied.saved)}/mo{RESET}")
            print(f"        {DIM}vs {applied.counterfactual_sku} · {tool}{RESET}")
            for reason in applied.match.reasons:
                print(f"        {DIM}{reason}{RESET}")

    for match in option.advisory:
        print(f"      {CYAN}~{RESET} {match.technique.name} "
              f"{DIM}(advice only — not priced){RESET}")
        print(f"        {DIM}{match.technique.summary.splitlines()[0]}{RESET}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--describe",
        help="describe the app in plain English; Claude fills the rest "
             "(needs ANTHROPIC_API_KEY)",
    )
    ap.add_argument("--goal", default="a web application")
    ap.add_argument("--workload", default="web", choices=list(VALID_WORKLOADS))
    ap.add_argument("--scale", default="medium", choices=list(VALID_SCALES))
    ap.add_argument("--spiky", action="store_true", help="traffic spikes hard")
    ap.add_argument("--region", default="india", choices=sorted(REGIONS))
    ap.add_argument("--budget", type=float, default=None)
    ap.add_argument("--storage-gb", type=float, default=200)
    ap.add_argument("--egress-gb", type=float, default=500)
    ap.add_argument("--interruptible", action="store_true",
                    help="work can be restarted — unlocks spot")
    ap.add_argument("--x86-only", action="store_true",
                    help="has x86-only dependencies — blocks ARM")
    ap.add_argument("--provider", choices=["aws", "azure", "gcp"], default="aws")
    ap.add_argument("--all-clouds", action="store_true")
    args = ap.parse_args()

    if args.describe:
        from whichcloud.intake import IntakeError, parse_description

        print(f"\n{DIM}Reading your description…{RESET}")
        try:
            intake = parse_description(args.describe)
        except IntakeError as exc:
            print(f"{YELLOW}{exc}{RESET}\n")
            return 1

        requirement = intake.requirement
        if intake.assumed:
            print(f"{DIM}Assumed (not stated): {', '.join(intake.assumed)}{RESET}")
        if intake.clarifying_question:
            print(f"{CYAN}One question that would sharpen this:{RESET} "
                  f"{intake.clarifying_question}")
    else:
        requirement = Requirement(
            goal=args.goal,
            workload_type=args.workload,
            traffic_pattern="spiky" if args.spiky else "steady",
            traffic_scale=args.scale,
            region=args.region,
            budget_monthly_usd=args.budget,
            storage_gb=args.storage_gb,
            egress_gb=args.egress_gb,
            interruptible=args.interruptible,
            arm_compatible=not args.x86_only,
        )

    print(f"\n{BOLD}WhichCloud · recommendation{RESET}")
    print(f"{DIM}{requirement.goal} — {requirement.workload_type}, "
          f"{requirement.traffic_pattern} traffic, {requirement.traffic_scale} scale, "
          f"{requirement.region}"
          + (f", budget ${requirement.budget_monthly_usd:g}/mo" if requirement.budget_monthly_usd else "")
          + f"{RESET}")

    if args.all_clouds:
        results = recommend_across_clouds(requirement)
        for provider, options in results.items():
            print(f"\n{BOLD}{'─' * 68}{RESET}")
            for option in options:
                render(option, provider)

        print(f"\n{BOLD}{'─' * 68}{RESET}")
        print(f"{BOLD}Balanced option across clouds{RESET}")
        ranked = sorted(
            (
                (p, o)
                for p, opts in results.items()
                for o in opts
                if o.label == "Balanced"
            ),
            key=lambda pair: (not pair[1].estimate.is_complete, pair[1].monthly),
        )
        for provider, option in ranked:
            note = "" if option.estimate.is_complete else f"  {YELLOW}(incomplete){RESET}"
            print(f"  {provider:<8}{money(option.monthly):>11}{note}")
        if ranked and ranked[0][1].estimate.is_complete:
            print(f"\n  {GREEN}→ {ranked[0][0]} is cheapest at "
                  f"{money(ranked[0][1].monthly)}/mo{RESET}")
    else:
        for option in recommend(requirement, args.provider):
            render(option, args.provider)

        skipped = why_not(requirement, args.provider)
        if skipped:
            print(f"\n  {DIM}Not applied:{RESET}")
            for technique, reason in skipped:
                print(f"    {DIM}· {technique.name} — {reason}{RESET}")

    print(f"\n{DIM}{'─' * 68}{RESET}")
    print(f"{DIM}{SIZING_BASIS}{RESET}")
    print(f"{DIM}Prices are list rates from provider catalogs. "
          f"Estimate, not a quote.{RESET}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
