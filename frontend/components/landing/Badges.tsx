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
