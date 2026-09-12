"use client";

import { useState } from "react";
import { Icon } from "@iconify/react";
import { CURRENCIES, CurrencyCode } from "@/lib/currency";

interface FinOpsSettingsViewProps {
  provider: string;
  currency: CurrencyCode;
  onCurrencyChange: (c: CurrencyCode) => void;
  accountId?: string;
}

export function FinOpsSettingsView({
  provider = "aws",
  currency = "USD",
  onCurrencyChange,
  accountId = "1243-9821-4412",
}: FinOpsSettingsViewProps) {
  const [testingConnection, setTestingConnection] = useState(false);
  const [connectionSuccess, setConnectionSuccess] = useState(false);
  const [anomalyThreshold, setAnomalyThreshold] = useState("15");
  const [slackWebhook, setSlackWebhook] = useState("https://hooks.slack.com/services/T00/B00/XXXX");
  const [emailAlerts, setEmailAlerts] = useState(true);
  const [savedNotice, setSavedNotice] = useState(false);

  const handleTest = () => {
    setTestingConnection(true);
    setConnectionSuccess(false);
    setTimeout(() => {
      setTestingConnection(false);
      setConnectionSuccess(true);
      setTimeout(() => setConnectionSuccess(false), 4000);
    }, 1200);
  };

  const handleSave = () => {
    setSavedNotice(true);
    setTimeout(() => setSavedNotice(false), 3000);
  };

  return (
    <div className="mt-6 max-w-4xl space-y-8">
      {savedNotice && (
        <div className="flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-[13px] font-medium text-emerald-500 animate-fadeIn">
          <Icon icon="mdi:check-circle" className="h-4 w-4 shrink-0" />
          <span>Settings saved successfully.</span>
        </div>
      )}

      {/* SECTION 1: Display Currency Selection */}
      <div className="rounded-2xl border border-line bg-surface p-6 shadow-xs">
        <div className="border-b border-line pb-4">
          <h3 className="text-[17px] font-bold text-ink flex items-center gap-2">
            <Icon icon="mdi:currency-usd" className="h-5 w-5 text-accent" />
            Display Currency & Regional Format
          </h3>
          <p className="mt-0.5 text-[13px] text-ink-3">
            Choose your preferred currency for cost charts, topology estimates, and recommendations.
          </p>
        </div>

        <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {(Object.keys(CURRENCIES) as CurrencyCode[]).map((cCode) => {
            const c = CURRENCIES[cCode];
            const isSelected = currency === cCode;

            return (
              <button
                key={cCode}
                onClick={() => onCurrencyChange(cCode)}
                className={`flex items-center justify-between rounded-xl border p-4 text-left transition-all ${
                  isSelected
                    ? "border-accent bg-accent/5 ring-1 ring-accent shadow-xs"
                    : "border-line bg-surface hover:border-ink-3/40 hover:bg-sunk"
                }`}
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-sunk font-mono text-[14px] font-bold text-ink">
                      {c.symbol}
                    </span>
                    <span className="font-bold text-[14px] text-ink">{c.code}</span>
                  </div>
                  <div className="mt-1 text-[11.5px] text-ink-3">
                    {c.rate === 1.0 ? "Base Currency (1.0x)" : `Rate: 1 USD = ${c.rate} ${c.code}`}
                  </div>
                </div>

                {isSelected && (
                  <Icon icon="mdi:check-circle" className="h-5 w-5 text-accent shrink-0" />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* SECTION 2: Connected Cloud Credentials & Telemetry Link */}
      <div className="rounded-2xl border border-line bg-surface p-6 shadow-xs">
        <div className="flex items-center justify-between border-b border-line pb-4">
          <div>
            <h3 className="text-[17px] font-bold text-ink flex items-center gap-2">
              <Icon icon="mdi:cloud-check-outline" className="h-5 w-5 text-emerald-500" />
              Connected Cloud Telemetry ({provider.toUpperCase()})
            </h3>
            <p className="mt-0.5 text-[13px] text-ink-3">
              IAM cross-account role and read-only telemetry bridge status.
            </p>
          </div>

          <button
            onClick={handleTest}
            disabled={testingConnection}
            className="inline-flex items-center gap-1.5 rounded-xl border border-line bg-surface px-3.5 py-1.5 text-[12.5px] font-medium text-ink hover:bg-sunk transition-colors"
          >
            {testingConnection ? (
              <>
                <Icon icon="line-md:loading-loop" className="h-4 w-4 animate-spin text-accent" />
                <span>Validating...</span>
              </>
            ) : (
              <>
                <Icon icon="mdi:sync" className="h-4 w-4 text-ink-3" />
                <span>Test Telemetry Sync</span>
              </>
            )}
          </button>
        </div>

        {connectionSuccess && (
          <div className="mt-4 flex items-center gap-2 rounded-xl bg-emerald-500/10 p-3 text-[12.5px] text-emerald-500 font-medium">
            <Icon icon="mdi:check-circle" className="h-4 w-4 shrink-0" />
            <span>Telemetry bridge verified! All CloudWatch and billing metrics responding normally.</span>
          </div>
        )}

        <div className="mt-5 space-y-4 text-[13px]">
          <div>
            <label className="text-ink-2 font-medium">Account Identifier</label>
            <div className="mt-1 font-mono text-[13px] text-ink bg-sunk rounded-xl border border-line p-2.5">
              {accountId}
            </div>
          </div>

          <div>
            <label className="text-ink-2 font-medium">Assumed Cross-Account Role ARN</label>
            <div className="mt-1 font-mono text-[13px] text-ink bg-sunk rounded-xl border border-line p-2.5">
              arn:aws:iam::{accountId}:role/WhichCloudFinOpsReadOnlyBridge
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="text-ink-2 font-medium">Data Refresh Cadence</label>
              <select className="mt-1 w-full rounded-xl border border-line bg-sunk p-2 text-[13px] text-ink focus:border-accent focus:outline-none">
                <option>Every 15 minutes (Real-time telemetry)</option>
                <option>Hourly snapshot</option>
                <option>Daily at 00:00 UTC</option>
              </select>
            </div>

            <div>
              <label className="text-ink-2 font-medium">Default Telemetry Region</label>
              <select className="mt-1 w-full rounded-xl border border-line bg-sunk p-2 text-[13px] text-ink focus:border-accent focus:outline-none">
                <option>us-east-1 (N. Virginia)</option>
                <option>us-west-2 (Oregon)</option>
                <option>eu-west-1 (Ireland)</option>
                <option>ap-south-1 (Mumbai)</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* SECTION 3: Cost Anomaly Alerts & Webhooks */}
      <div className="rounded-2xl border border-line bg-surface p-6 shadow-xs">
        <div className="border-b border-line pb-4">
          <h3 className="text-[17px] font-bold text-ink flex items-center gap-2">
            <Icon icon="mdi:bell-ring-outline" className="h-5 w-5 text-amber-500" />
            Alerting & Webhook Notifications
          </h3>
          <p className="mt-0.5 text-[13px] text-ink-3">
            Receive automated alerts whenever sudden spend anomalies or unused instances are detected.
          </p>
        </div>

        <div className="mt-5 space-y-4 text-[13px]">
          <div>
            <label className="text-ink-2 font-medium">Cost Spike Alert Threshold (%)</label>
            <div className="flex items-center gap-3 mt-1">
              <input
                type="number"
                value={anomalyThreshold}
                onChange={(e) => setAnomalyThreshold(e.target.value)}
                className="w-32 rounded-xl border border-line bg-sunk p-2 font-mono text-[13px] text-ink focus:border-accent focus:outline-none"
              />
              <span className="text-ink-3">
                % jump above trailing 7-day baseline
              </span>
            </div>
          </div>

          <div>
            <label className="text-ink-2 font-medium">Slack / Discord Webhook URL</label>
            <input
              type="text"
              value={slackWebhook}
              onChange={(e) => setSlackWebhook(e.target.value)}
              className="mt-1 w-full rounded-xl border border-line bg-sunk p-2 font-mono text-[12.5px] text-ink focus:border-accent focus:outline-none"
            />
          </div>

          <div className="flex items-center justify-between pt-2">
            <div>
              <div className="font-semibold text-ink">Daily Digest Email</div>
              <div className="text-[12px] text-ink-3">Send 9:00 AM summary of spend and new waste issues.</div>
            </div>
            <button
              onClick={() => setEmailAlerts(!emailAlerts)}
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                emailAlerts ? "bg-accent" : "bg-sunk"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                  emailAlerts ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>
        </div>

        <div className="mt-6 flex justify-end border-t border-line pt-4">
          <button
            onClick={handleSave}
            className="rounded-xl bg-accent px-5 py-2 text-[13px] font-semibold text-white hover:opacity-90 shadow-2xs"
          >
            Save Preferences
          </button>
        </div>
      </div>
    </div>
  );
}
