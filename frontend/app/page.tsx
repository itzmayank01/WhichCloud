import Link from "next/link";
import { CloudArchitectures } from "@/components/landing/CloudArchitectures";
import { ShowcaseDiagram } from "@/components/landing/ShowcaseDiagram";
import { PriceTicker } from "@/components/PriceTicker";
import {
  FeatureBlock,
  Footer,
  Pill,
  ProviderBar,
  Stats,
} from "@/components/landing/Sections";

export const revalidate = 300;

/* ── small visuals used inside the feature blocks ── */

function DiffVisual() {
  return (
    <div className="rounded-xl border border-line bg-surface p-5 shadow-[0_1px_2px_rgba(13,20,20,.04),0_20px_44px_-24px_rgba(13,20,20,.24)]">
      <div className="font-mono text-[13px] uppercase tracking-[0.13em] text-ink-3 font-medium">
        Balanced → Most reliable
      </div>
      <div className="mt-4 space-y-3 font-mono text-[15px]">
        <div className="flex items-baseline justify-between gap-3">
          <span className="text-ink-2">
            <span className="text-spend">~</span> Database
          </span>
          <span className="tnum text-spend">+$121.91</span>
        </div>
        <div className="pl-3 text-[13.5px] text-ink-3 font-medium">
          db.t4g.large → db.t4g.large:multi-az
        </div>
        <div className="flex items-baseline justify-between gap-3 border-t border-line pt-3">
          <span className="text-ink-3">= Compute, storage, egress, LB</span>
          <span className="text-ink-3">unchanged</span>
        </div>
      </div>
      <div className="mt-4 rounded-lg bg-caution-wash px-3 py-2.5">
        <div className="font-mono text-[13px] uppercase tracking-[0.12em] text-caution font-medium">
          What you give up on Cheapest
        </div>
        <p className="mt-1.5 text-[15px] leading-relaxed text-ink-2">
          Single instance — a restart is downtime. Single-zone database.
        </p>
      </div>
    </div>
  );
}

function TerraformVisual() {
  return (
    <div className="overflow-hidden rounded-xl border border-line bg-[#12171a] shadow-[0_1px_2px_rgba(13,20,20,.04),0_20px_44px_-24px_rgba(13,20,20,.3)]">
      <div className="flex items-center gap-1.5 border-b border-white/8 px-4 py-2.5">
        <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
        <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
        <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
        <span className="ml-2 font-mono text-[13.5px] text-white/40 font-medium">main.tf</span>
      </div>
      <pre className="overflow-x-auto p-5 font-mono text-[14.5px] leading-[1.75] text-zinc-400">
        <span className="text-zinc-500"># Graviton — measured 9% cheaper here</span>
        {"\n"}
        <span className="text-white">module</span>{" "}
        <span className="text-amber-200">&quot;ecs_service&quot;</span> {"{"}
        {"\n  source           = "}
        <span className="text-amber-200">&quot;terraform-aws-modules/ecs/aws&quot;</span>
        {"\n  cpu_architecture = "}
        <span className="text-amber-200">&quot;ARM64&quot;</span>
        {"\n  desired_count    = "}
        <span className="text-white">3</span>
        {"\n  min_capacity     = "}
        <span className="text-white">1</span>{" "}
        <span className="text-zinc-500"># scale to zero</span>
        {"\n}"}
      </pre>
    </div>
  );
}

/* ─────────────────────────── page ─────────────────────────── */

export default function Home() {
  return (
    <>
      {/* hero */}
      <section className="px-6 pt-16 pb-20 text-center sm:pt-24">
        <Pill>GCP pricing now included — three clouds, one query</Pill>

        <h1 className="mx-auto mt-8 max-w-4xl text-balance text-[clamp(2.5rem,6.5vw,4.5rem)] font-semibold leading-[1.02] tracking-[-0.035em]">
          Know what it costs{" "}
          <span className="text-accent">before</span> you build it
        </h1>

        <p className="mx-auto mt-7 max-w-2xl text-balance text-lg leading-relaxed text-ink-2 sm:text-xl">
          Describe your app in a sentence. Get three priced architectures across
          AWS, Azure and Google — with the optimizations that lower the bill.
        </p>

        <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/estimate"
            className="rounded-lg bg-accent px-6 py-3 text-[17px] font-medium text-white transition-opacity hover:opacity-90"
          >
            Price my app
          </Link>
          <Link
            href="/prices"
            className="rounded-lg border border-line-strong bg-surface px-6 py-3 text-[17px] font-medium text-ink transition-colors hover:bg-sunk"
          >
            Browse prices
          </Link>
        </div>

        <p className="mt-7 font-mono text-[14px] text-ink-3 font-medium">
          Prices fetched from AWS, Azure and Google · computed, not guessed
        </p>
      </section>

      {/* live prices, moving */}
      <PriceTicker />

      {/* priced comparison — the first thing after the hero */}
      <section className="px-6 pb-24 pt-16">
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
              one costs — every number fetched from that provider&apos;s
              published rates.
            </p>
          </div>
          <CloudArchitectures />
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
            <span className="text-ink-3">
              Multiply that across every service you run, for a year.
            </span>
          </h2>
          <p className="mx-auto mt-6 max-w-xl text-[18px] leading-relaxed text-ink-2">
            Cost tools tell you what you already spent. This one tells you what
            you would spend — while the decision is still cheap to change.
          </p>
        </div>
      </section>

      {/* architecture, all three clouds */}
      <section className="px-6 pb-24">
        <div className="mx-auto max-w-6xl">
          <div className="mb-8 max-w-2xl">
            <div className="font-mono text-[13.5px] uppercase tracking-[0.14em] text-accent font-medium">
              Architecture
            </div>
            <h2 className="mt-3 text-balance text-[clamp(1.75rem,3.6vw,2.5rem)] font-semibold leading-tight tracking-[-0.025em]">
              The same system, drawn on all three clouds
            </h2>
            <p className="mt-4 text-[16px] leading-relaxed text-ink-2">
              WhichCloud reads systems like this one — every service, every
              tier, every dependency — and prices each part against live
              provider rates.
            </p>
          </div>

          <ShowcaseDiagram />

        </div>
      </section>

      {/* feature blocks */}
      <section className="px-6 pb-24">
        <div className="mx-auto flex max-w-6xl flex-col gap-6">
          <FeatureBlock
            eyebrow="Trade-offs"
            title="Know what the extra money actually buys"
            body="Switching options does not just show a bigger number. It shows which line changed, what it changed to, and what stayed the same — plus what the cheaper option gives up."
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
        <Stats />
      </section>

      {/* honest limits */}
      <section className="px-6 py-20">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="font-mono text-[13.5px] uppercase tracking-[0.14em] text-ink-3 font-medium">
            What we don&apos;t do
          </h2>
          <p className="mt-5 text-[17px] leading-relaxed text-ink-2">
            Sizing is a documented heuristic, not measured from your workload.
            GCP covers compute only. Prices are public list rates — no
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
            className="rounded-lg bg-accent px-7 py-3.5 text-[17px] font-medium text-white transition-opacity hover:opacity-90"
          >
            Price my app
          </Link>
          <Link
            href="/prices"
            className="rounded-lg border border-line-strong bg-surface px-7 py-3.5 text-[17px] font-medium text-ink transition-colors hover:bg-sunk"
          >
            Browse prices
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
