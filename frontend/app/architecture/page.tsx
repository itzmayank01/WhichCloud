"use client";

import { useEffect, useRef, useState } from "react";
import { api, type ArchitectureView } from "@/lib/api";
import {
  ArchitectureCanvas,
  FlowLegend,
} from "@/components/architecture/ArchitectureCanvas";

/* A full pass is held under twelve seconds however large the architecture is,
   because past that the animation stops being a build and becomes a wait. The
   per-node step is derived from the node count and then clamped: without the
   floor a forty node diagram would flicker, and without the ceiling a five
   node one would crawl. */
const TOTAL_MS = 10_000;
const step = (count: number) =>
  Math.max(140, Math.min(480, TOTAL_MS / Math.max(1, count)));

const SAMPLE = `Design a highly scalable multi-region e-commerce platform on AWS for 10 million users. Use Route 53, CloudFront, WAF, Shield, and Global Accelerator at the edge. Deploy containerized microservices on Amazon EKS across 3 AWS regions and multiple Availability Zones, including authentication, catalog, inventory, orders, payments, and recommendations. Use Aurora PostgreSQL Global Database, DynamoDB Global Tables, ElastiCache Redis, S3, MSK, SQS/SNS, and API Gateway. Implement VPCs with public/private subnets, NAT Gateways, VPC endpoints, security groups, IAM, KMS, and Secrets Manager. Add CI/CD with GitHub Actions and ECR, observability with CloudWatch, X-Ray and OpenTelemetry, and active-active disaster recovery with automatic regional failover.`;

export default function ArchitecturePage() {
  const [description, setDescription] = useState(SAMPLE);
  const [view, setView] = useState<ArchitectureView | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [revealed, setRevealed] = useState(0);
  const timer = useRef<number | null>(null);

  /* Reveal in placement order, which the layout engine already sorted by
     tier, so the picture builds the way it is read: traffic arrives at the
     top and the system fills in beneath it. */
  useEffect(() => {
    if (!view) return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setRevealed(view.nodes.length);
      return;
    }

    const ms = step(view.nodes.length);
    const tick = () =>
      setRevealed((n) => {
        if (n >= view.nodes.length) return n;
        timer.current = window.setTimeout(tick, ms);
        return n + 1;
      });

    timer.current = window.setTimeout(tick, 260);
    return () => {
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [view]);

  async function draw() {
    setBusy(true);
    setError(null);
    setView(null);
    setRevealed(0);
    try {
      setView(await api.architecture({ description }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not read that description");
    } finally {
      setBusy(false);
    }
  }

  const done = view ? revealed >= view.nodes.length : false;

  return (
    <div className="mx-auto max-w-6xl px-6 py-12">
      <h1 className="text-[clamp(1.75rem,3.6vw,2.5rem)] font-semibold tracking-[-0.025em]">
        Draw an architecture
      </h1>
      <p className="mt-3 max-w-2xl text-[16px] leading-relaxed text-ink-2">
        Describe a system and it is drawn as described — every service named,
        whether or not the price catalog reaches it. Services it cannot price
        say so rather than showing nothing.
      </p>

      <textarea
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        rows={7}
        spellCheck={false}
        className="mt-6 w-full resize-y rounded-xl border border-line bg-surface p-4 font-mono text-[13.5px] leading-relaxed text-ink outline-none focus:border-accent"
        placeholder="Describe your system…"
      />

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          onClick={draw}
          disabled={busy || !description.trim()}
          className="rounded-lg bg-accent px-5 py-2.5 text-[15.5px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          {busy ? "Reading…" : "Draw it"}
        </button>
        {view && !done && (
          <button
            onClick={() => setRevealed(view.nodes.length)}
            className="rounded-lg border border-line-strong bg-surface px-5 py-2.5 text-[15.5px] font-medium text-ink transition-colors hover:bg-sunk"
          >
            Skip animation
          </button>
        )}
        {view && done && (
          <button
            onClick={() => setRevealed(0)}
            className="rounded-lg border border-line-strong bg-surface px-5 py-2.5 text-[15.5px] font-medium text-ink transition-colors hover:bg-sunk"
          >
            Replay
          </button>
        )}
      </div>

      {error && (
        <p className="mt-4 rounded-lg bg-caution-wash px-4 py-3 text-[14.5px] text-caution">
          {error}
        </p>
      )}

      {view && (
        <>
          <div className="mt-8 flex flex-wrap items-baseline gap-x-6 gap-y-2 border-t border-line pt-5 font-mono text-[13px] text-ink-3">
            <span className="text-ink">
              {view.counts.services} services
            </span>
            <span>{view.counts.edges} connections</span>
            <span>
              {view.regions} region{view.regions === 1 ? "" : "s"} ·{" "}
              {view.azs_per_region} AZ each
            </span>
            <span>
              {view.counts.priced} priced · {view.counts.services - view.counts.priced}{" "}
              not in catalog
            </span>
            {view.external.length > 0 && (
              <span>external: {view.external.join(", ")}</span>
            )}
          </div>

          <div className="mt-4">
            <FlowLegend />
          </div>

          <div className="mt-6 overflow-hidden rounded-xl border border-line bg-canvas p-2">
            <ArchitectureCanvas view={view} revealed={revealed} />
          </div>
        </>
      )}
    </div>
  );
}
