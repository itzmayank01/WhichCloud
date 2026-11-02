"""Engine for IaC Multi-Environment Deployment.

Handles:
- Orchestrating multi-environment Terraform plan & apply
- Version management and state tracking
- Reversible zero-downtime rollbacks
- Configuration drift detection & auto-remediation
- Controlled cloud failure injection & automated failover demonstration
- In-memory Terraform bundle generation
"""

from __future__ import annotations

import io
import json
import os
import time
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .iac_models import (
    AuditLogEntry,
    DeploymentRecord,
    DeployRequest,
    DriftAuditRecord,
    DriftItem,
    DriftScanRequest,
    EnvironmentConfig,
    EnvironmentRecord,
    FailureIncidentRecord,
    MetricSnapshot,
    RollbackRequest,
    SimulateFailureRequest,
)
from . import iac_store


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def execute_deployment(req: DeployRequest, actor: str = "devops_engineer", role: str = "devops") -> DeploymentRecord:
    start_t = time.perf_counter()
    env = iac_store.get_environment(req.environment_name)
    if not env:
        raise ValueError(f"Environment '{req.environment_name}' does not exist.")

    if env.is_locked:
        raise ValueError(f"Environment '{req.environment_name}' is locked: {env.lock_reason}")

    # Set status to DEPLOYING
    env.status = "DEPLOYING"
    iac_store.update_environment(env)

    # Calculate version increment
    curr_v = env.active_version.lstrip("v").split(".")
    try:
        new_patch = int(curr_v[2]) + 1
        new_version = f"v{curr_v[0]}.{curr_v[1]}.{new_patch}"
    except Exception:
        new_version = f"v1.0.{int(time.time()) % 1000}"

    # Apply parameter overrides if supplied
    params = env.parameters.model_dump()
    plan_changes = {"add": 0, "change": 0, "destroy": 0}

    if req.parameter_overrides:
        for k, v in req.parameter_overrides.items():
            if k in params:
                if params[k] != v:
                    plan_changes["change"] += 1
                params[k] = v

    # Re-calculate estimated cost if instance type or capacity changed
    new_cfg = EnvironmentConfig(**params)
    if new_cfg.name == "prod":
        new_cfg.monthly_estimated_cost = round(684.20 * (new_cfg.desired_capacity / 3.0), 2)
    elif new_cfg.name == "dev":
        new_cfg.monthly_estimated_cost = round(48.50 * (new_cfg.desired_capacity / 1.0), 2)
    elif new_cfg.name == "staging":
        new_cfg.monthly_estimated_cost = round(215.80 * (new_cfg.desired_capacity / 2.0), 2)

    # Build simulated execution logs
    logs = [
        f"[{_now_iso()}] [INFO] Starting IaC Multi-Environment deployment for '{req.environment_name}' (Target Version: {new_version})",
        f"[{_now_iso()}] [INFO] Triggered by: {actor} (Role: {role}, Trigger: {req.trigger_type})",
        f"[{_now_iso()}] [INFO] Checking out Terraform root: terraform/environments/{req.environment_name}/",
        f"[{_now_iso()}] [EXEC] terraform init -upgrade -backend=true",
        f"[{_now_iso()}] [INIT] Successfully initialized backend 's3://whichcloud-tfstate-{req.environment_name}'",
        f"[{_now_iso()}] [INIT] Verified provider plugins: hashicorp/aws ~> 5.0",
        f"[{_now_iso()}] [EXEC] terraform validate",
        f"[{_now_iso()}] [VALIDATE] Success! Configuration is valid.",
        f"[{_now_iso()}] [EXEC] terraform plan -var-file=terraform.tfvars -out=tfplan",
        f"[{_now_iso()}] [PLAN] Parameterized Diff:",
        f"             ~ module.compute.aws_autoscaling_group.app: desired_capacity = {new_cfg.desired_capacity}",
        f"             ~ module.compute.aws_launch_template.app: instance_type = \"{new_cfg.instance_type}\"",
        f"             ~ module.database.aws_db_instance.primary: multi_az = {str(new_cfg.db_multi_az).lower()}",
        f"[{_now_iso()}] [PLAN] Plan summary: {plan_changes['add']} to add, {plan_changes['change']} to change, {plan_changes['destroy']} to destroy.",
    ]

    dep_id = f"dep-{req.environment_name}-{uuid.uuid4().hex[:8]}"

    if req.dry_run_only:
        logs.append(f"[{_now_iso()}] [DRY-RUN] Dry run requested. Apply skipped.")
        duration_ms = int((time.perf_counter() - start_t) * 1000)
        env.status = "HEALTHY"
        iac_store.update_environment(env)
        dep_rec = DeploymentRecord(
            id=dep_id,
            environment_name=req.environment_name,
            version=new_version,
            triggered_by=actor,
            trigger_type=req.trigger_type,
            status="PLANNING",
            plan_summary=plan_changes,
            parameters_snapshot=new_cfg.model_dump(),
            execution_logs=logs,
            duration_ms=duration_ms,
            created_at=_now_iso(),
        )
        iac_store.add_deployment(dep_rec)
        return dep_rec

    # Execute simulated Apply
    logs.extend([
        f"[{_now_iso()}] [EXEC] terraform apply tfplan",
        f"[{_now_iso()}] [APPLY] Updating module.compute.aws_autoscaling_group.app... [id={env.live_resources.get('asg_name', 'asg-app')}]",
        f"[{_now_iso()}] [APPLY] Target group health checks passing across {new_cfg.desired_capacity} instances.",
        f"[{_now_iso()}] [APPLY] Synchronizing database parameters (storage={new_cfg.db_allocated_storage}GB, multi_az={new_cfg.db_multi_az}).",
        f"[{_now_iso()}] [APPLY] CloudWatch metric alarms active: high-cpu, alb-5xx-errors.",
        f"[{_now_iso()}] [SUCCESS] Apply complete! Resources: {plan_changes['add']} added, {plan_changes['change']} changed, {plan_changes['destroy']} destroyed.",
        f"[{_now_iso()}] [SUCCESS] State lock released. Active version updated to {new_version}.",
    ])

    duration_ms = int((time.perf_counter() - start_t) * 1000) + 1250

    # Update live state
    env.status = "HEALTHY"
    env.active_version = new_version
    env.parameters = new_cfg
    env.last_deployed_at = _now_iso()
    env.last_drift_status = "CLEAN"

    # Update live instance count
    env.live_resources["instances"] = [f"i-{req.environment_name}-node-{i+1}" for i in range(new_cfg.desired_capacity)]
    iac_store.update_environment(env)

    dep_rec = DeploymentRecord(
        id=dep_id,
        environment_name=req.environment_name,
        version=new_version,
        triggered_by=actor,
        trigger_type=req.trigger_type,
        status="SUCCESS",
        plan_summary=plan_changes,
        parameters_snapshot=new_cfg.model_dump(),
        execution_logs=logs,
        duration_ms=duration_ms,
        created_at=_now_iso(),
    )
    iac_store.add_deployment(dep_rec)

    iac_store.add_audit_log(AuditLogEntry(
        id=f"audit-{uuid.uuid4().hex[:8]}",
        actor=actor,
        role=role,
        action="DEPLOY_IAC_ENVIRONMENT",
        environment_name=req.environment_name,
        status="SUCCESS",
        details={"version": new_version, "duration_ms": duration_ms, "changes": plan_changes},
    ))

    return dep_rec


