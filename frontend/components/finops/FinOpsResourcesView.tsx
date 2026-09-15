"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { Icon } from "@iconify/react";
import { CurrencyCode, formatCurrency } from "@/lib/currency";
import { api } from "@/lib/api";

export interface CloudResource {
  id: string;
  name: string;
  service: string;
  type: string;
  category: "compute" | "database" | "storage" | "networking" | "cache";
  region: string;
  monthly_usd: number;
  utilization_pct: number;
  status: "healthy" | "idle" | "overprovisioned" | "warning";
  tags: {
    env: string;
    team: string;
    attached_to?: string;
    [key: string]: string | undefined;
  };
}

const DEFAULT_RESOURCES: Record<string, CloudResource[]> = {
  aws: [
    {
      id: "i-084920b9101f2",
      name: "eks-prod-worker-01",
      service: "Amazon EC2",
      type: "m5.2xlarge (8 vCPU, 32 GB)",
      category: "compute",
      region: "us-east-1a",
      monthly_usd: 280.32,
      utilization_pct: 18,
      status: "overprovisioned",
      tags: { env: "prod", team: "Core Infra" },
    },
    {
      id: "i-091a18bc0091b",
      name: "eks-prod-worker-02",
      service: "Amazon EC2",
      type: "m5.2xlarge (8 vCPU, 32 GB)",
      category: "compute",
      region: "us-east-1b",
      monthly_usd: 280.32,
      utilization_pct: 22,
      status: "overprovisioned",
      tags: { env: "prod", team: "Core Infra" },
    },
    {
      id: "i-0af81726bb109",
      name: "payment-api-worker-01",
      service: "Amazon ECS (Fargate)",
      type: "2 vCPU, 4 GB",
      category: "compute",
      region: "us-east-1",
      monthly_usd: 148.20,
      utilization_pct: 64,
      status: "healthy",
      tags: { env: "prod", team: "Payments" },
    },
    {
      id: "rds-aurora-cluster-prod",
      name: "aurora-pg-cluster-writer",
      service: "Amazon RDS",
      type: "db.r6g.2xlarge (Aurora PostgreSQL)",
      category: "database",
      region: "us-east-1",
      monthly_usd: 1180.0,
      utilization_pct: 42,
      status: "healthy",
      tags: { env: "prod", team: "Database" },
    },
    {
      id: "rds-aurora-cluster-ro-01",
      name: "aurora-pg-cluster-reader",
      service: "Amazon RDS",
      type: "db.r6g.2xlarge (Aurora PostgreSQL)",
      category: "database",
      region: "us-east-1b",
      monthly_usd: 1180.0,
      utilization_pct: 28,
      status: "warning",
      tags: { env: "prod", team: "Database" },
    },
    {
      id: "arn:aws:s3:::prod-customer-assets",
      name: "prod-customer-assets",
      service: "Amazon S3",
      type: "S3 Standard (14.2 TB)",
      category: "storage",
      region: "us-east-1",
      monthly_usd: 326.6,
      utilization_pct: 88,
      status: "warning",
      tags: { env: "prod", team: "Media" },
    },
    {
      id: "vol-084129b8c19a28f",
      name: "unattached-scratch-volume",
      service: "Amazon EBS",
      type: "gp3 (500 GB)",
      category: "storage",
      region: "us-east-1a",
      monthly_usd: 40.0,
      utilization_pct: 0,
      status: "idle",
      tags: { env: "staging", team: "QA" },
    },
    {
      id: "nat-0a8174f82810cd02",
      name: "prod-nat-gateway-us-east-1a",
      service: "Amazon VPC",
      type: "NAT Gateway (12.4 TB processed)",
      category: "networking",
      region: "us-east-1a",
      monthly_usd: 588.0,
      utilization_pct: 75,
      status: "warning",
      tags: { env: "prod", team: "Networking" },
    },
    {
      id: "alb-production-public-01",
      name: "prod-ingress-alb",
      service: "Elastic Load Balancing",
      type: "Application Load Balancer",
      category: "networking",
      region: "us-east-1",
      monthly_usd: 88.5,
      utilization_pct: 55,
      status: "healthy",
      tags: { env: "prod", team: "Core Infra" },
    },
    {
      id: "redis-cache-prod-cluster",
      name: "redis-session-cache",
      service: "Amazon ElastiCache",
      type: "cache.m6g.large (2 nodes)",
      category: "cache",
      region: "us-east-1",
      monthly_usd: 198.4,
      utilization_pct: 35,
      status: "healthy",
      tags: { env: "prod", team: "Session Team" },
    },
  ],
  azure: [
    {
      id: "/subscriptions/.../aks-prod-01",
      name: "aks-production-nodes",
      service: "Azure Kubernetes Service",
      type: "Standard_D4ds_v5 (4 nodes)",
      category: "compute",
      region: "eastus",
      monthly_usd: 1680.0,
      utilization_pct: 28,
      status: "overprovisioned",
      tags: { env: "prod", team: "Platform" },
    },
    {
      id: "/subscriptions/.../sqldb-prod",
      name: "sqldb-enterprise-core",
      service: "Azure SQL Database",
      type: "Business Critical 4 vCore",
      category: "database",
      region: "eastus",
      monthly_usd: 1820.0,
      utilization_pct: 38,
      status: "overprovisioned",
      tags: { env: "prod", team: "DBA" },
    },
    {
      id: "/subscriptions/.../stgprodcool",
      name: "stgproductionblob",
      service: "Azure Blob Storage",
      type: "Hot Tier (8.5 TB)",
      category: "storage",
      region: "eastus",
      monthly_usd: 380.5,
      utilization_pct: 85,
      status: "warning",
      tags: { env: "prod", team: "Analytics" },
    },
    {
      id: "/subscriptions/.../appgw-v2",
      name: "appgw-ingress-prod",
      service: "Application Gateway",
      type: "WAF_v2 Standard",
      category: "networking",
      region: "eastus",
      monthly_usd: 248.5,
      utilization_pct: 42,
      status: "healthy",
      tags: { env: "prod", team: "SecOps" },
    },
    {
      id: "/subscriptions/.../redis-p1",
      name: "redis-cache-cluster",
      service: "Azure Cache for Redis",
      type: "Premium P1",
      category: "cache",
      region: "eastus",
      monthly_usd: 412.0,
      utilization_pct: 22,
      status: "warning",
      tags: { env: "prod", team: "Backend" },
    },
  ],
  gcp: [
    {
      id: "projects/prod-981/gke-nodes",
      name: "gke-autopilot-cluster",
      service: "Google Kubernetes Engine",
      type: "e2-standard-4 (Autopilot)",
      category: "compute",
      region: "us-central1",
      monthly_usd: 1540.0,
      utilization_pct: 32,
      status: "overprovisioned",
      tags: { env: "prod", team: "Platform" },
    },
    {
      id: "projects/prod-981/csql-pg",
      name: "cloud-sql-postgres",
      service: "Cloud SQL",
      type: "db-custom-8-32 (32 GB RAM)",
      category: "database",
      region: "us-central1",
      monthly_usd: 1780.0,
      utilization_pct: 24,
      status: "overprovisioned",
      tags: { env: "prod", team: "Data" },
    },
    {
      id: "bkt-prod-assets-981",
      name: "bkt-prod-analytics-exports",
      service: "Cloud Storage",
      type: "Standard Bucket (11 TB)",
      category: "storage",
      region: "us-central1",
      monthly_usd: 295.0,
      utilization_pct: 90,
      status: "healthy",
      tags: { env: "prod", team: "BI" },
    },
    {
      id: "glb-ingress-us-central1",
      name: "global-http-loadbalancer",
      service: "Cloud Load Balancing",
      type: "External HTTP(S) LB",
      category: "networking",
      region: "us-central1",
      monthly_usd: 185.0,
      utilization_pct: 55,
      status: "healthy",
      tags: { env: "prod", team: "DevOps" },
    },
  ],
  github: [
    {
      id: "gh-repo-infra-main",
      name: "acme-corp/infra",
      service: "Terraform Module",
      type: "AWS Multi-AZ VPC + EKS",
      category: "compute",
      region: "us-east-1",
      monthly_usd: 3950.0,
      utilization_pct: 38,
      status: "overprovisioned",
      tags: { env: "prod", team: "Core Infra" },
    },
  ],
};

