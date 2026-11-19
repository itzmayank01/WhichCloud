"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@clerk/nextjs";
import { Icon } from "@iconify/react";
import { api, money, type SavedArchitecture } from "@/lib/api";
import { TerraformLogo } from "@/components/Logo";

interface StarterProject {
  id: string;
  title: string;
  description: string;
  archetype: string;
  services: number;
  regions: number;
  monthlyEstimate: number;
  cloud: "aws" | "gcp" | "azure";
  createdAt: string;
}

const STARTER_PROJECTS: StarterProject[] = [
  {
    id: "proj-retail-40",
    title: "Retail Chain High-Availability Billing",
    description: "40 stores in India moving stock and live billing online. 300 staff daily, 8,000 txns/day, Multi-AZ PostgreSQL, ElastiCache Redis, and ALB with zero business hours downtime.",
    archetype: "Web App (HA)",
    services: 10,
    regions: 1,
    monthlyEstimate: 411.00,
    cloud: "aws",
    createdAt: "2026-11-18T10:00:00Z",
  },
  {
    id: "proj-hospital-pune",
    title: "Healthcare Appointments & EHR Portal",
    description: "3-hospital healthcare group in Pune. Patient appointments, encrypted lab reports, 450 staff, 6,000 lookups/day with strict in-country data compliance.",
    archetype: "Healthcare / Web App",
    services: 8,
    regions: 1,
    monthlyEstimate: 248.79,
    cloud: "aws",
    createdAt: "2026-11-16T14:30:00Z",
  },
  {
    id: "proj-overnight-etl",
    title: "Nightly Financial Reporting ETL Pipeline",
    description: "Sales data loaded overnight from till systems into reporting database. Finance team reads next-day reports. Serverless batch compute idle during the day.",
    archetype: "Batch ETL",
    services: 6,
    regions: 1,
    monthlyEstimate: 184.20,
    cloud: "aws",
    createdAt: "2026-11-15T09:15:00Z",
  },
];

interface ConnectedAccount {
  account_id: string;
  provider: string;
  role_arn?: string;
  status: "connected" | "pending";
  last_sync?: string;
  primary_region: string;
}