def execute_rollback(req: RollbackRequest, actor: str = "admin", role: str = "admin") -> DeploymentRecord:
    start_t = time.perf_counter()
    env = iac_store.get_environment(req.environment_name)
    if not env:
        raise ValueError(f"Environment '{req.environment_name}' does not exist.")

    history = iac_store.get_deployments(req.environment_name)
    target_dep: Optional[DeploymentRecord] = None

    if req.target_deployment_id:
        target_dep = iac_store.get_deployment(req.target_deployment_id)
    else:
        # Pick the most recent successful deployment before the active one
        for d in history:
            if d.version != env.active_version and d.status == "SUCCESS":
                target_dep = d
                break

    if not target_dep:
        raise ValueError("No eligible previous deployment found for rollback.")

    # Execute rollback
    env.status = "ROLLING_BACK"
    iac_store.update_environment(env)

    target_cfg = EnvironmentConfig(**target_dep.parameters_snapshot)
    rollback_dep_id = f"dep-rollback-{uuid.uuid4().hex[:8]}"

    logs = [
        f"[{_now_iso()}] [WARNING] INITIATING EMERGENCY ROLLBACK for '{req.environment_name}'",
        f"[{_now_iso()}] [ROLLBACK] Reverting active version {env.active_version} -> target version {target_dep.version}",
        f"[{_now_iso()}] [ROLLBACK] Triggered by: {actor} (Reason: {req.reason})",
        f"[{_now_iso()}] [EXEC] terraform plan -var-file=reverted_snapshot.tfvars",
        f"[{_now_iso()}] [PLAN] Restoring desired_capacity = {target_cfg.desired_capacity}, instance_type = \"{target_cfg.instance_type}\"",
        f"[{_now_iso()}] [EXEC] terraform apply -auto-approve",
        f"[{_now_iso()}] [ROLLBACK] Shifting ALB traffic to healthy reverted target nodes...",
        f"[{_now_iso()}] [SUCCESS] Rollback complete! Restored infrastructure state matching deployment {target_dep.id}.",
    ]

    duration_ms = int((time.perf_counter() - start_t) * 1000) + 1100

    env.status = "HEALTHY"
    env.active_version = target_dep.version
    env.parameters = target_cfg
    env.last_deployed_at = _now_iso()
    env.live_resources["instances"] = [f"i-{req.environment_name}-node-{i+1}" for i in range(target_cfg.desired_capacity)]
    iac_store.update_environment(env)

    rollback_rec = DeploymentRecord(
        id=rollback_dep_id,
        environment_name=req.environment_name,
        version=target_dep.version,
        triggered_by=actor,
        trigger_type="ROLLBACK",
        status="ROLLED_BACK",
        plan_summary={"rollback_to_version": target_dep.version},
        parameters_snapshot=target_cfg.model_dump(),
        execution_logs=logs,
        duration_ms=duration_ms,
        rollback_from_id=target_dep.id,
        created_at=_now_iso(),
    )
    iac_store.add_deployment(rollback_rec)

    iac_store.add_audit_log(AuditLogEntry(
        id=f"audit-{uuid.uuid4().hex[:8]}",
        actor=actor,
        role=role,
        action="ROLLBACK_IAC_ENVIRONMENT",
        environment_name=req.environment_name,
        status="SUCCESS",
        details={"reverted_to": target_dep.version, "reason": req.reason},
    ))

    return rollback_rec


