/* ── Colours for a stacked chart ──
   The existing --cat-1..5 ramp is sequential: five tints of one blue,
   made for ordered magnitude. A cost chart stacks up to ten unordered
   groups, and a ramp makes neighbouring bands indistinguishable exactly
   where a reader is trying to tell two services apart.

   These are mid-tone rather than pastel or dark, so one set stays legible
   on both the light and dark surfaces instead of needing a per-theme
   palette that then has to be kept in sync. */

export const SERIES_COLORS = [
  "#3d6fb5", // blue
  "#d9822b", // amber
  "#3f9e6a", // green
  "#a659c4", // violet
  "#d4585b", // red
  "#2f9aa8", // teal
  "#b5883d", // ochre
  "#7a72c9", // periwinkle
  "#5c9c3f", // olive
  "#c45f95", // magenta
];

/** Everything past the chart's cut, folded into one band. Deliberately
 *  grey: "Other" is a bucket, not a group, and giving it a hue of its own
 *  would let it read as a service somebody could go and look at. */
export const OTHER_COLOR = "#8b95a3";

export function seriesColor(key: string, index: number): string {
  return key === "Other" ? OTHER_COLOR : SERIES_COLORS[index % SERIES_COLORS.length];
}
