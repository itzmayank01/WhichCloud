"use client";

import { useEffect, useState } from "react";
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
}

export function FinOpsResourcesView({
  provider = "aws",
  currency = "USD",
  accountId = "demo",
}: FinOpsResourcesViewProps) {
  const p = provider.toLowerCase();
  const rawList = DEFAULT_RESOURCES[p] || DEFAULT_RESOURCES.aws;

  const [resources, setResources] = useState<CloudResource[]>(rawList);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [selectedStatus, setSelectedStatus] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    api.finopsResources(provider, accountId)
      .then((res) => {
        if (mounted && res?.resources && res.resources.length > 0) {
          setResources(res.resources);
        }
      })
      .catch((err) => {
        console.error("Live resources fetch error:", err);
      });

    return () => {
      mounted = false;
    };
  }, [provider, accountId]);

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
    resources.reduce((acc, r) => acc + r.utilization_pct, 0) / resources.length
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
        <div className="flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-[13px] font-medium text-emerald-500 animate-fadeIn">
          <Icon icon="mdi:check-circle" className="h-4 w-4 shrink-0" />
          <span>{actionNotice}</span>
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

        {/* Search input */}
        <div className="relative w-full sm:w-72">
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
              {filteredResources.map((res) => (
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
                      <button
                        onClick={() => handleAction(res, "Rightsize Simulation")}
                        className="rounded-lg border border-line bg-surface px-2.5 py-1 text-[11.5px] font-medium text-ink hover:bg-sunk transition-colors"
                        title="Analyze right-sizing options"
                      >
                        Rightsize
                      </button>
                      <button
                        onClick={() => handleAction(res, "Snapshot Backup")}
                        className="rounded-lg border border-line bg-surface p-1 text-ink-3 hover:text-ink hover:bg-sunk transition-colors"
                        title="Create backup snapshot"
                      >
                        <Icon icon="mdi:camera" className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
