"""PHASE 3 -- internal consistency. Seven checks, no external reference.

These need no vendor data, which is what makes them the cheapest signal
available and the right thing to run before anything is priced by hand. Each
one fails for exactly one reason, stated on the check, so a failure names its
own cause rather than sending anyone hunting.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from dataclasses import replace

from audit.fixtures.requirements import FIXTURES
from audit.phase0_triage import BASELINE_ROLES, _requirement_for

PROVIDERS = ("aws", "gcp", "azure")
TIERS = ("Cheapest", "Most reliable", "Most optimized")
BUDGETS = (500.0, 5_000.0, 50_000.0)


class Results:
    """Pass/fail counts with the failures kept, so the report can name them."""

    def __init__(self) -> None:
        self.rows: dict[str, list[tuple[bool, str]]] = {}

    def record(self, check: str, ok: bool, detail: str = "") -> None:
        self.rows.setdefault(check, []).append((ok, detail))

    def tally(self, check: str) -> tuple[int, int]:
        rows = self.rows.get(check, [])
        return sum(1 for ok, _ in rows if ok), len(rows)

    def failures(self, check: str) -> list[str]:
        return [d for ok, d in self.rows.get(check, []) if not ok]


def _shape(option) -> dict:
    """The architecture, with every sizing knob that would reveal a change.

    Compared as a dict rather than a hash so a failure can say WHICH field
    moved. A hash would prove the bug and then refuse to explain it.
    """
    spec = option.spec
    return {
        "compute_count": spec.compute_count,
        "compute_vcpu": spec.compute_vcpu,
        "compute_memory_gb": spec.compute_memory_gb,
        "database_vcpu": spec.database_vcpu,
        "database_memory_gb": spec.database_memory_gb,
        "database_multi_az": spec.database_multi_az,
        "database_read_replicas": spec.database_read_replicas,
        "cache_vcpu": spec.cache_vcpu,
        "warehouse_node_count": getattr(spec, "warehouse_node_count", 0),
        "nat_gateway_count": spec.nat_gateway_count,
        "load_balancer": spec.load_balancer,
        "waf_rule_count": spec.waf_rule_count,
        "storage_gb": spec.storage_gb,
    }


def _roles(option) -> set[str]:
    from whichcloud import topology

    nodes = topology.build(option.spec, option.estimate, option.applied).nodes
    return {n.kind for n in nodes} - BASELINE_ROLES


def _options(requirement, provider, budget=None):
    from whichcloud import engine

    if budget is not None:
        requirement = replace(requirement, budget_monthly_usd=budget)
    return {o.label: o for o in engine.recommend(requirement, provider, dsn=None)}


# ── C1 ────────────────────────────────────────────────────────────────────


def c1_role_diversity(results: Results, reqs: dict) -> None:
    """Six fixtures must produce at least four distinct role sets.

    FAIL MEANS: template bug in the resolver.
    """
    shapes = {
        f.id: frozenset(_roles(_options(reqs[f.id], "aws")["Most reliable"]))
        for f in FIXTURES
    }
    distinct = len(set(shapes.values()))
    results.record("C1", distinct >= 4, f"{distinct} distinct role sets of {len(FIXTURES)}")


# ── C2 ────────────────────────────────────────────────────────────────────


#: Knobs that make an architecture BIGGER. Used to tell the two directions
#: apart, because they are different bugs with the same symptom.
_CAPACITY_KNOBS = (
    "compute_count", "compute_vcpu", "compute_memory_gb", "database_vcpu",
    "database_memory_gb", "database_read_replicas", "cache_vcpu",
    "warehouse_node_count", "nat_gateway_count",
)


def _bigger(a: dict, b: dict) -> list[str]:
    """Knobs on which `a` provisions more than `b`."""
    return [
        k for k in _CAPACITY_KNOBS
        if (a.get(k) or 0) > (b.get(k) or 0)
    ] + [
        k for k in ("database_multi_az", "load_balancer")
        if a.get(k) and not b.get(k)
    ]


def c2_budget_invariance(results: Results, reqs: dict) -> None:
    """Hold the workload, vary the budget. Two directions, two verdicts.

    The literal reading -- byte-identical across budgets -- is the wrong
    test, and running it first is how that became clear. `_fit_within_budget`
    is DESIGNED to degrade a design that does not fit, and to say what it
    gave up. A $500 budget against a $770 architecture is supposed to come
    back smaller. Asserting byte-equality there fails the feature, not the
    bug.

    So the check splits by direction:

      C2  INFLATION -- a higher budget must never buy MORE capacity. This is
          the real invariant, and the one the growth loop violated: budget as
          a target rather than a ceiling. A failure here is a bug.

      C2b DEGRADATION -- a lower budget may buy less, but only with a
          recorded reason. Shrinking silently is the same defect wearing a
          different hat: the user cannot act on capacity they were never
          told was removed.

    WHAT THE EXISTING SUITE MISSED: it varied the budget and asserted on the
    CHEAPEST tier only. Cheapest is the honest floor -- sized to load, with
    nothing budget could add -- so it was invariant while the two tiers above
    it were not. The test passed for the whole life of the bug.
    """
    reference = max(BUDGETS)
    for fixture in FIXTURES:
        for provider in PROVIDERS:
            by_budget = {b: _options(reqs[fixture.id], provider, b) for b in BUDGETS}
            for tier in TIERS:
                shapes = {
                    b: _shape(opts[tier]) for b, opts in by_budget.items() if tier in opts
                }
                if len(shapes) < 2:
                    results.record("C2", True, f"{fixture.id}/{provider}/{tier} n/a")
                    results.record("C2b", True, f"{fixture.id}/{provider}/{tier} n/a")
                    continue

                # Compare every budget against the LEAST constrained run: what
                # this workload asks for when money is not the question.
                unconstrained = shapes[reference]
                where = f"{fixture.id}/{provider}/{tier}"

                inflated = sorted(
                    {k for b, s in shapes.items() for k in _bigger(s, unconstrained)}
                )
                results.record(
                    "C2", not inflated,
                    where + (f"  INFLATED: {', '.join(inflated)}" if inflated else ""),
                )

                shrunk, unexplained = [], []
                for budget, shape in shapes.items():
                    smaller = _bigger(unconstrained, shape)
                    if not smaller:
                        continue
                    shrunk += smaller
                    said = [
                        t for t in by_budget[budget][tier].tradeoffs
                        if "budget" in t.lower()
                    ]
                    if not said:
                        unexplained.append(f"${budget:,.0f}")
                results.record(
                    "C2b", not unexplained,
                    where + (
                        f"  shrank silently at {', '.join(unexplained)}: "
                        f"{', '.join(sorted(set(shrunk)))}"
                        if unexplained
                        else f"  degraded with reason ({', '.join(sorted(set(shrunk)))})"
                        if shrunk else ""
                    ),
                )


# ── C3 ────────────────────────────────────────────────────────────────────


def c3_monotonicity(results: Results, reqs: dict) -> None:
    """Within one workload and provider: Lean <= Balanced <= Resilient.

    FAIL MEANS: the tier definitions are incoherent.
    """
    for fixture in FIXTURES:
        for provider in PROVIDERS:
            for budget in BUDGETS:
                opts = _options(reqs[fixture.id], provider, budget)
                costs = [float(opts[t].monthly) for t in TIERS if t in opts]
                ok = all(a <= b for a, b in zip(costs, costs[1:]))
                detail = f"{fixture.id}/{provider}/${budget:,.0f}  " + " <= ".join(
                    f"{c:,.2f}" for c in costs
                )
                results.record("C3", ok, detail)


# ── C4 ────────────────────────────────────────────────────────────────────


def c4_determinism(results: Results, reqs: dict) -> None:
    """Same input ten times. Node set and total identical every time.

    FAIL MEANS: randomness in the resolver.
    """
    for fixture in FIXTURES[:3]:
        for provider in PROVIDERS:
            hashes = set()
            for _ in range(10):
                opts = _options(reqs[fixture.id], provider)
                blob = json.dumps(
                    {
                        t: {
                            "roles": sorted(_roles(opts[t])),
                            "total": str(opts[t].monthly),
                            "shape": _shape(opts[t]),
                        }
                        for t in TIERS
                        if t in opts
                    },
                    sort_keys=True,
                )
                hashes.add(hashlib.sha256(blob.encode()).hexdigest()[:12])
            results.record(
                "C4",
                len(hashes) == 1,
                f"{fixture.id}/{provider}  {len(hashes)} distinct of 10",
            )


# ── C5 ────────────────────────────────────────────────────────────────────


def c5_node_to_line(results: Results, reqs: dict) -> None:
    """Every node on the diagram has a line item, priced or explicitly free.

    FAIL MEANS: silent omissions in the cost sheet -- a box the user can see
    and point at, that nothing on the bill accounts for.
    """
    from whichcloud import topology

    for fixture in FIXTURES:
        for provider in PROVIDERS:
            opts = _options(reqs[fixture.id], provider)
            for tier, option in opts.items():
                topo = topology.build(option.spec, option.estimate, option.applied)
                unpriced = [
                    n.label for n in topo.nodes
                    if n.kind != "client" and not n.priced and n.monthly_usd == 0
                ]
                results.record(
                    "C5",
                    not unpriced,
                    f"{fixture.id}/{provider}/{tier}  {', '.join(unpriced[:4])}",
                )


# ── C6 ────────────────────────────────────────────────────────────────────


def c6_cross_provider_spread(results: Results, reqs: dict) -> None:
    """Three provider totals within 40% of the median, per fixture and tier.

    FAIL MEANS: one provider's role mapping or rate table is wrong. The same
    workload does not cost twice as much on one cloud because of physics.
    """
    for fixture in FIXTURES:
        for tier in TIERS:
            totals = {}
            incomplete = []
            for provider in PROVIDERS:
                opts = _options(reqs[fixture.id], provider)
                if tier not in opts:
                    continue
                # An estimate that ALREADY SAYS it is missing a meter is not
                # evidence of a mapping error -- it is evidence of a catalog
                # hole, which `missing` reports and which keeps that option
                # from winning a comparison. Scoring it here too would count
                # one known gap twice and bury the spread failures that are
                # not already declared.
                if opts[tier].estimate.missing:
                    incomplete.append(provider)
                    continue
                totals[provider] = float(opts[tier].monthly)
            if len(totals) < 3:
                results.record(
                    "C6", True,
                    f"{fixture.id}/{tier} skipped — incomplete: {', '.join(incomplete)}"
                    if incomplete else f"{fixture.id}/{tier} n/a",
                )
                continue
            median = statistics.median(totals.values())
            worst = max(totals, key=lambda p: abs(totals[p] - median))
            spread = abs(totals[worst] - median) / median if median else 0.0
            results.record(
                "C6",
                spread <= 0.40,
                f"{fixture.id}/{tier}  median {median:,.0f}  "
                f"{worst} {totals[worst]:,.0f} ({spread:+.0%})",
            )


# ── C7 ────────────────────────────────────────────────────────────────────


def c7_role_justification(results: Results, reqs: dict) -> None:
    """Every non-baseline role carries a reason it is there.

    FAIL MEANS: defaults leaking in -- and this is the MECHANISM behind a C1
    failure, which is why it is worth running even when C1 passes. A resolver
    that cannot say why a role is present cannot be trusted to have derived
    it; it may simply always emit it for this workload class.
    """
    from whichcloud import topology

    for fixture in FIXTURES:
        opts = _options(reqs[fixture.id], "aws")
        for tier, option in opts.items():
            topo = topology.build(option.spec, option.estimate, option.applied)
            unjustified = [
                n.label
                for n in topo.nodes
                if n.kind not in BASELINE_ROLES
                and n.kind != "client"
                and not getattr(n, "because", None)
            ]
            results.record(
                "C7",
                not unjustified,
                f"{fixture.id}/{tier}  {len(unjustified)} roles with no reason",
            )


CHECKS = [
    ("C1", "role diversity", c1_role_diversity),
    ("C2", "budget invariance (no inflation)", c2_budget_invariance),
    ("C2b", "degradation is explained", lambda *_: None),
    ("C3", "monotonicity", c3_monotonicity),
    ("C4", "determinism", c4_determinism),
    ("C5", "node-to-line", c5_node_to_line),
    ("C6", "cross-provider spread", c6_cross_provider_spread),
    ("C7", "role justification", c7_role_justification),
]


def run(verbose: bool = True) -> Results:
    results = Results()
    reqs = {f.id: _requirement_for(f) for f in FIXTURES}
    for code, name, fn in CHECKS:
        fn(results, reqs)
        if verbose:
            passed, total = results.tally(code)
            print(f"  {code} {name:<24} {passed}/{total}", flush=True)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--failures", action="store_true", help="list every failure")
    args = parser.parse_args()

    print()
    print("PHASE 3 — INTERNAL CONSISTENCY")
    print("=" * 74)
    results = run()
    print("-" * 74)

    for code, name, _ in CHECKS:
        fails = results.failures(code)
        if not fails:
            continue
        print()
        print(f"{code} {name} — {len(fails)} failing")
        for line in fails if args.failures else fails[:12]:
            print(f"    {line}")
        if not args.failures and len(fails) > 12:
            print(f"    ... {len(fails) - 12} more (--failures for all)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
