"""Data models for Infrastructure-as-Code Multi-Environment Deployment.

Entities:
- EnvironmentConfig: Parameterized configuration defining an environment (dev, staging, prod)
- EnvironmentRecord: Persistent entity capturing live status, active deployment, lock status
- DeploymentRecord: Full lifecycle run of an IaC apply or plan (parameters snapshot, logs, metrics)
- DriftAuditRecord: Configuration drift detection event (drifted resources, attribute diffs)
- FailureIncidentRecord: Controlled failure injection & auto-recovery simulation record
- DevOpsMetrics: Quantifiable DORA & cloud metrics (MTTR, lead time, failure rate, cost gap)
- AuditLogEntry: Immutable security and operation audit trail
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EnvironmentConfig(BaseModel):
    name: str = Field(..., description="Environment identifier: dev, staging, prod")
    cloud_provider: Literal["aws", "gcp", "azure"] = "aws"
    region: str = "ap-south-1"
    vpc_cidr: str = "10.0.0.0/16"
    availability_zones: List[str] = Field(default_factory=lambda: ["ap-south-1a", "ap-south-1b"])
    enable_nat_gateway: bool = True
    single_nat_gateway: bool = True
    instance_type: str = "t4g.small"
    min_capacity: int = 1
    max_capacity: int = 2
    desired_capacity: int = 1
    db_instance_class: str = "db.t4g.micro"
    db_allocated_storage: int = 20
    db_multi_az: bool = False
    db_read_replica_count: int = 0
    db_backup_retention_period: int = 1
    db_deletion_protection: bool = False
    cache_node_type: str = "cache.t4g.micro"
    num_cache_nodes: int = 1
    cache_automatic_failover: bool = false if False else False
    s3_versioning_status: Literal["Suspended", "Enabled"] = "Suspended"
    monthly_estimated_cost: float = 48.50
    cost_breakdown: Dict[str, float] = Field(default_factory=dict)


class EnvironmentRecord(BaseModel):
    name: str
    status: Literal["HEALTHY", "DEGRADED", "DEPLOYING", "DRIFTED", "ROLLING_BACK", "FAILED"] = "HEALTHY"
    active_version: str = "v1.0.0"
    is_locked: bool = False
    lock_reason: Optional[str] = None
    parameters: EnvironmentConfig
    live_resources: Dict[str, Any] = Field(default_factory=dict)
    last_deployed_at: str = Field(default_factory=_utc_now_iso)
    last_drift_check_at: Optional[str] = None
    last_drift_status: Optional[str] = "CLEAN"
    created_at: str = Field(default_factory=_utc_now_iso)
    updated_at: str = Field(default_factory=_utc_now_iso)


class DeploymentRecord(BaseModel):
    id: str
    environment_name: str
    version: str
    triggered_by: str
    trigger_type: Literal["MANUAL", "CI_CD", "AUTO_REMEDIATION", "ROLLBACK"] = "MANUAL"
    status: Literal["PLANNING", "IN_PROGRESS", "SUCCESS", "FAILED", "ROLLED_BACK"] = "SUCCESS"
    plan_summary: Dict[str, Any] = Field(default_factory=dict)
    parameters_snapshot: Dict[str, Any] = Field(default_factory=dict)
    execution_logs: List[str] = Field(default_factory=list)
    duration_ms: int = 0
    rollback_from_id: Optional[str] = None
    created_at: str = Field(default_factory=_utc_now_iso)


class DriftItem(BaseModel):
    resource_id: str
    resource_type: str
    attribute: str
    expected_value: Any
    actual_value: Any
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "MEDIUM"


class DriftAuditRecord(BaseModel):
    id: str
    environment_name: str
    is_drifted: bool
    drift_count: int = 0
    detected_drifts: List[DriftItem] = Field(default_factory=list)
    execution_time_ms: int = 0
    detected_at: str = Field(default_factory=_utc_now_iso)
    remediation_plan: List[str] = Field(default_factory=list)


class MetricSnapshot(BaseModel):
    timestamp: str
    request_rate_rps: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    error_rate_pct: float
    cpu_utilization_pct: float
    healthy_host_count: int


class FailureIncidentRecord(BaseModel):
    id: str
    environment_name: str
    scenario_type: Literal["PRIMARY_DB_OUTAGE", "COMPUTE_NODE_CRASH", "SECURITY_GROUP_DRIFT", "AZ_NETWORK_SEVER"]
    status: Literal["ACTIVE", "MITIGATED", "RESOLVED"] = "RESOLVED"
    description: str
    recovery_action: str
    mttr_seconds: float
    pre_metrics: MetricSnapshot
    incident_metrics: MetricSnapshot
    recovery_metrics: MetricSnapshot
    created_at: str = Field(default_factory=_utc_now_iso)
    resolved_at: str = Field(default_factory=_utc_now_iso)


class DevOpsMetrics(BaseModel):
    deployment_frequency_per_day: float
    lead_time_for_changes_minutes: float
    mttr_seconds: float
    change_failure_rate_percent: float
    total_deployments: int
    successful_deployments: int
    rollback_count: int
    drift_incidence_rate_percent: float
    cost_differential_dev_vs_prod_ratio: float
    avg_plan_duration_seconds: float
    avg_apply_duration_seconds: float


class AuditLogEntry(BaseModel):
    id: str
    actor: str
    role: str
    action: str
    environment_name: Optional[str] = None
    status: str
    ip_address: str = "127.0.0.1"
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=_utc_now_iso)


# API Request/Response Models
class DeployRequest(BaseModel):
    environment_name: str = Field(..., description="Target environment: dev, staging, prod")
    parameter_overrides: Optional[Dict[str, Any]] = None
    dry_run_only: bool = False
    triggered_by: Optional[str] = "devops_engineer"
    trigger_type: Literal["MANUAL", "CI_CD", "AUTO_REMEDIATION", "ROLLBACK"] = "MANUAL"


class RollbackRequest(BaseModel):
    environment_name: str
    target_deployment_id: Optional[str] = None
    reason: str = "Automated rollback due to anomaly or manual reversion"
    triggered_by: Optional[str] = "admin"


class DriftScanRequest(BaseModel):
    environment_name: str
    auto_remediate: bool = False


class SimulateFailureRequest(BaseModel):
    environment_name: str = "prod"
    scenario_type: Literal["PRIMARY_DB_OUTAGE", "COMPUTE_NODE_CRASH", "SECURITY_GROUP_DRIFT", "AZ_NETWORK_SEVER"] = "PRIMARY_DB_OUTAGE"

