"use client";

import { useEffect, useState } from "react";
import type { Selection } from "@/components/workspace/SketchCanvas";

/**
 * What is selected, and what can be done to it.
 *
 * Without this the editor's only verbs were drag, double-click-to-rename and
 * delete -- all of them invisible, all of them things you had to be told. A
 * canvas that says "select a thing and change it" has to have somewhere for
 * the changing to happen, and a panel that names the selected element is also
 * the clearest possible confirmation that the click landed.
 *
 * Arrows get the same treatment as boxes on purpose: an editor where every
 * service can be edited and the lines between them cannot is one that stops
 * halfway, and connections are most of what makes a diagram mean anything.
 */

const WHAT: Record<Selection["kind"], string> = {
  service: "Service",
  group: "Boundary",
  text: "Label",
  edge: "Arrow",
};

export function SketchInspector({
  selection,
  onRename,
  onDelete,
}: {
  selection: Selection;
  onRename: (label: string) => void;
  onDelete: () => void;
}) {
  const [draft, setDraft] = useState(selection.label);

  // Re-seed when the selection moves to a different element, or the field
  // keeps showing the previous one's name over the new one's properties.
  useEffect(() => {
    setDraft(selection.label);
  }, [selection.id, selection.label]);

  const changed = draft !== selection.label;

  return (
    <div className="pointer-events-auto w-[270px] rounded-xl border border-line bg-surface/95 shadow-lg backdrop-blur">
      <div className="flex items-center gap-2 border-b border-line px-3.5 py-2.5">
        <span className="font-mono text-[10.5px] font-semibold uppercase tracking-wide text-ink-3">
          {WHAT[selection.kind]}
        </span>
      </div>

      <div className="flex flex-col gap-3 px-3.5 py-3">
        <label className="flex flex-col gap-1.5">
          <span className="text-[11.5px] font-medium text-ink-2">
            {selection.kind === "edge" ? "Arrow label" : "Name"}
          </span>
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") onRename(draft);
              // Stops Escape reaching the canvas, where it would close the
              // whole sketch while someone is mid-edit in a text field.
              if (event.key === "Escape") {
                event.stopPropagation();
                setDraft(selection.label);
              }
            }}
            placeholder={selection.kind === "edge" ? "unlabelled" : "Name"}
            className="rounded-lg border border-line bg-canvas px-2.5 py-1.5 text-[13px] text-ink outline-none placeholder:text-ink-3 focus:border-accent-line focus:ring-2 focus:ring-accent-wash"
          />
        </label>

        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={!changed}
            onClick={() => onRename(draft)}
            className="flex-1 rounded-lg bg-accent px-3 py-1.5 text-[12.5px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-30"
          >
            Rename
          </button>
          <button
            type="button"
            onClick={onDelete}
            title="Delete this element"
            className="rounded-lg border border-caution/40 px-3 py-1.5 text-[12.5px] font-medium text-caution transition-colors hover:bg-caution-wash"
          >
            Delete
          </button>
        </div>

        <p className="text-[11px] leading-relaxed text-ink-3">
          {selection.kind === "edge"
            ? "Deleting an arrow leaves both services in place."
            : "Deleting also removes the arrows attached to it."}
        </p>
      </div>
    </div>
  );
}
