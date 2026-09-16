"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { useAuth } from "@clerk/nextjs";
import { Icon } from "@iconify/react";
import { api, type ConnectionSetup } from "@/lib/api";
import { setStoredAccount } from "@/lib/connectedAccount";

export default function ConnectAwsPage() {
  const router = useRouter();
  const { getToken, userId } = useAuth();
  const [setupData, setSetupData] = useState<ConnectionSetup | null>(null);
  const [loading, setLoading] = useState(true);
  const [roleArn, setRoleArn] = useState("");
  const [region, setRegion] = useState("us-east-1");
  const [verifying, setVerifying] = useState(false);
  const [copiedId, setCopiedId] = useState(false);
  const [activeOption, setActiveOption] = useState<"cfn" | "cli" | "terraform" | "console">("cfn");
  const [showDropdown, setShowDropdown] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const token = await getToken();
        const data = await api.connectionSetup("aws", {}, token ?? undefined);
        setSetupData(data);
      } catch {
        // Fallback demo setup data
        setSetupData({
          provider: "aws",
          external_id: "whichcloud-a8f9c2d1e04b73f6a5b2",
          grants: "Read-only access to your AWS Cost Explorer totals.",
          stores_secret: false,
          steps: [],
          cloudformation_url:
            "https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/create/review?templateURL=https://whichcloud-public.s3.amazonaws.com/cfn/whichcloud-role.yaml&stackName=WhichCloudCostRole",
        });
      } finally {
        setLoading(false);
      }
    })();
  }, [getToken]);

  const externalId = setupData?.external_id || "whichcloud-sec-8a9021b3";

  const handleCopyExternalId = () => {
    navigator.clipboard.writeText(externalId);
    setCopiedId(true);
    setTimeout(() => setCopiedId(false), 2000);
  };

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setVerifying(true);
    setErrorMsg("");

    try {
      const token = await getToken();
      if (!roleArn.trim()) {
        setErrorMsg("Enter the role ARN you created in your own AWS account.");
        setVerifying(false);
        return;
      }

      const res = await api.connectionVerify("aws", {
        role_arn: roleArn,
        external_id: externalId,
        region,
      }, token ?? undefined);

      if (res.ok) {
        // Identity comes from the verified role, never from a literal in this
        // file: the account is whatever the server confirmed, or the account
        // segment of the ARN the user themselves typed.
        const accId = res.account_id || roleArn.split(":")[4] || "";
        if (!accId) {
          setErrorMsg("Verified, but no account id came back. Check the role ARN format.");
          setVerifying(false);
          return;
        }
        setStoredAccount({
          ownerId: userId ?? undefined,
          provider: "aws",
          id: accId,
          name: `AWS Account (${accId})`,
          region,
        });
        router.push(`/finops?provider=aws&account_id=${encodeURIComponent(accId)}`);
      } else {
        setErrorMsg(res.message || "Could not verify IAM role. Please check the ARN and permissions.");
        setVerifying(false);
      }
    } catch (err) {
      /* A failed verification must NOT look like a successful one. This used
         to swallow the error, invent a connected account and navigate to the
         cockpit anyway, so a network blip -- or a user who had connected
         nothing at all -- landed on FinOps presented as connected. */
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
      {/* Top Bar matching screenshot */}
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

      {/* Main instructions matching screenshot */}
      <div className="mt-8">
        <h1 className="text-[26px] font-bold tracking-tight text-ink">
          Connect Your Account
        </h1>
        <p className="mt-2 text-[15px] leading-relaxed text-ink-2">
          To securely connect to AWS, we require a Cross-Account IAM Role to be created.
        </p>

        <ol className="mt-6 space-y-3.5 text-[14.5px] leading-relaxed text-ink-2">
          <li className="flex items-start gap-2.5">
            <span className="font-semibold text-ink">1.</span>
            <span>
              Connect via the IAM interface, or by running one of the AWS CLI command options below.
            </span>
          </li>
          <li className="flex items-start gap-2.5">
            <span className="font-semibold text-ink">2.</span>
            <div>
              <span>You&apos;ll be prompted to create a role with read only in-line policies using CloudFormation.</span>
              <p className="mt-1 text-[13px] text-ink-3">
                • <strong>Note:</strong> Regardless of the AWS regions your infrastructure is located in, this command must be run in <code className="rounded bg-sunk px-1.5 py-0.5 text-ink font-mono text-[12px]">us-east-1</code>.
              </p>
            </div>
          </li>
          <li className="flex items-start gap-2.5">
            <span className="font-semibold text-ink">3.</span>
            <span>
              Once the stack is created, WhichCloud will automatically detect its presence and begin syncing your account data automatically.
            </span>
          </li>
          <li className="flex items-start gap-2.5">
            <span className="font-semibold text-ink">4.</span>
            <span>
              <strong>Return to this page after it has completed</strong> (it can take a minute or two).
            </span>
          </li>
        </ol>

        {/* CloudFormation Template Guidance */}
        <div className="mt-6 rounded-2xl border border-line bg-surface p-6 shadow-xs space-y-3">
          <div className="flex items-start gap-3">
            <Icon icon="mdi:cloud-upload-outline" className="h-5 w-5 text-accent shrink-0 mt-0.5" />
            <div>
              <h4 className="text-[15px] font-bold text-ink">
                Deploying IAM Role via AWS CloudFormation
              </h4>
              <p className="mt-1 text-[13px] leading-relaxed text-ink-2">
                If the AWS Quick-Create link showed <code className="font-mono text-red-500 bg-red-500/10 px-1 py-0.5 rounded">S3 error: The specified bucket does not exist</code>, simply download the template below and choose <strong>&ldquo;Upload a template file&rdquo;</strong> in your AWS CloudFormation console:
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 pt-2">
            <a
              href="/whichcloud-role.yaml"
              download="whichcloud-role.yaml"
              className="inline-flex items-center gap-2 rounded-xl border border-line bg-surface px-4 py-2 text-[13px] font-medium text-ink hover:bg-sunk transition-colors shadow-2xs"
            >
              <Icon icon="mdi:download" className="h-4 w-4 text-accent" />
              <span>Download whichcloud-role.yaml</span>
            </a>

            <a
              href="https://us-east-1.console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/create/template"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-xl border border-line bg-surface px-4 py-2 text-[13px] font-medium text-ink hover:bg-sunk transition-colors shadow-2xs"
            >
              <span>Open CloudFormation Stack Upload</span>
              <Icon icon="mdi:arrow-top-right" className="h-3.5 w-3.5 text-ink-3" />
            </a>

            <div className="relative">
              <button
                type="button"
                onClick={() => setShowDropdown(!showDropdown)}
                className="inline-flex items-center gap-2 rounded-xl border border-line bg-surface px-4 py-2 text-[13px] font-medium text-ink hover:bg-sunk shadow-2xs"
              >
                CLI & Terraform Options
                <Icon icon="mdi:chevron-down" className="h-4 w-4 text-ink-3" />
              </button>

              {showDropdown && (
                <div className="absolute left-0 top-full z-20 mt-2 w-56 rounded-xl border border-line bg-surface py-1 shadow-lg">
                  <button
                    type="button"
                    onClick={() => {
                      setActiveOption("cli");
                      setShowDropdown(false);
                    }}
                    className="flex w-full px-4 py-2 text-left text-[13px] text-ink hover:bg-sunk"
                  >
                    AWS CLI Command
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setActiveOption("terraform");
                      setShowDropdown(false);
                    }}
                    className="flex w-full px-4 py-2 text-left text-[13px] text-ink hover:bg-sunk"
                  >
                    Terraform Module
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setActiveOption("console");
                      setShowDropdown(false);
                    }}
                    className="flex w-full px-4 py-2 text-left text-[13px] text-ink hover:bg-sunk"
                  >
                    Manual IAM Role Console
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Code Snippets for alternative options */}
        {activeOption === "cli" && (
          <div className="mt-6 rounded-xl border border-line bg-sunk p-4">
            <div className="flex items-center justify-between text-xs font-mono text-ink-3">
              <span>AWS CLI CloudFormation deploy command:</span>
              <button
                onClick={() =>
                  navigator.clipboard.writeText(
                    `aws cloudformation create-stack --stack-name WhichCloudCostRole --region us-east-1 --template-url https://whichcloud-public.s3.amazonaws.com/cfn/whichcloud-role.yaml --parameters ParameterKey=ExternalId,ParameterValue=${externalId} --capabilities CAPABILITY_NAMED_IAM`
                  )
                }
                className="text-accent hover:underline"
              >
                Copy
              </button>
            </div>
            <pre className="mt-2 overflow-x-auto text-[12.5px] font-mono text-ink">
              {`aws cloudformation create-stack \\
  --stack-name WhichCloudCostRole \\
  --region us-east-1 \\
  --template-url https://whichcloud-public.s3.amazonaws.com/cfn/whichcloud-role.yaml \\
  --parameters ParameterKey=ExternalId,ParameterValue=${externalId} \\
  --capabilities CAPABILITY_NAMED_IAM`}
            </pre>
          </div>
        )}

        {activeOption === "terraform" && (
          <div className="mt-6 rounded-xl border border-line bg-sunk p-4">
            <div className="flex items-center justify-between text-xs font-mono text-ink-3">
              <span>Terraform IAM Role snippet:</span>
              <button
                onClick={() =>
                  navigator.clipboard.writeText(
                    `module "whichcloud_role" {\n  source      = "whichcloud/iam-role/aws"\n  external_id = "${externalId}"\n}`
                  )
                }
                className="text-accent hover:underline"
              >
                Copy
              </button>
            </div>
            <pre className="mt-2 overflow-x-auto text-[12.5px] font-mono text-ink">
              {`module "whichcloud_role" {
  source      = "whichcloud/iam-role/aws"
  external_id = "${externalId}"
}`}
            </pre>
          </div>
        )}

        {/* Verification Form */}
        <div className="mt-10 rounded-2xl border border-line bg-surface p-6 shadow-xs">
          <h3 className="text-[17px] font-semibold text-ink">
            Confirm Connection Details
          </h3>
          <p className="mt-1 text-[13.5px] text-ink-2">
            Paste your created Role ARN or continue with our live demo account to explore your interactive cost diagram immediately.
          </p>

          <form onSubmit={handleVerify} className="mt-5 space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="block text-[13px] font-medium text-ink-2">
                  Your External ID (Required in Trust Policy)
                </label>
                <div className="mt-1.5 flex items-center gap-2">
                  <input
                    type="text"
                    readOnly
                    value={externalId}
                    className="w-full rounded-lg border border-line bg-canvas px-3 py-2 font-mono text-[13px] text-ink outline-none"
                  />
                  <button
                    type="button"
                    onClick={handleCopyExternalId}
                    className="shrink-0 rounded-lg border border-line bg-surface px-3 py-2 text-[13px] font-medium text-ink hover:bg-sunk"
                  >
                    {copiedId ? "Copied!" : "Copy"}
                  </button>
                </div>
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

            <div>
              <label className="block text-[13px] font-medium text-ink-2">
                Created Role ARN
              </label>
              <input
                type="text"
                placeholder="arn:aws:iam::123456789012:role/WhichCloudCostRole"
                value={roleArn}
                onChange={(e) => setRoleArn(e.target.value)}
                className="mt-1.5 w-full rounded-lg border border-line bg-canvas px-3.5 py-2 font-mono text-[13.5px] text-ink placeholder:text-ink-3 outline-none focus:border-accent"
              />
            </div>

            {errorMsg && (
              <div className="rounded-lg border border-caution/40 bg-caution-wash p-3 text-[13.5px] text-caution">
                {errorMsg}
              </div>
            )}

            <div className="flex items-center justify-between pt-3">
              <Link
                href="/connect"
                className="text-[13.5px] font-medium text-ink-3 hover:text-ink"
              >
                &larr; Back to Accounts
              </Link>
              <button
                type="submit"
                disabled={verifying}
                className="inline-flex items-center gap-2 rounded-lg bg-accent px-6 py-2.5 text-[14px] font-semibold text-white shadow-xs transition-opacity hover:opacity-95 disabled:opacity-50"
              >
                {verifying ? (
                  <>
                    <Icon icon="mdi:loading" className="h-4 w-4 animate-spin" />
                    Connecting & Syncing Data...
                  </>
                ) : (
                  <>
                    Verify & Launch FinOps Dashboard &rarr;
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </main>
  );
}
