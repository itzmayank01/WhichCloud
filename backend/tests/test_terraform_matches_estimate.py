"""The plan must build what the quote priced.

An estimate and a Terraform project that disagree are worse than either
alone: the number on the screen is defensible, the project that ships is
defensible, and nobody notices they are describing different architectures
until the first invoice.

NAT gateways are where the two most easily drift apart, because "how many"
is a question about the provider's model rather than about the design:

  * AWS  -- one per availability zone. A single gateway would strand the
    other zones' traffic across a boundary that is both slower and
    separately billed.
  * GCP  -- one per region. A per-zone Cloud NAT does not exist, so quoting
    three would price two resources that cannot be bought.
  * Azure -- one per subnet, and these architectures have one subnet. A
    zonal NAT gateway does exist, but reaching it needs a subnet per zone,
    and an Azure subnet is regional.

Three different right answers from the same design. This holds the estimator
and the generators to the same one.
"""

from __future__ import annotations

import re

import pytest

from whichcloud import (
    engine,
    terraform_export,
    terraform_export_azure,
    terraform_export_gcp,
)
from whichcloud.requirements import Requirement

GENERATORS = {
    "aws": terraform_export,
    "gcp": terraform_export_gcp,
    "azure": terraform_export_azure,
}


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


def _options(provider: str):
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
    return engine.recommend(req, provider, dsn=None)


def _priced_gateways(estimate) -> int | None:
    """However many the cost sheet charged for."""
    for item in estimate.items:
        if item.label.startswith("NAT gateway ×"):
            return int(item.label.split("×")[1].strip())
    return None


def _built_gateways(provider: str, files: dict[str, str]) -> int:
    """However many the project would actually create."""
    main = files["main.tf"]
    if provider == "gcp":
        return main.count('resource "google_compute_router_nat"')
    if provider == "azure":
        return main.count('resource "azurerm_nat_gateway"')

    # AWS delegates to the VPC module, so the count is an argument rather
    # than a resource: one gateway when single_nat_gateway is on, otherwise
    # one per zone.
    if "enable_nat_gateway = false" in main:
        return 0
    if "single_nat_gateway = true" in main:
        return 1
    default = re.search(r'variable "az_count"[^}]*default\s*=\s*(\d+)', files["variables.tf"])
    assert default, "az_count has no default to read the gateway count from"
    return int(default.group(1))


@needs_db
@pytest.mark.parametrize("provider", ["aws", "gcp", "azure"])
def test_the_project_builds_the_nat_gateways_the_estimate_charged_for(provider):
    for option in _options(provider):
        estimate = option.estimate
        priced = _priced_gateways(estimate)
        if priced is None:
            continue  # this tier has no private subnet to give outbound access
        built = _built_gateways(
            provider, GENERATORS[provider].generate(option.spec, estimate)
        )
        assert built == priced, (
            f"{provider}/{option.label}: priced {priced} NAT gateway(s), "
            f"builds {built}"
        )


@needs_db
def test_each_cloud_reaches_its_own_answer_and_not_the_same_one():
    """Guards the fix rather than the number.

    If a later change makes every provider quote the zone count again, the
    test above still passes on AWS and fails loudly elsewhere -- but if one
    made every provider quote 1, everything above would pass while AWS
    quietly stranded two zones. So assert the shapes differ.
    """
    reliable = {p: _options(p)[1] for p in GENERATORS}
    aws = _priced_gateways(reliable["aws"].estimate)
    assert aws is not None and aws > 1, "AWS should buy one gateway per zone"
    assert _priced_gateways(reliable["gcp"].estimate) == 1
    assert _priced_gateways(reliable["azure"].estimate) == 1
