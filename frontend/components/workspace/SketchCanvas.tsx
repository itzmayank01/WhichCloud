"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
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
  useNodesInitialized,
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
// Shared with the priced canvas on purpose. These are what make a box look
// like the diagram it came from; duplicating them here would guarantee the
// two drift apart the first time either is touched.
import {
  ContainerBadge,
  ROUTE_ROWS,
  containerStyle,
  serviceDisplayName,
  serviceIconPath,
} from "@/components/architecture/ArchitectureGraph";
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

/* Handles: four per box, one per side, because a single top/bottom pair sends
   every arrow out of the bottom and into the top -- so a link to the box on
   the LEFT loops all the way under both of them.

   Visible, not hover-revealed. They were 8px dots at default opacity and the
   first thing asked of this canvas was "where is the arrow so I can connect
   services" -- the answer was "drag the dot you cannot see". In connect mode
   they grow and turn accent, so the thing you are meant to grab is the most
   obvious thing on the box. */
function Handles({ connecting }: { connecting: boolean }) {
  const cls = connecting
    ? "!h-3 !w-3 !border-2 !border-white !bg-accent !opacity-100"
    : "!h-2.5 !w-2.5 !border-2 !border-white !bg-ink-3 !opacity-70";
  return (
    <>
      <Handle type="target" position={Position.Top} className={cls} />
      <Handle type="target" position={Position.Left} className={cls} />
      <Handle type="source" position={Position.Right} className={cls} />
      <Handle type="source" position={Position.Bottom} className={cls} />
    </>
  );
}

/* The service box, drawn from the SAME helpers as the priced canvas --
   serviceIconPath and serviceDisplayName are exported from ArchitectureGraph
   rather than reimplemented. The first version of this editor drew plain
   bordered rectangles, so opening it threw away every icon, every provider
   product name and the whole visual language of the diagram someone had just
   been reading. Editing a picture should not mean editing a worse one. */
function SketchService({ data, selected }: NodeProps) {
  const d = data as {
    label: string;
    kind?: string;
    icon?: string;
    detail?: string;
    cloud?: CloudId;
    connecting?: boolean;
  };
  const cloud = d.cloud ?? "aws";
  // An explicit icon (added from the palette) wins; otherwise the engine's
  // `kind` resolves exactly as it does on the priced canvas.
  const icon = d.icon ?? (d.kind ? serviceIconPath(d.kind, cloud) : null);
  const title = (d.kind ? serviceDisplayName(d.kind, cloud) : null) ?? d.label;

  return (
    <div
      className="flex h-full w-full items-center gap-2.5 border bg-white px-2.5 py-2"
      style={{
        borderRadius: 2,
        // Selection has to be unmistakable on a canvas whose whole point is
        // picking things: a 1px border change reads as a rendering artefact.
        borderColor: selected ? "#1b3a6b" : "#D5DBDB",
        boxShadow: selected
          ? "0 0 0 2px #1b3a6b, 0 4px 12px rgba(27,58,107,.20)"
          : "none",
      }}
    >
      <Handles connecting={Boolean(d.connecting)} />
      <div className="grid h-9 w-9 shrink-0 place-items-center">
        {icon ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={icon} alt="" className="h-8 w-8 object-contain" />
        ) : (
          <div className="h-7 w-7 rounded-[2px] bg-sunk ring-1 ring-line" />
        )}
      </div>
      <div className="min-w-0 flex-1 leading-tight">
        <p className="truncate text-[12.5px] font-semibold text-ink">{title}</p>
        {d.detail && (
          <p className="truncate text-[10.5px] italic text-ink-3">{d.detail}</p>
        )}
      </div>
    </div>
  );
}

/* The boundary, in the priced canvas's own colour language: VPC green, zone
   dashed blue, subnets by tier. Drawn from containerStyle so the two views
   cannot drift -- one hand-picked grey dashed rectangle made every boundary
   look alike, which is precisely what those colours exist to prevent. */
