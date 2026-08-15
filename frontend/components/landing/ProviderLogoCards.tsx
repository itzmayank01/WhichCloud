"use client";

import { Icon } from "@iconify/react";

/**
 * The three providers WhichCloud reads prices from.
 *
 * Set as marks rather than names. The claim this section makes is that the
 * figures come from the providers themselves, and three words in the site's
 * own typeface look like a claim; the providers' own marks look like a
 * source. Rendered at published colours and never recoloured.
 *
 * The lockup is horizontal — mark beside a two-line wordmark — because that
 * is how each of these companies sets its own, and a logo row that follows
 * the conventions of the logos in it reads as borrowed authority rather than
 * decoration.
 */

const PROVIDERS = [
  { icon: "logos:aws", top: "Amazon", bottom: "Web Services" },
  { icon: "logos:microsoft-azure", top: "Microsoft", bottom: "Azure" },
  { icon: "logos:google-cloud", top: "Google", bottom: "Cloud" },
];

export function ProviderLogoCards() {
  return (
    <div className="mt-8 grid gap-5 sm:grid-cols-3">
      {PROVIDERS.map((p) => (
        <div
          key={p.top}
          /* White against the section's grey band. The reference sets grey
             cards on white; inverted here for the same reason — the card has
             to separate from what is behind it, and this band is already
             grey. */
          className="flex items-center justify-center gap-4 rounded-2xl border border-line/70 bg-surface px-6 py-8 shadow-[0_1px_2px_rgba(11,13,18,.04)]"
        >
          <Icon icon={p.icon} width={46} height={46} aria-hidden />
          <span className="text-left text-[20px] font-medium leading-[1.18] tracking-[-0.015em] text-ink-2">
            {p.top}
            <br />
            {p.bottom}
          </span>
        </div>
      ))}
    </div>
  );
}
