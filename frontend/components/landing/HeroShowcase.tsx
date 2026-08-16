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
  advisory: string[];
};

/** Axis labels. The full names live on the panels that have room for them. */
const SHORT: Record<string, string> = {
  aws: "AWS",
  azure: "Azure",
  gcp: "Google",
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
  /* Re-keys the estimate rows so their entrance animation plays again. The
     panel is meant to look like it is still working rather than like a
     screenshot of a result, and re-costing is the thing it would be doing. */
  const [pass, setPass] = useState(0);
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

  useEffect(() => {
    if (!shown) return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const id = window.setInterval(() => setPass((p) => p + 1), 4400);
    return () => window.clearInterval(id);
  }, [shown]);

  const peak = Math.max(...data.chart.clouds.map((c) => c.total), 1);
  /* The bars are flex items. Without shrink-0 flexbox compresses them to fit
     the column, which flattens the difference between the clouds -- the
     inline heights stayed correct while every bar rendered the same size, so
     the chart quietly stopped showing its own data. The room left for the
     label above and the logo below is subtracted rather than guessed at. */
  const CHART_H = 168;
  const BAR_MAX = CHART_H - 50;

  return (
    <div ref={host} className="relative mx-auto max-w-7xl">
      {/* Widths are stated rather than shared out. flex-1 with basis-0 divides
          the free space equally, and a negative margin *is* free space, so
          the overlap it created was handed back to all three panels and came
          out asymmetric -- 34px on one side, 56px on the other, which meant
          one card gapped on slide and the other did not. Three widths of 36%
          overlapping 4% each side sum to 100% and are symmetric by
          construction. */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-stretch lg:justify-center lg:gap-0">
        {/* ── left: what it costs on each cloud ── */}
        <Card
          shown={shown}
          delay={0}
          zClass="z-0"
          className="lg:w-[36%] lg:min-w-0 lg:shrink-0"
          slide="left"
          icon="chart"
          eyebrow="Cost report"
          title="Costs by provider and service"
        >
          <p className="font-mono text-[10.5px] uppercase tracking-[0.11em] text-ink-3">
            Cheapest complete option
          </p>
          <div className="mt-1.5 flex items-baseline gap-2">
            <span className="tnum font-mono text-[30px] font-semibold leading-none tracking-[-0.02em]">
              {money(data.total, 2)}
            </span>
            <span className="text-[12.5px] text-ink-3">/mo</span>
          </div>
          <p className="mt-1.5 font-mono text-[12px] font-medium text-save">
            −{money(data.saved, 2)} after optimizations
          </p>

          {/* No legend here. Seven services wrapped to two lines in a card
              this wide, and the estimate panel beside it already lists every
              service against its colour -- a second key competing for the
              space the chart needs. */}
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
                {/* Short names on the axis: "Microsoft Azure" wrapped to two
                    lines under a 54px bar and pushed the row out of line. The
                    mark carries the rest. */}
                <span className="mt-2 inline-flex items-center gap-1.5 whitespace-nowrap">
                  <Icon icon={LOGO[cloud.id] ?? LOGO.aws} width={13} height={13} aria-hidden />
                  <span className="text-[11.5px] text-ink-3">{SHORT[cloud.id] ?? cloud.label}</span>
                </span>
              </div>
            ))}
              </div>
            </div>
          </div>

          {/* The totals as figures, under the chart that compares them. A bar
              answers "which is cheaper"; the row answers "by how much", and
              the reference panel carries both for the same reason. */}
          <div className="mt-5 border-t border-line pt-3">
            {data.chart.clouds.map((c, i) => (
              <div
                key={c.id}
                className={`flex items-center justify-between py-1.5 transition-all duration-500 ${
                  shown ? "opacity-100" : "opacity-0"
                }`}
                style={{ transitionDelay: `${560 + i * 90}ms` }}
              >
                <span className="inline-flex items-center gap-2">
                  <span
                    className="h-2 w-2 rounded-[2px]"
                    style={{ background: i === 0 ? "var(--save)" : "var(--border-strong)" }}
                  />
                  <span className="text-[13px] text-ink-2">{c.label}</span>
                </span>
                <span className="flex items-baseline gap-2.5">
                  <span className="tnum font-mono text-[11.5px] text-ink-3">
                    {i === 0
                      ? "cheapest"
                      : `+${money(c.total - data.chart.clouds[0].total)}`}
                  </span>
                  <span
                    className={`tnum font-mono text-[13.5px] font-semibold ${
                      i === 0 ? "text-save" : "text-ink"
                    }`}
                  >
                    {money(c.total, 2)}
                  </span>
                </span>
              </div>
            ))}
          </div>
        </Card>

        {/* ── centre: the estimate, floating across both ── */}
        <div
          className={`relative lg:z-20 lg:-mx-[4%] lg:-my-7 lg:w-[36%] lg:min-w-0 lg:shrink-0 transition-all duration-[750ms] ease-out ${
            shown ? "translate-y-0 opacity-100" : "translate-y-5 opacity-0"
          }`}
          style={{ transitionDelay: "140ms" }}
        >
          <div className="relative flex h-full flex-col overflow-hidden rounded-2xl border border-line bg-surface elev-4">
            {/* One pass of light across the top edge, timed with the rows
                below it, so the panel reads as still working rather than as a
                screenshot of a result. Nothing reflows while it runs. */}
            <span
              aria-hidden
              className="estimate-scan pointer-events-none absolute left-0 top-0 z-10 h-[2px] w-1/3 bg-gradient-to-r from-transparent via-accent to-transparent"
            />
            <div className="flex items-center gap-3 border-b border-line px-5 py-4 sm:px-6">
              <span className="grid h-9 w-9 place-items-center rounded-lg bg-accent">
                <svg viewBox="0 0 24 24" className="h-[18px] w-[18px]" fill="none" stroke="#fff" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                  <path d="M7 9h8M7 13h5" />
                </svg>
              </span>
              <span className="flex-1 text-[15.5px] font-semibold tracking-[-0.015em]">Your estimate</span>
              <span className="font-mono text-[11.5px] text-ink-3">india</span>
            </div>

            <div className="flex flex-1 flex-col px-6 py-5">
              <p className="text-[13.5px] leading-relaxed text-ink-2">
                You described{" "}
                <span className="font-mono text-[13px] text-ink">“{data.quote}”</span>.
                Here is what that costs, service by service.
              </p>

              <table className="mt-4 w-full flex-1 border-collapse">
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
                      key={`${b.label}-${pass}`}
                      className={`border-b border-line last:border-0 ${
                        shown ? "estimate-row" : "opacity-0"
                      }`}
                      style={{ animationDelay: `${i * 110}ms` }}
                    >
                      <td className="py-2.5 text-[13.5px]">
                        <span className="inline-flex items-center gap-2">
                          <span
                            className="h-2 w-2 shrink-0 rounded-[2px]"
                            style={{ background: colorFor(b.label) }}
                          />
                          <span className="text-ink-2">{b.label}</span>
                        </span>
                      </td>
                      <td className="py-2.5 font-mono text-[12.5px] text-ink-3">{b.sku}</td>
                      <td className="tnum py-2.5 text-right font-mono text-[13.5px] font-semibold text-ink">
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
          zClass="z-10"
          className="lg:w-[36%] lg:min-w-0 lg:shrink-0"
          slide="right"
          icon="save"
          eyebrow="Measured savings"
          title="Ways to pay less"
        >
          <p className="font-mono text-[10.5px] uppercase tracking-[0.11em] text-ink-3">
            Measured against what it replaced
          </p>
          <div className="mt-1.5 flex items-baseline gap-2">
            <span className="tnum font-mono text-[30px] font-semibold leading-none tracking-[-0.02em] text-save">
              −{money(data.saved, 2)}
            </span>
            <span className="text-[12.5px] text-ink-3">/mo</span>
          </div>

          <div className="mt-5 flex-1 space-y-3.5">
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
                  <p className="text-[12.5px] font-medium leading-snug text-ink">
                    {a.name}
                  </p>
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

          {data.advisory.length > 0 && (
            <div className="mt-4 border-t border-line pt-3.5">
              <p className="font-mono text-[10.5px] uppercase tracking-[0.11em] text-ink-3">
                Also worth doing, not priceable
              </p>
              <div className="mt-2 space-y-1.5">
                {data.advisory.map((name, i) => (
                  <p
                    key={name}
                    className={`flex gap-2 text-[12px] leading-snug text-ink-2 transition-all duration-500 ${
                      shown ? "translate-x-0 opacity-100" : "translate-x-3 opacity-0"
                    }`}
                    style={{ transitionDelay: `${900 + i * 110}ms` }}
                  >
                    <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-ink-3" />
                    {name}
                  </p>
                ))}
              </div>
            </div>
          )}

          {/* The ones that did not apply are part of the answer: a tool that
              only ever reports wins is not measuring anything. */}
          <p className="mt-4 border-t border-line pt-3 font-mono text-[11px] text-ink-3">
            {data.techniquesTested} tested · {data.applied.length} measured ·{" "}
            {data.advisory.length} advisory
          </p>
        </Card>
      </div>
    </div>
  );
}

