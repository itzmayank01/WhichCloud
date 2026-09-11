/* ── The cost report's query layer ──
   Filtering, grouping and date binning, kept apart from the interface so
   the arithmetic can be tested without rendering anything.

   One invariant governs all of it: REGROUPING NEVER MOVES MONEY. The
   server hands back cells that are already disjoint on all four axes, so
   every subtotal here is a sum over a partition rather than a fresh
   estimate. Any view of a bill must add up to the same bill. */

import type { CostRow } from "./api";

export type Dimension = "service" | "region" | "resource_type";

export const DIMENSIONS: { id: Dimension; label: string }[] = [
  { id: "service", label: "Service" },
  { id: "region", label: "Region" },
  { id: "resource_type", label: "Resource type" },
];

/** Kept small on purpose. Vantage ships six operators including regex;
 *  these four cover what a person actually reaches for, and each one is
 *  unambiguous about what it does to a row. */
export type Operator = "is" | "is not" | "contains" | "does not contain";

export const OPERATORS: Operator[] = ["is", "is not", "contains", "does not contain"];

export type Filter = {
  id: string;
  dimension: Dimension;
  operator: Operator;
  /** Multiple values are OR'd within one filter, and filters are AND'd
   *  with each other — the behaviour people expect from faceted search,
   *  where picking a second region widens rather than narrows. */
  values: string[];
};

export type DateBin = "day" | "week" | "month";

/** The label a dimension's empty string gets. The server sends "" for a
 *  dimension the export did not state, and it has to stay visible: the
 *  money is real even where the label is missing, and dropping the row
 *  would make the chart disagree with the bill. */
export const UNLABELLED = "Not specified";

export function label(row: CostRow, dimension: Dimension): string {
  return row[dimension] || UNLABELLED;
}

function matches(row: CostRow, filter: Filter): boolean {
  if (filter.values.length === 0) return true;   // an empty filter is not a filter
  const value = label(row, filter.dimension).toLowerCase();
  const hit = filter.values.some((candidate) => {
    const needle = candidate.toLowerCase();
    return filter.operator === "is" || filter.operator === "is not"
      ? value === needle
      : value.includes(needle);
  });
  return filter.operator === "is not" || filter.operator === "does not contain"
    ? !hit
    : hit;
}

export function applyFilters(rows: CostRow[], filters: Filter[]): CostRow[] {
  const active = filters.filter((f) => f.values.length > 0);
  if (active.length === 0) return rows;
  return rows.filter((row) => active.every((filter) => matches(row, filter)));
}

/** Every distinct value on one axis, with its spend, largest first — what
 *  the filter menus offer. Built from the rows still standing under the
 *  OTHER filters, so the menu never offers a value that would return an
 *  empty report. */
export function facet(
  rows: CostRow[],
  dimension: Dimension,
  filters: Filter[],
  self?: string,
): { value: string; monthly_usd: number }[] {
  const others = filters.filter((f) => f.id !== self);
  const totals = new Map<string, number>();
  for (const row of applyFilters(rows, others)) {
    const key = label(row, dimension);
    totals.set(key, (totals.get(key) ?? 0) + row.monthly_usd);
  }
  return [...totals.entries()]
    .map(([value, monthly_usd]) => ({ value, monthly_usd }))
    .sort((a, b) => b.monthly_usd - a.monthly_usd);
}

/* ── time ── */

/** The Monday of a day's week. ISO weeks, so a chart binned weekly does
 *  not shift its buckets depending on which day the export starts. */
function weekStart(day: string): string {
  const date = new Date(`${day}T00:00:00Z`);
  const weekday = (date.getUTCDay() + 6) % 7;         // Monday = 0
  date.setUTCDate(date.getUTCDate() - weekday);
  return date.toISOString().slice(0, 10);
}

/** The day after a bucket's last, so a bucket's span is [start, end). */
function bucketEnd(start: string, size: DateBin): string {
  const date = new Date(`${start}T00:00:00Z`);
  if (size === "month") date.setUTCMonth(date.getUTCMonth() + 1);
  else if (size === "week") date.setUTCDate(date.getUTCDate() + 7);
  else date.setUTCDate(date.getUTCDate() + 1);
  return date.toISOString().slice(0, 10);
}

/** Which buckets the export does not fully cover.
 *
 * Only the ends can be partial: a gap in the middle is a real day with no
 * spend, and flagging it would claim missing data where there is none.
 * Daily bins are never flagged — a billing export's finest unit is a day,
 * so a day present in it is a day it covers. */