interface FinOpsResourcesViewProps {
  provider: string;
  currency?: CurrencyCode;
  accountId?: string;
  onResourceAction?: () => void;
}

interface ActionModalState {
  resource: CloudResource;
  actionType: string;
  title: string;
  command: string;
  savingsUsd: number;
}

export function FinOpsResourcesView({
  provider = "aws",
  currency = "USD",
  accountId = "demo",
  onResourceAction,
}: FinOpsResourcesViewProps) {
  const { getToken } = useAuth();
  const p = provider.toLowerCase();
  const rawList = DEFAULT_RESOURCES[p] || DEFAULT_RESOURCES.aws;

  const [resources, setResources] = useState<CloudResource[]>(rawList);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [selectedStatus, setSelectedStatus] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  // Modal State for Individual Deletion & Stopping
  const [confirmModal, setConfirmModal] = useState<ActionModalState | null>(null);
  const [executingAction, setExecutingAction] = useState(false);
  const [copiedCommand, setCopiedCommand] = useState(false);

  // Modal State for Delete All Resources with Keyboard Confirmation
  const [showDeleteAllModal, setShowDeleteAllModal] = useState(false);
  const [confirmText, setConfirmText] = useState("");
  const [executingDeleteAll, setExecutingDeleteAll] = useState(false);
  const [deleteAllActions, setDeleteAllActions] = useState<Array<{
    resource: string;
    type: string;
    action: string;
    savings: number;
    cmd: string;
  }> | null>(null);

  const isNukeConfirmed =
    confirmText.trim().toLowerCase() === "delete all resources" ||
    confirmText.trim().toLowerCase() === "confirm";

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const token = await getToken();
        const res = await api.finopsResources(provider, accountId, token ?? undefined);
        if (mounted && res?.resources && res.resources.length > 0) {
          setResources(res.resources);
        }
      } catch (err) {
        console.error("Live resources fetch error:", err);
      }
    })();

    return () => {
      mounted = false;
    };
  }, [provider, accountId, getToken]);

  // Listen for global trigger event from top navbar
  useEffect(() => {
    const handleTriggerModal = () => {
      setShowDeleteAllModal(true);
      setConfirmText("");
      setDeleteAllActions(null);
    };
    window.addEventListener("open-delete-all-resources-modal", handleTriggerModal);
    return () => window.removeEventListener("open-delete-all-resources-modal", handleTriggerModal);
  }, []);

  const openActionModal = (
    res: CloudResource,
    actionType: string,
    title: string,
    command: string,
    savingsUsd: number
  ) => {
    setConfirmModal({
      resource: res,
      actionType,
      title,
      command,
      savingsUsd,
    });
    setCopiedCommand(false);
  };

  const handleExecuteDeleteAll = async (isDryRun = false) => {
    if (!isNukeConfirmed) return;
    setExecutingDeleteAll(true);
    try {
      const token = await getToken();
      const res = await api.finopsDeleteAllResources({
        provider,
        account_id: accountId,
        confirm_phrase: confirmText.trim(),
        dry_run: isDryRun,
      }, token ?? undefined);

      if (res.ok) {
        if (isDryRun) {
          setActionNotice(
            `Dry Run Completed: Simulated deletion of ${res.deleted_count || resources.length} resources. Potential savings: ${formatCurrency(
              res.total_savings_usd || totalCost,
              currency,
              2
            )}/mo.`
          );
          if (res.actions) {
            setDeleteAllActions(res.actions);
          }
        } else {
          setResources([]);
          setShowDeleteAllModal(false);
          setConfirmText("");
          setActionNotice(
            `Teardown Complete: Successfully deleted all ${res.deleted_count || resources.length} active resources from account ${accountId}. Eliminated ${formatCurrency(
              res.total_savings_usd || totalCost,
              currency,
              2
            )}/mo in cloud waste.`
          );
          onResourceAction?.();
        }
      } else {
        setActionNotice(`Delete All Notice: ${res.message}`);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      setActionNotice(`Failed to execute deletion: ${msg}`);
    } finally {
      setExecutingDeleteAll(false);
    }
  };


  const handleExecuteAction = async (isDryRun = false) => {
    if (!confirmModal) return;
    setExecutingAction(true);
    try {
      const token = await getToken();
      const res = await api.finopsResourceAction({
        provider,
        action: confirmModal.actionType,
        resource_id: confirmModal.resource.id,
        region: confirmModal.resource.region,
        dry_run: isDryRun,
      }, token ?? undefined);

      if (res.ok) {
        if (isDryRun) {
          setActionNotice(
            `Dry Run Validation Passed: ${res.message || "AWS confirmed your credentials have permission to execute this operation."}`
          );
        } else {
          if (
            confirmModal.actionType.startsWith("delete") ||
            confirmModal.actionType === "terminate_instance" ||
            confirmModal.actionType === "release_eip"
          ) {
            setResources((prev) => prev.filter((r) => r.id !== confirmModal.resource.id));
          } else if (confirmModal.actionType === "stop_instance") {
            setResources((prev) =>
              prev.map((r) =>
                r.id === confirmModal.resource.id
                  ? { ...r, status: "idle", type: r.type.replace(/RUNNING/i, "STOPPED") }
                  : r
              )
            );
          }

          setActionNotice(
            `Live AWS Execution Succeeded: ${confirmModal.title} on AWS (${confirmModal.resource.name}). Immediate savings: ${formatCurrency(
              confirmModal.savingsUsd,
              currency,
              2
            )}/mo.`
          );
          onResourceAction?.();
        }
      } else {
        setActionNotice(`Action Notice: ${res.message}`);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      setActionNotice(`Failed to execute: ${msg}`);
    } finally {
      setExecutingAction(false);
      setConfirmModal(null);
    }
  };

  const filteredResources = resources.filter((res) => {
    if (selectedCategory !== "all" && res.category !== selectedCategory) return false;
    if (selectedStatus !== "all" && res.status !== selectedStatus) return false;
    if (
      searchQuery &&
      !res.name.toLowerCase().includes(searchQuery.toLowerCase()) &&
      !res.service.toLowerCase().includes(searchQuery.toLowerCase()) &&
      !res.id.toLowerCase().includes(searchQuery.toLowerCase())
    ) {
      return false;
    }
    return true;
  });

  const totalCost = resources.reduce((acc, r) => acc + r.monthly_usd, 0);
  const avgUtil = Math.round(
    resources.reduce((acc, r) => acc + r.utilization_pct, 0) / Math.max(1, resources.length)
  );
  const idleCount = resources.filter((r) => r.status === "idle" || r.status === "overprovisioned").length;

  const handleAction = (res: CloudResource, actionName: string) => {
    setActionNotice(`${actionName} initiated for ${res.name}. Generating cloud event...`);
    setTimeout(() => {
      setActionNotice(null);
    }, 2800);
  };

  return (
    <div className="mt-6 space-y-6">
      {/* Action Notification Pill */}
      {actionNotice && (
        <div
          className={`flex items-center justify-between gap-3 rounded-xl border p-3.5 text-[13px] font-medium animate-fadeIn ${
            actionNotice.toLowerCase().includes("error") || actionNotice.toLowerCase().includes("failed")
              ? "border-red-500/30 bg-red-500/10 text-red-400"
              : actionNotice.toLowerCase().includes("dry run")
              ? "border-amber-500/30 bg-amber-500/10 text-amber-400"
              : "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
          }`}
        >
          <div className="flex items-center gap-2.5">
            <Icon
              icon={
                actionNotice.toLowerCase().includes("error") || actionNotice.toLowerCase().includes("failed")
                  ? "mdi:alert-circle"
                  : actionNotice.toLowerCase().includes("dry run")
                  ? "mdi:shield-check"
                  : "mdi:check-circle"
              }
              className="h-5 w-5 shrink-0"
            />
            <span>{actionNotice}</span>
          </div>
          <button
            onClick={() => setActionNotice(null)}
            className="rounded-lg p-1 text-ink-3 hover:bg-surface hover:text-ink transition-colors"
            title="Dismiss notice"
          >
            <Icon icon="mdi:close" className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* KPI Stats Row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
        <div className="rounded-2xl border border-line bg-surface p-5 shadow-xs">
          <div className="text-[12.5px] font-medium text-ink-3">Total Active Resources</div>
          <div className="mt-1.5 font-mono text-[26px] font-bold text-ink">
            {resources.length}
          </div>
          <div className="mt-1 text-[11.5px] text-ink-2">
            Discovered across {p.toUpperCase()}
          </div>
        </div>

        <div className="rounded-2xl border border-line bg-surface p-5 shadow-xs">
          <div className="text-[12.5px] font-medium text-ink-3">Inventory Monthly Run-rate</div>
          <div className="mt-1.5 font-mono text-[26px] font-bold text-ink">
            {formatCurrency(totalCost, currency, 0)}
          </div>
          <div className="mt-1 text-[11.5px] text-ink-2">
            Direct infrastructure charges
          </div>
        </div>

        <div className="rounded-2xl border border-line bg-surface p-5 shadow-xs">
          <div className="text-[12.5px] font-medium text-ink-3">Average Resource Utilization</div>
          <div className="mt-1.5 flex items-baseline gap-2">
            <span className="font-mono text-[26px] font-bold text-ink">{avgUtil}%</span>
            <span className="text-[12px] text-amber-500 font-medium">Headroom: {100 - avgUtil}%</span>
          </div>
          <div className="mt-1 text-[11.5px] text-ink-2">
            CPU & memory metrics across nodes
          </div>
        </div>

        <div className="rounded-2xl border border-line bg-surface p-5 shadow-xs">
          <div className="text-[12.5px] font-medium text-ink-3">Idle / Overprovisioned</div>
          <div className="mt-1.5 font-mono text-[26px] font-bold text-amber-500">
            {idleCount} Workloads
          </div>
          <div className="mt-1 text-[11.5px] text-ink-2">
            Flagged for right-sizing
          </div>
        </div>
      </div>

      {/* Search & Filter Controls */}
      <div className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-4 sm:flex-row sm:items-center sm:justify-between shadow-xs">
        {/* Category Tabs */}
        <div className="flex flex-wrap items-center gap-1.5">
          {[
            { id: "all", label: "All Services" },
            { id: "compute", label: "Compute" },
            { id: "database", label: "Database" },
            { id: "storage", label: "Storage" },
            { id: "networking", label: "Networking" },
            { id: "cache", label: "Cache" },
          ].map((cat) => (
            <button
              key={cat.id}
              onClick={() => setSelectedCategory(cat.id)}
              className={`rounded-xl px-3 py-1.5 text-[12.5px] font-medium transition-all ${
                selectedCategory === cat.id
                  ? "bg-accent text-white shadow-2xs"
                  : "bg-sunk text-ink-2 hover:text-ink"
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* Controls right: Search + Delete All Resources Button */}
        <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center">
          <div className="relative w-full sm:w-64">
            <Icon
              icon="mdi:magnify"
              className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-3"
            />
            <input
              type="text"
              placeholder="Filter by name, ID or type..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-xl border border-line bg-sunk/60 py-1.5 pl-9 pr-3 text-[12.5px] text-ink placeholder:text-ink-3 focus:border-accent focus:outline-none"
            />
          </div>

          <button
            onClick={() => {
              setShowDeleteAllModal(true);
              setConfirmText("");
              setDeleteAllActions(null);
            }}
            disabled={resources.length === 0}
            className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-red-500/40 bg-red-500/10 px-3.5 py-1.5 text-[12.5px] font-bold text-red-500 hover:bg-red-500/20 hover:border-red-500/60 shadow-2xs transition-all active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap cursor-pointer"
            title="Delete all active provisioned resources with keyboard confirmation"
          >
            <Icon icon="mdi:trash-can-alert" className="h-4 w-4 shrink-0" />
            <span>Delete All Resources</span>
          </button>
        </div>
      </div>

      {/* Resource Inventory Table */}
      <div className="overflow-hidden rounded-2xl border border-line bg-surface shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[13px]">
            <thead className="border-b border-line bg-sunk/50 text-[11px] font-bold uppercase tracking-wider text-ink-3">
              <tr>
                <th className="px-5 py-3">Resource & Identifier</th>
                <th className="px-4 py-3">Service & Spec</th>
                <th className="px-4 py-3">Region</th>
                <th className="px-4 py-3">Utilization</th>
                <th className="px-4 py-3 text-right">Monthly Spend</th>
                <th className="px-4 py-3">Cost Tag</th>
                <th className="px-5 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/60">
              {filteredResources.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-5 py-14 text-center">
                    <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 mb-3 shadow-inner">
                      <Icon icon="mdi:check-decagram" className="h-6 w-6" />
                    </div>
                    <div className="text-[15px] font-bold text-ink">
                      No Active Provisioned Workloads Found
                    </div>
                    <p className="mt-1 text-[12.5px] text-ink-3 max-w-md mx-auto">
                      All provisioned cloud workloads in account <span className="font-mono font-semibold text-ink-2">{accountId}</span> have been deleted or terminated. Zero monthly idle waste is accruing.
                    </p>
                  </td>
                </tr>
              ) : (
                filteredResources.map((res) => (
                  <tr key={res.id} className="hover:bg-sunk/40 transition-colors">
                    <td className="px-5 py-4">
                      <div className="font-semibold text-ink">{res.name}</div>
                      <div className="font-mono text-[11px] text-ink-3 truncate max-w-[200px]">
                        {res.id}
                      </div>
                    </td>

                    <td className="px-4 py-4">
                      <div className="font-medium text-ink-2">{res.service}</div>
                      <div className="text-[11.5px] text-ink-3">{res.type}</div>
                    </td>

                    <td className="px-4 py-4">
                      <span className="font-mono text-[11.5px] text-ink-3">{res.region}</span>
                    </td>

                    <td className="px-4 py-4">
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-16 overflow-hidden rounded-full bg-sunk">
                          <div
                            className={`h-full ${
                              res.utilization_pct < 25
                                ? "bg-amber-500"
                                : res.utilization_pct > 80
                                ? "bg-red-500"
                                : "bg-emerald-500"
                            }`}
                            style={{ width: `${res.utilization_pct}%` }}
                          />
                        </div>
                        <span className="font-mono text-[11.5px] text-ink">
                          {res.utilization_pct}%
                        </span>
                      </div>
                    </td>

                    <td className="px-4 py-4 text-right">
                      <span className="font-mono font-bold text-ink">
                        {formatCurrency(res.monthly_usd, currency, 2)}
                      </span>
                      <div className="text-[10.5px] text-ink-3">/ month</div>
                    </td>

                    <td className="px-4 py-4">
                      <div className="flex flex-col gap-0.5">
                        <span className="inline-flex rounded bg-sunk px-1.5 py-0.5 text-[10.5px] font-mono text-ink-2">
                          team:{res.tags.team}
                        </span>
                        <span className="inline-flex rounded bg-sunk px-1.5 py-0.5 text-[10.5px] font-mono text-ink-3">
                          env:{res.tags.env}
                        </span>
                      </div>
                    </td>

                    <td className="px-5 py-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        {/* Contextual Action Buttons for Provisioned Cloud Resources */}
                        {(res.id.startsWith("eipalloc-") || res.type.includes("Elastic IP") || res.name.startsWith("eip-")) ? (
                          <button
                            onClick={() =>
                              openActionModal(
                                res,
                                "release_eip",
                                "Release Elastic IP Address",
                                `aws ec2 release-address --allocation-id ${res.id} --region ${res.region}`,
                                res.monthly_usd
                              )
                            }
                            className="inline-flex items-center gap-1 rounded-lg border border-red-500/30 bg-red-500/10 px-2.5 py-1 text-[11.5px] font-semibold text-red-500 hover:bg-red-500/20 transition-colors"
                            title="Release unassociated IP address to eliminate $3.65/mo idle fee"
                          >
                            <Icon icon="mdi:ip-network-outline" className="h-3.5 w-3.5" />
                            <span>Release IP</span>
                          </button>
                        ) : (res.service === "Amazon EBS" || res.id.startsWith("vol-")) ? (
                          <button
                            onClick={() =>
                              openActionModal(
                                res,
                                "delete_volume",
                                "Delete Detached EBS Volume",
                                `aws ec2 delete-volume --volume-id ${res.id} --region ${res.region}`,
                                res.monthly_usd
                              )
                            }
                            className="inline-flex items-center gap-1 rounded-lg border border-red-500/30 bg-red-500/10 px-2.5 py-1 text-[11.5px] font-semibold text-red-500 hover:bg-red-500/20 transition-colors"
                            title="Delete unattached EBS volume"
                          >
                            <Icon icon="mdi:trash-can-outline" className="h-3.5 w-3.5" />
                            <span>Delete Volume</span>
                          </button>
                        ) : (res.service === "Amazon EC2" || res.id.startsWith("i-")) ? (
                          <div className="flex items-center gap-1.5">
                            {!(res.status === "idle" || res.type.includes("STOPPED")) && (
                              <button
                                onClick={() =>
                                  openActionModal(
                                    res,
                                    "stop_instance",
                                    "Stop EC2 Instance",
                                    `aws ec2 stop-instances --instance-ids ${res.id} --region ${res.region}`,
                                    Math.round(res.monthly_usd * 0.75 * 100) / 100
                                  )
                                }
                                className="inline-flex items-center gap-1 rounded-lg border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-[11.5px] font-semibold text-amber-500 hover:bg-amber-500/20 transition-colors"
                                title="Stop instance compute runtime"
                              >
                                <Icon icon="mdi:stop-circle-outline" className="h-3.5 w-3.5" />
                                <span>Stop</span>
                              </button>
                            )}
                            <button
                              onClick={() =>
                                openActionModal(
                                  res,
                                  "terminate_instance",
                                  "Terminate EC2 Instance",
                                  `aws ec2 terminate-instances --instance-ids ${res.id} --region ${res.region}`,
                                  res.monthly_usd
                                )
                              }
                              className="inline-flex items-center gap-1 rounded-lg border border-red-500/30 bg-red-500/10 px-2.5 py-1 text-[11.5px] font-semibold text-red-500 hover:bg-red-500/20 transition-colors"
                              title="Permanently terminate EC2 instance"
                            >
                              <Icon icon="mdi:trash-can-outline" className="h-3.5 w-3.5" />
                              <span>Terminate</span>
                            </button>
                          </div>
                        ) : (res.service === "Amazon S3" || res.id.startsWith("arn:aws:s3")) ? (
                          <button
                            onClick={() => {
                              const bucketName = res.id.replace("arn:aws:s3:::", "").split("/")[0] || res.name;
                              openActionModal(
                                res,
                                "delete_bucket",
                                "Delete S3 Bucket",
                                `aws s3 rb s3://${bucketName} --force --region ${res.region}`,
                                res.monthly_usd
                              );
                            }}
                            className="inline-flex items-center gap-1 rounded-lg border border-line bg-surface px-2.5 py-1 text-[11.5px] font-medium text-red-500 hover:bg-red-500/10 transition-colors"
                            title="Delete S3 bucket and empty objects"
                          >
                            <Icon icon="mdi:trash-can-outline" className="h-3.5 w-3.5" />
                            <span>Delete Bucket</span>
                          </button>
                        ) : (
                          <button
                            onClick={() => handleAction(res, "Rightsize Simulation")}
                            className="rounded-lg border border-line bg-surface px-2.5 py-1 text-[11.5px] font-medium text-ink hover:bg-sunk transition-colors"
                            title="Analyze right-sizing options"
                          >
                            Rightsize
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Action Confirmation Modal */}
      {confirmModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in">
          <div className="relative w-full max-w-lg rounded-2xl border border-line bg-surface p-6 shadow-2xl transition-all">
            {/* Header */}
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-red-500/20 bg-red-500/10 text-red-500">
                <Icon icon="mdi:alert-circle-outline" className="h-5 w-5" />
              </div>
              <div className="flex-1">
                <h3 className="text-[17px] font-bold text-ink">{confirmModal.title}</h3>
                <p className="mt-0.5 text-[12.5px] text-ink-2">
                  Confirm cloud resource lifecycle action. This will directly modify your provisioned cloud resources.
                </p>
              </div>
              <button
                onClick={() => setConfirmModal(null)}
                className="rounded-lg p-1 text-ink-3 hover:bg-sunk hover:text-ink transition-colors"
              >
                <Icon icon="mdi:close" className="h-5 w-5" />
              </button>
            </div>

            {/* Resource Spec Summary */}
            <div className="mt-5 rounded-xl border border-line bg-sunk/60 p-4 space-y-2.5">
              <div className="flex items-center justify-between text-[12.5px]">
                <span className="text-ink-3">Resource Name:</span>
                <span className="font-semibold text-ink">{confirmModal.resource.name}</span>
              </div>
              <div className="flex items-center justify-between text-[12.5px]">
                <span className="text-ink-3">Resource ID:</span>
                <span className="font-mono text-[11.5px] text-ink-2 truncate max-w-[240px]">
                  {confirmModal.resource.id}
                </span>
              </div>
              <div className="flex items-center justify-between text-[12.5px]">
                <span className="text-ink-3">Region & Service:</span>
                <span className="font-mono text-[11.5px] text-ink-2">
                  {confirmModal.resource.region} • {confirmModal.resource.service}
                </span>
              </div>
              {confirmModal.resource.tags?.attached_to && confirmModal.resource.tags.attached_to !== "unattached" && (
                <div className="flex items-center justify-between text-[12.5px]">
                  <span className="text-ink-3">Attached Instance:</span>
                  <span className="font-mono text-[11.5px] text-blue-400">
                    {confirmModal.resource.tags.attached_to}
                  </span>
                </div>
              )}
              <div className="flex items-center justify-between border-t border-line/60 pt-2 text-[12.5px]">
                <span className="font-medium text-ink-2">Immediate Monthly Savings:</span>
                <span className="font-mono font-bold text-emerald-500">
                  +{formatCurrency(confirmModal.savingsUsd, currency, 2)}/mo
                </span>
              </div>
            </div>

            {/* Cloud CLI Command Box */}
            <div className="mt-4">
              <div className="flex items-center justify-between pb-1.5 text-[11.5px] font-medium text-ink-3">
                <span className="flex items-center gap-1.5 font-mono">
                  <Icon icon="mdi:console-line" className="h-4 w-4" />
                  Live Cloud CLI Command
                </span>
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(confirmModal.command);
                    setCopiedCommand(true);
                    setTimeout(() => setCopiedCommand(false), 2000);
                  }}
                  className="flex items-center gap-1 text-[11px] text-accent hover:underline"
                >
                  <Icon icon={copiedCommand ? "mdi:check" : "mdi:content-copy"} className="h-3.5 w-3.5" />
                  <span>{copiedCommand ? "Copied" : "Copy command"}</span>
                </button>
              </div>
              <div className="overflow-x-auto rounded-xl border border-line bg-canvas p-3 font-mono text-[11.5px] text-ink">
                <code>{confirmModal.command}</code>
              </div>
            </div>

            {/* Warning Notice */}
            <div className="mt-4 flex items-center gap-2 rounded-xl bg-amber-500/10 border border-amber-500/20 p-3 text-[12px] text-amber-500">
              <Icon icon="mdi:shield-alert" className="h-4 w-4 shrink-0" />
              <span>
                Live execution executes directly against your authentic {p.toUpperCase()} IAM credentials. Terminations permanently destroy the workload.
              </span>
            </div>

            {/* Action Buttons */}
            <div className="mt-6 flex items-center justify-end gap-2.5">
              <button
                type="button"
                disabled={executingAction}
                onClick={() => setConfirmModal(null)}
                className="rounded-xl border border-line bg-surface px-4 py-2 text-[13px] font-medium text-ink hover:bg-sunk transition-colors"
              >
                Cancel
              </button>

              <button
                type="button"
                disabled={executingAction}
                onClick={() => handleExecuteAction(true)}
                className="rounded-xl border border-line bg-sunk px-4 py-2 text-[13px] font-medium text-ink-2 hover:text-ink hover:bg-sunk/80 transition-colors"
                title="Verify AWS IAM permissions without altering resource state"
              >
                {executingAction ? "Testing..." : "Dry Run (Simulate Only)"}
              </button>

              <button
                type="button"
                disabled={executingAction}
                onClick={() => handleExecuteAction(false)}
                className="inline-flex items-center gap-2 rounded-xl bg-red-600 px-4 py-2 text-[13px] font-bold text-white hover:bg-red-700 shadow-sm transition-colors disabled:opacity-50"
              >
                {executingAction ? (
                  <>
                    <Icon icon="mdi:loading" className="h-4 w-4 animate-spin" />
                    <span>Executing Live on AWS...</span>
                  </>
                ) : (
                  <>
                    <Icon icon="mdi:flash" className="h-4 w-4" />
                    <span>Execute Live on {p.toUpperCase()}</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* High-Security Delete All Resources Keyboard Confirmation Modal */}
      {showDeleteAllModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-in fade-in">
          <div className="relative w-full max-w-xl rounded-2xl border border-red-500/40 bg-surface p-6 sm:p-7 shadow-2xl transition-all">
            {/* Header */}
            <div className="flex items-start gap-3.5">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-red-500/30 bg-red-500/15 text-red-500 shadow-inner">
                <Icon icon="mdi:alert-octagon" className="h-6 w-6 animate-pulse" />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="text-[18px] font-bold text-ink">
                    Delete All Provisioned Resources
                  </h3>
                  <span className="rounded-full bg-red-500/15 border border-red-500/30 px-2 py-0.5 text-[10.5px] font-bold text-red-500 uppercase tracking-wide">
                    Destructive Action
                  </span>
                </div>
                <p className="mt-1 text-[12.5px] text-ink-2 leading-relaxed">
                  This action will permanently deprovision, terminate, and delete all active cloud workloads in connected account{" "}
                  <span className="font-mono font-semibold text-ink">{accountId}</span> ({p.toUpperCase()}).
                </p>
              </div>
              <button
                onClick={() => {
                  setShowDeleteAllModal(false);
                  setConfirmText("");
                  setDeleteAllActions(null);
                }}
                className="rounded-lg p-1 text-ink-3 hover:bg-sunk hover:text-ink transition-colors"
              >
                <Icon icon="mdi:close" className="h-5 w-5" />
              </button>
            </div>

            {/* Impact Metrics Summary Box */}
            <div className="mt-5 grid grid-cols-2 gap-3 rounded-xl border border-line bg-sunk/60 p-3.5">
              <div>
                <span className="text-[11px] uppercase font-bold text-ink-3 tracking-wider">Resources to Purge</span>
                <div className="mt-0.5 font-mono text-[20px] font-bold text-red-500">
                  {resources.length} Workloads
                </div>
                <div className="text-[11px] text-ink-3">Across {p.toUpperCase()} live environment</div>
              </div>
              <div>
                <span className="text-[11px] uppercase font-bold text-ink-3 tracking-wider">Eliminated Run-Rate</span>
                <div className="mt-0.5 font-mono text-[20px] font-bold text-emerald-500">
                  +{formatCurrency(totalCost, currency, 2)}/mo
                </div>
                <div className="text-[11px] text-ink-3">Immediate monthly reduction</div>
              </div>
            </div>

            {/* Teardown Actions Preview if available */}
            {deleteAllActions && deleteAllActions.length > 0 && (
              <div className="mt-4 max-h-40 overflow-y-auto rounded-xl border border-line bg-canvas p-3 space-y-1.5 font-mono text-[11px]">
                <div className="text-[11px] font-sans font-bold text-emerald-500 mb-1">
                  Dry Run Output ({deleteAllActions.length} actions verified):
                </div>
                {deleteAllActions.map((act, idx) => (
                  <div key={idx} className="flex items-center justify-between text-ink-2">
                    <span className="truncate max-w-[280px]">{act.action}: {act.resource}</span>
                    <span className="text-emerald-500 font-semibold shrink-0">+{formatCurrency(act.savings, currency, 2)}/mo</span>
                  </div>
                ))}
              </div>
            )}

            {/* Physical Keyboard Confirmation Box */}
            <div className="mt-5 rounded-xl border border-red-500/25 bg-red-500/5 p-4">
              <label className="block text-[12.5px] font-semibold text-ink">
                Type <span className="font-mono text-red-500 bg-red-500/10 px-1.5 py-0.5 rounded border border-red-500/20">delete all resources</span> or <span className="font-mono text-red-500 bg-red-500/10 px-1.5 py-0.5 rounded border border-red-500/20">confirm</span> with your keyboard:
              </label>
              <div className="relative mt-2.5">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-ink-3">
                  <Icon icon="mdi:keyboard-outline" className="h-5 w-5" />
                </div>
                <input
                  type="text"
                  autoFocus
                  value={confirmText}
                  onChange={(e) => setConfirmText(e.target.value)}
                  placeholder='Type "delete all resources" or "confirm"'
                  className={`w-full rounded-xl border py-2.5 pl-11 pr-4 font-mono text-[13px] text-ink placeholder:text-ink-3 focus:outline-none transition-all ${
                    isNukeConfirmed
                      ? "border-emerald-500 bg-emerald-500/10 text-emerald-500 ring-2 ring-emerald-500/20"
                      : confirmText.length > 0
                      ? "border-amber-500 bg-amber-500/10 text-amber-500"
                      : "border-line bg-surface focus:border-red-500"
                  }`}
                />
              </div>

              {/* Real-time Keyboard Match Status */}
              <div className="mt-2 flex items-center gap-1.5 text-[11.5px]">
                {confirmText.trim() === "" ? (
                  <span className="flex items-center gap-1 text-ink-3">
                    <Icon icon="mdi:information-outline" className="h-3.5 w-3.5" />
                    Enter the exact confirmation phrase above using your laptop keyboard to unlock the button.
                  </span>
                ) : !isNukeConfirmed ? (
                  <span className="flex items-center gap-1 font-mono text-amber-500 font-medium">
                    <Icon icon="mdi:alert-circle-outline" className="h-3.5 w-3.5" />
                    Typing: &quot;{confirmText}&quot; (must match &quot;delete all resources&quot; or &quot;confirm&quot;)
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-emerald-500 font-semibold animate-fadeIn">
                    <Icon icon="mdi:check-circle" className="h-3.5 w-3.5" />
                    Keyboard confirmation verified! Safety lock disabled.
                  </span>
                )}
              </div>
            </div>

            {/* Action Buttons */}
            <div className="mt-6 flex flex-wrap items-center justify-end gap-2.5">
              <button
                type="button"
                disabled={executingDeleteAll}
                onClick={() => {
                  setShowDeleteAllModal(false);
                  setConfirmText("");
                  setDeleteAllActions(null);
                }}
                className="rounded-xl border border-line bg-surface px-4 py-2 text-[13px] font-medium text-ink hover:bg-sunk transition-colors"
              >
                Cancel
              </button>

              <button
                type="button"
                disabled={!isNukeConfirmed || executingDeleteAll}
                onClick={() => handleExecuteDeleteAll(true)}
                className="rounded-xl border border-line bg-sunk px-4 py-2 text-[13px] font-medium text-ink-2 hover:text-ink hover:bg-sunk/80 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                title="Verify commands safely in dry-run mode"
              >
                {executingDeleteAll ? "Simulating..." : "Dry Run Simulation"}
              </button>

              <button
                type="button"
                disabled={!isNukeConfirmed || executingDeleteAll}
                onClick={() => handleExecuteDeleteAll(false)}
                className="inline-flex items-center gap-2 rounded-xl bg-red-600 px-5 py-2 text-[13px] font-bold text-white hover:bg-red-700 shadow-md transition-all disabled:opacity-40 disabled:cursor-not-allowed hover:shadow-red-600/20"
              >
                {executingDeleteAll ? (
                  <>
                    <Icon icon="mdi:loading" className="h-4 w-4 animate-spin" />
                    <span>Teardown in Progress...</span>
                  </>
                ) : (
                  <>
                    <Icon icon="mdi:trash-can-alert" className="h-4 w-4" />
                    <span>Delete All Resources</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