/* Drawn at the same weight and on the same grid as the rest of the interface.
   The bars mean a cost report; the falling line means a bill coming down,
   which is what the panel is about -- a currency symbol only says the panel
   concerns money, which the figures already say. */
const HEAD_ICON: Record<string, React.ReactNode> = {
  chart: (
    <>
      <path d="M3 21h18" />
      <path d="M7 21V11" />
      <path d="M12 21V4" />
      <path d="M17 21v-6" />
    </>
  ),
  save: (
    <>
      <path d="M3 7l6.5 6.5 4-4L21 17" />
      <path d="M21 12v5h-5" />
    </>
  ),
};

function Card({
  children,
  shown,
  delay,
  zClass,
  className = "",
  slide,
  icon,
  eyebrow,
  title,
}: {
  children: React.ReactNode;
  shown: boolean;
  delay: number;
  /* A class, not an inline style: inline zIndex outranks hover:z-30, so the
     panel would step out from under the centre and stay beneath it. */
  zClass: string;
  className?: string;
  /* Which way this panel steps out from under the centre when pointed at. */
  slide?: "left" | "right";
  icon: keyof typeof HEAD_ICON;
  eyebrow: string;
  title: string;
}) {
  return (
    /* Pointing at a side panel steps it out from under the centre without
       changing what is in front of what. The stacking order stays fixed, so
       the composition never reshuffles under the cursor; the card simply
       moves far enough that more of it is showing.

       The step is deliberately smaller than the overlap.
       Sliding further than the cards overlap pulls them apart and opens a
       strip of background between them mid-animation, which reads as the
       layout breaking rather than as a card moving.

       The slide lives on an inner element because the outer one is already
       using a transform for the reveal, and two transforms on one element
       overwrite rather than compose -- the same thing that silently dropped
       an animation earlier in this project. */
    <div
      className={`${className} ${zClass} group relative transition-all duration-[750ms] ease-out ${
        shown ? "translate-y-0 opacity-100" : "translate-y-5 opacity-0"
      }`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      <div
        className={`h-full transition-transform duration-300 ease-out ${
          slide === "left"
            ? "lg:group-hover:-translate-x-8"
            : slide === "right"
              ? "lg:group-hover:translate-x-8"
              : ""
        }`}
      >
      <div className="flex h-full flex-col rounded-2xl border border-line bg-surface elev-2 transition-shadow duration-300 group-hover:elev-4">
        <div className="flex items-center gap-3 border-b border-line px-5 py-4">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-accent-wash">
            <svg
              viewBox="0 0 24 24"
              className="h-[18px] w-[18px] text-accent"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.9"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden
            >
              {HEAD_ICON[icon]}
            </svg>
          </span>
          <div className="min-w-0">
            <p className="font-mono text-[10.5px] uppercase tracking-[0.11em] text-ink-3">
              {eyebrow}
            </p>
            <p className="mt-0.5 truncate text-[15px] font-semibold tracking-[-0.015em]">
              {title}
            </p>
          </div>
        </div>
        <div className="flex flex-1 flex-col px-5 py-5 sm:px-6">{children}</div>
      </div>
      </div>
    </div>
  );
}
