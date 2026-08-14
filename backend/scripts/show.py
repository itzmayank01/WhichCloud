#!/usr/bin/env python3
"""Inspect what is actually in the price catalog.

Answers the question "where did this number come from?" without writing SQL.

    python scripts/show.py stats
    python scripts/show.py provenance
    python scripts/show.py cheapest --vcpu 2 --memory 8
    python scripts/show.py cheapest --vcpu 4 --memory 16 --arch arm64
    python scripts/show.py sku t4g.large
    python scripts/show.py sku Standard_B2ps_v2
"""

from __future__ import annotations

import argparse
import sys

from whichcloud.pricing.store import connect

BOLD, DIM, GREEN, YELLOW, RESET = "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[0m"

# Where every category's numbers come from, and whether we have checked them.
PROVENANCE = [
    ("aws", "compute", "ec2instances.info (Vantage)", "validated 807/807 vs AWS Price List CSV"),
    ("aws", "compute:spot", "AWS public spot feed", "real, but the feed carries no timestamp"),
    ("aws", "database", "AWS Price List Bulk API", "AWS's own authoritative feed"),
    ("aws", "storage", "AWS Price List Bulk API", "AWS's own authoritative feed"),
    ("aws", "network", "AWS Price List Bulk API", "AWS's own authoritative feed"),
    ("aws", "loadbalancer", "AWS Price List Bulk API", "AWS's own authoritative feed"),
    ("azure", "compute", "Azure Retail Prices API", "validated 923/928 vs Vantage catalog"),
    ("azure", "database", "Azure Retail Prices API", "Microsoft's own feed; specs from catalog"),
    ("azure", "database:HA", "DERIVED — 2x primary", "Azure publishes no HA meter"),
    ("azure", "storage", "Azure Retail Prices API", "Microsoft's own feed"),
    ("azure", "network", "Azure Retail Prices API", "Microsoft's own feed"),
    ("azure", "loadbalancer", "Azure Retail Prices API", "priced globally, not per region"),
    ("gcp", "compute", "gcpinstances (Vantage)", "NOT validated — no second free source"),
    ("gcp", "compute:arch", "INFERRED from family naming", "t2a/c4a = Arm, per Google's docs"),
]


