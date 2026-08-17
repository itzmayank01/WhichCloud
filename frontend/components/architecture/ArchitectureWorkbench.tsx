"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type ArchitectureView, type SavedArchitecture, type Tier } from "@/lib/api";
import { ArchitectureCanvas } from "@/components/architecture/ArchitectureCanvas";

/**
 * 5 Rich Presets including the exact reference architecture from the user's screenshot.
 */
const PRESETS = [
  {
    id: "aws-serverless-ref",
    title: "AWS Serverless & Container Platform (Reference)",
    badge: "Official Reference",
    description: `Design an enterprise AWS serverless and containerized web platform.
At the edge, users access the Web UI component through Amazon CloudFront CDN and Amazon S3 bucket WebUIBucket, authenticated with Amazon Cognito.
State and settings are handled by AWS Lambda Settings function and Amazon DynamoDB Settings table.
The Client API tier routes traffic through Amazon API Gateway and AWS AppSync.
In the Storage management component, AWS Amplify interacts with Amazon S3 bucket AmplifyStorageBucket.
Inside a secure VPC and Private subnet:
- Data component: AWS Lambda Gremlin function connects to Amazon Neptune graph database, and AWS Lambda Search function indexes data into Amazon OpenSearch Service.
- Discovery component: Amazon Elastic Container Service (ECS) orchestrates AWS Fargate container tasks, pulling container images from Amazon Elastic Container Registry (ECR).
Cost component: AWS Lambda Cost function processes billing data with Amazon Athena, storing Cost & Usage Reports (CUR) in Amazon S3 bucket CURBucket and results in Amazon S3 bucket AthenaResultsBucket.
Image deployment component: AWS CodePipeline and AWS CodeBuild build and deploy container images to Amazon S3 bucket DiscoveryBucket.
Management and tracking use AWS SDK, ServiceGremlin API Gateway, and AWS Config.`,
  },
  {
    id: "ai-rag-pipeline",
    title: "Generative AI & RAG Reasoning Engine",
    badge: "AI / LLM",
    description: `Design a high-performance Generative AI and Retrieval-Augmented Generation (RAG) system on AWS.
Users send prompts via Amazon CloudFront and Amazon API Gateway to AWS Lambda inference router.
Amazon Bedrock serves foundation models (Claude and Titan), with custom fine-tuned models running on Amazon SageMaker.
Vector embeddings and semantic search are stored in Amazon OpenSearch Service and Amazon Aurora PostgreSQL with pgvector.
Unstructured enterprise documents are ingested into Amazon S3 data lake, extracted with Amazon Textract, and processed with AWS Step Functions.
Conversational session history and user preferences are cached in Amazon DynamoDB and Amazon ElastiCache Redis.
Monitoring and trace latency are tracked using Amazon CloudWatch and AWS X-Ray.`,
  },
  {
    id: "eks-microservices",
    title: "Multi-Region Microservices on EKS",
    badge: "Kubernetes",
    description: `Design a highly available multi-region e-commerce microservices platform on AWS.
Traffic arrives at Amazon Route 53 with latency-based routing, protected by AWS WAF and AWS Shield, accelerated by AWS Global Accelerator and Amazon CloudFront.
Containerized microservices run on Amazon EKS clusters across multiple Availability Zones inside a secure VPC with public and private subnets.
Transactional data is managed with Amazon Aurora PostgreSQL Global Database and Amazon DynamoDB Global Tables.
In-memory caching is powered by Amazon ElastiCache Redis, event streaming by Amazon MSK (Managed Streaming for Apache Kafka), and asynchronous decoupling by Amazon SQS and Amazon SNS.
Secrets and encryption are secured with AWS KMS, AWS Secrets Manager, and AWS IAM.`,
  },
  {
    id: "data-lakehouse",
    title: "Modern Enterprise Data Lake & Analytics",
    badge: "Analytics",
    description: `Design a serverless real-time data lake and analytics platform on AWS.
Streaming data ingests through Amazon Kinesis Data Firehose and Amazon MSK into Amazon S3 raw zone bucket.
AWS Glue catalogs schemas with Data Catalog and runs serverless ETL transformations into partitioned parquet data in Amazon S3 curated bucket.
Interactive ad-hoc SQL queries are executed with Amazon Athena, enterprise data warehousing with Amazon Redshift Serverless, and large-scale batch processing with Amazon EMR.
Business intelligence dashboards are served via Amazon QuickSight, with access control governed by AWS Lake Formation.`,
  },
];

