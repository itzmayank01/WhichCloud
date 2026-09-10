"use client";

import { useCallback, useEffect, useRef } from "react";
import {
  addEdge,
  Background,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Connection,
  type Edge as RFEdge,
  type Node as RFNode,
  type NodeProps,
} from "@xyflow/react";
// Imported here too, not only in ArchitectureGraph. Sketch mode renders with
// that component unmounted, and relying on a sibling's side-effect import to
// have styled this canvas is the kind of coupling that breaks the day someone
// splits the bundle.
import "@xyflow/react/dist/style.css";
import type { Node as TopoNode, Edge as TopoEdge } from "@/lib/api";
import { buildGraphModel } from "@/lib/graphModel";
import { layout, type CloudId } from "@/lib/elkLayout";
import type { IconEntry } from "@/lib/iconCatalog";

/**
 * The architecture as something you can move.
 *
 * Deliberately a SEPARATE canvas from ArchitectureGraph rather than an edit
 * mode bolted onto it. That component draws the estimate: its positions come
 * from ELK, its boxes carry the prices the engine computed, and every part of
 * it is arranged so the picture and the bill cannot disagree. The moment a
 * person drags a box or adds a service, that guarantee is gone -- and a canvas
 * that is sometimes authoritative and sometimes a drawing is worse than either,
 * because nothing on screen says which one you are looking at.
 *
 * So: this is a sketch. It STARTS from the priced layout, because "rearrange
 * what the engine gave me" is the actual use, and it says plainly that its
 * contents are no longer costed. Going back to the priced view is one click
 * and discards nothing on the engine's side, since the engine was never told.
 */

/* ── nodes ── */

function SketchService({ data, selected }: NodeProps) {
  const d = data as { label: string; icon?: string; detail?: string };
  return (
    <div
      className="flex h-full w-full items-center gap-2.5 border bg-white px-2.5 py-2"
      style={{
        borderRadius: 2,
        borderColor: selected ? "#1b3a6b" : "#D5DBDB",
        boxShadow: selected ? "0 0 0 1px #1b3a6b" : "none",
      }}
    >
      {/* Four handles, one per side. A single pair means every arrow leaves
          the bottom and arrives at the top, so a link to the box on the left
          loops all the way under both. */}
      <Handle type="target" position={Position.Top} className="!h-2 !w-2 !border-white !bg-ink-3" />
      <Handle type="target" position={Position.Left} className="!h-2 !w-2 !border-white !bg-ink-3" />
      <Handle type="source" position={Position.Right} className="!h-2 !w-2 !border-white !bg-ink-3" />
      <Handle type="source" position={Position.Bottom} className="!h-2 !w-2 !border-white !bg-ink-3" />
      {d.icon && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={d.icon} alt="" className="h-8 w-8 shrink-0 object-contain" />
      )}
      <div className="min-w-0 flex-1 leading-tight">
        <p className="truncate text-[12.5px] font-medium text-ink">{d.label}</p>
        {d.detail && (
          <p className="truncate text-[10.5px] italic text-ink-3">{d.detail}</p>
        )}
      </div>
    </div>
  );
}

function SketchGroup({ data, selected }: NodeProps) {
  const d = data as { label: string };
  return (
    <div
      className="h-full w-full border-[1.5px] border-dashed bg-transparent"
      style={{ borderRadius: 4, borderColor: selected ? "#1b3a6b" : "#8FA3BF" }}
    >
      <span className="absolute -top-2.5 left-2 bg-white px-1 text-[11px] font-medium text-ink-3">
        {d.label}
      </span>
    </div>
  );
}

function SketchText({ data, selected }: NodeProps) {
  const d = data as { label: string };
  return (
    <div
      className={`h-full w-full px-1 text-[13px] leading-snug text-ink ${
        selected ? "ring-1 ring-accent" : ""
      }`}
    >
      {d.label}
    </div>
  );
}

const nodeTypes = {
  sketchService: SketchService,
  sketchGroup: SketchGroup,
  sketchText: SketchText,
};

/* ── canvas ── */

type Tool = "select" | "connect" | "box" | "text";

