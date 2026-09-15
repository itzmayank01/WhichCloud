/**
 * Next.js wraps page.tsx's async work in Suspense automatically when a
 * sibling loading.tsx exists -- this is that boundary. Without it, the
 * catalog fetch in page.tsx (a server-side await, not client-side) left the
 * whole page blank until it resolved, which is a fast no-op locally but a
 * real, visible stall against a cold-started backend (Render's free tier
 * sleeps after 15 min idle; the first request after that can take 30-60s).
 * A stalled fetch and a broken one look identical without this -- both were
 * just an empty box.
 */
export default function Loading() {
  return (
    <div className="mx-auto max-w-6xl px-6 py-14">
      <div className="font-mono text-[13.5px] uppercase tracking-[0.14em] text-accent font-medium">
        Price index
      </div>
      <h1 className="mt-3 text-balance text-[clamp(2rem,4.5vw,3rem)] font-semibold leading-[1.06] tracking-[-0.03em]">
        Every machine, and what it costs
      </h1>
      <p className="mt-4 max-w-2xl text-[17px] leading-relaxed text-ink-2">
        The catalog the rest of the site prices against. These are the
        providers&apos; own published on-demand rates, not estimates and not
        marked up. Search it, sort it, check any row against the provider.
      </p>

      <div className="mt-10 flex min-h-[320px] flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-line-strong bg-canvas p-10 text-center">
        <div
          className="h-8 w-8 animate-spin rounded-full border-2 border-accent/25 border-t-accent"
          aria-hidden
        />
        <p className="font-mono text-[14px] font-medium text-ink-3">
          Fetching the price catalog…
        </p>
      </div>
    </div>
  );
}
