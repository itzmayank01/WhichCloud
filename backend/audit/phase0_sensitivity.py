"""Does ADDING a requirement change the architecture?

The role matrix shows six different descriptions producing six different
shapes. That rules out a fixed template, but not a coarse one: a resolver
with four buckets would also pass it.

The sharper test is sensitivity. Take one description, add one clause that
implies a new role, and see whether the shape moves. If it does not, the
resolver is reading the workload CLASS and ignoring the rest of the
sentence -- which looks like derivation on a matrix and behaves like a
template in the product.

The pairs are chosen so the added clause implies a role the base does not
have, with nothing else changed.
"""

from __future__ import annotations

import sys

from audit.phase0_triage import BASELINE_ROLES

PAIRS = [
    (
        "reporting",
        "Online stock and billing for a retail chain in India, 40 stores, "
        "300 internal staff, 8,000 transactions/day, must not go down in "
        "business hours.",
        " Head office needs to see live numbers across all stores.",
        "reporting over the whole estate implies a read replica or a warehouse",
    ),
    (
        "search",
        "Product catalogue site, 5M page views a month, almost no writes, "
        "visitors across India.",
        " Shoppers search the catalogue by keyword and filter by brand.",
        "faceted keyword search implies a search cluster, not a LIKE query",
    ),
    (
        "media",
        "Internal HR tool for 80 employees. Leave requests and payroll "
        "records. Office hours only.",
        " Staff upload and watch training videos through it.",
        "video implies object storage plus a delivery path",
    ),
]


def _roles(description: str, provider: str, tier: str) -> set[str]:
    from whichcloud import engine, intake, topology

    requirement = intake.parse_description(description).requirement
    options = engine.recommend(requirement, provider, dsn=None)
    option = next((o for o in options if o.label == tier), options[0])
    nodes = topology.build(option.spec, option.estimate, option.applied).nodes
    return {n.kind for n in nodes} - BASELINE_ROLES


def main() -> int:
    provider, tier = "aws", "Most reliable"
    print()
    print("PHASE 0 — SENSITIVITY: does one added clause move the shape?")
    print("=" * 74)
    print(f"{'case':<11}{'added':<7}{'removed':<9}{'verdict':<10}what the clause implies")
    print("-" * 74)
    unmoved = 0
    for name, base, clause, implies in PAIRS:
        before = _roles(base, provider, tier)
        after = _roles(base + clause, provider, tier)
        added, removed = after - before, before - after
        moved = bool(added or removed)
        unmoved += not moved
        print(
            f"{name:<11}{len(added):<7}{len(removed):<9}"
            f"{'moved' if moved else 'UNMOVED':<10}{implies}"
        )
        if added:
            print(f"           + {', '.join(sorted(added))}")
        if removed:
            print(f"           - {', '.join(sorted(removed))}")
    print("-" * 74)
    print(f"clauses that changed nothing: {unmoved}/{len(PAIRS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
