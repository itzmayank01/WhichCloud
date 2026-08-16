/**
 * The two tile badges that mark section labels.
 *
 * Drawn as vectors rather than set as emoji characters. An emoji is rendered
 * by the reader's own font, so the same character arrives as Apple's artwork
 * on a Mac, Microsoft's on Windows and Google's on Android -- three different
 * pictures, none of them in this site's palette, and all of them sitting on
 * the text baseline where a tile does not belong. These carry the page's own
 * accent and caution colours and stay sharp at any size.
 *
 * Both are decorative: the label beside them already says what the section is,
 * so they are hidden from screen readers rather than repeating it.
 */

function Tile({
  size,
  className,
  children,
}: {
  size: number;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`shrink-0 ${className ?? ""}`}
      aria-hidden
    >
      {children}
    </svg>
  );
}

/** Rising bars under a trend line — the cost comparison. */
export function ChartBadge({ size = 22, className }: { size?: number; className?: string }) {
  return (
    <Tile size={size} className={className}>
      <rect width="40" height="40" rx="11" fill="#DCE9FB" />
      <rect x="10.5" y="21.5" width="5" height="8" rx="1.8" fill="#3B82F6" />
      <rect x="17.5" y="17.5" width="5" height="12" rx="1.8" fill="#3B82F6" />
      <rect x="24.5" y="12.5" width="5" height="17" rx="1.8" fill="#3B82F6" />
      {/* The line reads as a trajectory over the bars, so it sits above them
          in a lighter weight rather than competing at the same density. */}
      <path
        d="M11 17.5 L20 13.5 L29 8.5"
        stroke="#93B4F7"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Tile>
  );
}

/**
 * The estimate panel's mark: a speech bubble with a rounded, lit body rather
 * than a flat outline on a tile.
 *
 * The depth is three cheap tricks, not a raster: a diagonal gradient down the
 * body, a soft white sheen across the top third, and a darker rim that only
 * covers the bottom and right edges. At 36px that is enough to read as a
 * rounded object; anything finer would be thrown away at this size.
 *
 * Gradient ids are namespaced because ids are global to the document -- a
 * second component defining "a" would silently repaint this one.
 */
export function ChatBubble3D({ size = 36, className }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`shrink-0 ${className ?? ""}`}
      aria-hidden
    >
      <defs>
        <linearGradient id="wc-bub-body" x1="6" y1="2" x2="34" y2="34" gradientUnits="userSpaceOnUse">
          <stop stopColor="#5A8BF7" />
          <stop offset="0.5" stopColor="#2F62E8" />
          <stop offset="1" stopColor="#1B3FC4" />
        </linearGradient>
        <linearGradient id="wc-bub-sheen" x1="20" y1="3" x2="20" y2="17" gradientUnits="userSpaceOnUse">
          <stop stopColor="#FFFFFF" stopOpacity="0.42" />
          <stop offset="1" stopColor="#FFFFFF" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="wc-bub-dot" x1="20" y1="10" x2="20" y2="18" gradientUnits="userSpaceOnUse">
          <stop stopColor="#FFFFFF" />
          <stop offset="1" stopColor="#DDE1EA" />
        </linearGradient>
      </defs>

      {/* Body and tail are one path so the gradient runs unbroken through the
          join instead of stopping at a seam. */}
      <path
        d="M9 3 H31 A7 7 0 0 1 38 10 V20 A7 7 0 0 1 31 27 H20.5 L12.6 35.4 A1.6 1.6 0 0 1 9.9 34.3 V27 H9 A7 7 0 0 1 2 20 V10 A7 7 0 0 1 9 3 Z"
        fill="url(#wc-bub-body)"
      />
      {/* Sheen, inset so it sits inside the body's edge rather than on it. */}
      <path
        d="M9.6 4 H30.4 A6.4 6.4 0 0 1 36.8 10.4 V15 A80 80 0 0 0 3.2 15 V10.4 A6.4 6.4 0 0 1 9.6 4 Z"
        fill="url(#wc-bub-sheen)"
      />
      {/* Lit rim: bottom and right only, which is what makes it read as round
          rather than as a shape with a border. */}
      <path
        d="M38 14 V20 A7 7 0 0 1 31 27 H20.5 L12.6 35.4"
        stroke="#12309B"
        strokeOpacity="0.28"
        strokeWidth="1.4"
        strokeLinecap="round"
        fill="none"
      />
      <circle cx="12.5" cy="14.5" r="3.3" fill="url(#wc-bub-dot)" />
      <circle cx="20" cy="14.5" r="3.3" fill="url(#wc-bub-dot)" />
      <circle cx="27.5" cy="14.5" r="3.3" fill="url(#wc-bub-dot)" />
    </svg>
  );
}

