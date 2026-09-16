"use client";

import { Suspense, useEffect, useState, type ReactNode } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { Icon } from "@iconify/react";
import { api, FinOpsLiveResponse, FinOpsNode, FinOpsTechnique, money } from "@/lib/api";
import { CostReportView } from "@/components/finops/CostReportView";
import { SidebarNav, NavItemKey } from "@/components/layout/SidebarNav";
import { FinOpsIssuesView } from "@/components/finops/FinOpsIssuesView";
import { FinOpsResourcesView } from "@/components/finops/FinOpsResourcesView";
import { FinOpsPlanningView } from "@/components/finops/FinOpsPlanningView";
import { FinOpsSettingsView } from "@/components/finops/FinOpsSettingsView";
import { TerraformLogo } from "@/components/Logo";
import { CurrencyCode, formatCurrency } from "@/lib/currency";
import { getStoredAccount, setStoredAccount, CloudProviderId, CLOUD_PROVIDERS } from "@/lib/connectedAccount";

/** Shared shell for the four KPI cards above the topology graph: the
 *  gradient overlay, blur glow, and icon/label/badge header row were
 *  identical boilerplate repeated at each of the four call sites and had
 *  already begun drifting (some had a footer progress bar, some didn't).
 *  Only the tone (border/gradient/blur/icon color) and the body below the
 *  header are per-card -- those genuinely differ (a trend badge here, a
 *  progress bar there) so they stay as props/children rather than being
 *  forced into one shape. */
function KpiCard({
  tone,
  icon,
  label,
  badge,
  children,
}: {
  tone: "accent" | "amber" | "emerald";
  icon: string;
  label: string;
  badge: ReactNode;
  children: ReactNode;
}) {
  const toneClasses: Record<typeof tone, { border: string; gradient: string; blur: string; iconColor: string }> = {
    accent: { border: "border-accent-line/40", gradient: "from-accent/5", blur: "bg-accent/8", iconColor: "text-accent" },
    amber: { border: "border-amber-500/25", gradient: "from-amber-500/6", blur: "bg-amber-500/10", iconColor: "text-amber-500" },
    emerald: { border: "border-emerald-500/25", gradient: "from-emerald-500/6", blur: "bg-emerald-500/10", iconColor: "text-emerald-500" },
  };
  const t = toneClasses[tone];

  return (
    <div className={`group relative overflow-hidden rounded-2xl border ${t.border} bg-surface p-5 shadow-xs transition-all duration-300 hover:shadow-md hover:-translate-y-0.5`}>
      <div className={`absolute inset-0 bg-gradient-to-br ${t.gradient} via-transparent to-transparent pointer-events-none`} />
      <div className={`absolute -top-6 -right-6 h-20 w-20 rounded-full ${t.blur} blur-2xl pointer-events-none`} />
      <div className="relative">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Icon icon={icon} className={`h-4 w-4 ${t.iconColor}`} />
            <span className="text-[12px] font-semibold text-ink-3 uppercase tracking-wide">{label}</span>
          </div>
          {badge}
        </div>
        {children}
      </div>
    </div>
  );
}

/** The `<track><fill style={{width}}/></track>` progress-bar recipe was
 *  hand-rolled 6 times on this page alone (KPI cards, per-node bill share,
 *  the mini spend bar, workload utilization), each a near-identical copy
 *  differing only in height, track color, gradient, and an optional
 *  transition class. One shared component so a future tweak (radius,
 *  reduced-motion handling) lands in one place instead of 6. */
function ProgressBar({
  pct,
  gradient,
  className = "mt-2 h-1",
  track = "bg-sunk",
  transitionClass = "",
}: {
  pct: number;
  gradient: string;
  className?: string;
  track?: string;
  transitionClass?: string;
}) {
  return (
    <div className={`${className} w-full overflow-hidden rounded-full ${track}`}>
      <div
        className={`h-full rounded-full bg-gradient-to-r ${gradient} ${transitionClass}`}
        style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
      />
    </div>
  );
}