function SketchGroup({ data, selected }: NodeProps) {
  const d = data as { label: string; kind?: string; cloud?: CloudId };
  const st = containerStyle(d.kind ?? "cloud");
  const routes = d.kind ? ROUTE_ROWS[d.kind] : undefined;

  return (
    <div
      className="h-full w-full"
      style={{
        background: st.fill,
        border: `${selected ? st.width + 1 : st.width}px ${
          st.dash ? "dashed" : "solid"
        } ${selected ? "#1b3a6b" : st.border}`,
        borderRadius: 2,
        boxShadow: selected ? "0 0 0 2px rgba(27,58,107,.18)" : "none",
      }}
    >
      <span
        className="absolute flex items-center gap-1.5 whitespace-nowrap rounded-[2px] pr-1.5 text-[12px] font-semibold leading-[18px]"
        style={{ left: 8, top: -10, background: "#FFFFFF", color: st.ink }}
      >
        {d.kind && <ContainerBadge kind={d.kind} cloud={d.cloud} />}
        {d.label}
      </span>
      {routes && (
        <div className="flex h-full flex-col justify-center gap-0.5 px-2 pt-2">
          {routes.map(([dest, via]) => (
            <div key={dest} className="flex items-center justify-between gap-2">
              <span className="font-mono text-[9.5px] text-ink-2">{dest}</span>
              <span className="font-mono text-[9.5px] text-ink-3">{via}</span>
            </div>
          ))}
        </div>
      )}
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

/* ── saved layouts ──
 *
 * A sketch survives leaving the editor. Without this the canvas discarded
 * everything the moment you pressed "Back to the priced diagram" -- so the
 * one thing the editor exists for, arranging a diagram the way you want it,
 * could not be kept, and every visit started from the ELK layout again.
 *
 * Deliberately localStorage rather than the API. /architecture/save stores a
 * DESCRIPTION against an owner; a sketch is neither -- it is a scratch
 * arrangement of one tier on one cloud, worth keeping for the person who made
 * it and nobody else. Putting it on the server would mean an owner, a schema
 * and a migration for something that belongs in the browser that drew it.
 *
 * Keyed on cloud + tier + the shape of the topology, so switching tiers gives
 * you that tier's sketch rather than this one's boxes in the wrong places,
 * and re-pricing a genuinely different architecture does not restore a layout
 * built for the old one.
 */
const STORE_PREFIX = "whichcloud.sketch.v1";

function layoutKey(cloud: string, nodes: TopoNode[], edges: TopoEdge[]): string {
  const shape = `${nodes.length}:${edges.length}:${nodes
    .map((n) => n.id)
    .sort()
    .join(",")}`;
  // A short non-cryptographic digest; this only has to separate architectures
  // from each other, not resist anything.
  let h = 0;
  for (let i = 0; i < shape.length; i++) h = (h * 31 + shape.charCodeAt(i)) | 0;
  return `${STORE_PREFIX}.${cloud}.${h}`;
}

type Saved = { nodes: RFNode[]; edges: RFEdge[] };

function readSaved(key: string): Saved | null {
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Saved;
    return parsed?.nodes?.length ? parsed : null;
  } catch {
    // A corrupt or unreadable entry must not take the editor down with it:
    // the fallback is the ELK layout, which is where a first visit starts.
    return null;
  }
}

/* ── canvas ── */

type Tool = "select" | "connect" | "box" | "text";

/** Whatever is currently picked -- a service, a boundary, a label or an arrow.
 *  Arrows included deliberately: an editor where every box can be changed and
 *  the lines between them cannot is an editor that stops halfway. */
export type Selection = {
  kind: "service" | "group" | "text" | "edge";
  id: string;
  label: string;
};

export type Command =
  | { type: "rename"; id: string; label: string }
  | { type: "delete"; id: string };

function Inner({
  nodes: topoNodes,
  edges: topoEdges,
  cloud,
  pending,
  onPendingConsumed,
  tool,
  onToolDone,
  seedToken,
  onSelectionChange,
  command,
  onCommandDone,
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
  onSelectionChange?: (selection: Selection | null) => void;
  command?: Command | null;
  onCommandDone?: () => void;
}) {
  const [nodes, setNodes, onNodesChange] = useNodesState<RFNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<RFEdge>([]);
  const rf = useReactFlow();
  const nextId = useRef(0);
  const host = useRef<HTMLDivElement | null>(null);
  /* The seedToken this canvas has already acted on. Initialised to the
     incoming value so a first mount is NOT mistaken for a reset -- otherwise
     opening the editor would wipe the saved sketch it was about to restore. */
  const seenToken = useRef(seedToken);
  const ready = useNodesInitialized();

  /* Fit once React Flow has actually MEASURED the nodes, not on a timer.
     The seed runs ELK asynchronously and the old code guessed 40ms; when the
     layout took longer than that the fit ran against an empty canvas and
     never re-ran, which is why the sketch opened zoomed into one corner with
     boxes the size of the viewport. `useNodesInitialized` is the event that
     guess was standing in for. */
  useEffect(() => {
    if (!ready || nodes.length === 0) return;
    rf.fitView({ padding: 0.14, duration: 200 });
    // seedToken so a reset re-fits too.
  }, [ready, seedToken, rf, nodes.length]);

  /* Seed from the same ELK run the priced canvas uses, so the sketch opens on
     the arrangement the reader was just looking at rather than on a pile of
     boxes they have to sort out before they can start.

     Unless there is a saved sketch for this exact architecture, in which case
     that wins: someone returning to a diagram they arranged wants THEIR
     arrangement, and re-running ELK over it would silently throw the work
     away a second time. */
  useEffect(() => {
    let alive = true;
    const key = layoutKey(cloud, topoNodes, topoEdges);
    /* Reset means reset. The tool bumps seedToken to ask for the priced
       layout back, and restoring the save here would hand it exactly the
       arrangement it was trying to discard -- a button that appears to do
       nothing, which is worse than no button. */
    const isReset = seenToken.current !== seedToken;
    seenToken.current = seedToken;
    if (isReset) {
      try {
        window.localStorage.removeItem(key);
      } catch {
        /* nothing to do; the ELK path below is the correct outcome anyway */
      }
    }
    const saved = isReset ? null : readSaved(key);
    if (saved) {
      setNodes(saved.nodes);
      setEdges(saved.edges);
      return () => {
        alive = false;
      };
    }
    const model = buildGraphModel(topoNodes, topoEdges, cloud);
    layout(model, cloud)
      .then((laid) => {
        if (!alive) return;
        const seeded: RFNode[] = [
          ...laid.containers.map((c) => ({
            id: `g:${c.id}`,
            type: "sketchGroup",
            position: { x: c.x, y: c.y },
            // kind is what containerStyle reads to pick the boundary's colour
            // and dash; dropping it made every boundary an identical grey box.
            data: { label: c.label, kind: c.kind, cloud },
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
            // kind + cloud, so the box resolves the same mark and the same
            // provider product name the priced canvas gave it.
            data: {
              label: n.label,
              kind: n.kind,
              cloud,
              detail: n.detail,
            },
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
      /* The middle of the CANVAS, not of the window. Using window centre put
         the new box wherever that point happened to fall inside a pane that
         is inset by a 380px rail and a header -- so a service added while
         scrolled anywhere but the middle appeared far from where the reader
         was looking, or behind the palette that had just been used to add it. */
      const box = host.current?.getBoundingClientRect();
      const centre = rf.screenToFlowPosition(
        box
          ? { x: box.left + box.width / 2, y: box.top + box.height / 2 }
          : { x: window.innerWidth / 2, y: window.innerHeight / 2 },
      );
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

  /* Persist the arrangement.
     Debounced, because this fires on every frame of a drag and localStorage
     is synchronous -- writing per frame would put a disk round-trip inside
     the drag loop and make the canvas feel heavy, which is the one thing an
     editor cannot afford. The `selected` flag is stripped: restoring a sketch
     with three boxes mysteriously highlighted looks like a bug. */
  useEffect(() => {
    if (nodes.length === 0) return;
    const key = layoutKey(cloud, topoNodes, topoEdges);
    const timer = window.setTimeout(() => {
      try {
        window.localStorage.setItem(
          key,
          JSON.stringify({
            nodes: nodes.map((n) => ({ ...n, selected: false })),
            edges: edges.map((e) => ({ ...e, selected: false })),
          }),
        );
      } catch {
        // Quota exceeded, or storage disabled. Losing the save is survivable;
        // taking the editor down over it is not.
      }
    }, 400);
    return () => window.clearTimeout(timer);
  }, [nodes, edges, cloud, topoNodes, topoEdges]);

  /* Report what is selected so the workspace can offer a properties panel.
     React Flow tracks selection internally; without lifting it, "select a
     thing and change it" has nowhere to happen -- which is why the only edits
     available were drag, rename-by-double-click and delete. */
  useEffect(() => {
    const node = nodes.find((n) => n.selected);
    if (node) {
      const d = node.data as { label?: string };
      onSelectionChange?.({
        kind: node.type === "sketchGroup" ? "group" : node.type === "sketchText" ? "text" : "service",
        id: node.id,
        label: String(d.label ?? ""),
      });
      return;
    }
    const edge = edges.find((e) => e.selected);
    onSelectionChange?.(
      edge ? { kind: "edge", id: edge.id, label: String(edge.label ?? "") } : null,
    );
  }, [nodes, edges, onSelectionChange]);

  /* Commands from that panel. Kept as an imperative handle rather than more
     props because the panel lives outside the ReactFlowProvider -- it cannot
     reach useReactFlow, and threading a callback per action would mean a new
     prop for every future edit. */
  useEffect(() => {
    if (!command) return;
    if (command.type === "rename") {
      setNodes((all) =>
        all.map((n) =>
          n.id === command.id ? { ...n, data: { ...n.data, label: command.label } } : n,
        ),
      );
      setEdges((all) =>
        all.map((e) => (e.id === command.id ? { ...e, label: command.label } : e)),
      );
    }
    if (command.type === "delete") {
      setNodes((all) => all.filter((n) => n.id !== command.id));
      setEdges((all) =>
        all.filter(
          (e) => e.id !== command.id && e.source !== command.id && e.target !== command.id,
        ),
      );
    }
    onCommandDone?.();
  }, [command, setNodes, setEdges, onCommandDone]);

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

  /* The connect flag rides on each node's data so the handles can grow. Done
     here rather than written into state at seed time because the tool changes
     far more often than the graph does, and rewriting every node on each tool
     press would make dragging fight a re-render. */
  const painted = useMemo(
    () =>
      nodes.map((node) =>
        node.type === "sketchService"
          ? { ...node, data: { ...node.data, connecting: tool === "connect" } }
          : node,
      ),
    [nodes, tool],
  );

  return (
    <div ref={host} className="h-full w-full">
    <ReactFlow
      nodes={painted}
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
    </div>
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
  onSelectionChange?: (selection: Selection | null) => void;
  command?: Command | null;
  onCommandDone?: () => void;
}) {
  return (
    <ReactFlowProvider>
      <Inner {...props} />
    </ReactFlowProvider>
  );
}

export type { Tool as SketchTool };
