"use client";

import { Icon } from "@iconify/react";
import { useEffect, useRef, useState } from "react";

/**
 * The product, as three overlapping panels.
 *
 * Modelled on the dashboard shot this kind of page usually opens with, but
 * showing what WhichCloud actually does. The panels it was modelled on read a
 * connected billing account -- accrued spend, savings realised, a Fix button
 * that changes your infrastructure. There is no billing connection here and
 * deliberately so: this tool prices a plan before it exists. So the same three
 * shapes carry the things it can honestly show.
 *
 *   left    what the same workload costs on each cloud
 *   centre  the estimate, floating over the other two
 *   right   the savings it measured, and the SKU each one beat
 *
 * Every figure is passed in from the engine.
 */

export type ShowcaseData = {
  providers: { id: string; label: string; monthly: number; cheapest: boolean }[];
  breakdown: { label: string; monthly: number }[];
  total: number;
  saved: number;
  applied: { name: string; saved: number; versus: string; category: string }[];
};

const LOGO: Record<string, string> = {
  aws: "logos:aws",
  azure: "logos:microsoft-azure",
  gcp: "logos:google-cloud",
};

const CAT_ICON: Record<string, string> = {
  compute: "M9 3v2m6-2v2M9 19v2m6-2v2M3 9h2m-2 6h2m14-6h2m-2 6h2M7 7h10v10H7z",
  database: "M21 6c0 1.66-4 3-9 3S3 7.66 3 6s4-3 9-3 9 1.34 9 3zM3 6v12c0 1.66 4 3 9 3s9-1.34 9-3V6",
  network: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM3.6 9h16.8M3.6 15h16.8",
  storage: "M4 4h16v6H4zM4 14h16v6H4zM7 7h.01M7 17h.01",
};

const money = (n: number, dp = 0) =>
  `$${n.toLocaleString(undefined, { minimumFractionDigits: dp, maximumFractionDigits: dp })}`;

