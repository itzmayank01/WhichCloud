"use client";

import { useEffect, useRef, useState } from "react";
import { iconFor } from "@/lib/serviceIcon";

/**
 * Enterprise AWS Architecture Showcase for the Landing Page.
 *
 * Implements the authentic AWS Solutions Architecture Reference standard:
 * - Official AWS Cloud dark header banner
 * - Users client actor on the left
 * - Green VPC boundary with [VPC] badge
 * - Soft blue Private Subnet with lock badge
 * - Functional component containers (Web UI, Client API, Data, Discovery, Cost, Image Deployment)
 * - Authentic high-res AWS icons with 2-line typography
 * - Solid blue step callout badges (1..17)
 * - Live animated traffic request particles moving along the flow sequence
 */

const W = 1200;
const H = 680;
const MIN_SCALE = 0.58;

type Node = {
  id: string;
  x: number;
  y: number;
  label: string;
  sub?: string;
  icon?: string;
  outside?: boolean;
};

const NODES: Node[] = [
  // Outside
  { id: "users", x: 16, y: 310, label: "Users", sub: "Web & Mobile", outside: true },

  // Web UI Component
  { id: "cloudfront", x: 140, y: 150, label: "Amazon CloudFront", sub: "Global Edge CDN" },
  { id: "s3-web", x: 275, y: 150, label: "Amazon S3 bucket", sub: "WebUIBucket" },
  { id: "cognito", x: 275, y: 280, label: "Amazon Cognito", sub: "User Authentication" },
  { id: "dynamo-settings", x: 275, y: 40, label: "Amazon DynamoDB", sub: "Settings table" },
  { id: "lambda-settings", x: 445, y: 40, label: "AWS Lambda", sub: "Settings function" },

  // Client API
  { id: "apigw-client", x: 410, y: 250, label: "Amazon API Gateway", sub: "REST Endpoint" },
  { id: "appsync", x: 495, y: 250, label: "AWS AppSync", sub: "GraphQL API" },

  // Storage Management Component
  { id: "amplify", x: 180, y: 480, label: "AWS Amplify", sub: "Frontend Host" },
  { id: "s3-amplify", x: 300, y: 480, label: "Amazon S3 bucket", sub: "AmplifyStorageBucket" },

  // Service Management
  { id: "apigw-gremlin", x: 470, y: 360, label: "Amazon API Gateway", sub: "ServiceGremlin API" },
  { id: "sdk", x: 470, y: 460, label: "AWS SDK", sub: "Client Library" },
  { id: "config", x: 470, y: 550, label: "AWS Config", sub: "Compliance Rules" },

  // Inside Private Subnet -> Data Component
  { id: "lambda-gremlin", x: 670, y: 200, label: "AWS Lambda", sub: "Gremlin function" },
  { id: "neptune", x: 800, y: 200, label: "Amazon Neptune", sub: "Graph Database" },
  { id: "lambda-search", x: 670, y: 310, label: "AWS Lambda", sub: "Search function" },
  { id: "opensearch", x: 800, y: 310, label: "Amazon OpenSearch", sub: "Search & Vector Index" },

  // Inside Private Subnet -> Discovery Component
  { id: "ecs", x: 740, y: 470, label: "Amazon ECS", sub: "Container Service" },
  { id: "fargate", x: 670, y: 535, label: "AWS Fargate", sub: "Serverless Compute" },
  { id: "ecr", x: 830, y: 535, label: "Amazon ECR", sub: "Container Registry" },

  // Cost Component
  { id: "lambda-cost", x: 620, y: 60, label: "AWS Lambda", sub: "Cost function" },
  { id: "athena", x: 730, y: 60, label: "Amazon Athena", sub: "Interactive SQL" },
  { id: "s3-cur", x: 840, y: 60, label: "Amazon S3 bucket", sub: "CURBucket" },
  { id: "cur", x: 950, y: 60, label: "AWS Cost & Usage", sub: "Billing Reports" },
  { id: "s3-results", x: 1070, y: 60, label: "Amazon S3 bucket", sub: "AthenaResultsBucket" },

  // Image Deployment Component
  { id: "s3-discovery", x: 1040, y: 220, label: "Amazon S3 bucket", sub: "DiscoveryBucket" },
  { id: "codepipeline", x: 1040, y: 330, label: "AWS CodePipeline", sub: "CI/CD Pipeline" },
  { id: "codebuild", x: 1040, y: 440, label: "AWS CodeBuild", sub: "Build & Test" },
  { id: "container-img", x: 1040, y: 540, label: "Container image", sub: "Docker Artifact" },
];

