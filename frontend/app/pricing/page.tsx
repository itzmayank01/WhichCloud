"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Icon } from "@iconify/react";
import { useAuth } from "@clerk/nextjs";
import { money } from "@/lib/api";
import { TerraformLogo } from "@/components/Logo";

interface PlanTier {
  id: string;
  name: string;
  badge?: string;
  tagline: string;
  monthlyPrice: number;
  annualPricePerMonth: number;
  popular?: boolean;
  ctaText: string;
  ctaHref: string;
  features: {
    name: string;
    detail?: string;
    highlight?: boolean;
  }[];
  notIncluded?: string[];
}

const PLANS: PlanTier[] = [
  {
    id: "free",
    name: "Starter / Free",
    tagline: "Explore the multi-cloud price index and size simple workloads.",
    monthlyPrice: 0,
    annualPricePerMonth: 0,
    ctaText: "Get Started Free",
    ctaHref: "/estimate",
    features: [
      { name: "36,000+ catalog SKU lookup across AWS, GCP, Azure" },
      { name: "3 architecture estimates per month" },
      { name: "Three-tier architecture comparison (Cheapest, Reliable, Optimized)" },
      { name: "Interactive architecture diagram viewer & SVG export" },
      { name: "Single-file starter Terraform preview" },
      { name: "Demo sandbox access in FinOps Live" },
      { name: "Community Discord support" },
    ],
    notIncluded: [
      "Production multi-module Terraform ZIP with KMS & IAM",
      "Live AWS account connection via STS AssumeRole",
      "Automated idle waste detection & 1-click remediation",
      "Multi-environment IaC drift detection (dev/staging/prod)",
      "Saved architecture projects library",
    ],
  },
  {
    id: "pro",
    name: "Pro Engineer",
    badge: "Most Popular",
    tagline: "For freelance architects, senior DevOps engineers, and fast-moving founders.",
    monthlyPrice: 29,
    annualPricePerMonth: 24, // $290/year (saves 17%)
    popular: true,
    ctaText: "Upgrade to Pro",
    ctaHref: "/dashboard",
    features: [
      { name: "Unlimited architecture generation across all 7 archetypes", highlight: true },
      { name: "Full production Terraform ZIP exports (Modules, KMS, IAM, variables, cost markdown)", highlight: true },
      { name: "Connect 1 live AWS account via read-only STS AssumeRole", highlight: true },
      { name: "Real-time FinOps waste detection (unattached EBS, idle NAT, unused IPs)", highlight: true },
      { name: "1-click Terraform remediation diffs to kill cloud waste", highlight: true },
      { name: "Save up to 25 architecture projects in your Projects Hub" },
      { name: "Bill CSV audit up to 50MB with instant anomaly detection" },
      { name: "Multi-cloud migration sizing (Windows/x86/Graviton compatibility checks)" },
      { name: "Priority email & ticket support (within 4 hours)" },
    ],
    notIncluded: [
      "Multi-account AWS Organizations & multi-cloud fleet monitoring",
      "Multi-environment lifecycle & automated drift detection",
      "Shared team workspaces & RBAC via Clerk Organizations",
    ],
  },
  {
    id: "team",
    name: "Team & Scale",
    badge: "Best Value for Teams",
    tagline: "For scaling startups and platform engineering teams managing multi-cloud infrastructure.",
    monthlyPrice: 99,
    annualPricePerMonth: 82, // $990/year (saves 17%)
    ctaText: "Start Team Plan",
    ctaHref: "/dashboard",
    features: [
      { name: "Connect up to 5 cloud accounts (AWS Organizations / GCP / Azure)", highlight: true },
      { name: "Multi-Environment IaC Studio (/environments) with automated drift sync", highlight: true },
      { name: "Unlimited saved architecture projects & revision history", highlight: true },
      { name: "Team workspaces & role-based access control via Clerk Organizations" },
      { name: "Continuous CloudWatch & Cost Explorer telemetry polling" },
      { name: "Weekly automated FinOps spend & waste digest reports" },
      { name: "GitHub PR export & CI/CD pipeline integration" },
      { name: "Custom tagging conventions & budget threshold alerts" },
      { name: "Dedicated private Slack channel support with cloud architects" },
    ],
    notIncluded: [
      "Custom Enterprise Discount Program (EDP) catalog pricing",
      "Custom IaC templates (Terragrunt, Pulumi, CloudFormation)",
    ],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    tagline: "For high-scale enterprises needing custom pricing, EDP contracts, and private compliance.",
    monthlyPrice: 499,
    annualPricePerMonth: 415,
    ctaText: "Contact Cloud Architect",
    ctaHref: "mailto:sales@whichcloud.com?subject=WhichCloud%20Enterprise%20Inquiry",
    features: [
      { name: "Unlimited cloud accounts, AWS Organizations & multi-cloud fleets", highlight: true },
      { name: "Custom Private Pricing Agreements (PPA) & AWS EDP discount rates", highlight: true },
      { name: "Custom IaC generators: Terragrunt, Pulumi & CloudFormation", highlight: true },
      { name: "Dedicated VPC peering / self-hosted private backend option" },
      { name: "SAML 2.0 / Okta / Azure AD enterprise Single Sign-On" },
      { name: "Custom FinOps compliance, SOC 2 and ISO 27001 audit packs" },
      { name: "Dedicated senior cloud architect for quarterly architecture reviews" },
      { name: "99.95% uptime SLA & 1-hour response time guarantee" },
    ],
  },
];

