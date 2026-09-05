"""THE SCORECARD. One command, and the regression suite from here on.

    python -m audit

Architecture correctness and cost accuracy are scored SEPARATELY because they
are independent failures. A correct architecture can be priced wrong; a wrong
architecture can be priced perfectly. Reporting one number hides which of the
two is broken, which is the state this audit was built to end.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys

PROVIDERS = ("aws", "gcp", "azure")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tier", default="Most reliable")
    args = ap.parse_args()

    from audit import phase1_architecture, phase2_cost, phase3_consistency
    from audit.fixtures.requirements import FIXTURES
    from audit.phase3_consistency import CHECKS

    print()
    print("=" * 62)
    print(f"  WHICHCLOUD AUDIT — {dt.date.today().isoformat()}")
    print("=" * 62)

    arch = phase1_architecture.run(args.tier)
    cost = phase2_cost.run()
    consistency = phase3_consistency.run(verbose=False)

    def col(values) -> str:
        return "".join(f"{v:>9}" for v in values)

    print()
    print(f"  ARCHITECTURE CORRECTNESS      {col(p.upper() for p in PROVIDERS)}")
    means = [
        round(sum(arch[f.id][p]["score"] for f in FIXTURES) / len(FIXTURES))
        for p in PROVIDERS
    ]
    print(f"    mean score / 100            {col(means)}")
    for key, label in (
        ("missing", "missing roles (total)"),
        ("extra", "extra roles, unjustified"),
        ("forbidden_present", "roles the brief ruled out"),
        ("hierarchy", "hierarchy violations"),
    ):
        print(f"    {label:<28}" + col(
            sum(len(arch[f.id][p][key]) for f in FIXTURES) for p in PROVIDERS
        ))

    print()
    print(f"  COST ACCURACY                 {col(p.upper() for p in PROVIDERS)}")
    recon, worst, sane = [], [], []
    for p in PROVIDERS:
        rows = cost[p]
        lines = sum(r["lines"] for r in rows)
        off = [o for r in rows for o in r["off"]]
        recon.append(f"{lines - len(off)}/{lines}")
        worst.append("—" if not off else "see --detail")
        per_check = [
            all(r["sanity"][name][0] for r in rows) for name, _ in phase2_cost.SANITY
        ]
        sane.append(f"{sum(per_check)}/{len(per_check)}")
    print(f"    lines reconciled            {col(recon)}")
    print(f"    worst line delta            {col(worst)}")
    print(f"    unit sanity checks          {col(sane)}")

    print()
    print("  INTERNAL CONSISTENCY          pass / total")
    for code, name, _ in CHECKS:
        passed, total = consistency.tally(code)
        flag = "" if passed == total else "   <-- FAILING"
        print(f"    {code:<4}{name:<26}{passed:>4}/{total}{flag}")

    print()
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