function Inner({
  nodes: topoNodes,
  edges: topoEdges,
  cloud,
  pending,
  onPendingConsumed,
  tool,
  onToolDone,
  seedToken,
}: {
  nodes: TopoNode[];
  edges: TopoEdge[];
  cloud: CloudId;
  /** A service picked in the palette, waiting to be placed. */
  pending: IconEntry | null;
  onPendingConsumed: () => void;
  tool: Tool;
  onToolDone: () => void;
  /** Bumped to re-seed from the priced layout, discarding edits. */
  seedToken: number;
}) {
  const [nodes, setNodes, onNodesChange] = useNodesState<RFNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<RFEdge>([]);
  const rf = useReactFlow();
  const nextId = useRef(0);

  /* Seed from the same ELK run the priced canvas uses, so the sketch opens on
     the arrangement the reader was just looking at rather than on a pile of
     boxes they have to sort out before they can start. */
  useEffect(() => {
    let alive = true;
    const model = buildGraphModel(topoNodes, topoEdges, cloud);
    layout(model, cloud)
      .then((laid) => {
        if (!alive) return;
        const seeded: RFNode[] = [
          ...laid.containers.map((c) => ({
            id: `g:${c.id}`,
            type: "sketchGroup",
            position: { x: c.x, y: c.y },
            data: { label: c.label },
            style: { width: c.w, height: c.h },
            // Boundaries sit behind and must not swallow clicks aimed at the
            // services inside them.
            zIndex: 0,
            selectable: true,
            draggable: true,
          })),
          ...laid.nodes.map((n) => ({
            id: n.id,
            type: "sketchService",
            position: { x: n.x, y: n.y },
            data: { label: n.label, icon: undefined, detail: n.detail },
            style: { width: n.w, height: n.h },
            zIndex: 10,
          })),
        ];
        setNodes(seeded);
        setEdges(
          laid.edges.map((e) => ({
            id: e.id,
            source: e.source,
            target: e.target,
            markerEnd: { type: MarkerType.ArrowClosed },
            style: { stroke: "#8C9AAB" },
          })),
        );
        window.setTimeout(() => rf.fitView({ padding: 0.12 }), 40);
      })
      .catch((err) => console.error("[sketch] seed layout failed", err));
    return () => {
      alive = false;
    };
  }, [topoNodes, topoEdges, cloud, seedToken, setNodes, setEdges, rf]);

  /* Icons on seeded nodes.
     The priced layout knows a node's `kind`, not its file, and resolving that
     per provider already lives in ArchitectureGraph. Rather than duplicate it,
     seeded boxes carry no mark and services ADDED from the palette do -- which
     also happens to make an added box visibly different from an engine one. */

  const place = useCallback(
    (entry: IconEntry) => {
      // Dropped at the middle of what the reader is currently looking at, not
      // at the origin: on a diagram this wide, a node placed at 0,0 lands
      // somewhere off screen and reads as nothing having happened.
      const centre = rf.screenToFlowPosition({
        x: window.innerWidth / 2,
        y: window.innerHeight / 2,
      });
      const id = `added:${entry.id}:${nextId.current++}`;
      setNodes((current) => [
        ...current,
        {
          id,
          type: "sketchService",
          position: centre,
          data: { label: entry.name, icon: entry.icon },
          style: { width: 190, height: 52 },
          zIndex: 10,
          selected: true,
        },
      ]);
    },
    [rf, setNodes],
  );

  useEffect(() => {
    if (!pending) return;
    place(pending);
    onPendingConsumed();
  }, [pending, place, onPendingConsumed]);

  /* Box and text are one-shot tools: pick, click, and the tool releases. A
     mode that stays armed means the next click meant for a node draws another
     box, which is the commonest complaint about editors that do it. */
  const onPaneClick = useCallback(
    (event: React.MouseEvent) => {
      if (tool !== "box" && tool !== "text") return;
      const at = rf.screenToFlowPosition({ x: event.clientX, y: event.clientY });
      const id = `${tool}:${nextId.current++}`;
      setNodes((current) => [
        ...current,
        tool === "box"
          ? {
              id,
              type: "sketchGroup",
              position: at,
              data: { label: "Group" },
              style: { width: 260, height: 170 },
              zIndex: 0,
            }
          : {
              id,
              type: "sketchText",
              position: at,
              data: { label: "Text" },
              style: { width: 140, height: 22 },
              zIndex: 20,
            },
      ]);
      onToolDone();
    },
    [tool, rf, setNodes, onToolDone],
  );

  const onConnect = useCallback(
    (connection: Connection) =>
      setEdges((current) =>
        addEdge(
          {
            ...connection,
            markerEnd: { type: MarkerType.ArrowClosed },
            style: { stroke: "#1b3a6b" },
          },
          current,
        ),
      ),
    [setEdges],
  );

  /* Rename on double click. A palette entry arrives called "EC2" and the
     thing it stands for on this diagram is "Checkout workers"; without this
     the sketch can only ever say what the vendor calls the box. */
  const onNodeDoubleClick = useCallback(
    (_: React.MouseEvent, node: RFNode) => {
      const current = (node.data as { label?: string }).label ?? "";
      const next = window.prompt("Label", current);
      if (next === null) return;
      setNodes((all) =>
        all.map((n) =>
          n.id === node.id ? { ...n, data: { ...n.data, label: next } } : n,
        ),
      );
    },
    [setNodes],
  );

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onConnect={onConnect}
      onPaneClick={onPaneClick}
      onNodeDoubleClick={onNodeDoubleClick}
      nodeTypes={nodeTypes}
      nodesDraggable
      nodesConnectable={tool === "connect" || tool === "select"}
      elementsSelectable
      // Backspace as well as Delete: the Mac keyboard has no Delete key in
      // the position people reach for.
      deleteKeyCode={["Delete", "Backspace"]}
      minZoom={0.1}
      maxZoom={2.5}
      proOptions={{ hideAttribution: true }}
      className="bg-white"
      style={{ cursor: tool === "box" || tool === "text" ? "crosshair" : undefined }}
    >
      <Background gap={20} size={1} color="#EDEFF2" />
      <Controls showInteractive={false} />
    </ReactFlow>
  );
}

export function SketchCanvas(props: {
  nodes: TopoNode[];
  edges: TopoEdge[];
  cloud: CloudId;
  pending: IconEntry | null;
  onPendingConsumed: () => void;
  tool: Tool;
  onToolDone: () => void;
  seedToken: number;
}) {
  return (
    <ReactFlowProvider>
      <Inner {...props} />
    </ReactFlowProvider>
  );
}

export type { Tool as SketchTool };