def run_drift_detection(req: DriftScanRequest, actor: str = "devops_engineer", role: str = "devops") -> DriftAuditRecord:
    start_t = time.perf_counter()
    env = iac_store.get_environment(req.environment_name)
    if not env:
        raise ValueError(f"Environment '{req.environment_name}' does not exist.")

    # Check whether the environment currently has simulated or recorded drift
    # In cloud environments, common drift items:
    # 1. Manual security group rule opening port 22/0.0.0.0 (High severity)
    # 2. Instance count scaled manually via AWS Console without updating IaC code
    # 3. Read replica manually detached
    audit_id = f"drift-{uuid.uuid4().hex[:8]}"

    # For demonstration, simulate real cloud drift scan
    # If environment is already marked DRIFTED or randomly/flagged, return detected items
    detected_drifts: List[DriftItem] = []
    remediation_plan: List[str] = []

    # If staging or prod, test drift scenarios
    if env.status == "DRIFTED" or env.last_drift_status == "DRIFTED":
        detected_drifts = [
            DriftItem(
                resource_id="sg-0app-access",
                resource_type="aws_security_group_rule",
                attribute="ingress[22].cidr_blocks",
                expected_value=["10.0.0.0/8"],
                actual_value=["0.0.0.0/0"],
                severity="CRITICAL",
            ),
            DriftItem(
                resource_id=env.live_resources.get("asg_name", "asg-app"),
                resource_type="aws_autoscaling_group",
                attribute="desired_capacity",
                expected_value=env.parameters.desired_capacity,
                actual_value=env.parameters.desired_capacity + 1,
                severity="MEDIUM",
            ),
        ]
        remediation_plan = [
            "Revoke unauthorized ingress rule 0.0.0.0/0 on SSH port 22",
            f"Re-converge ASG desired_capacity back to {env.parameters.desired_capacity} via terraform apply",
        ]
    else:
        # Scan finds clean synchronization
        detected_drifts = []
        remediation_plan = ["Infrastructure is 100% in sync with Terraform state."]

    duration_ms = int((time.perf_counter() - start_t) * 1000) + 450
    is_drifted = len(detected_drifts) > 0

    if req.auto_remediate and is_drifted:
        # Automatically re-apply IaC desired state
        env.status = "HEALTHY"
        env.last_drift_status = "CLEAN"
        remediation_plan.append("[AUTO-REMEDIATE] Successfully re-converged drift back to IaC desired state.")
        detected_drifts = []
        is_drifted = False

    env.last_drift_check_at = _now_iso()
    env.last_drift_status = "DRIFTED" if is_drifted else "CLEAN"
    iac_store.update_environment(env)

    audit_rec = DriftAuditRecord(
        id=audit_id,
        environment_name=req.environment_name,
        is_drifted=is_drifted,
        drift_count=len(detected_drifts),
        detected_drifts=detected_drifts,
        execution_time_ms=duration_ms,
        detected_at=_now_iso(),
        remediation_plan=remediation_plan,
    )
    iac_store.add_drift_audit(audit_rec)

    iac_store.add_audit_log(AuditLogEntry(
        id=f"audit-{uuid.uuid4().hex[:8]}",
        actor=actor,
        role=role,
        action="DRIFT_DETECTION_SCAN",
        environment_name=req.environment_name,
        status="DRIFTED" if is_drifted else "CLEAN",
        details={"drift_count": len(detected_drifts), "auto_remediate": req.auto_remediate},
    ))

    return audit_rec


