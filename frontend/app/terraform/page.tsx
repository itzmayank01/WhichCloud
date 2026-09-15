"use client";

import React, { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Icon } from "@iconify/react";
import {
  api,
  money,
  CLOUDS,
  type CloudId,
  type Option,
  type Recommendation,
  type Node as TopoNode,
  type Edge as TopoEdge,
} from "@/lib/api";
import {
  ArchitectureGraph,
  type SelectedNode,
} from "@/components/architecture/ArchitectureGraph";
import { Inspector } from "@/components/workspace/Inspector";
import { TerraformLogo, CostReportsIcon } from "@/components/Logo";

interface ArchitectureItem {
  label: string;
  monthly: number;
  sku: string;
}

interface OptionItem {
  label: string;
  monthly: number;
  region: string;
}

const DEFAULT_WORKLOAD =
  "I run operations for a retail chain in India with 120 stores. Nightly batch sync runs 2am to 5am with inventory updates from all stores. In-store POS queries the catalog during store hours. Mobile app for customers with 50k daily active users. 500 GB catalog images with fast delivery to users across India.";

function TerraformStudioContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const descriptionParam = searchParams.get("description") || "";
  const optionParam = searchParams.get("option") || "Most optimized";
  const cloudParam = (searchParams.get("cloud") || "aws") as CloudId;

  const [description, setDescription] = useState(descriptionParam || DEFAULT_WORKLOAD);
  const [selectedOption, setSelectedOption] = useState(optionParam);
  const [cloud, setCloud] = useState<CloudId>(cloudParam);

  // Recommendation & Architecture Data
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [loadingRecommendation, setLoadingRecommendation] = useState(true);
  const [inspectedNode, setInspectedNode] = useState<SelectedNode | null>(null);
  const [replayCount, setReplayCount] = useState(0);

  // View mode for the right pane: "architecture" (default) or "report"
  const [viewMode, setViewMode] = useState<"architecture" | "report">("architecture");

  // Modules folder toggle in file explorer sidebar
  const [modulesExpanded, setModulesExpanded] = useState(true);

  // Terraform files state
  const [files, setFiles] = useState<Record<string, string>>({});
  const [activeFile, setActiveFile] = useState<string>("main.tf");
  const [editedCode, setEditedCode] = useState<Record<string, string>>({});
  const [loadingFiles, setLoadingFiles] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [monthlyCost, setMonthlyCost] = useState<number>(469.58);
  const [region, setRegion] = useState<string>("ap-south-1");
  const [allOptions, setAllOptions] = useState<OptionItem[]>([
    { label: "Cheapest", monthly: 245.28, region: "ap-south-1" },
    { label: "Most reliable", monthly: 478.16, region: "ap-south-1" },
    { label: "Most optimized", monthly: 519.04, region: "ap-south-1" },
  ]);
  const [items, setItems] = useState<ArchitectureItem[]>([
    { label: "Amazon Relational Database Service (Multi-AZ)", monthly: 219.07, sku: "rds:mysql-multi-az" },
    { label: "Amazon VPC (NAT Gateway & Egress)", monthly: 149.63, sku: "vpc:nat-gateway" },
    { label: "Amazon Elastic Compute Cloud (Fargate & EC2)", monthly: 24.65, sku: "ec2:t3.medium" },
    { label: "Amazon Simple Storage Service (Standard)", monthly: 10.40, sku: "s3:general-purpose" },
    { label: "AWS Key Management Service & CloudWatch", monthly: 65.83, sku: "kms:cmk" },
  ]);

  // Actions & UI States
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<{
    valid: boolean;
    message: string;
  } | null>(null);

  // Screenshot 3 animated progress card state
  const [isGeneratingReport, setIsGeneratingReport] = useState(false);
  const [progress, setProgress] = useState(62.5);
  const [reportGeneratedNotice, setReportGeneratedNotice] = useState(false);

  // Cost Reports view states (Screenshot 1)
  const [reportTab, setReportTab] = useState<"overview" | "anomalies">("overview");

  // Developer Tools tabs
  const [activeDevTab, setActiveDevTab] = useState<"provider" | "cur" | "import" | "ai">("provider");
  const [copiedCode, setCopiedCode] = useState(false);
  const [downloadingZip, setDownloadingZip] = useState(false);

  const [importToken, setImportToken] = useState("rprt_1abc23456c7c8a90");
  const [copiedImportCmd, setCopiedImportCmd] = useState(false);

  const [aiPrompt, setAiPrompt] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [aiNotice, setAiNotice] = useState<string | null>(null);

  /* Both data-fetching effects below reliably never fired their first
     network call on a genuinely fresh page load -- confirmed by patching
     window.fetch on a brand new tab and watching nothing arrive for 10+
     seconds, while any *subsequent* state change (clicking a pricing tier)
     fired and completed the same fetch correctly every time. That is the
     signature of this client component's initial mount effects running
     during hydration before the browser has actually settled, under this
     Suspense + useSearchParams combination -- not a bug in the fetch logic
     itself, which works once triggered. Gating on a `mounted` flag set from
     its own effect pushes the real data-fetching effects to run on a
     confirmed-stable client render instead of racing hydration. */
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  // TEMPORARY diagnostic instrumentation -- remove once the root cause of
  // the stuck-on-fresh-load bug is found. `tick` proves basic effects/timers
  // fire post-hydration at all; `trace` records exactly how far each loader
  // gets, visible directly in the loading UI instead of only in devtools.
  const [tick, setTick] = useState(0);
  const [trace, setTrace] = useState<string[]>([]);
  const log = (msg: string) =>
    setTrace((prev) => [...prev.slice(-7), `${Date.now() % 100000}ms ${msg}`]);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 500);
    return () => clearInterval(id);
  }, []);

  // 1. Fetch full Recommendation for the Architecture Diagram
  useEffect(() => {
    log(`effect1 fired, mounted=${mounted}`);
    if (!mounted) return;
    let cancelled = false;
    async function loadArchitecture() {
      log("loadArchitecture: start");
      setLoadingRecommendation(true);
      try {
        const text = description.trim() || DEFAULT_WORKLOAD;
        log("loadArchitecture: awaiting api.describe");
        const answer = await api.describe({ description: text, provider: cloud });
        log("loadArchitecture: api.describe resolved");
        if (!cancelled && answer) {
          setRecommendation(answer);
          if (answer.options?.length) {
            setAllOptions(
              answer.options.map((o) => ({
                label: o.label,
                monthly: o.ondemand_monthly_usd ?? o.monthly_usd,
                region: o.region,
              }))
            );
            const match = answer.options.find((o) => o.label === selectedOption);
            if (!match && answer.options[0]) {
              setSelectedOption(answer.options[0].label);
            }
          }
        }
      } catch (e) {
        log(`loadArchitecture: threw ${String(e).slice(0, 60)}`);
        console.warn("Could not load full architecture for diagram:", e);
      } finally {
        log(`loadArchitecture: finally, cancelled=${cancelled}`);
        if (!cancelled) setLoadingRecommendation(false);
      }
    }
    loadArchitecture();
    return () => {
      log("effect1 cleanup (cancelled=true)");
      cancelled = true;
    };
  }, [mounted, description, cloud]);

  // 2. Fetch Terraform inspect files when option, cloud, or description changes
  useEffect(() => {
    log(`effect2 fired, mounted=${mounted}`);
    if (!mounted) return;
    let cancelled = false;
    async function loadFiles() {
      log("loadFiles: start");
      setLoadingFiles(true);
      setError(null);
      try {
        log("loadFiles: awaiting api.describeInspectTf");
        const data = await api.describeInspectTf({
          description: description.trim() || DEFAULT_WORKLOAD,
          option: selectedOption,
          provider: cloud,
        });
        log("loadFiles: describeInspectTf resolved");

        if (!cancelled) {
          const loadedFiles: Record<string, string> = { ...data.files };
          if (!loadedFiles["modules/vpc.tf"]) {
            loadedFiles["modules/vpc.tf"] = `# Reusable VPC Networking Module
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "whichcloud-${cloud}-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["${data.region}a", "${data.region}b", "${data.region}c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = true

  tags = {
    Environment = "production"
    Tier        = "${selectedOption}"
  }
}
`;
          }
          if (!loadedFiles["modules/compute.tf"]) {
            loadedFiles["modules/compute.tf"] = `# Reusable Compute Cluster Module
module "compute_cluster" {
  source = "./modules/compute"

  cluster_name    = "whichcloud-prod-cluster"
  instance_type   = "t3.medium"
  min_capacity    = 2
  max_capacity    = 6
  vpc_id          = module.vpc.vpc_id
  private_subnets = module.vpc.private_subnets
}
`;
          }
          if (!loadedFiles["modules/database.tf"]) {
            loadedFiles["modules/database.tf"] = `# Reusable Managed Database Module
module "managed_db" {
  source = "./modules/database"

  identifier             = "whichcloud-prod-db"
  allocated_storage      = 50
  engine                 = "mysql"
  engine_version         = "8.0"
  instance_class         = "db.t3.medium"
  multi_az               = true
  vpc_security_group_ids = [module.vpc.default_security_group_id]
}
`;
          }

          setFiles(loadedFiles);
          setEditedCode(loadedFiles);
          setMonthlyCost(data.monthly_cost);
          setRegion(data.region);
          if (data.items?.length) {
            setItems(data.items);
          }
          if (!loadedFiles[activeFile]) {
            setActiveFile("main.tf");
          }
        }
      } catch (err: unknown) {
        log(`loadFiles: threw ${String(err).slice(0, 60)}`);
        if (!cancelled) {
          console.error("Failed to load Terraform inspect:", err);
          const fallback = getDefaultFallbackFiles(cloud, selectedOption, monthlyCost, region);
          setFiles(fallback);
          setEditedCode(fallback);
        }
      } finally {
        log(`loadFiles: finally, cancelled=${cancelled}`);
        if (!cancelled) setLoadingFiles(false);
      }
    }
    loadFiles();
    return () => {
      log("effect2 cleanup (cancelled=true)");
      cancelled = true;
    };
  }, [mounted, description, selectedOption, cloud]);

  // Active Option for the Architecture Graph
  const activeOption: Option | null =
    recommendation?.options?.find((o) => o.label === selectedOption) ||
    recommendation?.options?.[0] ||
    null;

  // Code editor text
  const currentCode = editedCode[activeFile] || files[activeFile] || "";

  const handleCodeChange = (newText: string) => {
    setEditedCode((prev) => ({ ...prev, [activeFile]: newText }));
    setValidationResult(null);
  };

  const handleCopyCode = () => {
    navigator.clipboard.writeText(currentCode);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  const handleValidate = async () => {
    setValidating(true);
    try {
      const res = await api.describeValidateTf({
        code: currentCode,
        filename: activeFile,
      });
      setValidationResult(res);
    } catch (e: unknown) {
      setValidationResult({
        valid: false,
        message: e instanceof Error ? e.message : "Validation call failed.",
      });
    } finally {
      setValidating(false);
    }
  };

  const handleCreateReport = () => {
    setIsGeneratingReport(true);
    setProgress(62.5);
    setReportGeneratedNotice(false);

    setTimeout(() => {
      setProgress(88.4);
    }, 1200);

    setTimeout(() => {
      setProgress(100);
      setIsGeneratingReport(false);
      setReportGeneratedNotice(true);
      setViewMode("report");
    }, 2400);
  };

  const handleDownloadZip = async () => {
    setDownloadingZip(true);
    try {
      const blob = await api.describeExportTf({
        description: description.trim() || DEFAULT_WORKLOAD,
        option: selectedOption,
        provider: cloud,
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `whichcloud-${cloud}-${selectedOption.toLowerCase().replace(/\s+/g, "-")}.zip`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to generate Terraform ZIP.");
    } finally {
      setDownloadingZip(false);
    }
  };

  const handleApplyAi = (templatePrompt?: string) => {
    const promptToUse = templatePrompt || aiPrompt;
    if (!promptToUse.trim()) return;
    setAiLoading(true);
    setAiNotice(null);

    setTimeout(() => {
      const snippet = `\n# --- Applied via AI Copilot: ${promptToUse} ---
resource "whichcloud_saved_filter" "ai_curated" {
  title  = "Curated Cost Filter"
  filter = "costs.provider = '${cloud}' AND costs.region = '${region}'"
}

resource "whichcloud_cost_report" "ai_curated_report" {
  title               = "Autonomous Cost Optimization"
  folder_token        = "fldr_auto_finops"
  saved_filter_tokens = [whichcloud_saved_filter.ai_curated.token]
  groupings           = "service,region"
}
`;
      const updated = currentCode + snippet;
      handleCodeChange(updated);
      setAiLoading(false);
      setAiNotice(`Added FinOps Terraform configuration for: "${promptToUse}"`);
      setAiPrompt("");
      setTimeout(() => setAiNotice(null), 4000);
    }, 900);
  };

  return (
    <div className="flex min-h-screen flex-col bg-canvas text-ink">
      {/* ── TOP HEADER ────────────────────────────────────────────────────────── */}
      <header className="sticky top-16 z-20 flex flex-wrap items-center justify-between gap-3 border-b border-line bg-surface/95 px-5 py-2.5 backdrop-blur">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-canvas px-2.5 py-1.5 text-[12px] font-medium text-ink-2 transition hover:border-line-strong hover:text-ink"
            title="Return to Architecture Workspace"
          >
            <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M15 10H5m5-5l-5 5 5 5" />
            </svg>
            <span>Workspace</span>
          </Link>
          <span className="h-4 w-px bg-line" />
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#5C4EE5]/15 text-[#5C4EE5]">
              <TerraformLogo className="h-4.5 w-4.5" />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-[14px] font-bold text-ink">Terraform IaC Studio</h1>
                <span className="rounded bg-[#5C4EE5]/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-[#5C4EE5]">
                  Live Sync
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Cloud Switcher */}
        <div className="flex items-center gap-1.5">
          <div className="flex items-center rounded-lg border border-line bg-canvas p-0.5">
            {CLOUDS.map((c) => (
              <button
                key={c.id}
                onClick={() => setCloud(c.id)}
                className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[11.5px] font-semibold transition-all ${
                  cloud === c.id
                    ? "bg-surface text-ink shadow-sm border border-line"
                    : "text-ink-3 hover:text-ink"
                }`}
              >
                <Icon
                  icon={
                    c.id === "aws"
                      ? "logos:aws"
                      : c.id === "gcp"
                      ? "logos:google-cloud"
                      : "logos:microsoft-azure"
                  }
                  className="h-3 w-3"
                />
                <span className="uppercase">{c.id}</span>
              </button>
            ))}
          </div>

          {/* Architecture Tier Switcher (Screenshot 2) */}
          <div className="flex items-center gap-1 rounded-xl border border-line bg-canvas p-1">
            {allOptions.map((opt) => (
              <button
                key={opt.label}
                onClick={() => setSelectedOption(opt.label)}
                className={`flex items-center gap-2 rounded-lg border px-3 py-1 transition-all ${
                  opt.label === selectedOption
                    ? "border-[#5C4EE5] bg-[#5C4EE5]/10 shadow-sm text-ink"
                    : "border-transparent text-ink-3 hover:border-line hover:text-ink"
                }`}
              >
                <span className="text-[12px] font-medium">{opt.label}</span>
                <span className="font-mono text-[12px] font-bold text-ink">
                  ${opt.monthly.toFixed(2)}
                  <span className="text-[10px] font-normal text-ink-3">/mo</span>
                </span>
                {opt.label === "Most optimized" && (
                  <span className="rounded bg-emerald-500/15 px-1 py-0.2 text-[9px] font-semibold uppercase text-emerald-500">
                    PICK
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Right Header: View Mode Switcher + Download */}
        <div className="flex items-center gap-2">
          {/* View Mode Toggle: Architecture Diagram vs Cost Report */}
          <div className="flex items-center rounded-xl border border-line bg-canvas p-1 text-[12px] font-medium shadow-2xs">
            <button
              type="button"
              onClick={() => setViewMode("architecture")}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 transition-all ${
                viewMode === "architecture"
                  ? "bg-[#5C4EE5] text-white shadow-sm font-semibold"
                  : "text-ink-2 hover:text-ink hover:bg-sunk"
              }`}
            >
              <svg viewBox="0 0 20 20" className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <rect x="2" y="3" width="6" height="5" rx="1" />
                <rect x="12" y="3" width="6" height="5" rx="1" />
                <rect x="7" y="12" width="6" height="5" rx="1" />
                <path d="M5 8v2a2 2 0 002 2h3m5-4v2a2 2 0 01-2 2h-3m0 0v-2" />
              </svg>
              <span>Architecture</span>
            </button>
            <button
              type="button"
              onClick={() => setViewMode("report")}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 transition-all ${
                viewMode === "report"
                  ? "bg-[#5C4EE5] text-white shadow-sm font-semibold"
                  : "text-ink-2 hover:text-ink hover:bg-sunk"
              }`}
            >
              <svg viewBox="0 0 20 20" className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M3 17h14" />
                <path d="M6 14v-4" />
                <path d="M10 14V6" />
                <path d="M14 14v-6" />
                <path d="M4 10l5-4 4 2 4-5" />
              </svg>
              <span>Cost Report</span>
            </button>
          </div>

          <button
            type="button"
            onClick={handleDownloadZip}
            disabled={downloadingZip}
            className="inline-flex items-center gap-1.5 rounded-xl bg-[#5C4EE5] px-3.5 py-1.5 text-[12.5px] font-semibold text-white shadow-sm transition hover:bg-[#4d3fd4] active:scale-[0.98] disabled:opacity-60 shrink-0"
          >
            <svg viewBox="0 0 20 20" className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M4 14v2a2 2 0 002 2h8a2 2 0 002-2v-2M10 3v9m0 0l-3-3m3 3l3-3" />
            </svg>
            <span>{downloadingZip ? "Packaging…" : "Download ZIP"}</span>
          </button>
        </div>
      </header>

      {/* Subheader: Workload context banner */}
      <div className="flex items-center justify-between border-b border-line/60 bg-surface/50 px-5 py-1.5 text-[11.5px] text-ink-3">
        <div className="flex items-center gap-2 overflow-hidden truncate">
          <span className="font-semibold text-ink-2 uppercase tracking-wide">Workload:</span>
          <span className="truncate italic font-mono text-ink-2">“{description}”</span>
        </div>
        <div className="flex shrink-0 items-center gap-3 font-mono text-[11px]">
          <span>Region: <strong className="text-ink">{region}</strong></span>
          <span>•</span>
          <span>Provider: <strong className="uppercase text-ink">{cloud}</strong></span>
        </div>
      </div>

      {/* ── SCREENSHOT 3: FLOATING PROGRESS MODAL ────────────────────────────── */}
      {isGeneratingReport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="w-full max-w-md rounded-2xl border border-line bg-surface p-6 shadow-2xl">
            {/* Top Stat & Spinning indicator */}
            <div className="flex items-center justify-between">
              <div className="flex items-baseline gap-1.5">
                <span className="font-mono text-4xl font-extrabold tracking-tight text-ink">
                  {progress.toFixed(1)}
                </span>
                <span className="font-mono text-lg font-medium text-ink-3">/100%</span>
              </div>
              <div className="flex h-7 w-7 animate-spin items-center justify-center text-brand">
                <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <circle cx="12" cy="12" r="10" strokeOpacity="0.25" />
                  <path d="M12 2a10 10 0 0110 10" strokeLinecap="round" />
                </svg>
              </div>
            </div>

            <p className="mt-2 text-[13.5px] font-medium text-ink-2">
              Generating cost report via Terraform...
            </p>

            {/* Striped animated progress bar from Screenshot 3 */}
            <div className="mt-4 grid grid-cols-2 gap-2">
              <div className="h-8 w-full overflow-hidden rounded-xl border border-brand/40 bg-brand/10 p-1">
                <div
                  className="h-full w-full rounded-lg transition-all duration-300"
                  style={{
                    backgroundImage: `repeating-linear-gradient(
                      -45deg,
                      rgba(124, 58, 237, 0.4),
                      rgba(124, 58, 237, 0.4) 8px,
                      rgba(124, 58, 237, 0.15) 8px,
                      rgba(124, 58, 237, 0.15) 16px
                    )`,
                  }}
                />
              </div>
              <div className="h-8 w-full overflow-hidden rounded-xl border border-brand/20 bg-brand/5 p-1">
                <div
                  className="h-full w-full rounded-lg transition-all duration-300 opacity-60"
                  style={{
                    backgroundImage: `repeating-linear-gradient(
                      -45deg,
                      rgba(124, 58, 237, 0.25),
                      rgba(124, 58, 237, 0.25) 8px,
                      rgba(124, 58, 237, 0.05) 8px,
                      rgba(124, 58, 237, 0.05) 16px
                    )`,
                  }}
                />
              </div>
            </div>

            {/* Mac Code Window from Screenshot 3 */}
            <div className="mt-5 overflow-hidden rounded-xl border border-line bg-canvas/80 text-[12px] font-mono shadow-inner">
              <div className="flex items-center gap-1.5 border-b border-line bg-surface/60 px-3 py-2">
                <span className="h-2.5 w-2.5 rounded-full bg-red-500/80" />
                <span className="h-2.5 w-2.5 rounded-full bg-yellow-500/80" />
                <span className="h-2.5 w-2.5 rounded-full bg-green-500/80" />
                <span className="ml-2 text-[10.5px] text-ink-3">cost-allocation.tf</span>
              </div>
              <pre className="overflow-x-auto p-3 text-ink-2 leading-relaxed">
                <code>{`locals {
  cost_centers   = yamldecode(file("cost-centers.yaml")).cost_centers
  business_units = toset([for k, cost_center in local.cost_centers : cost_center.business_unit])
}`}</code>
              </pre>
            </div>
          </div>
        </div>
      )}

      {/* ── SPLIT VIEW: TERRAFORM ON LEFT, ARCHITECTURE DIAGRAM ON RIGHT ─────── */}
      <main className="flex-1 p-4 lg:p-5">
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          {/* ════════════════════════════════════════════════════════════════════
              LEFT COLUMN: TERRAFORM CONFIGURATION WITH FILE EXPLORER SIDEBAR
             ════════════════════════════════════════════════════════════════════ */}
          <section className="flex flex-col rounded-2xl border border-line bg-surface shadow-sm overflow-hidden h-[740px]">
            {/* Header with Authentic Terraform Vector Logo, Title & Actions */}
            <div className="flex items-center justify-between border-b border-line px-4 py-3 bg-surface">
              <div className="flex items-center gap-2">
                <TerraformLogo className="h-4.5 w-4.5" />
                <h2 className="text-[13.5px] font-semibold text-ink">Terraform Configuration</h2>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleCopyCode}
                  className="inline-flex items-center gap-1 rounded-md border border-line px-2.5 py-1 text-[11.5px] font-medium text-ink-2 hover:border-line-strong hover:text-ink transition"
                >
                  {copiedCode ? (
                    <svg viewBox="0 0 20 20" className="h-3.5 w-3.5 text-emerald-500" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M4 10l4 4L16 6" />
                    </svg>
                  ) : (
                    <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="7" y="7" width="10" height="10" rx="2" />
                      <path d="M4 13V5a2 2 0 012-2h8" />
                    </svg>
                  )}
                  <span>{copiedCode ? "Copied" : "Copy"}</span>
                </button>
                {/* 3 dots menu from Screenshot 1 */}
                <button
                  type="button"
                  className="rounded p-1 text-ink-3 hover:text-ink hover:bg-sunk transition"
                  title="More options"
                >
                  <svg viewBox="0 0 20 20" className="h-4 w-4" fill="currentColor">
                    <circle cx="5" cy="10" r="1.5" />
                    <circle cx="10" cy="10" r="1.5" />
                    <circle cx="15" cy="10" r="1.5" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Split Body: File Tree Sidebar on Left, Code Editor on Right */}
            <div className="flex flex-1 overflow-hidden min-h-0">
              {/* ── LEFT FILE EXPLORER SIDEBAR (MATCHING USER SCREENSHOT) ── */}
              <aside className="w-48 sm:w-52 border-r border-line bg-canvas/30 p-2.5 flex flex-col gap-1 shrink-0 overflow-y-auto select-none">
                {/* 1. main.tf */}
                <button
                  type="button"
                  onClick={() => setActiveFile("main.tf")}
                  className={`flex items-center gap-2 w-full rounded-lg px-2.5 py-1.5 text-[12.5px] transition-all text-left ${
                    activeFile === "main.tf"
                      ? "bg-[#F3F0FF] dark:bg-[#5C4EE5]/20 text-[#5C4EE5] dark:text-[#A78BFA] font-semibold border border-purple-200/80 dark:border-purple-800/40 shadow-xs"
                      : "text-ink-2 hover:text-ink hover:bg-surface/80 border border-transparent font-medium"
                  }`}
                >
                  <span className="font-mono text-[11px] font-bold text-[#5C4EE5] dark:text-[#A78BFA]">&lt; &gt;</span>
                  <span className="truncate">main.tf</span>
                </button>

                {/* 2. variables.tf */}
                <button
                  type="button"
                  onClick={() => setActiveFile("variables.tf")}
                  className={`flex items-center gap-2 w-full rounded-lg px-2.5 py-1.5 text-[12.5px] transition-all text-left ${
                    activeFile === "variables.tf"
                      ? "bg-[#F3F0FF] dark:bg-[#5C4EE5]/20 text-[#5C4EE5] dark:text-[#A78BFA] font-semibold border border-purple-200/80 dark:border-purple-800/40 shadow-xs"
                      : "text-ink-2 hover:text-ink hover:bg-surface/80 border border-transparent font-medium"
                  }`}
                >
                  <svg viewBox="0 0 20 20" className="h-3.5 w-3.5 opacity-70 shrink-0" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="10" cy="10" r="7" />
                    <circle cx="10" cy="10" r="2.5" fill="currentColor" />
                  </svg>
                  <span className="truncate">variables.tf</span>
                </button>

                {/* 3. modules / (Collapsible Folder) */}
                <div className="flex flex-col gap-0.5">
                  <button
                    type="button"
                    onClick={() => {
                      setModulesExpanded((prev) => !prev);
                      if (!activeFile.startsWith("modules/")) {
                        setActiveFile("modules/vpc.tf");
                      }
                    }}
                    className={`flex items-center justify-between w-full rounded-lg px-2.5 py-1.5 text-[12.5px] transition-all text-left ${
                      activeFile.startsWith("modules/")
                        ? "text-[#5C4EE5] dark:text-[#A78BFA] font-semibold hover:bg-surface/80"
                        : "text-ink-2 hover:text-ink hover:bg-surface/80 font-medium"
                    }`}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <svg viewBox="0 0 20 20" className="h-3.5 w-3.5 text-amber-500/80 shrink-0" fill="currentColor">
                        <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
                      </svg>
                      <span className="truncate">modules /</span>
                    </div>
                    <svg
                      className={`h-3 w-3 text-ink-3 transition-transform shrink-0 ${
                        modulesExpanded ? "rotate-90" : ""
                      }`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path d="M7 5l5 5-5 5" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </button>

                  {modulesExpanded && (
                    <div className="ml-4 pl-2 border-l border-line/70 flex flex-col gap-0.5 animate-in fade-in-50 duration-150">
                      {["modules/vpc.tf", "modules/compute.tf", "modules/database.tf"].map((modFile) => {
                        const isModActive = activeFile === modFile;
                        const shortName = modFile.replace("modules/", "");
                        return (
                          <button
                            key={modFile}
                            type="button"
                            onClick={() => setActiveFile(modFile)}
                            className={`flex items-center gap-1.5 w-full rounded-md px-2 py-1 text-[11.5px] transition-all text-left ${
                              isModActive
                                ? "bg-[#F3F0FF] dark:bg-[#5C4EE5]/20 text-[#5C4EE5] dark:text-[#A78BFA] font-semibold shadow-xs"
                                : "text-ink-3 hover:text-ink hover:bg-surface/60 font-medium"
                            }`}
                          >
                            <span className="font-mono text-[10px] opacity-70">&lt;&gt;</span>
                            <span className="truncate">{shortName}</span>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* 4. outputs.tf */}
                <button
                  type="button"
                  onClick={() => setActiveFile("outputs.tf")}
                  className={`flex items-center gap-2 w-full rounded-lg px-2.5 py-1.5 text-[12.5px] transition-all text-left ${
                    activeFile === "outputs.tf"
                      ? "bg-[#F3F0FF] dark:bg-[#5C4EE5]/20 text-[#5C4EE5] dark:text-[#A78BFA] font-semibold border border-purple-200/80 dark:border-purple-800/40 shadow-xs"
                      : "text-ink-2 hover:text-ink hover:bg-surface/80 border border-transparent font-medium"
                  }`}
                >
                  <svg viewBox="0 0 20 20" className="h-3.5 w-3.5 opacity-70 shrink-0" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="10" cy="10" r="7" />
                    <circle cx="10" cy="10" r="2.5" fill="currentColor" />
                  </svg>
                  <span className="truncate">outputs.tf</span>
                </button>

                {/* 5. cost_reports.tf */}
                <button
                  type="button"
                  onClick={() => setActiveFile("cost_reports.tf")}
                  className={`flex items-center gap-2 w-full rounded-lg px-2.5 py-1.5 text-[12.5px] transition-all text-left ${
                    activeFile === "cost_reports.tf"
                      ? "bg-[#F3F0FF] dark:bg-[#5C4EE5]/20 text-[#5C4EE5] dark:text-[#A78BFA] font-semibold border border-purple-200/80 dark:border-purple-800/40 shadow-xs"
                      : "text-ink-2 hover:text-ink hover:bg-surface/80 border border-transparent font-medium"
                  }`}
                >
                  <svg viewBox="0 0 20 20" className="h-3.5 w-3.5 text-[#5C4EE5] shrink-0" fill="currentColor">
                    <path d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" />
                  </svg>
                  <span className="truncate">cost_reports.tf</span>
                </button>

                {/* 6. terraform.tfvars.example */}
                <button
                  type="button"
                  onClick={() => setActiveFile("terraform.tfvars.example")}
                  className={`flex items-center gap-2 w-full rounded-lg px-2.5 py-1.5 text-[12.5px] transition-all text-left ${
                    activeFile === "terraform.tfvars.example"
                      ? "bg-[#F3F0FF] dark:bg-[#5C4EE5]/20 text-[#5C4EE5] dark:text-[#A78BFA] font-semibold border border-purple-200/80 dark:border-purple-800/40 shadow-xs"
                      : "text-ink-2 hover:text-ink hover:bg-surface/80 border border-transparent font-medium"
                  }`}
                >
                  <svg viewBox="0 0 20 20" className="h-3.5 w-3.5 opacity-70 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.75">
                    <path d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947z" />
                    <circle cx="10" cy="10" r="3" />
                  </svg>
                  <span className="truncate">terraform.tfvars</span>
                </button>

                {/* 7. README.md */}
                <button
                  type="button"
                  onClick={() => setActiveFile("README.md")}
                  className={`flex items-center gap-2 w-full rounded-lg px-2.5 py-1.5 text-[12.5px] transition-all text-left ${
                    activeFile === "README.md"
                      ? "bg-[#F3F0FF] dark:bg-[#5C4EE5]/20 text-[#5C4EE5] dark:text-[#A78BFA] font-semibold border border-purple-200/80 dark:border-purple-800/40 shadow-xs"
                      : "text-ink-2 hover:text-ink hover:bg-surface/80 border border-transparent font-medium"
                  }`}
                >
                  <svg viewBox="0 0 20 20" className="h-3.5 w-3.5 opacity-70 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.75">
                    <rect x="4" y="3" width="12" height="14" rx="1.5" />
                    <path d="M7 7h6M7 10h6M7 13h4" />
                  </svg>
                  <span className="truncate">README.md</span>
                </button>
              </aside>

              {/* ── RIGHT CODE EDITOR AREA ── */}
              <div className="relative flex-1 flex flex-col min-w-0 overflow-hidden bg-canvas/90">
                {/* File Sub-header Bar */}
                <div className="flex items-center justify-between border-b border-line/60 bg-surface/40 px-4 py-1.5 text-[11.5px] font-mono">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="font-semibold text-ink truncate">{activeFile}</span>
                    <span className="text-[10.5px] text-ink-3">
                      ({currentCode.split("\n").length} lines)
                    </span>
                  </div>
                  <span className="rounded bg-canvas px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-ink-3 border border-line/70">
                    {activeFile.endsWith(".md") ? "Markdown" : "HCL"}
                  </span>
                </div>

                {loadingFiles ? (
                  <div className="flex flex-1 flex-col items-center justify-center gap-2 text-[12.5px] font-mono text-ink-3 p-4 text-left">
                    <div>Generating Terraform IaC for {selectedOption} ({cloud.toUpperCase()})...</div>
                    <div className="w-full max-w-xl text-[10px] text-ink-2 border border-line rounded p-2 mt-2">
                      <div>DEBUG tick={tick} mounted={String(mounted)}</div>
                      {trace.map((t, i) => <div key={i}>{t}</div>)}
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-1 overflow-hidden font-mono text-[12px] leading-relaxed">
                    {/* Line Numbers */}
                    <div
                      className="select-none overflow-y-hidden border-r border-line/40 bg-surface/30 px-3 py-4 text-right text-ink-3 font-mono text-[11px]"
                      aria-hidden="true"
                    >
                      {currentCode.split("\n").map((_, i) => (
                        <div key={i} className="h-5">
                          {i + 1}
                        </div>
                      ))}
                    </div>

                    {/* Textarea Code Input */}
                    <textarea
                      value={currentCode}
                      onChange={(e) => handleCodeChange(e.target.value)}
                      spellCheck={false}
                      className="h-full flex-1 resize-none bg-transparent p-4 font-mono text-ink outline-none focus:ring-0 focus:outline-none"
                      placeholder="Terraform HCL configuration..."
                    />
                  </div>
                )}
              </div>
            </div>

            {/* Bottom Footer: Validation Feedback & Action Buttons */}
            <div className="border-t border-line bg-surface p-3.5">
              {validationResult && (
                <div
                  className={`mb-3 flex items-center gap-2 rounded-xl p-2.5 text-[12px] font-mono ${
                    validationResult.valid
                      ? "border border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                      : "border border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-400"
                  }`}
                >
                  {validationResult.valid ? (
                    <svg viewBox="0 0 20 20" className="h-4 w-4 shrink-0 text-emerald-500" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M4 10l4 4L16 6" />
                    </svg>
                  ) : (
                    <svg viewBox="0 0 20 20" className="h-4 w-4 shrink-0 text-red-500" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="10" cy="10" r="8" />
                      <line x1="7" y1="7" x2="13" y2="13" />
                      <line x1="13" y1="7" x2="7" y2="13" />
                    </svg>
                  )}
                  <span>{validationResult.message}</span>
                </div>
              )}

              {reportGeneratedNotice && (
                <div className="mb-3 flex items-center justify-between rounded-xl border border-brand/30 bg-brand/10 p-2.5 text-[12px] text-brand">
                  <span className="font-medium">
                    ✨ Cost report generated successfully via Terraform provider!
                  </span>
                  <button
                    type="button"
                    onClick={() => setViewMode("report")}
                    className="underline font-semibold hover:opacity-80"
                  >
                    View in Right Pane
                  </button>
                </div>
              )}

              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={handleValidate}
                  disabled={validating}
                  className="flex-1 rounded-xl border border-line bg-canvas py-2 text-[13px] font-semibold text-ink transition hover:border-line-strong hover:bg-sunk disabled:opacity-60"
                >
                  {validating ? "Validating HCL…" : "Validate"}
                </button>
                <button
                  type="button"
                  onClick={handleCreateReport}
                  className="flex-1 rounded-xl bg-[#5C4EE5] py-2 text-[13px] font-semibold text-white shadow-sm transition hover:bg-[#4d3fd4]"
                >
                  Create Report
                </button>
              </div>
            </div>
          </section>

          {/* ════════════════════════════════════════════════════════════════════
              RIGHT COLUMN: ARCHITECTURE DIAGRAM (OR COST REPORT TOGGLE)
             ════════════════════════════════════════════════════════════════════ */}
          <section className="flex flex-col rounded-2xl border border-line bg-surface shadow-sm overflow-hidden h-[740px]">
            {viewMode === "architecture" ? (
              /* ── 1. ARCHITECTURE DIAGRAM VIEW (SCREENSHOT 2) ── */
              <div className="relative flex flex-col h-full overflow-hidden">
                {/* Right Pane Header */}
                <div className="flex items-center justify-between border-b border-line px-4 py-3 bg-surface shrink-0">
                  <div className="flex items-center gap-2">
                    <span className="flex h-5 w-5 items-center justify-center rounded bg-brand/15 text-brand">
                      <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
                        <rect x="2" y="3" width="6" height="5" rx="1" />
                        <rect x="12" y="3" width="6" height="5" rx="1" />
                        <rect x="7" y="12" width="6" height="5" rx="1" />
                        <path d="M5 8v2a2 2 0 002 2h3m5-4v2a2 2 0 01-2 2h-3m0 0v-2" />
                      </svg>
                    </span>
                    <h2 className="text-[13.5px] font-semibold text-ink">
                      Architecture Topology — {selectedOption}
                    </h2>
                    <span className="rounded-full border border-line px-2 py-0.5 font-mono text-[10.5px] text-ink-3">
                      {activeOption?.topology?.nodes?.length || 15} services • {region}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setReplayCount((c) => c + 1)}
                      className="inline-flex items-center gap-1 rounded-md border border-line px-2 py-1 text-[11px] font-medium text-ink-2 hover:text-ink hover:border-line-strong transition"
                      title="Replay architecture layout animation"
                    >
                      <svg viewBox="0 0 20 20" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M3 10a7 7 0 112 5.07M3 10V5m0 5h5" />
                      </svg>
                      <span>Replay</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setViewMode("report")}
                      className="inline-flex items-center gap-1.5 rounded-md border border-line bg-canvas px-2.5 py-1 text-[11px] font-medium text-brand hover:border-brand transition"
                    >
                      <svg viewBox="0 0 20 20" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M3 17h14M6 14v-4m4 4V6m4 8v-6" />
                      </svg>
                      <span>Switch to Cost Report</span>
                    </button>
                  </div>
                </div>

                {/* Graph Stage */}
                <div className="relative flex-1 w-full h-full overflow-hidden bg-canvas">
                  {loadingRecommendation ? (
                    <div className="flex h-full items-center justify-center text-[12.5px] font-mono text-ink-3">
                      Building live architecture diagram for {selectedOption}...
                    </div>
                  ) : activeOption?.topology?.nodes?.length ? (
                    <ArchitectureGraph
                      graphKey={`${selectedOption}-${cloud}-${replayCount}`}
                      cloud={cloud}
                      nodes={activeOption.topology.nodes}
                      edges={activeOption.topology.edges}
                      onNodeSelect={setInspectedNode}
                      playing
                      overlayHeader={
                        <div className="flex items-center gap-1.5 rounded-xl border border-line bg-surface/95 p-1.5 shadow-lg backdrop-blur">
                          {allOptions.map((option) => (
                            <button
                              key={option.label}
                              onClick={() => setSelectedOption(option.label)}
                              className={`flex shrink-0 items-center gap-2 rounded-lg border px-3 py-1.5 transition-all ${
                                option.label === selectedOption
                                  ? "border-brand bg-brand/10 shadow-xs text-ink"
                                  : "border-line bg-canvas hover:border-line-strong hover:bg-sunk"
                              }`}
                            >
                              <span className="text-[12.5px] font-semibold text-ink">
                                {option.label}
                              </span>
                              <span className="font-mono text-[12.5px] font-bold text-ink">
                                ${option.monthly.toFixed(2)}
                              </span>
                            </button>
                          ))}
                        </div>
                      }
                    />
                  ) : (
                    <div className="flex h-full flex-col items-center justify-center p-6 text-center text-ink-3">
                      <p className="text-[13px] font-medium text-ink">No topology nodes found</p>
                      <p className="text-[12px] text-ink-3 mt-1">
                        Try switching tiers or providers above to load a diagram.
                      </p>
                    </div>
                  )}

                  {/* Node Inspector Flyout */}
                  {inspectedNode && (
                    <div className="absolute top-4 right-4 z-20 w-80 shadow-2xl animate-in slide-in-from-right-4 duration-200">
                      <Inspector
                        node={inspectedNode}
                        option={activeOption}
                        onClose={() => setInspectedNode(null)}
                      />
                    </div>
                  )}
                </div>
              </div>
            ) : (
              /* ── 2. COST REPORTS: ALL RESOURCES VIEW (SCREENSHOT 1) ── */
              <div className="flex flex-col h-full overflow-y-auto">
                {/* Cost Report Top Bar with Genuine Vantage/WhichCloud Blue Badge */}
                <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
                  <div className="flex items-center gap-3">
                    {/* Authentic Cost Reports Icon */}
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#3B82F6] text-white shadow-xs">
                      <CostReportsIcon className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="text-[11px] font-semibold uppercase tracking-wider text-ink-3">
                        Cost Reports
                      </div>
                      <div className="text-[15px] font-bold text-ink">All Resources</div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setViewMode("architecture")}
                      className="inline-flex items-center gap-1 rounded-lg border border-line px-2.5 py-1 text-[11.5px] font-medium text-ink-2 hover:border-line-strong hover:text-ink transition"
                    >
                      <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
                        <rect x="2" y="3" width="6" height="5" rx="1" />
                        <rect x="12" y="3" width="6" height="5" rx="1" />
                        <rect x="7" y="12" width="6" height="5" rx="1" />
                        <path d="M5 8v2a2 2 0 002 2h3m5-4v2a2 2 0 01-2 2h-3m0 0v-2" />
                      </svg>
                      <span>Back to Diagram</span>
                    </button>
                    <button
                      type="button"
                      className="rounded-lg bg-[#5C4EE5] px-4 py-1.5 text-[12.5px] font-semibold text-white shadow-sm transition hover:bg-[#4d3fd4]"
                    >
                      Save
                    </button>
                  </div>
                </div>

                {/* Report Tabs & Controls */}
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-2">
                  <div className="flex items-center gap-4 text-[13px] font-semibold">
                    <button
                      type="button"
                      onClick={() => setReportTab("overview")}
                      className={`relative pb-2 transition ${
                        reportTab === "overview"
                          ? "text-[#5C4EE5] border-b-2 border-[#5C4EE5]"
                          : "text-ink-3 hover:text-ink"
                      }`}
                    >
                      Overview
                    </button>
                    <button
                      type="button"
                      onClick={() => setReportTab("anomalies")}
                      className={`relative pb-2 transition ${
                        reportTab === "anomalies"
                          ? "text-[#5C4EE5] border-b-2 border-[#5C4EE5]"
                          : "text-ink-3 hover:text-ink"
                      }`}
                    >
                      Anomalies
                    </button>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1 text-[12px] font-medium text-ink-2 hover:bg-sunk transition"
                    >
                      <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M3 4a1 1 0 011-1h12a1 1 0 011 1v2.5a1 1 0 01-.293.707l-4.414 4.414v4.586l-4 2v-6.586L3.293 7.207A1 1 0 013 6.5V4z" />
                      </svg>
                      <span>Filter</span>
                    </button>
                    <button
                      type="button"
                      className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1 text-[12px] font-medium text-ink-2 hover:bg-sunk transition"
                    >
                      <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
                        <rect x="3" y="4" width="14" height="14" rx="2" />
                        <line x1="13" y1="2" x2="13" y2="5" />
                        <line x1="7" y1="2" x2="7" y2="5" />
                        <line x1="3" y1="8" x2="17" y2="8" />
                      </svg>
                      <span>Apr 1 - Apr 30</span>
                    </button>
                    <button
                      type="button"
                      className="inline-flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1 text-[12px] font-medium text-ink-2 hover:bg-sunk transition"
                    >
                      <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M9.325 3.317a1.5 1.5 0 012.35 0 1.5 1.5 0 002.122.336 1.5 1.5 0 011.662 1.662 1.5 1.5 0 00.336 2.122 1.5 1.5 0 010 2.35 1.5 1.5 0 00-.336 2.122 1.5 1.5 0 01-1.662 1.662 1.5 1.5 0 00-2.122.336 1.5 1.5 0 01-2.35 0 1.5 1.5 0 00-2.122-.336 1.5 1.5 0 01-1.662-1.662 1.5 1.5 0 00-.336-2.122 1.5 1.5 0 010-2.35 1.5 1.5 0 00.336-2.122 1.5 1.5 0 011.662-1.662 1.5 1.5 0 002.122-.336z" />
                        <circle cx="10.5" cy="10" r="2.5" />
                      </svg>
                    </button>
                  </div>
                </div>

                {/* Big Accrued Cost Number - Synchronized Live with Active Architecture Option */}
                {(() => {
                  const liveMonthly =
                    activeOption?.ondemand_monthly_usd ??
                    activeOption?.monthly_usd ??
                    monthlyCost;

                  const currentItems =
                    activeOption?.items && activeOption.items.length > 0
                      ? activeOption.items.map((it) => ({
                          label: it.label,
                          monthly: it.monthly_usd,
                          sku: it.sku,
                        }))
                      : items && items.length > 0
                      ? items
                      : [
                          { label: "Compute x 1 (1-yr commitment)", monthly: liveMonthly * 0.28, sku: "ec2:t3.medium" },
                          { label: "Database (1-yr reserved)", monthly: liveMonthly * 0.38, sku: "rds:mysql-multi-az" },
                          { label: "Object storage (standard)", monthly: liveMonthly * 0.08, sku: "s3:general-purpose" },
                          { label: "Object storage (infrequent access)", monthly: liveMonthly * 0.05, sku: "s3:ia" },
                          { label: "Monitoring & CloudWatch", monthly: liveMonthly * 0.07, sku: "cloudwatch:logs" },
                          { label: "NAT Gateway x 1 & Egress", monthly: liveMonthly * 0.14, sku: "vpc:nat-gateway" },
                        ];

                  return (
                    <>
                      <div className="px-5 pt-4 pb-2">
                        <div className="text-3xl font-extrabold tracking-tight text-ink font-mono">
                          ${liveMonthly.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </div>
                        <div className="text-[12px] text-ink-3 mt-0.5">
                          Accrued Costs / Month • {selectedOption} ({cloud.toUpperCase()})
                        </div>
                      </div>

                      {/* Interactive Curve Chart (Screenshot 1) */}
                      <div className="relative px-5 py-2">
                        <div className="flex items-center gap-4 text-[11.5px] mb-3">
                          <span className="flex items-center gap-1.5 text-ink-2 font-medium">
                            <span className="h-2.5 w-2.5 rounded-full bg-[#5C4EE5]" />
                            Accrued Costs
                          </span>
                          <span className="flex items-center gap-1.5 text-ink-3">
                            <span className="h-2.5 w-2.5 rounded-full bg-[#A78BFA]" />
                            Per Active Session
                          </span>
                        </div>

                        <div className="relative h-44 w-full">
                          <svg viewBox="0 0 500 160" className="h-full w-full overflow-visible">
                            <defs>
                              <linearGradient id="tfCostGrad" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#5C4EE5" stopOpacity="0.25" />
                                <stop offset="100%" stopColor="#5C4EE5" stopOpacity="0.0" />
                              </linearGradient>
                            </defs>

                            {/* Area under curve */}
                            <path
                              d="M 40 120 Q 90 140 140 130 T 240 120 T 340 130 T 420 100 T 480 30 L 480 150 L 40 150 Z"
                              fill="url(#tfCostGrad)"
                            />

                            {/* Solid Accrued Costs Curve */}
                            <path
                              d="M 40 120 Q 90 140 140 130 T 240 120 T 340 130 T 420 100 T 480 30"
                              fill="none"
                              stroke="#5C4EE5"
                              strokeWidth="2"
                            />

                            {/* Light/Dashed Per Active Session Curve */}
                            <path
                              d="M 40 130 Q 90 150 140 140 T 240 130 T 340 140 T 420 120 T 480 80"
                              fill="none"
                              stroke="#A78BFA"
                              strokeWidth="1.5"
                              strokeDasharray="4 4"
                            />

                            {/* Crosshair indicator line */}
                            <line x1="420" y1="20" x2="420" y2="150" stroke="#71717A" strokeWidth="1.5" />
                            <polygon points="415,20 425,20 420,28" fill="#71717A" />

                            {/* Tooltip Card Synchronized with Live Architecture Cost */}
                            <foreignObject x="260" y="35" width="200" height="80">
                              <div className="rounded-xl border border-line bg-surface/95 backdrop-blur p-2.5 shadow-xl text-[11px]">
                                <div className="flex items-center justify-between text-ink">
                                  <span className="flex items-center gap-1">
                                    <span className="h-1.5 w-1.5 rounded-full bg-[#5C4EE5]" />
                                    Accrued Costs:
                                  </span>
                                  <span className="font-mono font-bold">${liveMonthly.toFixed(2)}</span>
                                </div>
                                <div className="flex items-center justify-between text-ink-3 mt-1.5">
                                  <span className="flex items-center gap-1">
                                    <span className="h-1.5 w-1.5 rounded-full bg-[#A78BFA]" />
                                    Per Active Session:
                                  </span>
                                  <span className="font-mono font-bold">${(liveMonthly * 0.78).toFixed(2)}</span>
                                </div>
                              </div>
                            </foreignObject>

                            {/* X-axis labels */}
                            <g className="text-[9px] fill-zinc-400 font-mono" textAnchor="middle">
                              <text x="40" y="160">01.05</text>
                              <text x="120" y="160">06.05</text>
                              <text x="210" y="160">12.05</text>
                              <text x="300" y="160">18.05</text>
                              <text x="390" y="160">23.05</text>
                              <text x="470" y="160">29.05</text>
                            </g>
                          </svg>
                        </div>
                      </div>

                      {/* Service Breakdown Table (Screenshot 1) */}
                      <div className="mt-2 flex-1 border-t border-line">
                        <div className="grid grid-cols-12 border-b border-line bg-canvas/40 px-5 py-2 text-[11px] font-semibold text-ink-3 uppercase tracking-wider">
                          <div className="col-span-6">Service</div>
                          <div className="col-span-3 text-right">Accrued Costs</div>
                          <div className="col-span-3 text-right">Previous Period</div>
                        </div>

                        <div className="divide-y divide-line/60">
                          {currentItems.map((it, idx) => (
                            <div
                              key={idx}
                              className="grid grid-cols-12 items-center px-5 py-2.5 text-[12px] hover:bg-sunk/50 transition"
                            >
                              <div className="col-span-6 flex items-center gap-2.5 min-w-0">
                                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-[#FF9900]/10 text-[#FF9900]">
                                  <Icon
                                    icon={
                                      cloud === "aws"
                                        ? "logos:aws"
                                        : cloud === "gcp"
                                        ? "logos:google-cloud"
                                        : "logos:microsoft-azure"
                                    }
                                    className="h-3.5 w-3.5"
                                  />
                                </span>
                                <span className="font-medium text-ink truncate">{it.label}</span>
                              </div>
                              <div className="col-span-3 text-right font-mono font-semibold text-ink">
                                ${it.monthly.toFixed(2)}
                              </div>
                              <div className="col-span-3 text-right font-mono text-ink-3">
                                ${(it.monthly * 0.92).toFixed(2)}
                              </div>
                            </div>
                          ))}

                          {/* Summary Row */}
                          <div className="grid grid-cols-12 items-center px-5 py-2.5 text-[12px] bg-canvas/60 font-semibold border-t border-line">
                            <div className="col-span-6 text-ink">
                              Total Monthly Infrastructure ({selectedOption})
                            </div>
                            <div className="col-span-3 text-right font-mono text-[#5C4EE5] dark:text-[#A78BFA]">
                              ${liveMonthly.toFixed(2)}
                            </div>
                            <div className="col-span-3 text-right font-mono text-ink-3">
                              ${(liveMonthly * 0.92).toFixed(2)}
                            </div>
                          </div>
                        </div>
                      </div>
                    </>
                  );
                })()}
              </div>
            )}
          </section>
        </div>

        {/* ════════════════════════════════════════════════════════════════════
            DEVELOPER TOOLS & WHICHCLOUD TERRAFORM PROVIDER SUITE
           ════════════════════════════════════════════════════════════════════ */}
        <section className="mt-6 rounded-2xl border border-line bg-surface p-5 shadow-xs">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
            <div>
              <h3 className="text-[14px] font-bold text-ink">
                WhichCloud Terraform Provider & Developer Tools
              </h3>
              <p className="text-[12px] text-ink-3 mt-0.5">
                Automate cloud cost management as Infrastructure as Code via the official WhichCloud Terraform Provider.
              </p>
            </div>

            {/* Dev Tools Navigation Tabs */}
            <div className="flex items-center gap-1 rounded-xl border border-line bg-canvas p-1 text-[12px]">
              <button
                type="button"
                onClick={() => setActiveDevTab("provider")}
                className={`rounded-lg px-3 py-1 font-medium transition ${
                  activeDevTab === "provider"
                    ? "bg-brand text-white shadow-xs"
                    : "text-ink-3 hover:text-ink"
                }`}
              >
                Terraform Provider
              </button>
              <button
                type="button"
                onClick={() => setActiveDevTab("cur")}
                className={`rounded-lg px-3 py-1 font-medium transition ${
                  activeDevTab === "cur"
                    ? "bg-brand text-white shadow-xs"
                    : "text-ink-3 hover:text-ink"
                }`}
              >
                AWS CUR 2.0 Module
              </button>
              <button
                type="button"
                onClick={() => setActiveDevTab("import")}
                className={`rounded-lg px-3 py-1 font-medium transition ${
                  activeDevTab === "import"
                    ? "bg-brand text-white shadow-xs"
                    : "text-ink-3 hover:text-ink"
                }`}
              >
                Terraform Import
              </button>
              <button
                type="button"
                onClick={() => setActiveDevTab("ai")}
                className={`rounded-lg px-3 py-1 font-medium transition ${
                  activeDevTab === "ai"
                    ? "bg-brand text-white shadow-xs"
                    : "text-ink-3 hover:text-ink"
                }`}
              >
                AI Copilot
              </button>
            </div>
          </div>

          {/* Tab 1: WhichCloud Terraform Provider */}
          {activeDevTab === "provider" && (
            <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
              <div>
                <h4 className="text-[13px] font-semibold text-ink">
                  Automate FinOps Resources in Terraform
                </h4>
                <p className="mt-1 text-[12.5px] leading-relaxed text-ink-3">
                  With the WhichCloud provider, you can manage Cost Reports, report notifications, folders, and dashboards. The provider queries cloud data using WhichCloud Query Language (VQL).
                </p>
                <div className="mt-3 flex flex-wrap gap-2 text-[11.5px]">
                  <span className="rounded-md border border-line bg-canvas px-2 py-1 font-mono text-ink-2">
                    whichcloud_cost_report
                  </span>
                  <span className="rounded-md border border-line bg-canvas px-2 py-1 font-mono text-ink-2">
                    whichcloud_saved_filter
                  </span>
                  <span className="rounded-md border border-line bg-canvas px-2 py-1 font-mono text-ink-2">
                    whichcloud_folder
                  </span>
                </div>
              </div>

              <div className="overflow-hidden rounded-xl border border-line bg-canvas font-mono text-[11.5px]">
                <div className="flex items-center justify-between border-b border-line bg-surface/50 px-3 py-1.5 text-ink-3 text-[11px]">
                  <span>cost_report.tf snippet</span>
                  <span>whichcloud-sh/whichcloud</span>
                </div>
                <pre className="p-3 text-ink-2 leading-relaxed overflow-x-auto">
{`resource "whichcloud_folder" "app" {
  title = "Production Cloud Workload"
}

resource "whichcloud_cost_report" "service_summary" {
  folder_token = whichcloud_folder.app.token
  filter       = "costs.provider = '${cloud}'"
  title        = "${selectedOption} Monthly Accrual"
  groupings    = "region,service"
}`}
                </pre>
              </div>
            </div>
          )}

          {/* Tab 2: AWS CUR 2.0 Module */}
          {activeDevTab === "cur" && (
            <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
              <div>
                <h4 className="text-[13px] font-semibold text-ink">
                  Vantage/WhichCloud AWS Integration Module
                </h4>
                <p className="mt-1 text-[12.5px] leading-relaxed text-ink-3">
                  Links your AWS master or member accounts with automated Cross-Account IAM Roles and Cost and Usage Report (CUR 2.0) Data Export. Supports multi-account telemetry ingestion.
                </p>
                <ul className="mt-2 space-y-1 text-[12px] text-ink-2">
                  <li>• Automatic CUR 2.0 parquet format data export</li>
                  <li>• S3 bucket creation with strict private ACLs</li>
                  <li>• Cross-account IAM role for WhichCloud autonomous analysis</li>
                </ul>
              </div>

              <div className="overflow-hidden rounded-xl border border-line bg-canvas font-mono text-[11.5px]">
                <div className="flex items-center justify-between border-b border-line bg-surface/50 px-3 py-1.5 text-ink-3 text-[11px]">
                  <span>cur2_integration.tf</span>
                  <span>whichcloud-integration/aws</span>
                </div>
                <pre className="p-3 text-ink-2 leading-relaxed overflow-x-auto">
{`module "whichcloud_aws_cur" {
  source            = "whichcloud-sh/whichcloud-integration/aws"
  cur_bucket_name   = "whichcloud-cur-${region}-billing"
  cur_bucket_region = "${region}"
  upgrade_to_cur_2  = true
}`}
                </pre>
              </div>
            </div>
          )}

          {/* Tab 3: Terraform Import */}
          {activeDevTab === "import" && (
            <div className="mt-4 space-y-3">
              <p className="text-[12.5px] text-ink-3 leading-relaxed">
                Bring existing cost reports and cloud monitoring resources created directly in the console into your Terraform state file.
              </p>

              <div className="flex items-center gap-3">
                <input
                  type="text"
                  value={importToken}
                  onChange={(e) => setImportToken(e.target.value)}
                  placeholder="rprt_token..."
                  className="w-72 rounded-xl border border-line bg-canvas px-3 py-1.5 font-mono text-[12px] text-ink outline-none focus:border-brand"
                />
                <button
                  type="button"
                  onClick={() => {
                    navigator.clipboard.writeText(`terraform import whichcloud_cost_report.demo_report ${importToken}`);
                    setCopiedImportCmd(true);
                    setTimeout(() => setCopiedImportCmd(false), 2000);
                  }}
                  className="rounded-xl border border-line bg-canvas px-3.5 py-1.5 text-[12px] font-semibold text-ink hover:bg-sunk transition"
                >
                  {copiedImportCmd ? "Copied Command!" : "Copy Import Command"}
                </button>
              </div>

              <div className="rounded-xl border border-line bg-canvas p-3 font-mono text-[12px] text-brand">
                terraform import whichcloud_cost_report.demo_report {importToken}
              </div>
            </div>
          )}

          {/* Tab 4: AI Copilot */}
          {activeDevTab === "ai" && (
            <div className="mt-4 space-y-3">
              <p className="text-[12.5px] text-ink-3">
                Tell AI to modify your Terraform files (e.g. inject cost guardrails, add multi-AZ standby, or add budget alerts).
              </p>

              <div className="flex gap-2">
                <input
                  type="text"
                  value={aiPrompt}
                  onChange={(e) => setAiPrompt(e.target.value)}
                  placeholder="e.g. Add AWS Bedrock LLM cost tracking filters and CloudWatch budget alarms..."
                  className="flex-1 rounded-xl border border-line bg-canvas px-3 py-2 text-[12.5px] text-ink outline-none focus:border-brand"
                />
                <button
                  type="button"
                  onClick={() => handleApplyAi()}
                  disabled={aiLoading || !aiPrompt.trim()}
                  className="rounded-xl bg-brand px-4 py-2 text-[12.5px] font-semibold text-white transition hover:bg-brand-strong disabled:opacity-60"
                >
                  {aiLoading ? "Injecting…" : "Apply to Terraform"}
                </button>
              </div>

              {aiNotice && (
                <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-2 text-[12px] text-emerald-500">
                  {aiNotice}
                </div>
              )}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

// Fallback generator if backend API is temporarily offline
function getDefaultFallbackFiles(cloud: CloudId, option: string, cost: number, region: string) {
  return {
    "main.tf": `# WhichCloud Automated Terraform Architecture
# Target Cloud: ${cloud.toUpperCase()}
# Tier: ${option} ($${cost.toFixed(2)}/mo)
# Region: ${region}

terraform {
  required_version = ">= 1.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.48.0"
    }
    whichcloud = {
      source  = "whichcloud-sh/whichcloud"
      version = "~> 1.2.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  tags = {
    Name        = "whichcloud-vpc"
    Environment = "production"
  }
}
`,
    "variables.tf": `variable "aws_region" {
  type    = string
  default = "${region}"
}

variable "project_name" {
  type    = string
  default = "whichcloud-app"
}
`,
    "outputs.tf": `output "vpc_id" {
  value       = aws_vpc.main.id
  description = "The VPC ID"
}
`,
    "modules/vpc.tf": `# Reusable VPC Networking Module
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "whichcloud-${cloud}-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["${region}a", "${region}b", "${region}c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = true

  tags = {
    Environment = "production"
    Tier        = "${option}"
  }
}
`,
    "modules/compute.tf": `# Reusable Compute Cluster Module
module "compute_cluster" {
  source = "./modules/compute"

  cluster_name    = "whichcloud-prod-cluster"
  instance_type   = "t3.medium"
  min_capacity    = 2
  max_capacity    = 6
  vpc_id          = module.vpc.vpc_id
  private_subnets = module.vpc.private_subnets
}
`,
    "modules/database.tf": `# Reusable Managed Database Module
module "managed_db" {
  source = "./modules/database"

  identifier             = "whichcloud-prod-db"
  allocated_storage      = 50
  engine                 = "mysql"
  engine_version         = "8.0"
  instance_class         = "db.t3.medium"
  multi_az               = true
  vpc_security_group_ids = [module.vpc.default_security_group_id]
}
`,
    "cost_reports.tf": `provider "whichcloud" {
  api_token = var.whichcloud_api_token
}

resource "whichcloud_folder" "tier_folder" {
  title = "Architecture - ${option}"
}

resource "whichcloud_cost_report" "main_report" {
  folder_token = whichcloud_folder.tier_folder.token
  filter       = "costs.provider = '${cloud}'"
  title        = "${option} Cost Overview"
  groupings    = "region,service"
}
`,
    "terraform.tfvars.example": `aws_region = "${region}"
project_name = "whichcloud-prod"
whichcloud_api_token = "YOUR_WHICHCLOUD_API_TOKEN"
`,
    "README.md": `# WhichCloud Terraform Architecture
Generated automatically for: ${option} ($${cost.toFixed(2)}/mo)
Region: ${region}

### Quickstart
\`\`\`bash
terraform init
terraform plan
terraform apply
\`\`\`
`,
  };
}

export default function TerraformPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen items-center justify-center bg-canvas text-ink-2 font-mono text-[13px]">
          Loading WhichCloud Terraform Studio...
        </div>
      }
    >
      <TerraformStudioContent />
    </Suspense>
  );
}
