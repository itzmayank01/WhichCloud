"""Azure Terraform must describe Azure.

Same failure the Google generator was written for: the export handed out AWS
resources whatever cloud the architecture was priced on. Azure's shape is the
furthest from AWS of the three, so these assert the differences a literal
translation would get wrong -- and get wrong quietly, since the wrong file
still plans and still applies.
"""

from __future__ import annotations

import pytest

from whichcloud import engine, terraform_export_azure
from whichcloud.requirements import Requirement
from whichcloud.terraform_export_azure import _flexible_server_sku


def db_available() -> bool:
    try:
        from whichcloud.pricing.store import connect

        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) AS n FROM price_points")
            return cur.fetchone()["n"] > 0
    except Exception:
        return False


needs_db = pytest.mark.skipif(
    not db_available(), reason="needs an ingested price catalog"
)


def _options():
    req = Requirement(
        goal="Retail billing",
        workload_type="web",
        traffic_pattern="steady",
        traffic_scale="high",
        region="india",
        budget_monthly_usd=5000.0,
        storage_gb=500,
        egress_gb=500,
        high_availability=True,
        daily_transactions=8_000,
    )
    return engine.recommend(req, "azure", dsn=None)


def _main(option) -> str:
    return terraform_export_azure.generate(option.spec, option.estimate)["main.tf"]


@needs_db
def test_no_other_cloud_reaches_an_azure_subscription():
    for option in _options():
        files = terraform_export_azure.generate(option.spec, option.estimate)
        body = "\n".join(files.values())
        assert "aws_" not in body, f"AWS resources in {option.label}"
        assert "google_compute" not in body, f"Google resources in {option.label}"
        assert 'provider "azurerm"' in files["main.tf"]


@needs_db
def test_everything_is_inside_a_resource_group():
    """Azure's mandatory container, and AWS's missing one.

    A generator ported from the AWS templates would have no reason to emit
    this, and every resource below it would fail to plan.
    """
    main = _main(_options()[1])
    assert 'resource "azurerm_resource_group" "main"' in main
    for resource in ("azurerm_virtual_network", "azurerm_linux_virtual_machine_scale_set"):
        block = main.split(f'resource "{resource}"')[1].split("\nresource ")[0]
        assert "azurerm_resource_group.main.name" in block, (
            f"{resource} is not in the resource group"
        )


@needs_db
def test_zones_live_on_the_scale_set_and_not_on_the_subnet():
    """The trap in translating an AWS design.

    On AWS a subnet is IN an availability zone, so spanning zones means more
    subnets. On Azure the subnet is regional and the resource names its
    zones -- so a literal port produces three subnets that buy nothing, and
    a scale set with no zones at all.
    """
    option = _options()[1]  # the HA tier
    main = _main(option)

    app_subnet = main.split('resource "azurerm_subnet" "app"')[1].split("}")[0]
    assert "zones" not in app_subnet, "an Azure subnet is regional, not zonal"

    vmss = main.split('resource "azurerm_linux_virtual_machine_scale_set"')[1]
    vmss = vmss.split("\nresource ")[0]
    assert "zones" in vmss, "nothing spreads this scale set across zones"


@needs_db
def test_one_nat_gateway_because_a_subnet_accepts_one():
    main = _main(_options()[1])
    assert main.count('resource "azurerm_nat_gateway"') == 1
    assert main.count('resource "azurerm_subnet_nat_gateway_association"') == 1


@needs_db
def test_the_database_gets_the_delegated_subnet_it_requires():
    """Flexible Server on a private address needs both of these.

    Neither has an AWS counterpart, so neither would survive a port -- and
    the apply fails without them, after the resource group already exists.
    """
    main = _main(_options()[1])
    assert 'resource "azurerm_private_dns_zone" "database"' in main
    db_subnet = main.split('resource "azurerm_subnet" "database"')[1].split("\nresource ")[0]
    assert "Microsoft.DBforPostgreSQL/flexibleServers" in db_subnet


@needs_db
def test_high_availability_is_zone_redundant_with_a_different_standby():
    """Naming the same zone twice is accepted and buys nothing."""
    option = _options()[1]
    main = _main(option)
    if not option.spec.database_multi_az:
        pytest.skip("this tier is not highly available")
    ha = main.split("high_availability {")[1].split("}")[0]
    assert '"ZoneRedundant"' in ha
    primary = main.split("  zone                          = ")[1].split("\n")[0].strip()
    standby = ha.split("standby_availability_zone = ")[1].split("\n")[0].strip()
    assert primary != standby, "the standby is in the primary's zone"


@needs_db
def test_the_gateway_gets_a_subnet_of_its_own():
    """Application Gateway will not share one, and says so at apply time."""
    for option in _options():
        main = _main(option)
        if 'resource "azurerm_application_gateway"' not in main:
            continue
        assert 'resource "azurerm_subnet" "gateway"' in main
        gw = main.split('resource "azurerm_application_gateway"')[1]
        assert "azurerm_subnet.gateway.id" in gw


def test_catalog_skus_become_names_azure_will_accept():
    """The price list and the API do not spell these the same way.

    Passing the catalog's spelling through fails at apply, which is late --
    the resource group and network already exist by then.
    """
    assert _flexible_server_sku("B4ms") == "B_Standard_B4ms"
    assert _flexible_server_sku("B1MS") == "B_Standard_B1ms"
    assert _flexible_server_sku("Ddsv5-4vcore") == "GP_Standard_D4ds_v5"
    # E is the memory-optimised family, and gets the MO_ tier, not GP_.
    assert _flexible_server_sku("Eadsv5-16vcore") == "MO_Standard_E16ads_v5"
    # The multi-az suffix is a catalog detail, not part of the SKU.
    assert _flexible_server_sku("B4ms:multi-az") == "B_Standard_B4ms"
    # Unrecognised comes back untouched rather than invented.
    assert _flexible_server_sku("something-new") == "something-new"


# ── endpoint wiring ───────────────────────────────────────────────────────


@needs_db
def test_plan_export_generates_for_the_provider_it_priced():
    """The other half of the same bug.

    `/describe/export.tf` was fixed to read the provider from the request;
    `/plan/export.tf` still priced on AWS and exported AWS whatever was
    asked for. Both routes reach the same generators, so both had to learn
    the same thing -- a fix in one is half a fix.
    """
    from fastapi.testclient import TestClient

    from whichcloud.api import app

    client = TestClient(app)
    description = "An e-commerce site for 50k users, spiky weekend traffic."
    expected = {"aws": "aws_", "gcp": "google_compute_network", "azure": "azurerm_resource_group"}

    for provider, marker in expected.items():
        response = client.post(
            "/plan/export.tf",
            json={"description": description, "tier": "tier_2", "provider": provider},
        )
        assert response.status_code == 200, (provider, response.text[:200])
        import io
        import zipfile

        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            main = zf.read("main.tf").decode()
        assert marker in main, f"{provider} export has no {marker}"
        for other, other_marker in expected.items():
            if other != provider:
                assert other_marker not in main, (
                    f"{provider} export contains {other} resources"
                )
