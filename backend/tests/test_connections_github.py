"""GitHub connect: real Terraform-repo scanning, not the fabricated stub.

`connections/github.py` used to return a hardcoded fake success message for
any input, including a repository that does not exist. These tests cover
the real replacement: parsing recognised AWS Terraform shapes and pricing
them against the live catalog (needs an ingested catalog, like every other
pricing test in this suite), the network-fetch layer mocked out so no test
here makes a real call to GitHub, and the route-level guarantee that a
GitHub token is never written to the saved connection.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from whichcloud.api import app
from whichcloud.connections import github as conn_gh
from whichcloud.pricing.store import stats


def catalog_ready() -> bool:
    try:
        return sum(r["n"] for r in stats()) > 0
    except Exception:
        return False


needs_db = pytest.mark.skipif(
    not catalog_ready(), reason="needs an ingested price catalog"
)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _as(owner: str):
    from whichcloud.auth import current_owner

    app.dependency_overrides[current_owner] = lambda: owner


def _anonymous():
    app.dependency_overrides.clear()


# ── _parse_and_price: pure, literal fixtures, no mocking ────────────────


@needs_db
def test_compute_module_with_a_literal_instance_type_is_priced():
    tf = '''
    module "compute" {
      source        = "terraform-aws-modules/autoscaling/aws"
      instance_type = "t4g.large"
    }
    '''
    items, missing, total = conn_gh._parse_and_price({"main.tf": tf}, "ap-south-1")
    assert len(items) == 1
    assert items[0]["sku"] == "t4g.large"
    assert items[0]["monthly"] > 0
    assert float(total) == items[0]["monthly"]
    assert missing == []


@needs_db
def test_compute_module_referencing_a_variable_is_reported_unpriced_not_guessed():
    tf = '''
    module "compute" {
      source        = "terraform-aws-modules/autoscaling/aws"
      instance_type = var.compute_instance_type
    }
    '''
    items, missing, total = conn_gh._parse_and_price({"main.tf": tf}, "ap-south-1")
    assert items == []
    assert total == 0
    assert len(missing) == 1
    assert "variable" in missing[0]


@needs_db
def test_rds_module_with_multi_az_gets_the_multi_az_sku_suffix():
    tf = '''
    module "database" {
      source         = "terraform-aws-modules/rds/aws"
      instance_class = "db.t4g.large"
      multi_az       = true
    }
    '''
    items, missing, total = conn_gh._parse_and_price({"main.tf": tf}, "ap-south-1")
    assert len(items) == 1
    assert items[0]["sku"] == "db.t4g.large:multi-az"
    assert missing == []


@needs_db
def test_rds_module_without_multi_az_prices_single_az():
    tf = '''
    module "database" {
      source         = "terraform-aws-modules/rds/aws"
      instance_class = "db.t4g.large"
    }
    '''
    items, _, _ = conn_gh._parse_and_price({"main.tf": tf}, "ap-south-1")
    assert items[0]["sku"] == "db.t4g.large"


@needs_db
def test_s3_module_is_recognised_but_never_priced_from_a_guessed_size():
    tf = '''
    module "storage" {
      source = "terraform-aws-modules/s3-bucket/aws"
      bucket = "my-app-assets"
    }
    '''
    items, missing, total = conn_gh._parse_and_price({"main.tf": tf}, "ap-south-1")
    assert items == []
    assert total == 0
    assert len(missing) == 1
    assert "size" in missing[0]


@needs_db
def test_arm_fargate_task_definition_is_priced_at_arm_rates():
    tf = '''
    resource "aws_ecs_task_definition" "app" {
      cpu    = 512
      memory = 1024
      runtime_platform {
        cpu_architecture = "ARM64"
      }
    }
    '''
    items, missing, total = conn_gh._parse_and_price({"main.tf": tf}, "ap-south-1")
    assert len(items) == 1
    assert items[0]["monthly"] > 0
    assert missing == []


@needs_db
def test_a_real_multi_resource_file_prices_correctly_end_to_end():
    """The shape terraform_export.py itself generates -- compute, database,
    alb, storage -- all in one file, matching what a repo built from this
    app's own /plan or /describe export would actually contain."""
    tf = '''
    module "compute" {
      source        = "terraform-aws-modules/autoscaling/aws"
      instance_type = "t4g.large"
    }
    module "database" {
      source         = "terraform-aws-modules/rds/aws"
      instance_class = "db.t4g.large"
      multi_az       = true
    }
    module "alb" {
      source = "terraform-aws-modules/alb/aws"
    }
    module "storage" {
      source = "terraform-aws-modules/s3-bucket/aws"
    }
    '''
    items, missing, total = conn_gh._parse_and_price({"main.tf": tf}, "ap-south-1")
    assert {i["label"].split(" (")[0] for i in items} == {"Compute", "Database", "Load balancer"}
    assert len(missing) == 1  # only the storage module
    assert total > 0