function FinOpsContent() {
  const { getToken } = useAuth();
  const searchParams = useSearchParams();
  const providerParam = searchParams.get("provider");
  const accountIdParam = searchParams.get("account_id");
  const tabParam = (searchParams.get("tab") as NavItemKey) || "overview";

  // Initialize from URL param or stored connected account
  const [provider, setProvider] = useState<string>(() => {
    if (providerParam && ["aws", "azure", "gcp", "github"].includes(providerParam)) {
      return providerParam;
    }
    if (typeof window !== "undefined") {
      return getStoredAccount().provider;
    }
    return "aws";
  });

  const [activeTab, setActiveTab] = useState<NavItemKey>(
    ["overview", "reports", "issues", "resources", "planning", "recommendations", "settings"].includes(tabParam)
      ? tabParam
      : "overview"
  );
  const [currency, setCurrency] = useState<CurrencyCode>("USD");
  const [data, setData] = useState<FinOpsLiveResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeNode, setActiveNode] = useState<FinOpsNode | null>(null);
  const [appliedTechniques, setAppliedTechniques] = useState<Record<string, boolean>>({});
  const [activeDiffModal, setActiveDiffModal] = useState<FinOpsTechnique | null>(null);
  const [showExportModal, setShowExportModal] = useState(false);
  const [copiedDiff, setCopiedDiff] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const [secondsWaiting, setSecondsWaiting] = useState(0);

  useEffect(() => {
    if (!loading) {
      setSecondsWaiting(0);
      return;
    }
    const id = setInterval(() => setSecondsWaiting((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [loading]);

  // Sync state when URL params or provider changes
  useEffect(() => {
    let mounted = true;
    setLoading(true);

    const effectiveId = accountIdParam || CLOUD_PROVIDERS[provider as CloudProviderId]?.id || "demo";

    // Save active provider to localStorage
    setStoredAccount({
      provider: provider as CloudProviderId,
      id: effectiveId,
    });

    (async () => {
      try {
        const token = await getToken();
        const res = await api.finopsLive(provider, effectiveId, token ?? undefined);
        if (mounted) {
          setData(res);
          setAppliedTechniques({});
          setActiveNode(res.nodes.find((n) => n.status === "action_needed") || res.nodes[2]);
          setLoading(false);
        }
      } catch (err) {
        console.error(err);
        if (mounted) setLoading(false);
      }
    })();

    return () => {
      mounted = false;
    };
  }, [provider, accountIdParam, getToken]);

  const handleSwitchAccount = (newProv: string) => {
    setProvider(newProv);
    const target = CLOUD_PROVIDERS[newProv as CloudProviderId];
    if (target && typeof window !== "undefined") {
      setStoredAccount({
        provider: newProv as CloudProviderId,
        id: target.id,
        name: target.name,
        region: target.region,
      });
      window.history.replaceState(
        null,
        "",
        `/finops?provider=${newProv}&account_id=${encodeURIComponent(target.id)}`
      );
    }
  };

  const toggleTechnique = (techId: string) => {
    setAppliedTechniques((prev) => ({
      ...prev,
      [techId]: !prev[techId],
    }));
  };

  const handleResync = () => {
    setSyncing(true);
    setTimeout(() => {
      setSyncing(false);
    }, 850);
  };

  if (loading || !data) {
    return (
      <div className="mx-auto flex min-h-[70vh] w-full items-center justify-center p-12 text-center">
        <div>
          <Icon icon="line-md:loading-loop" className="mx-auto h-10 w-10 text-accent animate-spin" />
          <h2 className="mt-4 text-[18px] font-semibold text-ink">
            Connecting to Cloud Telemetry & Cost Engine...
          </h2>
          <p className="mt-1 text-[13.5px] text-ink-3">
            Querying CloudWatch, Cost Explorer, BigQuery billing exports & CUR tables.
          </p>
          {secondsWaiting >= 5 && (
            <p className="mt-2 text-[12px] text-ink-3">
              {secondsWaiting}s
              {secondsWaiting >= 15
                ? " — the backend is waking from idle on the free tier, this can take up to a minute"
                : ""}
            </p>
          )}
        </div>
      </div>
    );
  }

  // Dynamic calculations based on toggled techniques
  const totalTechniqueSavings = Object.entries(appliedTechniques).reduce((acc, [id, applied]) => {
    if (!applied) return acc;
    const tech = data.techniques.find((t) => t.id === id);
    return acc + (tech ? tech.monthly_saving : 0);
  }, 0);

  const currentSpend = Math.max(0, data.summary.total_monthly_usd - totalTechniqueSavings);
  const savingsPct = Math.min(
    100,
    Math.round((totalTechniqueSavings / data.summary.total_monthly_usd) * 100)
  );
  const dynamicEfficiencyScore = Math.min(
    98,
    Math.round(
      data.summary.efficiency_score +
        (totalTechniqueSavings / (data.summary.realizable_savings_usd || 1)) * 20
    )
  );

  const getNodeMonthlyCost = (node: FinOpsNode): number => {
    if (node.id === "eip-idle" && appliedTechniques["aws-release-eip"]) return 0;
    if (node.id === "ec2-stopped" && appliedTechniques["aws-detach-ebs"]) return 0;
    if (node.id === "ebs-volumes" && appliedTechniques["aws-detach-ebs"]) return 0;
    if (node.id === "s3-fleet" && appliedTechniques["aws-s3-lifecycle"]) return Math.max(0, node.monthly_usd - 1.80);
    if (node.id === "ecs" && appliedTechniques["aws-graviton"]) return node.monthly_usd - 220;
    if (node.id === "rds" && appliedTechniques["aws-graviton"]) return node.monthly_usd - 190;
    if (node.id === "s3" && appliedTechniques["aws-s3-endpoint"]) return node.monthly_usd - 180;
    if (node.id === "aks" && appliedTechniques["azure-aks-spot"]) return node.monthly_usd - 280;
    if (node.id === "sql" && appliedTechniques["azure-sql-gp"]) return node.monthly_usd - 490;
    if (node.id === "gke" && appliedTechniques["gcp-cud"]) return node.monthly_usd - 460;
    if (node.id === "csql" && appliedTechniques["gcp-sql-arm"]) return node.monthly_usd - 430;
    if (node.id === "eks" && appliedTechniques["gh-karpenter"]) return node.monthly_usd - 490;
    return node.monthly_usd;
  };

  return (
    <div className="flex min-h-[calc(100vh-4rem)] w-full bg-canvas">
      {/* Enterprise Left Sidebar matching user screenshot */}
      <SidebarNav
        mobileOpen={navOpen}
        onCloseMobile={() => setNavOpen(false)}
        activeKey={activeTab}
        onSelectKey={(key) => setActiveTab(key)}
        connectedAccount={{
          name: data.account.name,
          id: data.account.id,
          provider: data.account.provider,
        }}
        onSwitchAccount={handleSwitchAccount}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col px-4 py-6 sm:px-8 overflow-y-auto max-w-7xl">
        {/* Top Header with Breadcrumbs & Action Controls */}
        <div className="flex flex-col gap-4 border-b border-line pb-5 md:flex-row md:items-center md:justify-between">
          <div>
            {/* Opens the nav drawer. Mobile only -- above md the sidebar is a
                permanent column and needs no trigger. */}
            <button
              type="button"
              onClick={() => setNavOpen(true)}
              className="mb-3 inline-flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-1.5 text-[13px] font-medium text-ink-2 transition hover:text-ink md:hidden"
              aria-label="Open FinOps navigation"
            >
              <Icon icon="mdi:menu" className="h-4 w-4" />
              <span>Menu</span>
            </button>

            <div className="flex items-center gap-2 text-[12.5px] font-medium text-ink-3">
              <Link href="/connect" className="hover:text-ink">
                Connected Accounts
              </Link>
              <span>/</span>
              <span className="capitalize font-semibold text-ink-2">{data.account.provider}</span>
              <span>/</span>
              <span className="font-mono text-ink-3">{data.account.id}</span>
            </div>

            <div className="mt-2 flex items-center gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-line bg-surface p-1.5 shadow-2xs">
                <Icon
                  icon={
                    data.account.provider === "azure"
                      ? "logos:microsoft-azure"
                      : data.account.provider === "gcp"
                      ? "logos:google-cloud"
                      : data.account.provider === "github"
                      ? "logos:github-icon"
                      : "logos:aws"
                  }
                  className="h-5 w-5"
                />
              </div>

              <h1 className="text-[24px] font-bold tracking-tight text-ink">
                {activeTab === "overview"
                  ? "Live Topology & Telemetry"
                  : activeTab === "reports"
                  ? "Cost Reports"
                  : activeTab === "issues"
                  ? "Cloud Waste & Anomaly Center"
                  : activeTab === "resources"
                  ? "Active Resources Inventory"
                  : activeTab === "planning"
                  ? "Financial Planning & Budgets"
                  : activeTab === "recommendations"
                  ? "FinOps Cost Reduction Engine"
                  : "Settings & Regional Formats"}
              </h1>

              <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-0.5 text-[11.5px] font-medium text-emerald-500">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                Live {data.account.cloud_label}
              </span>
            </div>
          </div>

          {/* Quick Utility Actions */}
          <div className="flex flex-wrap items-center gap-2.5">
            {/* Currency Switcher Pill */}
            <div className="flex items-center rounded-xl border border-line bg-surface p-1 shadow-2xs">
              {(["USD", "EUR", "GBP", "INR"] as CurrencyCode[]).map((curr) => (
                <button
                  key={curr}
                  onClick={() => setCurrency(curr)}
                  className={`rounded-lg px-2.5 py-1 text-[11.5px] font-mono font-bold transition-all ${
                    currency === curr
                      ? "bg-accent text-white shadow-xs"
                      : "text-ink-2 hover:bg-sunk hover:text-ink"
                  }`}
                >
                  {curr}
                </button>
              ))}
            </div>

            {/* Sync Button */}
            <button
              onClick={handleResync}
              disabled={syncing}
              className="inline-flex items-center gap-1.5 rounded-xl border border-line bg-surface px-3 py-1.5 text-[12.5px] font-medium text-ink-2 hover:bg-sunk hover:text-ink shadow-2xs transition-colors"
              title="Refresh metrics from Cloud API"
            >
              <Icon
                icon="mdi:refresh"
                className={`h-4 w-4 text-ink-2 ${syncing ? "animate-spin text-accent" : ""}`}
              />
              <span>{syncing ? "Syncing..." : "Sync"}</span>
            </button>

            {/* Delete All Resources Button for Active Resources Tab */}
            {activeTab === "resources" && (
              <button
                onClick={() => {
                  window.dispatchEvent(new CustomEvent("open-delete-all-resources-modal"));
                }}
                className="inline-flex items-center gap-1.5 rounded-xl border border-red-500/40 bg-red-500/10 px-3 py-1.5 text-[12.5px] font-bold text-red-500 hover:bg-red-500/20 hover:border-red-500/60 shadow-2xs transition-all active:scale-95"
                title="Open Delete All Resources confirmation modal"
              >
                <Icon icon="mdi:trash-can-alert" className="h-4 w-4" />
                <span>Delete All Resources</span>
              </button>
            )}

            {/* Executive Memo Button */}
            <button
              onClick={() => setShowExportModal(true)}
              className="inline-flex items-center gap-1.5 rounded-xl bg-accent px-3.5 py-1.5 text-[12.5px] font-semibold text-white hover:opacity-90 shadow-2xs"
            >
              <Icon icon="mdi:file-document-outline" className="h-4 w-4" />
              Executive Memo
            </button>
          </div>
        </div>

        {/* VIEW 1: Overview (Live Topology & Inspector + KPIs) */}
        {activeTab === "overview" && (
          <div className="space-y-6 mt-6">

            {/* ── KPI Summary Cards ── */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">

              <KpiCard
                tone="accent"
                icon="mdi:currency-usd"
                label="Monthly Spend"
                badge={
                  <span className="rounded-md bg-accent/10 px-1.5 py-0.5 text-[10px] font-mono text-accent border border-accent-line/40">
                    {data.account.region}
                  </span>
                }
              >
                <div className="mt-3 flex items-baseline gap-1.5">
                  <span className="text-[30px] font-bold tracking-tight text-ink font-mono">
                    {formatCurrency(currentSpend, currency, 2)}
                  </span>
                  <span className="text-[12px] text-ink-3">/mo</span>
                </div>
                <div className="mt-2.5 flex items-center gap-1.5">
                  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] font-semibold text-emerald-500 border border-emerald-500/20">
                    <Icon icon="mdi:trending-down" className="h-3 w-3" />
                    {formatCurrency(data.summary.previous_monthly_usd - currentSpend, currency, 0)}
                  </span>
                  <span className="text-[11.5px] text-ink-3">vs prev month</span>
                </div>
              </KpiCard>

              <KpiCard
                tone="amber"
                icon="mdi:fire"
                label="Cloud Waste"
                badge={
                  <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-500 border border-amber-500/20">
                    <span className="h-1.5 w-1.5 rounded-full bg-amber-500 animate-pulse" />
                    Unused
                  </span>
                }
              >
                <div className="mt-3 flex items-baseline gap-1.5">
                  <span className="text-[30px] font-bold tracking-tight text-amber-500 font-mono">
                    {formatCurrency(data.summary.realizable_savings_usd, currency, 0)}
                  </span>
                  <span className="text-[12px] text-ink-3">/mo</span>
                </div>
                <div className="mt-2.5 text-[11.5px] text-ink-3">
                  Overprovisioned nodes & idle egress
                </div>
                <ProgressBar
                  pct={(data.summary.realizable_savings_usd / data.summary.total_monthly_usd) * 100}
                  gradient="from-amber-500 to-orange-400"
                />
              </KpiCard>

              <KpiCard
                tone="emerald"
                icon="mdi:lightning-bolt"
                label="Simulated Savings"
                badge={
                  <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-bold text-emerald-500 border border-emerald-500/20">
                    {savingsPct}% reducible
                  </span>
                }
              >
                <div className="mt-3 flex items-baseline gap-1.5">
                  <span className="text-[30px] font-bold tracking-tight text-emerald-500 font-mono">
                    +{formatCurrency(totalTechniqueSavings, currency, 0)}
                  </span>
                  <span className="text-[12px] text-ink-3">/mo</span>
                </div>
                <div className="mt-2.5 flex items-center gap-1.5">
                  <span className="text-[11.5px] text-ink-3">
                    {Object.values(appliedTechniques).filter(Boolean).length} of {data.techniques.length} optimizations enabled
                  </span>
                </div>
                <ProgressBar pct={savingsPct} gradient="from-emerald-500 to-teal-400" transitionClass="transition-all duration-700" />
              </KpiCard>

              <KpiCard
                tone="accent"
                icon="mdi:shield-check"
                label="Health Score"
                badge={
                  <span className="rounded-full bg-accent/10 px-2 py-0.5 text-[10px] font-bold text-accent border border-accent-line/40">
                    {dynamicEfficiencyScore >= 90 ? "Grade A" : dynamicEfficiencyScore >= 80 ? "Grade B+" : "Grade B"}
                  </span>
                }
              >
                <div className="mt-3 flex items-baseline gap-1">
                  <span className="text-[30px] font-bold tracking-tight text-ink font-mono">{dynamicEfficiencyScore}</span>
                  <span className="text-[13px] font-medium text-ink-3">/100</span>
                </div>
                <ProgressBar
                  pct={dynamicEfficiencyScore}
                  gradient="from-accent to-blue-400"
                  className="mt-2.5 relative h-2"
                  transitionClass="transition-all duration-700 ease-out"
                />
                <div className="mt-1.5 flex justify-between text-[10px] text-ink-3">
                  <span>Poor</span><span>Excellent</span>
                </div>
              </KpiCard>
            </div>

            {/* ── Topology Graph & Inspector ── */}
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">

              {/* Topology Panel */}
              <div className="relative overflow-hidden rounded-2xl border border-line bg-surface shadow-xs lg:col-span-2">
                {/* Panel Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-line bg-gradient-to-r from-sunk/40 to-transparent">
                  <h3 className="text-[15px] font-bold text-ink flex items-center gap-2">
                    <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent/10 border border-accent-line/30">
                      <Icon icon="mdi:graph-outline" className="h-4 w-4 text-accent" />
                    </span>
                    Live Topology Graph & Cost Heatmap
                  </h3>
                  <div className="flex items-center gap-1.5 rounded-full border border-emerald-500/20 bg-emerald-500/8 px-2.5 py-1">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-ping" />
                    <span className="text-[10.5px] font-mono font-semibold text-emerald-500 tracking-wide">LIVE TELEMETRY</span>
                  </div>
                </div>

                <div className="p-6 space-y-5">

                  {/* Layer 1 – Edge & Ingress */}
                  <div>
                    <div className="mb-3 flex items-center gap-2">
                      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-accent/15 text-[10px] font-bold text-accent">1</span>
                      <span className="text-[11px] font-bold uppercase tracking-widest text-ink-3">Edge & Ingress Layer</span>
                    </div>
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                      {data.nodes
                        .filter((n) => n.kind === "client" || n.kind === "network" || n.kind === "loadbalancer")
                        .map((node) => {
                          const isSelected = activeNode?.id === node.id;
                          const nodeCost = getNodeMonthlyCost(node);
                          const hasWaste = node.waste_usd > 0;
                          return (
                            <button
                              key={node.id}
                              onClick={() => setActiveNode(node)}
                              className={`group/card flex flex-col items-start rounded-xl border p-4 text-left transition-all duration-200 ${
                                isSelected
                                  ? "border-accent/60 bg-accent/5 ring-1 ring-accent/30 shadow-sm"
                                  : "border-line bg-surface hover:border-accent/30 hover:bg-accent/3"
                              }`}
                            >
                              <div className="flex w-full items-center justify-between">
                                <div className="flex items-center gap-2">
                                  <span className={`h-2 w-2 rounded-full ${hasWaste ? "bg-amber-500" : "bg-emerald-500"}`} />
                                  <span className="text-[13px] font-semibold text-ink truncate max-w-[150px]">{node.label}</span>
                                </div>
                                <span className="font-mono text-[13px] font-bold text-ink">{formatCurrency(nodeCost, currency, 2)}</span>
                              </div>
                              <div className="mt-2 flex w-full items-center justify-between text-[11px]">
                                <span className="text-ink-3">Util: {node.utilization}</span>
                                {hasWaste ? (
                                  <span className="font-medium text-amber-500">Waste: {formatCurrency(node.waste_usd, currency, 0)}</span>
                                ) : (
                                  <span className="font-medium text-emerald-500">✓ Healthy</span>
                                )}
                              </div>
                            </button>
                          );
                        })}
                    </div>
                  </div>

                  {/* Connector */}
                  <div className="flex justify-center">
                    <div className="flex flex-col items-center gap-1">
                      <div className="h-4 w-px bg-gradient-to-b from-accent/40 to-accent/10" />
                      <Icon icon="mdi:arrow-down" className="h-4 w-4 text-accent/50" />
                    </div>
                  </div>

                  {/* Layer 2 – Compute */}
                  <div>
                    <div className="mb-3 flex items-center gap-2">
                      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-red-500/15 text-[10px] font-bold text-red-500">2</span>
                      <span className="text-[11px] font-bold uppercase tracking-widest text-ink-3">Compute Workloads & Clusters</span>
                    </div>
                    <div className="grid grid-cols-1 gap-3">
                      {data.nodes.filter((n) => n.kind === "compute").map((node) => {
                        const isSelected = activeNode?.id === node.id;
                        const nodeCost = getNodeMonthlyCost(node);
                        const isAdjusted = nodeCost < node.monthly_usd;
                        const billShare = Math.round((node.monthly_usd / data.summary.total_monthly_usd) * 100);
                        return (
                          <button
                            key={node.id}
                            onClick={() => setActiveNode(node)}
                            className={`group/card relative flex flex-col overflow-hidden rounded-xl border p-4 text-left transition-all duration-200 ${
                              isSelected
                                ? "border-accent/60 bg-accent/5 ring-1 ring-accent/30"
                                : "border-line bg-surface hover:border-accent/30 hover:bg-accent/3"
                            }`}
                          >
                            {/* Heat bar – visual cost weight */}
                            <div className="absolute top-0 left-0 h-0.5 bg-gradient-to-r from-red-500/60 to-orange-500/30 rounded-t-xl" style={{ width: `${Math.min(100, billShare * 3)}%` }} />

                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2.5">
                                <span className="h-2.5 w-2.5 rounded-full bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.6)] animate-pulse" />
                                <span className="text-[14px] font-bold text-ink">{node.label}</span>
                              </div>
                              <div className="flex items-baseline gap-1.5">
                                <span className="font-mono text-[15px] font-bold text-ink">{formatCurrency(nodeCost, currency, 2)}</span>
                                {isAdjusted && (
                                  <span className="font-mono text-[11.5px] text-emerald-500 line-through opacity-70">{formatCurrency(node.monthly_usd, currency, 2)}</span>
                                )}
                              </div>
                            </div>

                            {node.alert && (
                              <div className="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/8 px-3 py-2 text-[11.5px] text-amber-400 flex items-start gap-2">
                                <Icon icon="mdi:alert" className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                                <span className="leading-relaxed">{node.alert}</span>
                              </div>
                            )}

                            <div className="mt-3 flex items-center justify-between text-[11.5px]">
                              <span className="text-ink-3">Utilization: <strong className="text-ink">{node.utilization}</strong></span>
                              <span className={`font-semibold ${node.waste_usd > 0 ? "text-amber-500" : "text-emerald-500"}`}>
                                {node.waste_usd > 0 ? `Reducible Waste: ${formatCurrency(node.waste_usd, currency, 0)}/mo` : "✓ Optimal"}
                              </span>
                            </div>
                            <ProgressBar pct={billShare} gradient="from-red-500/60 to-orange-400/60" />
                            <div className="mt-1 text-[10px] text-ink-3">{billShare}% of bill</div>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Connector */}
                  <div className="flex justify-center">
                    <div className="flex flex-col items-center gap-1">
                      <div className="h-4 w-px bg-gradient-to-b from-accent/40 to-accent/10" />
                      <Icon icon="mdi:arrow-down" className="h-4 w-4 text-accent/50" />
                    </div>
                  </div>

                  {/* Layer 3 – Databases */}
                  <div>
                    <div className="mb-3 flex items-center gap-2">
                      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-500/15 text-[10px] font-bold text-blue-400">3</span>
                      <span className="text-[11px] font-bold uppercase tracking-widest text-ink-3">Databases, Storage & Cache</span>
                    </div>
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                      {data.nodes
                        .filter((n) => n.kind === "database" || n.kind === "storage" || n.kind === "cache" || n.kind === "monitoring")
                        .map((node) => {
                          const isSelected = activeNode?.id === node.id;
                          const nodeCost = getNodeMonthlyCost(node);
                          const hasWaste = node.waste_usd > 0;
                          return (
                            <button
                              key={node.id}
                              onClick={() => setActiveNode(node)}
                              className={`group/card flex flex-col items-start rounded-xl border p-4 text-left transition-all duration-200 ${
                                isSelected
                                  ? "border-accent/60 bg-accent/5 ring-1 ring-accent/30 shadow-sm"
                                  : "border-line bg-surface hover:border-accent/30 hover:bg-accent/3"
                              }`}
                            >
                              <div className="flex w-full items-center justify-between">
                                <div className="flex items-center gap-2">
                                  <span className={`h-2 w-2 rounded-full ${
                                    node.kind === "database" ? "bg-blue-400" :
                                    node.kind === "storage" ? "bg-green-400" :
                                    node.kind === "cache" ? "bg-purple-400" : "bg-ink-3"
                                  }`} />
                                  <span className="text-[12.5px] font-semibold text-ink truncate max-w-[160px]">{node.label}</span>
                                </div>
                                <span className="font-mono text-[13px] font-bold text-ink">{formatCurrency(nodeCost, currency, 2)}</span>
                              </div>
                              <div className="mt-2 flex w-full items-center justify-between text-[11px]">
                                <span className="text-ink-3">Util: {node.utilization}</span>
                                {hasWaste ? (
                                  <span className="font-semibold text-amber-500">Waste: {formatCurrency(node.waste_usd, currency, 0)}</span>
                                ) : (
                                  <span className="text-emerald-500">Normal</span>
                                )}
                              </div>
                            </button>
                          );
                        })}
                    </div>
                  </div>

                </div>
              </div>

              {/* ── Resource Inspector Panel ── */}
              <div className="relative flex flex-col overflow-hidden rounded-2xl border border-line bg-surface shadow-xs">
                {/* Glow accent top edge */}
                <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-accent/50 to-transparent" />

                {activeNode ? (
                  <>
                    {/* Inspector Header */}
                    <div className="px-5 py-4 border-b border-line bg-gradient-to-r from-sunk/50 to-transparent">
                      <span className="text-[10px] uppercase font-bold tracking-widest text-ink-3">Resource Inspector</span>
                      <h3 className="mt-1 text-[15px] font-bold text-ink leading-tight">{activeNode.label}</h3>
                      <div className="mt-2 flex items-center gap-2">
                        <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-semibold border ${
                          activeNode.status === "healthy"
                            ? "bg-emerald-500/10 text-emerald-500 border-emerald-500/20"
                            : activeNode.status === "warning"
                            ? "bg-amber-500/10 text-amber-500 border-amber-500/20"
                            : "bg-red-500/10 text-red-400 border-red-500/20"
                        }`}>
                          <span className={`h-1.5 w-1.5 rounded-full ${
                            activeNode.status === "healthy" ? "bg-emerald-500" :
                            activeNode.status === "warning" ? "bg-amber-500" : "bg-red-500"
                          } ${activeNode.status !== "healthy" ? "animate-pulse" : ""}`} />
                          {activeNode.status.replace("_", " ")}
                        </span>
                        <span className="text-[11px] text-ink-3">{activeNode.kind}</span>
                      </div>
                    </div>

                    {/* Inspector Body */}
                    <div className="flex-1 overflow-y-auto p-5 space-y-4">

                      {/* Cost card */}
                      <div className="relative overflow-hidden rounded-xl border border-accent-line/30 bg-gradient-to-br from-accent/5 to-transparent p-4">
                        <div className="absolute -top-4 -right-4 h-16 w-16 rounded-full bg-accent/8 blur-xl" />
                        <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-3">Monthly Run-rate</div>
                        <div className="mt-2 flex items-baseline gap-1.5">
                          <span className="font-mono text-[26px] font-bold text-ink">
                            {formatCurrency(getNodeMonthlyCost(activeNode), currency, 2)}
                          </span>
                        </div>
                        <div className="mt-1 text-[11.5px] text-ink-3">
                          {Math.round((activeNode.monthly_usd / data.summary.total_monthly_usd) * 100)}% of total bill
                        </div>
                        {/* Mini spend bar */}
                        <ProgressBar
                          pct={(activeNode.monthly_usd / data.summary.total_monthly_usd) * 100 * 8}
                          gradient="from-accent to-blue-400"
                          className="mt-3 h-1"
                        />
                      </div>

                      {/* Utilization. Computed once so the label color, bar
                          color, and bar width can never disagree about the
                          same node -- they used three different fallback
                          rules for non-numeric utilization values (e.g.
                          "Active Task", "Pay-Per-Request") before this,
                          which could show a red "0%" label next to a green
                          85%-filled bar. */}
                      {(() => {
                        const parsed = parseInt(activeNode.utilization, 10);
                        const utilPct = Number.isNaN(parsed)
                          ? (activeNode.status === "healthy" || activeNode.status === "optimized" ? 85 : 15)
                          : Math.min(100, Math.max(0, parsed));
                        const isLow = utilPct < 30;
                        return (
                          <div className="rounded-xl border border-line bg-sunk p-4">
                            <div className="flex items-center justify-between text-[12px]">
                              <span className="font-semibold text-ink-2">Workload Utilization</span>
                              <span className={`font-mono font-bold ${isLow ? "text-amber-500" : "text-emerald-500"}`}>
                                {activeNode.utilization}
                              </span>
                            </div>
                            <ProgressBar
                              pct={utilPct}
                              gradient={isLow ? "from-amber-500 to-orange-400" : "from-emerald-500 to-teal-400"}
                              className="mt-2.5 h-2"
                              track="bg-surface"
                              transitionClass="transition-all duration-1000 ease-out"
                            />
                            <div className="mt-1.5 flex justify-between text-[10px] text-ink-3">
                              <span>0%</span><span>50%</span><span>100%</span>
                            </div>
                          </div>
                        );
                      })()}

                      {/* Waste info */}
                      {activeNode.waste_usd > 0 && (
                        <div className="rounded-xl border border-amber-500/20 bg-amber-500/6 p-3.5">
                          <div className="flex items-center justify-between">
                            <span className="text-[11.5px] font-semibold text-amber-500">Reducible Waste</span>
                            <span className="font-mono text-[14px] font-bold text-amber-500">{formatCurrency(activeNode.waste_usd, currency, 2)}/mo</span>
                          </div>
                          <div className="mt-1 text-[11px] text-ink-3">Could be eliminated with optimization</div>
                        </div>
                      )}

                      {/* Alert notice */}
                      {activeNode.alert && (
                        <div className="rounded-xl border border-red-500/20 bg-red-500/6 p-4">
                          <div className="flex items-center gap-2 font-semibold text-red-400 text-[12px]">
                            <Icon icon="mdi:alert-decagram" className="h-4 w-4 shrink-0" />
                            FinOps Optimization Notice
                          </div>
                          <p className="mt-2 text-[11.5px] text-ink-2 leading-relaxed">{activeNode.alert}</p>
                        </div>
                      )}

                    </div>

                    {/* CTA */}
                    <div className="p-5 border-t border-line bg-gradient-to-t from-sunk/30 to-transparent">
                      <button
                        onClick={() => setActiveTab("recommendations")}
                        className="group/btn flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-accent to-accent/80 px-4 py-2.5 text-[13px] font-semibold text-white shadow-sm hover:shadow-accent/20 hover:shadow-md transition-all duration-200 hover:-translate-y-0.5"
                      >
                        <Icon icon="mdi:wrench" className="h-4 w-4" />
                        <span>View Remediation Hub</span>
                        <Icon icon="mdi:arrow-right" className="h-4 w-4 group-hover/btn:translate-x-0.5 transition-transform" />
                      </button>
                    </div>
                  </>
                ) : (
                  <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
                    <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-line bg-sunk">
                      <Icon icon="mdi:cursor-default-click-outline" className="h-7 w-7 text-ink-3" />
                    </div>
                    <p className="text-[13px] text-ink-3 leading-relaxed">Click any node in the topology to inspect its telemetry and cost data.</p>
                  </div>
                )}
              </div>

            </div>
          </div>
        )}

        {/* VIEW 2: Cost Reports */}
        {activeTab === "reports" && (
          <div className="mt-6">
            <CostReportView provider={provider} currency={currency} accountId={data.account.id} />
          </div>
        )}

        {/* VIEW 3: Issues (Cloud Waste Remediation Center) */}
        {activeTab === "issues" && (
          <FinOpsIssuesView provider={provider} currency={currency} accountId={data.account.id} />
        )}

        {/* VIEW 4: Active Resources (Cloud Inventory Table) */}
        {activeTab === "resources" && (
          <FinOpsResourcesView
            provider={provider}
            currency={currency}
            accountId={data.account.id}
            onResourceAction={handleResync}
          />
        )}

        {/* VIEW 5: Financial Planning (Budgets & Forecasting) */}
        {activeTab === "planning" && (
          <FinOpsPlanningView
            provider={provider}
            currency={currency}
            accountId={data.account.id}
          />
        )}

        {/* VIEW 6: Recommendations (FinOps Cost Reduction Hub) */}
        {activeTab === "recommendations" && (
          <div className="mt-6 space-y-6">
            <div className="flex items-center justify-between border-b border-line pb-4">
              <div>
                <h3 className="text-[18px] font-bold text-ink flex items-center gap-2">
                  <Icon icon="mdi:lightning-bolt" className="h-5 w-5 text-amber-500" />
                  FinOps Cost Reduction Engine
                </h3>
                <p className="mt-0.5 text-[13px] text-ink-2">
                  Toggle optimizations to simulate live bill reduction. Each recommendation includes production-ready Terraform code.
                </p>
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={() => {
                    const all: Record<string, boolean> = {};
                    data.techniques.forEach((t) => (all[t.id] = true));
                    setAppliedTechniques(all);
                  }}
                  className="text-[12.5px] font-medium text-accent hover:underline"
                >
                  Apply All ({formatCurrency(data.summary.realizable_savings_usd, currency, 0)}/mo)
                </button>
                <span className="text-line">|</span>
                <button
                  onClick={() => setAppliedTechniques({})}
                  className="text-[12.5px] font-medium text-ink-3 hover:text-ink"
                >
                  Reset Simulation
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              {data.techniques.map((tech) => {
                const isApplied = !!appliedTechniques[tech.id];

                return (
                  <div
                    key={tech.id}
                    className={`flex flex-col justify-between rounded-2xl border p-5 transition-all ${
                      isApplied
                        ? "border-emerald-500/40 bg-emerald-500/5 shadow-xs"
                        : "border-line bg-surface hover:border-ink-3/40"
                    }`}
                  >
                    <div>
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="rounded-md bg-sunk px-2 py-0.5 text-[11px] font-medium text-ink-2">
                              {tech.category}
                            </span>
                            <span className="rounded-md bg-accent/10 px-2 py-0.5 text-[11px] font-medium text-accent">
                              {tech.confidence} Confidence
                            </span>
                          </div>
                          <h3 className="mt-2 text-[16px] font-bold text-ink">
                            {tech.name}
                          </h3>
                        </div>

                        <button
                          onClick={() => toggleTechnique(tech.id)}
                          className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                            isApplied ? "bg-emerald-500" : "bg-sunk"
                          }`}
                        >
                          <span
                            className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                              isApplied ? "translate-x-5" : "translate-x-0"
                            }`}
                          />
                        </button>
                      </div>

                      <p className="mt-2.5 text-[13px] leading-relaxed text-ink-2">
                        {tech.description}
                      </p>
                    </div>

                    <div className="mt-5 flex items-center justify-between border-t border-line/60 pt-4">
                      <div className="flex items-baseline gap-1.5">
                        <span className="text-[18px] font-bold text-emerald-500 font-mono">
                          -{formatCurrency(tech.monthly_saving, currency, 0)}
                        </span>
                        <span className="text-[12px] text-ink-3">/ mo savings</span>
                      </div>

                      <button
                        onClick={() => setActiveDiffModal(tech)}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-1.5 text-[12.5px] font-medium text-ink hover:bg-sunk transition-colors"
                      >
                        <TerraformLogo className="h-3.5 w-3.5" />
                        <span>View Terraform Diff</span>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* VIEW 7: Settings & Currency */}
        {activeTab === "settings" && (
          <FinOpsSettingsView
            provider={provider}
            currency={currency}
            onCurrencyChange={(newCurr) => setCurrency(newCurr)}
            accountId={data.account.id}
          />
        )}
      </div>

      {/* Terraform Diff Modal */}
      {activeDiffModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
          <div className="relative w-full max-w-xl rounded-2xl border border-line bg-surface p-6 shadow-2xl">
            <button
              onClick={() => {
                setActiveDiffModal(null);
                setCopiedDiff(false);
              }}
              className="absolute right-4 top-4 rounded-md p-1 text-ink-3 hover:text-ink"
            >
              <Icon icon="mdi:close" className="h-5 w-5" />
            </button>

            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-line bg-sunk">
                <TerraformLogo className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-[17px] font-bold text-ink">
                  Remediated Terraform Code
                </h3>
                <p className="text-[12.5px] text-ink-3">
                  {activeDiffModal.name} (-{formatCurrency(activeDiffModal.monthly_saving, currency, 0)}/mo)
                </p>
              </div>
            </div>

            <div className="mt-3 relative rounded-xl border border-line bg-[#10141a] p-4 font-mono text-[12.5px] text-emerald-400 overflow-x-auto">
              <pre>{activeDiffModal.terraform_diff}</pre>
            </div>

            <div className="mt-6 flex items-center justify-between">
              <span className="text-[12px] text-ink-3">
                Zero-downtime infrastructure update
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(activeDiffModal.terraform_diff);
                    setCopiedDiff(true);
                    setTimeout(() => setCopiedDiff(false), 2000);
                  }}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-4 py-2 text-[13px] font-medium text-ink hover:bg-sunk"
                >
                  <Icon icon={copiedDiff ? "mdi:check" : "mdi:content-copy"} className="h-4 w-4 text-accent" />
                  {copiedDiff ? "Copied Diff" : "Copy Code"}
                </button>
                <button
                  onClick={() => {
                    toggleTechnique(activeDiffModal.id);
                    setActiveDiffModal(null);
                  }}
                  className="rounded-lg bg-accent px-4 py-2 text-[13px] font-semibold text-white hover:opacity-90"
                >
                  {appliedTechniques[activeDiffModal.id] ? "Remove from Simulation" : "Apply to Simulation"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Executive Brief Modal */}
      {showExportModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
          <div className="relative w-full max-w-2xl rounded-2xl border border-line bg-surface p-8 shadow-2xl">
            <button
              onClick={() => setShowExportModal(false)}
              className="absolute right-4 top-4 rounded-md p-1 text-ink-3 hover:text-ink"
            >
              <Icon icon="mdi:close" className="h-5 w-5" />
            </button>

            <div className="border-b border-line pb-4">
              <span className="text-[11px] font-bold uppercase tracking-wider text-accent">
                WhichCloud FinOps Executive Memo
              </span>
              <h2 className="mt-1 text-[22px] font-bold text-ink">
                Cloud Cost Assessment: {data.account.name}
              </h2>
              <p className="mt-0.5 text-[12.5px] text-ink-3">
                Target Cloud: {data.account.cloud_label} • Region: {data.account.region}
              </p>
            </div>

            <div className="mt-6 space-y-4 text-[13.5px] text-ink-2">
              <p>
                <strong>Executive Summary:</strong> An automated telemetry analysis of infrastructure reveals an annual run-rate of{" "}
                <strong className="text-ink">{formatCurrency(data.summary.total_monthly_usd * 12, currency, 0)}</strong>.
              </p>

              <div className="grid grid-cols-3 gap-3 rounded-xl border border-line bg-sunk p-4 text-center">
                <div>
                  <div className="text-[11.5px] text-ink-3">Current Annual Spend</div>
                  <div className="font-mono text-[16px] font-bold text-ink">
                    {formatCurrency(data.summary.total_monthly_usd * 12, currency, 0)}
                  </div>
                </div>
                <div>
                  <div className="text-[11.5px] text-ink-3">Identified Annual Waste</div>
                  <div className="font-mono text-[16px] font-bold text-amber-500">
                    {formatCurrency(data.summary.realizable_savings_usd * 12, currency, 0)}
                  </div>
                </div>
                <div>
                  <div className="text-[11.5px] text-ink-3">Optimized Annual Target</div>
                  <div className="font-mono text-[16px] font-bold text-emerald-500">
                    {formatCurrency((data.summary.total_monthly_usd - data.summary.realizable_savings_usd) * 12, currency, 0)}
                  </div>
                </div>
              </div>

              <div>
                <h4 className="font-bold text-ink text-[14px]">Primary Levers for Immediate Action:</h4>
                <ul className="mt-2 list-disc pl-5 space-y-1">
                  {data.techniques.slice(0, 3).map((t) => (
                    <li key={t.id}>
                      <strong>{t.name}:</strong> Saves {formatCurrency(t.monthly_saving, currency, 0)}/month ({formatCurrency(t.monthly_saving * 12, currency, 0)}/yr).
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="mt-8 flex justify-end gap-3 pt-2">
              <button
                onClick={() => window.print()}
                className="inline-flex items-center gap-1.5 rounded-lg border border-line px-4 py-2 text-[13px] font-medium text-ink hover:bg-sunk"
              >
                <Icon icon="mdi:printer" className="h-4 w-4" />
                Print / Save PDF
              </button>
              <button
                onClick={() => setShowExportModal(false)}
                className="rounded-lg bg-accent px-5 py-2 text-[13px] font-semibold text-white hover:opacity-90"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function FinOpsDashboardPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[50vh] items-center justify-center">
          <Icon icon="line-md:loading-loop" className="h-8 w-8 text-accent animate-spin" />
        </div>
      }
    >
      <FinOpsContent />
    </Suspense>
  );
}
