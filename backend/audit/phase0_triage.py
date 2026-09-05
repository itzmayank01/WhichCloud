"""PHASE 0 -- the ten-minute triage.

One question: is our problem ARCHITECTURE or COST?

Prints the resolved ROLE LIST for six deliberately different requirements.
Not the diagram, not the price. Roles.

  * If the six columns are identical or near-identical, the resolver is
    emitting a TEMPLATE. Architecture is the problem, and cost accuracy is
    moot until it is fixed -- pricing the wrong architecture precisely is
    worse than pricing it roughly, because the precision is misleading.
  * If the columns genuinely differ, the resolver works and the problem is
    cost.

Run:  python -m audit.phase0_triage [--provider aws] [--tier "Most reliable"]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from audit.fixtures.requirements import FIXTURES, Fixture

# Roles that are governance rather than architecture. They appear on every
# design by policy, so including them in the matrix would make six different
# architectures look similar for a reason that has nothing to do with the
# resolver. Listed explicitly rather than filtered by heuristic, because the
# line between "baseline" and "leaked default" is exactly what is in dispute.
BASELINE_ROLES = frozenset(
    {
        "monitoring",
        "audit",
        "kms",
        "secrets",
        "auth",
        "threat",
        "posture",
        "tracing",
        "flowlogs",
        "backup",
        "dns",
        "tls",
        "client",
    }
)

CACHE = pathlib.Path(__file__).parent / ".intake-cache.json"


def _requirement_for(fixture: Fixture, refresh: bool = False):
    """The fixture's description, through the REAL intake path.

    Cached on disk. The point of this audit is to test what the resolver
    derives from prose, so it has to go through the model rather than
    hand-built Requirement objects -- but re-extracting on every run makes
    the harness slow, costs money, and introduces model drift between runs
    that would be indistinguishable from a code regression.
    """
    from whichcloud import intake

    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    if not refresh and fixture.id in cache:
        from whichcloud.intake import RequirementDraft

        return RequirementDraft(**cache[fixture.id]).to_requirement()

    result = intake.parse_description(fixture.description)
    cache[fixture.id] = json.loads(result.raw.model_dump_json())
    CACHE.write_text(json.dumps(cache, indent=2, sort_keys=True))
    return result.requirement


def roles_for(fixture: Fixture, provider: str, tier: str, refresh: bool = False):
    """The resolved role set: which KINDS of thing this architecture contains.

    Deduplicated node kinds, which is what "role" means here -- three compute
    instances are one role, and the audit is about shape, not size.
    """
    from whichcloud import engine

    requirement = _requirement_for(fixture, refresh)
    options = engine.recommend(requirement, provider, dsn=None)
    option = next((o for o in options if o.label == tier), options[0])
    kinds = {n.kind for n in option.estimate and option.spec and _nodes(option)}
    return kinds, requirement, option


def _nodes(option):
    from whichcloud import topology

    return topology.build(option.spec, option.estimate, option.applied).nodes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default="aws")
    parser.add_argument("--tier", default="Most reliable")
    parser.add_argument("--refresh", action="store_true", help="re-run intake")
    parser.add_argument("--show-baseline", action="store_true")
    args = parser.parse_args()

    resolved: dict[str, set[str]] = {}
    requirements = {}
    for fixture in FIXTURES:
        kinds, requirement, _ = roles_for(
            fixture, args.provider, args.tier, args.refresh
        )
        if not args.show_baseline:
            kinds = kinds - BASELINE_ROLES
        resolved[fixture.id] = kinds
        requirements[fixture.id] = requirement

    every_role = sorted({r for rs in resolved.values() for r in rs})
    ids = [f.id for f in FIXTURES]

    print()
    print(f"PHASE 0 — ROLE MATRIX   provider={args.provider}  tier={args.tier}")
    print("=" * 68)
    print(f"{'role':<20}" + "".join(f"{i:>5}" for i in ids))
    print("-" * 68)
    for role in every_role:
        marks = "".join(f"{'X' if role in resolved[i] else '-':>5}" for i in ids)
        print(f"{role:<20}{marks}")
    print("-" * 68)
    print(f"{'roles':<20}" + "".join(f"{len(resolved[i]):>5}" for i in ids))
    print()

    # How many DISTINCT shapes came out of six different descriptions. This
    # single number is the triage: six means the resolver reads the
    # requirement, one means it does not.
    distinct = {frozenset(v) for v in resolved.values()}
    print(f"distinct role sets: {len(distinct)} of {len(FIXTURES)}")

    # Pairwise overlap, so "near-identical" is a measured claim rather than an
    # impression. Two shapes that differ by one role out of fifteen are the
    # same template with a switch flipped.
    print()
    print("pairwise Jaccard similarity (1.00 = identical shape)")
    print(f"{'':<6}" + "".join(f"{i:>7}" for i in ids))
    for a in ids:
        row = ""
        for b in ids:
            sa, sb = resolved[a], resolved[b]
            j = len(sa & sb) / len(sa | sb) if (sa | sb) else 1.0
            row += f"{j:>7.2f}"
        print(f"{a:<6}{row}")

    # What each description RULED OUT, and whether it stayed out.
    print()
    print("EXPECTED FAILURES — roles the description rules out")
    print("-" * 68)
    violations = 0
    for fixture in FIXTURES:
        for role, why in fixture.forbidden.items():
            present = role in resolved[fixture.id]
            violations += present
            print(f"  {fixture.id} {role:<14} {'PRESENT ✗' if present else 'absent ✓'}   {why}")
    print()
    print("MISSING — roles the workload cannot be built without")
    print("-" * 68)
    missing = 0
    for fixture in FIXTURES:
        for role, why in fixture.required.items():
            absent = role not in resolved[fixture.id]
            missing += absent
            print(f"  {fixture.id} {role:<14} {'MISSING ✗' if absent else 'present ✓'}   {why}")

    print()
    print("=" * 68)
    print(f"unjustified roles present : {violations}")
    print(f"required roles missing    : {missing}")
    print(f"distinct shapes           : {len(distinct)}/{len(FIXTURES)}")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    sys.exit(main())