export default function ProjectsPage() {
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const [activeTab, setActiveTab] = useState<"architectures" | "accounts" | "environments">("architectures");
  const [saved, setSaved] = useState<SavedArchitecture[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Accounts state
  const [connectedAccounts, setConnectedAccounts] = useState<ConnectedAccount[]>([
    {
      account_id: "demo",
      provider: "aws",
      role_arn: "arn:aws:iam::demo:role/WhichCloudCostRole",
      status: "connected",
      primary_region: "us-east-1",
      last_sync: "Just now",
    },
  ]);

  useEffect(() => {
    let mounted = true;

    async function loadData() {
      if (!isLoaded) return;
      setLoading(true);
      setError(null);

      try {
        if (isSignedIn) {
          const token = await getToken();
          if (token) {
            // Load saved architectures
            try {
              const res = await api.savedArchitectures(token);
              if (mounted && res?.saved) {
                setSaved(res.saved);
              }
            } catch (err) {
              console.warn("Could not load user saved architectures:", err);
            }

            // Load connected accounts
            try {
              const accRes = await api.myConnections(token);
              if (mounted && accRes?.connections && accRes.connections.length > 0) {
                setConnectedAccounts(accRes.connections.map((c) => ({
                  account_id: c.account_id,
                  provider: c.provider,
                  role_arn: c.role_arn,
                  status: c.status === "verified" || c.status === "connected" ? "connected" : "pending",
                  primary_region: c.region || "us-east-1",
                  last_sync: "Active",
                })));
              }
            } catch (err) {
              console.warn("Could not load user connections:", err);
            }
          }
        }
      } catch (e) {
        if (mounted) setError("Could not load workspace data.");
      } finally {
        if (mounted) setLoading(false);
      }
    }

    void loadData();

    return () => {
      mounted = false;
    };
  }, [isLoaded, isSignedIn, getToken]);

  async function handleDelete(id: string) {
    if (!confirm("Are you sure you want to delete this saved architecture?")) return;
    try {
      const token = await getToken();
      if (!token) return;
      await api.deleteArchitecture(id, token);
      setSaved((prev) => prev.filter((p) => p.id !== id));
    } catch (err) {
      alert("Could not delete architecture.");
    }
  }

  const allProjectsCount = saved.length > 0 ? saved.length : STARTER_PROJECTS.length;

  return (
    <div className="min-h-screen bg-canvas text-ink px-4 py-10 md:px-8 max-w-7xl mx-auto">
      {/* Top Banner / Breadcrumb */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between border-b border-line pb-8">
        <div>
          <div className="inline-flex items-center gap-2 font-mono text-[12.5px] uppercase tracking-wider text-accent font-medium">
            <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
            WhichCloud Workspace & Projects Hub
          </div>
          <h1 className="mt-2 text-[clamp(1.75rem,3.2vw,2.5rem)] font-bold tracking-tight">
            Cloud Projects & Infrastructure Hub
          </h1>
          <p className="mt-2 text-[15.5px] text-ink-2 max-w-2xl">
            Manage your architectures, export production Terraform, inspect multi-environment drift, and monitor live cloud waste in one smooth flow.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Link
            href="/estimate"
            className="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-[14.5px] font-semibold text-canvas shadow-sm transition hover:opacity-95"
          >
            <Icon icon="heroicons:plus-20-solid" className="h-5 w-5" />
            New Architecture
          </Link>
          <Link
            href="/connect"
            className="inline-flex items-center gap-2 rounded-xl border border-line bg-surface px-4 py-2.5 text-[14.5px] font-medium text-ink transition hover:bg-sunk"
          >
            <Icon icon="heroicons:link-20-solid" className="h-4 w-4 text-ink-2" />
            Connect AWS Account
          </Link>
          <Link
            href="/pricing"
            className="inline-flex items-center gap-1.5 rounded-xl border border-accent/40 bg-accent/10 px-3.5 py-2.5 text-[14px] font-semibold text-accent transition hover:bg-accent/15"
          >
            <Icon icon="heroicons:sparkles-20-solid" className="h-4 w-4" />
            Upgrade to Pro
          </Link>
        </div>
      </div>

      {/* Metrics Fleet Overview */}
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-line bg-surface p-5 shadow-sm">
          <div className="flex items-center justify-between text-ink-3">
            <span className="text-[13px] font-medium uppercase tracking-wider">Saved Projects</span>
            <Icon icon="heroicons:folder-20-solid" className="h-5 w-5 text-accent" />
          </div>
          <div className="mt-3 font-mono text-[28px] font-bold text-ink">
            {allProjectsCount}
          </div>
          <div className="mt-1 text-[12px] text-ink-2">
            {saved.length > 0 ? "Saved in your account" : "Starter template projects"}
          </div>
        </div>

        <div className="rounded-xl border border-line bg-surface p-5 shadow-sm">
          <div className="flex items-center justify-between text-ink-3">
            <span className="text-[13px] font-medium uppercase tracking-wider">Connected Accounts</span>
            <Icon icon="heroicons:server-stack-20-solid" className="h-5 w-5 text-emerald-500" />
          </div>
          <div className="mt-3 font-mono text-[28px] font-bold text-ink">
            {connectedAccounts.length}
          </div>
          <div className="mt-1 text-[12px] text-ink-2">
            1 live STS telemetry connection
          </div>
        </div>

        <div className="rounded-xl border border-line bg-surface p-5 shadow-sm">
          <div className="flex items-center justify-between text-ink-3">
            <span className="text-[13px] font-medium uppercase tracking-wider">Environments</span>
            <Icon icon="heroicons:cube-transparent-20-solid" className="h-5 w-5 text-sky-500" />
          </div>
          <div className="mt-3 font-mono text-[28px] font-bold text-ink">
            3 Active
          </div>
          <div className="mt-1 text-[12px] text-ink-2">
            dev · staging · production
          </div>
        </div>

        <div className="rounded-xl border border-line bg-surface p-5 shadow-sm">
          <div className="flex items-center justify-between text-ink-3">
            <span className="text-[13px] font-medium uppercase tracking-wider">Monthly Spend Tracked</span>
            <Icon icon="heroicons:banknotes-20-solid" className="h-5 w-5 text-amber-500" />
          </div>
          <div className="mt-3 font-mono text-[28px] font-bold text-ink">
            $843.99
          </div>
          <div className="mt-1 text-[12px] text-ink-2">
            ~24% estimated waste identified
          </div>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="mt-10 border-b border-line">
        <nav className="flex gap-6">
          <button
            onClick={() => setActiveTab("architectures")}
            className={`pb-3.5 text-[15px] font-semibold transition-colors border-b-2 ${
              activeTab === "architectures"
                ? "border-accent text-accent"
                : "border-transparent text-ink-2 hover:text-ink"
            }`}
          >
            Cloud Architectures ({allProjectsCount})
          </button>
          <button
            onClick={() => setActiveTab("accounts")}
            className={`pb-3.5 text-[15px] font-semibold transition-colors border-b-2 ${
              activeTab === "accounts"
                ? "border-accent text-accent"
                : "border-transparent text-ink-2 hover:text-ink"
            }`}
          >
            Connected Cloud Accounts ({connectedAccounts.length})
          </button>
          <button
            onClick={() => setActiveTab("environments")}
            className={`pb-3.5 text-[15px] font-semibold transition-colors border-b-2 ${
              activeTab === "environments"
                ? "border-accent text-accent"
                : "border-transparent text-ink-2 hover:text-ink"
            }`}
          >
            Multi-Env IaC Deployments (3)
          </button>
        </nav>
      </div>

      {/* Tab 1: Cloud Architectures */}
      {activeTab === "architectures" && (
        <div className="mt-8 space-y-5">
          {saved.length === 0 && (
            <div className="rounded-xl border border-line/80 bg-surface/50 p-4 mb-6 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Icon icon="heroicons:information-circle-20-solid" className="h-5 w-5 text-accent shrink-0" />
                <span className="text-[14px] text-ink-2">
                  Showing starter architecture templates. Save custom architectures from{" "}
                  <Link href="/dashboard" className="text-accent underline font-medium">Workspace</Link> or{" "}
                  <Link href="/estimate" className="text-accent underline font-medium">Price your app</Link> to pin them here.
                </span>
              </div>
              <Link
                href="/estimate"
                className="hidden sm:inline-block rounded-lg bg-surface border border-line px-3 py-1.5 text-[13px] font-medium text-ink hover:bg-sunk"
              >
                Create Architecture
              </Link>
            </div>
          )}

          {/* User Saved Architectures (if any) */}
          {saved.map((arch) => (
            <div
              key={arch.id}
              className="rounded-2xl border border-line bg-surface p-6 shadow-sm hover:border-line-strong transition-all flex flex-col justify-between md:flex-row md:items-center gap-6"
            >
              <div className="space-y-2 max-w-3xl">
                <div className="flex items-center gap-2.5">
                  <span className="rounded bg-accent/15 px-2.5 py-0.5 font-mono text-[11px] font-semibold uppercase text-accent">
                    Custom Save
                  </span>
                  <span className="text-[12px] text-ink-3">
                    Created {new Date(arch.created_at).toLocaleDateString()}
                  </span>
                </div>
                <h3 className="text-[18px] font-bold text-ink">{arch.title}</h3>
                <p className="text-[14px] leading-relaxed text-ink-2 line-clamp-2">
                  {arch.description}
                </p>
                <div className="flex items-center gap-4 text-[13px] text-ink-3 pt-1">
                  <span>{arch.services} cloud services</span>
                  <span>·</span>
                  <span>{arch.regions} region</span>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-3 shrink-0">
                <Link
                  href={`/terraform`}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-canvas px-3.5 py-2 text-[13.5px] font-medium text-ink hover:bg-sunk"
                >
                  <TerraformLogo className="h-3.5 w-3.5" />
                  Terraform Studio
                </Link>
                <Link
                  href={`/dashboard`}
                  className="rounded-lg bg-accent px-4 py-2 text-[13.5px] font-semibold text-canvas hover:opacity-90"
                >
                  Open in Workspace
                </Link>
                <button
                  onClick={() => handleDelete(arch.id)}
                  title="Delete architecture"
                  className="rounded-lg border border-line p-2 text-ink-3 hover:text-red-500 hover:bg-sunk transition"
                >
                  <Icon icon="heroicons:trash-20-solid" className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}

          {/* Starter Presets (if no custom saves yet) */}
          {saved.length === 0 && (
            <div className="grid gap-6 md:grid-cols-3">
              {STARTER_PROJECTS.map((proj) => (
                <div
                  key={proj.id}
                  className="rounded-2xl border border-line bg-surface p-6 shadow-sm flex flex-col justify-between hover:border-line-strong transition"
                >
                  <div>
                    <div className="flex items-center justify-between">
                      <span className="rounded bg-accent/10 px-2 py-0.5 font-mono text-[11px] font-semibold text-accent uppercase">
                        {proj.archetype}
                      </span>
                      <span className="font-mono text-[12px] font-semibold uppercase text-ink-3">
                        {proj.cloud}
                      </span>
                    </div>

                    <h3 className="mt-3 text-[17px] font-bold text-ink">{proj.title}</h3>
                    <p className="mt-2 text-[13.5px] leading-relaxed text-ink-2 line-clamp-3">
                      {proj.description}
                    </p>

                    <div className="mt-4 pt-4 border-t border-line flex items-baseline justify-between">
                      <span className="text-[12px] text-ink-3">Estimated:</span>
                      <span className="font-mono text-[18px] font-bold text-ink">
                        {money(proj.monthlyEstimate)}
                        <span className="text-[12px] font-normal text-ink-3">/mo</span>
                      </span>
                    </div>
                  </div>

                  <div className="mt-6 pt-2 flex items-center gap-2">
                    <Link
                      href="/terraform"
                      className="flex-1 rounded-xl border border-line bg-canvas py-2 text-center text-[13px] font-medium text-ink hover:bg-sunk transition"
                    >
                      Terraform
                    </Link>
                    <Link
                      href="/dashboard"
                      className="flex-1 rounded-xl bg-accent py-2 text-center text-[13px] font-semibold text-canvas hover:opacity-90 transition"
                    >
                      Workspace
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Connected Cloud Accounts */}
      {activeTab === "accounts" && (
        <div className="mt-8 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-[18px] font-semibold text-ink">Linked Cloud Providers</h3>
              <p className="text-[14px] text-ink-2">
                WhichCloud reads cost telemetry and waste signals using read-only STS AssumeRole.
              </p>
            </div>
            <Link
              href="/connect"
              className="rounded-xl bg-accent px-4 py-2 text-[14px] font-semibold text-canvas hover:opacity-90"
            >
              Add AWS Account
            </Link>
          </div>

          <div className="space-y-4">
            {connectedAccounts.map((acc, idx) => (
              <div
                key={idx}
                className="rounded-xl border border-line bg-surface p-5 flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="flex items-center gap-4">
                  <div className="h-10 w-10 rounded-lg bg-amber-500/10 flex items-center justify-center text-amber-500">
                    <Icon icon="simple-icons:amazonaws" className="h-6 w-6" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-ink">AWS Account: {acc.account_id}</span>
                      <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[11px] font-medium text-emerald-500">
                        {acc.status}
                      </span>
                    </div>
                    <div className="text-[13px] text-ink-3 mt-0.5 font-mono">
                      Region: {acc.primary_region} · Role: {acc.role_arn || "WhichCloudCostRole"}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <Link
                    href={`/finops?provider=${acc.provider}&account_id=${acc.account_id}`}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-[13.5px] font-medium text-canvas hover:opacity-90"
                  >
                    <Icon icon="heroicons:chart-bar-20-solid" className="h-4 w-4" />
                    Open FinOps Live
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 3: Multi-Env IaC Deployments */}
      {activeTab === "environments" && (
        <div className="mt-8 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-[18px] font-semibold text-ink">Infrastructure Environments</h3>
              <p className="text-[14px] text-ink-2">
                Manage dev, staging, and production sizing with automated configuration drift detection.
              </p>
            </div>
            <Link
              href="/environments"
              className="rounded-xl bg-accent px-4 py-2 text-[14px] font-semibold text-canvas hover:opacity-90"
            >
              Open Multi-Env Studio
            </Link>
          </div>

          <div className="grid gap-6 md:grid-cols-3">
            <div className="rounded-2xl border border-line bg-surface p-6">
              <div className="flex items-center justify-between">
                <span className="rounded bg-emerald-500/15 px-2 py-0.5 text-[11px] font-bold text-emerald-500 uppercase">
                  Healthy
                </span>
                <span className="font-mono text-[12px] text-ink-3">v1.0.4</span>
              </div>
              <h4 className="mt-3 text-[18px] font-bold text-ink">dev</h4>
              <p className="mt-1 text-[13px] text-ink-2">Single NAT · t3.micro · db.t4g.micro</p>
              <div className="mt-4 pt-3 border-t border-line flex justify-between items-baseline font-mono">
                <span className="text-[12px] text-ink-3">Cost:</span>
                <span className="font-bold text-ink">$52.40/mo</span>
              </div>
            </div>

            <div className="rounded-2xl border border-line bg-surface p-6">
              <div className="flex items-center justify-between">
                <span className="rounded bg-emerald-500/15 px-2 py-0.5 text-[11px] font-bold text-emerald-500 uppercase">
                  Healthy
                </span>
                <span className="font-mono text-[12px] text-ink-3">v1.0.4</span>
              </div>
              <h4 className="mt-3 text-[18px] font-bold text-ink">staging</h4>
              <p className="mt-1 text-[13px] text-ink-2">Multi-AZ Subnets · t3.small · db.t4g.small</p>
              <div className="mt-4 pt-3 border-t border-line flex justify-between items-baseline font-mono">
                <span className="text-[12px] text-ink-3">Cost:</span>
                <span className="font-bold text-ink">$148.90/mo</span>
              </div>
            </div>

            <div className="rounded-2xl border border-line bg-surface p-6">
              <div className="flex items-center justify-between">
                <span className="rounded bg-accent/15 px-2 py-0.5 text-[11px] font-bold text-accent uppercase">
                  Production
                </span>
                <span className="font-mono text-[12px] text-ink-3">v1.0.3</span>
              </div>
              <h4 className="mt-3 text-[18px] font-bold text-ink">production</h4>
              <p className="mt-1 text-[13px] text-ink-2">Graviton Cluster · Multi-AZ RDS + Replica</p>
              <div className="mt-4 pt-3 border-t border-line flex justify-between items-baseline font-mono">
                <span className="text-[12px] text-ink-3">Cost:</span>
                <span className="font-bold text-ink">$411.00/mo</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Pro Value / Upgrade Banner */}
      <div className="mt-16 rounded-2xl border border-line bg-gradient-to-r from-surface to-sunk p-8 flex flex-col md:flex-row md:items-center justify-between gap-6 shadow-sm">
        <div className="space-y-2 max-w-2xl">
          <div className="inline-flex items-center gap-1.5 font-mono text-[12px] font-semibold uppercase tracking-wider text-accent">
            <Icon icon="heroicons:sparkles-20-solid" className="h-4 w-4" />
            Supercharge Your Cloud Workflows
          </div>
          <h3 className="text-[20px] font-bold text-ink">
            Need production multi-module Terraform ZIPs & unlimited account monitoring?
          </h3>
          <p className="text-[14.5px] leading-relaxed text-ink-2">
            WhichCloud Pro unlocks complete production Terraform modules with KMS encryption, IAM roles, cost reports, and continuous FinOps waste remediation.
          </p>
        </div>

        <Link
          href="/pricing"
          className="shrink-0 rounded-xl bg-accent px-6 py-3 text-center text-[15px] font-semibold text-canvas shadow-md transition hover:opacity-95"
        >
          View Plans & Pricing →
        </Link>
      </div>
    </div>
  );
}
