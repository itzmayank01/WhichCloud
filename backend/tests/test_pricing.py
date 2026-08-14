"""Tests for the pricing layer's correctness rules.

These lock in the behaviours that keep estimates honest. Several of them exist
because the corresponding bug actually shipped and was caught by validation —
those are marked REGRESSION.

    .venv/bin/pytest -q
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from whichcloud.estimator import ArchitectureSpec, Estimate, LineItem, compare
from whichcloud.pricing import azure, specs
from whichcloud.pricing.models import (
    HOURS_PER_MONTH,
    REGIONS,
    ComputeQuery,
    PricePoint,
    provider_region,
)


def point(**kw) -> PricePoint:
    base = dict(
        provider="aws",
        category="compute",
        sku="t4g.medium",
        name="t4g.medium",
        region="ap-south-1",
        unit="hour",
        price_usd=Decimal("0.0224"),
    )
    base.update(kw)
    return PricePoint(**base)


# ── no hand-written data ────────────────────────────────────────────────


def test_no_handwritten_spec_tables():
    """Specs must come from a catalog, never from a table typed by a human.

    REGRESSION: AZURE_VM_SPECS and AZURE_DB_SPECS used to hold ~38 sizes
    recalled from memory. Prices were real but the specs beside them were not
    sourced, so a wrong entry would silently mis-match a requirement.
    """
    assert not hasattr(azure, "AZURE_VM_SPECS")
    assert not hasattr(azure, "AZURE_DB_SPECS")


def test_azure_specs_come_from_catalog():
    catalog = specs.azure_specs()
    assert len(catalog) > 500, "catalog looks truncated"

    b2s = specs.azure_spec_for("Standard_B2s")
    assert b2s is not None
    assert b2s.vcpu == 2
    assert b2s.memory_gb == 4.0
    assert b2s.arch == "x86_64"


def test_azure_arm_is_detected_from_published_arch():
    arm = specs.azure_spec_for("Standard_D2ps_v5")
    assert arm is not None and arm.arch == "arm64"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Standard_D2ps_v5", "d2psv5"),
        ("Standard_B2s", "b2s"),
        ("B2ms", "b2ms"),
        ("  Standard_E4ps_v5  ", "e4psv5"),
    ],
)
def test_sku_normalization_is_deterministic(raw, expected):
    """The VM and database feeds name the same shape differently."""
    assert specs.normalize_azure_sku(raw) == expected


def test_every_azure_spec_is_plausible():
    for name, spec in specs.azure_specs().items():
        assert spec.vcpu >= 1, name
        assert spec.memory_gb > 0, name
        assert spec.arch in ("x86_64", "arm64"), name


# ── Azure meter filtering ───────────────────────────────────────────────


def test_cloud_services_meter_is_rejected():
    """REGRESSION: the Windows-priced 'Cloud Services' meter carries neither
    'windows' nor any other distinctive word. Selecting it made 36 Azure types
    read 2.65x too expensive ($0.148 instead of $0.0556 for D2as_v5)."""
    assert not azure.is_ondemand_vm_meter(
        {
            "type": "Consumption",
            "productName": "Dasv5 Series Cloud Services",
            "skuName": "Standard_D2as_v5",
            "meterName": "D2as v5",
        }
    )


def test_linux_vm_meter_is_accepted():
    assert azure.is_ondemand_vm_meter(
        {
            "type": "Consumption",
            "productName": "Virtual Machines Dasv5 Series",
            "skuName": "Standard_D2as_v5",
            "meterName": "D2as v5",
        }
    )


@pytest.mark.parametrize(
    "item",
    [
        {"type": "DevTestConsumption", "productName": "Virtual Machines Dasv5 Series"},
        {"type": "Reservation", "productName": "Virtual Machines Dasv5 Series"},
        {"type": "Consumption", "productName": "Virtual Machines Dasv5 Series Windows"},
        {
            "type": "Consumption",
            "productName": "Virtual Machines Dasv5 Series",
            "skuName": "Standard_D2as_v5 Low Priority",
        },
    ],
)
def test_non_ondemand_linux_meters_are_rejected(item):
    assert not azure.is_ondemand_vm_meter(item)


# ── GCP architecture inference ──────────────────────────────────────────


@pytest.mark.parametrize(
    "machine,expected",
    [
        ("t2a-standard-2", "arm64"),
        ("c4a-standard-4", "arm64"),
        ("n2d-standard-2", "x86_64"),
        ("e2-medium", "x86_64"),
        ("c2d-standard-2", "x86_64"),
    ],
)
def test_gcp_arch_follows_documented_naming(machine, expected):
    """The one inference left in the pricing layer, asserted explicitly."""
    assert specs.gcp_arch_for(machine) == expected


# ── price model arithmetic ──────────────────────────────────────────────


def test_hourly_price_converts_to_month():
    assert point(price_usd=Decimal("1")).monthly_usd == HOURS_PER_MONTH


def test_metered_price_is_not_multiplied_by_hours():
    gb = point(category="storage", unit="GB-month", price_usd=Decimal("0.025"))
    assert gb.monthly_usd == Decimal("0.025")


def test_region_mapping_is_defined_for_all_providers():
    for key, mapped in REGIONS.items():
        for provider in ("aws", "azure", "gcp"):
            assert provider_region(key, provider) == mapped[provider]


def test_unknown_region_raises_rather_than_defaulting():
    with pytest.raises(ValueError):
        provider_region("atlantis", "aws")


# ── requirement matching ────────────────────────────────────────────────


def test_query_rejects_undersized_machines():
    query = ComputeQuery(min_vcpu=4, min_memory_gb=8, region="india")
    assert not query.matches(point(vcpu=2, memory_gb=8))
    assert not query.matches(point(vcpu=4, memory_gb=4))
    assert query.matches(point(vcpu=4, memory_gb=8))


def test_query_without_specs_never_matches():
    """A machine we cannot describe must not be recommended."""
    query = ComputeQuery(min_vcpu=1, min_memory_gb=1, region="india")
    assert not query.matches(point(vcpu=None, memory_gb=None))


def test_arch_constraint_is_honoured():
    query = ComputeQuery(2, 4, "india", arch="arm64")
    assert query.matches(point(vcpu=2, memory_gb=4, arch="arm64"))
    assert not query.matches(point(vcpu=2, memory_gb=4, arch="x86_64"))


# ── estimator honesty ───────────────────────────────────────────────────


def line(amount: str) -> LineItem:
    return LineItem(
        label="x",
        sku="x",
        unit="hour",
        unit_price=Decimal(amount),
        quantity=Decimal(1),
        monthly_usd=Decimal(amount),
    )


def test_incomplete_estimate_never_wins_a_comparison(monkeypatch):
    """REGRESSION-GUARD: a total missing its database is not cheaper, it is
    wrong. Ranking it first would tell the user to pick the wrong cloud."""
    spec = ArchitectureSpec(name="t", region="india")

    cheap_but_broken = Estimate("gcp", "asia-south1", spec, [line("10")], ["database"])
    dearer_but_whole = Estimate("aws", "ap-south-1", spec, [line("100")], [])

    def fake_estimate(_spec, provider, dsn=None):
        return cheap_but_broken if provider == "gcp" else dearer_but_whole

    monkeypatch.setattr("whichcloud.estimator.estimate", fake_estimate)
    ranked = compare(spec, providers=("aws", "gcp"))

    assert ranked[0].provider == "aws"
    assert ranked[0].is_complete
    assert not ranked[-1].is_complete


def test_estimate_totals_its_line_items():
    spec = ArchitectureSpec(name="t", region="india")
    est = Estimate("aws", "ap-south-1", spec, [line("10"), line("2.50")])
    assert est.total_monthly == Decimal("12.50")
    assert est.is_complete


def test_estimate_with_no_items_is_zero_not_an_error():
    est = Estimate("aws", "ap-south-1", ArchitectureSpec(name="t", region="india"))
    assert est.total_monthly == Decimal(0)