type StepEdge = {
  step: number;
  source: string;
  target: string;
  points: string;
  badgeX: number;
  badgeY: number;
  desc: string;
};

const EDGES: StepEdge[] = [
  { step: 1, source: "users", target: "cloudfront", points: "M 70 330 H 105 V 170 H 140", badgeX: 115, badgeY: 200, desc: "Users request UI assets via Amazon CloudFront global edge" },
  { step: 2, source: "cloudfront", target: "s3-web", points: "M 200 170 H 275", badgeX: 238, badgeY: 160, desc: "CloudFront fetches web bundle from Amazon S3 WebUIBucket" },
  { step: 3, source: "amplify", target: "s3-amplify", points: "M 235 500 H 300", badgeX: 268, badgeY: 490, desc: "Amplify manages client storage in S3 AmplifyStorageBucket" },
  { step: 4, source: "s3-web", target: "apigw-client", points: "M 335 170 H 375 V 270 H 410", badgeX: 388, badgeY: 230, desc: "Web UI invokes REST & GraphQL backend via API Gateway & AppSync" },
  { step: 5, source: "lambda-settings", target: "cognito", points: "M 445 60 H 370 V 290 H 335", badgeX: 355, badgeY: 200, desc: "Settings function authorizes requests with Amazon Cognito" },
  { step: 6, source: "lambda-settings", target: "dynamo-settings", points: "M 445 60 H 335", badgeX: 390, badgeY: 50, desc: "Settings function loads user configuration from DynamoDB" },
  { step: 7, source: "apigw-client", target: "lambda-gremlin", points: "M 555 270 H 610 V 220 H 670", badgeX: 630, badgeY: 220, desc: "API Gateway triggers Lambda Gremlin function for graph queries" },
  { step: 8, source: "apigw-client", target: "lambda-search", points: "M 555 270 H 610 V 330 H 670", badgeX: 630, badgeY: 330, desc: "API Gateway invokes Lambda Search function for full-text search" },
  { step: 9, source: "lambda-cost", target: "athena", points: "M 675 80 H 730", badgeX: 702, badgeY: 70, desc: "Cost function executes Athena SQL queries on billing logs" },
  { step: 10, source: "athena", target: "s3-cur", points: "M 790 80 H 840", badgeX: 815, badgeY: 70, desc: "Athena queries cost data in Amazon S3 CURBucket" },
  { step: 11, source: "cur", target: "s3-cur", points: "M 950 80 H 900", badgeX: 925, badgeY: 70, desc: "AWS Cost & Usage Report publishes daily cost data" },
  { step: 12, source: "athena", target: "s3-results", points: "M 760 100 V 120 H 1070 V 90", badgeX: 900, badgeY: 120, desc: "Athena stores query results in S3 AthenaResultsBucket" },
  { step: 13, source: "codepipeline", target: "codebuild", points: "M 1070 360 V 440", badgeX: 1085, badgeY: 400, desc: "CodePipeline triggers automated container builds in CodeBuild" },
  { step: 14, source: "codebuild", target: "ecr", points: "M 1040 460 H 930 V 555 H 890", badgeX: 955, badgeY: 530, desc: "CodeBuild pushes validated container image to Amazon ECR" },
  { step: 15, source: "ecs", target: "fargate", points: "M 740 490 H 700 V 535", badgeX: 710, badgeY: 510, desc: "Amazon ECS provisions serverless container tasks on AWS Fargate" },
  { step: 16, source: "sdk", target: "ecs", points: "M 530 480 H 635 V 490 H 740", badgeX: 620, badgeY: 480, desc: "AWS SDK configures service discovery for container tasks" },
  { step: 17, source: "apigw-gremlin", target: "lambda-gremlin", points: "M 530 380 H 640 V 240 H 670", badgeX: 645, badgeY: 310, desc: "ServiceGremlin API Gateway connects to Gremlin graph processing" },
];

