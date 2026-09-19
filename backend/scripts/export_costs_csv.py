#!/usr/bin/env python3
"""Export WhichCloud's real cost line items to a CSV for Athena/QuickSight."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from whichcloud import plan as plan_module  # noqa: E402
from run_harness import constraints_from_fixture, load_fixtures  # noqa: E402

OUT = ROOT / "whichcloud_costs.csv"
HEADER = ["workload", "tier", "provider", "region", "service", "sku", "monthly_cost"]


def main() -> int:
    rows, skipped = [], []
    for fx in load_fixtures():
        if fx.get("type") == "catalog":
            continue
        direct = constraints_from_fixture(fx)
        if direct is None:
            skipped.append(fx["id"])
            continue
        constraints, archetype = direct
        try:
            built = plan_module.plan_from(constraints, fx["prompt"], archetype=archetype)
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR {fx['id']}: {exc}")
            skipped.append(fx["id"])
            continue
        for tier in built.tiers:
            est = tier.estimate
            for item in est.items:
                rows.append([
                    fx["id"], tier.label or tier.name, est.provider, est.region,
                    item.label, item.sku, round(float(item.monthly_usd), 2),
                ])

    with OUT.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUT}")
    if skipped:
        print(f"Skipped: {', '.join(skipped)}")
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
