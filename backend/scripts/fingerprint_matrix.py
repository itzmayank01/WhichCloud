"""Emit the architecture fingerprint matrix across representative fixtures.

Run against the engine to see, at a glance, which workloads produce the same
architecture. Identical tier-1 fingerprints across genuinely different
workloads is the template bug; this is the fastest way to see it, and to see
it come back.

    .venv/bin/python scripts/fingerprint_matrix.py

Reports:
  - the tier-1 fingerprint per fixture
  - DIVERGENCE collisions: fixture pairs with a different profile that share
    a tier-1 fingerprint (each one is the template bug)
  - TIER SPREAD per fixture (consecutive tiers must differ by >= 3 services)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from whichcloud.engine import recommend
from whichcloud.fingerprint import fingerprint, profile, tier_spread
from whichcloud.requirements import Requirement


# Representative workloads spanning the four derivation axes. Each is a
# genuinely different profile; the acceptance is that no two of them share a
# tier-1 fingerprint.
FIXTURES: dict[str, Requirement] = {
    "web-ecommerce": Requirement(
        goal="online store", workload_type="web", traffic_scale="high",
        daily_transactions=50_000, region="india", storage_gb=200, egress_gb=400,
        ingress_shape="requests", processing_mode="synchronous",
        data_shape="relational", egress_shape="api",
    ),
    "web-internal-tool": Requirement(
        goal="internal admin tool", workload_type="web", traffic_scale="low",
        daily_transactions=2_000, region="india", storage_gb=50, egress_gb=20,
        ingress_shape="requests", processing_mode="synchronous",
        data_shape="relational", egress_shape="api",
    ),
    "media-streaming": Requirement(
        goal="video streaming", workload_type="web", traffic_scale="high",
        daily_transactions=2_000_000, region="india", storage_gb=50_000, egress_gb=200_000,
        ingress_shape="requests", processing_mode="synchronous",
        data_shape="object", egress_shape="media",
    ),
    "batch-etl": Requirement(
        goal="nightly ETL", workload_type="batch", traffic_scale="high",
        interruptible=True, daily_transactions=1_000_000, region="india",
        storage_gb=2_000, egress_gb=50,
        ingress_shape="batches", processing_mode="batch",
        data_shape="warehouse", egress_shape="exports",
    ),
    "event-iot": Requirement(
        goal="IoT telemetry", workload_type="mixed", traffic_scale="high",
        interruptible=True, event_driven=True, telemetry=True, needs_analytics=True,
        daily_transactions=5_000_000, region="india", storage_gb=2_000, egress_gb=500,
        ingress_shape="streams", processing_mode="near-real-time",
        data_shape="time-series", egress_shape="dashboards",
    ),
    "serverless-api": Requirement(
        goal="spiky webhook API", workload_type="api", traffic_scale="medium",
        serverless=True, daily_transactions=100_000, region="india",
        storage_gb=50, egress_gb=100,
        ingress_shape="events", processing_mode="near-real-time",
        data_shape="key-value", egress_shape="api",
    ),
    "ai-vision": Requirement(
        goal="image recognition platform", workload_type="api", traffic_scale="high",
        ai=True, ai_vision=True, daily_transactions=500_000, region="india",
        storage_gb=200, egress_gb=100,
        ingress_shape="files", processing_mode="synchronous",
        data_shape="object", egress_shape="api",
    ),
}


def _fmt(fp: frozenset[str]) -> str:
    return " ".join(sorted(fp))


def main() -> int:
    tier1: dict[str, frozenset[str]] = {}
    spreads: dict[str, list[int]] = {}
    profiles: dict[str, tuple] = {}

    print("=" * 78)
    print("ARCHITECTURE FINGERPRINT MATRIX")
    print("=" * 78)
    for name, req in FIXTURES.items():
        options = recommend(req, "aws")
        tier1[name] = fingerprint(options[0])
        spreads[name] = tier_spread(options)
        profiles[name] = profile(req)
        print(f"\n{name}  (tier-1, {len(tier1[name])} services)")
        print(f"  {_fmt(tier1[name])}")
        print(f"  tier spread (>=3 each): {spreads[name]}")

    # DIVERGENCE
    print("\n" + "=" * 78)
    print("DIVERGENCE — pairs with a DIFFERENT profile sharing a tier-1 fingerprint")
    print("(each one is the template bug)")
    print("=" * 78)
    names = list(FIXTURES)
    collisions = 0
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if profiles[a] == profiles[b]:
                continue  # same profile may legitimately share
            if tier1[a] == tier1[b]:
                collisions += 1
                print(f"  COLLISION  {a}  ==  {b}")
                print(f"             {_fmt(tier1[a])}")
    if not collisions:
        print("  none — every distinct workload has a distinct tier-1 architecture")

    # TIER SPREAD
    print("\n" + "=" * 78)
    print("TIER SPREAD — fixtures whose consecutive tiers differ by < 3 services")
    print("=" * 78)
    thin = {n: s for n, s in spreads.items() if any(x < 3 for x in s)}
    if thin:
        for n, s in thin.items():
            print(f"  THIN  {n}: {s}")
    else:
        print("  none — every fixture's tiers differ by >= 3 services")

    print("\n" + "=" * 78)
    print(f"SUMMARY: {collisions} divergence collision(s), "
          f"{len(thin)} thin-spread fixture(s)")
    print("=" * 78)
    return 1 if (collisions or thin) else 0


if __name__ == "__main__":
    raise SystemExit(main())
