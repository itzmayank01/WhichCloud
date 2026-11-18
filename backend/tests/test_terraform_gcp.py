"""Google Cloud Terraform must describe Google Cloud.

The export used to hand out AWS resources for a GCP architecture -- not
because it had no guard, but because the guard read the provider from the
description rather than from the request. The file that produced was valid
HCL: it planned, and it would have applied, against the wrong cloud.

These assert the two things that failure needed: that the right generator is
chosen, and that what it emits is Google's resource graph rather than a
renamed copy of Amazon's.
"""

from __future__ import annotations

import pytest

from whichcloud import engine, terraform_export_gcp
from whichcloud.requirements import Requirement

from tests.tf_validate import needs_terraform, validate_project


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


def _option():
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
    return engine.recommend(req, "gcp", dsn=None)[1]  # the HA tier


@needs_db
def test_no_aws_resource_reaches_a_google_project():
    """The failure that started this: aws_ resources in a GCP export."""
    files = terraform_export_gcp.generate(_option().spec, _option().estimate)
    body = "\n".join(files.values())
    assert "aws_" not in body, "AWS resources in a Google Cloud project"
    assert 'provider "google"' in files["main.tf"]


@needs_db
def test_the_google_shape_is_google_shaped():
    """Not a renamed AWS graph.

    Each assertion here is a place the two clouds genuinely differ, and each
    is something a find-and-replace over the AWS templates would get wrong.
    """
    option = _option()
    main = terraform_export_gcp.generate(option.spec, option.estimate)["main.tf"]

    # The network is global: it takes no region argument at all.
    net = main.split('resource "google_compute_network"')[1].split("}")[0]
    assert "region" not in net, "a Google VPC network is global, not regional"

    # ONE Cloud NAT on ONE router, however many zones the design spans.
    assert main.count('resource "google_compute_router_nat"') == 1
    assert main.count('resource "google_compute_router"') == 1

    # Regional manager: this is what spreads instances across zones, and is
    # what "survives a zone failure" actually means here.
    assert 'resource "google_compute_region_instance_group_manager"' in main
    assert 'resource "google_compute_instance_group_manager"' not in main

    # The external load balancer is global and anycast, not regional.
    assert 'resource "google_compute_global_forwarding_rule"' in main


@needs_db
def test_high_availability_is_expressed_as_cloud_sql_regional():
    """Google's word for it is REGIONAL, and it has to be the real argument.

    Labelling a database multi-AZ in prose while emitting a zonal instance is
    the class of error this whole branch has been unpicking.
    """
    option = _option()
    main = terraform_export_gcp.generate(option.spec, option.estimate)["main.tf"]
    if option.spec.database_multi_az:
        assert 'availability_type = "REGIONAL"' in main
    else:
        assert 'availability_type = "ZONAL"' in main


# ── environment parameterization ────────────────────────────────────────
#
# GCP got dev/prod after AWS, so these mirror the AWS cases in
# test_terraform_export.py rather than inventing a second shape for it.


@needs_db
def test_dev_and_prod_tfvars_both_generated_and_differ():
    opt = _option()
    files = terraform_export_gcp.generate(opt.spec, opt.estimate)
    dev_vars = files["environments/dev.tfvars"]
    prod_vars = files["environments/prod.tfvars"]
    assert 'environment = "dev"' in dev_vars
    assert 'environment = "prod"' in prod_vars
    # The one deliberately environment-scaled number: dev runs a single
    # instance regardless of how large the priced fleet is.
    assert "compute_count = 1" in dev_vars
    assert f"compute_count = {opt.spec.compute_count}" in prod_vars


@needs_db
def test_environment_variable_has_a_closed_validation():
    variables = terraform_export_gcp.generate(_option().spec, _option().estimate)[
        "variables.tf"
    ]
    assert 'variable "environment"' in variables
    assert 'contains(["dev", "prod"], var.environment)' in variables


@needs_db
def test_unknown_environment_falls_back_to_dev():
    files = terraform_export_gcp.generate(
        _option().spec, _option().estimate, environment="staging"
    )
    assert 'default = "dev"' in files["variables.tf"]


@needs_db
def test_the_env_map_is_the_only_place_dev_and_prod_differ():
    """Cloud SQL safety settings read from local.env, never from a literal.

    A hardcoded `deletion_protection = true` is what this replaced: it made
    a dev teardown need a console visit, and it meant the two environments
    were the same file with a different label rather than one module.
    """
    opt = _option()
    main = terraform_export_gcp.generate(opt.spec, opt.estimate)["main.tf"]
    assert "local.env_defaults" in main
    assert "deletion_protection = local.env.deletion_protection" in main
    assert "point_in_time_recovery_enabled = local.env.point_in_time_recovery" in main
    assert "deletion_protection = true" not in main


@needs_db
def test_priced_choices_do_not_vary_by_environment():
    """The invariant the whole design protects: an environment switch must
    never change what gets built relative to what was estimated. Machine
    type, Cloud SQL tier and REGIONAL/ZONAL availability are line items on
    the bill, so they must read identically in both."""
    opt = _option()
    dev = terraform_export_gcp.generate(opt.spec, opt.estimate, environment="dev")
    prod = terraform_export_gcp.generate(opt.spec, opt.estimate, environment="prod")
    # main.tf is where the resources are; it must be byte-identical, because
    # everything environment-shaped lives in locals + tfvars, not here.
    assert dev["main.tf"] == prod["main.tf"]
    availability = (
        'availability_type = "REGIONAL"'
        if opt.spec.database_multi_az
        else 'availability_type = "ZONAL"'
    )
    assert availability in dev["main.tf"]


# ── real terraform validate (provider schema, not just grammar) ─────────


@needs_db
@needs_terraform
@pytest.mark.parametrize("environment", ["dev", "prod"])
def test_generated_project_passes_real_terraform_validate(tmp_path, environment):
    """hcl2 proves the grammar; only Terraform proves the schema.

    `backup_retention_settings` nesting inside `backup_configuration` and
    `user_labels` on `settings` are both things the Google provider either
    accepts or does not, and a parse cannot tell the difference.
    """
    opt = _option()
    files = terraform_export_gcp.generate(opt.spec, opt.estimate, environment=environment)
    validate_project(tmp_path, files)
