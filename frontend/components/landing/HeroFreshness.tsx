import { LiveBadge } from "@/components/landing/LiveBadge";
import { api } from "@/lib/api";

/**
 * Supplies the live badge with the catalog's real refresh time.
 *
 * Kept separate, and suspended in the page, so the hero heading is never
 * waiting on a network call to paint. If /health cannot be reached the badge
 * renders without a timestamp rather than guessing one.
 */
export async function HeroFreshness() {
  let updatedAt: string | null = null;
  try {
    updatedAt = (await api.health()).last_updated ?? null;
  } catch {
    /* badge renders without the age */
  }
  return <LiveBadge updatedAt={updatedAt} />;
}
