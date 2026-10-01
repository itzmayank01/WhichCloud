"use client";

import { useCallback, useEffect, useState } from "react";
import { HeroShowcase, type ShowcaseData } from "@/components/landing/HeroShowcase";
import { ShimmerBlock } from "@/components/ui/ShimmerBlock";

//: Render's free tier sleeps the backend after 15 minutes idle; the first
//: request after that wakes it, which the client already retries through
//: (see fetchThroughWake in lib/api.ts) but can still take the better part
//: of a minute. Said here rather than left silent, same reasoning as the
//: AWS connect page's identical wait.
const SLOW_HINT_DELAY_MS = 6000;

function Skeleton({ slow }: { slow: boolean }) {
  return (
    <div className="space-y-4">
      <ShimmerBlock height={300} />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <ShimmerBlock height={200} />
        <ShimmerBlock height={200} />
      </div>
      {slow && (
        <p className="text-center text-[12.5px] text-ink-3">
          Waking up the pricing engine&hellip; first load after a few idle
          minutes can take up to a minute.
        </p>
      )}
    </div>
  );
}

function LoadError({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-line bg-canvas px-6 py-10 text-center">
      <p className="text-[13.5px] text-ink-2">
        Couldn&apos;t load the live example. The pricing engine may still be
        waking up, or the request timed out.
      </p>
      <button
        onClick={onRetry}
        className="rounded-lg border border-line bg-surface px-3 py-1.5 text-[12.5px] font-medium text-ink-2 hover:bg-sunk hover:text-ink"
      >
        Retry
      </button>
    </div>
  );
}

/**
 * Fills the hero showcase from one same-origin, edge-cached request.
 *
 * The comparison, the reduction and the catalog counts all happen in
 * app/api/landing/showcase/route.ts now. This component used to do that
 * work itself, from the browser, on every page view: three cross-origin
 * calls (each POST preceded by a CORS preflight), ~270 KB of comparison
 * JSON reduced on the visitor's CPU to the few dozen numbers the panel
 * shows, and none of it cached -- `next: { revalidate }` is a server-side
 * fetch option the browser ignores, and a POST is never served from the
 * HTTP cache regardless. See that route's docstring for the full account.
 */
export function HeroShowcaseSection() {
  const [data, setData] = useState<ShowcaseData | null>(null);
  const [failed, setFailed] = useState(false);
  const [slow, setSlow] = useState(false);
  // Bumped to re-run the effect below from the retry button, without
  // duplicating the fetch logic in two places.
  const [attempt, setAttempt] = useState(0);

  const retry = useCallback(() => {
    setFailed(false);
    setSlow(false);
    setAttempt((n) => n + 1);
  }, []);

  useEffect(() => {
    // `failed`/`slow` are reset by retry() before it bumps `attempt`, so the
    // initial mount (where both already default to false) needs no reset.
    const slowTimer = setTimeout(() => setSlow(true), SLOW_HINT_DELAY_MS);
    // Abandoned rather than applied if this effect is torn down -- a retry,
    // or the visitor leaving -- instead of setting state on a dead component.
    let live = true;

    fetch("/api/landing/showcase")
      .then((res) => {
        if (!res.ok) throw new Error(`showcase ${res.status}`);
        return res.json() as Promise<ShowcaseData>;
      })
      .then((showcase) => {
        if (live) setData(showcase);
      })
      .catch(() => {
        if (live) setFailed(true);
      })
      .finally(() => clearTimeout(slowTimer));

    return () => {
      live = false;
      clearTimeout(slowTimer);
    };
  }, [attempt]);

  if (data) return <HeroShowcase data={data} />;
  if (failed) return <LoadError onRetry={retry} />;
  return <Skeleton slow={slow} />;
}