export function ArchitectureWorkbench({ owner }: { owner: string }) {
  const [selectedPreset, setSelectedPreset] = useState<string>(PRESETS[0].id);
  const [description, setDescription] = useState(PRESETS[0].description);
  const [view, setView] = useState<ArchitectureView | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [revealed, setRevealed] = useState(0);
  const [saved, setSaved] = useState<SavedArchitecture[]>([]);
  const [saving, setSaving] = useState(false);

  // Interactive Flow Simulation State
  const [isPlaying, setIsPlaying] = useState(true);
  const [activeStep, setActiveStep] = useState<number | null>(1);
  const [playbackSpeed, setPlaybackSpeed] = useState<1 | 2>(1);
  const [selectedTier, setSelectedTier] = useState<Tier | "all">("all");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const timer = useRef<number | null>(null);
  const animTimer = useRef<number | null>(null);

  // Fetch saved architectures
  const refreshSaved = useCallback(async () => {
    try {
      setSaved((await api.savedArchitectures(owner)).saved);
    } catch {
      /* ignore */
    }
  }, [owner]);

  useEffect(() => {
    void refreshSaved();
  }, [refreshSaved]);

  // Initial draw
  const draw = useCallback(async (customDesc?: string) => {
    const textToDraw = customDesc || description;
    if (!textToDraw.trim()) return;

    setBusy(true);
    setError(null);
    setView(null);
    setRevealed(0);
    setActiveStep(1);

    try {
      const result = await api.architecture({ description: textToDraw });
      setView(result);
      setRevealed(result.nodes.length);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not generate architecture diagram.");
    } finally {
      setBusy(false);
    }
  }, [description]);

  useEffect(() => {
    void draw(PRESETS[0].description);
  }, []);

  // Save architecture
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
      setError("Could not save architecture.");
    } finally {
      setSaving(false);
    }
  }

  // Download SVG
  async function downloadSvg() {
    try {
      const svg = await api.architectureSvg({ description });
      const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = "aws-architecture.svg";
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Could not export SVG.");
    }
  }

  // Get max steps
  const totalSteps = useMemo(() => {
    if (!view) return 0;
    const steps = view.edges.map((e) => e.step).filter((s): s is number => typeof s === "number");
    return steps.length > 0 ? Math.max(...steps) : 0;
  }, [view]);

  // Active step flow information
  const activeStepEdge = useMemo(() => {
    if (!view || activeStep === null) return null;
    const edge = view.edges.find((e) => e.step === activeStep);
    if (!edge) return null;
    const sourceNode = view.nodes.find((n) => n.id === edge.source);
    const targetNode = view.nodes.find((n) => n.id === edge.target);
    return { edge, sourceNode, targetNode };
  }, [view, activeStep]);

  // Step simulation loop
  useEffect(() => {
    if (!isPlaying || !view || totalSteps === 0) return;

    const interval = 2200 / playbackSpeed;
    animTimer.current = window.setInterval(() => {
      setActiveStep((curr) => {
        if (curr === null || curr >= totalSteps) return 1;
        return curr + 1;
      });
    }, interval);

    return () => {
      if (animTimer.current) window.clearInterval(animTimer.current);
    };
  }, [isPlaying, totalSteps, playbackSpeed, view]);

  // Selected node details
  const selectedNode = useMemo(() => {
    if (!view || !selectedNodeId) return null;
    return view.nodes.find((n) => n.id === selectedNodeId) || null;
  }, [view, selectedNodeId]);

  return (
    <div className="space-y-6">
      {/* ─── Presets Bar ─── */}
      <div>
        <div className="flex items-center justify-between">
          <label className="text-[13px] font-bold uppercase tracking-wider text-neutral-500">
            Select Architecture Template or Describe Your Own
          </label>
          <span className="text-[12px] font-medium text-blue-600">
            ⚡ Powered by WhichCloud Architecture Engine
          </span>
        </div>

        <div className="mt-2.5 grid gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
          {PRESETS.map((p) => {
            const isSelected = selectedPreset === p.id;
            return (
              <button
                key={p.id}
                onClick={() => {
                  setSelectedPreset(p.id);
                  setDescription(p.description);
                  void draw(p.description);
                }}
                className={`flex flex-col rounded-xl border p-3.5 text-left transition-all ${
                  isSelected
                    ? "border-blue-600 bg-blue-50/60 shadow-sm ring-1 ring-blue-600"
                    : "border-neutral-200 bg-white hover:border-neutral-300 hover:bg-neutral-50"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span
                    className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                      isSelected ? "bg-blue-600 text-white" : "bg-neutral-100 text-neutral-600"
                    }`}
                  >
                    {p.badge}
                  </span>
                  {isSelected && <span className="h-2 w-2 rounded-full bg-blue-600" />}
                </div>
                <span className="mt-2 text-[13.5px] font-bold text-neutral-900 line-clamp-1">
                  {p.title}
                </span>
                <span className="mt-1 text-[11.5px] text-neutral-500 line-clamp-2">
                  {p.description.slice(0, 90)}...
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* ─── Custom Prompt Area ─── */}
      <div className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between pb-2">
          <span className="text-[13px] font-semibold text-neutral-700">
            Architecture Specification Prompt
          </span>
          <span className="text-[11.5px] text-neutral-400 font-mono">
            Natural language to multi-tier diagram
          </span>
        </div>
        <textarea
          value={description}
          onChange={(e) => {
            setDescription(e.target.value);
            setSelectedPreset("custom");
          }}
          rows={4}
          spellCheck={false}
          className="w-full resize-y rounded-lg border border-neutral-200 bg-neutral-50/70 p-3 font-mono text-[13px] leading-relaxed text-neutral-900 outline-none focus:border-blue-500 focus:bg-white focus:ring-1 focus:ring-blue-500"
          placeholder="Describe your multi-tier cloud system (services, VPCs, subnets, databases, connections)..."
        />

        <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-neutral-100 pt-3">
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => void draw()}
              disabled={busy || !description.trim()}
              className="flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2 text-[14px] font-bold text-white shadow-sm transition-all hover:bg-blue-700 disabled:opacity-50 active:scale-95"
            >
              {busy ? (
                <>
                  <svg className="h-4 w-4 animate-spin text-white" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  Building Architecture...
                </>
              ) : (
                <>
                  <svg viewBox="0 0 20 20" className="h-4 w-4" fill="currentColor">
                    <path d="M10 2a8 8 0 100 16 8 8 0 000-16zm1 11H9v-2h2v2zm0-4H9V5h2v4z" />
                  </svg>
                  Render Architecture
                </>
              )}
            </button>

            {view && (
              <>
                <button
                  onClick={downloadSvg}
                  className="rounded-lg border border-neutral-200 bg-white px-3.5 py-2 text-[13px] font-semibold text-neutral-700 hover:bg-neutral-50 active:scale-95"
                >
                  Export SVG
                </button>
                <button
                  onClick={save}
                  disabled={saving}
                  className="rounded-lg border border-neutral-200 bg-white px-3.5 py-2 text-[13px] font-semibold text-neutral-700 hover:bg-neutral-50 disabled:opacity-50 active:scale-95"
                >
                  {saving ? "Saving..." : "Save Template"}
                </button>
              </>
            )}
          </div>

          {/* Layer Filter Pills */}
          {view && (
            <div className="flex flex-wrap items-center gap-1.5 rounded-lg border border-neutral-200 bg-neutral-50 p-1">
              {(
                [
                  ["all", "All Layers"],
                  ["edge", "Edge"],
                  ["compute", "Compute"],
                  ["data", "Data"],
                  ["security", "Security"],
                  ["observability", "Monitoring"],
                ] as const
              ).map(([t, label]) => (
                <button
                  key={t}
                  onClick={() => setSelectedTier(t as Tier | "all")}
                  className={`rounded px-2.5 py-1 text-[11.5px] font-semibold transition-all ${
                    selectedTier === t
                      ? "bg-white text-blue-600 shadow-sm"
                      : "text-neutral-500 hover:text-neutral-900"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-[14px] text-red-700">
          <span className="font-bold">Error:</span> {error}
        </div>
      )}

      {/* ─── Interactive Playback Bar & Step Inspector ─── */}
      {view && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-neutral-200 bg-white px-5 py-3.5 shadow-sm">
            {/* Playback Controls */}
            <div className="flex items-center gap-3">
              <button
                onClick={() => setIsPlaying((p) => !p)}
                className={`flex items-center gap-2 rounded-lg px-4 py-2 text-[13.5px] font-bold text-white shadow-sm transition-all ${
                  isPlaying ? "bg-amber-600 hover:bg-amber-700" : "bg-blue-600 hover:bg-blue-700"
                }`}
              >
                {isPlaying ? (
                  <>
                    <svg viewBox="0 0 20 20" className="h-4 w-4" fill="currentColor">
                      <rect x="5" y="4" width="3" height="12" rx="1" />
                      <rect x="12" y="4" width="3" height="12" rx="1" />
                    </svg>
                    Pause Traffic
                  </>
                ) : (
                  <>
                    <svg viewBox="0 0 20 20" className="h-4 w-4" fill="currentColor">
                      <path d="M6 4l10 6-10 6V4z" />
                    </svg>
                    Simulate Flow
                  </>
                )}
              </button>

              <div className="flex items-center gap-1">
                <button
                  onClick={() =>
                    setActiveStep((s) => (s && s > 1 ? s - 1 : totalSteps))
                  }
                  title="Previous step"
                  className="grid h-8 w-8 place-items-center rounded-lg border border-neutral-200 bg-white text-neutral-600 hover:bg-neutral-50 active:scale-95"
                >
                  <svg viewBox="0 0 20 20" className="h-4 w-4" fill="currentColor">
                    <path d="M12.7 5.3a1 1 0 00-1.4 0L7 9.6a1 1 0 000 1.4l4.3 4.3a1 1 0 001.4-1.4L9.1 10.3l3.6-3.6a1 1 0 000-1.4z" />
                  </svg>
                </button>
                <button
                  onClick={() =>
                    setActiveStep((s) => (s && s < totalSteps ? s + 1 : 1))
                  }
                  title="Next step"
                  className="grid h-8 w-8 place-items-center rounded-lg border border-neutral-200 bg-white text-neutral-600 hover:bg-neutral-50 active:scale-95"
                >
                  <svg viewBox="0 0 20 20" className="h-4 w-4" fill="currentColor">
                    <path d="M7.3 14.7a1 1 0 001.4 0l4.3-4.3a1 1 0 000-1.4L8.7 4.7a1 1 0 00-1.4 1.4l3.6 3.6-3.6 3.6a1 1 0 000 1.4z" />
                  </svg>
                </button>
              </div>

              {/* Speed toggle */}
              <div className="flex items-center gap-1 rounded-lg border border-neutral-200 bg-neutral-50 p-1">
                <button
                  onClick={() => setPlaybackSpeed(1)}
                  className={`rounded px-2 py-0.5 text-[11px] font-bold ${
                    playbackSpeed === 1 ? "bg-white text-blue-600 shadow-xs" : "text-neutral-500"
                  }`}
                >
                  1x
                </button>
                <button
                  onClick={() => setPlaybackSpeed(2)}
                  className={`rounded px-2 py-0.5 text-[11px] font-bold ${
                    playbackSpeed === 2 ? "bg-white text-blue-600 shadow-xs" : "text-neutral-500"
                  }`}
                >
                  2x
                </button>
              </div>
            </div>

            {/* Architecture Metrics */}
            <div className="flex flex-wrap items-center gap-x-5 gap-y-1 font-mono text-[12px] text-neutral-500">
              <span>
                <strong className="text-neutral-900 font-bold">{view.counts.services}</strong> Services
              </span>
              <span>
                <strong className="text-neutral-900 font-bold">{view.counts.edges}</strong> Flows
              </span>
              <span>
                <strong className="text-neutral-900 font-bold">{totalSteps}</strong> Sequence Steps
              </span>
              <span>
                <strong className="text-emerald-700 font-bold">{view.counts.priced}</strong> Priced
              </span>
            </div>
          </div>

          {/* Active Flow Inspector Ribbon */}
          {activeStepEdge && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-blue-200 bg-blue-50/80 px-5 py-3 shadow-xs">
              <div className="flex items-center gap-3">
                <span className="grid h-7 w-7 place-items-center rounded bg-blue-600 text-[12px] font-extrabold text-white shadow-xs">
                  {activeStep}
                </span>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-[13.5px] font-bold text-neutral-900">
                      {activeStepEdge.sourceNode?.label || "Source"}
                    </span>
                    <span className="text-blue-500 font-bold">→</span>
                    <span className="text-[13.5px] font-bold text-neutral-900">
                      {activeStepEdge.targetNode?.label || "Target"}
                    </span>
                  </div>
                  <p className="text-[11.5px] text-neutral-600">
                    {activeStepEdge.edge.flow.toUpperCase()} request flow: traffic routed through sequence step {activeStep}.
                  </p>
                </div>
              </div>

              {/* Step Navigation Pill buttons */}
              <div className="flex items-center gap-1">
                {Array.from({ length: totalSteps }, (_, i) => i + 1).map((s) => (
                  <button
                    key={s}
                    onClick={() => setActiveStep(s)}
                    className={`h-5 w-5 rounded text-[10px] font-bold transition-all ${
                      s === activeStep
                        ? "bg-blue-600 text-white shadow-xs scale-110"
                        : "bg-white text-neutral-600 hover:bg-blue-100"
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* ─── Main Canvas Rendering ─── */}
          <div className="rounded-2xl border border-neutral-200 bg-white p-3 shadow-sm">
            <ArchitectureCanvas
              view={view}
              revealed={revealed}
              activeStep={activeStep}
              selectedTier={selectedTier}
              isPlaying={isPlaying}
              onSelectNode={setSelectedNodeId}
            />
          </div>

          {/* ─── Node Inspector Card (On Hover or Selection) ─── */}
          {selectedNode && (
            <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-neutral-200 bg-neutral-900 p-4 text-white shadow-lg">
              <div className="flex items-center gap-3">
                <span className="grid h-10 w-10 place-items-center rounded-lg bg-white/10 text-white font-bold">
                  {selectedNode.tier.toUpperCase().slice(0, 3)}
                </span>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-[15px] font-bold">{selectedNode.label}</span>
                    <span className="rounded bg-blue-500/30 px-2 py-0.5 text-[10.5px] font-bold uppercase text-blue-300">
                      {selectedNode.tier}
                    </span>
                  </div>
                  <p className="text-[12px] text-neutral-300">
                    {selectedNode.purpose || "Enterprise cloud resource component."}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-5 text-right font-mono text-[13px]">
                {selectedNode.priced && selectedNode.monthly_usd !== null ? (
                  <div>
                    <span className="text-[10px] uppercase text-neutral-400 block">List Rate</span>
                    <span className="text-[16px] font-bold text-emerald-400">
                      ${selectedNode.monthly_usd.toFixed(2)}/mo
                    </span>
                  </div>
                ) : (
                  <span className="text-amber-400 font-bold">Heuristic / Unpriced</span>
                )}
                {selectedNode.sku && (
                  <div>
                    <span className="text-[10px] uppercase text-neutral-400 block">SKU</span>
                    <span className="text-neutral-300">{selectedNode.sku}</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ─── Saved Architectures ─── */}
      {saved.length > 0 && (
        <div className="border-t border-neutral-200 pt-6">
          <h3 className="text-[15px] font-bold text-neutral-900">Saved System Architectures</h3>
          <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {saved.map((item) => (
              <div
                key={item.id}
                className="flex items-center justify-between rounded-xl border border-neutral-200 bg-white p-3 shadow-2xs hover:border-neutral-300"
              >
                <button
                  onClick={() => {
                    setDescription(item.description);
                    void draw(item.description);
                  }}
                  className="min-w-0 flex-1 text-left"
                >
                  <span className="block truncate text-[13px] font-bold text-neutral-900">
                    {item.title}
                  </span>
                  <span className="block font-mono text-[11px] text-neutral-500">
                    {item.services} services · {new Date(item.created_at).toLocaleDateString()}
                  </span>
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
