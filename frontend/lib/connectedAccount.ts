/**
 * Connected Cloud Account State & Metadata
 * Manages the single connected account across AWS, Azure, GCP, and GitHub.
 * When a user connects an account, all dashboards, reports, and diagrams dynamically update.
 */

export type CloudProviderId = "aws" | "azure" | "gcp" | "github";

export interface ConnectedAccountData {
  provider: CloudProviderId;
  id: string;
  name: string;
  region: string;
  logo: string;
  brandName: string;
  connectedAt?: string;
}

export const CLOUD_PROVIDERS: Record<CloudProviderId, ConnectedAccountData> = {
  aws: {
    provider: "aws",
    id: "616551057703",
    name: "AWS Account (616551057703 • awsmayank)",
    brandName: "Amazon Web Services",
    region: "us-east-1 & us-west-2",
    logo: "logos:aws",
  },
  azure: {
    provider: "azure",
    id: "sub-azure-enterprise-01",
    name: "Azure Enterprise (sub-azure-01)",
    brandName: "Microsoft Azure",
    region: "eastus",
    logo: "logos:microsoft-azure",
  },
  gcp: {
    provider: "gcp",
    id: "gcp-prod-981",
    name: "Google Cloud Platform (gcp-prod-981)",
    brandName: "Google Cloud Platform",
    region: "us-central1",
    logo: "logos:google-cloud",
  },
  github: {
    provider: "github",
    id: "acme-corp/infra",
    name: "GitHub IaC Scanner (acme-corp/infra)",
    brandName: "GitHub IaC",
    region: "us-east-1",
    logo: "logos:github-icon",
  },
};

const STORAGE_KEY = "whichcloud.connected_account";

export function getStoredAccount(): ConnectedAccountData {
  if (typeof window === "undefined") {
    return CLOUD_PROVIDERS.aws;
  }

  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && parsed.provider && CLOUD_PROVIDERS[parsed.provider as CloudProviderId]) {
        return {
          ...CLOUD_PROVIDERS[parsed.provider as CloudProviderId],
          ...parsed,
          logo: CLOUD_PROVIDERS[parsed.provider as CloudProviderId].logo,
        };
      }
    }
  } catch {
    // Ignore JSON errors and fallback
  }

  return CLOUD_PROVIDERS.aws;
}

export function setStoredAccount(account: Partial<ConnectedAccountData> & { provider: CloudProviderId }) {
  if (typeof window === "undefined") return;

  try {
    const base = CLOUD_PROVIDERS[account.provider];
    const full: ConnectedAccountData = {
      ...base,
      ...account,
      connectedAt: new Date().toISOString(),
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(full));
    // Trigger storage event for cross-tab or cross-component reactivity
    window.dispatchEvent(new Event("whichcloud:account_changed"));
  } catch {
    // Ignore localStorage failures
  }
}
