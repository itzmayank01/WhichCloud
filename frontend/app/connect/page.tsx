"use client";

import Link from "next/link";
import { useState } from "react";
import { Icon } from "@iconify/react";

interface ProviderItem {
  id: string;
  name: string;
  logo: string;
  description: string;
  route?: string;
  badge?: string;
  enabled: boolean;
}

const PROVIDERS: ProviderItem[] = [
  {
    id: "aws",
    name: "AWS",
    logo: "logos:aws",
    description: "Connect Cost Explorer & cross-account IAM role",
    route: "/connect/aws",
    enabled: true,
  },
  {
    id: "azure",
    name: "Azure",
    logo: "logos:microsoft-azure",
    description: "Connect Service Principal & Cost Management",
    route: "/connect/azure",
    enabled: true,
  },
  {
    id: "gcp",
    name: "GCP",
    logo: "logos:google-cloud",
    description: "Connect BigQuery billing export & project IAM",
    route: "/connect/gcp",
    enabled: true,
  },
  {
    id: "github",
    name: "GitHub",
    logo: "logos:github-icon",
    description: "Scan Terraform / IaC repository to map architecture",
    route: "/connect/github",
    enabled: true,
    badge: "IaC Sync",
  },
  {
    id: "fastly",
    name: "Fastly",
    logo: "logos:fastly",
    description: "CDN and edge compute billing metrics",
    badge: "Soon",
    enabled: false,
  },
  {
    id: "snowflake",
    name: "Snowflake",
    logo: "logos:snowflake-icon",
    description: "Warehouse compute credits and storage",
    badge: "Soon",
    enabled: false,
  },
  {
    id: "datadog",
    name: "Datadog",
    logo: "logos:datadog-icon",
    description: "APM, custom metrics and ingest spend",
    badge: "Soon",
    enabled: false,
  },
  {
    id: "planetscale",
    name: "PlanetScale",
    logo: "simple-icons:planetscale",
    description: "Serverless MySQL database cost analytics",
    badge: "Soon",
    enabled: false,
  },
  {
    id: "newrelic",
    name: "New Relic",
    logo: "logos:new-relic-icon",
    description: "Observability compute and log query units",
    badge: "Soon",
    enabled: false,
  },
];

