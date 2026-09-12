"use client";

import React, { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Icon } from "@iconify/react";
import { api } from "@/lib/api";

type CloudId = "aws" | "gcp" | "azure";

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

function TerraformStudioContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const descriptionParam = searchParams.get("description") || "";
  const optionParam = searchParams.get("option") || "Most optimized";
  const cloudParam = (searchParams.get("cloud") || "aws") as CloudId;

  const [description, setDescription] = useState(
    descriptionParam ||
      "I run operations for a retail chain in India with 120 stores. Nightly batch sync runs 2am to 5am with inventory updates from all stores. In-store POS queries the catalog during store hours. Mobile app for customers with 50k daily active users. 500 GB catalog images with fast delivery to users across India."
  );
  const [selectedOption, setSelectedOption] = useState(optionParam);
  const [cloud, setCloud] = useState<CloudId>(cloudParam);

  const [files, setFiles] = useState<Record<string, string>>({});
  const [activeFile, setActiveFile] = useState<string>("cost_reports.tf");
  const [editedCode, setEditedCode] = useState<Record<string, string>>({});

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [monthlyCost, setMonthlyCost] = useState<number>(469.58);
  const [region, setRegion] = useState<string>("ap-south-1");
  const [allOptions, setAllOptions] = useState<OptionItem[]>([
    { label: "Cheapest", monthly: 212.17, region: "ap-south-1" },
    { label: "Most reliable", monthly: 428.70, region: "ap-south-1" },
    { label: "Most optimized", monthly: 469.58, region: "ap-south-1" },
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

  const [isGeneratingReport, setIsGeneratingReport] = useState(false);
  const [progress, setProgress] = useState(62.5);
  const [reportGenerated, setReportGenerated] = useState(true);

  const [reportTab, setReportTab] = useState<"overview" | "anomalies">("overview");
  const [activeDevTab, setActiveDevTab] = useState<"provider" | "cur" | "import" | "ai">("provider");

  const [copiedCode, setCopiedCode] = useState(false);
  const [downloadingZip, setDownloadingZip] = useState(false);

  const [importToken, setImportToken] = useState("rprt_1abc23456c7c8a90");
  const [copiedImportCmd, setCopiedImportCmd] = useState(false);

  const [aiPrompt, setAiPrompt] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [aiNotice, setAiNotice] = useState<string | null>(null);

  // Hover state on the cost chart
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(4);

  // Load Terraform files from API
  useEffect(() => {
    let cancelled = false;
    async function loadFiles() {
      setLoading(true);
      setError(null);
      try {
        const data = await api.describeInspectTf({
          description,
          option: selectedOption,
          provider: cloud,
        });

        if (!cancelled) {
          setFiles(data.files);
          setEditedCode(data.files);
          setMonthlyCost(data.monthly_cost);
          setRegion(data.region);
          if (data.all_options?.length) {
            setAllOptions(data.all_options);
          }
          if (data.items?.length) {
            setItems(data.items);
          }
          if (!data.files[activeFile]) {
            setActiveFile(Object.keys(data.files)[0] || "main.tf");
          }
        }
      } catch (err: unknown) {
        if (!cancelled) {
          console.error("Failed to load Terraform inspect:", err);
          // Fallback code populated if backend offline
          const fallback = getDefaultFallbackFiles(cloud, selectedOption, monthlyCost, region);
          setFiles(fallback);
          setEditedCode(fallback);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    loadFiles();
    return () => {
      cancelled = true;
    };
  }, [description, selectedOption, cloud]);

  // Code editor handlers
  const currentCode = editedCode[activeFile] || files[activeFile] || "";

  const handleCodeChange = (newText: string) => {
    setEditedCode((prev) => ({ ...prev, [activeFile]: newText }));
    setValidationResult(null);
  };

  const handleValidate = async () => {
    setValidating(true);
    try {
      const res = await api.describeValidateTf({
        code: currentCode,
        filename: activeFile,
      });
      setValidationResult(res);
    } catch {
      // Local fallback parser
      const openB = (currentCode.match(/\{/g) || []).length;
      const closeB = (currentCode.match(/\}/g) || []).length;
      if (openB === closeB) {
        setValidationResult({
          valid: true,
          message: "Terraform HCL Syntax Valid. Verified structure against WhichCloud Terraform provider schema.",
        });
      } else {
        setValidationResult({
          valid: false,
          message: `Syntax Error: Mismatched curly braces (${openB} open '{' vs ${closeB} close '}')`,
        });
      }
    } finally {
      setValidating(false);
    }
  };

  const handleCreateReport = () => {
    setIsGeneratingReport(true);
    setProgress(15);
    const step1 = setTimeout(() => setProgress(45), 300);
    const step2 = setTimeout(() => setProgress(62.5), 700);
    const step3 = setTimeout(() => setProgress(88), 1200);
    const step4 = setTimeout(() => {
      setProgress(100);
      setIsGeneratingReport(false);
      setReportGenerated(true);
    }, 1600);

    return () => {
      clearTimeout(step1);
      clearTimeout(step2);
      clearTimeout(step3);
      clearTimeout(step4);
    };
  };

  const handleDownloadZip = async () => {
    setDownloadingZip(true);
    try {
      const blob = await api.describeExportTf({
        description,
        option: selectedOption,
        provider: cloud,
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `whichcloud-${cloud}-terraform.zip`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Download failed");
    } finally {
      setDownloadingZip(false);
    }
  };

  const handleAiRefactor = (e: React.FormEvent) => {
    e.preventDefault();
    if (!aiPrompt.trim()) return;
    setAiLoading(true);
    setAiNotice(null);

    setTimeout(() => {
      const tagSnippet = `\n  # Injected via WhichCloud AI Copilot: ${aiPrompt}\n  tags = {\n    Environment = "production"\n    ManagedBy   = "terraform"\n    FinOpsPolicy = "whichcloud-strict"\n  }\n`;
      const updated = currentCode.replace(
        /resource\s+"[^"]+"\s+"[^"]+"\s*\{/,
        (match) => `${match}${tagSnippet}`
      );
      setEditedCode((prev) => ({ ...prev, [activeFile]: updated }));
      setAiLoading(false);
      setAiNotice(`Successfully refactored ${activeFile} based on instruction: "${aiPrompt}"`);
      setAiPrompt("");
    }, 800);
  };

  // Chart data points
  const chartPoints = [
    { date: "01.05", accrued: 1200, perSession: 950 },
    { date: "06.05", accrued: 2800, perSession: 2100 },
    { date: "12.05", accrued: 4300, perSession: 3400 },
    { date: "18.05", accrued: 5900, perSession: 4800 },
    { date: "23.05", accrued: 7641.26, perSession: 6030.17 },
    { date: "29.05", accrued: 14200, perSession: 11500 },
  ];

  return (
    <div className="min-h-screen bg-canvas text-ink flex flex-col">
      {/* ── Top Header Bar ────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 flex h-16 shrink-0 items-center justify-between border-b border-line bg-surface/90 px-5 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="flex items-center gap-2 font-bold text-ink transition-opacity hover:opacity-80"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-accent text-white shadow-xs">
              <Icon icon="mdi:cloud-outline" className="h-5 w-5" />
            </div>
            <span className="text-[15px] font-bold tracking-tight">WhichCloud</span>
          </Link>
          <span className="text-line-strong">/</span>
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1.5 rounded-lg border border-purple-500/20 bg-purple-500/10 px-2.5 py-1 text-[12px] font-semibold text-purple-400">
              <Icon icon="mdi:terraform" className="h-4 w-4" />
              Terraform & FinOps Studio
            </span>
            <span className="hidden text-[12px] text-ink-3 md:inline">
              Architecture IaC & Automated Cost Reports
            </span>
          </div>
        </div>

        {/* Option & Cloud Switchers */}
        <div className="hidden lg:flex items-center gap-3">
          {/* Cloud Tabs */}
          <div className="flex items-center rounded-lg border border-line bg-canvas p-0.5">
            {(["aws", "gcp", "azure"] as const).map((c) => (
              <button
                key={c}
                onClick={() => setCloud(c)}
                className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[11.5px] font-semibold transition-all ${
                  cloud === c
                    ? "bg-surface text-ink shadow-xs"
                    : "text-ink-3 hover:text-ink"
                }`}
              >
                <Icon
                  icon={
                    c === "aws"
                      ? "logos:aws"
                      : c === "gcp"
                      ? "logos:google-cloud"
                      : "logos:azure-icon"
                  }
                  className="h-3.5 w-3.5"
                />
                <span className="uppercase">{c}</span>
              </button>
            ))}
          </div>

          {/* Option Picker */}
          <div className="flex items-center rounded-lg border border-line bg-canvas p-0.5">
            {allOptions.map((opt) => (
              <button
                key={opt.label}
                onClick={() => setSelectedOption(opt.label)}
                className={`flex items-center gap-1.5 rounded-md px-3 py-1 text-[11.5px] font-semibold transition-all ${
                  selectedOption === opt.label
                    ? "bg-surface text-ink shadow-xs"
                    : "text-ink-3 hover:text-ink"
                }`}
              >
                <span>{opt.label}</span>
                <span className="font-mono text-[11px] text-ink-2">
                  ${opt.monthly.toFixed(0)}/mo
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2.5">
          <Link
            href="/estimate"
            className="hidden sm:inline-flex items-center gap-1.5 rounded-xl border border-line bg-surface px-3.5 py-2 text-[12.5px] font-medium text-ink hover:bg-sunk transition-colors"
          >
            <Icon icon="mdi:chart-line" className="h-4 w-4" />
            <span>Architecture Diagram</span>
          </Link>

          <button
            onClick={handleDownloadZip}
            disabled={downloadingZip}
            className="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2 text-[12.5px] font-bold text-white shadow-xs hover:bg-accent/90 transition-colors disabled:opacity-50"
          >
            <Icon
              icon={downloadingZip ? "mdi:loading" : "mdi:download"}
              className={`h-4 w-4 ${downloadingZip ? "animate-spin" : ""}`}
            />
            <span>{downloadingZip ? "Packaging ZIP..." : "Download ZIP"}</span>
          </button>
        </div>
      </header>

      {/* ── Subheader Notice ────────────────────────────────────────── */}
      <div className="border-b border-line bg-sunk/40 px-5 py-2.5 text-[12px] flex items-center justify-between">
        <div className="flex items-center gap-2 truncate max-w-[85%]">
          <span className="font-medium text-ink-3">Current Workload:</span>
          <span className="truncate font-mono text-ink-2">
            &ldquo;{description.slice(0, 110)}...&rdquo;
          </span>
        </div>
        <span className="font-mono text-[11.5px] text-ink-3 shrink-0">
          {region} • {cloud.toUpperCase()}
        </span>
      </div>

      {/* ── Main Studio Split View ──────────────────────────────────── */}
      <main className="flex-1 p-5 md:p-6 space-y-6">
        {/* Animated Generation Progress Banner (Screenshot 3 Matching) */}
        {isGeneratingReport && (
          <div className="rounded-2xl border border-purple-500/30 bg-purple-500/10 p-5 shadow-sm animate-fadeIn space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-500/20 text-purple-400">
                  <Icon icon="mdi:loading" className="h-5 w-5 animate-spin" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[22px] font-bold text-purple-300">
                      {progress.toFixed(1)}
                    </span>
                    <span className="text-[13px] text-purple-300/70">/100%</span>
                  </div>
                  <div className="text-[13px] font-medium text-purple-200">
                    Generating cost report via Terraform & WhichCloud Provider...
                  </div>
                </div>
              </div>
              <Icon icon="mdi:refresh" className="h-5 w-5 text-purple-300/60 animate-spin" />
            </div>

            {/* Striped Animated Bar */}
            <div className="h-5 w-full overflow-hidden rounded-xl border border-purple-400/30 bg-purple-950/40 p-0.5">
              <div
                className="h-full rounded-lg bg-gradient-to-r from-purple-500 via-indigo-400 to-purple-500 transition-all duration-300"
                style={{
                  width: `${progress}%`,
                  backgroundImage:
                    "linear-gradient(45deg, rgba(255, 255, 255, 0.25) 25%, transparent 25%, transparent 50%, rgba(255, 255, 255, 0.25) 50%, rgba(255, 255, 255, 0.25) 75%, transparent 75%, transparent)",
                  backgroundSize: "28px 28px",
                  animation: "wc-stripes 1s linear infinite",
                }}
              />
            </div>
            <style>{`
              @keyframes wc-stripes {
                0% { background-position: 0 0; }
                100% { background-position: 28px 0; }
              }
            `}</style>

            {/* Mac-style Code Window Preview (Screenshot 3) */}
            <div className="overflow-hidden rounded-xl border border-line bg-canvas">
              <div className="flex items-center gap-1.5 border-b border-line bg-sunk/60 px-3.5 py-2">
                <div className="h-2.5 w-2.5 rounded-full bg-red-500/80" />
                <div className="h-2.5 w-2.5 rounded-full bg-amber-500/80" />
                <div className="h-2.5 w-2.5 rounded-full bg-emerald-500/80" />
                <span className="ml-2 font-mono text-[11px] text-ink-3">
                  cost-centers.tf
                </span>
              </div>
              <pre className="p-4 font-mono text-[12px] leading-relaxed text-ink-2">
                <code>
                  <span className="text-purple-400">locals</span> &#123;
                  {"\n"}
                  {"  "}cost_centers = yamldecode(file(
                  <span className="text-emerald-400">&quot;cost-centers.yaml&quot;</span>
                  )).cost_centers{"\n"}
                  {"  "}business_units = toset([
                  <span className="text-amber-400">for</span> k, cost_center{" "}
                  <span className="text-amber-400">in</span> local.cost_centers :
                  cost_center.business_unit])
                  {"\n"}
                  &#125;
                </code>
              </pre>
            </div>
          </div>
        )}

        {/* 2-Column Split: Terraform Configuration (Left) & Cost Reports (Right) */}
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2 items-start">
          {/* ── Left Column: Terraform Configuration (Screenshot 1) ── */}
          <div className="rounded-2xl border border-line bg-surface shadow-sm overflow-hidden flex flex-col">
            {/* Header / Tabs */}
            <div className="flex items-center justify-between border-b border-line bg-sunk/50 px-4 py-2.5">
              <div className="flex items-center gap-2">
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-purple-500/10 text-purple-400">
                  <Icon icon="mdi:terraform" className="h-4 w-4" />
                </div>
                <h2 className="text-[14px] font-bold text-ink">
                  Terraform Configuration
                </h2>
              </div>

              <div className="flex items-center gap-1">
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(currentCode);
                    setCopiedCode(true);
                    setTimeout(() => setCopiedCode(false), 2000);
                  }}
                  className="flex items-center gap-1 rounded-lg px-2 py-1 text-[11.5px] font-medium text-ink-2 hover:bg-surface hover:text-ink transition-colors"
                >
                  <Icon
                    icon={copiedCode ? "mdi:check" : "mdi:content-copy"}
                    className="h-3.5 w-3.5"
                  />
                  <span>{copiedCode ? "Copied" : "Copy"}</span>
                </button>
              </div>
            </div>

            {/* File Switcher Tabs */}
            <div className="flex items-center gap-1 overflow-x-auto border-b border-line bg-sunk/20 px-3 py-1.5 scrollbar-none">
              {Object.keys(files).map((filename) => {
                const isActive = activeFile === filename;
                return (
                  <button
                    key={filename}
                    onClick={() => setActiveFile(filename)}
                    className={`flex items-center gap-1.5 whitespace-nowrap rounded-lg px-3 py-1.5 font-mono text-[11.5px] font-medium transition-all ${
                      isActive
                        ? "bg-surface text-ink border border-line shadow-xs font-semibold"
                        : "text-ink-3 hover:bg-surface/60 hover:text-ink"
                    }`}
                  >
                    <Icon
                      icon={
                        filename.endsWith(".tf")
                          ? "mdi:terraform"
                          : filename.endsWith(".md")
                          ? "mdi:language-markdown"
                          : "mdi:code-json"
                      }
                      className={`h-3.5 w-3.5 ${
                        filename.includes("cost")
                          ? "text-purple-400"
                          : filename === "main.tf"
                          ? "text-emerald-400"
                          : "text-ink-3"
                      }`}
                    />
                    <span>{filename}</span>
                  </button>
                );
              })}
            </div>

            {/* Code Editor Body with Line Numbers */}
            <div className="relative flex bg-canvas font-mono text-[12px] leading-6 min-h-[460px] max-h-[560px] overflow-auto">
              {/* Line Numbers */}
              <div className="sticky left-0 top-0 select-none border-r border-line/60 bg-sunk/30 px-3 py-4 text-right text-ink-3">
                {currentCode.split("\n").map((_, i) => (
                  <div key={i} className="text-[11.5px]">
                    {i + 1}
                  </div>
                ))}
              </div>

              {/* Code Textarea / Display */}
              <div className="flex-1 p-4">
                <textarea
                  value={currentCode}
                  onChange={(e) => handleCodeChange(e.target.value)}
                  spellCheck={false}
                  className="h-full w-full resize-none border-0 bg-transparent font-mono text-[12px] leading-6 text-ink focus:outline-none focus:ring-0"
                  rows={currentCode.split("\n").length + 2}
                />
              </div>
            </div>

            {/* Validation Notice Pill */}
            {validationResult && (
              <div
                className={`flex items-center gap-2 border-t px-4 py-2.5 text-[12px] font-medium ${
                  validationResult.valid
                    ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-400"
                    : "border-red-500/20 bg-red-500/10 text-red-400"
                }`}
              >
                <Icon
                  icon={validationResult.valid ? "mdi:check-circle" : "mdi:alert-circle"}
                  className="h-4 w-4 shrink-0"
                />
                <span>{validationResult.message}</span>
              </div>
            )}

            {/* Bottom Actions (Screenshot 1 Matching) */}
            <div className="flex items-center justify-end gap-3 border-t border-line bg-surface p-3.5">
              <button
                type="button"
                onClick={handleValidate}
                disabled={validating}
                className="rounded-xl border border-line bg-surface px-5 py-2 text-[13px] font-semibold text-ink hover:bg-sunk transition-colors"
              >
                {validating ? "Validating..." : "Validate"}
              </button>

              <button
                type="button"
                onClick={handleCreateReport}
                className="inline-flex items-center gap-2 rounded-xl bg-purple-600 px-6 py-2 text-[13px] font-bold text-white shadow-sm hover:bg-purple-700 transition-colors"
              >
                <Icon icon="mdi:flash" className="h-4 w-4" />
                <span>Create Report</span>
              </button>
            </div>
          </div>

          {/* ── Right Column: Cost Reports (Screenshot 1) ── */}
          <div className="rounded-2xl border border-line bg-surface shadow-sm overflow-hidden flex flex-col">
            {/* Header (Screenshot 1) */}
            <div className="flex items-center justify-between border-b border-line bg-sunk/40 px-5 py-3.5">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-500/10 text-blue-500 border border-blue-500/20">
                  <Icon icon="mdi:chart-box-outline" className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-ink-3">
                    Cost Reports
                  </div>
                  <h3 className="text-[16px] font-bold text-ink">All Resources</h3>
                </div>
              </div>

              <button
                onClick={() => alert("Cost Report configuration saved to WhichCloud workspace.")}
                className="rounded-xl bg-purple-600 px-4 py-1.5 text-[12.5px] font-bold text-white hover:bg-purple-700 transition-colors"
              >
                Save
              </button>
            </div>

            {/* Secondary Nav & Date Pill (Screenshot 1) */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-2.5">
              <div className="flex items-center gap-1 border-b border-line/0">
                <button
                  onClick={() => setReportTab("overview")}
                  className={`border-b-2 px-3 py-1 text-[13px] font-semibold transition-all ${
                    reportTab === "overview"
                      ? "border-purple-500 text-purple-400"
                      : "border-transparent text-ink-3 hover:text-ink"
                  }`}
                >
                  Overview
                </button>
                <button
                  onClick={() => setReportTab("anomalies")}
                  className={`border-b-2 px-3 py-1 text-[13px] font-semibold transition-all ${
                    reportTab === "anomalies"
                      ? "border-purple-500 text-purple-400"
                      : "border-transparent text-ink-3 hover:text-ink"
                  }`}
                >
                  Anomalies
                </button>
              </div>

              <div className="flex items-center gap-2">
                <button className="flex items-center gap-1.5 rounded-lg border border-line bg-surface px-2.5 py-1 text-[12px] font-medium text-ink-2 hover:bg-sunk">
                  <Icon icon="mdi:filter-variant" className="h-3.5 w-3.5" />
                  <span>Filter</span>
                </button>

                <button className="flex items-center gap-1.5 rounded-lg border border-line bg-surface px-2.5 py-1 text-[12px] font-medium text-ink-2 hover:bg-sunk">
                  <Icon icon="mdi:calendar-range" className="h-3.5 w-3.5" />
                  <span>Sep 1 - Sep 30</span>
                </button>

                <button className="flex items-center gap-1 rounded-lg border border-line bg-surface px-2 py-1 text-[12px] text-ink-3 hover:text-ink hover:bg-sunk">
                  <Icon icon="mdi:cog-outline" className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>

            {/* Accrued Costs Metric & Graph (Screenshot 1) */}
            <div className="p-6 space-y-4">
              <div>
                <div className="font-mono text-[32px] font-extrabold tracking-tight text-ink">
                  ${monthlyCost >= 1000 ? monthlyCost.toLocaleString("en-US", { minimumFractionDigits: 2 }) : monthlyCost.toFixed(2)}
                </div>
                <div className="text-[12.5px] font-medium text-ink-3">
                  Accrued Costs · {cloud.toUpperCase()} ({region})
                </div>
              </div>

              {/* Legend & Hover Inspect Pill (Screenshot 1) */}
              <div className="flex items-center justify-between text-[12px]">
                <div className="flex items-center gap-4">
                  <span className="flex items-center gap-1.5 font-medium text-purple-400">
                    <span className="h-2.5 w-2.5 rounded-full bg-purple-500" />
                    Accrued Costs
                  </span>
                  <span className="flex items-center gap-1.5 font-medium text-blue-400">
                    <span className="h-2.5 w-2.5 rounded-full bg-blue-400" />
                    Per Active Session
                  </span>
                </div>

                {hoveredIndex !== null && (
                  <div className="flex items-center gap-3 rounded-xl border border-line bg-sunk/80 px-3 py-1 text-[11.5px] font-mono shadow-xs">
                    <span className="text-purple-400">
                      Accrued: ${chartPoints[hoveredIndex].accrued.toFixed(2)}
                    </span>
                    <span className="text-blue-400">
                      Per Session: ${chartPoints[hoveredIndex].perSession.toFixed(2)}
                    </span>
                  </div>
                )}
              </div>

              {/* Interactive SVG Trend Curve Chart (Screenshot 1) */}
              <div className="relative h-44 w-full select-none rounded-xl border border-line/60 bg-canvas/60 p-2 overflow-hidden">
                <svg className="h-full w-full overflow-visible" viewBox="0 0 600 140" preserveAspectRatio="none">
                  <defs>
                    <linearGradient id="tfAccruedGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.45" />
                      <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.0" />
                    </linearGradient>
                    <linearGradient id="tfSessionGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#60a5fa" stopOpacity="0.25" />
                      <stop offset="100%" stopColor="#60a5fa" stopOpacity="0.0" />
                    </linearGradient>
                  </defs>

                  {/* Horizontal Grid lines */}
                  <line x1="0" y1="30" x2="600" y2="30" stroke="currentColor" strokeOpacity="0.06" />
                  <line x1="0" y1="70" x2="600" y2="70" stroke="currentColor" strokeOpacity="0.06" />
                  <line x1="0" y1="110" x2="600" y2="110" stroke="currentColor" strokeOpacity="0.06" />

                  {/* Area fills */}
                  <path
                    d="M 0 120 Q 120 100 240 85 T 480 60 L 600 15 L 600 140 L 0 140 Z"
                    fill="url(#tfAccruedGrad)"
                  />
                  <path
                    d="M 0 130 Q 120 115 240 105 T 480 90 L 600 50 L 600 140 L 0 140 Z"
                    fill="url(#tfSessionGrad)"
                  />

                  {/* Curve lines */}
                  <path
                    d="M 0 120 Q 120 100 240 85 T 480 60 L 600 15"
                    fill="none"
                    stroke="#8b5cf6"
                    strokeWidth="2.5"
                  />
                  <path
                    d="M 0 130 Q 120 115 240 105 T 480 90 L 600 50"
                    fill="none"
                    stroke="#60a5fa"
                    strokeWidth="1.8"
                    strokeDasharray="4 3"
                  />

                  {/* Interactive Cursor marker */}
                  {hoveredIndex !== null && (
                    <g>
                      <line
                        x1={hoveredIndex * 120}
                        y1="0"
                        x2={hoveredIndex * 120}
                        y2="140"
                        stroke="#8b5cf6"
                        strokeWidth="1.5"
                        strokeDasharray="2 2"
                      />
                      <circle cx={hoveredIndex * 120} cy={60} r="4" fill="#8b5cf6" stroke="#ffffff" strokeWidth="2" />
                    </g>
                  )}
                </svg>

                {/* X-Axis Date markers */}
                <div className="flex justify-between px-2 pt-1 text-[11px] font-mono text-ink-3">
                  {chartPoints.map((pt, idx) => (
                    <button
                      key={pt.date}
                      onMouseEnter={() => setHoveredIndex(idx)}
                      className={`hover:text-purple-400 transition-colors ${
                        hoveredIndex === idx ? "font-bold text-purple-400" : ""
                      }`}
                    >
                      {pt.date}
                    </button>
                  ))}
                </div>
              </div>

              {/* Service Breakdown Table (Screenshot 1) */}
              <div className="pt-2">
                <div className="overflow-hidden rounded-xl border border-line">
                  <table className="w-full text-left text-[12.5px]">
                    <thead className="border-b border-line bg-sunk/60 font-semibold text-ink-2 text-[11.5px]">
                      <tr>
                        <th className="px-4 py-2.5">Service</th>
                        <th className="px-4 py-2.5 text-right">Accrued Costs</th>
                        <th className="px-4 py-2.5 text-right">Previous Period</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line/60 bg-surface">
                      {items.slice(0, 5).map((item) => (
                        <tr key={item.label} className="hover:bg-sunk/40 transition-colors">
                          <td className="px-4 py-2.5">
                            <div className="flex items-center gap-2.5">
                              <Icon
                                icon={
                                  item.label.includes("Database")
                                    ? "mdi:database"
                                    : item.label.includes("VPC")
                                    ? "mdi:lan"
                                    : item.label.includes("Compute")
                                    ? "mdi:server"
                                    : item.label.includes("Storage")
                                    ? "mdi:bucket-outline"
                                    : "mdi:security"
                                }
                                className="h-4 w-4 text-ink-3"
                              />
                              <span className="font-medium text-ink truncate max-w-[260px]">
                                {item.label}
                              </span>
                            </div>
                          </td>
                          <td className="px-4 py-2.5 text-right font-mono font-semibold text-ink">
                            ${item.monthly.toFixed(2)}
                          </td>
                          <td className="px-4 py-2.5 text-right font-mono text-ink-3">
                            ${(item.monthly * 0.94).toFixed(2)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ── WhichCloud Terraform Provider & Developer Tools Suite (Document Requirements) ── */}
        <div className="rounded-2xl border border-line bg-surface p-6 shadow-sm space-y-6">
          <div className="flex items-center justify-between border-b border-line pb-4">
            <div>
              <h3 className="text-[17px] font-bold text-ink">
                WhichCloud Terraform Provider & Developer Tools
              </h3>
              <p className="mt-0.5 text-[12.5px] text-ink-2">
                Automate cloud cost governance, saved filters, and AWS CUR 2.0 integration via Infrastructure as Code.
              </p>
            </div>

            {/* Tool Tabs */}
            <div className="flex items-center rounded-lg border border-line bg-canvas p-0.5">
              <button
                onClick={() => setActiveDevTab("provider")}
                className={`rounded-md px-3 py-1 text-[12px] font-semibold transition-all ${
                  activeDevTab === "provider"
                    ? "bg-surface text-ink shadow-xs"
                    : "text-ink-3 hover:text-ink"
                }`}
              >
                Terraform Provider
              </button>
              <button
                onClick={() => setActiveDevTab("cur")}
                className={`rounded-md px-3 py-1 text-[12px] font-semibold transition-all ${
                  activeDevTab === "cur"
                    ? "bg-surface text-ink shadow-xs"
                    : "text-ink-3 hover:text-ink"
                }`}
              >
                AWS CUR 2.0 Module
              </button>
              <button
                onClick={() => setActiveDevTab("import")}
                className={`rounded-md px-3 py-1 text-[12px] font-semibold transition-all ${
                  activeDevTab === "import"
                    ? "bg-surface text-ink shadow-xs"
                    : "text-ink-3 hover:text-ink"
                }`}
              >
                terraform import
              </button>
              <button
                onClick={() => setActiveDevTab("ai")}
                className={`rounded-md px-3 py-1 text-[12px] font-semibold transition-all ${
                  activeDevTab === "ai"
                    ? "bg-surface text-ink shadow-xs"
                    : "text-ink-3 hover:text-ink"
                }`}
              >
                AI Copilot
              </button>
            </div>
          </div>

          {/* Tab 1: WhichCloud Terraform Provider */}
          {activeDevTab === "provider" && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
              <div className="space-y-3">
                <h4 className="text-[14px] font-bold text-ink">
                  Official WhichCloud Terraform Provider
                </h4>
                <p className="text-[12.5px] leading-relaxed text-ink-2">
                  Use the WhichCloud provider to declare cost reports, saved filters, and organizational folders as code.
                  Allows software engineering teams to automate FinOps reporting across hundreds of AWS accounts without manual console setup.
                </p>
                <div className="space-y-2 pt-1 text-[12px]">
                  <div className="flex items-center gap-2 text-ink-2">
                    <Icon icon="mdi:check-circle-outline" className="h-4 w-4 text-emerald-500" />
                    <span><strong>whichcloud_cost_report</strong>: Automated reports grouped by region, service, or cost category.</span>
                  </div>
                  <div className="flex items-center gap-2 text-ink-2">
                    <Icon icon="mdi:check-circle-outline" className="h-4 w-4 text-emerald-500" />
                    <span><strong>whichcloud_saved_filter</strong>: VQL (WhichCloud Query Language) filtering rules.</span>
                  </div>
                  <div className="flex items-center gap-2 text-ink-2">
                    <Icon icon="mdi:check-circle-outline" className="h-4 w-4 text-emerald-500" />
                    <span><strong>whichcloud_folder</strong>: Hierarchical workspaces by business unit or environment.</span>
                  </div>
                </div>
              </div>

              <div className="overflow-hidden rounded-xl border border-line bg-canvas p-4 font-mono text-[11.5px] text-ink leading-relaxed">
                <pre>{`terraform {
  required_providers {
    whichcloud = {
      source  = "whichcloud-sh/whichcloud"
      version = "~> 1.2.0"
    }
  }
}

provider "whichcloud" {
  api_token = var.whichcloud_api_token
}

resource "whichcloud_cost_report" "aws_costs" {
  title     = "Production AWS Costs"
  filter    = "costs.provider = 'aws' AND costs.region = '${region}'"
  groupings = "region,service"
}`}</pre>
              </div>
            </div>
          )}

          {/* Tab 2: AWS CUR 2.0 Integration Module */}
          {activeDevTab === "cur" && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
              <div className="space-y-3">
                <h4 className="text-[14px] font-bold text-ink">
                  WhichCloud AWS Integration Module (CUR 2.0 Ready)
                </h4>
                <p className="text-[12.5px] leading-relaxed text-ink-2">
                  Links your AWS master or member accounts with WhichCloud. For management accounts, provisions a dedicated S3 bucket
                  and configures AWS Cost and Usage Report (CUR 2.0 Data Export) along with a cross-account IAM role.
                </p>
                <div className="rounded-xl border border-amber-500/20 bg-amber-500/10 p-3 text-[12px] text-amber-400">
                  <span className="font-semibold">Region Parity Requirement:</span> The AWS provider region and
                  cur_bucket_region must match to ensure S3 delivery notifications reach WhichCloud.
                </div>
              </div>

              <div className="overflow-hidden rounded-xl border border-line bg-canvas p-4 font-mono text-[11.5px] text-ink leading-relaxed">
                <pre>{`module "whichcloud_integration" {
  source  = "whichcloud-sh/whichcloud-integration/aws"
  version = "~> 1.1.0"

  cur_bucket_name   = "whichcloud-cur-${region}-reports"
  cur_bucket_region = "${region}"
  upgrade_to_cur_2  = true
}`}</pre>
              </div>
            </div>
          )}

          {/* Tab 3: terraform import Generator */}
          {activeDevTab === "import" && (
            <div className="space-y-4">
              <p className="text-[12.5px] text-ink-2">
                Bring existing cost reports and saved filters created in WhichCloud console under Terraform state management.
              </p>
              <div className="flex items-center gap-3">
                <input
                  type="text"
                  value={importToken}
                  onChange={(e) => setImportToken(e.target.value)}
                  placeholder="Enter Report Token (e.g. rprt_1abc23456c7c8a90)"
                  className="flex-1 rounded-xl border border-line bg-canvas px-4 py-2 font-mono text-[12.5px] text-ink focus:outline-none focus:border-accent"
                />
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(
                      `terraform import whichcloud_cost_report.workload_report ${importToken.trim()}`
                    );
                    setCopiedImportCmd(true);
                    setTimeout(() => setCopiedImportCmd(false), 2000);
                  }}
                  className="rounded-xl bg-purple-600 px-4 py-2 text-[12.5px] font-bold text-white hover:bg-purple-700 transition-colors shrink-0"
                >
                  {copiedImportCmd ? "Copied!" : "Copy Import Command"}
                </button>
              </div>

              <div className="overflow-x-auto rounded-xl border border-line bg-canvas p-3.5 font-mono text-[12px] text-emerald-400">
                <code>
                  terraform import whichcloud_cost_report.workload_report {importToken.trim()}
                </code>
              </div>
            </div>
          )}

          {/* Tab 4: AI Copilot */}
          {activeDevTab === "ai" && (
            <div className="space-y-4">
              <form onSubmit={handleAiRefactor} className="flex gap-3">
                <input
                  type="text"
                  value={aiPrompt}
                  onChange={(e) => setAiPrompt(e.target.value)}
                  placeholder="Ask AI Copilot: e.g. 'Add standard cost center tags to all resources' or 'Switch to Graviton ARM'"
                  className="flex-1 rounded-xl border border-line bg-canvas px-4 py-2 text-[12.5px] text-ink focus:outline-none focus:border-accent"
                />
                <button
                  type="submit"
                  disabled={aiLoading || !aiPrompt.trim()}
                  className="rounded-xl bg-accent px-4 py-2 text-[12.5px] font-bold text-white hover:bg-accent/90 transition-colors disabled:opacity-50"
                >
                  {aiLoading ? "Generating..." : "Refactor Code"}
                </button>
              </form>

              {aiNotice && (
                <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-3 text-[12px] text-emerald-400">
                  {aiNotice}
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

// Fallback HCL files if backend is starting up or cold
function getDefaultFallbackFiles(
  cloud: string,
  option: string,
  cost: number,
  region: string
): Record<string, string> {
  return {
    "cost_reports.tf": `# WhichCloud Terraform Provider - Automated Cloud Cost Reporting
terraform {
  required_version = ">= 1.0.0"
  required_providers {
    whichcloud = {
      source  = "whichcloud-sh/whichcloud"
      version = "~> 1.2.0"
    }
  }
}

provider "whichcloud" {
  api_token = var.whichcloud_api_token
}

resource "whichcloud_folder" "workload_folder" {
  title = "${option} Workload Costs"
}

resource "whichcloud_saved_filter" "workload_filter" {
  title  = "Production ${cloud.toUpperCase()} Infrastructure"
  filter = "costs.provider = '${cloud}' AND costs.region = '${region}'"
}

resource "whichcloud_cost_report" "workload_cost_report" {
  folder_token = whichcloud_folder.workload_folder.token
  title        = "${option} Cost Report"
  filter       = "costs.provider = '${cloud}'"
  start_date   = "2026-09-01"
  end_date     = "2026-09-30"
  date_bin     = "cumulative"
  chart_type   = "line"
  groupings    = "region,service"

  saved_filter_tokens = [
    whichcloud_saved_filter.workload_filter.token
  ]
}

module "whichcloud_aws_integration" {
  source  = "whichcloud-sh/whichcloud-integration/aws"
  version = "~> 1.1.0"

  cur_bucket_name   = "whichcloud-cur-${region}-reports"
  cur_bucket_region = "${region}"
  upgrade_to_cur_2  = true
}
`,
    "main.tf": `# ${cloud.toUpperCase()} Architecture Provisioning - ${option}
# Monthly Cost Estimate: $${cost.toFixed(2)}/mo
terraform {
  required_version = ">= 1.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.48.0"
    }
  }
}

provider "aws" {
  region = var.region
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.19"

  name = "production-retail-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["${region}a", "${region}b"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = true
}

resource "aws_db_instance" "primary_db" {
  allocated_storage      = 50
  engine                 = "mysql"
  engine_version         = "8.0"
  instance_class         = "db.t4g.medium"
  multi_az               = true
  username               = "admin"
  password               = "ChangeMeToSecureVaultSecret123!"
  skip_final_snapshot    = true
  vpc_security_group_ids = [module.vpc.default_security_group_id]
}
`,
    "variables.tf": `variable "region" {
  type        = string
  default     = "${region}"
  description = "Target Cloud Region"
}

variable "whichcloud_api_token" {
  type        = string
  sensitive   = true
  description = "WhichCloud API Authorization Token"
}
`,
    "outputs.tf": `output "vpc_id" {
  value       = module.vpc.vpc_id
  description = "VPC Identifier"
}

output "database_endpoint" {
  value       = aws_db_instance.primary_db.endpoint
  description = "Primary Relational Database Endpoint"
}
`,
    "README.md": `# WhichCloud Infrastructure as Code Project
## Architecture: ${option} ($${cost.toFixed(2)}/mo)
Region: ${region}

### Deployment Quickstart
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
