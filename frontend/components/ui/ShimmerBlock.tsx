/**
 * The loading placeholder for a data-backed section, shared so every
 * section's "still loading" state looks the same and -- the part that
 * actually matters -- is visible.
 *
 * `bg-sunk` resolves to `--paper` in light mode, i.e. pure white: the same
 * colour as the page behind it. A block with a `animate-pulse` opacity
 * toggle on that background pulses between white and white, which reads as
 * a blank, broken section rather than a loading one, especially across a
 * cold Render backend's up-to-a-minute wake time. This shimmer uses a
 * translucent tint of `ink` over the block instead, so it stays visible in
 * both themes.
 */
export function ShimmerBlock({
  height,
  className = "",
}: {
  height: number;
  className?: string;
}) {
  return (
    <div
      className={`relative overflow-hidden rounded-xl border border-line bg-sunk ${className}`}
      style={{ height }}
      aria-hidden
    >
      <div
        className="absolute inset-0 animate-pulse bg-gradient-to-r from-transparent via-ink/5 to-transparent"
        style={{ animation: "whichcloud-shimmer 2s infinite" }}
      />
      <style>{`
        @keyframes whichcloud-shimmer {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
      `}</style>
    </div>
  );
}
