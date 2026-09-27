"""Terraform export: generated HCL must actually be valid HCL.

Templates are fixed at development time, so there is no runtime reason to
call the `terraform` binary from the API on every request — but it is
exactly the right tool to catch a hand-written-template mistake before it
ships. Each fixture below builds a spec/estimate combination the same way
production does (a real `ArchitectureSpec` priced against the live catalog),
generates the project, and runs a real `terraform init -backend=false` +
`terraform validate` against the result.

    .venv/bin/pytest tests/test_terraform_export.py -q
"""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from whichcloud import terraform_export
from whichcloud.api import app
from whichcloud.estimator import ArchitectureSpec, estimate
from whichcloud.pricing.store import stats

pytestmark = pytest.mark.skipif(
    sum(r["n"] for r in stats()) == 0, reason="needs an ingested price catalog"
)

TERRAFORM = shutil.which("terraform")
needs_terraform = pytest.mark.skipif(
    TERRAFORM is None, reason="terraform CLI not installed"
)


def _validate(tmp_path: Path, files: dict[str, str]) -> None:
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    init = subprocess.run(
        [TERRAFORM, "init", "-backend=false", "-input=false"],
        cwd=tmp_path, capture_output=True, text=True, timeout=120,
    )
    assert init.returncode == 0, f"terraform init failed:\n{init.stdout}\n{init.stderr}"

    validate = subprocess.run(
        [TERRAFORM, "validate"],
        cwd=tmp_path, capture_output=True, text=True, timeout=60,
    )
    assert validate.returncode == 0, (
        f"terraform validate failed:\n{validate.stdout}\n{validate.stderr}"
    )


# ── fixtures: one per resource combination ──────────────────────────────


@needs_terraform
def test_compute_and_storage_only(tmp_path):
    spec = ArchitectureSpec(
        name="web", region="india", compute_count=2, compute_vcpu=2,
        compute_memory_gb=4.0, storage_gb=200.0,
    )
    files = terraform_export.generate(spec, estimate(spec, "aws"))
    assert "module \"compute\"" in files["main.tf"]
    assert "module \"storage\"" in files["main.tf"]
    assert "module \"database\"" not in files["main.tf"]
    _validate(tmp_path, files)


@needs_terraform
def test_ec2_with_database_and_alb(tmp_path):
    spec = ArchitectureSpec(
        name="app", region="india", compute_count=3, compute_vcpu=2,
        compute_memory_gb=8.0, load_balancer=True,
        database_vcpu=2, database_memory_gb=8.0, database_multi_az=True,
        nat_gateway_count=2,
    )
    files = terraform_export.generate(spec, estimate(spec, "aws"))
    assert "module \"database\"" in files["main.tf"]
    assert "module \"alb\"" in files["main.tf"]
    assert "multi_az = var.database_multi_az" in files["main.tf"]
    # Deletion protection and backup retention ARE environment properties --
    # unlike multi_az, they carry no price tag, so they're safe to vary.
    assert "local.env.deletion_protection" in files["main.tf"]
    _validate(tmp_path, files)


@needs_terraform
def test_fargate_with_alb(tmp_path):
    spec = ArchitectureSpec(
        name="api", region="india", compute_count=0, load_balancer=True,
        fargate_task_count=2, fargate_task_vcpu=0.5, fargate_task_memory_gb=1.0,
        fargate_peak_tasks=4, nat_gateway_count=1,
    )
    files = terraform_export.generate(spec, estimate(spec, "aws"))
    assert "aws_ecs_service" in files["main.tf"]
    assert "module \"alb\"" in files["main.tf"]
    _validate(tmp_path, files)


@needs_terraform
def test_minimal_compute_only_still_validates(tmp_path):
    spec = ArchitectureSpec(name="tiny", region="india", compute_count=1)
    files = terraform_export.generate(spec, estimate(spec, "aws"))
    _validate(tmp_path, files)


@needs_terraform
@pytest.mark.parametrize("environment", ["dev", "prod"])
def test_generated_for_either_environment_still_validates(tmp_path, environment):
    """Same module, either environment -- both must be real, valid HCL, not
    just the default ("dev") that every other fixture in this file exercises."""
    spec = ArchitectureSpec(
        name="app", region="india", compute_count=3, compute_vcpu=2,
        compute_memory_gb=8.0, load_balancer=True,
        database_vcpu=2, database_memory_gb=8.0, database_multi_az=True,
        nat_gateway_count=2,
    )
    files = terraform_export.generate(spec, estimate(spec, "aws"), environment=environment)
    assert f'default = "{environment}"' in files["variables.tf"]
    _validate(tmp_path, files)


# ── environment parameterization (no terraform binary needed) ───────────


