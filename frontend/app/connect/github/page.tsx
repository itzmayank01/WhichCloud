"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { Icon } from "@iconify/react";
import { api } from "@/lib/api";
import { setStoredAccount } from "@/lib/connectedAccount";

export default function ConnectGitHubPage() {
  const router = useRouter();
  const { getToken } = useAuth();
  const [showModal, setShowModal] = useState(false);
  // Starts empty: a pre-filled repository reads as one already chosen, and
  // submitting without editing it connected that repo rather than the user's.
  const [repoUrl, setRepoUrl] = useState("");
  const [branch, setBranch] = useState("main");
  const [token, setToken] = useState("");
  const [iacPath, setIacPath] = useState("terraform/");
  const [verifying, setVerifying] = useState(false);
  const [connectedOrgs, setConnectedOrgs] = useState<string[]>([]);
  const [errorMsg, setErrorMsg] = useState("");

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    setVerifying(true);
    setErrorMsg("");

    /* The repo and the token are the user's own. `github_token` used to fall
       back to a literal that looked like a PAT, so a blank submit sent a
       fabricated credential to the verifier and, if it came back ok, stored a
       repository the user had never named as their connection. */
    if (!repoUrl.trim() || !token.trim()) {
      setErrorMsg("Enter the repository to scan and a GitHub token that can read it.");
      setVerifying(false);
      return;
    }

    try {
      const clerkToken = await getToken();
      const res = await api.connectionVerify("github", {
        repo_url: repoUrl,
        branch: branch,
        github_token: token,
        iac_path: iacPath,
      }, clerkToken ?? undefined);

      if (res.ok) {
        setConnectedOrgs((prev) => [...prev, repoUrl]);
        const accId = res.account_id || repoUrl;
        setStoredAccount({
          provider: "github",
          id: accId,
          name: `GitHub repository (${accId})`,
          region: "us-east-1",
        });
        setTimeout(() => {
          router.push(
            `/finops?provider=github&account_id=${encodeURIComponent(accId)}`
          );
        }, 600);
      } else {
        setErrorMsg(res.message || "Failed to scan GitHub repository.");
        setVerifying(false);
      }
    } catch (err) {
      // A failed scan must not read as a successful one.
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
      {/* Breadcrumb & Header matching Screenshot 5 */}
      <div className="flex items-center justify-between border-b border-line pb-6">
        <div className="flex items-center gap-3.5">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-line bg-surface p-2 shadow-xs">
            <Icon icon="mdi:github" width={28} height={28} className="text-ink" />
          </div>
          <div>
            <div className="flex items-center gap-2 text-[12.5px] font-medium text-ink-3">
              <Link href="/connect" className="hover:text-ink">
                Onboarding
              </Link>
              <span>/</span>
              <span>Connect GitHub</span>
            </div>
            <h2 className="text-[20px] font-bold text-ink">GitHub</h2>
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
            href="https://docs.github.com/en/apps"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 rounded-lg border border-line bg-surface px-3 py-1.5 text-[13px] font-medium text-ink-2 hover:bg-sunk hover:text-ink"
          >
            Docs <Icon icon="mdi:arrow-top-right" className="h-3.5 w-3.5" />
          </a>
        </div>
      </div>

      {/* Main Card matching Screenshot 5 */}
      <div className="mt-20 flex flex-col items-center justify-center text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-surface border border-line shadow-xs">
          <Icon icon="mdi:github" className="h-10 w-10 text-ink" />
        </div>

        <h3 className="mt-5 text-[20px] font-bold text-ink">
          GitHub Organizations
        </h3>

        <p className="mt-2 text-[14.5px] text-ink-2">
          You haven&apos;t connected any GitHub Organizations yet.
        </p>

        <p className="mt-1 text-[13px] text-ink-3">
          If you have multiple GitHub Organizations, you can repeat this process for each one you want to connect.
        </p>

        <div className="mt-8 flex flex-col sm:flex-row items-center gap-3">
          <button
            onClick={() => setShowModal(true)}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#7c3aed] px-6 py-3 text-[14.5px] font-semibold text-white shadow-sm hover:bg-[#6d28d9] transition-all"
          >
            <Icon icon="mdi:github" className="h-4 w-4" />
            Connect GitHub Account
          </button>
          {/* "Quick Demo Repo" removed. It stored a fixed repository as a
              real connection without contacting GitHub or verifying anything,
              so the app then presented that repo as the signed-in user's and
              FinOps went on to request data for it. A demo that writes real
              connection state is indistinguishable from connecting. */}
        </div>

        {/* Feature badges */}
        <div className="mt-14 grid w-full max-w-2xl grid-cols-1 gap-4 sm:grid-cols-3 text-left">
          <div className="rounded-xl border border-line bg-surface p-4 shadow-xs">
            <div className="flex items-center gap-2 text-[13.5px] font-semibold text-ink">
              <Icon icon="logos:terraform-icon" className="h-4 w-4" />
              Terraform & OpenTofu
            </div>
            <p className="mt-1.5 text-[12px] text-ink-2">
              Automatic AST parsing of .tf files to predict deployment spend per commit.
            </p>
          </div>
          <div className="rounded-xl border border-line bg-surface p-4 shadow-xs">
            <div className="flex items-center gap-2 text-[13.5px] font-semibold text-ink">
              <Icon icon="logos:github-actions" className="h-4 w-4" />
              PR Cost Comments
            </div>
            <p className="mt-1.5 text-[12px] text-ink-2">
              Bot posts dollar diffs directly on pull requests before infrastructure merges.
            </p>
          </div>
          <div className="rounded-xl border border-line bg-surface p-4 shadow-xs">
            <div className="flex items-center gap-2 text-[13.5px] font-semibold text-ink">
              <Icon icon="mdi:shield-check-outline" className="h-4 w-4 text-emerald-500" />
              Read-Only Token
            </div>
            <p className="mt-1.5 text-[12px] text-ink-2">
              Only requires metadata and repository contents read access. Zero write permissions.
            </p>
          </div>
        </div>
      </div>

      {/* GitHub Setup Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
          <div className="relative w-full max-w-md rounded-2xl border border-line bg-surface p-6 shadow-xl">
            <button
              onClick={() => setShowModal(false)}
              className="absolute right-4 top-4 rounded-md p-1 text-ink-3 hover:text-ink"
            >
              <Icon icon="mdi:close" className="h-5 w-5" />
            </button>

            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-line bg-sunk">
                <Icon icon="mdi:github" className="h-6 w-6 text-ink" />
              </div>
              <div>
                <h3 className="text-[17px] font-semibold text-ink">
                  Connect GitHub Repository
                </h3>
                <p className="text-[12.5px] text-ink-3">
                  Read-only access for IaC scanning
                </p>
              </div>
            </div>

            {errorMsg && (
              <div className="mt-4 rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-[13px] text-red-500">
                {errorMsg}
              </div>
            )}

            <form onSubmit={handleConnect} className="mt-5 space-y-4">
              <div>
                <label className="block text-[13px] font-medium text-ink">
                  Repository URL or Name
                </label>
                <input
                  type="text"
                  required
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  placeholder="github.com/organization/repo"
                  className="mt-1 w-full rounded-lg border border-line bg-sunk px-3 py-2 text-[13.5px] text-ink focus:border-accent focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[13px] font-medium text-ink">
                    Branch
                  </label>
                  <input
                    type="text"
                    required
                    value={branch}
                    onChange={(e) => setBranch(e.target.value)}
                    placeholder="main"
                    className="mt-1 w-full rounded-lg border border-line bg-sunk px-3 py-2 text-[13.5px] text-ink focus:border-accent focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[13px] font-medium text-ink">
                    IaC Directory
                  </label>
                  <input
                    type="text"
                    required
                    value={iacPath}
                    onChange={(e) => setIacPath(e.target.value)}
                    placeholder="terraform/"
                    className="mt-1 w-full rounded-lg border border-line bg-sunk px-3 py-2 text-[13.5px] text-ink focus:border-accent focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[13px] font-medium text-ink">
                  Personal Access Token (or leave blank for Demo)
                </label>
                <input
                  type="password"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  placeholder="ghp_xxxxxxxxxxxx"
                  className="mt-1 w-full rounded-lg border border-line bg-sunk px-3 py-2 font-mono text-[13px] text-ink focus:border-accent focus:outline-none"
                />
                <p className="mt-1 text-[11.5px] text-ink-3">
                  Needs only <code className="rounded bg-sunk px-1 py-0.5">repo:read</code> scope.
                </p>
              </div>

              <div className="mt-6 flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="rounded-lg border border-line px-4 py-2 text-[13.5px] font-medium text-ink-2 hover:bg-sunk hover:text-ink"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={verifying}
                  className="inline-flex items-center gap-2 rounded-lg bg-[#7c3aed] px-4 py-2 text-[13.5px] font-semibold text-white hover:bg-[#6d28d9] disabled:opacity-50"
                >
                  {verifying ? (
                    <>
                      <Icon icon="line-md:loading-loop" className="h-4 w-4" />
                      Scanning Repository...
                    </>
                  ) : (
                    "Authorize & Scan"
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