def cmd_stats(args) -> int:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT provider, region, category,
                      count(*) AS n,
                      min(price_usd) AS lo,
                      max(price_usd) AS hi,
                      max(fetched_at)::timestamp(0) AS fetched
               FROM price_points
               GROUP BY provider, region, category
               ORDER BY provider, category"""
        )
        rows = cur.fetchall()

    if not rows:
        print(f"{YELLOW}Catalog is empty. Run: python scripts/ingest_prices.py{RESET}")
        return 1

    print(f"\n{BOLD}Price catalog{RESET}")
    print(f"{DIM}{'provider':<9}{'region':<15}{'category':<14}{'rows':>7}"
          f"{'cheapest':>12}{'dearest':>12}   updated{RESET}")
    for r in rows:
        print(
            f"{r['provider']:<9}{r['region']:<15}{r['category']:<14}{r['n']:>7,}"
            f"{float(r['lo']):>12.4f}{float(r['hi']):>12.2f}   {r['fetched']}"
        )
    print(f"\n{DIM}total {sum(r['n'] for r in rows):,} prices{RESET}\n")
    return 0


def cmd_provenance(args) -> int:
    print(f"\n{BOLD}Where every number comes from{RESET}\n")
    print(f"{DIM}{'provider':<10}{'category':<18}{'source':<32}status{RESET}")
    for provider, category, source, status in PROVENANCE:
        derived = source.startswith(("DERIVED", "INFERRED"))
        unvalidated = status.startswith("NOT")
        colour = YELLOW if (derived or unvalidated) else GREEN
        print(f"{provider:<10}{category:<18}{colour}{source:<32}{status}{RESET}")
    print(
        f"\n{GREEN}green{RESET}{DIM} = fetched from a provider feed.{RESET}\n"
        f"{YELLOW}yellow{RESET}{DIM} = derived, inferred, or unverified. "
        f"Nothing here is model-generated.{RESET}\n"
    )
    return 0


def cmd_cheapest(args) -> int:
    sql = """
        SELECT provider, region, sku, vcpu, memory_gb, arch, price_usd,
               round(price_usd * 730, 2) AS monthly,
               attributes->>'purchase' AS purchase
        FROM price_points
        WHERE category = 'compute'
          AND vcpu >= %(vcpu)s AND memory_gb >= %(memory)s
          AND attributes->>'purchase' = %(purchase)s
    """
    params = {
        "vcpu": args.vcpu,
        "memory": args.memory,
        "purchase": "spot" if args.spot else "ondemand",
    }
    if args.arch:
        sql += " AND arch = %(arch)s"
        params["arch"] = args.arch
    if args.provider:
        sql += " AND provider = %(provider)s"
        params["provider"] = args.provider
    sql += " ORDER BY price_usd LIMIT %(limit)s"
    params["limit"] = args.limit

    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    kind = "spot" if args.spot else "on-demand"
    print(
        f"\n{BOLD}Cheapest {kind} machines with ≥{args.vcpu} vCPU / "
        f"≥{args.memory:g} GB{RESET}"
        + (f"{DIM} · {args.arch}{RESET}" if args.arch else "")
    )
    if not rows:
        print(f"{YELLOW}  nothing matches — try smaller specs or drop --arch{RESET}\n")
        return 1

    print(f"{DIM}{'provider':<9}{'sku':<24}{'vCPU':>5}{'GB':>7}{'arch':>8}"
          f"{'$/hour':>11}{'$/month':>11}{RESET}")
    for i, r in enumerate(rows):
        mark = GREEN if i == 0 else ""
        print(
            f"{mark}{r['provider']:<9}{r['sku']:<24}{r['vcpu']:>5}"
            f"{r['memory_gb']:>7.0f}{r['arch'] or '?':>8}"
            f"{float(r['price_usd']):>11.4f}{float(r['monthly']):>11.2f}{RESET}"
        )
    print()
    return 0


def cmd_sku(args) -> int:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT * FROM price_points
               WHERE sku ILIKE %s ORDER BY provider, price_usd LIMIT 20""",
            (f"%{args.name}%",),
        )
        rows = cur.fetchall()

    if not rows:
        print(f"\n{YELLOW}No SKU matching '{args.name}'.{RESET}\n")
        return 1

    print(f"\n{BOLD}Matches for '{args.name}'{RESET}\n")
    for r in rows:
        monthly = float(r["price_usd"]) * (730 if r["unit"] == "hour" else 1)
        print(f"  {BOLD}{r['sku']}{RESET}  {DIM}({r['provider']} · {r['region']}){RESET}")
        print(f"    {r['name']}")
        print(f"    ${float(r['price_usd']):.6f} per {r['unit']}"
              f"   →  ${monthly:,.2f}/month" if r["unit"] == "hour"
              else f"    ${float(r['price_usd']):.6f} per {r['unit']}")
        if r["vcpu"]:
            print(f"    {r['vcpu']} vCPU · {r['memory_gb']:g} GB · {r['arch']}")
        attrs = r["attributes"] or {}
        if attrs.get("derived"):
            print(f"    {YELLOW}derived: {attrs['derived']}{RESET}")
        if attrs:
            shown = {k: v for k, v in attrs.items() if k != "derived"}
            if shown:
                print(f"    {DIM}{shown}{RESET}")
        print(f"    {DIM}fetched {r['fetched_at']:%Y-%m-%d %H:%M}{RESET}\n")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("stats", help="what is in the catalog").set_defaults(fn=cmd_stats)
    sub.add_parser("provenance", help="where each number came from").set_defaults(
        fn=cmd_provenance
    )

    c = sub.add_parser("cheapest", help="cheapest machine meeting a spec")
    c.add_argument("--vcpu", type=int, default=2)
    c.add_argument("--memory", type=float, default=8)
    c.add_argument("--arch", choices=["arm64", "x86_64"])
    c.add_argument("--provider", choices=["aws", "azure", "gcp"])
    c.add_argument("--spot", action="store_true")
    c.add_argument("--limit", type=int, default=8)
    c.set_defaults(fn=cmd_cheapest)

    s = sub.add_parser("sku", help="look up a specific SKU")
    s.add_argument("name")
    s.set_defaults(fn=cmd_sku)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
