"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, type ArchitectureView, type SavedArchitecture } from "@/lib/api";
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

export function ArchitectureWorkbench({ owner }: { owner: string }) {
  const [description, setDescription] = useState(SAMPLE);
  const [view, setView] = useState<ArchitectureView | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [revealed, setRevealed] = useState(0);
  const [saved, setSaved] = useState<SavedArchitecture[]>([]);
  const [saving, setSaving] = useState(false);
  const timer = useRef<number | null>(null);

  /* The list is what makes an account worth having: a description typed once
     can be reopened instead of rewritten. */
  const refreshSaved = useCallback(async () => {
    try {
      setSaved((await api.savedArchitectures(owner)).saved);
    } catch {
      /* The workbench still works without its history. */
    }
  }, [owner]);

  useEffect(() => {
    void refreshSaved();
  }, [refreshSaved]);

  async function save() {
    if (!view) return;
    setSaving(true);
    try {
      await api.saveArchitecture({
        owner,
        title: description.trim().slice(0, 60),
        description,
        services: view.counts.services,
        regions: view.regions,
      });
      await refreshSaved();
    } catch {
      setError("Could not save that one");
    } finally {
      setSaving(false);
    }
  }

  /* The file is built server-side and handed over as a blob. A diagram that
     can only be looked at on the page that made it is a demo; one that can go
     into a report or a pull request is a tool. SVG because draw.io, Figma and
     Illustrator open it as editable shapes rather than a picture of them. */
  async function download() {
    try {
      const svg = await api.architectureSvg({ description });
      const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = "architecture.svg";
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Could not export that one");
    }
  }

  async function remove(id: string) {
    try {
      await api.deleteArchitecture(id, owner);
      await refreshSaved();
    } catch {
      /* Leaving it listed is better than pretending it went. */
    }
  }

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
    <div>
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
            onClick={download}
            className="rounded-lg border border-line-strong bg-surface px-5 py-2.5 text-[15.5px] font-medium text-ink transition-colors hover:bg-sunk"
          >
            Download SVG
          </button>
        )}
        {view && done && (
          <button
            onClick={save}
            disabled={saving}
            className="rounded-lg border border-line-strong bg-surface px-5 py-2.5 text-[15.5px] font-medium text-ink transition-colors hover:bg-sunk disabled:opacity-40"
          >
            {saving ? "Saving…" : "Save this"}
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

      {saved.length > 0 && (
        <div className="mt-12 border-t border-line pt-8">
          <h2 className="text-[17px] font-semibold tracking-[-0.015em]">
            Saved architectures
          </h2>
          <ul className="mt-4 space-y-2">
            {saved.map((item) => (
              <li
                key={item.id}
                className="flex items-center gap-4 rounded-lg border border-line bg-surface px-4 py-3"
              >
                <button
                  onClick={() => {
                    setDescription(item.description);
                    setView(null);
                    setRevealed(0);
                  }}
                  className="min-w-0 flex-1 text-left"
                >
                  <span className="block truncate text-[14.5px] font-medium text-ink">
                    {item.title}
                  </span>
                  <span className="mt-0.5 block font-mono text-[12px] text-ink-3">
                    {item.services} services · {item.regions} region
                    {item.regions === 1 ? "" : "s"} ·{" "}
                    {new Date(item.created_at).toLocaleDateString()}
                  </span>
                </button>
                <button
                  onClick={() => remove(item.id)}
                  className="shrink-0 text-[13px] text-ink-3 transition-colors hover:text-spend"
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