export default function ConnectAccountsPage() {
  const [invited, setInvited] = useState(false);
  const [emailInput, setEmailInput] = useState("");
  const [showInviteModal, setShowInviteModal] = useState(false);

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-col items-center px-6 py-16">
      {/* Header section matching reference */}
      <div className="text-center">
        <h1 className="text-[34px] font-bold tracking-tight text-ink sm:text-[40px]">
          Connect Accounts
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-[16px] leading-relaxed text-ink-2">
          WhichCloud will automatically begin crunching your cloud cost data
          once your accounts have been connected.
        </p>

        <div className="mt-7 flex flex-wrap items-center justify-center gap-4">
          <button
            onClick={() => setShowInviteModal(true)}
            className="rounded-lg border border-line bg-surface px-5 py-2 text-[14px] font-medium text-ink shadow-xs transition-colors hover:bg-sunk hover:border-line-strong"
          >
            Invite My Team First
          </button>
          <Link
            href="/finops?provider=aws&account_id=demo"
            className="inline-flex items-center gap-2 rounded-lg bg-accent px-5 py-2 text-[14px] font-medium text-white transition-opacity hover:opacity-95"
          >
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            Explore Live Demo Account
          </Link>
        </div>
      </div>

      {/* Grid of Providers */}
      <div className="mt-14 grid w-full grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {PROVIDERS.map((provider) => {
          const CardContent = (
            <div
              className={`group flex h-full flex-col justify-between rounded-xl border p-5 transition-all duration-200 ${
                provider.enabled
                  ? "border-line bg-surface hover:border-line-strong hover:shadow-md cursor-pointer"
                  : "border-line/60 bg-surface/50 opacity-60 cursor-not-allowed"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-surface border border-line p-2">
                    <Icon icon={provider.logo} width={24} height={24} />
                  </div>
                  <div>
                    <span className="text-[16px] font-semibold text-ink">
                      {provider.name}
                    </span>
                    {provider.badge && (
                      <span className="ml-2 rounded-full bg-accent-wash px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-accent">
                        {provider.badge}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <p className="mt-3 text-[13px] leading-snug text-ink-3">
                {provider.description}
              </p>

              <div className="mt-5 border-t border-line/70 pt-3">
                <span
                  className={`inline-flex items-center gap-1.5 text-[13px] font-semibold transition-colors ${
                    provider.enabled
                      ? "text-accent group-hover:underline"
                      : "text-ink-3"
                  }`}
                >
                  {provider.enabled ? "Connect Now" : "Coming Soon"}
                  {provider.enabled && <span>&rarr;</span>}
                </span>
              </div>
            </div>
          );

          if (provider.enabled && provider.route) {
            return (
              <Link key={provider.id} href={provider.route} className="block">
                {CardContent}
              </Link>
            );
          }

          return <div key={provider.id}>{CardContent}</div>;
        })}
      </div>

      {/* Security Guarantee callout */}
      <div className="mt-16 w-full rounded-2xl border border-line bg-surface p-6 shadow-xs sm:p-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="max-w-2xl">
            <div className="flex items-center gap-2 font-mono text-[12.5px] font-medium uppercase tracking-[0.14em] text-accent">
              <Icon icon="mdi:shield-check" className="h-4 w-4" />
              Enterprise Zero-Trust Security
            </div>
            <h3 className="mt-1 text-[18px] font-semibold text-ink">
              Read-Only Access via Cross-Account IAM & Service Principals
            </h3>
            <p className="mt-1 text-[14px] leading-relaxed text-ink-2">
              We never ask for root keys or write permissions. WhichCloud uses temporary STS AssumeRole credentials with unique External IDs or BigQuery data reader roles that you can revoke in 1 click at any time.
            </p>
          </div>
          <div className="shrink-0">
            <Link
              href="/#provenance"
              className="inline-flex items-center gap-1 text-[14px] font-medium text-accent hover:underline"
            >
              Read Security Whitepaper &rarr;
            </Link>
          </div>
        </div>
      </div>

      {/* Team Invite Modal */}
      {showInviteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs">
          <div className="w-full max-w-md rounded-2xl border border-line bg-surface p-6 shadow-2xl">
            <h3 className="text-[19px] font-semibold text-ink">
              Invite Engineering & FinOps Teammates
            </h3>
            <p className="mt-1.5 text-[14px] text-ink-2">
              Add your colleagues who manage cloud billing or Terraform modules.
            </p>

            {invited ? (
              <div className="mt-5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 text-[14px] text-emerald-400">
                Invitation link sent to {emailInput}!
              </div>
            ) : (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (emailInput.trim()) setInvited(true);
                }}
                className="mt-5 space-y-4"
              >
                <div>
                  <label className="block text-[13px] font-medium text-ink-2">
                    Teammate Email
                  </label>
                  <input
                    type="email"
                    required
                    placeholder="sarah@company.com"
                    value={emailInput}
                    onChange={(e) => setEmailInput(e.target.value)}
                    className="mt-1.5 w-full rounded-lg border border-line bg-canvas px-3.5 py-2 text-[14px] text-ink placeholder:text-ink-3 outline-none focus:border-accent"
                  />
                </div>
                <div className="flex justify-end gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowInviteModal(false)}
                    className="rounded-lg border border-line px-4 py-2 text-[13px] font-medium text-ink-2 hover:bg-sunk"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="rounded-lg bg-accent px-4 py-2 text-[13px] font-medium text-white hover:opacity-95"
                  >
                    Send Invitation
                  </button>
                </div>
              </form>
            )}
            {invited && (
              <div className="mt-4 flex justify-end">
                <button
                  onClick={() => {
                    setShowInviteModal(false);
                    setInvited(false);
                    setEmailInput("");
                  }}
                  className="rounded-lg bg-accent px-4 py-1.5 text-[13px] font-medium text-white"
                >
                  Done
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </main>
  );
}
