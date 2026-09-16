/**
 * Connected Cloud Account State & Metadata
 * Manages the single connected account across AWS, Azure, GCP, and GitHub.
 * When a user connects an account, all dashboards, reports, and diagrams dynamically update.
 */

export type CloudProviderId = "aws" | "azure" | "gcp" | "github";

/** Provider branding, with no account identity in it. */
export interface ProviderBrand {
  provider: CloudProviderId;
  region: string;
  logo: string;
  brandName: string;
}

export interface ConnectedAccountData extends ProviderBrand {
  id: string;
  name: string;
  connectedAt?: string;
}

/** Branding per provider -- name, logo, default region. Deliberately carries
 *  NO account identity.
 *
 *  `aws` used to hold a real account number and alias, and `getStoredAccount`
 *  returned this record whenever nothing was stored. So a user who had just
 *  signed up and connected nothing was shown, and had requests made for,
 *  another person's AWS account. Identity belongs only to a connection the
 *  current user actually completed; anything shipped as a constant here is
 *  visible to everyone. */
export const CLOUD_PROVIDERS: Record<CloudProviderId, ProviderBrand> = {
  aws: {
    provider: "aws",
    brandName: "Amazon Web Services",
    region: "us-east-1",
    logo: "logos:aws",
  },
  azure: {
    provider: "azure",
    brandName: "Microsoft Azure",
    region: "eastus",
    logo: "logos:microsoft-azure",
  },
  gcp: {
    provider: "gcp",
    brandName: "Google Cloud Platform",
    region: "us-central1",
    logo: "logos:google-cloud",
  },
  github: {
    provider: "github",
    brandName: "GitHub IaC",
    region: "us-east-1",
    logo: "logos:github-icon",
  },
};

const STORAGE_KEY = "whichcloud.connected_account";

/** The account this user connected, or null if they have not connected one.
 *
 *  Null is the important case and the reason this returns a union: it used to
 *  fall back to the `aws` entry above, which meant "no connection" was
 *  indistinguishable from "connected to that account" and every caller
 *  rendered somebody else's data for a brand new user. Callers must handle
 *  null by offering to connect, never by substituting a default. */
export function getStoredAccount(): ConnectedAccountData | null {
  if (typeof window === "undefined") return null;

  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      const brand = CLOUD_PROVIDERS[parsed?.provider as CloudProviderId];
      // An entry without an id is not a connection, whatever else it holds.
      if (brand && typeof parsed.id === "string" && parsed.id.trim()) {
        return { ...brand, ...parsed, logo: brand.logo };
      }
    }
  } catch {
    // Unreadable storage is treated as "not connected", never as a default.
  }

  return null;
}

/** Forget the current connection (sign-out, or switching user). */
export function clearStoredAccount() {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(STORAGE_KEY);
    window.dispatchEvent(new Event("whichcloud:account_changed"));
  } catch {
    // ignore
  }
}

/** `id` is required: the branding record no longer carries one, and a stored
 *  entry without an id is exactly the shape that used to read as "connected"
 *  while naming an account the user never supplied. */
export function setStoredAccount(
  account: Partial<ConnectedAccountData> & { provider: CloudProviderId; id: string },
) {
  if (typeof window === "undefined") return;
  if (!account.id.trim()) return;

  try {
    const base = CLOUD_PROVIDERS[account.provider];
    const full: ConnectedAccountData = {
      ...base,
      name: `${base.brandName} (${account.id})`,
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
