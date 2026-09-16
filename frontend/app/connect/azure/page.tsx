"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { Icon } from "@iconify/react";
import { api } from "@/lib/api";
import { setStoredAccount } from "@/lib/connectedAccount";

export default function ConnectAzurePage() {
  const router = useRouter();
  const { getToken } = useAuth();
  const [showModal, setShowModal] = useState(false);
  const [tenantId, setTenantId] = useState("");
  const [appId, setAppId] = useState("");
  const [password, setPassword] = useState("");
  const [subscriptionId, setSubscriptionId] = useState("");
  const [verifying, setVerifying] = useState(false);
  const [copiedCmd1, setCopiedCmd1] = useState(false);
  const [copiedCmd2, setCopiedCmd2] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const cmd1 = 'az ad sp create-for-rbac -n "whichcloud"';
  const cmd2 = `az role assignment create --assignee <SERVICE_PRINCIPAL_APP_ID> \\\n  --role Reader \\\n  --scope "/subscriptions/<SUBSCRIPTION_ID>"`;

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setVerifying(true);
    setErrorMsg("");

    /* Every field is the user's own. These used to fall back to a fixed
       tenant id, app id, client secret and subscription id, so submitting the
       form blank sent somebody else's directory identifiers to the verifier
       and, on success, stored that subscription as this user's connection. */
    if (!tenantId.trim() || !appId.trim() || !password.trim() || !subscriptionId.trim()) {
      setErrorMsg("Enter your own tenant ID, app ID, client secret and subscription ID.");
      setVerifying(false);
      return;
    }

    try {
      const token = await getToken();
      const res = await api.connectionVerify("azure", {
        tenant_id: tenantId,
        app_id: appId,
        client_secret: password,
        subscription_id: subscriptionId,
      }, token ?? undefined);

      if (res.ok) {
        const accId = res.account_id || subscriptionId;
        setStoredAccount({
          provider: "azure",
          id: accId,
          name: `Azure subscription (${accId})`,
          region: "eastus",
        });
        router.push(
          `/finops?provider=azure&account_id=${encodeURIComponent(accId)}`
        );
      } else {
        setErrorMsg(res.message || "Failed to verify Azure credentials.");
        setVerifying(false);
      }
    } catch (err) {
      // A failed verification must not read as a successful one.
      setErrorMsg(
        err instanceof Error
          ? `Could not reach the verification service: ${err.message}`
          : "Could not reach the verification service. Please try again.",
      );
      setVerifying(false);
    }
  };

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col px-6 py-12">
      {/* Breadcrumb & Header matching Screenshot 3 */}
      <div className="flex items-center justify-between border-b border-line pb-6">
        <div className="flex items-center gap-3.5">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-line bg-surface p-2 shadow-xs">
            <Icon icon="logos:microsoft-azure" width={28} height={28} />
          </div>
          <div>
            <div className="flex items-center gap-2 text-[12.5px] font-medium text-ink-3">
              <Link href="/connect" className="hover:text-ink">
                Onboarding
              </Link>
              <span>/</span>
              <span>Connect Azure</span>
            </div>
            <h2 className="text-[20px] font-bold text-ink">Azure</h2>
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
            href="https://learn.microsoft.com/en-us/azure/cost-management-billing/"
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
            WhichCloud integrates with your Azure account by granting read access to a service principal. A service principal is created specifically for WhichCloud and assigned <code className="rounded bg-sunk px-1.5 py-0.5 font-mono text-[13px] text-ink">Reader</code> permissions to your subscriptions.
          </p>
        </div>

        {/* Note Callout */}
        <div className="mt-5 flex gap-3.5 rounded-xl border border-line bg-sunk p-4.5">
          <Icon icon="mdi:lightbulb-outline" className="h-5 w-5 shrink-0 text-amber-500 mt-0.5" />
          <p className="text-[13.5px] leading-relaxed text-ink-2">
            Microsoft offers different billing account types based on your organization&apos;s setup, which affects the way you&apos;ll connect your Azure account with WhichCloud. See our documentation for Microsoft Customer Agreement (MCA) or Enterprise Agreement (EA) details.
          </p>
        </div>

        <p className="mt-6 text-[14px] text-ink-3">
          The below instructions are completed using the Azure CLI. For instructions on how to set up the integration using the Azure portal, see the documentation.
        </p>

        {/* Step 1: Grant Access */}
        <div className="mt-7">
          <h3 className="text-[18px] font-semibold text-ink">Grant Access</h3>
          <p className="mt-1 text-[14px] text-ink-2">
            Start by creating the WhichCloud service principal:
          </p>

          <div className="relative mt-3 rounded-xl border border-line bg-canvas p-4">
            <button
              onClick={() => {
                navigator.clipboard.writeText(cmd1);
                setCopiedCmd1(true);
                setTimeout(() => setCopiedCmd1(false), 2000);
              }}
              className="absolute right-3 top-3 rounded-md border border-line bg-surface p-1.5 text-ink-3 hover:text-ink"
              title="Copy to clipboard"
            >
              {copiedCmd1 ? <span className="text-[11px] font-mono text-emerald-500">Copied!</span> : <Icon icon="mdi:content-copy" className="h-4 w-4" />}
            </button>
            <code className="block font-mono text-[13.5px] text-ink">{cmd1}</code>
          </div>

          <p className="mt-4 text-[13.5px] text-ink-2">
            The output of that command will give you the <code className="font-mono text-[12px] bg-sunk px-1 py-0.5 rounded">appId</code>, <code className="font-mono text-[12px] bg-sunk px-1 py-0.5 rounded">password</code>, and <code className="font-mono text-[12px] bg-sunk px-1 py-0.5 rounded">tenant</code>, which are required in the final step. See the example below:
          </p>

          <div className="mt-2.5 rounded-xl border border-line bg-sunk p-4 font-mono text-[12.5px] leading-relaxed text-ink-2">
            <pre>{`{
  "appId": "2d2233f5-7ad5-4a12-abc7-bad2889d6407",
  "displayName": "whichcloud",
  "password": "*8zkj~yswKd433fsdf2SHrvp22UoA6t000kZ_BYar2",
  "tenant": "1050a480-ef60-43d7-b8db-2123dcd100b60"
}`}</pre>
          </div>
        </div>

        {/* Step 2: Assign Permissions */}
        <div className="mt-8">
          <h3 className="text-[18px] font-semibold text-ink">Assign Permissions</h3>
          <p className="mt-1 text-[14px] text-ink-2">
            Next, assign <code className="rounded bg-sunk px-1.5 py-0.5 font-mono text-[12px] text-ink">Reader</code> permissions to the subscription:
          </p>

          <div className="relative mt-3 rounded-xl border border-line bg-canvas p-4">
            <button
              onClick={() => {
                navigator.clipboard.writeText(cmd2);
                setCopiedCmd2(true);
                setTimeout(() => setCopiedCmd2(false), 2000);
              }}
              className="absolute right-3 top-3 rounded-md border border-line bg-surface p-1.5 text-ink-3 hover:text-ink"
              title="Copy to clipboard"
            >
              {copiedCmd2 ? <span className="text-[11px] font-mono text-emerald-500">Copied!</span> : <Icon icon="mdi:content-copy" className="h-4 w-4" />}
            </button>
            <pre className="overflow-x-auto font-mono text-[13px] text-ink">{cmd2}</pre>
          </div>
        </div>

        {/* Add Credentials Button / Section */}
        <div className="mt-8">
          <p className="text-[14px] text-ink-2">
            Click the <strong>Add Credentials</strong> button below, and add the tenant ID, service principal app ID, and password previously generated.
          </p>

          <button
            type="button"
            onClick={() => setShowModal(true)}
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-[#6b21a8] px-5 py-2.5 text-[14px] font-semibold text-white shadow-xs hover:bg-[#581c87]"
          >
            Add Credentials
          </button>
        </div>
      </div>

      {/* Credentials Modal matching Screenshot 3 */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs">
          <div className="w-full max-w-lg rounded-2xl border border-line bg-surface p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-line pb-4">
              <h3 className="text-[18px] font-bold text-ink">
                Azure Service Principal Credentials
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
                  Tenant ID (Directory ID)
                </label>
                <input
                  type="text"
                  placeholder="1050a480-ef60-43d7-b8db-2123dcd100b60"
                  value={tenantId}
                  onChange={(e) => setTenantId(e.target.value)}
                  className="mt-1.5 w-full rounded-lg border border-line bg-canvas px-3.5 py-2 font-mono text-[13px] text-ink placeholder:text-ink-3 outline-none focus:border-accent"
                />
              </div>

              <div>
                <label className="block text-[13px] font-medium text-ink-2">
                  Application (Client) ID
                </label>
                <input
                  type="text"
                  placeholder="2d2233f5-7ad5-4a12-abc7-bad2889d6407"
                  value={appId}
                  onChange={(e) => setAppId(e.target.value)}
                  className="mt-1.5 w-full rounded-lg border border-line bg-canvas px-3.5 py-2 font-mono text-[13px] text-ink placeholder:text-ink-3 outline-none focus:border-accent"
                />
              </div>

              <div>
                <label className="block text-[13px] font-medium text-ink-2">
                  Client Secret (Password)
                </label>
                <input
                  type="password"
                  placeholder="Client secret value"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="mt-1.5 w-full rounded-lg border border-line bg-canvas px-3.5 py-2 font-mono text-[13px] text-ink placeholder:text-ink-3 outline-none focus:border-accent"
                />
              </div>

              <div>
                <label className="block text-[13px] font-medium text-ink-2">
                  Subscription ID
                </label>
                <input
                  type="text"
                  placeholder="sub-azure-prod-01 (Optional for Demo)"
                  value={subscriptionId}
                  onChange={(e) => setSubscriptionId(e.target.value)}
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
