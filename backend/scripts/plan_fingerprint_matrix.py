"""The architecture fingerprint matrix for the PLAN path.

scripts/fingerprint_matrix.py covers the other engine -- the one that
takes a Requirement and is reached by /recommend, /compare and /describe.
This one covers `plan.build()`, reached by /plan, which is where the
archetype lives and therefore where the one-shape bug lives.

A fingerprint is the sorted set of service kinds in a tier, with every
size, count and AZ multiplier stripped away. Two architectures with the
same fingerprint are the same architecture however different their bills.

    .venv/bin/python scripts/plan_fingerprint_matrix.py
    .venv/bin/python scripts/plan_fingerprint_matrix.py --json out.json

Three properties, per the brief:

  DIVERGENCE   two fixtures with a different profile must not share a
               tier-1 fingerprint. Each collision IS the template bug.
  TIER SPREAD  consecutive tiers differ by >= 3 services, not by size.
  STABILITY    the same Constraints produce the same fingerprint every
               run (asserted at 100 iterations in tests/test_fingerprint).

Withheld plans are reported as WITHHELD rather than as an empty
fingerprint. They are a real answer -- "we do not build this shape" --
and folding them into the matrix as empty sets would make six honest
refusals look like six identical architectures.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from whichcloud import plan as plan_module
from whichcloud.fingerprint import (
    MIN_TIER_SPREAD, divergence_collisions, plan_fingerprints, plan_profile,
    thin_spreads,
)

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
PROBES = ROOT / "tests" / "probes"

RULE = "=" * 78


def _prompts() -> dict[str, str]:
    """Every prompt-bearing fixture and probe, by id.

    Probes are included deliberately: they are the six shapes the engine
    could not build, so leaving them out would produce a matrix that
    looks complete while covering only the one shape that worked.
    """
    out: dict[str, str] = {}
    for path in sorted(FIXTURES.glob("*.yaml")) + sorted(PROBES.glob("*.yaml")):
        data = yaml.safe_load(path.read_text()) or {}
        if isinstance(data, dict) and data.get("prompt"):
            out[data.get("id", path.stem)] = data["prompt"]
    return out


def build_all() -> dict:
    plans = {}
    for name, prompt in _prompts().items():
        try:
            plans[name] = plan_module.build(prompt)
        except Exception as exc:  # noqa: BLE001 -- one bad fixture must not hide the rest
            print(f"  !! {name}: {type(exc).__name__}: {exc}", file=sys.stderr)
    return plans


def report(plans: dict) -> dict:
    print(RULE)
    print("PLAN-PATH ARCHITECTURE FINGERPRINT MATRIX")
    print(RULE)

    priced, withheld = {}, {}
    for name, plan in sorted(plans.items()):
        if plan.tiers:
            priced[name] = plan
        else:
            withheld[name] = plan

    for name, plan in priced.items():
        prints = plan_fingerprints(plan)
        spreads = [
            len((a - b) | (b - a)) for a, b in zip(prints, prints[1:])
        ]
        print(f"\n{name}  [{plan.archetype}]  tier-1: {len(prints[0])} services")
        for tier, fp in zip(plan.tiers, prints):
            print(f"    {tier.name}: {' '.join(sorted(fp))}")
        flag = "" if all(s >= MIN_TIER_SPREAD for s in spreads) else "   <-- THIN"
        print(f"    tier spread (>={MIN_TIER_SPREAD} each): {spreads}{flag}")

    if withheld:
        print(f"\n{RULE}")
        print("WITHHELD — no architecture to fingerprint")
        print(RULE)
        for name, plan in withheld.items():
            print(f"  {name:<22} {plan.archetype:<14} {plan.archetype_state}")

    collisions = divergence_collisions(plans)
    print(f"\n{RULE}")
    print("DIVERGENCE — different profile, same tier-1 fingerprint")
    print("(each one is the template bug)")
    print(RULE)
    if collisions:
        for a, b in collisions:
            print(f"  COLLISION  {a}  ==  {b}")
    else:
        print("  none — every distinct workload has a distinct tier-1 architecture")

    thin = thin_spreads(plans)
    print(f"\n{RULE}")
    print(f"TIER SPREAD — consecutive tiers differing by < {MIN_TIER_SPREAD} services")
    print(RULE)
    if thin:
        for name, spreads in sorted(thin.items()):
            print(f"  THIN  {name}: {spreads}")
    else:
        print("  none — every tier differs from its neighbour by service, not size")

    print(f"\n{RULE}")
    print(f"SUMMARY: {len(priced)} priced, {len(withheld)} withheld, "
          f"{len(collisions)} divergence collision(s), {len(thin)} thin-spread")
    print(RULE)

    return {
        "priced": {
            name: {
                "archetype": plan.archetype,
                "profile": list(plan_profile(plan)),
                "tiers": {
                    tier.name: sorted(fp)
                    for tier, fp in zip(plan.tiers, plan_fingerprints(plan))
                },
                "spread": [
                    len((a - b) | (b - a))
                    for a, b in zip(plan_fingerprints(plan),
                                    plan_fingerprints(plan)[1:])
                ],
            }
            for name, plan in priced.items()
        },
        "withheld": {
            name: {"archetype": p.archetype, "state": p.archetype_state}
            for name, p in withheld.items()
        },
        "collisions": [list(c) for c in collisions],
        "thin_spreads": thin,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, help="also write the matrix here")
    args = parser.parse_args()

    summary = report(build_all())
    if args.json:
        args.json.write_text(json.dumps(summary, indent=2))
        print(f"\nwrote {args.json}")
    # Deliberately always 0: this is a measurement, and at baseline it is
    # SUPPOSED to fail. The harness asserts; this reports.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
