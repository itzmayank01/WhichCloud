"""Every approximation is visible where the number appears.

The rule this file holds: a README note is not disclosure. The reader of
a bill sees a line and a figure and nothing else, so a figure that is
derived rather than published, single-sourced rather than cross-checked,
or good for ranking but not for billing has to say so ON THE LINE.

Three approximations were previously recorded only in provider adapters
or in backend/README.md, where nobody pricing a workload would meet them:

    Azure HA      billed as 2x primary, because Azure publishes no HA
                  meter at all
    AWS spot      from a public feed carrying NO TIMESTAMP
    GCP           single-sourced, because no independent credential-free
                  feed exists to cross-check it against

A fourth is structural: GCP's ARM detection is inferred from machine
naming, and the cached GCP catalog was checked on 2026-09-09 to confirm
there is no architecture field to read instead.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from whichcloud.estimator import ArchitectureSpec, caveats_for, estimate
from whichcloud.pricing.models import PricePoint
from whichcloud.pricing.store import stats

pytestmark = pytest.mark.skipif(
    sum(r["n"] for r in stats()) == 0, reason="needs an ingested price catalog"
)


def _point(provider="aws", **attrs) -> PricePoint:
    return PricePoint(
        provider=provider, category="c", sku="s", name="n", region="r",
        unit="hour", price_usd=Decimal("1"), attributes=attrs or {},
    )


# ── the four approximations ──────────────────────────────────────────


def test_a_derived_rate_says_it_is_derived():
    caveats = caveats_for(
        _point("azure", derived="2x primary; Azure bills the HA standby "
                                "as a second instance"),
        "azure",
    )
    assert any("Derived" in c and "2x primary" in c for c in caveats)


def test_azure_multi_az_carries_the_caveat_on_a_real_bill():
    """Not a unit test of the helper — the actual line item a user sees."""
    est = estimate(ArchitectureSpec(
        name="t", region="india", compute_count=0,
        database_vcpu=2, database_memory_gb=8.0, database_multi_az=True,
    ), "azure")
    ha = [i for i in est.items if "Multi-AZ" in i.label]
    assert ha, "no Multi-AZ line to check"
    assert any("Derived" in c for c in ha[0].caveats)


def test_a_spot_rate_says_it_is_not_billing_grade():
    """AWS's public spot feed carries no timestamp. Fine for ranking spot
    against on-demand; not a number to budget from."""
    est = estimate(ArchitectureSpec(
        name="t", region="india", compute_count=2, compute_vcpu=2,
        use_spot=True,
    ), "aws")
    spot = [i for i in est.items if i.label.startswith("Compute")]
    assert spot
    joined = " ".join(spot[0].caveats)
    assert "NO TIMESTAMP" in joined
    assert "not billing-grade" in joined


def test_every_gcp_figure_says_it_is_single_sourced():
    """AWS is cross-checked against the AWS Price List CSV and Azure
    against the Vantage catalog. Nothing comparable exists for GCP, and
    that is a property of every GCP number rather than a footnote."""
    est = estimate(ArchitectureSpec(
        name="t", region="india", compute_count=2, compute_vcpu=2,
        storage_gb=100,
    ), "gcp")
    assert est.items
    for item in est.items:
        assert any("Single-sourced" in c for c in item.caveats), item.label


def test_aws_and_azure_are_not_marked_single_sourced():
    """The label has to mean something. Applying it everywhere would make
    it noise, and both of these ARE cross-checked."""
    for provider in ("aws", "azure"):
        est = estimate(ArchitectureSpec(
            name="t", region="india", compute_count=1, compute_vcpu=2,
        ), provider)
        for item in est.items:
            assert not any("Single-sourced" in c for c in item.caveats)


def test_a_gcp_arm_line_says_the_architecture_was_inferred():
    caveats = caveats_for(
        PricePoint(provider="gcp", category="compute", sku="t2a-standard-2",
                   name="n", region="r", unit="hour",
                   price_usd=Decimal("1"), arch="arm64"),
        "gcp",
    )
    assert any("INFERRED" in c for c in caveats)


def test_the_gcp_catalog_really_has_no_architecture_field():
    """The inference is only defensible if there is nothing to read
    instead. This asserts the premise rather than trusting the comment."""
    import json
    from pathlib import Path

    cache = Path.home() / ".cache" / "whichcloud" / "gcp-instances.json"
    if not cache.exists():
        pytest.skip("GCP machine catalog not cached")
    rows = json.loads(cache.read_text())
    rows = rows if isinstance(rows, list) else rows.get("instances", [])
    assert rows
    keys = set(rows[0])
    assert not {k for k in keys if "arch" in k.lower()}


# ── the label must not fire where nothing is approximate ─────────────


def test_a_published_on_demand_rate_carries_no_caveat():
    """Most numbers here are published rates read straight from a
    provider feed. Marking those would drown the ones that matter."""
    assert caveats_for(_point("aws"), "aws") == ()


def test_a_committed_rate_says_it_assumes_a_commitment():
    caveats = caveats_for(_point("aws", purchase="commit1yr"), "aws")
    assert any("commitment you have not made" in c for c in caveats)


# ── GCP depth ────────────────────────────────────────────────────────


def test_gcp_prices_all_four_of_its_storage_classes():
    """Coldline was missing, leaving GCP with three of four and no
    equivalent for the 90-day tier AWS prices. A lifecycle comparison
    that skips a class is not a cheaper cloud, it is a shorter list."""
    from whichcloud.pricing import store

    for sku in ("gcs:standard", "gcs:nearline", "gcs:coldline", "gcs:archive"):
        category = "storage" if sku == "gcs:standard" else "storage_lifecycle"
        point = store.get_price("gcp", "asia-south1", category, sku)
        assert point is not None, f"{sku} is not priced"