export function ShowcaseDiagram() {
  const shell = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const [activeStep, setActiveStep] = useState<number>(1);
  const [isPlaying, setIsPlaying] = useState(true);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);

  const lastWidth = useRef(-1);

  useEffect(() => {
    const el = shell.current;
    if (!el) return;

    const fit = () => {
      const available = el.clientWidth - 16;
      if (available === lastWidth.current || available <= 0) return;
      lastWidth.current = available;
      setScale(Math.max(MIN_SCALE, Math.min(1, available / W)));
    };

    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Step simulation loop
  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setActiveStep((curr) => (curr >= 17 ? 1 : curr + 1));
    }, 2400);
    return () => clearInterval(interval);
  }, [isPlaying]);

  const activeEdge = EDGES.find((e) => e.step === activeStep);

  return (
    <div ref={shell} className="relative rounded-2xl border border-neutral-200 bg-white p-4 shadow-sm">
      {/* Top Interactive Bar */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-neutral-100 pb-3">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsPlaying((p) => !p)}
            className={`flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-[12.5px] font-bold text-white shadow-xs transition-all ${
              isPlaying ? "bg-amber-600 hover:bg-amber-700" : "bg-blue-600 hover:bg-blue-700"
            }`}
          >
            {isPlaying ? "Pause Flow" : "Play Simulation"}
          </button>

          <div className="flex items-center gap-1">
            <button
              onClick={() => setActiveStep((s) => (s > 1 ? s - 1 : 17))}
              className="grid h-7 w-7 place-items-center rounded border border-neutral-200 bg-white text-neutral-600 hover:bg-neutral-50"
            >
              ◀
            </button>
            <button
              onClick={() => setActiveStep((s) => (s < 17 ? s + 1 : 1))}
              className="grid h-7 w-7 place-items-center rounded border border-neutral-200 bg-white text-neutral-600 hover:bg-neutral-50"
            >
              ▶
            </button>
          </div>
        </div>

        {/* Live Step Tracker Ribbon */}
        {activeEdge && (
          <div className="flex items-center gap-2.5 rounded-lg border border-blue-200 bg-blue-50 px-3.5 py-1.5 text-[12.5px]">
            <span className="grid h-5 w-5 place-items-center rounded bg-blue-600 text-[10.5px] font-extrabold text-white">
              {activeStep}
            </span>
            <span className="font-semibold text-neutral-900 line-clamp-1">
              {activeEdge.desc}
            </span>
          </div>
        )}

        <div className="flex items-center gap-1 text-[10.5px] font-mono text-neutral-500">
          <span>17 Sequence Steps</span>
          <span>·</span>
          <span>VPC & Private Subnet</span>
        </div>
      </div>

      {/* SVG + HTML Stage */}
      <div style={{ overflowX: "auto", overflowY: "hidden" }}>
        <div style={{ width: W * scale, height: H * scale, position: "relative" }}>
          <div
            className="relative origin-top-left select-none"
            style={{ width: W, height: H, transform: `scale(${scale})` }}
          >
            <svg width={W} height={H} className="absolute inset-0">
              <defs>
                <marker
                  id="showcase-arrow"
                  viewBox="0 0 10 10"
                  refX="9"
                  refY="5"
                  markerWidth="5"
                  markerHeight="5"
                  orient="auto-start-reverse"
                >
                  <path d="M0 1 L9 5 L0 9 z" fill="#475569" />
                </marker>

                <marker
                  id="showcase-arrow-active"
                  viewBox="0 0 10 10"
                  refX="9"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M0 1 L9 5 L0 9 z" fill="#2563EB" />
                </marker>
              </defs>

              {/* 1. AWS Cloud Outer Container */}
              <rect
                x={100}
                y={10}
                width={1080}
                height={650}
                rx={10}
                fill="#FFFFFF"
                stroke="#232F3E"
                strokeWidth={1.8}
              />

              {/* AWS Brand Header */}
              <g>
                <rect x={101} y={11} width={138} height={30} fill="#232F3E" rx={6} />
                <rect x={101} y={11} width={138} height={28} fill="#232F3E" />
                <text x={114} y={31} fontSize="13" fontWeight="900" fill="#FF9900">
                  aws
                </text>
                <text x={148} y={30} fontSize="13.5" fontWeight="700" fill="#FFFFFF">
                  AWS Cloud
                </text>
              </g>

              {/* 2. Users (Actor) on the left */}
              <g>
                <rect x={10} y={280} width={75} height={90} rx={8} fill="#FFFFFF" stroke="#E2E8F0" strokeWidth={1.2} />
                <g transform="translate(26, 296)">
                  <circle cx="20" cy="10" r="5" fill="none" stroke="#232F3E" strokeWidth="1.8" />
                  <path d="M 12 24 C 12 18, 28 18, 28 24" fill="none" stroke="#232F3E" strokeWidth="1.8" />
                  <circle cx="10" cy="12" r="3.5" fill="none" stroke="#64748B" strokeWidth="1.4" />
                  <path d="M 4 24 C 4 19, 14 19, 15 24" fill="none" stroke="#64748B" strokeWidth="1.4" />
                  <circle cx="30" cy="12" r="3.5" fill="none" stroke="#64748B" strokeWidth="1.4" />
                  <path d="M 25 24 C 26 19, 36 19, 36 24" fill="none" stroke="#64748B" strokeWidth="1.4" />
                </g>
                <text x={47} y={350} textAnchor="middle" fontSize="12" fontWeight="700" fill="#232F3E">
                  Users
                </text>
              </g>

              {/* 3. Component Groups (Dashed boxes matching reference image) */}
              {/* Web UI component */}
              <rect x={115} y={20} width={430} height={385} rx={8} fill="none" stroke="#94A3B8" strokeWidth={1.3} strokeDasharray="6 4" />
              <text x={130} y={42} fill="#334155" fontSize="13" fontWeight="700">
                Web UI component
              </text>

              {/* Client API */}
              <rect x={380} y={225} width={180} height={110} rx={8} fill="none" stroke="#94A3B8" strokeWidth={1.3} strokeDasharray="6 4" />
              <text x={470} y={242} textAnchor="middle" fill="#334155" fontSize="12" fontWeight="700">
                Client API
              </text>

              {/* Storage management component */}
              <rect x={130} y={455} width={260} height={180} rx={8} fill="none" stroke="#94A3B8" strokeWidth={1.3} strokeDasharray="6 4" />
              <text x={145} y={476} fill="#334155" fontSize="12.5" fontWeight="700">
                Storage management component
              </text>

              {/* Cost component */}
              <rect x={585} y={35} width={580} height={145} rx={8} fill="none" stroke="#94A3B8" strokeWidth={1.3} strokeDasharray="6 4" />
              <text x={600} y={54} fill="#334155" fontSize="13" fontWeight="700">
                Cost component
              </text>

              {/* Image deployment component */}
              <rect x={970} y={200} width={195} height={435} rx={8} fill="none" stroke="#94A3B8" strokeWidth={1.3} strokeDasharray="6 4" />
              <text x={985} y={220} fill="#334155" fontSize="12.5" fontWeight="700">
                Image deployment component
              </text>

              {/* 4. VPC Boundary (Green) */}
              <rect x={585} y={195} width={365} height={440} rx={8} fill="rgba(30, 142, 62, 0.03)" stroke="#1E8E3E" strokeWidth={1.6} />
              {/* VPC Badge */}
              <g>
                <rect x={595} y={185} width={68} height={20} rx={3} fill="#1E8E3E" />
                <text x={629} y={199} textAnchor="middle" fontSize="10.5" fontWeight="800" fill="#FFFFFF">
                  VPC
                </text>
              </g>

              {/* 5. Private Subnet (Blue container inside VPC) */}
              <rect x={600} y={220} width={335} height={400} rx={8} fill="rgba(25, 118, 210, 0.05)" stroke="#1976D2" strokeWidth={1.4} strokeDasharray="6 4" />
              {/* Private Subnet Badge */}
              <g>
                <rect x={610} y={210} width={110} height={20} rx={3} fill="#1976D2" />
                <text x={665} y={224} textAnchor="middle" fontSize="10" fontWeight="700" fill="#FFFFFF">
                  Private subnet
                </text>
              </g>

              {/* Sub-groups inside Private Subnet */}
              <rect x={615} y={240} width={305} height={175} rx={6} fill="#FFFFFF" stroke="#CBD5E1" strokeWidth={1.2} strokeDasharray="4 3" />
              <text x={625} y={256} fill="#475569" fontSize="11" fontWeight="700">
                Data component
              </text>

              <rect x={615} y={430} width={305} height={175} rx={6} fill="#FFFFFF" stroke="#CBD5E1" strokeWidth={1.2} strokeDasharray="4 3" />
              <text x={625} y={446} fill="#475569" fontSize="11" fontWeight="700">
                Discovery component
              </text>

              {/* 6. Routed Connection Arrows */}
              {EDGES.map((edge) => {
                const isActive = edge.step === activeStep;
                return (
                  <g key={`edge-${edge.step}`}>
                    {isActive && (
                      <path
                        d={edge.points}
                        fill="none"
                        stroke="#93C5FD"
                        strokeWidth={6}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        opacity={0.6}
                      />
                    )}
                    <path
                      d={edge.points}
                      fill="none"
                      stroke={isActive ? "#2563EB" : "#475569"}
                      strokeWidth={isActive ? 2.4 : 1.5}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      markerEnd={`url(#${isActive ? "showcase-arrow-active" : "showcase-arrow"})`}
                      className="transition-colors duration-200"
                    />

                    {/* Animated moving packet */}
                    {isPlaying && (
                      <circle r={3.5} fill={isActive ? "#2563EB" : "#3B82F6"}>
                        <animateMotion path={edge.points} dur={isActive ? "1.4s" : "2.2s"} repeatCount="indefinite" />
                      </circle>
                    )}
                  </g>
                );
              })}

              {/* 7. Step Badges (Solid Blue 1..17) */}
              {EDGES.map((edge) => {
                const isActive = edge.step === activeStep;
                return (
                  <g
                    key={`badge-${edge.step}`}
                    transform={`translate(${edge.badgeX}, ${edge.badgeY})`}
                    onClick={() => setActiveStep(edge.step)}
                    className="cursor-pointer transition-transform hover:scale-110"
                  >
                    <rect
                      x={-10}
                      y={-10}
                      width={20}
                      height={20}
                      rx={4}
                      fill={isActive ? "#1D4ED8" : "#0066CC"}
                      stroke="#FFFFFF"
                      strokeWidth={1.5}
                    />
                    <text
                      x={0}
                      y={4}
                      textAnchor="middle"
                      fontSize="11"
                      fontWeight="800"
                      fill="#FFFFFF"
                    >
                      {edge.step}
                    </text>
                  </g>
                );
              })}
            </svg>

            {/* HTML Nodes with Official AWS Icons */}
            {NODES.filter((n) => !n.outside).map((node) => {
              const iconSrc = iconFor(node.label);
              const isHovered = hoveredNode === node.id;

              return (
                <div
                  key={node.id}
                  onMouseEnter={() => setHoveredNode(node.id)}
                  onMouseLeave={() => setHoveredNode(null)}
                  className={`group absolute flex cursor-pointer flex-col items-center transition-all ${
                    isHovered ? "z-30 scale-105" : "z-10"
                  }`}
                  style={{
                    left: node.x,
                    top: node.y,
                    width: 100,
                  }}
                >
                  <div
                    className={`grid h-12 w-12 place-items-center rounded-lg p-1 transition-all ${
                      isHovered ? "ring-2 ring-blue-500 shadow-md bg-white" : ""
                    }`}
                  >
                    {iconSrc ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={iconSrc}
                        alt={node.label}
                        width={48}
                        height={48}
                        className="h-11 w-11 object-contain drop-shadow-sm transition-transform group-hover:scale-105"
                      />
                    ) : (
                      <span className="grid h-10 w-10 place-items-center rounded bg-blue-50 text-blue-600 font-bold text-[11px]">
                        AWS
                      </span>
                    )}
                  </div>
                  <span className="mt-1 block line-clamp-2 px-1 text-center text-[11px] font-bold leading-tight text-neutral-900 group-hover:text-blue-600">
                    {node.label}
                  </span>
                  {node.sub && (
                    <span className="mt-0.5 block truncate px-1 text-center text-[9.5px] font-medium text-neutral-500">
                      {node.sub}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