function partialBuckets(
  buckets: string[], size: DateBin, first: string, last: string,
): boolean[] {
  // The ends among DATED buckets, not among all of them. An export with
  // undated rows puts an empty bucket at index 0, which displaced the end
  // check and left a genuinely clipped first week unflagged.
  const dated = buckets.map((b, i) => (b ? i : -1)).filter((i) => i >= 0);
  if (dated.length === 0) return buckets.map(() => false);
  const [head, tail] = [dated[0], dated[dated.length - 1]];

  return buckets.map((bucket, i) => {
    if (!bucket || size === "day") return false;
    if (i !== head && i !== tail) return false;
    return bucket < first || bucketEnd(bucket, size) > bucketEnd(last, "day");
  });
}

export function bin(day: string, size: DateBin): string {
  if (!day) return "";
  if (size === "month") return `${day.slice(0, 7)}-01`;
  if (size === "week") return weekStart(day);
  return day;
}

export function hasDates(rows: CostRow[]): boolean {
  return rows.some((row) => row.day !== "");
}

/* ── grouping ── */

export type Series = {
  key: string;
  total: number;
  /** Spend per time bucket, aligned to `buckets` below. Zero where the
   *  group was not billed in that bucket — an absent point and a zero are
   *  different claims, and a line chart has to draw the second. */
  points: number[];
};

export type Grouped = {
  buckets: string[];
  /** Aligned to `buckets`: true where the bucket's full span is not
   *  covered by the export. A week holding two billed days draws as a
   *  short bar, which reads as a spending drop rather than as a week the
   *  data does not cover — so the chart has to say which is which. */
  partial: boolean[];
  series: Series[];
  total: number;
  /** Groups past the cut, folded into one row. Never dropped: the chart
   *  has to keep adding up to the bill. */
  otherCount: number;
};

/** Rows folded onto one dimension and one time bin, ranked by spend.
 *  Everything past `limit` becomes a single "Other" series rather than
 *  disappearing, because a chart that quietly omits the tail understates
 *  every total drawn beside it. */
export function group(
  rows: CostRow[],
  dimension: Dimension,
  size: DateBin,
  limit = 10,
): Grouped {
  const buckets = [...new Set(rows.map((r) => bin(r.day, size)))].sort();
  const index = new Map(buckets.map((b, i) => [b, i]));
  const days = rows.map((r) => r.day).filter(Boolean).sort();
  const partial = days.length
    ? partialBuckets(buckets, size, days[0], days[days.length - 1])
    : buckets.map(() => false);

  const totals = new Map<string, number>();
  for (const row of rows) {
    const key = label(row, dimension);
    totals.set(key, (totals.get(key) ?? 0) + row.monthly_usd);
  }
  const ranked = [...totals.entries()].sort((a, b) => b[1] - a[1]);
  const kept = new Set(ranked.slice(0, limit).map(([key]) => key));
  const otherCount = Math.max(0, ranked.length - limit);

  const series = new Map<string, Series>();
  const ensure = (key: string) => {
    let existing = series.get(key);
    if (!existing) {
      existing = { key, total: 0, points: new Array(buckets.length).fill(0) };
      series.set(key, existing);
    }
    return existing;
  };
  for (const [key] of ranked) if (kept.has(key)) ensure(key);

  for (const row of rows) {
    const raw = label(row, dimension);
    const target = ensure(kept.has(raw) ? raw : OTHER);
    target.total += row.monthly_usd;
    const at = index.get(bin(row.day, size));
    if (at !== undefined) target.points[at] += row.monthly_usd;
  }

  const ordered = [...series.values()].sort((a, b) =>
    a.key === OTHER ? 1 : b.key === OTHER ? -1 : b.total - a.total,
  );
  return {
    buckets,
    partial,
    series: ordered,
    total: rows.reduce((sum, row) => sum + row.monthly_usd, 0),
    otherCount,
  };
}

export const OTHER = "Other";

/** What a bill is trending toward, by the mean of the buckets drawn.
 *  Deliberately not a regression: a few days of one export cannot support
 *  a slope, and a projection with a trend line reads as a forecast the
 *  data does not justify. */
export function projectedMonth(grouped: Grouped, size: DateBin): number | null {
  const drawn = grouped.buckets.filter((b) => b !== "");
  if (drawn.length < 2 || size !== "day") return null;
  const perDay = grouped.total / drawn.length;
  return perDay * 30.4;
}

/** The app's one money formatter, re-exported so the report's modules
 *  import it from here alongside everything else they need. Defining a
 *  second one was the first thing I did and the wrong thing: two
 *  formatters drift, and the same figure rendering as $438.20 in a table
 *  and $438 in the chart beside it reads as two different numbers. */
export { money } from "./api";

/** Axis ticks only, where a rounded label is the point: a gridline
 *  reading $1,200 is easier to scan than $1,200.00, and the exact figure
 *  is one hover away in the tooltip. */
export function axisMoney(value: number): string {
  return `$${Math.round(value).toLocaleString("en-US")}`;
}
