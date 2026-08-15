"use client";

import { Icon } from "@iconify/react";

/**
 * The three providers WhichCloud reads prices from.
 *
 * Set as marks rather than names. The claim this section makes is that the
 * figures come from the providers themselves, and three words in the site's
 * own typeface look like a claim; the providers' own marks look like a
 * source. Rendered at published colours and never recoloured.
 */

const PROVIDERS = [
  { icon: "logos:aws", name: "Amazon Web Services", note: "Price List API" },
  { icon: "logos:microsoft-azure", name: "Microsoft Azure", note: "Retail Prices API" },
  { icon: "logos:google-cloud", name: "Google Cloud", note: "Cloud Billing Catalog" },
];

export function ProviderLogoCards() {
  return (
    <div className="mt-7 grid gap-4 sm:grid-cols-3">
      {PROVIDERS.map((p) => (
        <div
          key={p.name}
          className="flex flex-col items-center justify-center gap-3 rounded-xl border border-line bg-surface px-5 py-7 text-center transition-colors duration-150 hover:border-line-strong"
        >
          <Icon icon={p.icon} width={34} height={34} aria-hidden />
          <div>
            <div className="text-[15.5px] font-semibold tracking-[-0.01em] text-ink">
              {p.name}
            </div>
            {/* Naming the endpoint is the part that is checkable — it says
                which door the number came through, not merely whose logo
                sits above it. */}
            <div className="mt-1 font-mono text-[12.5px] font-medium text-ink-3">
              {p.note}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
