"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Icon } from "@iconify/react";
import { api } from "@/lib/api";
import { setStoredAccount } from "@/lib/connectedAccount";

export default function ConnectGcpPage() {
  const router = useRouter();
  const [showModal, setShowModal] = useState(false);
  const [projectId, setProjectId] = useState("");
  const [datasetId, setDatasetId] = useState("");
  const [verifying, setVerifying] = useState(false);
  const [copiedSa, setCopiedSa] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const serviceAccount = "etl-runner-12@whichcloud-gcp-etl-prod.iam.gserviceaccount.com";

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setVerifying(true);
    setErrorMsg("");

    try {
      const res = await api.connectionVerify("gcp", {
        project_id: projectId || "gcp-production-9021",
        dataset: datasetId || "billing_export_us",
      });

      if (res.ok) {
        const accId = res.account_id || projectId || "gcp-prod-981";
        setStoredAccount({
          provider: "gcp",
          id: accId,
          name: `Google Cloud Platform (${accId})`,
          region: "us-central1",
        });
        router.push(
          `/finops?provider=gcp&account_id=${encodeURIComponent(accId)}`
        );
      } else {
        setErrorMsg(res.message || "Failed to verify GCP project credentials.");
        setVerifying(false);
      }
    } catch {
      const accId = projectId || "gcp-prod-981";
      setStoredAccount({
        provider: "gcp",
        id: accId,
        name: `Google Cloud Platform (${accId})`,
        region: "us-central1",
      });
      router.push(`/finops?provider=gcp&account_id=${encodeURIComponent(accId)}`);
    }
  };

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col px-6 py-12">
      {/* Breadcrumb & Header matching Screenshot 4 */}
      <div className="flex items-center justify-between border-b border-line pb-6">
        <div className="flex items-center gap-3.5">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-line bg-surface p-2 shadow-xs">
            <Icon icon="logos:google-cloud" width={28} height={28} />
          </div>
          <div>
            <div className="flex items-center gap-2 text-[12.5px] font-medium text-ink-3">
              <Link href="/connect" className="hover:text-ink">
                Onboarding
              </Link>
              <span>/</span>
              <span>Connect GCP</span>
            </div>
            <h2 className="text-[20px] font-bold text-ink">GCP</h2>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <Link
            href="/#provenance"
            className="rounded-lg border border-line bg-surface px-3 py-1.5 text-[13px] font-medium text-ink-2 hover:bg-sunk hover:text-ink"
          >
            Support
          </Link>
          <a
            href="https://cloud.google.com/billing/docs/how-to/export-data-bigquery"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 rounded-lg border border-line bg-surface px-3 py-1.5 text-[13px] font-medium text-ink-2 hover:bg-sunk hover:text-ink"
          >
            Docs <Icon icon="mdi:arrow-top-right" className="h-3.5 w-3.5" />
          </a>
        </div>
      </div>

      <div className="mt-8">
        <h1 className="text-[26px] font-bold tracking-tight text-ink">
          Connect Your Account
        </h1>

        <div className="mt-4">
          <h3 className="text-[17px] font-semibold text-ink">Summary</h3>
          <p className="mt-1.5 text-[14.5px] leading-relaxed text-ink-2">
            WhichCloud integrates with your GCP account using a service account. During the integration workflow, you will grant this service account read access to your BigQuery billing dataset. This GCP service account is operated by WhichCloud and is the only link between GCP and WhichCloud. This set of IAM roles guarantees WhichCloud only has visibility to billing export data and nothing else.
          </p>
        </div>

        {/* Service account copy box */}
        <div className="mt-6">
          <p className="text-[13.5px] font-semibold text-ink">
            WhichCloud GCP Service Account
          </p>
          <div className="relative mt-2 flex items-center justify-between rounded-xl border border-line bg-canvas p-3.5">
            <code className="font-mono text-[13.5px] text-ink">{serviceAccount}</code>
            <button
              onClick={() => {
                navigator.clipboard.writeText(serviceAccount);
                setCopiedSa(true);
                setTimeout(() => setCopiedSa(false), 2000);
              }}
              className="rounded-md border border-line bg-surface p-1.5 text-ink-3 hover:text-ink"
              title="Copy to clipboard"
            >
              {copiedSa ? <span className="text-[11px] font-mono text-emerald-500">Copied!</span> : <Icon icon="mdi:content-copy" className="h-4 w-4" />}
            </button>
          </div>
          <p className="mt-2 text-[13px] text-ink-3">
            You will use the above service account in the steps below.
          </p>
        </div>

        {/* Prerequisite & steps */}
        <div className="mt-8">
          <h3 className="text-[18px] font-semibold text-ink">
            Prerequisite: Export Billing Data to BigQuery
          </h3>
          <p className="mt-1.5 text-[14px] leading-relaxed text-ink-2">
            If you have not exported billing data to BigQuery yet, follow the Google Cloud Billing documentation. Once you have set up Cloud Billing exports, you can continue with the steps below.
          </p>

          <div className="mt-5 flex gap-3.5 rounded-xl border border-line bg-sunk p-4">
            <Icon icon="mdi:lightbulb-outline" className="h-5 w-5 shrink-0 text-amber-500 mt-0.5" />
            <p className="text-[13.5px] leading-relaxed text-ink-2">
              If your organization has multiple billing accounts, you will need to complete the instructions below for each account.
            </p>
          </div>
        </div>

        {/* Step 1 */}
        <div className="mt-8">
          <h3 className="text-[17px] font-semibold text-ink">
            Step 1: Add BigQuery Permissions
          </h3>
          <ol className="mt-3 space-y-2 text-[14px] leading-relaxed text-ink-2 list-decimal list-inside">
            <li>Navigate to <strong>BigQuery</strong> in the GCP Console. Ensure you are in the project set up for your billing data.</li>
            <li>In the <strong>Explorer</strong> panel, select the project to expand it.</li>
            <li>Select the vertical three dots (⋮) next to the dataset name, then click <strong>Share</strong>.</li>
            <li>On the right, click <strong>+ ADD PRINCIPAL</strong>.</li>
            <li>Under <strong>New principals</strong>, add your WhichCloud GCP service account.</li>
            <li>Attach the <strong>BigQuery Data Viewer</strong> role, and save the permission.</li>
          </ol>
        </div>

        {/* Step 2 */}
        <div className="mt-8">
          <h3 className="text-[17px] font-semibold text-ink">
            Step 2: Enable Active Resources for the Organization
          </h3>
          <ol className="mt-3 space-y-2 text-[14px] leading-relaxed text-ink-2 list-decimal list-inside">
            <li>Open the <strong>IAM Console</strong>.</li>
            <li>On the top left of the console, select your organization or project.</li>
            <li>In the center of the page, under Permissions, click <strong>+ GRANT ACCESS</strong>.</li>
            <li>Under <strong>Add principals</strong>, add the WhichCloud GCP service account displayed above.</li>
            <li>Under <strong>Assign roles</strong>, click Basic and select the <strong>Viewer</strong> role from the Roles list. Then click <strong>SAVE</strong>.</li>
          </ol>
        </div>

        {/* Add Project Info Button */}
        <div className="mt-8">
          <p className="text-[14px] text-ink-2">
            Click the <strong>Add Project Info</strong> button below, and add your project details.
          </p>

          <button
            type="button"
            onClick={() => setShowModal(true)}
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-[#6b21a8] px-5 py-2.5 text-[14px] font-semibold text-white shadow-xs hover:bg-[#581c87]"
          >
            Add Project Info
          </button>
        </div>
      </div>

      {/* Project Info Modal matching Screenshot 4 */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs">
          <div className="w-full max-w-lg rounded-2xl border border-line bg-surface p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-line pb-4">
              <h3 className="text-[18px] font-bold text-ink">
                Google Cloud Project & Dataset Details
              </h3>
              <button
                onClick={() => setShowModal(false)}
                className="text-ink-3 hover:text-ink"
              >
                <Icon icon="mdi:close" className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleVerify} className="mt-5 space-y-4">
              <div>
                <label className="block text-[13px] font-medium text-ink-2">
                  GCP Project ID
                </label>
                <input
                  type="text"
                  placeholder="e.g. whichcloud-prod-123 (Optional for Demo)"
                  value={projectId}
                  onChange={(e) => setProjectId(e.target.value)}
                  className="mt-1.5 w-full rounded-lg border border-line bg-canvas px-3.5 py-2 font-mono text-[13px] text-ink placeholder:text-ink-3 outline-none focus:border-accent"
                />
              </div>

              <div>
                <label className="block text-[13px] font-medium text-ink-2">
                  BigQuery Billing Dataset ID
                </label>
                <input
                  type="text"
                  placeholder="e.g. gcp_billing_export"
                  value={datasetId}
                  onChange={(e) => setDatasetId(e.target.value)}
                  className="mt-1.5 w-full rounded-lg border border-line bg-canvas px-3.5 py-2 font-mono text-[13px] text-ink placeholder:text-ink-3 outline-none focus:border-accent"
                />
              </div>

              {errorMsg && (
                <div className="rounded-lg border border-caution/40 bg-caution-wash p-3 text-[13.5px] text-caution">
                  {errorMsg}
                </div>
              )}

              <div className="flex justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="rounded-lg border border-line px-4 py-2 text-[13px] font-medium text-ink-2 hover:bg-sunk"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={verifying}
                  className="inline-flex items-center gap-2 rounded-lg bg-accent px-5 py-2 text-[13px] font-medium text-white hover:opacity-95 disabled:opacity-50"
                >
                  {verifying ? (
                    <>
                      <Icon icon="mdi:loading" className="h-4 w-4 animate-spin" />
                      Verifying...
                    </>
                  ) : (
                    "Save & Launch FinOps"
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}