/**
 * The two side-panel marks, lit to match ChatBubble3D so the three panels
 * read as one set.
 *
 * Both light from the top left, so the gradient is declared in userSpaceOnUse
 * across the whole 40x40 box rather than per shape. Filling each bar from its
 * own objectBoundingBox gradient would light every bar identically and give
 * three light sources in one picture, which is the thing that makes an icon
 * look assembled rather than modelled.
 */

/** Rising bars, the cost comparison. */
export function ChartBars3D({ size = 36, className }: { size?: number; className?: string }) {
  const bars = [
    { x: 6.5, y: 21, h: 13 },
    { x: 16.5, y: 8, h: 26 },
    { x: 26.5, y: 25, h: 9 },
  ];
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`shrink-0 ${className ?? ""}`}
      aria-hidden
    >
      <defs>
        <linearGradient id="wc-bar-body" x1="6" y1="6" x2="34" y2="34" gradientUnits="userSpaceOnUse">
          <stop stopColor="#5A8BF7" />
          <stop offset="0.5" stopColor="#2F62E8" />
          <stop offset="1" stopColor="#1B3FC4" />
        </linearGradient>
      </defs>
      {bars.map((b) => (
        <g key={b.x}>
          <rect x={b.x} y={b.y} width="7" height={b.h} rx="2.6" fill="url(#wc-bar-body)" />
          {/* Lit cap, inset so it stops short of the rounded corner. */}
          <rect
            x={b.x + 1.1}
            y={b.y + 1.1}
            width="4.8"
            height="2.6"
            rx="1.3"
            fill="#FFFFFF"
            fillOpacity="0.34"
          />
          {/* Right edge only: the side facing away from the light. */}
          <rect
            x={b.x + 5.9}
            y={b.y + 2.4}
            width="1.1"
            height={b.h - 4.2}
            fill="#12309B"
            fillOpacity="0.22"
          />
        </g>
      ))}
    </svg>
  );
}

/** A line falling to the right, the saving. */
export function TrendDown3D({ size = 36, className }: { size?: number; className?: string }) {
  const LINE = "M5.5 11.5 L15.8 21.8 L22.4 15.2 L33 25.8";
  const HEAD = "M33 18.6 V25.8 H25.8";
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`shrink-0 ${className ?? ""}`}
      aria-hidden
    >
      <defs>
        <linearGradient id="wc-trend-body" x1="6" y1="8" x2="33" y2="30" gradientUnits="userSpaceOnUse">
          <stop stopColor="#5A8BF7" />
          <stop offset="0.5" stopColor="#2F62E8" />
          <stop offset="1" stopColor="#1B3FC4" />
        </linearGradient>
      </defs>
      {/* Three passes of the same path make the stroke read as a rounded bar:
          the underside first, then the body over it, then a sheen along the
          top. Offsetting rather than blurring keeps it crisp at 36px. */}
      <g transform="translate(0 0.9)" opacity="0.3">
        <path d={LINE} stroke="#12309B" strokeWidth="4.4" strokeLinecap="round" strokeLinejoin="round" />
        <path d={HEAD} stroke="#12309B" strokeWidth="4.4" strokeLinecap="round" strokeLinejoin="round" />
      </g>
      <path d={LINE} stroke="url(#wc-trend-body)" strokeWidth="4.4" strokeLinecap="round" strokeLinejoin="round" />
      <path d={HEAD} stroke="url(#wc-trend-body)" strokeWidth="4.4" strokeLinecap="round" strokeLinejoin="round" />
      <g transform="translate(0 -0.85)" opacity="0.36">
        <path d={LINE} stroke="#FFFFFF" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
      </g>
    </svg>
  );
}

/** A speech bubble around a star — the sentence you type, rated. */
export function AskBadge({ size = 22, className }: { size?: number; className?: string }) {
  return (
    <Tile size={size} className={className}>
      <rect width="40" height="40" rx="11" fill="#F7E8D0" />
      {/* Tail drawn before the body so the body's corner radius covers the
          join, leaving one silhouette instead of a visible seam. */}
      <path d="M13.5 24.5 L12.5 31.5 L20 25.5 Z" fill="#E4912E" />
      <rect x="8" y="9" width="24" height="18" rx="5.5" fill="#E4912E" />
      <path
        d="M20 12.8 L21.23 16.30 L24.95 16.39 L22.00 18.65 L23.06 22.21 L20 20.10 L16.94 22.21 L18.00 18.65 L15.05 16.39 L18.77 16.30 Z"
        fill="#FFFFFF"
      />
    </Tile>
  );
}