def run_failure_simulation(req: SimulateFailureRequest, actor: str = "admin", role: str = "admin") -> FailureIncidentRecord:
    env = iac_store.get_environment(req.environment_name)
    if not env:
        raise ValueError(f"Environment '{req.environment_name}' does not exist.")

    now = _now_iso()
    incident_id = f"inc-{uuid.uuid4().hex[:8]}"

    # Simulate realistic Cloud Failure and Auto-Recovery Scenarios
    if req.scenario_type == "PRIMARY_DB_OUTAGE":
        desc = "Simulated sudden hardware/kernel failure on RDS PostgreSQL Primary instance in AZ ap-south-1a."
        recovery_action = (
            "Multi-AZ failover mechanism detected loss of primary heartbeat. "
            "Automated promotion of standby replica in AZ ap-south-1b initiated. "
            "DNS CNAME record updated. New standby provisioned asynchronously."
        )
        mttr_seconds = 38.4
        pre_metrics = MetricSnapshot(
            timestamp=now,
            request_rate_rps=145.0,
            p50_latency_ms=14.2,
            p95_latency_ms=28.5,
            p99_latency_ms=45.0,
            error_rate_pct=0.00,
            cpu_utilization_pct=42.0,
            healthy_host_count=env.parameters.desired_capacity,
        )
        incident_metrics = MetricSnapshot(
            timestamp=now,
            request_rate_rps=112.0,
            p50_latency_ms=184.0,
            p95_latency_ms=850.0,
            p99_latency_ms=2100.0,
            error_rate_pct=4.85,
            cpu_utilization_pct=88.5,
            healthy_host_count=env.parameters.desired_capacity,
        )
        recovery_metrics = MetricSnapshot(
            timestamp=now,
            request_rate_rps=148.0,
            p50_latency_ms=15.1,
            p95_latency_ms=31.0,
            p99_latency_ms=48.2,
            error_rate_pct=0.00,
            cpu_utilization_pct=44.0,
            healthy_host_count=env.parameters.desired_capacity,
        )

    elif req.scenario_type == "COMPUTE_NODE_CRASH":
        desc = "Simulated unhandled OOM crash killing compute worker in Auto Scaling Group."
        recovery_action = (
            "ALB health check failed 3 consecutive HTTP 200 probes on /health. "
            "ASG triggered instance termination and spun up a replacement node via Launch Template. "
            "Warm-up passed and node re-entered ALB target group."
        )
        mttr_seconds = 54.2
        pre_metrics = MetricSnapshot(
            timestamp=now,
            request_rate_rps=160.0,
            p50_latency_ms=12.5,
            p95_latency_ms=24.0,
            p99_latency_ms=38.0,
            error_rate_pct=0.00,
            cpu_utilization_pct=38.0,
            healthy_host_count=env.parameters.desired_capacity,
        )
        incident_metrics = MetricSnapshot(
            timestamp=now,
            request_rate_rps=120.0,
            p50_latency_ms=88.0,
            p95_latency_ms=340.0,
            p99_latency_ms=920.0,
            error_rate_pct=2.15,
            cpu_utilization_pct=79.0,
            healthy_host_count=max(1, env.parameters.desired_capacity - 1),
        )
        recovery_metrics = MetricSnapshot(
            timestamp=now,
            request_rate_rps=162.0,
            p50_latency_ms=13.0,
            p95_latency_ms=25.2,
            p99_latency_ms=40.1,
            error_rate_pct=0.00,
            cpu_utilization_pct=39.5,
            healthy_host_count=env.parameters.desired_capacity,
        )

    elif req.scenario_type == "SECURITY_GROUP_DRIFT":
        desc = "Unauthorized manual modification opening ingress 0.0.0.0/0 on port 22 (SSH)."
        recovery_action = (
            "IaC Drift Auditor detected delta between live state and desired tfstate. "
            "Automated remediation trigger revoked wide-open ingress rule within 12 seconds."
        )
        mttr_seconds = 12.0
        pre_metrics = MetricSnapshot(
            timestamp=now,
            request_rate_rps=150.0,
            p50_latency_ms=12.0,
            p95_latency_ms=22.0,
            p99_latency_ms=35.0,
            error_rate_pct=0.00,
            cpu_utilization_pct=35.0,
            healthy_host_count=env.parameters.desired_capacity,
        )
        incident_metrics = MetricSnapshot(
            timestamp=now,
            request_rate_rps=150.0,
            p50_latency_ms=12.0,
            p95_latency_ms=22.0,
            p99_latency_ms=35.0,
            error_rate_pct=0.00,
            cpu_utilization_pct=36.0,
            healthy_host_count=env.parameters.desired_capacity,
        )
        recovery_metrics = MetricSnapshot(
            timestamp=now,
            request_rate_rps=150.0,
            p50_latency_ms=12.0,
            p95_latency_ms=22.0,
            p99_latency_ms=35.0,
            error_rate_pct=0.00,
            cpu_utilization_pct=35.0,
            healthy_host_count=env.parameters.desired_capacity,
        )

    else:  # AZ_NETWORK_SEVER
        desc = "Simulated network partition dropping all traffic to Availability Zone ap-south-1a."
        recovery_action = (
            "ALB cross-zone load balancing redirected incoming traffic away from degraded AZ. "
            "ASG auto-healed target capacity in remaining healthy AZs ap-south-1b and ap-south-1c."
        )
        mttr_seconds = 41.0
        pre_metrics = MetricSnapshot(
            timestamp=now,
            request_rate_rps=155.0,
            p50_latency_ms=13.0,
            p95_latency_ms=25.0,
            p99_latency_ms=42.0,
            error_rate_pct=0.00,
            cpu_utilization_pct=40.0,
            healthy_host_count=env.parameters.desired_capacity,
        )
        incident_metrics = MetricSnapshot(
            timestamp=now,
            request_rate_rps=105.0,
            p50_latency_ms=92.0,
            p95_latency_ms=410.0,
            p99_latency_ms=1200.0,
            error_rate_pct=3.40,
            cpu_utilization_pct=82.0,
            healthy_host_count=max(1, env.parameters.desired_capacity - 1),
        )
        recovery_metrics = MetricSnapshot(
            timestamp=now,
            request_rate_rps=156.0,
            p50_latency_ms=13.8,
            p95_latency_ms=27.1,
            p99_latency_ms=44.0,
            error_rate_pct=0.00,
            cpu_utilization_pct=42.0,
            healthy_host_count=env.parameters.desired_capacity,
        )

    incident_rec = FailureIncidentRecord(
        id=incident_id,
        environment_name=req.environment_name,
        scenario_type=req.scenario_type,
        status="RESOLVED",
        description=desc,
        recovery_action=recovery_action,
        mttr_seconds=mttr_seconds,
        pre_metrics=pre_metrics,
        incident_metrics=incident_metrics,
        recovery_metrics=recovery_metrics,
        created_at=now,
        resolved_at=_now_iso(),
    )
    iac_store.add_incident(incident_rec)

    iac_store.add_audit_log(AuditLogEntry(
        id=f"audit-{uuid.uuid4().hex[:8]}",
        actor=actor,
        role=role,
        action="CONTROLLED_FAILURE_EXPERIMENT",
        environment_name=req.environment_name,
        status="RECOVERED",
        details={"scenario": req.scenario_type, "mttr_seconds": mttr_seconds},
    ))

    return incident_rec


def generate_terraform_zip(env_name: str) -> bytes:
    """Reads all Terraform files for the given environment and modules into a downloadable ZIP."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "terraform"))
    env_dir = os.path.join(base_dir, "environments", env_name)
    modules_dir = os.path.join(base_dir, "modules")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add environment files
        if os.path.exists(env_dir):
            for root, _, files in os.walk(env_dir):
                for f in files:
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, base_dir)
                    zf.write(full_p, arcname=rel_p)

        # Add module files
        if os.path.exists(modules_dir):
            for root, _, files in os.walk(modules_dir):
                for f in files:
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, base_dir)
                    zf.write(full_p, arcname=rel_p)

    buf.seek(0)
    return buf.getvalue()


def get_terraform_files_dict(env_name: str) -> Dict[str, str]:
    """Returns {filepath: content} dictionary for preview in the UI."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "terraform"))
    env_dir = os.path.join(base_dir, "environments", env_name)
    files_map = {}

    if os.path.exists(env_dir):
        for f in os.listdir(env_dir):
            p = os.path.join(env_dir, f)
            if os.path.isfile(p):
                try:
                    with open(p, "r", encoding="utf-8") as fp:
                        files_map[f] = fp.read()
                except Exception:
                    pass
    return files_map
