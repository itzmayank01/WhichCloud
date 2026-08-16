"use client";

import { Icon } from "@iconify/react";
import { useEffect, useRef, useState } from "react";

/**
 * The product, as three overlapping panels.
 *
 * Modelled on the dashboard shot this kind of page opens with: one panel each
 * side, a larger one floating across both. What they carry is different,
 * because the panels it is modelled on read a connected billing account --
 * accrued spend, savings realised, a Fix button that changes your
 * infrastructure. There is no billing connection here and there is not meant
 * to be; this prices a plan before it exists.
 *
 *   left    the same workload on each cloud, stacked by service
 *   centre  the estimate, itemised, floating over the other two
 *   right   the savings it measured, each against the SKU it beat
 *
 * Every figure is passed in from the engine. The sequence runs once when the
 * section is scrolled to.
 */

export type ShowcaseData = {
  chart: {
    clouds: {
      id: string;
      label: string;
      total: number;
      segments: { label: string; value: number }[];
    }[];
    categories: string[];
  };
  quote: string;
  breakdown: { label: string; sku: string; monthly: number }[];
  total: number;
  saved: number;
  techniquesTested: number;
  applied: { name: string; saved: number; versus: string; category: string }[];
};

const LOGO: Record<string, string> = {
  aws: "logos:aws",
  azure: "logos:microsoft-azure",
  gcp: "logos:google-cloud",
};

/* A light palette, assigned by size: the biggest line on the bill always gets
   the first colour, so the same band means the same thing across all three
   bars. Kept pale on purpose -- these are large filled areas, and saturated
   blocks at this size fight the figures they are supposed to support. Held in
   one place so the chart, its legend and the itemised list cannot drift
   apart. */
const RAMP = [
  "#9cc4ef",
  "#f0c489",
  "#eda6c8",
  "#a6d9cd",
  "#c3b7ee",
  "#bcdda6",
  "#dcdee4",
];
const fallbackColor = "#c3cad6";

