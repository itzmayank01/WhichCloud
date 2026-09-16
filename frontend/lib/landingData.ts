import { cache } from "react";

import { api, type Comparison, type Recommendation } from "@/lib/api";

/**
 * The landing page's demo queries, fetched once per render.
 *
 * Five components asked for the same priced architecture and three for the
 * same comparison, each calling the API directly with an identical body.
 * Next.js memoises `fetch` per render for GET, but NOT for POST -- and these
 * are POSTs -- so all eight went to the backend. The backend runs one worker
 * on its current tier, so they did not even overlap: `/recommend` measures
 * ~14.5s there, and the page waited for them end to end. Time to first byte
 * stayed fast because the shell streams, which is why this showed up as
 * panels sitting empty for a minute rather than as a slow-loading page.
 *
 * `cache` from React collapses the identical calls within one render to a
 * single in-flight request, so the page makes three backend calls instead of
 * eight. The `revalidate` argument still does the across-request caching; this
 * is only about not asking the same question eight times in one render.
 *
 * Call these rather than `api.recommend`/`api.compare` from anything on the
 * landing page -- a direct call is a fresh request and silently opts out.
 */

/** The workload the demo cards price. One object, so every caller is
 *  provably asking the same question -- `cache` keys on the arguments, and
 *  two objects that merely look alike would miss. */
export const SHOP_WORKLOAD = {
  goal: "an online shop",
  workload_type: "web",
  traffic_pattern: "spiky",
  traffic_scale: "medium",
  storage_gb: 200,
  egress_gb: 500,
} as const;

/** Cached: the landing page asks this same fixed question on every visit, so
 *  one engine run per five minutes serves everyone. */
const REVALIDATE_S = 300;

export const shopRecommendation = cache(
  (): Promise<Recommendation> => api.recommend({ ...SHOP_WORKLOAD }, REVALIDATE_S),
);

export const shopComparison = cache(
  (): Promise<Comparison> => api.compare({ ...SHOP_WORKLOAD }, REVALIDATE_S),
);
