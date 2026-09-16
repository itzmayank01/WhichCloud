"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useState } from "react";
import { Icon } from "@iconify/react";

export type NavItemKey =
  | "overview"
  | "reports"
  | "issues"
  | "resources"
  | "planning"
  | "recommendations"
  | "settings";

interface SidebarNavProps {
  activeKey?: NavItemKey;
  onSelectKey?: (key: NavItemKey) => void;
  connectedAccount?: {
    name: string;
    id: string;
    provider: string;
  };
  onSwitchAccount?: (provider: string) => void;
  /** Mobile only. The sidebar is a fixed 256px column beside `flex-1` content,
   *  which on a 390px phone left about 134px for the page itself -- enough to
   *  wrap "Active Resource Inventory" one word per line. Below `md` it becomes
   *  an overlay drawer instead, opened from the page header. */
  mobileOpen?: boolean;
  onCloseMobile?: () => void;
}

export function SidebarNav({
  activeKey = "overview",
  onSelectKey,
  connectedAccount = {
    name: "Management",
    id: "1243-9821-4412",
    provider: "aws",
  },
  onSwitchAccount,
  mobileOpen = false,
  onCloseMobile,
}: SidebarNavProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [searchQuery, setSearchQuery] = useState("");
  const [showWorkspaceMenu, setShowWorkspaceMenu] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [showHelpModal, setShowHelpModal] = useState(false);
  const [showNotificationsModal, setShowNotificationsModal] = useState(false);

  const navItems: { key: NavItemKey; label: string; icon: string; badge?: string }[] = [
    { key: "overview", label: "Overview", icon: "mdi:view-grid-outline" },
    { key: "reports", label: "Cost Reports", icon: "mdi:chart-box-outline" },
    { key: "issues", label: "Issues", icon: "mdi:alert-triangle-outline", badge: "4" },
    { key: "resources", label: "Active Resources", icon: "mdi:lightning-bolt-outline" },
    { key: "planning", label: "Financial Planning", icon: "mdi:calendar-month-outline" },
    { key: "recommendations", label: "Recommendations", icon: "mdi:bookmark-outline", badge: "6" },
    { key: "settings", label: "Settings", icon: "mdi:cog-outline" },
  ];

  const handleNavClick = (key: NavItemKey) => {
    if (onSelectKey) {
      onSelectKey(key);
    }
    // The drawer covers the page on mobile, so leaving it open after a
    // selection hides the thing the reader just asked to see.
    onCloseMobile?.();
  };

  return (
    <>
      {/* Backdrop for the mobile drawer. Tapping it closes, which is the
          gesture people try first and the only way out when the drawer covers
          the header the trigger lives in. */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/45 md:hidden"
          onClick={onCloseMobile}
          aria-hidden
        />
      )}

      <aside
        className={`flex-col border-r border-line bg-surface select-none shrink-0 overflow-y-auto ${
          mobileOpen
            ? "fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] shadow-2xl"
            : "hidden"
        } md:static md:z-auto md:flex md:w-auto md:max-w-none md:shadow-none md:transition-all md:duration-300 ${
          collapsed ? "md:w-16" : "md:w-64"
        }`}
      >
        {/* Top: Workspace / Management Dropdown matching Image 2 */}
        <div className="relative border-b border-line p-3">
          <button
            onClick={() => setShowWorkspaceMenu(!showWorkspaceMenu)}
            className="flex w-full items-center justify-between rounded-xl px-2.5 py-2 hover:bg-sunk transition-all text-left"
          >
            <div className="flex items-center gap-2.5 truncate">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-line bg-surface p-1.5 shadow-2xs">
                <Icon
                  icon={
                    connectedAccount.provider === "azure"
                      ? "logos:microsoft-azure"
                      : connectedAccount.provider === "gcp"
                      ? "logos:google-cloud"
                      : connectedAccount.provider === "github"
                      ? "logos:github-icon"
                      : "logos:aws"
                  }
                  className="h-5 w-5"
                />
              </div>
              {!collapsed && (
                <div className="truncate">
                  <div className="text-[13.5px] font-bold text-ink truncate">
                    {connectedAccount.name}
                  </div>
                  <div className="text-[11px] font-mono text-ink-3 truncate">
                    {connectedAccount.id}
                  </div>
                </div>
              )}
            </div>
            {!collapsed && (
              <Icon icon="mdi:chevron-down" className="h-4 w-4 text-ink-3 shrink-0" />
            )}
          </button>

          {/* Switcher Dropdown */}
          {showWorkspaceMenu && !collapsed && (
            <div className="absolute left-3 right-3 top-full z-50 mt-1 rounded-2xl border border-line bg-surface p-2 shadow-2xl">
              <div className="px-2.5 py-1.5 text-[11px] font-bold uppercase tracking-wider text-ink-3">
                Switch Cloud Account
              </div>
              <div className="space-y-0.5">
                {[
                  { p: "aws", name: "AWS Production (1243-9821-4412)", icon: "logos:aws" },
                  { p: "azure", name: "Azure Enterprise (sub-azure-01)", icon: "logos:microsoft-azure" },
                  { p: "gcp", name: "Google Cloud Platform (gcp-prod-981)", icon: "logos:google-cloud" },
                  { p: "github", name: "GitHub IaC Scanner (acme-corp/infra)", icon: "logos:github-icon" },
                ].map((acc) => (
                  <button
                    key={acc.p}
                    onClick={() => {
                      if (onSwitchAccount) onSwitchAccount(acc.p);
                      setShowWorkspaceMenu(false);
                    }}
                    className="flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-[12.5px] hover:bg-sunk text-ink transition-colors"
                  >
                    <div className="flex items-center gap-2 truncate">
                      <Icon icon={acc.icon} className="h-3.5 w-3.5 shrink-0" />
                      <span className="truncate">{acc.name}</span>
                    </div>
                    {connectedAccount.provider === acc.p && (
                      <span className="h-1.5 w-1.5 rounded-full bg-accent" />
                    )}
                  </button>
                ))}
              </div>
              <div className="border-t border-line mt-1.5 pt-1.5">
                <Link
                  href="/connect"
                  onClick={() => setShowWorkspaceMenu(false)}
                  className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-[12px] font-semibold text-accent hover:bg-sunk"
                >
                  <Icon icon="mdi:plus-circle-outline" className="h-3.5 w-3.5" />
                  <span>Connect Another Cloud...</span>
                </Link>
              </div>
            </div>
          )}
        </div>

        {/* Search Input matching Image 2 */}
        {!collapsed && (
          <div className="px-3 pt-3">
            <div className="relative flex items-center">
              <Icon icon="mdi:magnify" className="absolute left-3 h-4 w-4 text-ink-3" />
              <input
                type="text"
                placeholder="Search..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-xl border border-line bg-sunk/60 py-1.5 pl-9 pr-8 text-[12.5px] text-ink placeholder:text-ink-3 focus:border-accent focus:outline-none"
              />
              <span className="absolute right-2.5 text-[10px] font-mono text-ink-3">⌘K</span>
            </div>
          </div>
        )}

        {/* Main Navigation Links matching Image 2 */}
        <nav className="flex-1 space-y-1 px-3 py-4 overflow-y-auto">
          {navItems
            .filter((item) => !searchQuery || item.label.toLowerCase().includes(searchQuery.toLowerCase()))
            .map((item) => {
              const isActive = activeKey === item.key;
              return (
                <button
                  key={item.key}
                  onClick={() => handleNavClick(item.key)}
                  className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-[13.5px] font-medium transition-all ${
                    isActive
                      ? "bg-[#7c3aed]/10 text-[#7c3aed] font-semibold shadow-2xs"
                      : "text-ink-2 hover:bg-sunk hover:text-ink"
                  }`}
                  title={collapsed ? item.label : undefined}
                >
                  <div className="flex items-center gap-3 truncate">
                    <Icon
                      icon={item.icon}
                      className={`h-4 w-4 shrink-0 ${isActive ? "text-[#7c3aed]" : "text-ink-3"}`}
                    />
                    {!collapsed && <span className="truncate">{item.label}</span>}
                  </div>

                  {!collapsed && item.badge && (
                    <span
                      className={`rounded-full px-2 py-0.2 text-[10.5px] font-bold ${
                        item.key === "issues"
                          ? "bg-amber-500/15 text-amber-600 dark:text-amber-400"
                          : "bg-accent/15 text-accent"
                      }`}
                    >
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
        </nav>

        {/* Pinned Bottom Section matching Image 2 */}
        <div className="border-t border-line p-3 space-y-1">
          {!collapsed && (
            <div className="px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-ink-3">
              Pinned
            </div>
          )}

          <button
            onClick={() => setShowNotificationsModal(true)}
            className="flex w-full items-center justify-between rounded-xl px-3 py-2 text-[13px] font-medium text-ink-2 hover:bg-sunk hover:text-ink transition-colors"
            title={collapsed ? "Notifications" : undefined}
          >
            <div className="flex items-center gap-3">
              <Icon icon="mdi:bell-outline" className="h-4 w-4 text-ink-3" />
              {!collapsed && <span>Notifications</span>}
            </div>
            {!collapsed && (
              <span className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
            )}
          </button>

          <Link
            href="/prices"
            className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-[13px] font-medium text-ink-2 hover:bg-sunk hover:text-ink transition-colors"
            title={collapsed ? "Documentation" : undefined}
          >
            <Icon icon="mdi:book-open-page-variant-outline" className="h-4 w-4 text-ink-3" />
            {!collapsed && <span>Documentation</span>}
          </Link>

          <button
            onClick={() => setShowHelpModal(true)}
            className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-[13px] font-medium text-ink-2 hover:bg-sunk hover:text-ink transition-colors"
            title={collapsed ? "Help & Support" : undefined}
          >
            <Icon icon="mdi:headphones" className="h-4 w-4 text-ink-3" />
            {!collapsed && <span>Help & Support</span>}
          </button>

          {/* Collapse toggle button */}
          <div className="pt-2 flex justify-end">
            <button
              onClick={() => setCollapsed(!collapsed)}
              className="flex h-7 w-7 items-center justify-center rounded-lg border border-line bg-surface text-ink-3 hover:bg-sunk hover:text-ink"
              title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              <Icon
                icon={collapsed ? "mdi:chevron-right" : "mdi:chevron-left"}
                className="h-4 w-4"
              />
            </button>
          </div>
        </div>
      </aside>

      {/* Notifications Drawer */}
      {showNotificationsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
          <div className="relative w-full max-w-md rounded-2xl border border-line bg-surface p-6 shadow-2xl">
            <button
              onClick={() => setShowNotificationsModal(false)}
              className="absolute right-4 top-4 rounded-md p-1 text-ink-3 hover:text-ink"
            >
              <Icon icon="mdi:close" className="h-5 w-5" />
            </button>

            <div className="flex items-center gap-2.5 border-b border-line pb-4">
              <Icon icon="mdi:bell" className="h-5 w-5 text-accent" />
              <h3 className="text-[17px] font-bold text-ink">Notifications</h3>
            </div>

            <div className="mt-4 space-y-3">
              <div className="rounded-xl border border-amber-500/20 bg-amber-500/10 p-3.5 text-[12.5px] text-amber-500">
                <div className="font-bold flex items-center gap-1.5">
                  <Icon icon="mdi:alert-decagram" className="h-4 w-4" />
                  Cost Anomaly Detected
                </div>
                <p className="mt-1 text-ink-2">
                  NAT Gateway data transfer in us-east-1 spiked by +34% due to S3 API calls.
                </p>
              </div>

              <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-3.5 text-[12.5px] text-emerald-500">
                <div className="font-bold flex items-center gap-1.5">
                  <Icon icon="mdi:check-circle" className="h-4 w-4" />
                  Optimization Ready
                </div>
                <p className="mt-1 text-ink-2">
                  Graviton 3 migration diff generated for 4 worker services. Saves $410/mo.
                </p>
              </div>
            </div>

            <div className="mt-6 flex justify-end">
              <button
                onClick={() => setShowNotificationsModal(false)}
                className="rounded-lg bg-accent px-4 py-1.5 text-[13px] font-semibold text-white"
              >
                Mark as Read
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Help & Support Modal */}
      {showHelpModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
          <div className="relative w-full max-w-md rounded-2xl border border-line bg-surface p-6 shadow-2xl">
            <button
              onClick={() => setShowHelpModal(false)}
              className="absolute right-4 top-4 rounded-md p-1 text-ink-3 hover:text-ink"
            >
              <Icon icon="mdi:close" className="h-5 w-5" />
            </button>

            <div className="flex items-center gap-2.5 border-b border-line pb-4">
              <Icon icon="mdi:headphones" className="h-5 w-5 text-accent" />
              <h3 className="text-[17px] font-bold text-ink">WhichCloud Support</h3>
            </div>

            <p className="mt-3 text-[13px] text-ink-2">
              Have questions about your cloud bill or need help tuning your architecture pricing?
            </p>

            <div className="mt-4 space-y-2 text-[13px]">
              <div className="rounded-xl border border-line bg-sunk p-3 flex items-center justify-between">
                <span className="text-ink-2">Documentation & Guides</span>
                <Link href="/#provenance" className="text-accent font-semibold hover:underline">
                  Visit Docs →
                </Link>
              </div>
              <div className="rounded-xl border border-line bg-sunk p-3 flex items-center justify-between">
                <span className="text-ink-2">FinOps Engineering Team</span>
                <span className="font-mono text-ink">support@whichcloud.io</span>
              </div>
            </div>

            <div className="mt-6 flex justify-end">
              <button
                onClick={() => setShowHelpModal(false)}
                className="rounded-lg bg-accent px-4 py-1.5 text-[13px] font-semibold text-white"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
