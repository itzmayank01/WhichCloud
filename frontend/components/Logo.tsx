/**
 * The WhichCloud mark: a cloud sitting on a measured baseline.
 *
 * Nothing floats — everything is weighed against a line. Drawn on a 24×24
 * grid so it survives at favicon size.
 */
export function Mark({ className = "h-6 w-6" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      className={className}
      role="img"
      aria-label="WhichCloud"
    >
      <path
        d="M6.5 13.5 A3.5 3.5 0 0 1 7.4 6.6 A4.6 4.6 0 0 1 16.2 6.2 A3.6 3.6 0 0 1 17.6 13.5 Z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <rect x="3" y="17.5" width="18" height="3.5" rx="1.2" fill="var(--accent)" />
    </svg>
  );
}

export function Wordmark() {
  return (
    <span className="flex items-center gap-2.5">
      <Mark className="h-6 w-6 text-ink" />
      <span className="text-[19px] font-medium tracking-tight text-ink">
        Which<span className="text-accent">Cloud</span>
      </span>
    </span>
  );
}