const CAT_ICON: Record<string, string> = {
  compute: "M7 7h10v10H7zM9 3v2m6-2v2M9 19v2m6-2v2M3 9h2m-2 6h2m14-6h2m-2 6h2",
  database: "M21 6c0 1.66-4 3-9 3S3 7.66 3 6s4-3 9-3 9 1.34 9 3zM3 6v12c0 1.66 4 3 9 3s9-1.34 9-3V6",
  network: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM3.6 9h16.8M3.6 15h16.8",
  storage: "M4 4h16v6H4zM4 14h16v6H4z",
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
    /* The panels start collapsed, so whatever triggers them is load-bearing:
       a trigger that never fires leaves three empty boxes. The timer
       guarantees they arrive and the observer only makes it sooner. */
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
        { threshold: 0.1 },
      );
      io.observe(el);
    }
    return () => {
      io?.disconnect();
      window.clearTimeout(fallback);
    };
  }, []);

  /* Rank the services by what they cost across every cloud, then hand out
     the ramp in that order, so the darkest band is always the largest line on
     the bill wherever it appears. */
  const rank = new Map<string, number>();
  [...data.chart.categories]
    .sort((a, b) => {
      const sum = (label: string) =>
        data.chart.clouds.reduce(
          (t, c) => t + (c.segments.find((s) => s.label === label)?.value ?? 0),
          0,
        );
      return sum(b) - sum(a);
    })
    .forEach((label, i) => rank.set(label, i));
  const colorFor = (label: string) => RAMP[rank.get(label) ?? 99] ?? fallbackColor;

  const peak = Math.max(...data.chart.clouds.map((c) => c.total), 1);
  /* The bars are flex items. Without shrink-0 flexbox compresses them to fit
     the column, which flattens the difference between the clouds -- the
     inline heights stayed correct while every bar rendered the same size, so
     the chart quietly stopped showing its own data. The room left for the
     label above and the logo below is subtracted rather than guessed at. */
  const CHART_H = 150;
  const BAR_MAX = CHART_H - 46;

  return (
    <div ref={host} className="relative mx-auto max-w-6xl">
      {/* The three sit in one grid row and overlap by column, so the centre
          panel crosses both neighbours instead of sitting between them. */}
      <div className="grid gap-4 lg:grid-cols-12 lg:gap-0">
        {/* ── left: what it costs on each cloud ── */}
        <Card
          shown={shown}
          delay={0}
          z={0}
          className="lg:col-start-1 lg:col-span-6 lg:row-start-1 lg:mt-14"
          icon="chart"
          eyebrow="Cost report"
          title="Costs by provider and service"
        >
          <div className="flex items-baseline gap-2.5">
            <span className="tnum font-mono text-[28px] font-semibold leading-none">
              {money(data.total, 2)}
            </span>
            <span className="rounded bg-save/10 px-1.5 py-0.5 font-mono text-[11.5px] font-semibold text-save">
              −{money(data.saved, 2)}
            </span>
          </div>
          <p className="mt-1 text-[12.5px] text-ink-3">
            Cheapest complete option, per month
          </p>

          {/* legend */}
          <div className="mt-4 flex flex-wrap gap-x-3 gap-y-1.5">
            {data.chart.categories.map((c) => (
              <span
                key={c}
                className="inline-flex items-center gap-1.5 text-[11.5px] text-ink-2"
              >
                <span
                  className="h-2 w-2 rounded-[2px]"
                  style={{ background: colorFor(c) }}
                />
                {c}
              </span>
            ))}
          </div>

          {/* stacked bars, one per cloud, over a ruled grid */}
          <div className="relative mt-4 flex" style={{ height: CHART_H }}>
            {/* the axis, and the lines it labels */}
            <div className="relative w-11 shrink-0">
              {[1, 0.5, 0].map((f) => (
                <span
                  key={f}
                  className="absolute right-1.5 -translate-y-1/2 font-mono text-[10px] text-ink-3"
                  style={{ top: `${(1 - f) * BAR_MAX + 20}px` }}
                >
                  ${Math.round((peak * f) / 10) * 10}
                </span>
              ))}
            </div>
            <div className="relative flex-1">
              {[1, 0.5, 0].map((f) => (
                <span
                  key={f}
                  aria-hidden
                  className="absolute inset-x-0 border-t border-dashed border-line"
                  style={{ top: `${(1 - f) * BAR_MAX + 20}px` }}
                />
              ))}
              <div className="relative flex h-full items-end justify-around gap-6">
            {data.chart.clouds.map((cloud, ci) => (
              <div key={cloud.id} className="flex h-full flex-1 flex-col items-center justify-end">
                <span className="tnum mb-1.5 font-mono text-[12px] font-semibold text-ink">
                  {money(cloud.total)}
                </span>
                <div
                  className="flex w-full max-w-[54px] shrink-0 flex-col-reverse overflow-hidden rounded-md transition-[height] duration-[900ms] ease-out"
                  style={{
                    height: shown ? `${(cloud.total / peak) * BAR_MAX}px` : "0px",
                    transitionDelay: `${260 + ci * 120}ms`,
                  }}
                >
                  {cloud.segments.map((s) => (
                    <span
                      key={s.label}
                      title={`${s.label} ${money(s.value, 2)}`}
                      style={{
                        height: `${(s.value / cloud.total) * 100}%`,
                        background: colorFor(s.label),
                      }}
                    />
                  ))}
                </div>
                <span className="mt-2 inline-flex items-center gap-1.5">
                  <Icon icon={LOGO[cloud.id] ?? LOGO.aws} width={13} height={13} aria-hidden />
                  <span className="text-[11.5px] text-ink-3">{cloud.label}</span>
                </span>
              </div>
            ))}
              </div>
            </div>
          </div>
        </Card>

        {/* ── centre: the estimate, floating across both ── */}
        <div
          className={`relative hover:z-30 lg:col-start-4 lg:col-span-5 lg:row-start-1 lg:z-20 transition-all duration-[750ms] ease-out ${
            shown ? "translate-y-0 opacity-100" : "translate-y-5 opacity-0"
          }`}
          style={{ transitionDelay: "140ms" }}
        >
          <div className="rounded-2xl border border-line bg-surface elev-4">
            <div className="flex items-center gap-2.5 border-b border-line px-5 py-3.5">
              <span className="grid h-8 w-8 place-items-center rounded-lg bg-accent">
                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
              </span>
              <span className="flex-1 text-[15px] font-semibold">Your estimate</span>
              <span className="font-mono text-[11.5px] text-ink-3">india</span>
            </div>

            <div className="px-5 py-4">
              <p className="text-[13.5px] leading-relaxed text-ink-2">
                You described{" "}
                <span className="font-mono text-[13px] text-ink">“{data.quote}”</span>.
                Here is what that costs, service by service.
              </p>

              <table className="mt-4 w-full border-collapse">
                <thead>
                  <tr className="border-b border-line text-[11px] uppercase tracking-[0.07em] text-ink-3">
                    <th className="pb-1.5 text-left font-medium">Service</th>
                    <th className="pb-1.5 text-left font-medium">What it runs</th>
                    <th className="pb-1.5 text-right font-medium">Monthly</th>
                  </tr>
                </thead>
                <tbody>
                  {data.breakdown.map((b, i) => (
                    <tr
                      key={b.label}
                      className={`border-b border-line last:border-0 transition-all duration-500 ${
                        shown ? "translate-x-0 opacity-100" : "translate-x-2 opacity-0"
                      }`}
                      style={{ transitionDelay: `${460 + i * 90}ms` }}
                    >
                      <td className="py-2 text-[13px]">
                        <span className="inline-flex items-center gap-2">
                          <span
                            className="h-2 w-2 shrink-0 rounded-[2px]"
                            style={{ background: colorFor(b.label) }}
                          />
                          <span className="text-ink-2">{b.label}</span>
                        </span>
                      </td>
                      <td className="py-2 font-mono text-[12px] text-ink-3">{b.sku}</td>
                      <td className="tnum py-2 text-right font-mono text-[13px] font-semibold text-ink">
                        {money(b.monthly, 2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div className="mt-3 flex items-baseline justify-between border-t border-line pt-3">
                <span className="text-[13px] text-ink-2">Every month</span>
                <span className="tnum font-mono text-[20px] font-semibold">
                  {money(data.total, 2)}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* ── right: what it saved ── */}
        <Card
          shown={shown}
          delay={280}
          z={10}
          className="lg:col-start-9 lg:col-span-4 lg:row-start-1 lg:mt-24"
          icon="save"
          eyebrow="Measured savings"
          title="Ways to pay less"
        >
          <div className="flex items-baseline gap-2">
            <span className="tnum font-mono text-[24px] font-semibold leading-none text-save">
              −{money(data.saved, 2)}
            </span>
            <span className="text-[12.5px] text-ink-2">a month</span>
          </div>

          <div className="mt-4 space-y-3">
            {data.applied.map((a, i) => (
              <div
                key={a.name}
                className={`flex items-start gap-2 transition-all duration-500 ${
                  shown ? "translate-x-0 opacity-100" : "translate-x-3 opacity-0"
                }`}
                style={{ transitionDelay: `${620 + i * 140}ms` }}
              >
                <svg viewBox="0 0 24 24" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <path d={CAT_ICON[a.category] ?? CAT_ICON.compute} />
                </svg>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[12.5px] font-medium text-ink">{a.name}</p>
                  {/* Naming what it beat is what makes the figure beside it a
                      measurement rather than a claim. */}
                  <p className="mt-0.5 truncate font-mono text-[11px] text-ink-3">
                    vs {a.versus}
                  </p>
                </div>
                <span className="tnum shrink-0 font-mono text-[12.5px] font-semibold text-save">
                  −{money(a.saved, 2)}
                </span>
              </div>
            ))}
          </div>

          {/* The ones that did not apply are part of the answer: a tool that
              only ever reports wins is not measuring anything. */}
          <p className="mt-4 border-t border-line pt-3 font-mono text-[11px] text-ink-3">
            {data.techniquesTested} tested · {data.applied.length} applied
          </p>
        </Card>
      </div>
    </div>
  );
}

const HEAD_ICON: Record<string, string> = {
  chart: "M3 3v18h18M7 15l3.5-3.5 3 3L20 8",
  save: "M12 1v22M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6",
};

function Card({
  children,
  shown,
  delay,
  z,
  className = "",
  icon,
  eyebrow,
  title,
}: {
  children: React.ReactNode;
  shown: boolean;
  delay: number;
  z: number;
  className?: string;
  icon: keyof typeof HEAD_ICON;
  eyebrow: string;
  title: string;
}) {
  return (
    /* hover:z-30 lets whichever panel you point at come to the front, so an
       overlap never hides something you are trying to read. */
    <div
      className={`${className} group relative transition-all duration-[750ms] ease-out hover:z-30 ${
        shown ? "translate-y-0 opacity-100" : "translate-y-5 opacity-0"
      }`}
      style={{ transitionDelay: `${delay}ms`, zIndex: z }}
    >
      <div className="rounded-2xl border border-line bg-surface elev-2 transition-shadow duration-200 group-hover:elev-4">
        <div className="flex items-center gap-2.5 border-b border-line px-4 py-3">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-sunk">
            <svg viewBox="0 0 24 24" className="h-4 w-4 text-ink-2" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d={HEAD_ICON[icon]} />
            </svg>
          </span>
          <div className="min-w-0">
            <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-ink-3">
              {eyebrow}
            </p>
            <p className="truncate text-[14.5px] font-semibold">{title}</p>
          </div>
        </div>
        <div className="px-4 py-4">{children}</div>
      </div>
    </div>
  );
}