const COMPARISON_SECTIONS = [
  {
    title: "Architecture & Sizing Engine",
    items: [
      { name: "Multi-cloud price catalog (AWS, GCP, Azure)", free: "36,000+ SKUs", pro: "36,000+ SKUs", team: "36,000+ SKUs", ent: "Custom EDP + Catalog" },
      { name: "Monthly architecture estimates", free: "3 / month", pro: "Unlimited", team: "Unlimited", ent: "Unlimited" },
      { name: "Supported archetypes", free: "Web apps only", pro: "All 7 archetypes", team: "All 7 archetypes", ent: "All + Custom" },
      { name: "Deterministic multi-tier comparison", free: true, pro: true, team: true, ent: true },
      { name: "Interactive visual diagram canvas", free: true, pro: true, team: true, ent: true },
      { name: "Export architecture diagrams (SVG/PNG)", free: true, pro: true, team: true, ent: true },
      { name: "Migration & Graviton compatibility checks", free: false, pro: true, team: true, ent: true },
    ],
  },
  {
    title: "Terraform & Infrastructure as Code (IaC)",
    items: [
      { name: "Single-file starter Terraform preview", free: true, pro: true, team: true, ent: true },
      { name: "Production multi-module ZIP export", free: false, pro: true, team: true, ent: true },
      { name: "KMS encryption & IAM least-privilege policies", free: false, pro: true, team: true, ent: true },
      { name: "Environment variables & terraform.tfvars", free: false, pro: true, team: true, ent: true },
      { name: "Detailed cost report markdown documentation", free: false, pro: true, team: true, ent: true },
      { name: "Custom module templates (Terragrunt, Pulumi)", free: false, pro: false, team: false, ent: true },
    ],
  },
  {
    title: "Live FinOps & Account Waste Elimination",
    items: [
      { name: "AWS STS AssumeRole connection", free: "Demo sandbox", pro: "1 account", team: "5 accounts", ent: "Unlimited" },
      { name: "Real-time waste detection (EBS, NAT, IPs, S3)", free: false, pro: true, team: true, ent: true },
      { name: "1-click Terraform remediation diffs", free: false, pro: true, team: true, ent: true },
      { name: "Historical bill CSV auditor", free: "5MB max", pro: "50MB max", team: "250MB max", ent: "Direct CUR warehouse" },
      { name: "Weekly automated spend anomaly digest", free: false, pro: false, team: true, ent: true },
    ],
  },
  {
    title: "Multi-Environment Lifecycle & Governance",
    items: [
      { name: "Multi-Env Studio (dev, staging, prod)", free: false, pro: "Single user", team: "Full multi-env", ent: "Full + Custom envs" },
      { name: "Live infrastructure drift detection", free: false, pro: "Manual scan", team: "Continuous", ent: "Continuous + alerts" },
      { name: "Environment state locking & rollback simulation", free: false, pro: false, team: true, ent: true },
      { name: "Saved architecture projects library", free: "None", pro: "Up to 25", team: "Unlimited", ent: "Unlimited" },
      { name: "Team collaboration & Clerk Organizations", free: false, pro: false, team: true, ent: true },
      { name: "Support SLA", free: "Community", pro: "Priority email (4h)", team: "Dedicated Slack", ent: "Dedicated architect + 1h SLA" },
    ],
  },
];