def test_unparseable_hcl_is_reported_not_raised():
    items, missing, total = conn_gh._parse_and_price({"broken.tf": "not { valid hcl"}, "ap-south-1")
    assert items == []
    assert total == 0
    assert len(missing) == 1
    assert "broken.tf" in missing[0]


# ── owner/repo parsing ────────────────────────────────────────────────


def test_owner_repo_accepts_bare_and_url_forms():
    assert conn_gh._owner_repo("owner/repo") == ("owner", "repo")
    assert conn_gh._owner_repo("https://github.com/owner/repo") == ("owner", "repo")
    assert conn_gh._owner_repo("https://github.com/owner/repo.git") == ("owner", "repo")


def test_owner_repo_rejects_garbage():
    with pytest.raises(ValueError):
        conn_gh._owner_repo("not-a-repo")


# ── verify(): network mocked, success/failure shaping ────────────────────


@needs_db
def test_verify_success_summarises_a_real_scan(monkeypatch):
    tf = '''
    module "compute" {
      source        = "terraform-aws-modules/autoscaling/aws"
      instance_type = "t4g.large"
    }
    '''
    monkeypatch.setattr(conn_gh, "_fetch_terraform_files", lambda *a, **k: {"main.tf": tf})

    result = conn_gh.verify({
        "repo_url": "owner/repo",
        "branch": "main",
        "github_token": "ghp_fake",
        "iac_path": "terraform/",
    })

    assert result.ok is True
    assert result.account_id == "owner/repo"
    assert result.data["items"]
    assert result.data["monthly_cost"] > 0
    assert "1 priced resource" in result.message


def test_verify_reports_a_bad_repo_name_without_raising():
    result = conn_gh.verify({
        "repo_url": "not-a-repo",
        "branch": "main",
        "github_token": "x",
        "iac_path": "",
    })
    assert result.ok is False
    assert result.data == {}


def test_verify_surfaces_the_fetch_failure_reason_verbatim(monkeypatch):
    def boom(*a, **k):
        raise ValueError("token can't read this repository")

    monkeypatch.setattr(conn_gh, "_fetch_terraform_files", boom)
    result = conn_gh.verify({
        "repo_url": "owner/repo", "branch": "main", "github_token": "bad", "iac_path": "",
    })
    assert result.ok is False
    assert "token can't read" in result.message


def test_verify_treats_an_unexpected_network_error_as_unreachable_not_a_crash(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("connection reset")

    monkeypatch.setattr(conn_gh, "_fetch_terraform_files", boom)
    result = conn_gh.verify({
        "repo_url": "owner/repo", "branch": "main", "github_token": "x", "iac_path": "",
    })
    assert result.ok is False
    assert "Could not reach GitHub" in result.message


@needs_db
def test_verify_fails_honestly_when_nothing_recognisable_is_found(monkeypatch):
    monkeypatch.setattr(
        conn_gh, "_fetch_terraform_files",
        lambda *a, **k: {"main.tf": 'resource "aws_iam_role" "x" { name = "x" }'},
    )
    result = conn_gh.verify({
        "repo_url": "owner/repo", "branch": "main", "github_token": "x", "iac_path": "",
    })
    assert result.ok is False
    assert "no recognised" in result.message


# ── route level: token never persisted ───────────────────────────────────


@needs_db
def test_route_never_saves_the_github_token(client, monkeypatch):
    tf = '''
    module "compute" {
      source        = "terraform-aws-modules/autoscaling/aws"
      instance_type = "t4g.large"
    }
    '''
    monkeypatch.setattr(conn_gh, "_fetch_terraform_files", lambda *a, **k: {"main.tf": tf})

    saved = {}

    def fake_save_connection(**kwargs):
        saved.update(kwargs)
        return {"id": "conn_1"}

    monkeypatch.setattr("whichcloud.api.store.save_connection", fake_save_connection)

    _as("test-owner")
    try:
        response = client.post(
            "/api/connections/verify",
            json={
                "provider": "github",
                "credentials": {
                    "repo_url": "owner/repo",
                    "branch": "main",
                    "github_token": "ghp_super_secret_value",
                    "iac_path": "terraform/",
                },
            },
        )
    finally:
        _anonymous()

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["data"]["items"]
    assert "github_token" not in saved.get("config", {})
    assert "ghp_super_secret_value" not in str(saved)