export function HeroShowcase({ data }: { data: ShowcaseData }) {
  const [shown, setShown] = useState(false);
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setShown(true);
      return;
    }
    /* Same rule as everywhere else here: the panels start collapsed, so a
       trigger that never fires would leave empty boxes. The timer guarantees
       they arrive; the observer only makes it happen sooner. */
    const fallback = window.setTimeout(() => setShown(true), 1200);
    let io: IntersectionObserver | undefined;
    if (typeof IntersectionObserver !== "undefined") {
      io = new IntersectionObserver(
        (e) => {
          if (e.some((x) => x.isIntersecting)) {
            window.clearTimeout(fallback);
            io?.disconnect();
            setShown(true);
          }
        },
        { threshold: 0.15 },
      );
      io.observe(el);
    }
    return () => {
      io?.disconnect();
      window.clearTimeout(fallback);
    };
  }, []);

  const maxProvider = Math.max(...data.providers.map((p) => p.monthly), 1);
  const maxLine = Math.max(...data.breakdown.map((b) => b.monthly), 1);

  return (
    <div ref={host} className="relative mx-auto max-w-6xl">
      <div className="grid items-start gap-4 lg:grid-cols-12">
        {/* ── left: the same workload on each cloud ── */}
        <Panel
          shown={shown}
          delay={0}
          className="lg:col-span-5 lg:mt-10"
          eyebrow="Price comparison"
          title="The same app, on each cloud"
        >
          <div className="flex items-baseline gap-2.5">
            <span className="tnum font-mono text-[26px] font-semibold leading-none">
              {money(data.total)}
            </span>
            <span className="rounded bg-save/10 px-1.5 py-0.5 font-mono text-[11.5px] font-semibold text-save">
              −{money(data.saved)}/mo
            </span>
          </div>
          <p className="mt-1 text-[12.5px] text-ink-3">
            Cheapest complete option, after optimizations
          </p>

          <div className="mt-4 space-y-2.5">
            {data.providers.map((p, i) => (
              <div key={p.id}>
                <div className="flex items-center justify-between text-[13px]">
                  <span className="inline-flex items-center gap-1.5">
                    <Icon icon={LOGO[p.id] ?? LOGO.aws} width={14} height={14} aria-hidden />
                    <span className="text-ink-2">{p.label}</span>
                  </span>
                  <span
                    className={`tnum font-mono text-[13px] font-semibold ${
                      p.cheapest ? "text-save" : "text-ink"
                    }`}
                  >
                    {money(p.monthly)}
                  </span>
                </div>
                <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-sunk">
                  <span
                    className="block h-full rounded-full transition-[width] duration-[900ms] ease-out"
                    style={{
                      width: shown ? `${(p.monthly / maxProvider) * 100}%` : "0%",
                      transitionDelay: `${240 + i * 130}ms`,
                      background: p.cheapest ? "var(--save)" : "var(--accent)",
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Panel>

        {/* ── centre: the estimate, floating ── */}
        <div
          className={`lg:col-span-4 lg:z-20 transition-all duration-[700ms] ease-out ${
            shown ? "translate-y-0 opacity-100" : "translate-y-4 opacity-0"
          }`}
          style={{ transitionDelay: "120ms" }}
        >
          <div className="rounded-2xl border border-line bg-surface elev-4">
            <div className="flex items-center gap-2.5 border-b border-line px-4 py-3">
              <span className="grid h-7 w-7 place-items-center rounded-lg bg-accent">
                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
              </span>
              <span className="text-[14.5px] font-semibold">Your estimate</span>
            </div>

            <div className="px-4 py-4">
              <p className="rounded-lg bg-sunk px-3 py-2 font-mono text-[12.5px] leading-relaxed text-ink-2">
                “an online shop for India, traffic comes in spikes”
              </p>

              <div className="mt-4 space-y-2">
                {data.breakdown.map((b, i) => (
                  <div key={b.label} className="flex items-center gap-2.5">
                    <span className="w-[86px] shrink-0 truncate text-[12.5px] text-ink-3">
                      {b.label}
                    </span>
                    <span className="h-2 flex-1 overflow-hidden rounded-full bg-sunk">
                      <span
                        className="block h-full rounded-full bg-accent transition-[width] duration-[900ms] ease-out"
                        style={{
                          width: shown ? `${(b.monthly / maxLine) * 100}%` : "0%",
                          transitionDelay: `${420 + i * 90}ms`,
                        }}
                      />
                    </span>
                    <span className="tnum w-[58px] shrink-0 text-right font-mono text-[12.5px] font-medium text-ink">
                      {money(b.monthly, 2)}
                    </span>
                  </div>
                ))}
              </div>

              <div className="mt-4 flex items-baseline justify-between border-t border-line pt-3">
                <span className="text-[13px] text-ink-2">Every month</span>
                <span className="tnum font-mono text-[18px] font-semibold">
                  {money(data.total, 2)}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* ── right: what it saved, and what it beat ── */}
        <Panel
          shown={shown}
          delay={240}
          className="lg:col-span-3 lg:mt-16"
          eyebrow="Measured savings"
          title="Ways to pay less"
        >
          <div className="space-y-3">
            {data.applied.map((a, i) => (
              <div
                key={a.name}
                className={`transition-all duration-500 ${
                  shown ? "translate-x-0 opacity-100" : "translate-x-3 opacity-0"
                }`}
                style={{ transitionDelay: `${520 + i * 140}ms` }}
              >
                <div className="flex items-start gap-2">
                  <svg viewBox="0 0 24 24" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                    <path d={CAT_ICON[a.category] ?? CAT_ICON.compute} />
                  </svg>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-medium text-ink">{a.name}</p>
                    {/* The SKU it beat is the reason the figure beside it is a
                        measurement rather than a claim. */}
                    <p className="mt-0.5 truncate font-mono text-[11.5px] text-ink-3">
                      vs {a.versus}
                    </p>
                  </div>
                  <span className="tnum shrink-0 font-mono text-[13px] font-semibold text-save">
                    −{money(a.saved, 2)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function Panel({
  children,
  shown,
  delay,
  className = "",
  eyebrow,
  title,
}: {
  children: React.ReactNode;
  shown: boolean;
  delay: number;
  className?: string;
  eyebrow: string;
  title: string;
}) {
  return (
    <div
      className={`${className} transition-all duration-[700ms] ease-out ${
        shown ? "translate-y-0 opacity-100" : "translate-y-5 opacity-0"
      }`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      <div className="rounded-2xl border border-line bg-surface elev-2">
        <div className="border-b border-line px-4 py-3">
          <p className="font-mono text-[11.5px] uppercase tracking-[0.1em] text-ink-3">
            {eyebrow}
          </p>
          <p className="mt-0.5 text-[14.5px] font-semibold">{title}</p>
        </div>
        <div className="px-4 py-4">{children}</div>
      </div>
    </div>
  );
}
