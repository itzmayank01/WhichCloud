"use client";

/**
 * The canvas tool rail.
 *
 * Every button here does something. A palette is the easiest place in an
 * interface to put a row of plausible-looking icons that are not wired to
 * anything, and the cost of doing that is not just the dead click -- it is
 * that the reader stops believing the buttons that do work. So the rail holds
 * exactly the actions the canvas actually supports, and grows when one is
 * built rather than in anticipation of it.
 */

type Tool = {
  id: string;
  label: string;
  icon: React.ReactNode;
  onSelect: () => void;
  /** Held down rather than pressed: inspect and ask are modes. */
  active?: boolean;
  disabled?: boolean;
};

function Divider() {
  return <span className="mx-auto h-px w-5 bg-line" aria-hidden />;
}

export function ToolRail({ tools }: { tools: (Tool | "divider")[] }) {
  return (
    <div
      role="toolbar"
      aria-orientation="vertical"
      aria-label="Diagram tools"
      className="pointer-events-auto flex flex-col gap-1 rounded-xl border border-line bg-surface/95 p-1.5 shadow-lg backdrop-blur"
    >
      {tools.map((tool, index) =>
        tool === "divider" ? (
          <Divider key={`divider-${index}`} />
        ) : (
          <button
            key={tool.id}
            type="button"
            title={tool.label}
            aria-label={tool.label}
            aria-pressed={tool.active}
            disabled={tool.disabled}
            onClick={tool.onSelect}
            className={`grid h-8 w-8 place-items-center rounded-lg transition-colors disabled:opacity-30 ${
              tool.active
                ? "bg-accent text-white"
                : "text-ink-2 hover:bg-sunk hover:text-ink"
            }`}
          >
            {tool.icon}
          </button>
        ),
      )}
    </div>
  );
}

/* ── icons ──
   Drawn here rather than pulled from a set: the rail needs five glyphs at one
   size and one stroke weight, and a dependency for that is more surface than
   it saves. */

const stroke = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export const ToolIcons = {
  cursor: (
    <svg viewBox="0 0 20 20" className="h-4 w-4" {...stroke} aria-hidden>
      <path d="M5 3l11 6.5-5 1.2-2.2 4.8z" />
    </svg>
  ),
  ask: (
    <svg viewBox="0 0 20 20" className="h-4 w-4" {...stroke} aria-hidden>
      <path d="M10 3l1.4 3.6L15 8l-3.6 1.4L10 13l-1.4-3.6L5 8l3.6-1.4z" />
      <path d="M15.5 12.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z" />
    </svg>
  ),
  replay: (
    <svg viewBox="0 0 20 20" className="h-4 w-4" {...stroke} aria-hidden>
      <path d="M16 10a6 6 0 11-1.8-4.3" />
      <path d="M16 3v3.2h-3.2" />
    </svg>
  ),
  fit: (
    <svg viewBox="0 0 20 20" className="h-4 w-4" {...stroke} aria-hidden>
      <path d="M3 7V4.5A1.5 1.5 0 014.5 3H7M13 3h2.5A1.5 1.5 0 0117 4.5V7M17 13v2.5a1.5 1.5 0 01-1.5 1.5H13M7 17H4.5A1.5 1.5 0 013 15.5V13" />
    </svg>
  ),
  expand: (
    <svg viewBox="0 0 20 20" className="h-4 w-4" {...stroke} aria-hidden>
      <path d="M12 3h5v5M8 17H3v-5M17 3l-6 6M3 17l6-6" />
    </svg>
  ),
  download: (
    <svg viewBox="0 0 20 20" className="h-4 w-4" {...stroke} aria-hidden>
      <path d="M10 3v9M6.5 8.5L10 12l3.5-3.5M4 15.5h12" />
    </svg>
  ),
  /** Enters sketch mode: a box with a handle, the shape of "rearrange this". */
  edit: (
    <svg viewBox="0 0 20 20" className="h-4 w-4" {...stroke} aria-hidden>
      <path d="M4 13.2V16h2.8l8-8-2.8-2.8z" />
      <path d="M12.6 4.4l1.4-1.4 2.8 2.8-1.4 1.4" />
    </svg>
  ),
  plus: (
    <svg viewBox="0 0 20 20" className="h-4 w-4" {...stroke} aria-hidden>
      <path d="M10 4.5v11M4.5 10h11" />
    </svg>
  ),
  box: (
    <svg viewBox="0 0 20 20" className="h-4 w-4" {...stroke} aria-hidden>
      <rect x="3.5" y="3.5" width="13" height="13" rx="1.5" strokeDasharray="3 2" />
    </svg>
  ),
  text: (
    <svg viewBox="0 0 20 20" className="h-4 w-4" {...stroke} aria-hidden>
      <path d="M4.5 5.5V4h11v1.5M10 4v12M7.5 16h5" />
    </svg>
  ),
  /** Connect two services. An actual arrow, because that is the word people
   *  use for it and the thing they look for in the rail. */
  arrow: (
    <svg viewBox="0 0 20 20" className="h-4 w-4" {...stroke} aria-hidden>
      <path d="M3.5 16.5L16 4" />
      <path d="M10.5 4H16v5.5" />
    </svg>
  ),
};
