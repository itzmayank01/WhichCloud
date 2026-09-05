"""PHASE 1 -- architecture correctness against published vendor references.

Scored per fixture per provider on four counts:

  MISSING ROLE     in the reference, absent from ours.              weight 3
  EXTRA ROLE       in ours, absent from the reference, and with no
                   recorded reason.                                 weight 2
  WRONG SERVICE    right role, wrong service for it.                weight 2
  WRONG HIERARCHY  node in the wrong container, or a provider-model
                   violation.                                       weight 3

  score = 100 - sum(weight x count), floored at 0

An extra role is not automatically wrong -- the reference may not have
considered this workload. But it must carry a reason. An extra role with no
reason is a default that leaked in, and it scores. That rule is why C7 in
Phase 3 matters even when C1 passes: with no reason recorded ANYWHERE, every
extra role we emit is by definition unjustified.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from audit.fixtures.requirements import FIXTURES
from audit.phase0_triage import _requirement_for
from audit.roles import BASELINE, KIND_TO_ROLE, roles_of, satisfied, unknown

FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures" / "architecture"
PROVIDERS = ("aws", "gcp", "azure")

WEIGHTS = {"missing": 3, "extra": 2, "wrong_service": 2, "hierarchy": 3}

#: Provider-model violations. Each is a shape that cannot exist on that cloud,
#: so finding one means the resolver copied another cloud's mental model.
#:
#: Read from what is PRICED AND DRAWN, never from the spec. The first version
#: of this read `spec.nat_gateway_count` and reported five violations each on
#: GCP and Azure that do not exist: the spec field keeps an AWS-shaped
#: per-zone count, and the estimator converts it to the provider's own model
#: on the way out. Auditing the intermediate rather than the output invented
#: ten defects. (The spec field IS still AWS-shaped, which is a latent trap
#: for the next reader of it -- recorded as a note, not scored as a violation,
#: because nothing a user sees is wrong.)
def hierarchy_violations(provider: str, estimate, kinds: set[str]) -> list[str]:
    out = []
    nat = next(
        (int(i.label.split("×")[1]) for i in estimate.items
         if i.label.startswith("NAT gateway ×")),
        0,
    )
    if provider == "gcp" and nat > 1:
        out.append(f"{nat} Cloud NATs priced: it is regional, one per region per VPC")
    if provider == "azure" and nat > 1:
        out.append(f"{nat} NAT gateways priced: an Azure subnet accepts at most one")
    if provider == "azure" and "waf" in kinds and "loadbalancer" not in kinds:
        out.append("WAF without a gateway: on Azure the WAF is a mode of the gateway")
    return out


def latent_notes(provider: str, spec) -> list[str]:
    """True of the SPEC but not of the output. Reported, never scored."""
    if provider in ("gcp", "azure") and spec.nat_gateway_count > 1:
        return [
            f"spec.nat_gateway_count={spec.nat_gateway_count} is an AWS per-zone "
            f"count; correct on the bill and the diagram, wrong for any new "
            f"reader of the field"
        ]
    return []


def _fixture_file(fixture) -> dict:
    name = f"{fixture.id}-{fixture.name}.json"
    return json.loads((FIXTURE_DIR / name).read_text())


def score_one(fixture, provider: str, requirement, tier: str) -> dict:
    from whichcloud import engine, topology

    ref = _fixture_file(fixture)
    expected = set(ref["expected"][provider]["roles"])
    forbidden = set(ref.get("forbidden", {}))

    options = engine.recommend(requirement, provider, dsn=None)
    option = next((o for o in options if o.label == tier), options[0])
    nodes = topology.build(option.spec, option.estimate, option.applied).nodes
    kinds = {n.kind for n in nodes}
    ours = roles_of(kinds)

    # A role delivered by an accepted equivalent is not missing. See
    # roles.SATISFIES for what counts and why the list is short.
    missing = sorted(r for r in expected if not satisfied(r, ours))

    # An extra role scores only when nothing records WHY it is there. Nothing
    # records why anything is there today, so every extra scores -- which is
    # the finding, not a harshness of the scale.
    justified = {
        KIND_TO_ROLE.get(n.kind, n.kind)
        for n in nodes
        if getattr(n, "because", None)
    }
    # An equivalent that FILLS an expected role is not an extra either --
    # it is the role, under the name this cloud sells it under.
    substitutes = {
        alt for role in expected for alt in
        __import__("audit.roles", fromlist=["SATISFIES"]).SATISFIES.get(role, ())
    }
    extra = sorted((ours - expected - substitutes) - justified)

    # A forbidden role is an extra that the DESCRIPTION ruled out, not merely
    # one the reference omitted. Counted at the missing weight, because
    # shipping a component the requirement excluded misleads as badly as
    # omitting one it demanded.
    violating = sorted(ours & forbidden)

    hierarchy = hierarchy_violations(provider, option.estimate, kinds)
    latent = latent_notes(provider, option.spec)

    penalty = (
        WEIGHTS["missing"] * len(missing)
        + WEIGHTS["extra"] * len(extra)
        + WEIGHTS["missing"] * len(violating)
        + WEIGHTS["hierarchy"] * len(hierarchy)
    )
    return {
        "score": max(0, 100 - penalty),
        "missing": missing,
        "extra": extra,
        "forbidden_present": violating,
        "hierarchy": hierarchy,
        "latent": latent,
        "unknown_kinds": sorted(unknown(kinds)),
        "ours": sorted(ours),
        "expected": sorted(expected),
        "source": ref["expected"][provider]["source"],
        "verified": ref["expected"][provider]["verified"],
    }


def run(tier: str = "Most reliable") -> dict:
    reqs = {f.id: _requirement_for(f) for f in FIXTURES}
    return {
        f.id: {p: score_one(f, p, reqs[f.id], tier) for p in PROVIDERS}
        for f in FIXTURES
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tier", default="Most reliable")
    ap.add_argument("--detail", action="store_true")
    args = ap.parse_args()

    scores = run(args.tier)

    print()
    print(f"PHASE 1 — ARCHITECTURE CORRECTNESS   tier={args.tier}")
    print("=" * 78)
    print(f"{'fixture':<20}{'AWS':>7}{'GCP':>7}{'Azure':>7}   notes")
    print("-" * 78)
    for fixture in FIXTURES:
        row = scores[fixture.id]
        note = []
        for p in PROVIDERS:
            r = row[p]
            bits = []
            if r["missing"]:
                bits.append(f"-{','.join(r['missing'])}")
            if r["forbidden_present"]:
                bits.append(f"!{','.join(r['forbidden_present'])}")
            if bits:
                note.append(f"{p}: {' '.join(bits)}")
        cells = "".join(f"{row[p]['score']:>7}" for p in PROVIDERS)
        label = f"{fixture.id} {fixture.name}"
        print(f"{label:<20}{cells}   {'; '.join(note)[:34]}")

    print("-" * 78)
    means = {
        p: sum(scores[f.id][p]["score"] for f in FIXTURES) / len(FIXTURES)
        for p in PROVIDERS
    }
    print(f"{'mean':<20}" + "".join(f"{means[p]:>7.0f}" for p in PROVIDERS))

    print()
    print("DEFECT COUNTS")
    print("-" * 78)
    print(f"{'':<28}{'AWS':>7}{'GCP':>7}{'Azure':>7}")
    for key, label in (
        ("missing", "missing roles"),
        ("extra", "extra roles, unjustified"),
        ("forbidden_present", "roles the brief ruled out"),
        ("hierarchy", "hierarchy violations"),
        ("latent", "latent spec traps (not scored)"),
    ):
        totals = {p: sum(len(scores[f.id][p][key]) for f in FIXTURES) for p in PROVIDERS}
        print(f"  {label:<26}" + "".join(f"{totals[p]:>7}" for p in PROVIDERS))

    if args.detail:
        print()
        for fixture in FIXTURES:
            for p in PROVIDERS:
                r = scores[fixture.id][p]
                print(f"\n{fixture.id}/{p}  score {r['score']}   [{r['verified']}] {r['source']}")
                print(f"    expected : {', '.join(r['expected'])}")
                print(f"    ours     : {', '.join(r['ours'])}")
                for k in ("missing", "extra", "forbidden_present", "hierarchy", "latent", "unknown_kinds"):
                    if r[k]:
                        print(f"    {k:<9}: {', '.join(r[k])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
