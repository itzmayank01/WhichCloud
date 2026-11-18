"use client";

import type { Node as ApiNode } from "@/lib/api";
import { money } from "@/lib/api";
import { serviceName } from "@/lib/services";
import { roleFor } from "@/lib/serviceMeta";

/**
 * The detail board that floats over the diagram while a service is hovered.
 *
 * Provider reference diagrams stop at the box. This is the panel that answers
 * the next question — what am I paying for this, what share of the bill is it,
 * and did an optimization already touch it — without navigating away from the
 * shape you are reading.
 *
 * It occupies fixed space rather than appearing and disappearing, so the
 * diagram never reflows underneath the cursor.
 */

/**
 * kind → what it is, and the thing worth knowing about what it costs.
 *
 * Every kind in `lib/serviceMeta.ts`'s KIND_ROLE belongs here. It held six
 * entries while the topology emits thirty-eight, so every supporting
 * service -- NAT, DNS, KMS, backups, audit, TLS, telemetry, the whole
 * control plane -- fell through to "Part of the architecture.", which
 * tells the reader nothing and is the one panel whose entire job is to
 * answer "why am I paying for this".
 */
const NOTE: Record<string, string> = {
  client: "Your users. Free, and the reason for everything to the right.",

  // edge and ingress
  cdn: "Caches content close to your users. Usually pays for itself: a byte served from here is a byte you are not paying origin egress for.",
  network: "Data leaving the provider's network. The invisible half of most cloud bills.",
  waf: "Filters hostile requests before they reach the app. Priced per rule and per million requests, so it tracks traffic rather than attacks.",
  apigateway: "Managed front door for the API. Priced per request — cheap at low volume, worth comparing against a load balancer past a few million calls.",
  loadbalancer: "Distributes traffic across instances. Fixed hourly cost regardless of load.",

  // compute
  compute: "Application servers. Usually the easiest line to shrink: smaller instances, ARM, or fewer of them off-peak.",
  compute_fargate: "Containers with no servers to manage. Billed per vCPU-second and GB-second, so idle costs nothing and busy costs more than the equivalent instance.",
  lambda: "Functions that run on demand. Free while nothing happens, which is what makes it cheap for spiky or occasional work.",

  // data
  cache: "Keeps hot data in memory so the database never answers the same question twice. Often removes more from the database line than it adds here.",
  database: "Managed database. Often the largest line on the bill, and the one people forget to right-size.",
  database_replica: "A read-only copy of the database. Takes read traffic off the primary, and costs roughly what the primary costs.",
  dynamodb: "Key-value store. Priced per read and write rather than per hour, so an idle table is close to free.",
  timestream: "Time-series store for metrics and telemetry. Priced on ingest and retention — the retention tier decides the bill.",
  storage: "Object storage. Cheap per gigabyte; the cost usually hides in egress rather than here.",
  search: "Full-text search cluster. Sized by index rather than by traffic, so it costs the same overnight as it does at peak.",
  warehouse: "Analytics warehouse for reporting queries. The storage is cheap; the compute left running is not.",

  // streaming and ingest
  streaming: "Buffers events between producers and consumers. Priced per shard or throughput unit, held whether or not events arrive.",
  kafka: "Managed Kafka for event streams. Brokers run continuously, so this is a fixed line rather than a usage one.",
  firehose: "Delivers a stream into storage or a warehouse. Priced per GB ingested, with no cluster to keep running.",
  iot: "Ingest point for device messages. Priced per message, so the bill tracks fleet size and reporting interval.",

  // analytics and ML
  athena: "Queries files in object storage directly. Priced per TB scanned — partitioning and columnar formats are what keep it cheap.",
  glue: "Managed ETL, and the catalog those queries read. Priced per DPU-hour while a job runs.",
  rekognition: "Image and video analysis. Priced per image or per minute processed.",
  comprehend: "Text analysis — entities, sentiment, language. Priced per unit of text processed.",

  // networking plumbing
  nat: "Lets private subnets reach the internet. Charges an hourly rate AND a per-GB processing fee, which is why it surprises people.",

  // control plane
  kms: "Encryption keys. Cents per key per month, plus a charge per API call — the calls are usually the larger half.",
  secrets: "Stores credentials the app fetches at runtime. Priced per secret per month.",
  tls: "The certificate behind HTTPS. Free from the provider on AWS and Google; what it costs you is the renewal you no longer do by hand.",
  auth: "Sign-in, sessions and user records. Priced per monthly active user, so it scales with your users rather than your servers.",
  dns: "Answers lookups for your domain. A few cents per zone plus a per-query rate; rarely a meaningful line.",
  backup: "Point-in-time copies. Priced per GB stored, and the retention window is the only lever that moves it.",

  // account plane
  audit: "Records every API call made in the account. The first copy of the trail is usually free; keeping it for years is not.",
  threat: "Watches logs for stolen credentials and unusual behaviour. Priced on the volume of events analysed.",
  posture: "Checks the account against security benchmarks continuously. Priced per check, per resource.",
  flowlogs: "Records which address talked to which. Cheap to produce — the storage is what you actually pay for.",
  monitoring: "Metrics, logs and alarms. Custom metrics and log retention are where this line grows.",
  tracing: "Follows a single request across services. Priced per trace recorded and scanned.",
};

