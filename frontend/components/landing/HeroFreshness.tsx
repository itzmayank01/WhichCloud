"use client";

import { useEffect, useState } from "react";
import { LiveBadge } from "@/components/landing/LiveBadge";
import { api } from "@/lib/api";

/**
 * Supplies the live badge with the catalog's real refresh time.
 *
 * Moved to client-side so ISR page generation never waits on /health.
 * The page renders immediately with no timestamp, then hydrates with the real
 * one once it arrives. Much faster than blocking Vercel during a cold start.
 */
export function HeroFreshness() {
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);

  useEffect(() => {
    api
      .health()
      .then((h) => setUpdatedAt(h.last_updated ?? null))
      .catch(() => {
        /* badge renders without the age if /health fails */
      });
  }, []);

  /* Always render. Badge hydrates with timestamp once /health responds. */
  return <LiveBadge updatedAt={updatedAt} />;
}
