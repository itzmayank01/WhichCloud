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
  /** The option as a laid-out, priced AWS architecture. Null on other clouds
      until a service-equivalence table exists. */
  drawn: ArchitectureView | null;
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
  /** What the budget was read as, so the interface can say what is unspent. */
  budget_monthly_usd: number | null;
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

/**
 * `revalidate` is opt-in, and the default is deliberately not to cache.
 *
 * These POSTs run the engine against the live price catalog, so a cached
 * response keeps showing an architecture the catalog no longer produces --
 * resubmitting the same description replayed a five-minute-old answer and
 * looked like the engine had stopped responding to changes. Anything a
 * person just typed must be fresh.
 *
 * The landing page is the exception that earns the parameter: its demo
 * cards ask the same fixed question on every visit, so caching them is
 * both correct and the difference between one engine run per five minutes
 * and one per page view.
 */
async function post<T>(
  path: string,
  body: Record<string, unknown>,
  revalidate?: number,
): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    ...(revalidate === undefined
      ? { cache: "no-store" as const }
      : { next: { revalidate } }),
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
  /** Position in the request path; null for links that are not on it. */
  step: number | null;
  /** Where the step number goes — placed server-side so both renderers agree. */
  badge: { x: number; y: number } | null;
  /** Already routed server-side, so the client draws rather than decides. */
  points: { x: number; y: number }[];
};

export type ArchFrame = {
  label: string;
  x: number; y: number; w: number; h: number;
};

export type ArchGroup = {
  id: string;
  kind: "account" | "region" | "az" | "vpc" | "subnet";
  label: string;
  depth: number;
  x: number; y: number; w: number; h: number;
};

export type ArchComponent = {
  name: string;
  x: number; y: number; w: number; h: number;
};

export type ArchitectureView = {
  canvas: { width: number; height: number };
  regions: number;
  azs_per_region: number;
  external: string[];
  counts: { services: number; edges: number; groups: number; priced: number };
  bands: { tier: Tier; y: number; h: number }[];
  components: ArchComponent[];
  cloud: ArchFrame | null;
  actor: ArchFrame | null;
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


/* ── the reasoning layer's contract ──
   Distinct from Recommendation: this shape carries what was ruled OUT and
   why, which is the part a reader cannot reconstruct from a price table. */
export type SizingBasis = {
  avg_rps: number;
  peak_rps: number;
  tier: "trivial" | "small" | "medium" | "large";
  sized_from: string;
};

export type PlanComponent = {
  label: string;
  sku: string;
  unit: string;
  monthly_usd: number;
};

export type PlanTier = {
  name: string;
  label: string;
  philosophy: string;
  monthly_total: number;
  within_budget: boolean;
  rto: string;
  rpo: string;
  region_rto: string;
  region_rpo: string;
  gives_up: string[];
  justifications: Record<string, string>;
  pattern_diff_vs_previous_tier: string[];
  no_further_improvement: string;
  warnings: string[];
  committed_use_note: string;
  components: PlanComponent[];
  complete: boolean;
  missing: string[];
};

export type ComplianceNote = {
  regulation: string;
  obligation: string;
  control: string;
};

export type AssumedField = {
  field: string;
  assumption: string | number | boolean;
  question: string;
};

export type Plan = {
  sizing_basis: SizingBasis;
  excluded_with_reason: string[];
  tiers: PlanTier[];
  default_tier: string;
  below_requirements_panel: {
    label: string;
    violations: string[];
    note: string;
  } | null;
  compliance_notes: ComplianceNote[];
  assumed_fields: AssumedField[];
  stated_fields: Record<string, string>;
  unspent_budget: { amount_usd: number; note: string } | null;
  over_budget_note: string;
  network_topology: string;
  network_topology_reason: string;
  archetype: string;
  archetype_note: string;
  /** priced | recognised_unpriced | unknown */
  archetype_state: string;
  archetype_requirements: string;
  coverage_summary: { shapes_recognised: number; shapes_priced: number };
  /** False means pricing was withheld by decision — `tiers` is empty on
   *  purpose, not because the request failed. */
  priced: boolean;
  withheld_reason: string;
  covered_archetypes: { archetype: string; description: string; status: string }[];
  clarifying_questions: string[];
  provisional: boolean;
  provisional_reasons: string[];
  extraction_confidence: Record<string, string>;
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

  recommend: (body: Record<string, unknown>, revalidate?: number) =>
    post<Recommendation>("/recommend", body, revalidate),

  /** The same requirement priced on every cloud. */
  compare: (body: Record<string, unknown>, revalidate?: number) =>
    post<Comparison>("/compare", body, revalidate),

  /** Plain English straight through to three priced options. */
  /* No cache. A plan is the answer to one description; serving a stale one
     for a different description is the failure this whole layer exists to
     avoid. */
  plan: (body: Record<string, unknown>) => post<Plan>("/plan", body),

  describe: (body: Record<string, unknown>) =>
    post<Recommendation>("/describe", body),

  architecture: (body: Record<string, unknown>) =>
    post<ArchitectureView>("/architecture", body),

  /** The diagram as a file. Returns the SVG source, not a parsed object. */
  architectureSvg: async (body: Record<string, unknown>): Promise<string> => {
    const response = await fetch(`${BASE}/architecture/export.svg`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error(`export failed: ${response.status}`);
    return response.text();
  },

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

/**
 * Per-cloud totals over only the services every cloud prices.
 *
 * A cross-cloud comparison is only meaningful when both sides cover the
 * same ground. AWS prices twenty-one components; Azure and GCP have
 * adapters for seven, so their raw totals are lower for a reason that has
 * nothing to do with being cheaper. Ranking those raw figures put "$336"
 * above "$649" and called it the winner, which is the opposite of true.
 *
 * This sums each cloud over the intersection of the line items they all
 * price, so the numbers answer one question: for the same set of services,
 * who charges less. `covered` says how many that was, so the interface can
 * state what the comparison actually covered rather than implying it is
 * the whole bill.
 */
export function comparableTotals(
  clouds: Record<string, Option[]>,
  label = "Most reliable",
): { provider: string; option: Option; total: number; covered: number }[] {
  const base = (item: LineItem) => item.label.replace(/ ×.*$/, "");

  const picked = Object.entries(clouds)
    .map(([provider, options]) => ({
      provider,
      option: options.find((o) => o.label === label) ?? options[0],
    }))
    .filter((r) => r.option && r.option.items.length > 0);

  if (picked.length < 2) return [];

  const shared = picked
    .map((r) => new Set(r.option.items.map(base)))
    .reduce((a, b) => new Set([...a].filter((x) => b.has(x))));

  if (shared.size === 0) return [];

  return picked
    .map((r) => ({
      provider: r.provider,
      option: r.option,
      total: r.option.items
        .filter((i) => shared.has(base(i)))
        .reduce((sum, i) => sum + i.monthly_usd, 0),
      covered: shared.size,
    }))
    .sort((a, b) => a.total - b.total);
}
