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

/**
 * Official HashiCorp Terraform brand mark:
 * 4 isometric facets rendered with authentic HashiCorp brand colors:
 * #5C4EE5 (primary violet) and #4040B2 (deep cobalt accent facet).
 */
export function TerraformLogo({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 128 128"
      className={className}
      aria-hidden="true"
      fill="none"
    >
      <g fillRule="evenodd">
        {/* Center facet */}
        <path
          d="M77.941 44.5v36.836L46.324 62.918V26.082zm0 0"
          fill="#5C4EE5"
        />
        {/* Top-right accent facet */}
        <path
          d="M81.41 81.336l31.633-18.418V26.082L81.41 44.5zm0 0"
          fill="#4040B2"
        />
        {/* Leftmost facet & Bottom facet */}
        <path
          d="M11.242 42.36L42.86 60.776V23.941L11.242 5.523zm0 0M77.941 85.375L46.324 66.957v36.82l31.617 18.418zm0 0"
          fill="#5C4EE5"
        />
      </g>
    </svg>
  );
}

