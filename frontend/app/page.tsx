import { Suspense } from "react";
import Link from "next/link";
import { CloudArchitectures } from "@/components/landing/CloudArchitectures";
import { ShowcaseDiagram } from "@/components/landing/ShowcaseDiagram";
import { PriceTicker } from "@/components/PriceTicker";
import { Reveal } from "@/components/landing/Reveal";
import { CountUp } from "@/components/landing/CountUp";
import { AskDemoSection } from "@/components/landing/AskDemoSection";
import { PipelineSection } from "@/components/landing/PipelineSection";
import { HeroFreshness } from "@/components/landing/HeroFreshness";
import {
  FeatureBlock,
  Footer,
  ProviderBar,
  Stats,
} from "@/components/landing/Sections";

export const revalidate = 300;

/* ── small visuals used inside the feature blocks ── */

function DiffVisual() {
  return (
    <Reveal className="rounded-xl border border-line bg-surface p-5 elev-3">
      <div
        className="reveal-line font-mono text-[13px] uppercase tracking-[0.13em] text-ink-3 font-medium"
        style={{ "--i": 0 } as React.CSSProperties}
      >
        Balanced → Most reliable
      </div>
      <div className="mt-4 space-y-3 font-mono text-[15px]">
        <div
          className="reveal-line diff-flash -mx-2 flex items-baseline justify-between gap-3 rounded px-2"
          style={{ "--i": 1 } as React.CSSProperties}
        >
          <span className="text-ink-2">
            <span className="text-spend">~</span> Database
          </span>
          <CountUp value={121.91} prefix="+" delayMs={220} className="text-spend" />
        </div>
        <div
          className="reveal-line pl-3 text-[13.5px] text-ink-3 font-medium"
          style={{ "--i": 2 } as React.CSSProperties}
        >
          db.t4g.large →{" "}
          <span
            className="sku-new inline-block text-ink-2"
            style={{ "--i": 2 } as React.CSSProperties}
          >
            db.t4g.large:multi-az
          </span>
        </div>
        <div
          className="reveal-line flex items-baseline justify-between gap-3 border-t border-line pt-3"
          style={{ "--i": 3 } as React.CSSProperties}
        >
          <span className="text-ink-3">= Compute, storage, egress, LB</span>
          <span className="text-ink-3">unchanged</span>
        </div>
      </div>
      <div
        className="reveal-line mt-4 rounded-lg bg-caution-wash px-3 py-2.5"
        style={{ "--i": 4 } as React.CSSProperties}
      >
        <div className="font-mono text-[13px] uppercase tracking-[0.12em] text-caution font-medium">
          What you give up on Cheapest
        </div>
        <p className="mt-1.5 text-[15px] leading-relaxed text-ink-2">
          Single instance, so a restart is downtime. Single-zone database.
        </p>
      </div>
    </Reveal>
  );
}

function TerraformVisual() {
  /* Written out a line at a time rather than dropped in whole, so the panel
     reads as a file being generated. The lines are listed here instead of
     inlined in a <pre> because each one needs to carry its own delay. */
  const LINES = [
    <span className="text-zinc-500"># Graviton, measured 9% cheaper here</span>,
    <>
      <span className="text-white">module</span>{" "}
      <span className="text-amber-200">&quot;ecs_service&quot;</span> {"{"}
    </>,
    <>
      {"  source           = "}
      <span className="text-amber-200">&quot;terraform-aws-modules/ecs/aws&quot;</span>
    </>,
    <>
      {"  cpu_architecture = "}
      <span className="text-amber-200">&quot;ARM64&quot;</span>
    </>,
    <>
      {"  desired_count    = "}
      <span className="text-white">3</span>
    </>,
    <>
      {"  min_capacity     = "}
      <span className="text-white">1</span>{" "}
      <span className="text-zinc-500"># scale to zero</span>
    </>,
    <>{"}"}</>,
  ];

  return (
    <Reveal className="overflow-hidden rounded-xl border border-line bg-[#12171a] elev-3">
      <div className="flex items-center gap-1.5 border-b border-white/8 px-4 py-2.5">
        <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
        <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
        <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
        <span className="ml-2 font-mono text-[13.5px] text-white/40 font-medium">main.tf</span>
      </div>
      <pre className="overflow-x-auto p-5 font-mono text-[14.5px] leading-[1.75] text-zinc-400">
        {LINES.map((line, i) => (
          <div
            key={i}
            className="reveal-line"
            style={{ "--i": i } as React.CSSProperties}
          >
            {line}
            {i === LINES.length - 1 && (
              <span
                className="reveal-caret ml-1 inline-block h-[1.05em] w-[0.55ch] translate-y-[0.18em] bg-zinc-500"
                style={{ "--i": LINES.length } as React.CSSProperties}
                aria-hidden
              />
            )}
          </div>
        ))}
      </pre>
    </Reveal>
  );
}