const FAQS = [
  {
    q: "Why should I pay for WhichCloud if I can use the cloud provider's calculator?",
    a: "Cloud provider calculators require you to already know every exact instance type, EBS IOPS, and network egress rule before you begin, and they never tell you where you are overpaying. WhichCloud translates plain English requirements into three production-tested architecture options, shows what each dollar buys in reliability, generates ready-to-run Terraform in 60 seconds, and continuously connects to your real AWS account to eliminate 20% to 35% in idle waste.",
  },
  {
    q: "How does WhichCloud connect to our AWS account safely?",
    a: "WhichCloud uses standard AWS IAM STS AssumeRole with an external ID. You deploy a read-only role directly from your AWS CloudShell in 30 seconds. WhichCloud never asks for or stores AWS root credentials, secret keys, or write permissions. The role is strictly limited to Cost Explorer (ce:*), CloudWatch metrics, and read-only describe calls.",
  },
  {
    q: "How fast do paid plans pay for themselves?",
    a: "For virtually all customers, WhichCloud pays for itself within the first 48 hours. A single unattached EBS gp2 volume costs $10-$40/month; an idle NAT gateway costs $35/month plus data; an unassociated Elastic IP costs $3.60/month. Finding just one idle NAT gateway or downsizing one oversized RDS instance saves more than the entire $29/month Pro subscription.",
  },
  {
    q: "Can I cancel or change my plan anytime?",
    a: "Yes. There are no long-term lock-ins. You can upgrade, downgrade, or cancel your subscription anytime directly from your dashboard or billing settings. If you cancel, your access continues until the end of your billing cycle.",
  },
  {
    q: "Do you offer discounts for open source projects or startups?",
    a: "Yes! If you are an early-stage bootstrapped founder, non-profit, or open source maintainer, reach out to us at support@whichcloud.com and we will set you up with extended Pro access.",
  },
];

