"""Dump every divergence fixture's three tiers as a priced topology graph.

The renderer is a pure function from component graph to diagram, so the graph
is the contract. This writes each fixture's three tiers -- nodes and edges,
exactly as the API's /recommend serves them -- to a JSON the frontend
diagram-lab renders and the layout-quality harness measures. One source of
truth for both the picture and its checks.

    .venv/bin/python scripts/dump_topology.py

Writes frontend/lib/fixtureTopologies.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from whichcloud import topology as topo
from whichcloud.engine import recommend
from whichcloud.fingerprint import fingerprint, profile, tier_spread
from fingerprint_matrix import FIXTURES

OUT = (
    Path(__file__).resolve().parent.parent.parent
    / "frontend" / "lib" / "fixtureTopologies.json"
)


def _node_out(n, total) -> dict:
    return {
        "id": n.id,
        "label": n.label,
        "kind": n.kind,
        "monthly_usd": float(n.monthly_usd),
        "share": n.share_of(total),
        "sku": n.sku,
        "detail": n.detail,
        "priced": n.priced,
        "optimized_by": list(n.optimized_by),
    }


def main() -> int:
    out: dict = {"fixtures": {}}
    for name, req in FIXTURES.items():
        options = recommend(req, "aws")
        tiers = []
        for opt in options:
            graph = topo.build(opt.spec, opt.estimate, opt.applied)
            total = graph.total_monthly
            tiers.append({
                "label": opt.label,
                "monthly_usd": float(opt.monthly),
                "fingerprint": sorted(fingerprint(opt)),
                "nodes": [_node_out(n, total) for n in graph.nodes],
                "edges": [
                    {"source": e.source, "target": e.target, "label": e.label}
                    for e in graph.edges
                ],
            })
        out["fixtures"][name] = {
            "goal": req.goal,
            "workload_type": req.workload_type,
            "profile": list(profile(req)),
            "tier_spread": tier_spread(options),
            "tiers": tiers,
        }
        print(f"  {name}: {len(tiers)} tiers, "
              f"{[len(t['nodes']) for t in tiers]} nodes, spread {tier_spread(options)}")

    OUT.write_text(json.dumps(out, indent=1))
    print(f"\nwrote {OUT}  ({OUT.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
