"use client";

import { useEffect, useState } from "react";

/**
 * A live indicator for the catalog, showing how recently it was refreshed.
 *
 * The relative label is computed here rather than on the server on purpose.
 * This page is cached for five minutes, so a server-rendered "2 minutes ago"
 * would still read "2 minutes ago" seven minutes later. The server sends the
 * absolute timestamp; the age is worked out in the browser and re-checked
 * every half minute, so the number is true whenever it is read.
 *
 * The dot is red because that is the broadcast convention for live, and a dot
 * cannot be mistaken for a figure. The word stays in ink: red already means
 * money going out everywhere else here, and a red "LIVE" beside red
 * over-budget totals would read as a warning.
 */

function ago(from: number, now: number): string {
  const secs = Math.max(0, Math.round((now - from) / 1000));
  if (secs < 60) return "just now";
  const mins = Math.round(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

/* Past this, the catalog is not "live" in any sense a reader would accept,
   and a pulsing red dot claiming otherwise is the sort of small dishonesty
   that costs you the big claims. */
const LIVE_WINDOW_MS = 24 * 60 * 60 * 1000;

export function LiveBadge({ updatedAt }: { updatedAt: string | null }) {
  const stamp = updatedAt ? Date.parse(updatedAt) : NaN;
  const valid = Number.isFinite(stamp);
  const [label, setLabel] = useState<string | null>(null);
  const [fresh, setFresh] = useState(true);

  useEffect(() => {
    if (!valid) return;
    const tick = () => {
      const now = Date.now();
      setLabel(ago(stamp, now));
      setFresh(now - stamp < LIVE_WINDOW_MS);
    };
    tick();
    const id = window.setInterval(tick, 30_000);
    return () => window.clearInterval(id);
  }, [stamp, valid]);

  return (
    /* A bordered pill rather than a line of loose text: a status indicator is
       a component, and reading as one is what separates it from a caption. */
    <div className="mt-8 flex justify-center">
      <div className="inline-flex items-center gap-3 rounded-full border border-line bg-surface py-1.5 pl-3 pr-3.5 elev-1">
        <span className="inline-flex items-center gap-2">
          <span className="relative flex h-2 w-2" aria-hidden>
            {fresh && (
              <span className="live-ping absolute inline-flex h-full w-full rounded-full bg-[#d64027] opacity-70" />
            )}
            <span
              className={`relative inline-flex h-2 w-2 rounded-full ${
                fresh ? "bg-[#d64027]" : "bg-line-strong"
              }`}
            />
          </span>
          <span
            className={`text-[11.5px] font-semibold uppercase tracking-[0.13em] ${
              fresh ? "text-ink" : "text-ink-3"
            }`}
          >
            {fresh ? "Live" : "Cached"}
          </span>
        </span>

        <span className="h-3.5 w-px bg-line" aria-hidden />

        <span className="font-mono text-[12.5px] font-medium text-ink-2">
          AWS · Azure · Google
        </span>

        {/* Only claims a time when there is one to claim. */}
        {label && (
          <>
            <span className="h-3.5 w-px bg-line" aria-hidden />
            <span
              className="font-mono text-[12.5px] font-medium text-ink-3"
              title={valid ? new Date(stamp).toISOString() : undefined}
            >
              {label}
            </span>
          </>
        )}
      </div>
    </div>
  );
}