export default function PricingPage() {
  const { isSignedIn } = useAuth();
  const [annual, setAnnual] = useState(true);

  // ROI Calculator state
  const [monthlySpend, setMonthlySpend] = useState<number>(4500);

  // Typical cloud waste is 24% of spend
  const estimatedWasteMonthly = Math.round(monthlySpend * 0.24);
  const estimatedSavingsAnnual = estimatedWasteMonthly * 12;
  const proAnnualCost = 290;
  const netRoiMultiplier = Math.max(1, Math.round(estimatedSavingsAnnual / proAnnualCost));

  return (
    <div className="min-h-screen bg-canvas text-ink">
      {/* Hero Section */}
      <section className="relative px-6 pt-16 pb-20 text-center md:pt-24 md:pb-28">
        <div className="mx-auto max-w-4xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3.5 py-1.5 text-[13.5px] font-medium text-accent">
            <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
            Clear ROI · Pre-Flight Sizing · Live FinOps Waste Elimination
          </div>

          <h1 className="mt-6 text-balance text-[clamp(2.25rem,5vw,3.75rem)] font-semibold leading-[1.08] tracking-[-0.035em]">
            Invest in clarity. <br className="hidden sm:inline" />
            <span className="text-accent">Save thousands</span> on cloud bills every month.
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-[17px] leading-relaxed text-ink-2 md:text-[18.5px]">
            From solo engineers delivering client proposals to DevOps teams managing multi-environment infrastructure.
            Stop guessing AWS bills and eliminate cloud waste with verified architecture and Terraform.
          </p>

          {/* Billing Cycle Toggle */}
          <div className="mt-10 flex items-center justify-center gap-4">
            <span className={`text-[15px] font-medium transition-colors ${!annual ? "text-ink font-semibold" : "text-ink-3"}`}>
              Monthly billing
            </span>
            <button
              onClick={() => setAnnual(!annual)}
              type="button"
              role="switch"
              aria-checked={annual}
              className="relative inline-flex h-8 w-15 shrink-0 cursor-pointer rounded-full border-2 border-line bg-surface p-0.5 transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-accent"
            >
              <span
                className={`pointer-events-none inline-block h-6.5 w-6.5 transform rounded-full bg-accent shadow-sm ring-0 transition duration-200 ease-in-out ${
                  annual ? "translate-x-7" : "translate-x-0"
                }`}
              />
            </button>
            <div className="flex items-center gap-2">
              <span className={`text-[15px] font-medium transition-colors ${annual ? "text-ink font-semibold" : "text-ink-3"}`}>
                Annual billing
              </span>
              <span className="rounded-full bg-accent/15 px-2.5 py-0.5 text-[12px] font-semibold text-accent">
                Save ~17% (2 Months Free)
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Pricing Cards Grid */}
      <section className="px-6 pb-24">
        <div className="mx-auto grid max-w-6xl gap-8 lg:grid-cols-4">
          {PLANS.map((plan) => {
            const price = annual ? plan.annualPricePerMonth : plan.monthlyPrice;

            return (
              <div
                key={plan.id}
                className={`relative flex flex-col justify-between rounded-2xl border p-7 transition-all duration-200 ${
                  plan.popular
                    ? "border-accent bg-surface shadow-xl ring-2 ring-accent/20"
                    : "border-line bg-surface/60 hover:border-line-strong hover:bg-surface"
                }`}
              >
                {plan.badge && (
                  <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 rounded-full bg-accent px-3 py-1 text-[11.5px] font-semibold uppercase tracking-wider text-canvas shadow-sm">
                    {plan.badge}
                  </div>
                )}

                <div>
                  <div className="flex items-center justify-between">
                    <h3 className="text-[20px] font-bold tracking-tight text-ink">{plan.name}</h3>
                  </div>
                  <p className="mt-2.5 text-[14px] leading-relaxed text-ink-2 min-h-[42px]">{plan.tagline}</p>

                  {/* Price */}
                  <div className="mt-6 flex items-baseline gap-1.5 border-b border-line pb-6">
                    <span className="font-mono text-[36px] font-bold tracking-tight text-ink">
                      ${price}
                    </span>
                    <span className="text-[14px] text-ink-3">
                      {plan.monthlyPrice === 0 ? "forever" : "/month"}
                    </span>
                    {annual && plan.monthlyPrice > 0 && (
                      <span className="ml-auto rounded bg-accent/10 px-2 py-0.5 text-[11px] font-medium text-accent">
                        billed annually
                      </span>
                    )}
                  </div>

                  {/* Features List */}
                  <div className="mt-6 space-y-3">
                    <div className="text-[12px] font-semibold uppercase tracking-wider text-ink-3">
                      Included in this plan:
                    </div>
                    {plan.features.map((feat, i) => (
                      <div key={i} className="flex items-start gap-2.5 text-[14px] leading-snug">
                        <Icon
                          icon="heroicons:check-circle-20-solid"
                          className={`mt-0.5 h-4 w-4 shrink-0 ${
                            feat.highlight ? "text-accent" : "text-emerald-500"
                          }`}
                        />
                        <span className={feat.highlight ? "font-medium text-ink" : "text-ink-2"}>
                          {feat.name}
                        </span>
                      </div>
                    ))}

                    {plan.notIncluded && plan.notIncluded.length > 0 && (
                      <div className="pt-2 space-y-2">
                        {plan.notIncluded.map((notFeat, i) => (
                          <div key={i} className="flex items-start gap-2.5 text-[13px] text-ink-3 opacity-60">
                            <Icon icon="heroicons:x-mark-20-solid" className="mt-0.5 h-4 w-4 shrink-0 text-ink-3" />
                            <span>{notFeat}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* CTA Button */}
                <div className="mt-8 pt-4">
                  <Link
                    href={plan.ctaHref}
                    className={`block w-full rounded-xl py-3 text-center text-[15px] font-semibold transition-all duration-150 ${
                      plan.popular
                        ? "bg-accent text-canvas shadow-md hover:opacity-95 active:scale-[.98]"
                        : "border border-line bg-surface text-ink hover:bg-sunk active:scale-[.98]"
                    }`}
                  >
                    {plan.ctaText}
                  </Link>
                  <p className="mt-2 text-center text-[11.5px] text-ink-3">
                    {plan.monthlyPrice === 0 ? "No credit card required" : "30-day money-back guarantee"}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Interactive Cloud Waste & ROI Calculator */}
      <section className="border-t border-line bg-surface/40 px-6 py-20">
        <div className="mx-auto max-w-4xl">
          <div className="text-center">
            <div className="inline-flex items-center gap-1.5 font-mono text-[13px] font-semibold uppercase tracking-[0.12em] text-accent">
              <Icon icon="heroicons:calculator-solid" className="h-4 w-4" />
              Interactive Return On Investment (ROI)
            </div>
            <h2 className="mt-3 text-[clamp(1.75rem,3.5vw,2.5rem)] font-bold tracking-tight">
              See how much WhichCloud saves you
            </h2>
            <p className="mx-auto mt-3 max-w-2xl text-[16px] text-ink-2">
              Based on empirical AWS and GCP telemetry, organizations waste an average of 24% of their cloud budget on unattached storage, idle gateways, and over-provisioned instances.
            </p>
          </div>

          <div className="mt-12 rounded-2xl border border-line bg-surface p-8 shadow-sm md:p-10">
            <div className="grid gap-8 md:grid-cols-2 md:items-center">
              <div>
                <label htmlFor="spend-slider" className="block text-[15px] font-semibold text-ink">
                  Your approximate monthly cloud bill:
                </label>
                <div className="mt-3 flex items-center gap-3">
                  <span className="font-mono text-[32px] font-bold text-accent">
                    {money(monthlySpend)}
                  </span>
                  <span className="text-[14px] text-ink-3">/month</span>
                </div>

                <input
                  id="spend-slider"
                  type="range"
                  min="500"
                  max="30000"
                  step="250"
                  value={monthlySpend}
                  onChange={(e) => setMonthlySpend(Number(e.target.value))}
                  className="mt-6 w-full accent-accent cursor-pointer"
                />
                <div className="flex justify-between font-mono text-[12px] text-ink-3 mt-1">
                  <span>$500/mo</span>
                  <span>$15,000/mo</span>
                  <span>$30,000+/mo</span>
                </div>

                <p className="mt-6 text-[13.5px] leading-relaxed text-ink-2">
                  <strong className="text-ink">Common waste sources detected:</strong> Unattached EBS volumes ($20-$60/ea), idle NAT gateways ($35/mo + data charges), unassociated Elastic IPs ($3.60/mo), and oversized Multi-AZ databases.
                </p>
              </div>

              <div className="rounded-xl border border-line/80 bg-canvas/70 p-6 space-y-4">
                <div className="flex items-center justify-between border-b border-line pb-3">
                  <span className="text-[14px] text-ink-2">Estimated Monthly Waste:</span>
                  <span className="font-mono text-[18px] font-bold text-caution">
                    ~{money(estimatedWasteMonthly)}/mo
                  </span>
                </div>

                <div className="flex items-center justify-between border-b border-line pb-3">
                  <span className="text-[14px] text-ink-2">Estimated Annual Savings:</span>
                  <span className="font-mono text-[22px] font-bold text-emerald-500">
                    {money(estimatedSavingsAnnual)}/yr
                  </span>
                </div>

                <div className="flex items-center justify-between border-b border-line pb-3">
                  <span className="text-[14px] text-ink-2">WhichCloud Pro Cost:</span>
                  <span className="font-mono text-[15px] text-ink-2 font-medium">
                    ${proAnnualCost}/yr
                  </span>
                </div>

                <div className="rounded-lg bg-accent/10 p-4 text-center">
                  <div className="text-[13px] font-medium text-accent uppercase tracking-wider">
                    Calculated Annual ROI
                  </div>
                  <div className="font-mono text-[34px] font-extrabold text-accent mt-0.5">
                    {netRoiMultiplier}x Return
                  </div>
                  <p className="text-[12px] text-ink-2 mt-1">
                    WhichCloud Pro pays for itself in less than <strong>10 days</strong>.
                  </p>
                </div>

                <Link
                  href="/connect"
                  className="mt-3 block w-full rounded-xl bg-accent py-2.5 text-center text-[14px] font-semibold text-canvas transition hover:opacity-90"
                >
                  Connect AWS Account & Find Waste
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Comparison Matrix */}
      <section className="px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <div className="text-center">
            <h2 className="text-[clamp(1.75rem,3.5vw,2.5rem)] font-bold tracking-tight">
              Detailed Plan Comparison
            </h2>
            <p className="mx-auto mt-3 max-w-2xl text-[16px] text-ink-2">
              Every capability engineered with production-tested accuracy and zero handcoded fluff.
            </p>
          </div>

          <div className="mt-12 overflow-x-auto rounded-2xl border border-line bg-surface shadow-sm">
            <table className="w-full min-w-[760px] border-collapse text-left text-[14px]">
              <thead>
                <tr className="border-b border-line bg-sunk/60 text-ink">
                  <th className="py-4.5 px-6 font-semibold w-2/5">Platform Feature</th>
                  <th className="py-4.5 px-4 font-semibold text-center w-[15%]">Free</th>
                  <th className="py-4.5 px-4 font-semibold text-center w-[15%] text-accent bg-accent/5">Pro ($29)</th>
                  <th className="py-4.5 px-4 font-semibold text-center w-[15%]">Team ($99)</th>
                  <th className="py-4.5 px-4 font-semibold text-center w-[15%]">Enterprise</th>
                </tr>
              </thead>
              <tbody>
                {COMPARISON_SECTIONS.map((section, sIdx) => (
                  <React.Fragment key={sIdx}>
                    <tr className="border-b border-line/80 bg-canvas/40 font-semibold text-ink">
                      <td colSpan={5} className="py-3 px-6 text-[13px] uppercase tracking-wider text-ink-3">
                        {section.title}
                      </td>
                    </tr>
                    {section.items.map((item, iIdx) => (
                      <tr key={iIdx} className="border-b border-line/40 hover:bg-sunk/30 transition-colors">
                        <td className="py-3.5 px-6 text-ink-2 font-medium">{item.name}</td>
                        <td className="py-3.5 px-4 text-center">
                          {typeof item.free === "boolean" ? (
                            item.free ? (
                              <Icon icon="heroicons:check-20-solid" className="h-5 w-5 mx-auto text-emerald-500" />
                            ) : (
                              <Icon icon="heroicons:minus-20-solid" className="h-5 w-5 mx-auto text-ink-3/50" />
                            )
                          ) : (
                            <span className="text-[13px] text-ink-2">{item.free}</span>
                          )}
                        </td>
                        <td className="py-3.5 px-4 text-center bg-accent/5 font-medium">
                          {typeof item.pro === "boolean" ? (
                            item.pro ? (
                              <Icon icon="heroicons:check-20-solid" className="h-5 w-5 mx-auto text-accent" />
                            ) : (
                              <Icon icon="heroicons:minus-20-solid" className="h-5 w-5 mx-auto text-ink-3/50" />
                            )
                          ) : (
                            <span className="text-[13px] text-ink font-semibold">{item.pro}</span>
                          )}
                        </td>
                        <td className="py-3.5 px-4 text-center">
                          {typeof item.team === "boolean" ? (
                            item.team ? (
                              <Icon icon="heroicons:check-20-solid" className="h-5 w-5 mx-auto text-emerald-500" />
                            ) : (
                              <Icon icon="heroicons:minus-20-solid" className="h-5 w-5 mx-auto text-ink-3/50" />
                            )
                          ) : (
                            <span className="text-[13px] text-ink-2">{item.team}</span>
                          )}
                        </td>
                        <td className="py-3.5 px-4 text-center">
                          {typeof item.ent === "boolean" ? (
                            item.ent ? (
                              <Icon icon="heroicons:check-20-solid" className="h-5 w-5 mx-auto text-emerald-500" />
                            ) : (
                              <Icon icon="heroicons:minus-20-solid" className="h-5 w-5 mx-auto text-ink-3/50" />
                            )
                          ) : (
                            <span className="text-[13px] text-ink-2">{item.ent}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Social Proof & Quotes */}
      <section className="border-t border-line bg-surface/50 px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <div className="grid gap-8 md:grid-cols-3">
            <div className="rounded-xl border border-line bg-surface p-6 shadow-sm">
              <div className="flex items-center gap-1 text-amber-400">
                {[...Array(5)].map((_, i) => (
                  <Icon key={i} icon="heroicons:star-solid" className="h-4 w-4" />
                ))}
              </div>
              <p className="mt-3.5 text-[14.5px] leading-relaxed text-ink-2 italic">
                &ldquo;WhichCloud reduced my proposal preparation time from 8 hours to 15 minutes. Clients love seeing the three priced tiers, and getting production Terraform immediately seals the deal.&rdquo;
              </p>
              <div className="mt-4 pt-3 border-t border-line text-[13px]">
                <div className="font-semibold text-ink">Devon R.</div>
                <div className="text-ink-3">Independent Cloud Architect</div>
              </div>
            </div>

            <div className="rounded-xl border border-line bg-surface p-6 shadow-sm">
              <div className="flex items-center gap-1 text-amber-400">
                {[...Array(5)].map((_, i) => (
                  <Icon key={i} icon="heroicons:star-solid" className="h-4 w-4" />
                ))}
              </div>
              <p className="mt-3.5 text-[14.5px] leading-relaxed text-ink-2 italic">
                &ldquo;Connected our AWS account via CloudShell in 30 seconds. FinOps Live identified 6 unattached EBS volumes and an idle RDS test instance, cutting our bill by $820/month.&rdquo;
              </p>
              <div className="mt-4 pt-3 border-t border-line text-[13px]">
                <div className="font-semibold text-ink">Priya M.</div>
                <div className="text-ink-3">CTO at PayScale Labs</div>
              </div>
            </div>

            <div className="rounded-xl border border-line bg-surface p-6 shadow-sm">
              <div className="flex items-center gap-1 text-amber-400">
                {[...Array(5)].map((_, i) => (
                  <Icon key={i} icon="heroicons:star-solid" className="h-4 w-4" />
                ))}
              </div>
              <p className="mt-3.5 text-[14.5px] leading-relaxed text-ink-2 italic">
                &ldquo;The Multi-Env IaC feature stopped staging and production drift completely. The Graviton auto-recommendations alone cut our compute spend by 19% across environments.&rdquo;
              </p>
              <div className="mt-4 pt-3 border-t border-line text-[13px]">
                <div className="font-semibold text-ink">Alex K.</div>
                <div className="text-ink-3">Lead Platform Engineer</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Frequently Asked Questions */}
      <section className="px-6 py-24">
        <div className="mx-auto max-w-3xl">
          <div className="text-center">
            <h2 className="text-[clamp(1.75rem,3.5vw,2.5rem)] font-bold tracking-tight">
              Frequently Asked Questions
            </h2>
            <p className="mt-3 text-[16px] text-ink-2">
              Everything you need to know about plans, security, and billing.
            </p>
          </div>

          <div className="mt-12 space-y-6">
            {FAQS.map((faq, idx) => (
              <div key={idx} className="rounded-xl border border-line bg-surface p-6 shadow-sm">
                <h3 className="text-[17px] font-semibold text-ink">{faq.q}</h3>
                <p className="mt-2.5 text-[15px] leading-relaxed text-ink-2">{faq.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Final Action CTA */}
      <section className="border-t border-line bg-[#0d1414] px-6 py-24 text-center text-white">
        <div className="mx-auto max-w-3xl">
          <h2 className="text-balance text-[clamp(2rem,4.5vw,3rem)] font-bold leading-tight">
            Stop overpaying the cloud providers.
          </h2>
          <p className="mt-4 text-[17px] text-zinc-300">
            Design right, build fast with audited Terraform, and eliminate idle waste starting today.
          </p>

          <div className="mt-9 flex flex-wrap items-center justify-center gap-4">
            <Link
              href={isSignedIn ? "/dashboard" : "/sign-up?redirect_url=/pricing"}
              className="rounded-xl bg-accent px-8 py-3.5 text-[16px] font-semibold text-canvas transition-all hover:opacity-95 active:scale-[.98]"
            >
              Start Free Trial · Pro Access
            </Link>
            <Link
              href="/estimate"
              className="rounded-xl border border-zinc-700 bg-zinc-800/80 px-8 py-3.5 text-[16px] font-semibold text-white transition hover:bg-zinc-700"
            >
              Price an Architecture First
            </Link>
          </div>

          <p className="mt-6 font-mono text-[13px] text-zinc-400">
            No credit card required for Starter · Instant CloudShell STS connect · Cancel anytime
          </p>
        </div>
      </section>
    </div>
  );
}

