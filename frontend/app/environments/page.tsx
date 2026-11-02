"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Icon } from "@iconify/react";
import {
  iacApi,
  type IacEnvironmentRecord,
  type IacDeploymentRecord,
  type IacDriftAuditRecord,
  type IacFailureIncidentRecord,
  type IacDevOpsMetrics,
} from "@/lib/api";
import { TerraformLogo } from "@/components/Logo";

export default function EnvironmentsPage() {
  const [environments, setEnvironments] = useState<IacEnvironmentRecord[]>([]);
  const [selectedEnvName, setSelectedEnvName] = useState<string>("dev");
  const [deployments, setDeployments] = useState<IacDeploymentRecord[]>([]);
  const [metrics, setMetrics] = useState<IacDevOpsMetrics | null>(null);
  const [tfFiles, setTfFiles] = useState<Record<string, string>>({});
  const [selectedTfFile, setSelectedTfFile] = useState<string>("terraform.tfvars");

  const [loading, setLoading] = useState<boolean>(true);
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);
  const [consoleLogs, setConsoleLogs] = useState<string[]>([]);
  const [driftReport, setDriftReport] = useState<IacDriftAuditRecord | null>(null);
  const [failureReport, setFailureReport] = useState<IacFailureIncidentRecord | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "matrix" | "terraform" | "deployments" | "failure-lab">("overview");

  // Load data
  const loadData = async () => {
    try {
      setLoading(true);
      const [envs, mets, deps] = await Promise.all([
        iacApi.getEnvironments(),
        iacApi.getMetrics().catch(() => null),
        iacApi.getDeployments(),
      ]);
      setEnvironments(envs);
      setMetrics(mets);
      setDeployments(deps);

      if (envs.length > 0 && !selectedEnvName) {
        setSelectedEnvName(envs[0].name);
      }
    } catch (err) {
      console.error("Failed to load IaC data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Fetch terraform files when selected environment changes
  useEffect(() => {
    if (!selectedEnvName) return;
    iacApi
      .getTerraformFiles(selectedEnvName)
      .then((res) => {
        setTfFiles(res.files || {});
        if (res.files && !res.files[selectedTfFile]) {
          const firstKey = Object.keys(res.files)[0];
          if (firstKey) setSelectedTfFile(firstKey);
        }
      })
      .catch((err) => console.error("Could not fetch terraform files", err));
  }, [selectedEnvName]);

  const selectedEnv = environments.find((e) => e.name === selectedEnvName) || environments[0];

  // Actions
  const handleDeploy = async (dryRun: boolean = false) => {
    try {
      setActionInProgress(dryRun ? "Running Terraform Plan..." : "Executing Terraform Apply...");
      setConsoleLogs([
        `[INIT] Starting ${dryRun ? "Plan" : "Apply"} workflow for environment '${selectedEnvName}'...`,
      ]);

      const dep = await iacApi.deploy({
        environment_name: selectedEnvName,
        dry_run_only: dryRun,
        parameter_overrides: {
          desired_capacity: selectedEnv.parameters.desired_capacity,
        },
      });

      setConsoleLogs(dep.execution_logs);
      await loadData();
    } catch (err: any) {
      setConsoleLogs((prev) => [...prev, `[ERROR] Deployment failed: ${err.message}`]);
    } finally {
      setActionInProgress(null);
    }
  };

  const handleRollback = async () => {
    if (!confirm(`Are you sure you want to rollback ${selectedEnvName} to the previous stable IaC version?`)) {
      return;
    }
    try {
      setActionInProgress("Executing Automated Rollback...");
      setConsoleLogs([`[ROLLBACK] Reverting '${selectedEnvName}' infrastructure...`]);

      const dep = await iacApi.rollback({
        environment_name: selectedEnvName,
        reason: "User initiated safe state reversion from WhichCloud UI",
      });

      setConsoleLogs(dep.execution_logs);
      await loadData();
    } catch (err: any) {
      setConsoleLogs((prev) => [...prev, `[ERROR] Rollback failed: ${err.message}`]);
    } finally {
      setActionInProgress(null);
    }
  };

  const handleDriftScan = async (autoRemediate: boolean = false) => {
    try {
      setActionInProgress(autoRemediate ? "Remediating Cloud Drift..." : "Scanning Cloud Drift...");
      const audit = await iacApi.detectDrift({
        environment_name: selectedEnvName,
        auto_remediate: autoRemediate,
      });
      setDriftReport(audit);
      setConsoleLogs([
        `[DRIFT-SCAN] Checked ${selectedEnvName} infrastructure state.`,
        `[DRIFT-SCAN] Detected Drifts: ${audit.drift_count}`,
        ...audit.remediation_plan.map((p) => `[PLAN] ${p}`),
      ]);
      await loadData();
    } catch (err: any) {
      setConsoleLogs((prev) => [...prev, `[ERROR] Drift scan failed: ${err.message}`]);
    } finally {
      setActionInProgress(null);
    }
  };

  const handleSimulateFailure = async (scenario: string) => {
    try {
      setActionInProgress(`Injecting Failure: ${scenario}...`);
      const result = await iacApi.simulateFailure({
        environment_name: selectedEnvName,
        scenario_type: scenario,
      });
      setFailureReport(result);
      setConsoleLogs([
        `[CHAOS-TEST] Injected failure scenario: ${scenario}`,
        `[CHAOS-TEST] Description: ${result.description}`,
        `[RECOVERY] Action: ${result.recovery_action}`,
        `[METRICS] Calculated MTTR: ${result.mttr_seconds}s`,
      ]);
      await loadData();
    } catch (err: any) {
      setConsoleLogs((prev) => [...prev, `[ERROR] Failure simulation failed: ${err.message}`]);
    } finally {
      setActionInProgress(null);
    }
  };

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 md:px-6">
      {/* Top Banner / Student Details */}
      <div className="mb-8 flex flex-col justify-between gap-4 rounded-2xl border border-line bg-panel p-6 shadow-sm md:flex-row md:items-center">
        <div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-accent/10 px-3 py-1 text-xs font-semibold text-accent">
              <TerraformLogo className="h-3.5 w-3.5" />
              DevOps & Advanced Architecture
            </span>
            <span className="rounded-full border border-line px-2.5 py-0.5 text-xs font-mono text-ink-2">
              Project ID: P74
            </span>
          </div>
          <h1 className="mt-2 text-2xl font-bold tracking-tight text-ink md:text-3xl">
            Infrastructure-as-Code Multi-Environment Deployment
          </h1>
          <p className="mt-1 text-sm text-ink-2">
            Reusable Terraform modules with parameterized differences for Development, Staging, and Production.
          </p>
        </div>

        <div className="flex flex-col items-start rounded-xl border border-line bg-canvas p-4 text-xs md:items-end">
          <div className="font-semibold text-ink">Mayank Thakur</div>
          <div className="font-mono text-ink-2">Roll / SAP: 500123412</div>
          <div className="text-ink-3">Section B3 • Cloud Application & Development</div>
        </div>
      </div>

      {/* DORA & DevOps Metrics Bar */}
      {metrics && (
        <div className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-4">
          <div className="rounded-xl border border-line bg-panel p-4">
            <div className="flex items-center justify-between text-xs text-ink-3">
              <span>Deployment Frequency</span>
              <Icon icon="lucide:activity" className="h-4 w-4 text-accent" />
            </div>
            <div className="mt-2 text-2xl font-bold text-ink">
              {metrics.deployment_frequency_per_day} <span className="text-xs font-normal text-ink-2">/ day</span>
            </div>
            <div className="mt-1 text-[11px] text-emerald-600 dark:text-emerald-400">High Performer (DORA)</div>
          </div>

          <div className="rounded-xl border border-line bg-panel p-4">
            <div className="flex items-center justify-between text-xs text-ink-3">
              <span>Mean Time to Recovery</span>
              <Icon icon="lucide:shield-check" className="h-4 w-4 text-emerald-500" />
            </div>
            <div className="mt-2 text-2xl font-bold text-ink">
              {metrics.mttr_seconds}s
            </div>
            <div className="mt-1 text-[11px] text-ink-3">Automated multi-AZ failover</div>
          </div>

          <div className="rounded-xl border border-line bg-panel p-4">
            <div className="flex items-center justify-between text-xs text-ink-3">
              <span>Dev vs Prod Cost Gap</span>
              <Icon icon="lucide:scale" className="h-4 w-4 text-amber-500" />
            </div>
            <div className="mt-2 text-2xl font-bold text-ink">
              {metrics.cost_differential_dev_vs_prod_ratio}x
            </div>
            <div className="mt-1 text-[11px] text-ink-3">\$48.50/mo vs \$684.20/mo</div>
          </div>

          <div className="rounded-xl border border-line bg-panel p-4">
            <div className="flex items-center justify-between text-xs text-ink-3">
              <span>Drift Incidence Rate</span>
              <Icon icon="lucide:git-pull-request-draft" className="h-4 w-4 text-purple-500" />
            </div>
            <div className="mt-2 text-2xl font-bold text-ink">
              {metrics.drift_incidence_rate_percent}%
            </div>
            <div className="mt-1 text-[11px] text-emerald-600 dark:text-emerald-400">Continuous reconciliation</div>
          </div>
        </div>
      )}

      {/* Environment Selector Cards */}
      <div className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-3">
        {environments.map((env) => {
          const isSelected = env.name === selectedEnvName;
          const isProd = env.name === "prod";
          const isStaging = env.name === "staging";

          return (
            <div
              key={env.name}
              onClick={() => setSelectedEnvName(env.name)}
              className={`cursor-pointer rounded-2xl border p-5 transition-all ${
                isSelected
                  ? "border-accent bg-accent/5 ring-2 ring-accent/20"
                  : "border-line bg-panel hover:border-accent/40"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span
                    className={`h-2.5 w-2.5 rounded-full ${
                      env.status === "HEALTHY"
                        ? "bg-emerald-500"
                        : env.status === "DRIFTED"
                        ? "bg-amber-500"
                        : "bg-accent"
                    }`}
                  />
                  <h3 className="text-lg font-bold capitalize text-ink">{env.name}</h3>
                </div>
                <span className="rounded-md border border-line bg-canvas px-2 py-0.5 text-xs font-mono font-medium text-ink-2">
                  {env.active_version}
                </span>
              </div>

              <div className="mt-3 flex items-baseline justify-between border-t border-line/60 pt-3">
                <div className="text-xs text-ink-3">Monthly Cost:</div>
                <div className="text-lg font-bold text-ink">
                  \${env.parameters.monthly_estimated_cost.toFixed(2)}
                  <span className="text-xs font-normal text-ink-3"> / mo</span>
                </div>
              </div>

              <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-ink-2">
                <div className="flex items-center gap-1.5">
                  <Icon icon="lucide:server" className="h-3.5 w-3.5 text-ink-3" />
                  <span>{env.parameters.instance_type}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Icon icon="lucide:database" className="h-3.5 w-3.5 text-ink-3" />
                  <span>{env.parameters.db_instance_class}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Icon icon="lucide:network" className="h-3.5 w-3.5 text-ink-3" />
                  <span>{env.parameters.availability_zones.length} AZs</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Icon icon="lucide:copy" className="h-3.5 w-3.5 text-ink-3" />
                  <span>{env.parameters.db_multi_az ? "Multi-AZ" : "Single-AZ"}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Tabs Navigation */}
      <div className="mb-6 flex border-b border-line">
        {[
          { id: "overview", label: "Environment Overview", icon: "lucide:layout-grid" },
          { id: "matrix", label: "Parameterized Differences Matrix", icon: "lucide:table" },
          { id: "terraform", label: "Terraform IaC Code", icon: "lucide:file-code-2" },
          { id: "failure-lab", label: "Controlled Failure & Recovery Lab", icon: "lucide:flame" },
          { id: "deployments", label: "Deployment History", icon: "lucide:history" },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id as any)}
            className={`flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium transition-colors ${
              activeTab === t.id
                ? "border-accent text-accent"
                : "border-transparent text-ink-2 hover:border-line hover:text-ink"
            }`}
          >
            <Icon icon={t.icon} className="h-4 w-4" />
            {t.label}
          </button>
        ))}
      </div>

      {/* ACTION BAR */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-panel p-4">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase text-ink-3">Actions for {selectedEnvName}:</span>
          <button
            onClick={() => handleDeploy(true)}
            disabled={actionInProgress !== null}
            className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-canvas px-3 py-1.5 text-xs font-medium text-ink transition-colors hover:bg-panel disabled:opacity-50"
          >
            <Icon icon="lucide:file-search" className="h-3.5 w-3.5 text-accent" />
            Terraform Plan
          </button>

          <button
            onClick={() => handleDeploy(false)}
            disabled={actionInProgress !== null}
            className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-canvas transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            <Icon icon="lucide:play" className="h-3.5 w-3.5" />
            Terraform Apply
          </button>

          <button
            onClick={() => handleDriftScan(false)}
            disabled={actionInProgress !== null}
            className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-canvas px-3 py-1.5 text-xs font-medium text-ink transition-colors hover:bg-panel disabled:opacity-50"
          >
            <Icon icon="lucide:radar" className="h-3.5 w-3.5 text-amber-500" />
            Detect Drift
          </button>

          <button
            onClick={handleRollback}
            disabled={actionInProgress !== null}
            className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-canvas px-3 py-1.5 text-xs font-medium text-amber-600 transition-colors hover:bg-amber-50 dark:hover:bg-amber-950/20 disabled:opacity-50"
          >
            <Icon icon="lucide:rotate-ccw" className="h-3.5 w-3.5" />
            Rollback
          </button>
        </div>

        <div>
          <a
            href={iacApi.getDownloadUrl(selectedEnvName)}
            download
            className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-canvas px-3 py-1.5 text-xs font-medium text-ink transition-colors hover:bg-panel"
          >
            <Icon icon="lucide:download" className="h-3.5 w-3.5 text-ink-2" />
            Download Terraform ZIP
          </a>
        </div>
      </div>

      {actionInProgress && (
        <div className="mb-6 flex items-center gap-2 rounded-xl bg-accent/10 p-3 text-xs font-medium text-accent">
          <Icon icon="lucide:loader-2" className="h-4 w-4 animate-spin" />
          <span>{actionInProgress}</span>
        </div>
      )}

      {/* TAB 1: OVERVIEW */}
      {activeTab === "overview" && selectedEnv && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Environment Specs */}
          <div className="space-y-6 lg:col-span-2">
            <div className="rounded-2xl border border-line bg-panel p-6">
              <h3 className="text-base font-semibold text-ink">Active Cloud Resources ({selectedEnv.name})</h3>
              <p className="mt-1 text-xs text-ink-3">Live resources managed by Terraform state.</p>

              <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="rounded-xl border border-line bg-canvas p-4">
                  <div className="flex items-center justify-between text-xs text-ink-3">
                    <span>VPC Network</span>
                    <Icon icon="lucide:cloud" className="h-4 w-4 text-accent" />
                  </div>
                  <div className="mt-2 font-mono text-xs font-bold text-ink">
                    {selectedEnv.live_resources.vpc_id || "vpc-default"}
                  </div>
                  <div className="mt-1 text-[11px] text-ink-3">
                    CIDR: {selectedEnv.parameters.vpc_cidr} • {selectedEnv.parameters.availability_zones.length} AZs
                  </div>
                </div>

                <div className="rounded-xl border border-line bg-canvas p-4">
                  <div className="flex items-center justify-between text-xs text-ink-3">
                    <span>Application Load Balancer</span>
                    <Icon icon="lucide:network" className="h-4 w-4 text-accent" />
                  </div>
                  <div className="mt-2 truncate font-mono text-xs font-bold text-ink" title={selectedEnv.live_resources.alb_dns}>
                    {selectedEnv.live_resources.alb_dns || "alb.amazonaws.com"}
                  </div>
                  <div className="mt-1 text-[11px] text-emerald-600 dark:text-emerald-400">
                    Health checks passing: {selectedEnv.parameters.desired_capacity}/{selectedEnv.parameters.desired_capacity}
                  </div>
                </div>

                <div className="rounded-xl border border-line bg-canvas p-4">
                  <div className="flex items-center justify-between text-xs text-ink-3">
                    <span>RDS PostgreSQL Primary</span>
                    <Icon icon="lucide:database" className="h-4 w-4 text-accent" />
                  </div>
                  <div className="mt-2 truncate font-mono text-xs font-bold text-ink" title={selectedEnv.live_resources.rds_primary}>
                    {selectedEnv.live_resources.rds_primary || "db.rds.amazonaws.com"}
                  </div>
                  <div className="mt-1 text-[11px] text-ink-3">
                    {selectedEnv.parameters.instance_type} • Multi-AZ: {selectedEnv.parameters.db_multi_az ? "Yes" : "No"} • Replicas: {selectedEnv.parameters.db_read_replica_count}
                  </div>
                </div>

                <div className="rounded-xl border border-line bg-canvas p-4">
                  <div className="flex items-center justify-between text-xs text-ink-3">
                    <span>Redis & S3 Storage</span>
                    <Icon icon="lucide:layers" className="h-4 w-4 text-accent" />
                  </div>
                  <div className="mt-2 truncate font-mono text-xs font-bold text-ink">
                    {selectedEnv.live_resources.s3_bucket || "whichcloud-artifacts"}
                  </div>
                  <div className="mt-1 text-[11px] text-ink-3">
                    Versioning: {selectedEnv.parameters.s3_versioning_status} • Cache Nodes: {selectedEnv.parameters.num_cache_nodes}
                  </div>
                </div>
              </div>
            </div>

            {/* Live Terminal Output */}
            <div className="rounded-2xl border border-line bg-[#0d1117] p-4 font-mono text-xs text-[#c9d1d9] shadow-inner">
              <div className="mb-2 flex items-center justify-between border-b border-[#30363d] pb-2 text-[11px] text-[#8b949e]">
                <div className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full bg-red-500/80" />
                  <span className="h-2.5 w-2.5 rounded-full bg-yellow-500/80" />
                  <span className="h-2.5 w-2.5 rounded-full bg-green-500/80" />
                  <span className="ml-2 font-bold text-[#f0f6fc]">Terraform Execution Console</span>
                </div>
                <span>{selectedEnvName} • bash</span>
              </div>
              <div className="max-h-60 overflow-y-auto space-y-1">
                {consoleLogs.length === 0 ? (
                  <div className="text-[#8b949e] italic">No recent execution logs. Click 'Terraform Plan', 'Terraform Apply', or 'Detect Drift' to inspect live execution.</div>
                ) : (
                  consoleLogs.map((line, idx) => (
                    <div
                      key={idx}
                      className={
                        line.includes("[ERROR]")
                          ? "text-red-400"
                          : line.includes("[SUCCESS]")
                          ? "text-emerald-400 font-semibold"
                          : line.includes("[WARNING]") || line.includes("[ROLLBACK]")
                          ? "text-amber-300"
                          : line.includes("[EXEC]")
                          ? "text-cyan-300 font-bold"
                          : "text-[#c9d1d9]"
                      }
                    >
                      {line}
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Cost & Sizing Breakdown Sidecard */}
          <div className="rounded-2xl border border-line bg-panel p-6">
            <h3 className="text-base font-semibold text-ink">Cost Distribution</h3>
            <p className="mt-1 text-xs text-ink-3">Monthly breakdown based on resolved AWS pricing.</p>

            <div className="mt-6 space-y-3">
              {Object.entries(selectedEnv.parameters.cost_breakdown).map(([category, amount]) => {
                const total = selectedEnv.parameters.monthly_estimated_cost;
                const pct = Math.round((amount / Math.max(total, 1)) * 100);

                return (
                  <div key={category} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="capitalize text-ink-2">{category}</span>
                      <span className="font-mono font-medium text-ink">\${amount.toFixed(2)} ({pct}%)</span>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-canvas">
                      <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="mt-6 rounded-xl border border-line bg-canvas p-4 text-xs text-ink-2">
              <div className="font-semibold text-ink">Architectural Rationale:</div>
              <p className="mt-1 text-ink-3">
                {selectedEnv.name === "dev"
                  ? "Uses ARM Graviton t4g.small with single-AZ RDS and shared NAT gateway. Optimized for zero waste during development."
                  : selectedEnv.name === "staging"
                  ? "Mirror-parity testing environment with 2 AZs and standby failover to validate production readiness."
                  : "Production High-Availability (HA) tier spanning 3 AZs with compute-optimized c6g instances, Multi-AZ RDS standby, and 2 read replicas."}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: PARAMETERIZED DIFFERENCES MATRIX */}
      {activeTab === "matrix" && (
        <div className="overflow-hidden rounded-2xl border border-line bg-panel shadow-sm">
          <div className="border-b border-line p-6">
            <h3 className="text-lg font-bold text-ink">Parameterized Environments Comparison</h3>
            <p className="mt-1 text-xs text-ink-3">
              Direct comparison of Terraform variable values across Development, Staging, and Production.
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-line bg-canvas text-ink-3">
                <tr>
                  <th className="px-6 py-3 font-semibold uppercase">Architectural Parameter</th>
                  <th className="px-6 py-3 font-semibold uppercase text-emerald-600 dark:text-emerald-400">Development (dev)</th>
                  <th className="px-6 py-3 font-semibold uppercase text-blue-600 dark:text-blue-400">Staging (staging)</th>
                  <th className="px-6 py-3 font-semibold uppercase text-purple-600 dark:text-purple-400">Production (prod)</th>
                  <th className="px-6 py-3 font-semibold uppercase">Cloud Rationale</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/60 text-ink-2 font-mono">
                <tr>
                  <td className="px-6 py-3.5 font-sans font-medium text-ink">VPC CIDR Block</td>
                  <td className="px-6 py-3.5">10.0.0.0/16</td>
                  <td className="px-6 py-3.5">10.2.0.0/16</td>
                  <td className="px-6 py-3.5">10.1.0.0/16</td>
                  <td className="px-6 py-3.5 font-sans text-ink-3">Strict network segregation prevents cross-env pollution</td>
                </tr>
                <tr>
                  <td className="px-6 py-3.5 font-sans font-medium text-ink">Availability Zones</td>
                  <td className="px-6 py-3.5">2 (ap-south-1a, 1b)</td>
                  <td className="px-6 py-3.5">2 (ap-south-1a, 1b)</td>
                  <td className="px-6 py-3.5">3 (ap-south-1a, 1b, 1c)</td>
                  <td className="px-6 py-3.5 font-sans text-ink-3">99.99% Multi-AZ SLA in Prod</td>
                </tr>
                <tr>
                  <td className="px-6 py-3.5 font-sans font-medium text-ink">NAT Gateway Strategy</td>
                  <td className="px-6 py-3.5">1 Shared NAT</td>
                  <td className="px-6 py-3.5">1 Shared NAT</td>
                  <td className="px-6 py-3.5 text-purple-600 dark:text-purple-400 font-semibold">3 Dedicated (1 per AZ)</td>
                  <td className="px-6 py-3.5 font-sans text-ink-3">Fault-isolated egress per AZ</td>
                </tr>
                <tr>
                  <td className="px-6 py-3.5 font-sans font-medium text-ink">Compute Instance Type</td>
                  <td className="px-6 py-3.5">t4g.small (ARM)</td>
                  <td className="px-6 py-3.5">t4g.medium</td>
                  <td className="px-6 py-3.5 text-purple-600 dark:text-purple-400 font-semibold">c6g.xlarge (Compute Opt)</td>
                  <td className="px-6 py-3.5 font-sans text-ink-3">Burst in Dev; guaranteed high CPU in Prod</td>
                </tr>
                <tr>
                  <td className="px-6 py-3.5 font-sans font-medium text-ink">Auto Scaling Capacity</td>
                  <td className="px-6 py-3.5">Min 1 / Max 2</td>
                  <td className="px-6 py-3.5">Min 2 / Max 4</td>
                  <td className="px-6 py-3.5">Min 3 / Max 12</td>
                  <td className="px-6 py-3.5 font-sans text-ink-3">Dynamic scaling under sudden traffic surges</td>
                </tr>
                <tr>
                  <td className="px-6 py-3.5 font-sans font-medium text-ink">Database Instance</td>
                  <td className="px-6 py-3.5">db.t4g.micro</td>
                  <td className="px-6 py-3.5">db.t4g.small</td>
                  <td className="px-6 py-3.5">db.m6g.large</td>
                  <td className="px-6 py-3.5 font-sans text-ink-3">Memory & IOPS headroom for heavy queries</td>
                </tr>
                <tr>
                  <td className="px-6 py-3.5 font-sans font-medium text-ink">RDS Multi-AZ Standby</td>
                  <td className="px-6 py-3.5 text-red-500 font-semibold">false</td>
                  <td className="px-6 py-3.5 text-emerald-600 dark:text-emerald-400">true</td>
                  <td className="px-6 py-3.5 text-emerald-600 dark:text-emerald-400 font-semibold">true (Sync standby)</td>
                  <td className="px-6 py-3.5 font-sans text-ink-3">Sub-60s zero data loss failover</td>
                </tr>
                <tr>
                  <td className="px-6 py-3.5 font-sans font-medium text-ink">Read Replicas</td>
                  <td className="px-6 py-3.5">0</td>
                  <td className="px-6 py-3.5">1</td>
                  <td className="px-6 py-3.5 text-purple-600 dark:text-purple-400 font-semibold">2 (cross-AZ)</td>
                  <td className="px-6 py-3.5 font-sans text-ink-3">Offloads read queries and analytics</td>
                </tr>
                <tr>
                  <td className="px-6 py-3.5 font-sans font-medium text-ink">Backup Retention Period</td>
                  <td className="px-6 py-3.5">1 day</td>
                  <td className="px-6 py-3.5">7 days</td>
                  <td className="px-6 py-3.5 text-purple-600 dark:text-purple-400 font-semibold">30 days (PITR)</td>
                  <td className="px-6 py-3.5 font-sans text-ink-3">Disaster recovery and compliance</td>
                </tr>
                <tr>
                  <td className="px-6 py-3.5 font-sans font-medium text-ink">Deletion Protection</td>
                  <td className="px-6 py-3.5 text-ink-3">false</td>
                  <td className="px-6 py-3.5 text-ink-3">false</td>
                  <td className="px-6 py-3.5 text-emerald-600 dark:text-emerald-400 font-semibold">true</td>
                  <td className="px-6 py-3.5 font-sans text-ink-3">Guards against accidental terraform destroy</td>
                </tr>
                <tr>
                  <td className="px-6 py-3.5 font-sans font-medium text-ink">Monthly Cost</td>
                  <td className="px-6 py-3.5 font-bold text-ink">\$48.50</td>
                  <td className="px-6 py-3.5 font-bold text-ink">\$215.80</td>
                  <td className="px-6 py-3.5 font-bold text-accent">\$684.20</td>
                  <td className="px-6 py-3.5 font-sans text-ink-3">14x cost difference reflecting reliability SLA</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 3: TERRAFORM IAC CODE */}
      {activeTab === "terraform" && (
        <div className="overflow-hidden rounded-2xl border border-line bg-panel shadow-sm">
          <div className="flex flex-wrap items-center justify-between border-b border-line px-6 py-4">
            <div>
              <h3 className="text-base font-semibold text-ink">
                Terraform Configuration: terraform/environments/{selectedEnvName}/
              </h3>
              <p className="text-xs text-ink-3">Parameterized HCL code calling reusable modules.</p>
            </div>

            <div className="flex gap-2">
              {Object.keys(tfFiles).map((fname) => (
                <button
                  key={fname}
                  onClick={() => setSelectedTfFile(fname)}
                  className={`rounded-lg px-3 py-1.5 font-mono text-xs font-medium transition-colors ${
                    selectedTfFile === fname
                      ? "bg-accent text-canvas"
                      : "border border-line bg-canvas text-ink-2 hover:text-ink"
                  }`}
                >
                  {fname}
                </button>
              ))}
            </div>
          </div>

          <div className="bg-[#0d1117] p-4">
            <pre className="max-h-[500px] overflow-auto font-mono text-xs leading-relaxed text-[#c9d1d9]">
              {tfFiles[selectedTfFile] || "// Loading Terraform files..."}
            </pre>
          </div>
        </div>
      )}

      {/* TAB 4: CONTROLLED FAILURE & RECOVERY LAB */}
      {activeTab === "failure-lab" && (
        <div className="space-y-6">
          <div className="rounded-2xl border border-line bg-panel p-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-ink">Controlled Cloud Failure & Recovery Simulation</h3>
                <p className="mt-1 text-xs text-ink-3">
                  Demonstrates automated recovery, health monitoring, and metrics before, during, and after an incident.
                </p>
              </div>
              <span className="rounded-full bg-amber-500/10 px-3 py-1 text-xs font-semibold text-amber-600 dark:text-amber-400">
                Resilience Testing
              </span>
            </div>

            <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-3">
              <div className="rounded-xl border border-line bg-canvas p-4">
                <h4 className="font-semibold text-ink">Primary Database Outage</h4>
                <p className="mt-1 text-xs text-ink-3">
                  Simulates sudden crash of RDS Primary in AZ-a; tests automated Multi-AZ failover to standby replica in AZ-b.
                </p>
                <button
                  onClick={() => handleSimulateFailure("PRIMARY_DB_OUTAGE")}
                  disabled={actionInProgress !== null}
                  className="mt-4 w-full rounded-lg bg-accent px-3 py-2 text-xs font-semibold text-canvas transition-opacity hover:opacity-90 disabled:opacity-50"
                >
                  Inject DB Outage
                </button>
              </div>

              <div className="rounded-xl border border-line bg-canvas p-4">
                <h4 className="font-semibold text-ink">Compute Worker Crash</h4>
                <p className="mt-1 text-xs text-ink-3">
                  Simulates unhandled worker crash; ALB health checks fail and Auto Scaling Group provisions replacement node.
                </p>
                <button
                  onClick={() => handleSimulateFailure("COMPUTE_NODE_CRASH")}
                  disabled={actionInProgress !== null}
                  className="mt-4 w-full rounded-lg bg-accent px-3 py-2 text-xs font-semibold text-canvas transition-opacity hover:opacity-90 disabled:opacity-50"
                >
                  Inject Node Crash
                </button>
              </div>

              <div className="rounded-xl border border-line bg-canvas p-4">
                <h4 className="font-semibold text-ink">Security Group Drift</h4>
                <p className="mt-1 text-xs text-ink-3">
                  Simulates unauthorized manual modification opening port 22 to 0.0.0.0/0; drift detection auto-revokes.
                </p>
                <button
                  onClick={() => handleSimulateFailure("SECURITY_GROUP_DRIFT")}
                  disabled={actionInProgress !== null}
                  className="mt-4 w-full rounded-lg bg-accent px-3 py-2 text-xs font-semibold text-canvas transition-opacity hover:opacity-90 disabled:opacity-50"
                >
                  Inject Drift Anomaly
                </button>
              </div>
            </div>
          </div>

          {/* Metric Comparison Before, During, After */}
          {failureReport && (
            <div className="rounded-2xl border border-line bg-panel p-6 shadow-sm">
              <div className="flex items-center justify-between border-b border-line pb-4">
                <div>
                  <h4 className="text-base font-bold text-ink">
                    Incident Report: {failureReport.scenario_type}
                  </h4>
                  <p className="text-xs text-ink-3">{failureReport.description}</p>
                </div>
                <div className="text-right">
                  <div className="text-xs text-ink-3">Mean Time To Recovery</div>
                  <div className="font-mono text-xl font-bold text-emerald-600 dark:text-emerald-400">
                    {failureReport.mttr_seconds}s
                  </div>
                </div>
              </div>

              <div className="mt-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-xs text-emerald-800 dark:text-emerald-300">
                <strong>Recovery Action Executed:</strong> {failureReport.recovery_action}
              </div>

              <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-3">
                {/* BEFORE */}
                <div className="rounded-xl border border-line bg-canvas p-4">
                  <div className="flex items-center justify-between text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                    <span>1. Before Incident (Baseline)</span>
                    <Icon icon="lucide:check-circle" className="h-4 w-4" />
                  </div>
                  <div className="mt-3 space-y-2 text-xs font-mono">
                    <div className="flex justify-between text-ink-2">
                      <span>Throughput:</span>
                      <span className="font-bold text-ink">{failureReport.pre_metrics.request_rate_rps} rps</span>
                    </div>
                    <div className="flex justify-between text-ink-2">
                      <span>Latency (p50):</span>
                      <span className="text-ink">{failureReport.pre_metrics.p50_latency_ms} ms</span>
                    </div>
                    <div className="flex justify-between text-ink-2">
                      <span>Latency (p95):</span>
                      <span className="text-ink">{failureReport.pre_metrics.p95_latency_ms} ms</span>
                    </div>
                    <div className="flex justify-between text-ink-2">
                      <span>Error Rate:</span>
                      <span className="text-emerald-600 font-bold">{failureReport.pre_metrics.error_rate_pct}%</span>
                    </div>
                    <div className="flex justify-between text-ink-2">
                      <span>CPU Utilization:</span>
                      <span className="text-ink">{failureReport.pre_metrics.cpu_utilization_pct}%</span>
                    </div>
                  </div>
                </div>

                {/* DURING */}
                <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-4">
                  <div className="flex items-center justify-between text-xs font-semibold text-red-600 dark:text-red-400">
                    <span>2. During Incident (Degraded)</span>
                    <Icon icon="lucide:alert-triangle" className="h-4 w-4" />
                  </div>
                  <div className="mt-3 space-y-2 text-xs font-mono">
                    <div className="flex justify-between text-ink-2">
                      <span>Throughput:</span>
                      <span className="font-bold text-ink">{failureReport.incident_metrics.request_rate_rps} rps</span>
                    </div>
                    <div className="flex justify-between text-ink-2">
                      <span>Latency (p50):</span>
                      <span className="text-red-500 font-bold">{failureReport.incident_metrics.p50_latency_ms} ms</span>
                    </div>
                    <div className="flex justify-between text-ink-2">
                      <span>Latency (p95):</span>
                      <span className="text-red-500 font-bold">{failureReport.incident_metrics.p95_latency_ms} ms</span>
                    </div>
                    <div className="flex justify-between text-ink-2">
                      <span>Error Rate:</span>
                      <span className="text-red-600 font-bold">{failureReport.incident_metrics.error_rate_pct}%</span>
                    </div>
                    <div className="flex justify-between text-ink-2">
                      <span>CPU Utilization:</span>
                      <span className="text-red-500">{failureReport.incident_metrics.cpu_utilization_pct}%</span>
                    </div>
                  </div>
                </div>

                {/* AFTER */}
                <div className="rounded-xl border border-line bg-canvas p-4">
                  <div className="flex items-center justify-between text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                    <span>3. Post Recovery (Restored)</span>
                    <Icon icon="lucide:shield-check" className="h-4 w-4" />
                  </div>
                  <div className="mt-3 space-y-2 text-xs font-mono">
                    <div className="flex justify-between text-ink-2">
                      <span>Throughput:</span>
                      <span className="font-bold text-ink">{failureReport.recovery_metrics.request_rate_rps} rps</span>
                    </div>
                    <div className="flex justify-between text-ink-2">
                      <span>Latency (p50):</span>
                      <span className="text-ink">{failureReport.recovery_metrics.p50_latency_ms} ms</span>
                    </div>
                    <div className="flex justify-between text-ink-2">
                      <span>Latency (p95):</span>
                      <span className="text-ink">{failureReport.recovery_metrics.p95_latency_ms} ms</span>
                    </div>
                    <div className="flex justify-between text-ink-2">
                      <span>Error Rate:</span>
                      <span className="text-emerald-600 font-bold">{failureReport.recovery_metrics.error_rate_pct}%</span>
                    </div>
                    <div className="flex justify-between text-ink-2">
                      <span>CPU Utilization:</span>
                      <span className="text-ink">{failureReport.recovery_metrics.cpu_utilization_pct}%</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 5: DEPLOYMENT HISTORY */}
      {activeTab === "deployments" && (
        <div className="overflow-hidden rounded-2xl border border-line bg-panel shadow-sm">
          <div className="border-b border-line p-6">
            <h3 className="text-base font-semibold text-ink">Deployment & Rollback History</h3>
            <p className="mt-1 text-xs text-ink-3">Complete audit trail of all IaC plan and apply runs.</p>
          </div>

          <div className="divide-y divide-line/60">
            {deployments.map((dep) => (
              <div key={dep.id} className="p-4 hover:bg-canvas/50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                        dep.status === "SUCCESS"
                          ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                          : dep.status === "ROLLED_BACK"
                          ? "bg-amber-500/10 text-amber-600 dark:text-amber-400"
                          : "bg-blue-500/10 text-blue-600"
                      }`}
                    >
                      {dep.status}
                    </span>
                    <span className="font-mono text-xs font-bold text-ink">{dep.id}</span>
                    <span className="capitalize text-xs text-ink-2">({dep.environment_name})</span>
                  </div>

                  <div className="font-mono text-xs text-ink-3">
                    Version: <strong className="text-ink">{dep.version}</strong> • Duration: {dep.duration_ms}ms
                  </div>
                </div>

                <div className="mt-2 flex items-center justify-between text-xs text-ink-3">
                  <div>
                    Trigger: <span className="font-medium text-ink-2">{dep.trigger_type}</span> by{" "}
                    <span className="font-medium text-ink-2">{dep.triggered_by}</span>
                  </div>
                  <div>{new Date(dep.created_at).toLocaleString()}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </main>
  );
}
