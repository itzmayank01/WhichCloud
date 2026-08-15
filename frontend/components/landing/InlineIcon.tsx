"use client";

import { Icon } from "@iconify/react";

/**
 * A brand mark set inline with text.
 *
 * Exists because Iconify renders on the client and the sections around it do
 * not, so this is the smallest possible boundary between the two rather than
 * making a whole section interactive to draw one logo.
 */
export function InlineIcon({
  icon,
  size = 16,
  className = "",
}: {
  icon: string;
  size?: number;
  className?: string;
}) {
  return (
    <Icon
      icon={icon}
      width={size}
      height={size}
      className={className}
      aria-hidden
    />
  );
}
