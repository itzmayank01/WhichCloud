"use client";

import { useEffect, useState } from "react";

/**
 * How recently the catalog was refreshed, stated and left alone.
 *
 * This was a pill with a pulsing dot in it, which is the single most
 * recognisable ornament on a generated landing page and reads as one. A tool
 * whose argument is that its numbers are real does not need a light flashing
 * beside the claim; it needs the timestamp, which is the part that can be
 * checked. So the line says what it knows in the same voice as everything
 * around it.
 *
 * The age is computed in the browser rather than on the server. This page is
 * cached for five minutes, so a server-rendered "2 minutes ago" would still
 * read "2 minutes ago" seven minutes later. The server sends the absolute
 * stamp; the browser works out the age and re-checks every half minute.
 */

function ago(from: number, now: number): string {
  const secs = Math.max(0, Math.round((now - from) / 1000));
  if (secs < 60) return "just now";
  const mins = Math.round(secs / 60);
  if (mins < 60) return `${mins} minute${mins === 1 ? "" : "s"} ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.round(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

/* Past a day the figures are not current, and the age should say so in the
   colour the rest of the site uses for "check this" rather than slipping by
   in the same grey as everything else. */
const FRESH_WINDOW_MS = 24 * 60 * 60 * 1000;

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
      setFresh(now - stamp < FRESH_WINDOW_MS);
    };
    tick();
    const id = window.setInterval(tick, 30_000);
    return () => window.clearInterval(id);
  }, [stamp, valid]);

  return (
    <p className="mt-7 font-mono text-[14px] font-medium text-ink-3">
      Prices from AWS, Azure and Google
      {/* Only claims a time when there is one to claim. */}
      {label && (
        <>
          {" · "}
          <span
            className={fresh ? "text-ink-2" : "text-caution"}
            title={valid ? new Date(stamp).toISOString() : undefined}
          >
            refreshed {label}
          </span>
        </>
      )}
    </p>
  );
}