def test_dev_and_prod_tfvars_both_generated_and_differ():
    spec = ArchitectureSpec(
        name="app", region="india", compute_count=3, compute_vcpu=2,
        compute_memory_gb=8.0, database_vcpu=2, database_memory_gb=8.0,
    )
    files = terraform_export.generate(spec, estimate(spec, "aws"))
    dev_vars = files["environments/dev.tfvars"]
    prod_vars = files["environments/prod.tfvars"]
    assert 'environment = "dev"' in dev_vars
    assert 'environment = "prod"' in prod_vars
    # The one deliberately environment-scaled number: dev runs a single
    # instance regardless of how large the priced fleet is.
    assert "compute_count = 1" in dev_vars
    assert "compute_count = 3" in prod_vars


def test_environment_variable_has_a_closed_validation():
    spec = ArchitectureSpec(name="tiny", region="india", compute_count=1)
    files = terraform_export.generate(spec, estimate(spec, "aws"))
    variables = files["variables.tf"]
    assert 'variable "environment"' in variables
    assert 'contains(["dev", "prod"], var.environment)' in variables


def test_unknown_environment_falls_back_to_dev():
    spec = ArchitectureSpec(name="tiny", region="india", compute_count=1)
    files = terraform_export.generate(spec, estimate(spec, "aws"), environment="staging")
    assert 'default = "dev"' in files["variables.tf"]


def test_database_ha_setting_is_priced_not_environment_driven():
    """The one thing that must NOT vary by environment: Multi-AZ is a real
    line item on the bill, so an environment switch must never silently
    change what gets built relative to what was estimated."""
    spec = ArchitectureSpec(
        name="app", region="india", compute_count=1,
        database_vcpu=2, database_memory_gb=8.0, database_multi_az=True,
    )
    est = estimate(spec, "aws")
    dev_files = terraform_export.generate(spec, est, environment="dev")
    prod_files = terraform_export.generate(spec, est, environment="prod")
    assert "multi_az = var.database_multi_az" in dev_files["main.tf"]
    assert "multi_az = var.database_multi_az" in prod_files["main.tf"]
    assert "default = true" in dev_files["variables.tf"]  # database_multi_az


def test_resource_names_carry_the_environment_so_stacks_do_not_collide():
    spec = ArchitectureSpec(
        name="app", region="india", compute_count=1,
        database_vcpu=2, database_memory_gb=8.0,
    )
    files = terraform_export.generate(spec, estimate(spec, "aws"))
    main = files["main.tf"]
    assert "${var.project_name}-${var.environment}-vpc" in main
    assert "${var.project_name}-${var.environment}-db" in main


# ── generator-level assertions (no terraform binary needed) ─────────────


def test_unpriced_components_are_named_not_invented():
    spec = ArchitectureSpec(
        name="observed", region="india", compute_count=1,
        monitored_metrics=100, waf_rule_count=5,
    )
    files = terraform_export.generate(spec, estimate(spec, "aws"))
    readme = files["README.md"]
    assert "Monitoring" in readme or "WAF" in readme
    # Neither is a real resource this generator builds yet.
    assert "aws_wafv2" not in files["main.tf"]


def test_no_compute_no_db_still_produces_a_zip():
    spec = ArchitectureSpec(name="empty", region="india", compute_count=0)
    files = terraform_export.generate(spec, estimate(spec, "aws"))
    archive = terraform_export.zip_bytes(files)
    assert archive[:2] == b"PK"


def test_generated_instance_type_matches_the_priced_sku():
    spec = ArchitectureSpec(
        name="web", region="india", compute_count=2, compute_vcpu=2,
        compute_memory_gb=4.0,
    )
    est = estimate(spec, "aws")
    compute_item = next(i for i in est.items if i.label.startswith("Compute"))
    files = terraform_export.generate(spec, est)
    assert compute_item.sku in files["variables.tf"]


# ── endpoint wiring ───────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_plan_export_endpoint_returns_a_zip(client):
    response = client.post(
        "/plan/export.tf",
        json={
            "description": (
                "An e-commerce site for 50k users, spiky weekend traffic, "
                "$400/mo budget."
            ),
            "tier": "tier_2",
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(__import__("io").BytesIO(response.content)) as zf:
        names = zf.namelist()
        assert "main.tf" in names
        assert "README.md" in names


def test_plan_export_rejects_empty_description(client):
    response = client.post("/plan/export.tf", json={"description": "  "})
    assert response.status_code == 400


def test_plan_export_rejects_unknown_tier(client):
    response = client.post(
        "/plan/export.tf",
        json={"description": "a small internal tool", "tier": "tier_9"},
    )
    assert response.status_code == 422  # tier is a closed Literal