/* Placeholder used while a data-backed section is still being fetched. It
   reserves roughly the height of the real thing so the page does not jump
   when the content lands. */
function Loading({ height }: { height: number }) {
  return (
    <div
      className="animate-pulse rounded-xl border border-line bg-sunk"
      style={{ height }}
      aria-hidden
    />
  );
}

/* ─────────────────────────── page ─────────────────────────── */

export default function Home() {
  return (
    <>
      {/* hero */}
      <section className="px-6 pt-16 pb-20 text-center sm:pt-24">
        <h1 className="mx-auto max-w-4xl text-balance text-[clamp(2.5rem,6.5vw,4.5rem)] font-semibold leading-[1.02] tracking-[-0.035em]">
          Know what it costs{" "}
          <span className="text-accent">before</span> you build it
        </h1>

        <p className="mx-auto mt-7 max-w-2xl text-balance text-lg leading-relaxed text-ink-2 sm:text-xl">
          Describe your app in a sentence. Get three priced architectures across
          AWS, Azure and Google, with the optimizations that lower the bill.
        </p>

        <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/estimate"
            className="rounded-lg bg-accent px-6 py-3 text-[17px] font-medium text-white transition-all hover:opacity-90 active:scale-[.98]"
          >
            Price my app
          </Link>
          <Link
            href="/#pricing"
            className="rounded-lg border border-line-strong bg-surface px-6 py-3 text-[17px] font-medium text-ink transition-colors hover:bg-sunk active:bg-line"
          >
            See the comparison
          </Link>
        </div>

        {/* Suspended so the heading still paints without waiting on /health,
            with the same line minus the timestamp as the fallback. */}
        <Suspense
          fallback={
            <p className="mt-7 font-mono text-[14px] text-ink-3 font-medium">
              Prices fetched from AWS, Azure and Google · computed, not guessed
            </p>
          }
        >
          <HeroFreshness />
        </Suspense>
      </section>

      {/* live prices, moving */}
      <PriceTicker />

      {/* priced comparison — the first thing after the hero */}
      <section id="pricing" className="px-6 pb-24 pt-16">
        <div className="mx-auto max-w-6xl">
          <div className="mb-8 max-w-2xl">
            <div className="font-mono text-[13.5px] uppercase tracking-[0.14em] text-accent font-medium">
              Priced, across three clouds
            </div>
            <h2 className="mt-3 text-balance text-[clamp(1.75rem,3.6vw,2.5rem)] font-semibold leading-tight tracking-[-0.025em]">
              The same workload, costed on each provider
            </h2>
            <p className="mt-4 text-[16px] leading-relaxed text-ink-2">
              Real figures. Pick a cloud to see its own services and what each
              one costs. Every number is fetched from that provider&apos;s
              published rates.
            </p>
          </div>
          <Suspense fallback={<Loading height={560} />}>
            <CloudArchitectures />
          </Suspense>
        </div>
      </section>

      {/* provider bar — our version of a logo wall */}
      <section className="border-y border-line bg-sunk px-6 py-16">
        <ProviderBar />
      </section>

      {/* the gap */}
      <section className="px-6 py-24">
        <div className="mx-auto max-w-3xl text-center">
          <h2 className="text-balance text-[clamp(2rem,4.5vw,3rem)] font-semibold leading-[1.08] tracking-[-0.03em]">
            One machine. Three prices.{" "}
            {/* The second half was set in the tertiary ink, which is scaled
                for small print. At heading size it read as faded rather than
                secondary, and it carries the actual point of the sentence. */}
            <span className="text-ink-2">
              Multiply that across every service you run, for a year.
            </span>
          </h2>
          <p className="mx-auto mt-6 max-w-xl text-[18px] leading-relaxed text-ink-2">
            Cost tools tell you what you already spent. This one tells you what
            you would spend, while the decision is still cheap to change.
          </p>
        </div>
      </section>

      {/* architecture, all three clouds */}
      <section id="architecture" className="px-6 pb-24">
        <div className="mx-auto max-w-6xl">
          <div className="mb-8 max-w-2xl">
            <div className="font-mono text-[13.5px] uppercase tracking-[0.14em] text-accent font-medium">
              Architecture
            </div>
            <h2 className="mt-3 text-balance text-[clamp(1.75rem,3.6vw,2.5rem)] font-semibold leading-tight tracking-[-0.025em]">
              The same system, drawn on all three clouds
            </h2>
            <p className="mt-4 text-[16px] leading-relaxed text-ink-2">
              WhichCloud reads systems like this one: every service, every
              tier, every dependency. It prices each part against live
              provider rates.
            </p>
          </div>

          <ShowcaseDiagram />

        </div>
      </section>

      {/* plain-English intake, playing itself */}
      <section className="border-t border-line bg-canvas px-6 py-24">
        <div className="mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-2">
          <div>
            <div className="font-mono text-[13.5px] uppercase tracking-[0.14em] text-accent font-medium">
              Plain English
            </div>
            <h2 className="mt-3 text-balance text-[clamp(1.75rem,3.6vw,2.5rem)] font-semibold leading-tight tracking-[-0.025em]">
              Describe it in a sentence, get it priced
            </h2>
            <p className="mt-4 max-w-md text-[17px] leading-relaxed text-ink-2">
              A reader turns your description into a requirement: workload,
              traffic shape, scale, region. The engine prices that requirement
              against every cloud and shows its working.
            </p>
            <ul className="mt-5 space-y-2.5">
              {[
                "The model reads the request. It never sets a price.",
                "Every figure comes from the provider's published rates",
                "Prefer a form? It is the default, and needs no model at all",
              ].map((b) => (
                <li key={b} className="flex gap-2.5 text-[15.5px] text-ink-2">
                  <span className="mt-[9px] h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                  {b}
                </li>
              ))}
            </ul>
            <Link
              href="/estimate"
              className="mt-6 inline-flex items-center gap-2 text-[15px] font-medium text-accent hover:underline"
            >
              Try it on your own app
            </Link>
          </div>
          <Suspense fallback={<Loading height={520} />}>
            <AskDemoSection />
          </Suspense>
        </div>
      </section>

      {/* feature blocks */}
      {/* how the automation actually runs */}
      <section className="border-t border-line px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <div className="mx-auto mb-10 max-w-2xl text-center">
            <div className="font-mono text-[13.5px] uppercase tracking-[0.14em] text-accent font-medium">
              How it works
            </div>
            <h2 className="mt-3 text-balance text-[clamp(1.75rem,3.6vw,2.5rem)] font-semibold leading-tight tracking-[-0.025em]">
              You write one sentence. It does the rest.
            </h2>
            <p className="mt-4 text-[16px] leading-relaxed text-ink-2">
              Five steps, and you only do the first one. The numbers under each
              step are live, read from the service as this page loaded.
            </p>
          </div>
          <Suspense fallback={<Loading height={240} />}>
            <PipelineSection />
          </Suspense>
        </div>
      </section>

      <section id="optimizations" className="px-6 pb-24">
        <div className="mx-auto flex max-w-6xl flex-col gap-6">
          <FeatureBlock
            eyebrow="Trade-offs"
            title="Know what the extra money actually buys"
            body="Switching options does not just show a bigger number. It shows which line changed, what it changed to, and what stayed the same, plus what the cheaper option gives up."
            bullets={[
              "One upgrade reported as one change, not two events",
              "Every cheap option states its cost in reliability",
            ]}
            tint="bg-sunk"
            reverse
            visual={<DiffVisual />}
          />

          <FeatureBlock
            eyebrow="Infrastructure as code"
            eyebrowIcon="logos:terraform-icon"
            title="Advice you can actually run"
            body="Every recommendation comes out as Terraform built from vetted modules, with the optimizations already applied and a comment explaining why each one is there."
            bullets={[
              "Built from terraform-aws-modules, not generated from scratch",
              "Optimizations applied and annotated",
            ]}
            tint="bg-[#f2f4f6]"
            visual={<TerraformVisual />}
          />
        </div>
      </section>

      {/* stats band */}
      <section className="bg-[#0d1414] px-6 py-24">
        <Suspense fallback={<Loading height={260} />}>
            <Stats />
          </Suspense>
      </section>

      {/* honest limits */}
      <section className="px-6 py-20">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="font-mono text-[13.5px] uppercase tracking-[0.14em] text-ink-3 font-medium">
            What we don&apos;t do
          </h2>
          <p className="mt-5 text-[17px] leading-relaxed text-ink-2">
            Sizing is a documented heuristic, not measured from your workload.
            GCP covers compute only. Prices are public list rates, with no
            committed-use or negotiated discounts. Spot rates move continuously,
            so treat them as indicative. These are estimates, not quotes.
          </p>
        </div>
      </section>

      {/* final CTA */}
      <section className="border-t border-line px-6 py-24 text-center">
        <h2 className="mx-auto max-w-3xl text-balance text-[clamp(2rem,5vw,3.25rem)] font-semibold leading-[1.05] tracking-[-0.03em]">
          Price it before you build it
        </h2>
        <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/estimate"
            className="rounded-lg bg-accent px-7 py-3.5 text-[17px] font-medium text-white transition-all hover:opacity-90 active:scale-[.98]"
          >
            Price my app
          </Link>
          <Link
            href="/#pricing"
            className="rounded-lg border border-line-strong bg-surface px-7 py-3.5 text-[17px] font-medium text-ink transition-colors hover:bg-sunk active:bg-line"
          >
            See the comparison
          </Link>
        </div>
        <p className="mt-8 font-mono text-[14.5px] text-ink-3">
          Takes one sentence. Needs no cloud account.
        </p>
      </section>

      <Footer />
    </>
  );
}
