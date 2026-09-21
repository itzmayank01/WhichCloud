"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useAuth } from "@clerk/nextjs";
import { Icon } from "@iconify/react";
import { api, type ConnectionSetup } from "@/lib/api";
import { setStoredAccount } from "@/lib/connectedAccount";

//: Gap BETWEEN checks, not a tick rate: the next check is scheduled once the
//: previous one has answered, so a slow backend cannot cause them to overlap.
const POLL_INTERVAL_MS = 6000;

//: How long to keep watching. A deadline rather than a count of attempts,
//: because attempts are not a unit of time when a request can take 30-60s:
//: the old "20 attempts, one every 6s" gave up after two minutes having
//: actually completed only a handful of them. Five minutes is sized for
//: someone signing in to AWS, opening CloudShell (which takes ~30s to boot)
//: and pasting -- with the backend possibly cold-starting underneath.
const POLL_WINDOW_MS = 5 * 60 * 1000;

export default function ConnectAwsPage() {
  const router = useRouter();
  const { getToken, userId } = useAuth();
  const [setupData, setSetupData] = useState<ConnectionSetup | null>(null);
  const [loading, setLoading] = useState(true);
  const [setupError, setSetupError] = useState("");

  const [awsAccountId, setAwsAccountId] = useState("");
  const [customRoleArn, setCustomRoleArn] = useState("");
  const [region, setRegion] = useState("us-east-1");
  const [connecting, setConnecting] = useState(false);
  const [copiedId, setCopiedId] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [advancedOption, setAdvancedOption] = useState<"cli" | "terraform">("cli");
  const [errorMsg, setErrorMsg] = useState("");

  const [autoStatus, setAutoStatus] = useState<"idle" | "waiting" | "failed">("idle");
  const pollTimerRef = useRef<number | null>(null);
  const pollStoppedRef = useRef(true);
  const pollDeadlineRef = useRef(0);

  useEffect(() => {
    (async () => {
      try {
        const token = await getToken();
        const data = await api.connectionSetup("aws", {}, token ?? undefined);
        setSetupData(data);
      } catch (err) {
        // A setup call that fails must say so, not hand the page a fake
        // external id and a broken link that looks the same as a working one.
        setSetupError(
          err instanceof Error
            ? `Could not load connection setup: ${err.message}`
            : "Could not load connection setup. Please refresh and try again.",
        );
      } finally {
        setLoading(false);
      }
    })();
  }, [getToken]);

  useEffect(() => {
    return () => {
      pollStoppedRef.current = true;
      if (pollTimerRef.current) window.clearTimeout(pollTimerRef.current);
    };
  }, []);


  const externalId = setupData?.external_id || "";
  const ourAccountId = setupData?.our_account_id || "";
  const accountIdValid = /^\d{12}$/.test(awsAccountId.trim());
  const derivedRoleArn = accountIdValid
    ? `arn:aws:iam::${awsAccountId.trim()}:role/WhichCloudCostRole`
    : "";
  const roleArnToUse = customRoleArn.trim() || derivedRoleArn;

  const templateUrl =
    typeof window !== "undefined" ? `${window.location.origin}/whichcloud-role.yaml` : "";

  /* CloudShell rather than a CloudFormation quick-create link.
   *
   * A quick-create link needs ?templateURL=, and CloudFormation only accepts
   * one "located in an Amazon S3 bucket or a Systems Manager document --
   * URLs from S3 static websites are not supported". Pointing it at the copy
   * this site serves fails with "TemplateURL must be a supported URL", so a
   * one-click stack is not available to us without publishing the template to
   * an S3 bucket of our own.
   *
   * These two commands need no bucket, no download and no upload: CloudShell
   * opens in the browser already signed in as the person who is looking at
   * it, so the whole flow stays inside the console tab they just opened. IAM
   * is global, so there is no region to get wrong either. */
  const roleCommand = useMemo(() => {
    if (!externalId || !ourAccountId) return "";
    const trust = JSON.stringify({
      Version: "2012-10-17",
      Statement: [
        {
          Effect: "Allow",
          Principal: { AWS: `arn:aws:iam::${ourAccountId}:root` },
          Action: "sts:AssumeRole",
          Condition: { StringEquals: { "sts:ExternalId": externalId } },
        },
      ],
    });
    const permissions = JSON.stringify({
      Version: "2012-10-17",
      Statement: [
        {
          Effect: "Allow",
          Action: ["ce:GetCostAndUsage", "ce:GetDimensionValues"],
          Resource: "*",
        },
      ],
    });
    return [
      `aws iam create-role --role-name WhichCloudCostRole \\`,
      `  --assume-role-policy-document '${trust}' && \\`,
      `aws iam put-role-policy --role-name WhichCloudCostRole \\`,
      `  --policy-name WhichCloudCostExplorerReadOnly \\`,
      `  --policy-document '${permissions}'`,
    ].join("\n");
  }, [externalId, ourAccountId]);

  const cloudShellUrl = "https://console.aws.amazon.com/cloudshell/home?region=us-east-1";

  const handleCopyExternalId = () => {
    navigator.clipboard.writeText(externalId);
    setCopiedId(true);
    setTimeout(() => setCopiedId(false), 2000);
  };

  const stopPolling = () => {
    pollStoppedRef.current = true;
    if (pollTimerRef.current) {
      window.clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  };

  /** One verification attempt against `arn`. Returns true and navigates on
   *  success; on failure, only surfaces an error when `silent` is false --
   *  a background poll failing once just means the stack isn't done yet,
   *  which is not the same thing as the connection being wrong. */
  const attemptConnect = useCallback(
    async (arn: string, silent: boolean): Promise<boolean> => {
      if (!arn) return false;
      try {
        const token = await getToken();
        const res = await api.connectionVerify(
          "aws",
          { role_arn: arn, external_id: externalId, region },
          token ?? undefined,
        );
        if (res.ok) {
          const accId = res.account_id || arn.split(":")[4] || "";
          if (!accId) {
            if (!silent) setErrorMsg("Verified, but no account id came back. Check the role ARN format.");
            return false;
          }
          setStoredAccount({
            ownerId: userId ?? undefined,
            provider: "aws",
            id: accId,
            name: `AWS Account (${accId})`,
            region,
          });
          router.push(`/finops?provider=aws&account_id=${encodeURIComponent(accId)}`);
          return true;
        }
        if (!silent) setErrorMsg(res.message || "Could not verify IAM role. Please check the ARN and permissions.");
        return false;
      } catch (err) {
        if (!silent) {
          setErrorMsg(
            err instanceof Error
              ? `Could not reach the verification service: ${err.message}`
              : "Could not reach the verification service. Please try again.",
          );
        }
        return false;
      }
    },
    [getToken, externalId, region, userId, router],
  );

  /* A self-scheduling chain, NOT setInterval.
   *
   * setInterval fired every 6s whether or not the previous check had come
   * back. Verification calls AssumeRole through a backend that sleeps when
   * idle, so the first check after a cold start can take 30-60s -- during
   * which the interval had already queued ten more, all of them redundant,
   * all of them hitting a backend that was busy waking up. Scheduling the
   * next check only once the previous has answered makes overlap
   * structurally impossible rather than unlikely. */
  const startAutoDetect = (arn: string) => {
    if (!arn) return;
    setErrorMsg("");
    setAutoStatus("waiting");
    stopPolling();
    pollStoppedRef.current = false;
    pollDeadlineRef.current = Date.now() + POLL_WINDOW_MS;

    const check = async () => {
      if (pollStoppedRef.current) return;
      const ok = await attemptConnect(arn, true);
      // Re-read the flag: the user may have cancelled, navigated or edited
      // the account id while this request was in flight.
      if (ok || pollStoppedRef.current) return;
      if (Date.now() >= pollDeadlineRef.current) {
        setAutoStatus("failed");
        setErrorMsg(
          "Still can't see that role. Check the command ran without an error in "
          + "CloudShell, or paste the role ARN under Advanced below.",
        );
        return;
      }
      pollTimerRef.current = window.setTimeout(check, POLL_INTERVAL_MS);
    };

    pollTimerRef.current = window.setTimeout(check, POLL_INTERVAL_MS);
  };

  const [copiedCmd, setCopiedCmd] = useState(false);

  const handleCopyCommand = async () => {
    if (!roleCommand) return;
    try {
      await navigator.clipboard.writeText(roleCommand);
      setCopiedCmd(true);
      setTimeout(() => setCopiedCmd(false), 2500);
    } catch {
      // Clipboard is blocked in some mobile browsers; the command is on
      // screen and selectable, so this is not worth an error message.
    }
  };

  const handleOpenCloudShell = () => {
    if (!accountIdValid || !roleCommand) return;
    // A blocked popup returns null. Mobile browsers block these routinely, and
    // silently starting to watch for a role in a console that never opened
    // looks exactly like the connection being broken.
    const opened = window.open(cloudShellUrl, "_blank", "noopener,noreferrer");
    startAutoDetect(derivedRoleArn);
    if (!opened) {
      setErrorMsg(
        "Your browser blocked the new tab. Open AWS CloudShell yourself and "
        + "paste the command — this page keeps watching either way.",
      );
    }
  };

  const handleCheckNow = async () => {
    setConnecting(true);
    setErrorMsg("");
    const ok = await attemptConnect(roleArnToUse, false);
    if (ok) {
      stopPolling();
      setAutoStatus("idle");
    }
    setConnecting(false);
  };

  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!roleArnToUse) {
      setErrorMsg("Enter the role ARN you created in your own AWS account.");
      return;
    }
    setConnecting(true);
    setErrorMsg("");
    const ok = await attemptConnect(roleArnToUse, false);
    if (ok) stopPolling();
    setConnecting(false);
  };

  /* --template-body with a local file, NOT --template-url: CloudFormation
   * only accepts a template URL that lives in S3, so the copy this site
   * serves has to be downloaded first and passed as a body. */
  const cliSnippet = `curl -O ${templateUrl || "<connect page origin>/whichcloud-role.yaml"}

aws cloudformation create-stack \\
  --stack-name WhichCloudCostRole \\
  --region us-east-1 \\
  --template-body file://whichcloud-role.yaml \\
  --parameters ParameterKey=ExternalId,ParameterValue=${externalId || "<external-id>"} ParameterKey=TrustedAccountId,ParameterValue=${ourAccountId || "<not configured>"} \\
  --capabilities CAPABILITY_NAMED_IAM`;

  const terraformSnippet = `resource "aws_iam_role" "whichcloud_cost_role" {
  name = "WhichCloudCostRole"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { AWS = "arn:aws:iam::${ourAccountId || "<not configured>"}:root" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "sts:ExternalId" = "${externalId || "<external-id>"}" }
      }
    }]
  })
}

resource "aws_iam_role_policy" "whichcloud_cost_explorer_readonly" {
  name = "WhichCloudCostExplorerReadOnly"
  role = aws_iam_role.whichcloud_cost_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ce:GetCostAndUsage", "ce:GetDimensionValues"]
      Resource = "*"
    }]
  })
}`;

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col px-6 py-12">
      {/* Top Bar */}
      <div className="flex items-center justify-between border-b border-line pb-6">
        <div className="flex items-center gap-3.5">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-line bg-surface p-2 shadow-xs">
            <Icon icon="logos:aws" width={28} height={28} />
          </div>
          <div>
            <div className="flex items-center gap-2 text-[12.5px] font-medium text-ink-3">
              <Link href="/connect" className="hover:text-ink">
                Onboarding
              </Link>
              <span>/</span>
              <span>Connect AWS</span>
            </div>
            <h2 className="text-[20px] font-bold text-ink">AWS</h2>
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
            href="https://docs.aws.amazon.com/cost-management/latest/userguide/ce-what-is.html"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 rounded-lg border border-line bg-surface px-3 py-1.5 text-[13px] font-medium text-ink-2 hover:bg-sunk hover:text-ink"
          >
            Docs <Icon icon="mdi:arrow-top-right" className="h-3.5 w-3.5" />
          </a>
        </div>
      </div>

      <div className="mt-8">
        <h1 className="text-[26px] font-bold tracking-tight text-ink">Connect Your Account</h1>
        <p className="mt-2 text-[15px] leading-relaxed text-ink-2">
          WhichCloud reads your AWS costs through a role you create in your own account. Nothing
          of yours is stored except that role&apos;s ARN.
        </p>

        {setupError && (
          <div className="mt-6 rounded-xl border border-caution/40 bg-caution-wash p-4 text-[13.5px] text-caution">
            {setupError}
          </div>
        )}

        {/* Every other branch here is gated on `!loading`, and nothing was
            gated on `loading` -- so while the setup call was in flight the
            page rendered its heading and then stopped. On a backend that
            sleeps after 15 minutes idle that is a blank page for up to a
            minute, with no indication anything is happening, which reads as
            the connect page being broken rather than slow. */}
        {loading && (
          <div className="mt-6 space-y-4" aria-busy="true">
            <p className="text-[13.5px] text-ink-3">
              Preparing your connection details&hellip; this can take up to a minute
              if the service has been idle.
            </p>
            <div className="animate-pulse rounded-xl border border-line bg-sunk" style={{ height: 120 }} />
            <div className="animate-pulse rounded-xl border border-line bg-sunk" style={{ height: 200 }} />
          </div>
        )}

        {!loading && !setupError && !ourAccountId && (
          <div className="mt-6 rounded-xl border border-caution/40 bg-caution-wash p-4 text-[13.5px] text-caution">
            This deployment can&apos;t accept AWS connections right now: it couldn&apos;t
            determine its own AWS identity, which is the account your role needs to trust.
            That usually means the backend is missing AWS credentials. Connecting will work
            as soon as it can reach AWS &mdash; nothing to do on your side.
          </div>
        )}

        {!loading && !setupError && ourAccountId && (
          <>
            <ol className="mt-6 space-y-3.5 text-[14.5px] leading-relaxed text-ink-2">
              <li className="flex items-start gap-2.5">
                <span className="font-semibold text-ink">1.</span>
                <span>Enter your 12-digit AWS account id below.</span>
              </li>
              <li className="flex items-start gap-2.5">
                <span className="font-semibold text-ink">2.</span>
                <span>
                  Copy the command below, then click <strong>Open AWS CloudShell</strong>. Sign
                  in if you need to, paste, and press Enter. It creates a read-only role that
                  trusts only this deployment.
                </span>
              </li>
              <li className="flex items-start gap-2.5">
                <span className="font-semibold text-ink">3.</span>
                <span>
                  Come back to this tab. WhichCloud checks for the role every few seconds and
                  connects automatically once it exists -- no ARN to copy back.
                </span>
              </li>
            </ol>

            <div className="mt-8 rounded-2xl border border-accent/30 bg-accent/5 p-6 shadow-xs">
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="block text-[13px] font-medium text-ink-2">
                    Your AWS Account ID
                  </label>
                  <input
                    type="text"
                    inputMode="numeric"
                    placeholder="123456789012"
                    value={awsAccountId}
                    onChange={(e) => {
                      setAwsAccountId(e.target.value.replace(/[^0-9]/g, "").slice(0, 12));
                      // The ARN being watched for is derived from this, so a
                      // poll started for the previous number is now watching a
                      // role the user is no longer asking about.
                      stopPolling();
                      setAutoStatus("idle");
                    }}
                    className="mt-1.5 w-full rounded-lg border border-line bg-canvas px-3.5 py-2 font-mono text-[13.5px] text-ink outline-none focus:border-accent"
                  />
                </div>
                <div>
                  <label className="block text-[13px] font-medium text-ink-2">
                    Primary AWS Region
                  </label>
                  <select
                    value={region}
                    onChange={(e) => setRegion(e.target.value)}
                    className="mt-1.5 w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13.5px] text-ink outline-none"
                  >
                    <option value="us-east-1">US East (N. Virginia) · us-east-1</option>
                    <option value="ap-south-1">Asia Pacific (Mumbai) · ap-south-1</option>
                    <option value="eu-west-1">Europe (Ireland) · eu-west-1</option>
                    <option value="us-west-2">US West (Oregon) · us-west-2</option>
                  </select>
                </div>
              </div>

              {accountIdValid && roleCommand && (
                <div className="mt-4 rounded-xl border border-line bg-sunk p-3">
                  <div className="flex items-center justify-between gap-3 text-[11.5px] font-mono uppercase tracking-wider text-ink-3">
                    <span>Run this in CloudShell</span>
                    <button
                      type="button"
                      onClick={handleCopyCommand}
                      className="rounded-md border border-line bg-surface px-2.5 py-1 text-[12px] font-medium normal-case tracking-normal text-ink hover:bg-sunk"
                    >
                      {copiedCmd ? "Copied!" : "Copy"}
                    </button>
                  </div>
                  <pre className="mt-2 overflow-x-auto whitespace-pre text-[11.5px] leading-relaxed font-mono text-ink">
                    {roleCommand}
                  </pre>
                </div>
              )}

              <div className="mt-4 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  disabled={!accountIdValid || !roleCommand}
                  onClick={handleOpenCloudShell}
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-accent px-5 py-2.5 text-[13.5px] font-semibold text-white transition-all shadow-xs hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <Icon icon="mdi:console" className="h-4 w-4" />
                  <span>Open AWS CloudShell</span>
                </button>

                {autoStatus === "waiting" && (
                  <span className="inline-flex items-center gap-2 text-[13px] text-ink-2">
                    <Icon icon="mdi:loading" className="h-4 w-4 animate-spin text-accent" />
                    Waiting for the role to appear...
                  </span>
                )}

                {autoStatus !== "idle" && (
                  <button
                    type="button"
                    disabled={connecting || !roleArnToUse}
                    onClick={handleCheckNow}
                    className="rounded-lg border border-line bg-surface px-4 py-2 text-[13px] font-medium text-ink hover:bg-sunk disabled:opacity-50"
                  >
                    Check now
                  </button>
                )}
              </div>

              {!accountIdValid && awsAccountId.length > 0 && (
                <p className="mt-2 text-[12px] text-caution">Account id must be 12 digits.</p>
              )}

              <div className="mt-4 flex items-center gap-2 border-t border-line/60 pt-3">
                <span className="text-[12px] font-mono text-ink-3">External ID:</span>
                <code className="rounded bg-canvas px-2 py-1 font-mono text-[12px] text-ink">
                  {externalId}
                </code>
                <button
                  type="button"
                  onClick={handleCopyExternalId}
                  className="text-[12px] font-medium text-accent hover:underline"
                >
                  {copiedId ? "Copied!" : "Copy"}
                </button>
              </div>
            </div>

            {errorMsg && (
              <div className="mt-4 rounded-lg border border-caution/40 bg-caution-wash p-3 text-[13.5px] text-caution">
                {errorMsg}
              </div>
            )}

            {/* Advanced / manual fallback */}
            <div className="mt-6">
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="inline-flex items-center gap-1.5 text-[13px] font-medium text-ink-2 hover:text-ink"
              >
                <Icon icon={showAdvanced ? "mdi:chevron-down" : "mdi:chevron-right"} className="h-4 w-4" />
                Advanced: used a different role name, the CLI, or Terraform?
              </button>

              {showAdvanced && (
                <div className="mt-4 space-y-4 rounded-2xl border border-line bg-surface p-6 shadow-xs">
                  <div className="flex flex-wrap items-center gap-3">
                    <a
                      href="/whichcloud-role.yaml"
                      download="whichcloud-role.yaml"
                      className="inline-flex items-center gap-2 rounded-xl border border-line bg-surface px-4 py-2 text-[13px] font-medium text-ink hover:bg-sunk transition-colors shadow-2xs"
                    >
                      <Icon icon="mdi:download" className="h-4 w-4 text-accent" />
                      <span>Download whichcloud-role.yaml</span>
                    </a>
                    <button
                      type="button"
                      onClick={() => setAdvancedOption("cli")}
                      className={`rounded-xl border px-4 py-2 text-[13px] font-medium shadow-2xs ${advancedOption === "cli" ? "border-accent text-accent" : "border-line text-ink hover:bg-sunk"}`}
                    >
                      AWS CLI
                    </button>
                    <button
                      type="button"
                      onClick={() => setAdvancedOption("terraform")}
                      className={`rounded-xl border px-4 py-2 text-[13px] font-medium shadow-2xs ${advancedOption === "terraform" ? "border-accent text-accent" : "border-line text-ink hover:bg-sunk"}`}
                    >
                      Terraform
                    </button>
                  </div>

                  {advancedOption === "cli" && (
                    <div className="rounded-xl border border-line bg-sunk p-4">
                      <div className="flex items-center justify-between text-xs font-mono text-ink-3">
                        <span>Deploy the role directly with the AWS CLI:</span>
                        <button onClick={() => navigator.clipboard.writeText(cliSnippet)} className="text-accent hover:underline">
                          Copy
                        </button>
                      </div>
                      <pre className="mt-2 overflow-x-auto text-[12.5px] font-mono text-ink">{cliSnippet}</pre>
                    </div>
                  )}

                  {advancedOption === "terraform" && (
                    <div className="rounded-xl border border-line bg-sunk p-4">
                      <div className="flex items-center justify-between text-xs font-mono text-ink-3">
                        <span>Equivalent Terraform, self-contained (no registry module):</span>
                        <button onClick={() => navigator.clipboard.writeText(terraformSnippet)} className="text-accent hover:underline">
                          Copy
                        </button>
                      </div>
                      <pre className="mt-2 overflow-x-auto text-[12.5px] font-mono text-ink">{terraformSnippet}</pre>
                    </div>
                  )}

                  <form onSubmit={handleManualSubmit} className="space-y-3 border-t border-line/60 pt-4">
                    <div>
                      <label className="block text-[13px] font-medium text-ink-2">
                        Role ARN (only needed if it doesn&apos;t match the auto-detected one above)
                      </label>
                      <input
                        type="text"
                        placeholder={derivedRoleArn || "arn:aws:iam::123456789012:role/WhichCloudCostRole"}
                        value={customRoleArn}
                        onChange={(e) => setCustomRoleArn(e.target.value)}
                        className="mt-1.5 w-full rounded-lg border border-line bg-canvas px-3.5 py-2 font-mono text-[13.5px] text-ink placeholder:text-ink-3 outline-none focus:border-accent"
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <Link href="/connect" className="text-[13.5px] font-medium text-ink-3 hover:text-ink">
                        &larr; Back to Accounts
                      </Link>
                      <button
                        type="submit"
                        disabled={connecting}
                        className="inline-flex items-center gap-2 rounded-lg bg-accent px-6 py-2.5 text-[14px] font-semibold text-white shadow-xs transition-opacity hover:opacity-95 disabled:opacity-50"
                      >
                        {connecting ? (
                          <>
                            <Icon icon="mdi:loading" className="h-4 w-4 animate-spin" />
                            Connecting...
                          </>
                        ) : (
                          <>Verify & Launch FinOps Dashboard &rarr;</>
                        )}
                      </button>
                    </div>
                  </form>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </main>
  );
}
