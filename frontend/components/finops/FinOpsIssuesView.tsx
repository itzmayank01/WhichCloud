"use client";

import { useState } from "react";
import { Icon } from "@iconify/react";
import { CurrencyCode, formatCurrency } from "@/lib/currency";

export interface FinOpsIssue {
  id: string;
  title: string;
  service: string;
  category: string;
  severity: "critical" | "warning" | "opportunity";
  waste_monthly_usd: number;
  detected_at: string;
  resource_id: string;
  region: string;
  description: string;
  remediation_summary: string;
  terraform_fix: string;
  remediated?: boolean;
}

const DEFAULT_ISSUES: Record<string, FinOpsIssue[]> = {
  aws: [
    {
      id: "aws-iss-1",
      title: "3 Unattached EBS gp3 Volumes Idle for > 45 Days",
      service: "Amazon EBS",
      category: "Storage",
      severity: "critical",
      waste_monthly_usd: 184.0,
      detected_at: "2 hours ago",
      resource_id: "vol-084129b8c19a28f, vol-0218ef71c08d, vol-091a141b7f",
      region: "us-east-1",
      description:
        "3 provisioned gp3 volumes (1,200 GB total) were detached when staging worker nodes were terminated, but delete_on_termination was set to false.",
      remediation_summary: "Take snapshot of volumes and purge detached EBS allocations.",
      terraform_fix: `# Cleanup unattached volumes or set auto-delete in launch template
resource "aws_launch_template" "workers" {
  name_prefix = "eks-worker-"
  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size           = 100
      volume_type           = "gp3"
-     delete_on_termination = false
+     delete_on_termination = true
    }
  }
}`,
    },
    {
      id: "aws-iss-2",
      title: "Cross-AZ & Inter-Service NAT Gateway Egress Spike",
      service: "Amazon VPC",
      category: "Networking",
      severity: "critical",
      waste_monthly_usd: 390.0,
      detected_at: "5 hours ago",
      resource_id: "nat-0a8174f82810cd02",
      region: "us-east-1",
      description:
        "ECS tasks and worker nodes in private subnets are routing large S3 and DynamoDB API calls through NAT Gateway at $0.045/GB instead of using free VPC Gateway Endpoints.",
      remediation_summary: "Provision free S3 and DynamoDB Gateway VPC Endpoints.",
      terraform_fix: `resource "aws_vpc_endpoint" "s3" {
  vpc_id       = aws_vpc.main.id
  service_name = "com.amazonaws.us-east-1.s3"
  route_table_ids = [aws_route_table.private.id]
  vpc_endpoint_type = "Gateway"
}`,
    },
    {
      id: "aws-iss-3",
      title: "Overprovisioned m5.2xlarge Core Workers (< 18% CPU)",
      service: "Amazon EC2 / EKS",
      category: "Compute",
      severity: "warning",
      waste_monthly_usd: 480.0,
      detected_at: "Yesterday",
      resource_id: "i-091bc8201a41, i-0a82195f20",
      region: "us-east-1",
      description:
        "Node group utilization shows peak CPU below 22% and memory below 35% over the trailing 30 days. Downsizing to m6g.xlarge (Graviton3) maintains safety buffer.",
      remediation_summary: "Right-size instance family from m5.2xlarge to m6g.xlarge.",
      terraform_fix: `resource "aws_eks_node_group" "core" {
- instance_types = ["m5.2xlarge"]
+ instance_types = ["m6g.xlarge"]
  scaling_config {
    desired_size = 2
    max_size     = 4
    min_size     = 1
  }
}`,
    },
    {
      id: "aws-iss-4",
      title: "4 Unassociated Elastic IP Addresses Charging Hourly Fee",
      service: "Amazon EC2",
      category: "Networking",
      severity: "warning",
      waste_monthly_usd: 28.8,
      detected_at: "3 days ago",
      resource_id: "eipalloc-0174bf918, eipalloc-09821af",
      region: "us-east-1",
      description:
        "AWS charges $0.005/hour for IPv4 addresses reserved in your account that are not attached to a running instance.",
      remediation_summary: "Release unassociated Elastic IPs back to AWS pool.",
      terraform_fix: `# Release dormant Elastic IPs
# aws ec2 release-address --allocation-id eipalloc-0174bf918
# aws ec2 release-address --allocation-id eipalloc-09821af`,
    },
    {
      id: "aws-iss-5",
      title: "Standard S3 Bucket Objects Inactive for > 90 Days",
      service: "Amazon S3",
      category: "Storage",
      severity: "opportunity",
      waste_monthly_usd: 215.0,
      detected_at: "4 days ago",
      resource_id: "arn:aws:s3:::prod-customer-media-bucket",
      region: "us-east-1",
      description:
        "8.4 TB of historical backup blobs and media files have had 0 read requests in 90+ days and remain in S3 Standard storage tier.",
      remediation_summary: "Enable S3 Intelligent-Tiering or Glacier Flexible Archive lifecycle.",
      terraform_fix: `resource "aws_s3_bucket_lifecycle_configuration" "bucket_lifecycle" {
  bucket = aws_s3_bucket.media.id
  rule {
    id     = "auto-glacier"
    status = "Enabled"
    transition {
      days          = 90
      storage_class = "GLACIER"
    }
  }
}`,
    },
  ],
  azure: [
    {
      id: "az-iss-1",
      title: "Idle Azure SQL Database (Business Critical Tier)",
      service: "Azure SQL",
      category: "Database",
      severity: "critical",
      waste_monthly_usd: 490.0,
      detected_at: "3 hours ago",
      resource_id: "/subscriptions/.../sqldb-enterprise-core-prod",
      region: "eastus",
      description:
        "IOPS utilization never exceeds 1,100 IOPS. Business Critical tier is paying 3x premium over General Purpose tier.",
      remediation_summary: "Switch Azure SQL SKU from Business Critical to General Purpose Gen5.",
      terraform_fix: `resource "azurerm_mssql_database" "prod" {
- sku_name = "BC_Gen5_4"
+ sku_name = "GP_Gen5_4"
}`,
    },
    {
      id: "az-iss-2",
      title: "Unattached Azure Managed Disks (Premium SSD)",
      service: "Azure Disks",
      category: "Storage",
      severity: "critical",
      waste_monthly_usd: 175.0,
      detected_at: "1 day ago",
      resource_id: "/subscriptions/.../disk-dev-scratch-01",
      region: "eastus",
      description: "2x 512GB Premium SSD P20 disks orphaned after VM deletion.",
      remediation_summary: "Snapshot and purge orphaned managed disks.",
      terraform_fix: `# Purge orphaned managed disk
# az disk delete --resource-group prod-rg --name disk-dev-scratch-01 --yes`,
    },
    {
      id: "az-iss-3",
      title: "Batch Processing Running on On-Demand AKS VMSS",
      service: "AKS",
      category: "Compute",
      severity: "opportunity",
      waste_monthly_usd: 280.0,
      detected_at: "2 days ago",
      resource_id: "aks-batch-pool",
      region: "eastus",
      description: "Nightly ingestion workers can run on Azure Spot VMSS at 70% discount.",
      remediation_summary: "Convert AKS batch node pool priority to Spot.",
      terraform_fix: `resource "azurerm_kubernetes_cluster_node_pool" "batch" {
+ priority        = "Spot"
+ eviction_policy = "Delete"
}`,
    },
  ],
  gcp: [
    {
      id: "gcp-iss-1",
      title: "Idle Cloud SQL 32GB RAM Instance (Avg 14% memory use)",
      service: "Cloud SQL",
      category: "Database",
      severity: "critical",
      waste_monthly_usd: 510.0,
      detected_at: "4 hours ago",
      resource_id: "projects/prod-981/instances/csql-pg",
      region: "us-central1",
      description: "High-memory PostgreSQL instance oversized for current read/write volume.",
      remediation_summary: "Right-size instance to db-custom-4-16 (16GB RAM).",
      terraform_fix: `resource "google_sql_database_instance" "master" {
  settings {
-   tier = "db-custom-8-32"
+   tier = "db-custom-4-16"
  }
}`,
    },
    {
      id: "gcp-iss-2",
      title: "Unattached Persistent Disks (pd-ssd)",
      service: "Compute Engine Disks",
      category: "Storage",
      severity: "warning",
      waste_monthly_usd: 145.0,
      detected_at: "1 day ago",
      resource_id: "disks/pd-staging-backup-ssd",
      region: "us-central1",
      description: "350GB PD-SSD unattached to any Compute Engine or GKE instance.",
      remediation_summary: "Delete orphaned persistent disk.",
      terraform_fix: `# gcloud compute disks delete pd-staging-backup-ssd --zone=us-central1-a --quiet`,
    },
  ],
  github: [
    {
      id: "gh-iss-1",
      title: "Hardcoded Fixed-Size EKS Node Groups in Terraform",
      service: "Terraform IaC",
      category: "Architecture",
      severity: "critical",
      waste_monthly_usd: 490.0,
      detected_at: "1 hour ago",
      resource_id: "terraform/modules/eks/nodes.tf",
      region: "us-east-1",
      description:
        "Static desired_size = 5 prevents cluster scaling in during low activity windows. Karpenter dynamic autoscaling reduces node count automatically.",
      remediation_summary: "Adopt Karpenter dynamic provisioner with Spot fallback.",
      terraform_fix: `resource "helm_release" "karpenter" {
  name       = "karpenter"
  repository = "oci://public.ecr.aws/karpenter"
  chart      = "karpenter"
  version    = "v0.34.0"
}`,
    },
  ],
};

