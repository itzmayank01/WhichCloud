import Link from "next/link";
import { PreviewCards } from "@/components/landing/PreviewCards";

export const revalidate = 300;

export default function Home() {
  return (
    <>
      {/* ── hero ─────────────────────────────────────────────── */}
      <section className="px-6 pt-20 pb-16 text-center sm:pt-28">
        <h1 className="mx-auto max-w-4xl text-balance text-[clamp(2.5rem,6.5vw,4.5rem)] font-semibold leading-[1.03] tracking-[-0.035em]">
          Know what it costs{" "}
          <span className="whitespace-nowrap rounded-lg bg-accent-wash px-2.5 py-0.5 text-accent">
            before
          </span>{" "}
          you build it
        </h1>

        <p className="mx-auto mt-7 max-w-2xl text-balance text-lg leading-relaxed text-ink-2 sm:text-xl">
          Describe your app in a sentence. Get three priced architectures across
          AWS, Azure and Google — with the optimizations that lower the bill.
        </p>

        <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/estimate"
            className="rounded-lg bg-accent px-6 py-3 text-[15px] font-medium text-white transition-opacity hover:opacity-90"
          >
            Price my app
          </Link>
          <Link
            href="/prices"
            className="rounded-lg border border-line-strong bg-surface px-6 py-3 text-[15px] font-medium text-ink transition-colors hover:bg-sunk"
          >
            Browse prices
          </Link>
        </div>

        <p className="mt-7 font-mono text-[11px] text-ink-3">
          No cloud account · no credit card · prices computed, not guessed
        </p>
      </section>

      {/* ── product preview ──────────────────────────────────── */}
      <section className="px-6 pb-24">
        <div className="mx-auto max-w-6xl">
          <PreviewCards />
        </div>
      </section>

      {/* ── the gap ──────────────────────────────────────────── */}
      <section className="border-y border-line bg-sunk px-6 py-20">
        <div className="mx-auto max-w-3xl text-center">
          <h2 className="text-balance text-[clamp(1.75rem,4vw,2.5rem)] font-semibold leading-tight tracking-[-0.025em]">
            One machine. Three prices.
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-ink-2">
            Same specs, same region, same hour. Multiply that gap across every
            service you run, for a year, and it stops being a rounding error.
          </p>
        </div>
      </section>

      {/* ── how it works ─────────────────────────────────────── */}
      <section className="px-6 py-20">
        <div className="mx-auto grid max-w-5xl gap-10 sm:grid-cols-3">
          {[
            {
              n: "01",
              title: "Describe",
              body: "One sentence, plain English. No account, no cloud credentials, nothing to connect.",
            },
            {
              n: "02",
              title: "Price",
              body: "Three architectures — cheapest, balanced, most reliable — itemised against live provider rates.",
            },
            {
              n: "03",
              title: "Optimize",
              body: "The techniques that lower the bill, each measured against the machine it beat.",
            },
          ].map((step) => (
            <div key={step.n}>
              <div className="tnum font-mono text-[28px] font-light text-line-strong">
                {step.n}
              </div>
              <h3 className="mt-3 text-[17px] font-medium tracking-tight">{step.title}</h3>
              <p className="mt-2 text-[14.5px] leading-relaxed text-ink-2">{step.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── honest limits ────────────────────────────────────── */}
      <section className="border-t border-line px-6 py-16">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-3">
            What we don&apos;t do
          </h2>
          <p className="mt-4 text-[14.5px] leading-relaxed text-ink-2">
            Sizing is a documented heuristic, not measured from your workload.
            GCP covers compute only. Prices are public list rates — no
            committed-use or negotiated discounts. These are estimates, not quotes.
          </p>
        </div>
      </section>
    </>
  );
}
