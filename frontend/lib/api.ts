/**
 * Typed client for the WhichCloud API.
 *
 * The backend deliberately returns things a typical API hides — when a price
 * was fetched, what a saving was measured against, which techniques were
 * skipped and why. Those fields are modelled here rather than dropped,
 * because the interface's job is to show them.
 */

// 127.0.0.1 rather than localhost, deliberately: uvicorn binds IPv4 only by
// default, and Node resolves "localhost" to ::1 first — which nothing is
// listening on. The result is a connection refused that looks like the API
// is down when it is running fine.
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type Health = {
  status: string;
  prices: number;
  providers: string[];
  last_updated: string;
};

export type CatalogRow = {
  provider: string;
  region: string;
  sku: string;
  name: string;
  vcpu: number | null;
  memory_gb: number | null;
  arch: string | null;
  unit: string;
  hourly_usd: number;
  monthly_usd: number;
  /** When this price came from the provider. Shown, never implied as live. */
  fetched_at: string;
};

export type Catalog = {
  region: string;
  category: string;
  count: number;
  rows: CatalogRow[];
};

export type LineItem = {
  label: string;
  sku: string;
  unit: string;
  unit_price: number;
  quantity: number;
  monthly_usd: number;
};

export type Technique = {
  id: string;
  name: string;
  category: string;
  summary: string;
  obviousness: string;
  confidence: string;
  tool: string;
  tool_url: string | null;
  tradeoffs: string[];
  /** Measured, never claimed — null when the technique cannot be priced. */
  saved_monthly_usd: number | null;
  /** The SKU this saving beat, so the figure can be checked. */
  versus_sku: string | null;
  reasons: string[];
  priced: boolean;
};

export type Node = {
  id: string;
  label: string;
  kind: string;
  monthly_usd: number;
  /** Fraction of the bill — drives visual weight, so expensive looks expensive. */
  share: number;
  sku: string;
  detail: string;
  priced: boolean;
  optimized_by: string[];
};

export type Edge = { source: string; target: string; label: string };

export type Option = {
  label: string;
  rationale: string;
  provider: string;
  region: string;
  monthly_usd: number;
  complete: boolean;
  within_budget: boolean | null;
  shape: string;
  items: LineItem[];
  missing: string[];
  measured_saving_usd: number;
  saving_pct: number;
  applied: Technique[];
  advisory: Technique[];
  tradeoffs: string[];
  topology: { nodes: Node[]; edges: Edge[] };
};

export type Diff = {
  from_label: string;
  to_label: string;
  delta_monthly_usd: number;
  changes: {
    label: string;
    kind: "added" | "removed" | "changed" | "unchanged";
    delta_usd: number;
    before_sku: string | null;
    after_sku: string | null;
  }[];
};

export type Recommendation = {
  goal: string;
  region: string;
  options: Option[];
  diffs: Diff[];
  not_applied: { id: string; name: string; reason: string }[];
  sizing_basis: string;
  assumed: string[];
  clarifying_question: string | null;
  read_by: string | null;
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function get<T>(path: string, revalidate = 300): Promise<T> {
  const response = await fetch(`${BASE}${path}`, { next: { revalidate } });
  if (!response.ok) {
    throw new ApiError(`GET ${path} failed`, response.status);
  }
  return response.json();
}

export const api = {
  health: () => get<Health>("/health", 60),

  catalog: (params: Record<string, string | number> = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).map(([k, v]) => [k, String(v)]),
    );
    return get<Catalog>(`/catalog?${query}`);
  },

  techniques: () => get<{ count: number; techniques: Technique[] }>("/techniques"),

  async recommend(body: Record<string, unknown>): Promise<Recommendation> {
    const response = await fetch(`${BASE}/recommend`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new ApiError(detail.detail ?? "recommendation failed", response.status);
    }
    return response.json();
  },
};

/** Prices are the product. Format them once, consistently, everywhere. */
export function money(value: number, decimals = 2): string {
  return `$${value.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
}

/** "14 Aug 16:44" — short enough for a pill, precise enough to be checkable. */
export function freshness(iso: string): string {
  return new Date(iso).toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}