interface FinOpsIssuesViewProps {
  provider: string;
  currency?: CurrencyCode;
}

export function FinOpsIssuesView({
  provider = "aws",
  currency = "USD",
}: FinOpsIssuesViewProps) {
  const p = provider.toLowerCase();
  const rawList = DEFAULT_ISSUES[p] || DEFAULT_ISSUES.aws;

  const [issues, setIssues] = useState<FinOpsIssue[]>(rawList);
  const [filterSeverity, setFilterSeverity] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [remediatingId, setRemediatingId] = useState<string | null>(null);
  const [activeTerraformModal, setActiveTerraformModal] = useState<FinOpsIssue | null>(null);
  const [copied, setCopied] = useState(false);

  const filteredIssues = issues.filter((iss) => {
    if (filterSeverity !== "all" && iss.severity !== filterSeverity) return false;
    if (
      searchQuery &&
      !iss.title.toLowerCase().includes(searchQuery.toLowerCase()) &&
      !iss.service.toLowerCase().includes(searchQuery.toLowerCase())
    ) {
      return false;
    }
    return true;
  });

  const totalWaste = issues
    .filter((iss) => !iss.remediated)
    .reduce((acc, curr) => acc + curr.waste_monthly_usd, 0);

  const totalResolved = issues
    .filter((iss) => iss.remediated)
    .reduce((acc, curr) => acc + curr.waste_monthly_usd, 0);

  const handleRemediate = (id: string) => {
    setRemediatingId(id);
    setTimeout(() => {
      setIssues((prev) =>
        prev.map((iss) => (iss.id === id ? { ...iss, remediated: true } : iss))
      );
      setRemediatingId(null);
    }, 850);
  };

  const handleUndo = (id: string) => {
    setIssues((prev) =>
      prev.map((iss) => (iss.id === id ? { ...iss, remediated: false } : iss))
    );
  };

  return (
    <div className="mt-6 space-y-6">
      {/* Top Banner & KPI Stat Row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-2xl border border-line bg-surface p-5 shadow-xs">
          <div className="flex items-center justify-between text-[13px] text-ink-3">
            <span>Detected Active Cloud Waste</span>
            <span className="h-2 w-2 rounded-full bg-red-500 animate-ping" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="font-mono text-[28px] font-bold text-red-500">
              {formatCurrency(totalWaste, currency, 0)}
            </span>
            <span className="text-[12.5px] text-ink-3">/ mo</span>
          </div>
          <p className="mt-1 text-[12px] text-ink-2">
            {formatCurrency(totalWaste * 12, currency, 0)}/yr across {issues.filter((i) => !i.remediated).length} unresolved anomalies
          </p>
        </div>

        <div className="rounded-2xl border border-line bg-surface p-5 shadow-xs">
          <div className="flex items-center justify-between text-[13px] text-ink-3">
            <span>Remediated & Recovered</span>
            <Icon icon="mdi:check-decagram" className="h-4 w-4 text-emerald-500" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="font-mono text-[28px] font-bold text-emerald-500">
              +{formatCurrency(totalResolved, currency, 0)}
            </span>
            <span className="text-[12.5px] text-ink-3">/ mo</span>
          </div>
          <p className="mt-1 text-[12px] text-ink-2">
            Instant savings applied to connected cloud account
          </p>
        </div>

        <div className="rounded-2xl border border-line bg-surface p-5 shadow-xs">
          <div className="flex items-center justify-between text-[13px] text-ink-3">
            <span>Autonomous FinOps Guardrails</span>
            <span className="rounded bg-accent/10 px-2 py-0.5 text-[11px] font-semibold text-accent">
              Active
            </span>
          </div>
          <div className="mt-2 font-mono text-[28px] font-bold text-ink">
            {issues.length} Monitored
          </div>
          <p className="mt-1 text-[12px] text-ink-2">
            Continuous scanning of CUR, CloudWatch & Resource tags
          </p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-4 sm:flex-row sm:items-center sm:justify-between shadow-xs">
        <div className="flex flex-wrap items-center gap-2">
          {[
            { id: "all", label: `All Issues (${issues.length})` },
            {
              id: "critical",
              label: `Critical (${issues.filter((i) => i.severity === "critical").length})`,
              color: "text-red-500",
            },
            {
              id: "warning",
              label: `Warning (${issues.filter((i) => i.severity === "warning").length})`,
              color: "text-amber-500",
            },
            {
              id: "opportunity",
              label: `Opportunities (${issues.filter((i) => i.severity === "opportunity").length})`,
              color: "text-sky-500",
            },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setFilterSeverity(tab.id)}
              className={`rounded-xl px-3 py-1.5 text-[12.5px] font-medium transition-all ${
                filterSeverity === tab.id
                  ? "bg-accent text-white shadow-2xs"
                  : "bg-sunk text-ink-2 hover:text-ink"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="relative w-full sm:w-64">
          <Icon
            icon="mdi:magnify"
            className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-3"
          />
          <input
            type="text"
            placeholder="Search anomalies..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-xl border border-line bg-sunk/60 py-1.5 pl-9 pr-3 text-[12.5px] text-ink placeholder:text-ink-3 focus:border-accent focus:outline-none"
          />
        </div>
      </div>

      {/* Issues List */}
      <div className="space-y-3.5">
        {filteredIssues.map((issue) => {
          const isRemediating = remediatingId === issue.id;
          const isRemediated = !!issue.remediated;

          return (
            <div
              key={issue.id}
              className={`flex flex-col justify-between rounded-2xl border p-5 transition-all shadow-xs ${
                isRemediated
                  ? "border-emerald-500/30 bg-emerald-500/5 opacity-80"
                  : "border-line bg-surface hover:border-ink-3/40"
              }`}
            >
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider ${
                        issue.severity === "critical"
                          ? "bg-red-500/10 text-red-500 border border-red-500/20"
                          : issue.severity === "warning"
                          ? "bg-amber-500/10 text-amber-500 border border-amber-500/20"
                          : "bg-sky-500/10 text-sky-500 border border-sky-500/20"
                      }`}
                    >
                      <Icon
                        icon={
                          issue.severity === "critical"
                            ? "mdi:alert-circle"
                            : issue.severity === "warning"
                            ? "mdi:alert"
                            : "mdi:lightbulb-outline"
                        }
                        className="h-3 w-3"
                      />
                      {issue.severity}
                    </span>

                    <span className="rounded-md bg-sunk px-2 py-0.5 text-[11px] font-medium text-ink-2">
                      {issue.service}
                    </span>

                    <span className="font-mono text-[11px] text-ink-3">
                      {issue.region}
                    </span>

                    <span className="text-[11px] text-ink-3">• {issue.detected_at}</span>
                  </div>

                  <h3
                    className={`text-[15.5px] font-bold ${
                      isRemediated ? "line-through text-ink-3" : "text-ink"
                    }`}
                  >
                    {issue.title}
                  </h3>

                  <p className="text-[13px] leading-relaxed text-ink-2 max-w-3xl">
                    {issue.description}
                  </p>

                  <div className="pt-1 text-[12px] text-ink-3">
                    <span className="font-semibold text-ink-2">Target Resource:</span>{" "}
                    <code className="font-mono text-[11.5px] text-ink bg-sunk px-1.5 py-0.5 rounded">
                      {issue.resource_id}
                    </code>
                  </div>
                </div>

                {/* Right: Dollar Waste & Action Buttons */}
                <div className="flex flex-row items-center justify-between lg:flex-col lg:items-end gap-3 shrink-0 pt-2 lg:pt-0">
                  <div className="text-right">
                    <div className="flex items-baseline gap-1.5">
                      <span
                        className={`font-mono text-[22px] font-bold ${
                          isRemediated ? "text-emerald-500 line-through" : "text-red-500"
                        }`}
                      >
                        {formatCurrency(issue.waste_monthly_usd, currency, 0)}
                      </span>
                      <span className="text-[12px] text-ink-3">/ mo waste</span>
                    </div>
                    <div className="text-[11px] text-ink-3">
                      {formatCurrency(issue.waste_monthly_usd * 12, currency, 0)}/yr
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setActiveTerraformModal(issue)}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-line bg-surface px-3 py-1.5 text-[12.5px] font-medium text-ink hover:bg-sunk transition-colors"
                      title="Inspect Terraform code to fix this issue"
                    >
                      <Icon icon="logos:terraform-icon" className="h-3.5 w-3.5" />
                      <span>Terraform Diff</span>
                    </button>

                    {isRemediated ? (
                      <button
                        onClick={() => handleUndo(issue.id)}
                        className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 px-3.5 py-1.5 text-[12.5px] font-semibold hover:bg-emerald-500/25 transition-all"
                      >
                        <Icon icon="mdi:check-circle" className="h-4 w-4" />
                        <span>Remediated</span>
                        <span className="text-[10px] underline ml-1 text-ink-3">Undo</span>
                      </button>
                    ) : (
                      <button
                        onClick={() => handleRemediate(issue.id)}
                        disabled={isRemediating}
                        className="inline-flex items-center gap-1.5 rounded-xl bg-accent px-3.5 py-1.5 text-[12.5px] font-semibold text-white hover:opacity-90 transition-all shadow-xs"
                      >
                        {isRemediating ? (
                          <>
                            <Icon
                              icon="line-md:loading-loop"
                              className="h-3.5 w-3.5 animate-spin"
                            />
                            <span>Applying Fix...</span>
                          </>
                        ) : (
                          <>
                            <Icon icon="mdi:lightning-bolt" className="h-3.5 w-3.5" />
                            <span>1-Click Fix</span>
                          </>
                        )}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Terraform Code Modal */}
      {activeTerraformModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
          <div className="relative w-full max-w-xl rounded-2xl border border-line bg-surface p-6 shadow-2xl">
            <button
              onClick={() => {
                setActiveTerraformModal(null);
                setCopied(false);
              }}
              className="absolute right-4 top-4 rounded-md p-1 text-ink-3 hover:text-ink"
            >
              <Icon icon="mdi:close" className="h-5 w-5" />
            </button>

            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-line bg-sunk">
                <Icon icon="logos:terraform-icon" className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-[17px] font-bold text-ink">
                  Automated Infrastructure Remediation
                </h3>
                <p className="text-[12.5px] text-ink-3">
                  {activeTerraformModal.title} (Saves{" "}
                  {formatCurrency(activeTerraformModal.waste_monthly_usd, currency, 0)}/mo)
                </p>
              </div>
            </div>

            <p className="mt-3 text-[13px] text-ink-2">
              Apply this infrastructure diff in your Git repo to permanently eliminate this waste:
            </p>

            <div className="mt-3 relative rounded-xl border border-line bg-[#10141a] p-4 font-mono text-[12.5px] text-emerald-400 overflow-x-auto">
              <pre>{activeTerraformModal.terraform_fix}</pre>
            </div>

            <div className="mt-6 flex items-center justify-between">
              <span className="text-[12px] text-ink-3">
                Zero-downtime, safe to apply in CI/CD pipeline
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(activeTerraformModal.terraform_fix);
                    setCopied(true);
                    setTimeout(() => setCopied(false), 2000);
                  }}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-4 py-2 text-[13px] font-medium text-ink hover:bg-sunk"
                >
                  <Icon
                    icon={copied ? "mdi:check" : "mdi:content-copy"}
                    className="h-4 w-4 text-accent"
                  />
                  {copied ? "Copied Diff" : "Copy Code"}
                </button>

                <button
                  onClick={() => {
                    handleRemediate(activeTerraformModal.id);
                    setActiveTerraformModal(null);
                  }}
                  className="rounded-lg bg-accent px-4 py-2 text-[13px] font-semibold text-white hover:opacity-90"
                >
                  Mark as Remediated
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