export function HoverBoard({
  node,
  provider,
  total,
}: {
  node: ApiNode | null;
  provider: string;
  total: number;
}) {
  const idle = node === null;

  return (
    <div
      className={`rounded-xl border bg-surface px-5 py-4 transition-all duration-200 ${
        idle
          ? "border-line"
          : "border-line-strong elev-3"
      }`}
      aria-live="polite"
    >
      {idle ? (
        <div className="flex items-center gap-3">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-sunk">
            <svg viewBox="0 0 24 24" className="h-4 w-4 stroke-ink-2" fill="none" strokeWidth="1.8" strokeLinecap="round">
              <path d="M5 12h14M13 6l6 6-6 6" />
            </svg>
          </span>
          <p className="text-[14.5px] text-ink-2">
            Hover any service to see what it costs and why it is there.
          </p>
        </div>
      ) : (
        <div className="flex flex-wrap items-start gap-x-8 gap-y-3">
          <div className="min-w-[200px]">
            <div className="font-mono text-[13px] uppercase tracking-[0.12em] text-ink-3 font-medium">
              {node.kind}
            </div>
            <div className="mt-1 text-[17px] font-medium leading-tight text-ink">
              {serviceName(provider, node.kind, node.label)}
            </div>
            {node.sku && (
              <div className="mt-1 font-mono text-[13px] text-ink-2 font-medium">{node.sku}</div>
            )}
          </div>

          <div>
            <div className="font-mono text-[13px] uppercase tracking-[0.12em] text-ink-3 font-medium">
              Monthly
            </div>
            <div className="tnum mt-1 font-mono text-[24px] leading-none text-ink">
              {node.priced ? money(node.monthly_usd) : "n/a"}
            </div>
            {node.priced && total > 0 && (
              <div className="tnum mt-1 font-mono text-[13px] text-ink-2 font-medium">
                {Math.round(node.share * 100)}% of {money(total, 0)}
              </div>
            )}
          </div>

          <div className="max-w-[380px] flex-1">
            <div className="font-mono text-[13px] uppercase tracking-[0.12em] text-ink-3 font-medium">
              What it is
            </div>
            <p className="mt-1 text-[14px] leading-relaxed text-ink-2 font-medium">
              {/* A kind added to the topology before it is described here
                  falls back to its one-line role ("Encryption keys") rather
                  than to filler, so the worst case is terse instead of
                  useless. */}
              {NOTE[node.kind] ?? roleFor(node.kind)}
            </p>
            {node.optimized_by.length > 0 && (
              <p className="mt-2 flex items-center gap-2 text-[13.5px] text-accent font-medium">
                <span className="h-2 w-2 rounded-full bg-accent" />
                Optimized by {node.optimized_by.join(", ")}
              </p>
            )}
            {!node.priced && (
              <p className="mt-2 text-[13.5px] text-caution font-medium">
                No published price for this on {provider.toUpperCase()}. Shown so
                the gap is visible rather than hidden.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
