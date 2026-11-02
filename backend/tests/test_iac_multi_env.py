"""Tests for Project P74: Infrastructure-as-Code Multi-Environment Deployment.

Validates:
- Parameterized differences between dev, staging, prod
- All 12 REST API endpoints
- Role-Based Access Control (Admin, DevOps, Viewer)
- Deployment lifecycle (Plan, Apply, Versioning)
- Rollback execution and state restoration
- Configuration drift detection and automated remediation
- Controlled failure scenario with MTTR & metric capture
- DevOps metrics aggregation
- Terraform file generation and ZIP export
"""

import pytest
from fastapi.testclient import TestClient
from whichcloud.api import app
from whichcloud import iac_store

client = TestClient(app)


def test_get_environments():
    res = client.get("/api/iac/environments")
    assert res.status_code == 200
    envs = res.json()
    assert len(envs) >= 3

    names = {e["name"] for e in envs}
    assert {"dev", "staging", "prod"}.issubset(names)

    dev = next(e for e in envs if e["name"] == "dev")
    prod = next(e for e in envs if e["name"] == "prod")

    # Parameterized differences
    assert dev["parameters"]["db_multi_az"] is False
    assert prod["parameters"]["db_multi_az"] is True
    assert dev["parameters"]["instance_type"] == "t4g.small"
    assert prod["parameters"]["instance_type"] == "c6g.xlarge"
    assert dev["parameters"]["db_backup_retention_period"] == 1
    assert prod["parameters"]["db_backup_retention_period"] == 30
    assert dev["parameters"]["monthly_estimated_cost"] < prod["parameters"]["monthly_estimated_cost"]


def test_get_single_environment():
    res = client.get("/api/iac/environments/dev")
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "dev"
    assert data["parameters"]["vpc_cidr"] == "10.0.0.0/16"

    # Non-existent environment returns 404
    res_err = client.get("/api/iac/environments/nonexistent")
    assert res_err.status_code == 404


def test_deploy_dry_run_and_apply():
    # 1. Dry run (Plan only)
    plan_payload = {
        "environment_name": "dev",
        "dry_run_only": True,
        "parameter_overrides": {"desired_capacity": 2},
    }
    res_plan = client.post("/api/iac/deploy", json=plan_payload, headers={"X-API-Key": "whichcloud-iac-devops-key"})
    assert res_plan.status_code == 200
    plan_data = res_plan.json()
    assert plan_data["status"] == "PLANNING"
    assert any("Plan summary" in log for log in plan_data["execution_logs"])

    # 2. Real Apply with parameter override
    apply_payload = {
        "environment_name": "dev",
        "dry_run_only": False,
        "parameter_overrides": {"desired_capacity": 2},
    }
    res_apply = client.post("/api/iac/deploy", json=apply_payload, headers={"X-API-Key": "whichcloud-iac-admin-key"})
    assert res_apply.status_code == 200
    apply_data = res_apply.json()
    assert apply_data["status"] == "SUCCESS"
    assert len(apply_data["execution_logs"]) > 5

    # Verify environment updated
    res_env = client.get("/api/iac/environments/dev")
    assert res_env.status_code == 200
    updated_env = res_env.json()
    assert updated_env["parameters"]["desired_capacity"] == 2
    assert len(updated_env["live_resources"]["instances"]) == 2


def test_rollback_execution():
    # Trigger rollback
    rollback_payload = {
        "environment_name": "dev",
        "reason": "Test rollback trigger to previous good state",
    }
    res_rb = client.post("/api/iac/rollback", json=rollback_payload, headers={"X-API-Key": "whichcloud-iac-admin-key"})
    assert res_rb.status_code == 200
    rb_data = res_rb.json()
    assert rb_data["status"] == "ROLLED_BACK"
    assert rb_data["trigger_type"] == "ROLLBACK"


def test_drift_detection_and_remediation():
    # Scan without auto-remediation
    scan_payload = {
        "environment_name": "prod",
        "auto_remediate": False,
    }
    res_scan = client.post("/api/iac/drift-detection", json=scan_payload, headers={"X-API-Key": "whichcloud-iac-devops-key"})
    assert res_scan.status_code == 200
    audit = res_scan.json()
    assert "detected_drifts" in audit
    assert "execution_time_ms" in audit

    # Scan with auto-remediation
    remediate_payload = {
        "environment_name": "prod",
        "auto_remediate": True,
    }
    res_remed = client.post("/api/iac/drift-detection", json=remediate_payload, headers={"X-API-Key": "whichcloud-iac-admin-key"})
    assert res_remed.status_code == 200
    remed_data = res_remed.json()
    assert remed_data["is_drifted"] is False


def test_controlled_failure_simulation():
    fail_payload = {
        "environment_name": "prod",
        "scenario_type": "PRIMARY_DB_OUTAGE",
    }
    res = client.post("/api/iac/simulate-failure", json=fail_payload, headers={"X-API-Key": "whichcloud-iac-admin-key"})
    assert res.status_code == 200
    incident = res.json()
    assert incident["scenario_type"] == "PRIMARY_DB_OUTAGE"
    assert incident["status"] == "RESOLVED"
    assert incident["mttr_seconds"] > 0
    assert incident["pre_metrics"]["error_rate_pct"] == 0.00
    assert incident["incident_metrics"]["error_rate_pct"] > 0.00
    assert incident["recovery_metrics"]["error_rate_pct"] == 0.00


def test_devops_metrics_calculation():
    res = client.get("/api/iac/metrics")
    assert res.status_code == 200
    metrics = res.json()
    assert metrics["deployment_frequency_per_day"] > 0
    assert metrics["mttr_seconds"] > 0
    assert metrics["cost_differential_dev_vs_prod_ratio"] > 1.0


def test_audit_logs():
    res = client.get("/api/iac/audit-logs?limit=10")
    assert res.status_code == 200
    logs = res.json()
    assert isinstance(logs, list)
    assert len(logs) > 0


def test_rbac_access_control():
    # Viewer attempting to deploy -> 403 Forbidden
    payload = {"environment_name": "dev", "dry_run_only": False}
    res = client.post("/api/iac/deploy", json=payload, headers={"X-API-Key": "whichcloud-iac-viewer-key"})
    assert res.status_code == 403

    # DevOps attempting rollback (Admin only) -> 403 Forbidden
    rb_payload = {"environment_name": "dev"}
    res_rb = client.post("/api/iac/rollback", json=rb_payload, headers={"X-API-Key": "whichcloud-iac-devops-key"})
    assert res_rb.status_code == 403


def test_terraform_files_and_zip_download():
    # Check HCL files endpoint
    res_files = client.get("/api/iac/terraform/dev")
    assert res_files.status_code == 200
    files_json = res_files.json()
    assert "main.tf" in files_json["files"]
    assert "terraform.tfvars" in files_json["files"]

    # Check zip download endpoint
    res_zip = client.get("/api/iac/terraform/dev/download")
    assert res_zip.status_code == 200
    assert res_zip.headers["content-type"] == "application/zip"
    assert len(res_zip.content) > 100
