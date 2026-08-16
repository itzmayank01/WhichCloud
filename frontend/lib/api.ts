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
/* 8010, not 8000. Another project on this machine runs a SurrealDB container
   published on 8000 with restart:always, so whichever of the two started
   first took the port and the other silently failed to bind -- which is why
   the API was intermittently unreachable rather than consistently broken.
   Moving ours removes the race without touching the other project. */
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8010";

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

export type Topology = { nodes: Node[]; edges: Edge[] };

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

export type Comparison = {
  goal: string;
  region: string;
  sizing_basis: string;
  clouds: Record<string, Option[]>;
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

async function del<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE}${path}`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error(`DELETE ${path} failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function post<T>(path: string, body: Record<string, unknown>): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    next: { revalidate: 300 },
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new ApiError(detail.detail ?? `POST ${path} failed`, response.status);
  }
  return response.json();
}

/** Tiers arrive in reading order; the union keeps the renderer honest. */
export type Tier =
  | "edge" | "api" | "compute" | "data" | "async"
  | "analytics" | "ml" | "security" | "cicd" | "observability";

export type Flow = "sync" | "async" | "replication" | "control";

export type ArchNode = {
  id: string;
  label: string;
  tier: Tier;
  purpose: string;
  priced: boolean;
  /** null when the catalog cannot price it — which is not the same as free. */
  monthly_usd: number | null;
  sku: string | null;
  x: number; y: number; w: number; h: number;
};

export type ArchEdge = {
  source: string;
  target: string;
  flow: Flow;
  /** Already routed server-side, so the client draws rather than decides. */
  points: { x: number; y: number }[];
};

export type ArchGroup = {
  id: string;
  kind: "account" | "region" | "az" | "vpc" | "subnet";
  label: string;
  depth: number;
  x: number; y: number; w: number; h: number;
};

export type ArchitectureView = {
  canvas: { width: number; height: number };
  regions: number;
  azs_per_region: number;
  external: string[];
  counts: { services: number; edges: number; groups: number; priced: number };
  bands: { tier: Tier; y: number; h: number }[];
  groups: ArchGroup[];
  nodes: ArchNode[];
  edges: ArchEdge[];
};

export type SavedArchitecture = {
  id: string;
  title: string;
  description: string;
  services: number;
  regions: number;
  created_at: string;
};

export type Provenance = {
  total: number;
  split: Record<string, number>;
};

export const api = {
  health: () => get<Health>("/health", 60),

  provenance: () => get<Provenance>("/provenance", 300),

  catalog: (params: Record<string, string | number> = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).map(([k, v]) => [k, String(v)]),
    );
    return get<Catalog>(`/catalog?${query}`);
  },

  techniques: () => get<{ count: number; techniques: Technique[] }>("/techniques"),
  /* Sixty seconds, not an hour. This list is derived from what the catalog
     holds, so it changes the moment a region is ingested -- caching it for an
     hour meant the switcher kept offering two regions while the service had
     four, which looks like the control is broken rather than stale. */
  regions: () => get<Record<string, Record<string, string>>>("/regions", 60),

  recommend: (body: Record<string, unknown>) =>
    post<Recommendation>("/recommend", body),

  /** The same requirement priced on every cloud. */
  compare: (body: Record<string, unknown>) => post<Comparison>("/compare", body),

  architecture: (body: Record<string, unknown>) =>
    post<ArchitectureView>("/architecture", body),

  saveArchitecture: (body: Record<string, unknown>) =>
    post<SavedArchitecture>("/architecture/save", body),

  savedArchitectures: (owner: string) =>
    get<{ saved: SavedArchitecture[] }>(
      `/architecture/saved?owner=${encodeURIComponent(owner)}`,
      0,
    ),

  deleteArchitecture: (id: string, owner: string) =>
    del<{ deleted: boolean }>(
      `/architecture/saved/${id}?owner=${encodeURIComponent(owner)}`,
    ),
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
